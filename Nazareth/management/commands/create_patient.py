from django.core.management.base import BaseCommand
from django.utils import timezone
from Nazareth.models import CustomUser , Patient

class Command(BaseCommand):
    help = 'Create multiple patients'

    def handle(self, *args, **kwargs):
        patients_data = [
            {
                'username': '',
                'password': '',
                'name': '',
                'age': None,
                'gender': '',
                'service': '',
                'priority': '',
                'department': '',
                'phone_number': '',
            },
            {
                'username': '',
                'password': '',
                'name': '',
                'age': None,
                'gender': '',
                'service': '',
                'priority': '',
                'department': '',
                'phone_number': '',
            },

        ]

        for patient_data in patients_data:

            user = CustomUser .objects.create_user(
                username=patient_data['username'],
                password=patient_data['password'],
                role='patient'
            )


            patient = Patient(
                user=user,
                name=patient_data['name'],
                age=patient_data['age'],
                gender=patient_data['gender'],
                service=patient_data['service'],
                priority=patient_data['priority'],
                department=patient_data['department'],
                phone_number=patient_data['phone_number'],
                date_registered=timezone.now()
            )
            patient.save()

            self.stdout.write(self.style.SUCCESS(f'Successfully created patient {patient_data["name"]}'))