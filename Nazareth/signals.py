from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser , Patient
from .views import send_registration_notification, send_queue_update_notification

@receiver(post_save, sender=CustomUser)
def manage_patient_profile(sender, instance, created, **kwargs):
    if created and instance.role == 'patient':

        patient = Patient.objects.create(
            name=instance.username
        )
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