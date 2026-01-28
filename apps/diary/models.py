"""
Django models for the diary application.

This module contains the data models for user authentication, blog posts,
and user interactions (likes).
"""

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .validators import MyUnicodeUsernameValidator, profanity


class CustomUser(AbstractUser):
    """
    Custom user model extending Django's AbstractUser.

    Extends the default Django user model with:
    - Email field that is unique and required
    - Custom username validator with Unicode support
    - Last request timestamp tracking
    """

    # Override username field to add custom validator
    username = models.CharField(
        _("username"),
        max_length=150,
        unique=True,
        help_text=_(
            "Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only."
        ),
        validators=[MyUnicodeUsernameValidator()],
        error_messages={
            "unique": _("A user with that username already exists."),
        },
    )

    # Make email field unique and required (not blank)
    email = models.EmailField(
        _("email address"),
        unique=True,
        error_messages={
            "unique": _("A user with that email already exists."),
        },
    )

    # Track when user last made a request (for analytics/activity tracking)
    last_request = models.DateTimeField(_("last request"), blank=True, null=True)

    # Track when username was last changed (for rate limiting username changes)
    username_changed_at = models.DateTimeField(
        _("username changed at"),
        blank=True,
        null=True,
        help_text=_("Timestamp of last username change. Used for rate limiting."),
    )

    # Email change verification fields
    pending_email = models.EmailField(
        _("pending email"),
        blank=True,
        help_text=_("New email address awaiting verification."),
    )
    email_verification_token = models.CharField(
        _("email verification token"),
        max_length=36,
        blank=True,
        help_text=_("UUID token for email verification."),
    )
    email_verification_expires = models.DateTimeField(
        _("email verification expires"),
        blank=True,
        null=True,
        help_text=_("Token expiry time (24 hours after creation)."),
    )


class Post(models.Model):
    """
    Blog post model representing a diary entry.

    Posts contain title, content, optional images, and metadata.
    Images are automatically resized and thumbnails are generated on save.
    Content is validated for profanity.
    """

    # Primary content fields
    title = models.CharField(max_length=100, validators=[profanity])
    content = models.TextField(validators=[profanity])

    # Foreign key relationships
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posts",
    )

    # Image fields
    image = models.ImageField(
        upload_to="diary/images/",
        blank=True,
        max_length=200,
        help_text="Upload an image for this post. Will be automatically resized.",
    )
    thumbnail = models.ImageField(
        upload_to="diary/images/thumbnails/",
        blank=True,
        null=True,
        editable=False,
        max_length=200,
        help_text="Automatically generated thumbnail image.",
    )

    # Timestamps
    created = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the post was created.",
    )
    updated = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the post was last updated.",
    )

    # Status flags
    published = models.BooleanField(
        default=True,
        help_text="Whether the post is published and visible to others.",
    )

    class Meta:
        """Meta options for Post model."""

        ordering = ["-updated"]
        verbose_name = _("Post")
        verbose_name_plural = _("Posts")

    def __str__(self) -> str:
        """String representation of the post."""
        return f"{self.author.username}: {self.title}"

    def save(self, *args, **kwargs):
        """
        Override save to trigger async image processing and cleanup.

        When a new image is uploaded, saves the model and triggers
        a Celery task to resize the image and generate a thumbnail.
        When an image is cleared or replaced, queues deletion of old files.
        """
        old_image, old_thumbnail, is_new_image = self._track_image_changes()
        super().save(*args, **kwargs)
        self._cleanup_old_images(old_image, old_thumbnail)
        if is_new_image:
            self._process_new_image()

    def get_absolute_url(self):
        """Return the absolute URL for this post."""
        return reverse("post-detail", kwargs={"pk": self.id})

    def _track_image_changes(self):
        """
        Track image changes before save.

        Returns:
            tuple: (old_image, old_thumbnail, is_new_image)
        """
        if not self.pk:
            return None, None, bool(self.image)

        old_data = Post.objects.filter(pk=self.pk).values("image", "thumbnail").first()
        if not old_data:
            return None, None, bool(self.image)

        old_image = old_data["image"]
        old_thumbnail = old_data["thumbnail"]
        is_new_image = bool(self.image and self.image.name != old_image)
        return old_image, old_thumbnail, is_new_image

    def _cleanup_old_images(self, old_image, old_thumbnail):
        """Queue deletion of old image files if they were cleared or replaced."""
        if not old_image:
            return

        image_cleared = not self.image
        image_replaced = self.image and self.image.name != old_image
        if not (image_cleared or image_replaced):
            return

        from django.db import transaction

        from .tasks import delete_media_files

        paths = [old_image]
        if old_thumbnail:
            paths.append(old_thumbnail)
        transaction.on_commit(lambda: delete_media_files.delay(paths))

    def _process_new_image(self):
        """Trigger async image processing for new images."""
        from .tasks import process_post_image

        process_post_image.delay(self.pk)


class Like(models.Model):
    """
    Like model representing a user's like on a post.

    Enforces uniqueness: each user can only like a post once.
    """

    # Foreign key relationships
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="likes",
    )
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="likes",
    )

    # Timestamps
    created = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the like was created.",
    )

    class Meta:
        """Meta options for Like model."""

        constraints = [
            models.UniqueConstraint(
                fields=["user", "post"],
                name="unique_like",
            )
        ]
        verbose_name = _("Like")
        verbose_name_plural = _("Likes")
        ordering = ["-created"]

    def __str__(self) -> str:
        """String representation of the like."""
        return f"{self.user.username} liked: {self.post.title}"
