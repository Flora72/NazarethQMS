from django.contrib import admin
from .models import Patient, Doctor, Department, Payment, Queue, CustomUser
from django.http import HttpResponse
import csv
from django.urls import path
from .views import report_view, generate_full_report



def generate_csv_report(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{modeladmin.model._meta.model_name}_report.csv"'

    writer = csv.writer(response)

    if modeladmin.model._meta.model_name == "customuser":
        writer.writerow(['Username', 'Email', 'Role'])
        for obj in queryset:
            writer.writerow([obj.username, obj.email, obj.role])

    elif modeladmin.model._meta.model_name == "department":
        writer.writerow(['Department Name', 'Department ID'])
        for obj in queryset:
            writer.writerow([obj.name, obj.id])

    elif modeladmin.model._meta.model_name == "patient":
        writer.writerow([
            'Patient Name',
            'Age',
            'Gender',
            'Phone Number',
            'Department',
            'Status',
            'Queue Number',
            'Date Registered'
        ])
        for obj in queryset:
            writer.writerow([
                obj.name,
                obj.age if obj.age else 'N/A',
                obj.gender.capitalize() if obj.gender else 'N/A',
                obj.phone_number,
                obj.department.name if obj.department else 'N/A',
                obj.status.replace('_', ' ').capitalize(),
                obj.queue_number if obj.queue_number else 'N/A',
                obj.date_registered.strftime('%Y-%m-%d %H:%M:%S')
            ])

    elif modeladmin.model._meta.model_name == "doctor":
        writer.writerow(['Doctor Name', 'Department'])
        for obj in queryset:
            writer.writerow([obj.name, obj.department.name if obj.department else 'N/A'])

    elif modeladmin.model._meta.model_name == "payment":
        writer.writerow(['Payment ID', 'Patient', 'Amount', 'Status', 'Date'])
        for obj in queryset:
            writer.writerow([
                obj.id,
                obj.patient.name if obj.patient else "N/A",
                obj.amount,
                obj.status,
                obj.date.strftime('%Y-%m-%d') if obj.date else "N/A"
            ])

    elif modeladmin.model._meta.model_name == "queue":
        writer.writerow(['Queue Position', 'Patient', 'Department', 'Date'])
        for obj in queryset:
            writer.writerow([
                obj.position,
                obj.patient.name if obj.patient else "N/A",
                obj.department.name if obj.department else "N/A",
                obj.date.strftime('%Y-%m-%d') if obj.date else "N/A"
            ])

    else:
        writer.writerow(['ID', 'Name'])
        for obj in queryset:
            writer.writerow([obj.id, getattr(obj, 'name', 'N/A')])

    return response


class PatientAdmin(admin.ModelAdmin):
    actions = [generate_csv_report]


class DoctorAdmin(admin.ModelAdmin):
    actions = [generate_csv_report]


class DepartmentAdmin(admin.ModelAdmin):
    actions = [generate_csv_report]


class PaymentAdmin(admin.ModelAdmin):
    actions = [generate_csv_report]


class QueueAdmin(admin.ModelAdmin):
    actions = [generate_csv_report]


class CustomUserAdmin(admin.ModelAdmin):
    actions = [generate_csv_report]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('report/', self.admin_site.admin_view(report_view)),
        ]
        return custom_urls + urls


class CustomAdminSite(admin.AdminSite):
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('generate-full-report/', self.admin_view(generate_full_report), name='generate-full-report'),
        ]
        return custom_urls + urls


custom_admin_site = CustomAdminSite(name='custom_admin')
custom_admin_site.register(Patient, PatientAdmin)
custom_admin_site.register(Doctor, DoctorAdmin)
custom_admin_site.register(Department, DepartmentAdmin)
custom_admin_site.register(Payment, PaymentAdmin)
custom_admin_site.register(Queue, QueueAdmin)
custom_admin_site.register(CustomUser, CustomUserAdmin)
