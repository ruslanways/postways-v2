"""
Django app configuration for the diary application.
"""
from django.apps import AppConfig


class DiaryConfig(AppConfig):
    """
    Configuration for the diary application.
    
    Handles app initialization and signal registration.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.diary'

    def ready(self) -> None:
        """
        Called when Django starts.
        
        Imports signal handlers to ensure they are registered.
        """
        import apps.diary.signals  # noqa: F401