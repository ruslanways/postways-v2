from datetime import timedelta
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.mail import send_mail
from django.core.management import call_command
from django.utils import timezone

from celery import shared_task
from PIL import Image, ImageOps


def _normalize_image_format(pil_format):
    """
    Normalize PIL image format to a web-safe format.

    Some formats like MPO (Multi-Picture Object from iPhones) are not recognized
    by browsers, causing them to download instead of display. This normalizes
    such formats to their web-compatible equivalents.
    """
    # MPO is JPEG-based (used by iPhones for depth/HDR photos)
    # Browsers don't recognize image/mpo, so normalize to JPEG
    if pil_format in ("MPO", None):
        return "JPEG"
    # Only allow web-safe formats
    if pil_format in ("JPEG", "PNG", "GIF", "WEBP"):
        return pil_format
    # Default everything else to JPEG
    return "JPEG"


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

    # Read image from storage (works with both local and S3)
    with post.image.open("rb") as f:
        img = Image.open(f)
        img.load()  # Load image data before closing file
        img_format = _normalize_image_format(img.format)

    max_size = (2000, 2000)

    # Apply EXIF orientation (fixes rotated phone photos)
    img = ImageOps.exif_transpose(img)

    # Resize main image while maintaining aspect ratio
    img.thumbnail(max_size, Image.Resampling.LANCZOS)

    # Save resized image back to storage
    img_buffer = BytesIO()
    img.save(img_buffer, format=img_format)
    img_buffer.seek(0)
    default_storage.delete(post.image.name)
    img_content = ContentFile(img_buffer.read())
    img_content.content_type = f"image/{img_format.lower()}"
    default_storage.save(post.image.name, img_content)

    # Generate thumbnail: 300x300 cropped to fit
    thumbnail_size = (300, 300)
    thumb_img = ImageOps.fit(
        img,
        thumbnail_size,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )

    # Generate thumbnail path
    original_filename = Path(post.image.name).name
    thumbnail_rel_path = f"diary/images/thumbnails/thumb_{original_filename}"

    # Save thumbnail to storage
    thumb_buffer = BytesIO()
    thumb_img.save(thumb_buffer, format=img_format)
    thumb_buffer.seek(0)
    thumb_content = ContentFile(thumb_buffer.read())
    thumb_content.content_type = f"image/{img_format.lower()}"
    default_storage.save(thumbnail_rel_path, thumb_content)

    # Update thumbnail field using filter().update() to avoid recursion
    Post.objects.filter(pk=post_id).update(thumbnail=thumbnail_rel_path)


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


@shared_task(bind=True, max_retries=3)
def delete_media_files(self, file_paths):
    """
    Delete media files from storage (works with local and S3).

    Uses Django's default_storage abstraction, so it works with any
    configured storage backend. Includes retries for S3 transient failures.

    Args:
        file_paths: List of file paths relative to MEDIA_ROOT
    """
    from django.core.files.storage import default_storage

    for path in file_paths:
        try:
            if default_storage.exists(path):
                default_storage.delete(path)
        except Exception as exc:
            # Retry on failure (useful for S3 transient errors)
            self.retry(exc=exc, countdown=60)


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
