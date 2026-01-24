"""
Django admin configuration for the diary application models.

This module registers models with the Django admin interface and configures
how they are displayed and filtered.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser, Like, Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    """
    Admin interface configuration for Post model.

    Provides list view with filtering and search capabilities.
    """

    list_display = ("title", "author", "created", "published")
    list_filter = ("created", "author", "published")
    search_fields = ("title", "content")
    date_hierarchy = "created"
    readonly_fields = ("created", "updated")
    list_editable = ("published",)


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    """
    Admin interface configuration for Like model.

    Provides list view with filtering capabilities.
    """

    list_display = ("user", "post", "created")
    list_filter = ("created", "user", "post")
    date_hierarchy = "created"
    readonly_fields = ("created",)
    search_fields = ("user__username", "post__title")


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """
    Admin interface configuration for CustomUser model.

    Extends Django's default UserAdmin to include the custom last_request field
    and improve the display of user information.
    """

    list_display = (
        "username",
        "email",
        "date_joined",
        "last_login",
        "last_request",
        "is_staff",
        "is_active",
    )
    list_filter = ("is_staff", "is_active", "date_joined", "last_login")
    search_fields = ("username", "email")
    date_hierarchy = "date_joined"

    fieldsets = UserAdmin.fieldsets + (
        ("Additional Info", {"fields": ("last_request",)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + ((None, {"fields": ("email",)}),)
