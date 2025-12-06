from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser, Patient
from .utils import initialize_africas_talking
import re

# -------------------------------
# Helper functions for SMS
# -------------------------------

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
        print(f"SMS sent to {formatted_phone_number}: {message}")
        return response
    except Exception as e:
        print(f"Failed to send SMS: {str(e)}")
        return {"error": str(e)}

# -------------------------------
# Notification functions
# -------------------------------

def send_registration_notification(patient):
    try:
        phone_number = patient.phone_number
        message = (
            f"Dear {patient.name}, you have been registered successfully! "
            f"Your queue position is {patient.queue_number}. Thank you!"
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
            f"Your current position is {patient.queue_number}. Please wait for further updates. Thank you!"
        )
        response = send_sms_notification(phone_number, message)
        print(f"Queue update notification sent to {phone_number}: {message}")
        return response
    except Exception as e:
        print(f"Failed to send queue update: {str(e)}")
        return {"error": str(e)}

# -------------------------------
# Signal handlers
# -------------------------------

@receiver(post_save, sender=CustomUser)
def manage_patient_profile(sender, instance, created, **kwargs):
    if created and instance.role == 'patient':
        patient = Patient.objects.create(name=instance.username, phone_number=instance.phone_number)
        send_registration_notification(patient)
    elif hasattr(instance, 'patient'):
        instance.patient.save()
        send_queue_update_notification(instance.patient)

@receiver(post_save, sender=Patient)
def notify_patient_on_change(sender, instance, created, **kwargs):
    if created:
        send_registration_notification(instance)
    else:
        send_queue_update_notification(instance)

def notify_all_patients_in_queue(queue):
    for patient in queue.patients.all():
        send_queue_update_notification(patient)
