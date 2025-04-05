from django.core.management.base import BaseCommand
from django.utils import timezone
from Nazareth.models import CustomUser , Patient

class Command(BaseCommand):
    help = 'Create multiple patients'

    def handle(self, *args, **kwargs):
        # List of patients to create with empty fields
        patients_data = [
            {
                'username': '',  # Fill in the username later
                'password': '',  # Fill in the password later
                'name': '',      # Fill in the name later
                'age': None,     # Fill in the age later
                'gender': '',    # Fill in the gender later
                'service': '',   # Fill in the service later
                'priority': '',  # Fill in the priority later
                'department': '', # Fill in the department later
                'phone_number': '', # Fill in the phone number later
            },
            {
                'username': '',  # Fill in the username later
                'password': '',  # Fill in the password later
                'name': '',      # Fill in the name later
                'age': None,     # Fill in the age later
                'gender': '',    # Fill in the gender later
                'service': '',   # Fill in the service later
                'priority': '',  # Fill in the priority later
                'department': '', # Fill in the department later
                'phone_number': '', # Fill in the phone number later
            },
            # Add more patients as needed
        ]

        for patient_data in patients_data:
            # Create a new CustomUser
            user = CustomUser .objects.create_user(
                username=patient_data['username'],
                password=patient_data['password'],
                role='patient'
            )

            # Create a new Patient record associated with the CustomUser
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
            patient.save()  # Save the patient record to the database

            self.stdout.write(self.style.SUCCESS(f'Successfully created patient {patient_data["name"]}'))