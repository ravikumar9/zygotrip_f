from django.apps import AppConfig


class ZygotripConfig(AppConfig):
    name = 'zygotrip_project'
    verbose_name = 'ZygoTrip Project'

    def ready(self):
        from .firebase_init import initialize_firebase
        initialize_firebase()
