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

    list_display = ("title", "author", "created_at", "published")
    list_filter = ("created_at", "author", "published")
    search_fields = ("title", "content")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at", "updated_at")
    list_editable = ("published",)


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    """
    Admin interface configuration for Like model.

    Provides list view with filtering capabilities.
    """

    list_display = ("user", "post", "created_at")
    list_filter = ("created_at", "user", "post")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at",)
    search_fields = ("user__username", "post__title")


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """
    Admin interface configuration for CustomUser model.

    Extends Django's default UserAdmin to include the custom last_activity_at field
    and improve the display of user information.
    """

    list_display = (
        "username",
        "email",
        "date_joined",
        "last_login",
        "last_activity_at",
        "is_staff",
        "is_active",
    )
    list_filter = ("is_staff", "is_active", "date_joined", "last_login")
    search_fields = ("username", "email")
    date_hierarchy = "date_joined"

    fieldsets = UserAdmin.fieldsets + (
        ("Additional Info", {"fields": ("last_activity_at",)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + ((None, {"fields": ("email",)}),)
