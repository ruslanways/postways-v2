"""
Django signal handlers for the diary application.

This module contains signal receivers that respond to Django framework events,
such as user authentication events, to perform side effects like logging.
"""

import logging

from django.contrib.auth.signals import user_logged_in
from django.db import transaction
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.utils import timezone

from .models import Post

logger = logging.getLogger(__name__)


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """
    Log user login events.

    Receives the user_logged_in signal and logs authentication events
    for monitoring and audit purposes.

    Args:
        sender: The model class that sent the signal (User model)
        request: The HTTP request object
        user: The user instance that logged in
        **kwargs: Additional signal arguments
    """
    login_time = timezone.now()
    logger.info(
        "User logged in",
        extra={
            "username": user.username,
            "user_id": user.pk,
            "login_time": login_time.isoformat(),
        },
    )


@receiver(pre_delete, sender=Post)
def queue_post_image_deletion(sender, instance, **kwargs):
    """
    Queue deletion of post images when a post is deleted.

    Uses pre_delete to capture file paths before the post record is removed.
    The actual deletion is handled asynchronously via Celery task, which
    supports both local storage and S3 with automatic retries.

    Args:
        sender: The model class (Post)
        instance: The Post instance being deleted
        **kwargs: Additional signal arguments
    """
    paths = []
    if instance.image:
        paths.append(instance.image.name)
    if instance.thumbnail:
        paths.append(instance.thumbnail.name)

    if paths:
        from .tasks import delete_media_files

        # Use on_commit to ensure task runs only if deletion succeeds
        transaction.on_commit(lambda: delete_media_files.delay(paths))
