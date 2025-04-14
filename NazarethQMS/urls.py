from Nazareth.admin import custom_admin_site
from django.urls import path, include

urlpatterns = [
    path('admin/', custom_admin_site.urls),
    path('', include('Nazareth.urls')),
]
