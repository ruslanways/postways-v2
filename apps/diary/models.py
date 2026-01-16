"""
Django models for the diary application.

This module contains the data models for user authentication, blog posts,
and user interactions (likes).
"""
from pathlib import Path

from PIL import Image, ImageOps
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
    )

    # Image fields
    image = models.ImageField(
        upload_to="diary/images/",
        blank=True,
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

    def save(self, *args, **kwargs):
        """
        Override save to handle image processing.
        
        When an image is uploaded:
        1. Resize the main image to a maximum of 2000x2000 pixels
        2. Generate a 300x300 thumbnail
        3. Save both images and update the model fields
        """
        # Save the model first to ensure we have an image path
        super().save(*args, **kwargs)

        # Process image if one was uploaded
        if self.image:
            # Open and process the main image
            with Image.open(self.image.path) as img:
                img_format = img.format
                max_size = (2000, 2000)

                # Resize main image while maintaining aspect ratio
                img_copy = img.copy()
                img_copy.thumbnail(max_size, Image.Resampling.LANCZOS)
                img_copy.save(self.image.path, format=img_format)

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
                original_filename = Path(self.image.name).name
                thumbnail_path = thumbnail_dir / f"thumb_{original_filename}"

                # Save thumbnail image
                thumb_img.save(thumbnail_path, format=img_format)

                # Update thumbnail field with relative path
                thumbnail_rel_path = thumbnail_path.relative_to(settings.MEDIA_ROOT)
                self.thumbnail.name = str(thumbnail_rel_path)

                # Save only the thumbnail field to avoid recursion
                super().save(update_fields=["thumbnail"], *args, **kwargs)

    class Meta:
        """Meta options for Post model."""
        ordering = ["-updated"]
        verbose_name = _("Post")
        verbose_name_plural = _("Posts")

    def __str__(self) -> str:
        """String representation of the post."""
        return f"{self.author.username}: {self.title}"

    def get_absolute_url(self):
        """Return the absolute URL for this post."""
        return reverse("post-detail", kwargs={"pk": self.id})


class Like(models.Model):
    """
    Like model representing a user's like on a post.
    
    Enforces uniqueness: each user can only like a post once.
    """

    # Foreign key relationships
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    post = models.ForeignKey(
        "Post",
        on_delete=models.CASCADE,
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
