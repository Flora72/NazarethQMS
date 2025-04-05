from django.urls import path
from . import views



urlpatterns = [
 path('', views.index, name='index'),
path('daraja/stk_push', views.stk_push_callback, name='stk_push_callback'),
 path('doctor/', views.doctor, name='doctor'),
 path('patient/', views.patient, name='patient'),
 path('receptionist/', views.receptionist, name='receptionist'),
 path('login/', views.login_view, name='login'),
 path('signup/', views.signup_view, name='signup'),
 path('register_patient/', views.register_patient, name='register_patient'),
 path('queue-management/', views.queue_management, name='queue_management'),
 path('patient_list/', views.patient_list, name='patient_list'),
 path('patient_doctor/', views.patient_doctor, name='patient_doctor'),
  path('process_payment/', views.process_payment, name='process_payment'),

 path('patient_doctor/<int:doctor_id>/', views.doctor_patient_list, name='doctor_patient_list'),
path('doctor/call-next/<int:doctor_id>/', views.call_next_patient, name='call_next_patient'),
path('mark-patient-seen/<int:patient_id>/', views.mark_patient_seen, name='mark_patient_seen'),
path('notify-patient/<int:patient_id>/', views.notify_patient, name='notify_patient'),
 path('patient/add/', views.patient_add, name='patient_add'),
 path('queue_management/', views.queue_management, name='queue_management'),
 path('filter-patients/', views.filter_patients, name='filter_patients'),
 path('move_patient/<int:queue_number>/<str:direction>/', views.move_patient, name='move_patient'),
    path('clear-patient/<int:queue_number>/', views.clear_patient, name='clear_patient'),
    path('assign_patient/<int:patient_id>/', views.assign_patient, name='assign_patient'),
    path('patient_delete/<int:queue_number>/', views.patient_delete, name='patient_delete'),
    path('patient/<int:id>/next/', views.mark_next_patient, name='mark_next_patient'),

    path('patient/<int:id>/edit/', views.patient_edit, name='patient_edit'),
    path('logout/', views.logout_view, name='logout_view'),
    path('get-queue-position/', views.get_queue_position, name='get_queue_position'),
    path('payments/', views.payments, name='payments'),


]

















