import csv
import json
import logging
import re
from datetime import datetime

import requests
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.serializers import serialize
from django.db import IntegrityError
from django.db import transaction
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import get_template
from django.urls import reverse
from django.utils.timezone import make_aware
from django_daraja.mpesa.core import MpesaClient
from xhtml2pdf import pisa

from .models import Appointment
from .models import Patient, Doctor, CustomUser, Department, PatientRecord, Payment
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
        phone_number = request.POST.get('phone_number', '').strip()

        logger.debug(f"Captured Form Data - Username: {username}, Email: {email}, Role: {role}, Phone: {phone_number}")

        if not all([username, email, role, password, phone_number]):
            messages.error(request, "All fields are required, including phone number.")
            return render(request, 'signup.html', {
                'username': username,
                'email': email,
                'role': role,
            })

        try:
            phone_number = format_phone_number(phone_number)
        except ValueError as e:
            logger.error(f"Phone Number Formatting Failed: {e}")
            messages.error(request, "Invalid phone number. Please use the format +254XXXXXXXXX.")
            return render(request, 'signup.html', {
                'username': username,
                'email': email,
                'role': role,
            })

        if CustomUser.objects.filter(username=username).exists():
            messages.error(request, f"Username '{username}' is already taken. Please choose a different username.")
            return render(request, 'signup.html')

        try:

            user = CustomUser.objects.create(
                username=username,
                email=email,
                role=role,
            )
            user.set_password(password)
            user.save()

            if role == 'patient':
                with transaction.atomic():

                    existing_patient = Patient.objects.filter(name=username, phone_number=phone_number).first()

                    if existing_patient:
                        existing_patient.in_queue = True
                        existing_patient.hidden = False
                        existing_patient.save()
                        logger.info(f"Updated Patient: {existing_patient.name}, Queue Position: {existing_patient.queue_number}")
                    else:

                        new_queue_number = get_next_queue_number()

                        Patient.objects.create(
                            name=username,
                            phone_number=phone_number,
                            queue_number=new_queue_number,
                            in_queue=True,
                            hidden=False,
                        )
                        logger.info(f"New Patient Created: {username}, Queue Position: {new_queue_number}")

            messages.success(request, "Account created successfully! You can now log in.")
            return redirect('login')

        except Exception as e:
            logger.error(f"Error during signup: {e}")
            messages.error(request, "An error occurred during registration. Please try again.")
            return render(request, 'signup.html', {'username': username, 'email': email, 'role': role})

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
    phone_number = phone_number.strip()

    if not phone_number.startswith("+254"):
        phone_number = "+254" + phone_number.lstrip("0")

    if not validate_phone_number(phone_number):
        raise ValueError(f"Invalid formatted phone number: {phone_number}")

    return phone_number

def send_sms_notification(phone_number, message):
    try:

        sms = initialize_africas_talking()

        if not validate_phone_number(phone_number):
            raise ValueError(f"Invalid phone number: {phone_number}")
        formatted_phone_number = format_phone_number(phone_number)


        response = sms.send(message, [formatted_phone_number], sender_id="NazarethQMS")
        print(f"SMS sent to {formatted_phone_number} using Sender ID 'NazarethQMS': {message}")

        return response

    except Exception as e:

        print(f"Failed to send SMS: {str(e)}")
        return {"error": str(e)}


def send_registration_notification(patient):
    try:
        phone_number = patient.phone_number
        message = (
            f"Dear {patient.name}, you have been registered successfully! "
            f"Your queue position is {patient.queue_number}. "
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


# .................................#
# PATIENT VIEWS                   #
# .................................#


logger = logging.getLogger(__name__)


def register_patient(request):
    if request.method == "POST":
        try:
            sms = initialize_africas_talking()

            with transaction.atomic():
                # Extract form data
                name = request.POST.get('name', '').strip()
                age = request.POST.get('age', '').strip()
                gender = request.POST.get('gender', '').strip()
                service = request.POST.get('service', '').strip()
                department_id = request.POST.get('department', '').strip()
                phone_number = request.POST.get('phone_number', '').strip()

                # Ensure required fields are provided
                if not all([name, age, gender, department_id, phone_number]):
                    raise ValueError("Name, age, gender, department, and phone number are required fields.")

                # Priority mapping
                priority_map = {"1": "low", "2": "medium", "3": "high"}
                priority = priority_map.get(request.POST.get('priority'))
                if not priority:
                    raise ValueError("Invalid priority selected")

                # Retrieve department
                department = Department.objects.get(id=department_id)
                logger.info(f"Selected Department: {department.name}")

                # Check for existing patient
                existing_patient = Patient.objects.filter(
                    name=name, department=department, phone_number=phone_number
                ).first()

                if existing_patient:
                    logger.warning(
                        f"Existing patient found: {existing_patient.name}, Queue Position: {existing_patient.queue_number}"
                    )
                    # Update `in_queue` to True and assign a queue number if needed
                    if not existing_patient.in_queue:
                        existing_patient.in_queue = True
                        if existing_patient.queue_number is None:
                            last_queue = Patient.objects.filter(in_queue=True).order_by('-queue_number').first()
                            queue_position = last_queue.queue_number + 1 if last_queue else 1
                            existing_patient.queue_number = queue_position
                        existing_patient.save()
                    messages.warning(
                        request, f"Patient '{name}' is already registered and has been updated."
                    )
                    return redirect('patient_list')

                # Assign a queue number for new patients
                last_queue = Patient.objects.filter(in_queue=True).order_by('-queue_number').first()
                queue_position = last_queue.queue_number + 1 if last_queue else 1

                # Create new patient
                patient = Patient.objects.create(
                    name=name,
                    age=int(age),
                    gender=gender,
                    phone_number=phone_number,
                    department=department,
                    priority=priority,
                    in_queue=True,
                    queue_number=queue_position,
                )
                logger.info(f"Created Patient: {patient}, Queue Position: {queue_position}")

                # Create or update patient record
                patient_record, created = PatientRecord.objects.update_or_create(
                    patient=patient,
                    defaults={
                        'service': service,
                        'priority': priority,
                        'department': department,
                    }
                )
                logger.info(f"Created/Updated PatientRecord: {patient_record}")

                # Cleanup invalid patients
                invalid_patients = Patient.objects.filter(queue_number=None, in_queue=False)
                logger.info(f"Cleaning up invalid patient records: {invalid_patients.count()}")
                invalid_patients.delete()

            # Send SMS notification
            message = f"Dear {name}, you have been successfully registered. Your queue position is {queue_position}."
            sms.send(message, [phone_number])
            logger.info(f"SMS Sent to {phone_number}: {message}")
            messages.success(request, f"Patient '{name}' registered successfully.")
            return redirect('patient_list')

        except Exception as e:
            logger.error(f"Error during registration: {e}")
            messages.error(request, "An error occurred during registration. Please try again.")
            return render(request, 'register_patient.html', {'departments': Department.objects.all()})

    # Render registration page
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
        try:
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

            # Save patient
            patient.save()
            messages.success(request, "Patient details updated successfully.")

            # Cleanup invalid patients
            invalid_patients = Patient.objects.filter(queue_number=None, in_queue=False)
            invalid_patients.delete()
            logger.info(f"Cleaned up {invalid_patients.count()} invalid patient records.")

            return redirect('patient_list')

        except Exception as e:
            logger.error(f"Error during patient edit: {e}")
            messages.error(request, "An error occurred while updating patient details.")
            return render(request, 'edit_patient.html', {
                'patient': patient,
                'departments': Department.objects.all(),
                'priorities': priorities,
                'statuses': statuses,
            })

    # Render edit page
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
    patients = Patient.objects.prefetch_related('queues').select_related('department').filter(in_queue=True,
                                                                                              hidden=False)

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

def get_next_queue_number():
    last_patient = Patient.objects.order_by('-queue_number').first()
    if last_patient:
        return last_patient.queue_number + 1
    return 1


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

        invalid_patients = Patient.objects.filter(queue_number=None, in_queue=False)
        invalid_patients.delete()

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

        # Fetch queue position
        response = requests.get(f'http://127.0.0.1:8000/get_queue_position/?name={patient_name}')
        if response.status_code == 200:
            data = response.json()
            queue_position = data.get('queue_position', 'N/A')
        else:
            queue_position = "N/A"

        appointments = Appointment.objects.filter(patient=request.user).order_by('date')


        doctors = Doctor.objects.all()

        context = {
            'name': patient_name,
            'appointments': appointments,
            'queue_number': queue_position,
            'doctors': doctors,
            'department': "N/A",
            'priority': "N/A",
            'status': "N/A",
        }

        return render(request, 'patient.html', context)
    except Exception as e:
        logger.error(f"Error fetching patient data: {e}")
        context = {
            'name': request.user.username,
            'appointments': [],
            'queue_number': "N/A",
            'doctors': [],
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


logger = logging.getLogger(__name__)

def notify_patient(request, patient_id):
    try:

        patient = Patient.objects.get(id=patient_id)
        patient_name = patient.name
        patient_phone = patient.phone_number
        doctor_name = f"Dr. {patient.assigned_doctor.name}" if patient.assigned_doctor else "the doctor"


        message = f"Dear {patient_name}, {doctor_name} is ready for you."
        logger.info(f"Sending SMS to {patient_phone}: {message}")


        sms = initialize_africas_talking()
        try:
            response = sms.send(
                message=message,
                recipients=[patient_phone],
                sender_id='NazarethQMS'
            )
            logger.info(f"SMS sent successfully to {patient_phone}: {response}")
            print(f"Notification to {patient_name}: {message}")
        except Exception as sms_error:
            logger.error(f"Failed to send SMS to {patient_phone}: {sms_error}")
            messages.error(request, f"Failed to send SMS: {sms_error}")
            return redirect('patient_doctor')

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

# .................................#
# REPORT GENERATION VIEWS          #
# .................................#

def report_view(request):

    data = CustomUser.objects.all()
    return render(request, 'report_view.html', {'data': data})

def generate_full_report(request, report_type='csv'):
    if report_type == 'pdf':
        # Generate PDF report
        template = get_template('report_view.html')
        context = {
            'patients': Patient.objects.all(),
            'payments': Payment.objects.all(),
            'users': CustomUser.objects.all()
        }
        html = template.render(context)

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="full_report.pdf"'
        pisa_status = pisa.CreatePDF(html.encode('UTF-8'), dest=response)

        if pisa_status.err:
            return HttpResponse("PDF generation failed!")
        return response

    elif report_type == 'csv':
        # Generate CSV report
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="full_report.csv"'

        writer = csv.writer(response)
        writer.writerow(['Report Type', 'Field 1', 'Field 2', 'Field 3'])

        # Add Patient Data
        writer.writerow(['Patients'])
        writer.writerow(['Name', 'Phone Number', 'Queue Number', 'In Queue'])
        for patient in Patient.objects.all():
            writer.writerow([patient.name, patient.phone_number, patient.queue_number, patient.in_queue])

        # Add Payment Data
        writer.writerow([])
        writer.writerow(['Payments'])
        writer.writerow(['Amount', 'Payment Date', 'Patient ID'])
        for payment in Payment.objects.all():
            writer.writerow([payment.amount, payment.date, payment.patient_id])

        return response

    # Fallback if no report_type specified
    return HttpResponse("Invalid report type!")

def download_records_view(request):
    patient = request.user
    records = f"Name: {patient.name}\nQueue Position: {patient.queue_position}\nDiagnostics: Normal"
    response = HttpResponse(records, content_type='text/plain')
    response['Content-Disposition'] = 'attachment; filename="patient_records.txt"'
    return response



# .................................#
# APPOINTMENTS VIEWS               #
# .................................#

@login_required
def book_appointment_view(request):
    if request.method == 'POST':
        try:
            # Extract form data
            contact_phone = request.POST.get('phone')
            contact_email = request.POST.get('email')
            date_str = request.POST.get('date')  # Date string from the form
            doctor_id = request.POST.get('doctor')
            reason = request.POST.get('reason')

            # Handle different datetime formats
            try:
                # Attempt to parse with seconds
                naive_date = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                # Fallback to parsing without seconds
                naive_date = datetime.strptime(date_str, "%Y-%m-%dT%H:%M")

            aware_date = make_aware(naive_date)  # Make datetime timezone-aware

            # Fetch doctor and create appointment
            doctor = Doctor.objects.get(id=doctor_id)
            appointment = Appointment.objects.create(
                patient=request.user,
                contact_phone=contact_phone,
                contact_email=contact_email,
                date=aware_date,
                doctor=doctor,
                reason=reason,
            )
            return JsonResponse({'message': 'Appointment booked successfully!'})

        except Doctor.DoesNotExist:
            return JsonResponse({'error': 'Selected doctor does not exist.'}, status=400)
        except Exception as e:
            return JsonResponse({'error': f'Error booking appointment: {e}'}, status=400)

    return JsonResponse({'error': 'Invalid request method.'}, status=400)


def contact_doctor_view(request):
    if request.method == 'POST':
        patient = request.user
        message = request.POST.get('message')

        # Handle messaging logic (e.g., save to database, send email)
        return JsonResponse({'message': 'Message sent successfully!'})

@login_required
def doctor_appointments_view(request):

    if hasattr(request.user, 'role') and request.user.role == "Doctor":
        appointments = Appointment.objects.filter(doctor__customuser=request.user).order_by('date')
    else:
        appointments = []

    context = {
        'appointments': appointments,
    }
    return render(request, 'doctor.html', context)

@login_required
def doctor_appointments_api(request):
    if request.user.is_authenticated and getattr(request.user, 'role', '').lower() == "doctor":
        appointments = Appointment.objects.filter(doctor__name=request.user.username).order_by('date')

        data = [
            {
                'patient_name': appointment.patient.name,
                'contact': appointment.patient.phone_number,
                'date': appointment.date.strftime('%Y-%m-%d %H:%M:%S'),
                'reason': appointment.reason,
            }
            for appointment in appointments
        ]
        return JsonResponse(data, safe=False)
    else:
        return JsonResponse({'error': 'Access denied. You must be logged in as a Doctor.'}, status=403)
