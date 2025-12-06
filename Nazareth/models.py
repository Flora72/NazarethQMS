from django.db import models
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.timezone import now
from django.db.models import Max
import logging


class CustomUserManager(BaseUserManager):
    def create_user(self, username, email, password=None, **extra_fields):
        if not username:
            raise ValueError("The Username must be set")
        if not email:
            raise ValueError("The Email must be set")

        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')

        if extra_fields.get('role') != 'admin':
            raise ValueError('Superuser must have role set to "admin".')

        return self.create_user(username, email, password, **extra_fields)


class CustomUser(AbstractUser):
    password = models.CharField(max_length=128)
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('doctor', 'Doctor'),
        ('receptionist', 'Receptionist'),
        ('patient', 'Patient'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='patient')
    phone_number = models.CharField(max_length=15, blank=True, null=True)

    objects = CustomUserManager()

    def __str__(self):
        return self.username



class Department(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Doctor(models.Model):
    name = models.CharField(max_length=100)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None
    )

    def __str__(self):
        return f"Dr. {self.name} ({self.department.name if self.department else 'N/A'})"

    class Meta:
        ordering = ['name']


logger = logging.getLogger(__name__)
class Patient(models.Model):
    assigned_doctor = models.ForeignKey(
        'Doctor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="patients"
    )
    name = models.CharField(max_length=100)
    age = models.PositiveIntegerField(null=True, blank=True)
    gender = models.CharField(
        max_length=10,
        choices=[
            ('male', 'Male'),
            ('female', 'Female'),
            ('other', 'Other'),
        ],
    )
    service = models.CharField(max_length=50)
    priority = models.CharField(
        max_length=10,
        choices=[
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
        ],
    )
    department = models.ForeignKey(
        'Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="patients"
    )
    in_queue = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    queue_number = models.IntegerField(null=True, blank=True)
    date_registered = models.DateTimeField(default=now)
    phone_number = models.CharField(max_length=20)
    status = models.CharField(
        max_length=20,
        choices=[
            ('waiting', 'Waiting'),
            ('in_queue', 'In Queue'),
            ('in_process', 'In Process'),
            ('completed', 'Completed'),
            ('under_observation', 'Under Observation'),
            ('discharged', 'Discharged'),
        ],
        default='in_queue'
    )
    hidden = models.BooleanField(default=False)

    def save(self, *args, **kwargs):

        if self.in_queue and self.queue_number is None:
            max_queue_number = Patient.objects.aggregate(Max('queue_number'))['queue_number__max']
            self.queue_number = (max_queue_number or 0) + 1
            logger.info(f"Assigned queue number: {self.queue_number} to patient {self.name}")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} (Queue: {self.queue_number}, Status: {self.status}, Department: {self.department.name if self.department else 'None'})"

    def update_status(self, new_status):
        if new_status not in dict(self._meta.get_field('status').choices):
            raise ValueError(f"Invalid status: {new_status}")
        self.status = new_status
        self.save()

    class Meta:
        ordering = ['queue_number']


class PatientRecord(models.Model):
    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name="records"
    )
    service = models.CharField(
        max_length=50,
        choices=[
            ("general", "General Consultation"),
            ("specialist", "Specialist"),
            ("diagnostics", "Diagnostics"),
        ],
    )
    priority = models.CharField(
        max_length=10,
        choices=[
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
        ],
        null=False,
        blank=False
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="patient_records"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.patient.name} - {self.service} - {self.priority.capitalize()} Priority - {self.department.name}"


class Queue(models.Model):
    PRIORITY_CHOICES = [
        (1, 'Low'),
        (2, 'Medium'),
        (3, 'High'),
    ]

    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="queues"
    )
    service_type = models.CharField(max_length=50, null=False, blank=False)
    patients = models.ManyToManyField(Patient, related_name="queues", blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('waiting', 'Waiting'),
            ('in_queue', 'In Queue'),
            ('in_process', 'In Process'),
            ('completed', 'Completed'),
            ('under_observation', 'Under Observation'),
            ('discharged', 'Discharged'),
        ],
        default='in_queue'
    )
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=2)

    def __str__(self):
        return f"{self.department.name if self.department else 'No Department'} - {self.service_type} - {self.get_priority_display()}"


class Payment(models.Model):
    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name="payments"
    )
    services = models.TextField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(
        max_length=20,
        choices=[('cash', 'Cash'), ('card', 'Card'), ('insurance', 'Insurance')]
    )
    payment_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment by {self.patient.name} - {self.amount} KES"


class QueueAdmin(admin.ModelAdmin):
    list_display = ('department', 'service_type', 'status', 'priority', 'patients_display')

    def patients_display(self, obj):
        return ", ".join([patient.name for patient in obj.patients.all()])

    patients_display.short_description = 'Patients'


admin.site.register(Queue, QueueAdmin)


class PaymentAdmin(admin.ModelAdmin):
    list_display = ('patient', 'amount', 'payment_method', 'payment_date')


admin.site.register(Payment, PaymentAdmin)


class Appointment(models.Model):
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        default=1
    )

    contact_phone = models.CharField(max_length=20, null=True, blank=True)
    contact_email = models.EmailField(null=True, blank=True)
    date = models.DateTimeField()
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    reason = models.TextField()

    def __str__(self):
        return f"Appointment with {self.doctor.name} on {self.date} for {self.patient.username}"
