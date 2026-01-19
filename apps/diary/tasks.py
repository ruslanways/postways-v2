from datetime import timedelta
from pathlib import Path

from PIL import Image, ImageOps
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from celery import shared_task


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
def send_token_recovery_email(link_to_change_user, token, user_email):
    """Sends a token recovery email to the user."""
    send_mail(
            "Postways token recovery",
            f"Here are your new access token expires in 5 min."
            f"\n\n'access': {token}\n\n"
            "You can use it to change password by Post-request to: "
            f"{link_to_change_user}"
            "\n\nTherefore you could obtain new tokens pair by logging.",
            None,
            [user_email],
        )


@shared_task
def send_week_report():
    from .models import CustomUser, Post, Like  # Import here to avoid circular import

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
        settings.WEEKLY_REPORT_RECIPIENTS
    )
