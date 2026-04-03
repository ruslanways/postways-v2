"""Email sending logic for notifications."""

import logging

logger = logging.getLogger(__name__)


def send_like_notification_email(
    *,
    author_email,
    author_username,
    liker_username,
    post_title,
    post_id,
):
    """
    Send email notification to post author about a new like.

    In development, this logs the email to stdout.
    In production, this would use SMTP.
    """
    subject = f"{liker_username} liked your post!"
    body = (
        f"Hi {author_username},\n\n"
        f'{liker_username} liked your post "{post_title}".\n\n'
        f"Keep writing!\n"
        f"-- Postways"
    )

    logger.info(
        "\n--- EMAIL NOTIFICATION ---\nTo: %s\nSubject: %s\n\n%s\n--- END EMAIL ---",
        author_email,
        subject,
        body,
    )
