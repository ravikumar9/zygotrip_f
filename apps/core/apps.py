from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'

    def ready(self):
        from . import platform_settings  # noqa: F401
        # Best-effort Firebase initialization for push notifications.
        from .firebase import initialize_firebase_app
        initialize_firebase_app()