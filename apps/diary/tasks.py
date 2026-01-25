from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.mail import send_mail
from django.core.management import call_command
from django.utils import timezone

from celery import shared_task
from PIL import Image, ImageOps


@shared_task
def process_post_image(post_id):
    """Process uploaded image: resize and generate thumbnail."""
    from .models import Post  # Import here to avoid circular import

    try:
        post = Post.objects.get(pk=post_id)
    except Post.DoesNotExist:
        return

    if not post.image:
        return

    with Image.open(post.image.path) as img:
        img_format = img.format
        max_size = (2000, 2000)

        # Apply EXIF orientation (fixes rotated phone photos)
        img_copy = ImageOps.exif_transpose(img)

        # Resize main image while maintaining aspect ratio
        img_copy.thumbnail(max_size, Image.Resampling.LANCZOS)
        img_copy.save(post.image.path, format=img_format)

        # Generate thumbnail: 300x300 cropped to fit
        thumbnail_size = (300, 300)
        thumb_img = ImageOps.fit(
            img_copy,
            thumbnail_size,
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )

        # Ensure thumbnail directory exists
        thumbnail_dir = Path(settings.MEDIA_ROOT) / "diary/images/thumbnails"
        thumbnail_dir.mkdir(parents=True, exist_ok=True)

        # Generate thumbnail filename with 'thumb_' prefix
        original_filename = Path(post.image.name).name
        thumbnail_path = thumbnail_dir / f"thumb_{original_filename}"

        # Save thumbnail image
        thumb_img.save(thumbnail_path, format=img_format)

        # Update thumbnail field using filter().update() to avoid recursion
        thumbnail_rel_path = thumbnail_path.relative_to(settings.MEDIA_ROOT)
        Post.objects.filter(pk=post_id).update(thumbnail=str(thumbnail_rel_path))


@shared_task
def send_token_recovery_email(password_reset_url, token, user_email):
    """Sends a password reset token email to the user."""
    send_mail(
        "Postways Password Reset",
        f"Here is your password reset token (expires in 5 minutes):"
        f"\n\n{token}\n\n"
        "To reset your password, send a POST request to:\n"
        f"{password_reset_url}\n\n"
        "With headers:\n"
        "  Authorization: Bearer <token>\n"
        "  Content-Type: application/json\n\n"
        "And body:\n"
        '  {"new_password": "your_new_password", "new_password2": "your_new_password"}\n\n'
        "After resetting, you can log in with your new password to obtain fresh tokens.",
        None,
        [user_email],
    )


@shared_task
def send_week_report():
    from .models import CustomUser, Like, Post  # Import here to avoid circular import

    now = timezone.now()
    week_ago = timezone.now() - timedelta(days=7)
    users = CustomUser.objects.filter(date_joined__range=(week_ago, now)).count()
    posts = Post.objects.filter(created__range=(week_ago, now)).count()
    likes = Like.objects.filter(created__range=(week_ago, now)).count()

    send_mail(
        "Postways week report",
        "Hi admin."
        "\n\nFor the last week 'Postways' got\n\n"
        f"new users: {users}\n"
        f"new posts: {posts}\n"
        f"new likes: {likes}\n"
        "\nHave a nice weekend😉",
        None,
        settings.WEEKLY_RECIPIENTS,
    )


@shared_task
def flush_expired_tokens():
    """Remove expired tokens from OutstandingToken and BlacklistedToken tables."""
    call_command("flushexpiredtokens")


@shared_task
def send_email_verification(verification_link, new_email):
    """Sends an email verification link to the user's new email address."""
    send_mail(
        "Postways email verification",
        f"Please click the link below to verify your new email address:\n\n"
        f"{verification_link}\n\n"
        "This link will expire in 24 hours.\n\n"
        "If you did not request this email change, please ignore this message.",
        None,
        [new_email],
    )


@shared_task
def send_password_reset_email(user_email, reset_url, username, site_name="Postways"):
    """
    Sends a password reset email to the user.

    Args:
        user_email: The user's email address
        reset_url: The password reset confirmation URL (with uidb64 and token)
        username: The user's username for the email template
        site_name: The site name to use in the email (defaults to "Postways")
    """
    # Build email message using similar format to Django's default template
    message = (
        f"Hi there😉\n\n"
        f"You're receiving this email because you requested a password reset "
        f"for your user account at {site_name}.\n\n"
        f"Please go to the following page and choose a new password:\n"
        f"{reset_url}\n\n"
        f"Your username, in case you've forgotten: {username}\n\n"
        f"Thanks for using our site!\n\n"
        f"The {site_name} team"
    )

    send_mail(
        subject=f"Password reset on {site_name}",
        message=message,
        from_email=None,  # Uses DEFAULT_FROM_EMAIL
        recipient_list=[user_email],
    )
