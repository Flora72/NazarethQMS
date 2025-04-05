from django.contrib.auth.management.commands.createsuperuser import Command as SuperuserCommand
from django.core.management import CommandError

class Command(SuperuserCommand):
    def handle(self, *args, **options):
        options['role'] = 'admin'
        super().handle(*args, **options)
