"""
Django forms for the diary application.

This module contains form classes for user authentication, registration,
password management, and blog post creation/editing.
"""

from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserChangeForm,
    UserCreationForm,
    UsernameField,
)
from django.utils.translation import gettext_lazy as _

from datetime import timedelta
from django.utils import timezone
from .models import CustomUser, Post
from .validators import MyUnicodeUsernameValidator


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

    username = UsernameField(widget=forms.TextInput(attrs={"autofocus": True}))
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


class CustomPasswordChangeForm(BootstrapFormMixin, PasswordChangeForm):
    """
    Password change form with Bootstrap styling.

    Extends Django's PasswordChangeForm with the BootstrapFormMixin
    to apply form-control class to all input widgets.
    """

    old_password = forms.CharField(
        label=_("Old password"),
        strip=False,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "current-password", "autofocus": True}
        ),
    )
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


class UsernameChangeForm(BootstrapFormMixin, forms.Form):
    """
    Form for changing username with password confirmation.

    Requires current password for verification and enforces a 30-day
    cooldown between username changes. Username must be unique (case-insensitive).
    """

    # 30-day cooldown between username changes
    USERNAME_CHANGE_COOLDOWN_DAYS = 30

    password = forms.CharField(
        label=_("Current Password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
        help_text=_("Enter your current password to confirm the change."),
    )
    new_username = forms.CharField(
        label=_("New Username"),
        max_length=150,
        widget=forms.TextInput(attrs={"autofocus": True}),
        help_text=_("150 characters or fewer. Letters, digits and @/./+/-/_ only."),
    )

    def __init__(self, user, *args, **kwargs):
        """
        Initialize form with user instance for validation.

        Args:
            user: The current user requesting the username change
        """
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        """
        Validate that the password is correct.

        Returns:
            str: The validated password

        Raises:
            ValidationError: If the password is incorrect
        """
        password = self.cleaned_data.get("password")
        if not self.user.check_password(password):
            raise forms.ValidationError(_("Password is incorrect."))
        return password

    def clean_new_username(self):
        """
        Validate that the new username is unique (case-insensitive) and properly formatted.

        Returns:
            str: The validated username

        Raises:
            ValidationError: If username is taken or invalid format
        """
        new_username = self.cleaned_data.get("new_username")

        # Check case-insensitive uniqueness (excluding current user)
        if (
            CustomUser.objects.filter(username__iexact=new_username)
            .exclude(pk=self.user.pk)
            .exists()
        ):
            raise forms.ValidationError(_("A user with that username already exists."))

        # Apply the custom username validator
        validator = MyUnicodeUsernameValidator()
        try:
            validator(new_username)
        except Exception as e:
            raise forms.ValidationError(str(e))

        return new_username

    def clean(self):
        """
        Validate that the 30-day cooldown has passed since last username change.

        Returns:
            dict: Cleaned data

        Raises:
            ValidationError: If username was changed less than 30 days ago
        """
        cleaned_data = super().clean()

        if self.user.username_changed_at:
            cooldown_end = self.user.username_changed_at + timedelta(
                days=self.USERNAME_CHANGE_COOLDOWN_DAYS
            )
            if timezone.now() < cooldown_end:
                days_remaining = (cooldown_end - timezone.now()).days + 1
                raise forms.ValidationError(
                    _(
                        "You can only change your username once every "
                        "%(days)d days. Please wait %(remaining)d more day(s)."
                    ),
                    code="cooldown",
                    params={
                        "days": self.USERNAME_CHANGE_COOLDOWN_DAYS,
                        "remaining": days_remaining,
                    },
                )

        return cleaned_data

    def save(self):
        """
        Save the new username and update the change timestamp.

        Returns:
            CustomUser: The updated user instance
        """
        self.user.username = self.cleaned_data["new_username"]
        self.user.username_changed_at = timezone.now()
        self.user.save()
        return self.user
