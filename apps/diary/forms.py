"""
Django forms for the diary application.

This module contains form classes for user authentication, registration,
password management, and blog post creation/editing.
"""
from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    SetPasswordForm,
    UserChangeForm,
    UserCreationForm,
    UsernameField,
)
from django.utils.translation import gettext_lazy as _

from .models import CustomUser, Post


class BootstrapFormMixin:
    """
    Mixin that adds Bootstrap form-control class to form widgets.

    Automatically applies 'form-control' class to text-like input widgets
    (TextInput, EmailInput, PasswordInput, Textarea, FileInput).
    Checkbox widgets are excluded as they use different Bootstrap classes.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        form_control_widgets = (
            forms.TextInput,
            forms.EmailInput,
            forms.PasswordInput,
            forms.Textarea,
            forms.FileInput,
        )
        for field in self.fields.values():
            if isinstance(field.widget, form_control_widgets):
                existing_class = field.widget.attrs.get("class", "")
                if "form-control" not in existing_class:
                    field.widget.attrs["class"] = (
                        f"{existing_class} form-control".strip()
                    )


class CustomUserCreationForm(BootstrapFormMixin, UserCreationForm):
    """
    Form for creating new users with email and terms acceptance.

    Extends Django's UserCreationForm with Bootstrap styling,
    email field, and terms acceptance checkbox.
    """

    password1 = forms.CharField(
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=password_validation.password_validators_help_text_html(),
    )
    password2 = forms.CharField(
        label=_("Password confirmation"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    email = forms.EmailField(
        label=_("Email"),
        max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )
    accept_terms = forms.BooleanField(
        label=_("Accept Terms"),
        widget=forms.CheckboxInput(attrs={"class": "checkbox-inline"}),
        help_text=_("I accept the terms of service and privacy policy"),
        error_messages={"required": _("You must accept the terms to continue")},
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ("username", "email", "accept_terms")


class CustomAuthenticationForm(BootstrapFormMixin, AuthenticationForm):
    """
    Authentication form with Bootstrap styling.

    Used for user login with username and password fields.
    """

    username = UsernameField(
        widget=forms.TextInput(attrs={"autofocus": True})
    )
    password = forms.CharField(
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )


class CustomPasswordResetForm(BootstrapFormMixin, PasswordResetForm):
    """
    Password reset form with Bootstrap styling.

    Used to request a password reset email.
    """

    email = forms.EmailField(
        label=_("Email"),
        max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )


class CustomSetPasswordForm(BootstrapFormMixin, SetPasswordForm):
    """
    Set password form with Bootstrap styling.

    Used when setting a new password after reset.
    """

    new_password1 = forms.CharField(
        label=_("New password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=password_validation.password_validators_help_text_html(),
    )
    new_password2 = forms.CharField(
        label=_("New password confirmation"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )


class CustomUserChangeForm(BootstrapFormMixin, UserChangeForm):
    """
    User profile change form with Bootstrap styling.

    Used for updating user profile information.
    """

    class Meta:
        model = CustomUser
        fields = ("username", "email")


class AddPostForm(BootstrapFormMixin, forms.ModelForm):
    """
    Form for creating new blog posts.

    Includes fields for title, content, image upload, and publish status.
    """

    class Meta:
        model = Post
        fields = ("title", "content", "image", "published")
        widgets = {
            "published": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "published": _("Publish"),
        }


class UpdatePostForm(AddPostForm):
    """
    Form for updating existing blog posts.

    Extends AddPostForm with additional help text for the image field.
    """

    class Meta(AddPostForm.Meta):
        help_texts = {
            "image": _("Leave empty to keep the current image."),
        }
