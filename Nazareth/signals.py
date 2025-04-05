from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser , Patient
from .views import send_registration_notification, send_queue_update_notification

@receiver(post_save, sender=CustomUser)
def manage_patient_profile(sender, instance, created, **kwargs):
    if created and instance.role == 'patient':
        # Create a new Patient profile when a new patient user is created
        patient = Patient.objects.create(
            name=instance.username  # Assuming username matches the patient name
        )
        send_registration_notification(patient)  # Send registration notification
    elif hasattr(instance, 'patient'):
        # Save the patient profile if it exists
        instance.patient.save()
        send_queue_update_notification(instance.patient)  # Notify on update

@receiver(post_save, sender=Patient)
def notify_patient_on_change(sender, instance, created, **kwargs):
    if created:  # If it's a new patient
        send_registration_notification(instance)
    else:
        send_queue_update_notification(instance)

def notify_all_patients_in_queue(queue):
    for patient in queue.patients.all():
        send_queue_update_notification(patient)