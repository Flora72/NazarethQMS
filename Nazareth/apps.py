from django.apps import AppConfig

class NazarethConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Nazareth'

    def ready(self):
        import Nazareth.signals