from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Post, Like


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "created")
    list_filter = ("created", "author")
    search_fields = ("title", "content")


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ("user", "post", "created")
    list_filter = ("created",)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "date_joined", "last_login", "last_request", "is_staff", "is_active")
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('last_request',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ('email',)}),
    )
