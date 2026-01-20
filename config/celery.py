"""
Celery configuration for Postways.

This module configures the Celery application instance, which handles asynchronous
task processing and scheduled periodic tasks. Tasks are automatically discovered
from Django apps that define a `tasks.py` module.

Configuration is loaded from Django settings using the `CELERY_*` namespace.
"""
import os
from pathlib import Path

from celery import Celery
from celery.schedules import crontab
from django.conf import settings

# Set default Django settings module before importing Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Create Celery app instance
app = Celery("postways_celery")

# Load configuration from Django settings (CELERY_* namespace)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks from all installed Django apps
# Looks for tasks.py modules in each app
app.autodiscover_tasks()

# Configure Celery Beat (periodic task scheduler)
# Use absolute path for beat schedule file to avoid issues with working directory changes
beat_schedule_dir = Path(settings.BASE_DIR) / "var"
beat_schedule_dir.mkdir(exist_ok=True)
app.conf.beat_schedule_filename = str(beat_schedule_dir / "celerybeat-schedule")

# Use Django's timezone for scheduled tasks
app.conf.timezone = settings.TIME_ZONE

# Define periodic tasks
app.conf.beat_schedule = {
    "week-report": {
        "task": "apps.diary.tasks.send_week_report",
        "schedule": crontab(hour=10, minute=0, day_of_week=6),  # Saturday 10:00
        "options": {"expires": 3600},  # Task expires after 1 hour if not executed
    },
    "flush-expired-tokens": {
        "task": "apps.diary.tasks.flush_expired_tokens",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),  # Sunday 03:00
        "options": {"expires": 3600},  # Task expires after 1 hour if not executed
    },
}

