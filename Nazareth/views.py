import logging
import re
import secrets
import string
import requests
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.serializers import serialize
from django.db import IntegrityError
from django.db import transaction
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django_daraja.mpesa.core import MpesaClient
import json
from django.http import HttpResponse
from .models import Patient, Queue, Doctor, CustomUser, Department, PatientRecord
from .utils import initialize_africas_talking


# .................................#
# GENERAL VIEWS                   #
# .................................#
def index(request):
    return render(request, 'index.html')

# .................................#
# AUTHENTICATION VIEWS            #
# .................................#

logger = logging.getLogger(__name__)

def signup_view(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        role = request.POST.get('role', '').strip()
        password = request.POST.get('pass', '').strip()

        if not all([username, email, role, password]):
            messages.error(request, "All fields are required.")
            return render(request, 'signup.html', {
                'username': username,
                'email': email,
                'role': role,
            })

        # CHECK POINT FOR THE EXISTENCE OF A USER
        if CustomUser.objects.filter(username=username).exists():
            messages.error(request, "Username already taken.")
            return render(request, 'signup.html')

        try:


            # CREATING THE USER

            user = CustomUser.objects.create(
                username=username,
                email=email,
                role=role,
            )
            user.set_password(password)
            user.save()

            # Handle patients
            if role == 'patient':
                with transaction.atomic():

                    existing_patient = Patient.objects.filter(name=username, queue_number__isnull=False).first()

                    if existing_patient:
                        logger.info(
                            f"Existing Patient Found: {existing_patient.name}, Queue Position: {existing_patient.queue_number}")

                        existing_patient.in_queue = True
                        existing_patient.save()
                    else:

                        last_patient = Patient.objects.filter(in_queue=True).order_by('-queue_number').first()
                        new_queue_number = last_patient.queue_number + 1 if last_patient else 1

                        Patient.objects.create(
                            name=username,
                            queue_number=new_queue_number,
                            in_queue=True,
                            hidden=True,
                        )
                        logger.info(f"New Patient Created: {username}, Queue Position: {new_queue_number}")

            messages.success(request, "Account created successfully! You can now log in.")
            return redirect('login')

        except Exception as e:
            logger.error(f"Error during signup: {e}")
            messages.error(request, "An error occurred during registration.")
            return render(request, 'signup.html')

    return render(request, 'signup.html')

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('pass', '').strip()


        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)


            if user.role == 'patient':
                return redirect('patient')
            elif user.role in ['doctor', 'receptionist', 'admin']:
                return redirect(f'{user.role}')
            else:
                messages.error(request, "Invalid role. Please contact support.")
                return redirect('login')
        else:
            messages.error(request, "Invalid username or password.")
            return render(request, 'login.html')

    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect('index')


# .................................#
# SMS VIEWS                       #
# .................................#
def validate_phone_number(phone_number):
    return bool(re.match(r'^\+254\d{9}$', phone_number))


def format_phone_number(phone_number):
    if not phone_number.startswith("+"):
        phone_number = "+254" + phone_number.lstrip("0")
    return phone_number

def generate_random_password(length=8):
    """
    Generates a secure random password.
    """
    characters = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(characters) for _ in range(length))

def send_sms_notification(phone_number, message):

    try:
        # Initialize the SMS service
        sms = initialize_africas_talking()

        # Validate and format the phone number
        if not validate_phone_number(phone_number):
            raise ValueError(f"Invalid phone number: {phone_number}")
        formatted_phone_number = format_phone_number(phone_number)

        # Send the SMS
        response = sms.send(message, [formatted_phone_number], sender_id="NazarethQMS")
        print(f"SMS sent to {formatted_phone_number} using Sender ID 'NazarethQMS': {message}")

        return response

    except Exception as e:
        # Handle any exceptions that occur
        print(f"Failed to send SMS: {str(e)}")
        return {"error": str(e)}

def send_registration_notification(patient):

    try:

        if not patient.temp_password:
            patient.temp_password = generate_random_password()
            patient.save()


        phone_number = patient.phone_number
        temp_password = patient.temp_password
        message = (
            f"Dear {patient.name}, you have been registered successfully! "
            f"Your queue position is {patient.queue_number}. "
            f"Login details: Temporary Password: {temp_password}. "
            "Thank you!"
        )
        response = send_sms_notification(phone_number, message)
        print(f"Registration notification sent to {phone_number}: {message}")
        return response
    except Exception as e:
        print(f"Failed to send registration notification: {str(e)}")
        return {"error": str(e)}

def send_queue_update_notification(patient):

    try:

        phone_number = patient.phone_number
        message = (
            f"Dear {patient.name}, your queue position has been updated! "
            f"Your current position is {patient.queue_number}. Please wait for further updates. "
            "Thank you!"
        )

        # Send SMS
        response = send_sms_notification(phone_number, message)
        print(f"Queue update notification sent to {phone_number}: {message}")
        return response
    except Exception as e:
        print(f"Failed to send queue update: {str(e)}")
        return {"error": str(e)}


def send_login_details(phone_number, username, temp_password):

    try:
        if not phone_number or phone_number.strip() == "":
            raise ValueError("Invalid phone number.")

        message = (
            f"Dear {username}, you have been registered successfully! "
            f"Login details: Username: {username}, Password: {temp_password}. "
            "Thank you!"
        )
        send_sms_notification(phone_number, message)
    except Exception as e:
        print(f"Failed to send login details: {str(e)}")


# .................................#
# PATIENT VIEWS                   #
# .................................#

logger = logging.getLogger(__name__)

def register_patient(request):
    if request.method == "POST":
        try:
            sms = initialize_africas_talking()

            with transaction.atomic():

                name = request.POST.get('name')
                age = int(request.POST.get('age'))
                gender = request.POST.get('gender')
                service = request.POST.get('service')
                department_id = request.POST.get('department')
                phone_number = request.POST.get('phone_number')


                priority_map = {"1": "low", "2": "medium", "3": "high"}
                priority = priority_map.get(request.POST.get('priority'))
                if not priority:
                    raise ValueError("Invalid priority selected")


                department = Department.objects.get(id=department_id)
                logger.info(f"Selected Department: {department.name}")


                existing_patient = Patient.objects.filter(name=name, department=department).first()

                if existing_patient:
                    logger.info(f"Existing Patient Found: {existing_patient.name}, Queue Position: {existing_patient.queue_number}")
                    patient = existing_patient
                else:

                    patient = Patient.objects.create(
                        name=name,
                        age=age,
                        gender=gender,
                        phone_number=phone_number,
                        department=department,
                        priority=priority,
                        in_queue=True
                    )
                    logger.info(f"Created Patient: {patient}")


                if patient.queue_number is None:
                    last_queue = Queue.objects.filter(department=department).order_by('-id').first()
                    queue_position = last_queue.id + 1 if last_queue else 1
                    patient.queue_number = queue_position
                    patient.save()
                    logger.info(f"Assigned Queue Position: {queue_position}")


                patient_record, created = PatientRecord.objects.update_or_create(
                    patient=patient,
                    defaults={
                        'service': service,
                        'priority': priority,
                        'department': department,
                    }
                )
                logger.info(f"Created/Updated PatientRecord: {patient_record}")


            message = f"Dear {name}, you have been successfully registered. Your queue position is {patient.queue_number}."
            sms.send(message, [phone_number])
            logger.info(f"SMS Sent to {phone_number}: {message}")

            return redirect('patient_list')

        except Exception as e:
            logger.error(f"Error during registration: {e}")
            messages.error(request, "An error occurred during registration. Please try again.")
            return render(request, 'register_patient.html', {'departments': Department.objects.all()})

    return render(request, 'register_patient.html', {'departments': Department.objects.all()})



def get_patient_list(request):
    patients = Patient.objects.filter(in_queue=True).order_by('queue_number')
    patient_data = serialize('json', patients)
    return JsonResponse({'patients': patient_data})


def patient_add(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        priority = request.POST.get('priority')
        status = request.POST.get('status')

        Patient.objects.create(name=name, priority=priority, doctor=doctor, status=status)
        messages.success(request, 'Patient added successfully!')
        return redirect('patient_list')
    else:

        return render(request, 'patient.html')

def patient_edit(request, id):
    patient = get_object_or_404(Patient, id=id)
    priorities = ['High', 'Medium', 'Low']
    statuses = ['in_queue', 'waiting', 'under_observation', 'discharged']

    if request.method == 'POST':
        department_name = request.POST.get('department')
        if department_name:
            try:

                department = Department.objects.get(name=department_name)
                patient.department = department
            except Department.DoesNotExist:
                messages.error(request, "Invalid department selected.")
                return render(request, 'edit_patient.html', {
                    'patient': patient,
                    'departments': Department.objects.all(),
                    'priorities': priorities,
                    'statuses': statuses,
                })

        # Update other patient fields
        patient.name = request.POST.get('name', patient.name)
        patient.age = request.POST.get('age', patient.age)
        patient.gender = request.POST.get('gender', patient.gender)
        patient.priority = request.POST.get('priority', patient.priority)
        patient.phone_number = request.POST.get('phone_number', patient.phone_number)
        patient.status = request.POST.get('status', patient.status)

        patient.save()
        messages.success(request, "Patient details updated successfully.")
        return redirect('patient_list')


    return render(request, 'edit_patient.html', {
        'patient': patient,
        'departments': Department.objects.all(),
        'priorities': priorities,
        'statuses': statuses,
    })


def update_patient_status(request, id):
    if request.method == 'POST':
        patient = get_object_or_404(Patient, id=id)
        new_status = request.POST.get('status')
        valid_statuses = ['waiting', 'in_queue', 'in_process', 'completed']
        if new_status not in valid_statuses:
            return JsonResponse({'error': 'Invalid status'}, status=400)

        if new_status:
            patient.status = new_status
            patient.save()
            return redirect('patient_list')
        else:
            return JsonResponse({'error': 'Invalid status'}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=400)


def patient_list(request):
    patients = Patient.objects.prefetch_related('queues').select_related('department').filter(in_queue=True, hidden=False)

    for patient in patients:
        queue = patient.queues.order_by('priority').first()
        patient.queue_status = queue.status if queue else "No Queue"

    return render(request, "patient_list.html", {"patients": patients})


def create_patient(name, age, gender, phone_number, service, priority, department_id):
    try:
        # Validate inputs
        if not name or not isinstance(name, str):
            raise ValueError("Patient name must be a non-empty string.")
        if not age or not isinstance(age, int) or age <= 0:
            raise ValueError("Patient age must be a positive integer.")
        if gender not in ['male', 'female', 'other']:
            raise ValueError("Invalid gender value. Must be 'male', 'female', or 'other'.")

        with transaction.atomic():
            department = Department.objects.get(id=department_id)

            patient = Patient.objects.create(
                name=name,
                age=age,
                gender=gender,
                phone_number=phone_number,
                service=service,
                priority=priority,
                department=department,
                status="in_queue"
            )

            return patient

    except Department.DoesNotExist:
        raise ValueError("Invalid department ID. Department not found.")
    except IntegrityError:
        raise ValueError("Database error occurred during patient creation.")
    except Exception as e:
        raise ValueError(f"An unexpected error occurred: {e}")


# .................................#
# QUEUE MANAGEMENT VIEWS          #
#       &                         #
#       QUEUE VIEWS               #
# .................................#
def queue_management(request):

    patients = Patient.objects.filter(in_queue=True).order_by('queue_number')
    doctors = Doctor.objects.all()

    return render(request, 'queue_management.html', {'patients': patients, 'doctors': doctors})

def get_queue_position(request):
    name = request.GET.get('name', '').strip()
    try:

        patient = Patient.objects.filter(name=name, queue_number__isnull=False).first()

        if patient:
            return JsonResponse({'queue_position': patient.queue_number})
        else:
            return JsonResponse({'error': 'Patient not found or no queue position available'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def get_queue_status(request):
    patients = Patient.objects.prefetch_related('queues').all()

    for patient in patients:
        queues = patient.queues.all()
        if queues.exists():
            patient.queue_status = queues.first().status
        else:
            patient.queue_status = "No Queue"

    return render(request, "patient_list.html", {"patients": patients, "no_patients": not patients})


def queue_update_api(request):
    queues = {}
    patients = Patient.objects.all().order_by('queue_number')

    for patient in patients:
        category = patient.category
        if category not in queues:
            queues[category] = []

        queues[category].append({
            "id": patient.id,
            "queue_number": patient.queue_number,
            "name": patient.name,
            "priority": patient.priority,
        })

    queues_data = [{"category": cat, "category_slug": cat.lower().replace(" ", "-"), "patients": data} for cat, data in
                   queues.items()]

    return JsonResponse({"queues": queues_data})

def patient_delete(request, patient_id):
    if request.method == "POST":
        patient = get_object_or_404(Patient, id=patient_id)
        patient.delete()
        remaining_patients = Patient.objects.filter(in_queue=True).order_by('queue_number')
        for index, patient in enumerate(remaining_patients, start=1):
            patient.queue_number = index
            patient.save()

        messages.success(request, "Patient deleted successfully.")
        return redirect('queue_management')

    messages.error(request, "Invalid request method.")
    return redirect('queue_management')


def move_patient(request, queue_number, direction):
    patient = get_object_or_404(Patient, queue_number=queue_number)

    if direction == 'up':
        above_patient = Patient.objects.filter(queue_number=queue_number - 1).first()
        if above_patient:
            above_patient.queue_number += 1
            patient.queue_number -= 1
            above_patient.save()
            patient.save()
    elif direction == 'down':
        below_patient = Patient.objects.filter(queue_number=queue_number + 1).first()
        if below_patient:
            below_patient.queue_number -= 1
            patient.queue_number += 1
            below_patient.save()
            patient.save()

    return redirect('queue_management')


def clear_patient(request, queue_number):
    if request.method == 'POST':
        patient = get_object_or_404(Patient, queue_number=queue_number)
        patient.in_queue = False
        patient.save()

        messages.success(request, f"Patient {patient.name} cleared successfully.")
        return redirect('queue_management')

    messages.error(request, "Invalid request method.")
    return redirect('queue_management')


def assign_patient(request, patient_id):
    if request.method == 'POST':
        patient = get_object_or_404(Patient, id=patient_id)
        doctor_name = request.POST.get('doctor_name')

        if not doctor_name or doctor_name.strip() == "":
            messages.error(request, "Doctor name is required. Please select a valid doctor.")
            return redirect('queue_management')

        doctor = get_object_or_404(Doctor, name=doctor_name.strip())

        try:

            patient.assigned_doctor = doctor
            patient.save()


            messages.success(request, f"Patient '{patient.name}' has been successfully assigned to Dr. {doctor.name}.")
            return redirect('queue_management')
        except Exception as e:
            # Error message
            messages.error(request, f"An error occurred while assigning the doctor: {str(e)}")
            return redirect('queue_management')


    messages.error(request, "Invalid request method. Please use POST for doctor assignment.")
    return redirect('queue_management')


# .................................#
# PAYMENT VIEWS                   #
# .................................#
def payments(request):
    patients = Patient.objects.filter(in_queue=True).order_by('name')

    consultation_fee = 100


    if request.method == 'POST':
        patient_id = request.POST.get('patient')
        amount = request.POST.get('amount')

        if not patient_id or not amount:
            return render(request, 'payments.html', {
                'error_message': "Please select a patient and enter a valid amount.",
                'patients': patients,
                'consultation_fee': consultation_fee,
            })

        try:
            amount = int(amount)
        except ValueError:
            return render(request, 'payments.html', {
                'error_message': "Amount must be a valid integer.",
                'patients': patients,
                'consultation_fee': consultation_fee,
            })

        patient = get_object_or_404(Patient, id=patient_id)
        phone_number = patient.phone_number
        cl = MpesaClient()

        personalized_message = (
            f"Dear {patient.name}, your consultation fee of Kshs {amount} "
            "will be paid to Nazareth Hospital. Thank you!"
        )

        try:
            mpesa_response = cl.stk_push(
                phone_number,
                amount,
                f'reference-{patient_id}',
                personalized_message,
                'https://darajambili.herokuapp.com/express-payment'
            )
        except Exception as e:
            return render(request, 'payments.html', {
                'error_message': f"Payment initiation failed: {str(e)}",
                'patients': patients,
                'consultation_fee': consultation_fee,
            })

        sms_message = (
            f"Dear {patient.name}, your consultation fee of Kshs {amount} has been initiated. "
            "Please check your M-Pesa app to complete the transaction. Thank you!"
        )
        try:
            sms_response = send_sms_notification(phone_number, sms_message)
            if "error" in sms_response:
                return render(request, 'payments.html', {
                    'error_message': f"Payment was initiated, but SMS failed: {sms_response['error']}",
                    'patients': patients,
                    'consultation_fee': consultation_fee,
                })
        except Exception as sms_error:
            print(f"Failed to send SMS: {str(sms_error)}")
            return render(request, 'payments.html', {
                'error_message': f"Payment was initiated, but SMS failed: {str(sms_error)}",
                'patients': patients,
                'consultation_fee': consultation_fee,
            })

        request.session['success_message'] = (
            f"Payment of KES {amount} for {patient.name} successfully initiated! Please check your phone."
        )
        return redirect(reverse('process_payment'))

    return render(request, 'payments.html', {'patients': patients, 'consultation_fee': consultation_fee})


def stk_push_callback(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            print("STK Push Callback Data:", data)

            result_code = data.get('Body', {}).get('stkCallback', {}).get('ResultCode')
            result_desc = data.get('Body', {}).get('stkCallback', {}).get('ResultDesc')
            amount = data.get('Body', {}).get('stkCallback', {}).get('CallbackMetadata', {}).get('Item', [{}])[0].get(
                'Value', None)
            receipt_number = data.get('Body', {}).get('stkCallback', {}).get('CallbackMetadata', {}).get('Item', [{}])[
                1].get('Value', None)


            if result_code == 0:
                print(f"Payment successful: Amount {amount}, Receipt {receipt_number}")

            else:
                print(f"Payment failed: {result_desc}")


            return HttpResponse("Callback received successfully!", status=200)
        except json.JSONDecodeError:
            print("Invalid JSON received in STK callback.")
            return HttpResponse("Invalid JSON format", status=400)

    return HttpResponse("Only POST requests are allowed", status=405)


def process_payment(request):
    if request.method == 'POST':
        patient_name = request.POST.get('patient', 'Unknown Patient')
        services = request.POST.get('services', 'No services specified')
        amount = request.POST.get('amount', '0')
        payment_method = request.POST.get('payment_method', 'Not specified')


        print(f'Payment processed for {patient_name}: {services} - KES {amount} via {payment_method}')


        return render(request, 'process_payment.html', {
            'patient_name': patient_name,
            'amount': amount,
            'services': services,
            'payment_method': payment_method,
        })

    return render(request, 'process_payment.html', status=404)


# .................................#
# DASHBOARD VIEWS                 #
# .................................#

@login_required
def doctor(request):
    return render(request, 'doctor.html')


@login_required
def receptionist(request):
    patients = Patient.objects.all()
    return render(request, 'receptionist.html')

logger = logging.getLogger(__name__)
@login_required
def patient(request):
    try:
        patient_name = request.user.username
        response = requests.get(f'http://127.0.0.1:8000/get-queue-position/?name={patient_name}')

        if response.status_code == 200:
            data = response.json()
            queue_position = data.get('queue_position', 'N/A')

            context = {
                'name': patient_name,
                'queue_number': queue_position,
                'department': "N/A",
                'priority': "N/A",
                'status': "N/A",
            }
        else:
            logger.warning(f"Unable to fetch queue position for {patient_name}: {response.json()}")
            context = {
                'name': patient_name,
                'queue_number': "N/A",
                'department': "N/A",
                'priority': "N/A",
                'status': "N/A",
            }

        return render(request, 'patient.html', context)

    except Exception as e:
        logger.error(f"Error fetching patient data: {e}")
        context = {
            'name': request.user.username,
            'queue_number': "N/A",
        }
        return render(request, 'patient.html', context)


# .................................#
# DOCTOR VIEWS                    #
# .................................#
def patient_doctor(request):
    patients = Patient.objects.filter(in_queue=True).order_by('queue_number')
    return render(request, 'patient_doctor.html', {'patients': patients})


def doctor_patient_list(request, doctor_id):
    doctor = get_object_or_404(Doctor, id=doctor_id)

    patients = Patient.objects.filter(assigned_doctor=doctor, in_queue=True).order_by('queue_number')

    return render(request, 'patient_doctor.html', {
        'doctor': doctor,
        'patients': patients,
    })


def call_next_patient(request, doctor_id):
    if request.method == 'POST':
        doctor = get_object_or_404(Doctor, id=doctor_id)

        next_patient = Patient.objects.filter(
            assigned_doctor=doctor, in_queue=True
        ).order_by('queue_number').first()

        if not next_patient:
            return JsonResponse({'error': 'No patients in the queue.'})
        message = (
            f"Dear {next_patient.name}, you are next in line to see Dr. {doctor.name}. "
            f"Please proceed to the {doctor.department.name} department."
        )
        send_sms_notification(next_patient.phone_number, message)

        next_patient.in_queue = False
        next_patient.save()

        return JsonResponse({'success': True, 'patient_name': next_patient.name})

    return JsonResponse({'error': 'Invalid request method.'})


def notify_patient(request, patient_id):

    try:
        patient = Patient.objects.get(id=patient_id)
        patient_name = patient.name
        patient_phone = patient.phone_number
        doctor_name = f"Dr. {patient.assigned_doctor.name}" if patient.assigned_doctor else "the doctor"

        message = f"Dear {patient_name}, {doctor_name} is ready for you."

        logger.info(f"Sending SMS to {patient_phone}: {message}")
        print(f"Notification to {patient_name}: {message}")

        messages.success(request, f"Notification sent to {patient_name}.")

        return redirect('patient_doctor')

    except Patient.DoesNotExist:
        logger.error(f"Patient with ID {patient_id} does not exist.")
        messages.error(request, "Patient not found.")
        return redirect('patient_doctor')

    except Exception as e:
        logger.error(f"Error occurred while notifying patient {patient_id}: {e}")
        messages.error(request, f"Error occurred: {str(e)}")
        return redirect('patient_doctor')


def mark_patient_seen(request, patient_id):
    if request.method == 'POST':
        patient = get_object_or_404(Patient, id=patient_id)

        patient.status = 'discharged'
        patient.save()

        messages.success(request, f"Patient {patient.name} has been marked as discharged.")

        return redirect('doctor')

    messages.error(request, "Invalid request method.")
    return redirect('doctor')

def filter_patients(request):
    department_name = request.GET.get('department')
    if department_name:

        patients = Patient.objects.filter(department__name=department_name)
    else:

        patients = Patient.objects.all()


    departments = Department.objects.all()

    context = {
        'patients': patients,
        'departments': departments,
    }
    return render(request, 'patient_doctor.html', context)


def mark_next_patient(request, id):
    patient = get_object_or_404(Patient, id=id)
    patient.status = 'In Progress'
    patient.save()
    return redirect('queue_status')
