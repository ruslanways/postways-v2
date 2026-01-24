"""
Django signal handlers for the diary application.

This module contains signal receivers that respond to Django framework events,
such as user authentication events, to perform side effects like logging.
"""

import logging

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.utils import timezone

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
