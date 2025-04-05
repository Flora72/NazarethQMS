from django.contrib import admin
from .models import Patient, Queue, Payment, Doctor, Department

# Registering models in the admin interface
admin.site.register(Patient)
admin.site.register(Queue)
admin.site.register(Payment)
admin.site.register(Doctor)
admin.site.register(Department)
