from django.apps import AppConfig


class DiaryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.diary'

    def ready(self):
        import apps.diary.signals  # noqa: F401