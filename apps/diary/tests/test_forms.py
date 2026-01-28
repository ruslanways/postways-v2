"""
Tests for diary application forms.

Tests cover:
- FormControlMixin (widget class assignment)
- UsernameChangeForm (password check, cooldown, uniqueness)
- EmailChangeForm (password check, uniqueness, token generation)
"""

from datetime import timedelta

from django import forms
from django.utils import timezone

import pytest

from apps.diary.forms import EmailChangeForm, FormControlMixin, UsernameChangeForm
from apps.diary.models import CustomUser

pytestmark = pytest.mark.django_db


class TestFormControlMixin:
    """Tests for FormControlMixin widget class assignment."""

    def test_text_input_gets_form_input_class(self):
        """TextInput widget receives form-input class."""

        class TestForm(FormControlMixin, forms.Form):
            name = forms.CharField(widget=forms.TextInput())

        form = TestForm()
        assert "form-input" in form.fields["name"].widget.attrs["class"]

    def test_email_input_gets_form_input_class(self):
        """EmailInput widget receives form-input class."""

        class TestForm(FormControlMixin, forms.Form):
            email = forms.EmailField(widget=forms.EmailInput())

        form = TestForm()
        assert "form-input" in form.fields["email"].widget.attrs["class"]

    def test_password_input_gets_form_input_class(self):
        """PasswordInput widget receives form-input class."""

        class TestForm(FormControlMixin, forms.Form):
            password = forms.CharField(widget=forms.PasswordInput())

        form = TestForm()
        assert "form-input" in form.fields["password"].widget.attrs["class"]

    def test_textarea_gets_form_input_class(self):
        """Textarea widget receives form-input class."""

        class TestForm(FormControlMixin, forms.Form):
            content = forms.CharField(widget=forms.Textarea())

        form = TestForm()
        assert "form-input" in form.fields["content"].widget.attrs["class"]

    def test_file_input_gets_form_input_class(self):
        """FileInput widget receives form-input class."""

        class TestForm(FormControlMixin, forms.Form):
            file = forms.FileField(widget=forms.FileInput())

        form = TestForm()
        assert "form-input" in form.fields["file"].widget.attrs["class"]

    def test_checkbox_gets_form_checkbox_class(self):
        """CheckboxInput widget receives form-checkbox class."""

        class TestForm(FormControlMixin, forms.Form):
            agree = forms.BooleanField(widget=forms.CheckboxInput())

        form = TestForm()
        assert "form-checkbox" in form.fields["agree"].widget.attrs["class"]

    def test_preserves_existing_classes(self):
        """Mixin preserves existing widget classes."""

        class TestForm(FormControlMixin, forms.Form):
            name = forms.CharField(widget=forms.TextInput(attrs={"class": "custom"}))

        form = TestForm()
        widget_class = form.fields["name"].widget.attrs["class"]
        assert "custom" in widget_class
        assert "form-input" in widget_class

    def test_does_not_duplicate_classes(self):
        """Mixin does not add duplicate form-input class."""

        class TestForm(FormControlMixin, forms.Form):
            name = forms.CharField(
                widget=forms.TextInput(attrs={"class": "form-input"})
            )

        form = TestForm()
        widget_class = form.fields["name"].widget.attrs["class"]
        assert widget_class.count("form-input") == 1


class TestUsernameChangeForm:
    """Tests for UsernameChangeForm."""

    def test_valid_form(self, user, user_password):
        """Form is valid with correct password and unique username."""
        form = UsernameChangeForm(
            user,
            data={
                "password": user_password,
                "new_username": "newusername",
            },
        )
        assert form.is_valid()

    def test_wrong_password(self, user):
        """Form is invalid with wrong password."""
        form = UsernameChangeForm(
            user,
            data={
                "password": "wrongpassword",
                "new_username": "newusername",
            },
        )
        assert not form.is_valid()
        assert "password" in form.errors
        assert "incorrect" in str(form.errors["password"]).lower()

    def test_duplicate_username_exact_match(self, user, other_user, user_password):
        """Form is invalid when username already exists (exact match)."""
        form = UsernameChangeForm(
            user,
            data={
                "password": user_password,
                "new_username": other_user.username,
            },
        )
        assert not form.is_valid()
        assert "new_username" in form.errors

    def test_duplicate_username_case_insensitive(self, user, other_user, user_password):
        """Form is invalid when username already exists (case-insensitive)."""
        form = UsernameChangeForm(
            user,
            data={
                "password": user_password,
                "new_username": other_user.username.upper(),
            },
        )
        assert not form.is_valid()
        assert "new_username" in form.errors

    def test_allows_own_username_different_case(self, user, user_password):
        """Form allows user to change case of their own username."""
        form = UsernameChangeForm(
            user,
            data={
                "password": user_password,
                "new_username": user.username.upper(),
            },
        )
        assert form.is_valid()

    def test_cooldown_enforced(self, user, user_password):
        """Form is invalid if changed within cooldown period."""
        user.username_changed_at = timezone.now() - timedelta(days=10)
        user.save()

        form = UsernameChangeForm(
            user,
            data={
                "password": user_password,
                "new_username": "newusername",
            },
        )
        assert not form.is_valid()
        assert "__all__" in form.errors
        assert "30 days" in str(form.errors["__all__"])

    def test_cooldown_expired(self, user, user_password):
        """Form is valid after cooldown period expires."""
        user.username_changed_at = timezone.now() - timedelta(days=31)
        user.save()

        form = UsernameChangeForm(
            user,
            data={
                "password": user_password,
                "new_username": "newusername",
            },
        )
        assert form.is_valid()

    def test_no_cooldown_for_first_change(self, user, user_password):
        """Form is valid for users who never changed username."""
        assert user.username_changed_at is None

        form = UsernameChangeForm(
            user,
            data={
                "password": user_password,
                "new_username": "newusername",
            },
        )
        assert form.is_valid()

    def test_invalid_username_format(self, user, user_password):
        """Form is invalid with invalid username characters."""
        form = UsernameChangeForm(
            user,
            data={
                "password": user_password,
                "new_username": "invalid username!",
            },
        )
        assert not form.is_valid()
        assert "new_username" in form.errors

    def test_save_updates_username(self, user, user_password):
        """Save method updates username and timestamp."""
        form = UsernameChangeForm(
            user,
            data={
                "password": user_password,
                "new_username": "newusername",
            },
        )
        assert form.is_valid()

        saved_user = form.save()

        assert saved_user.username == "newusername"
        assert saved_user.username_changed_at is not None

    def test_save_sets_change_timestamp(self, user, user_password):
        """Save method sets username_changed_at to current time."""
        before = timezone.now()

        form = UsernameChangeForm(
            user,
            data={
                "password": user_password,
                "new_username": "newusername",
            },
        )
        form.is_valid()
        form.save()

        after = timezone.now()
        user.refresh_from_db()
        assert before <= user.username_changed_at <= after


class TestEmailChangeForm:
    """Tests for EmailChangeForm."""

    def test_valid_form(self, user, user_password):
        """Form is valid with correct password and unique email."""
        form = EmailChangeForm(
            user,
            data={
                "password": user_password,
                "new_email": "newemail@example.com",
            },
        )
        assert form.is_valid()

    def test_wrong_password(self, user):
        """Form is invalid with wrong password."""
        form = EmailChangeForm(
            user,
            data={
                "password": "wrongpassword",
                "new_email": "newemail@example.com",
            },
        )
        assert not form.is_valid()
        assert "password" in form.errors
        assert "incorrect" in str(form.errors["password"]).lower()

    def test_duplicate_email_exact_match(self, user, other_user, user_password):
        """Form is invalid when email already exists (exact match)."""
        form = EmailChangeForm(
            user,
            data={
                "password": user_password,
                "new_email": other_user.email,
            },
        )
        assert not form.is_valid()
        assert "new_email" in form.errors

    def test_duplicate_email_case_insensitive(self, user, other_user, user_password):
        """Form is invalid when email already exists (case-insensitive)."""
        form = EmailChangeForm(
            user,
            data={
                "password": user_password,
                "new_email": other_user.email.upper(),
            },
        )
        assert not form.is_valid()
        assert "new_email" in form.errors

    def test_same_as_current_email(self, user, user_password):
        """Form is invalid when new email matches current email."""
        form = EmailChangeForm(
            user,
            data={
                "password": user_password,
                "new_email": user.email,
            },
        )
        assert not form.is_valid()
        assert "new_email" in form.errors
        assert "different" in str(form.errors["new_email"]).lower()

    def test_same_as_current_email_case_insensitive(self, user, user_password):
        """Form is invalid when new email matches current email (case-insensitive)."""
        form = EmailChangeForm(
            user,
            data={
                "password": user_password,
                "new_email": user.email.upper(),
            },
        )
        assert not form.is_valid()
        assert "new_email" in form.errors

    def test_email_normalized_to_lowercase(self, user, user_password):
        """Email is normalized to lowercase."""
        form = EmailChangeForm(
            user,
            data={
                "password": user_password,
                "new_email": "NewEmail@Example.COM",
            },
        )
        assert form.is_valid()
        assert form.cleaned_data["new_email"] == "newemail@example.com"

    def test_save_sets_pending_email(self, user, user_password):
        """Save method sets pending_email field."""
        form = EmailChangeForm(
            user,
            data={
                "password": user_password,
                "new_email": "newemail@example.com",
            },
        )
        form.is_valid()
        saved_user, token, new_email = form.save()

        assert saved_user.pending_email == "newemail@example.com"
        assert new_email == "newemail@example.com"

    def test_save_generates_verification_token(self, user, user_password):
        """Save method generates verification token."""
        form = EmailChangeForm(
            user,
            data={
                "password": user_password,
                "new_email": "newemail@example.com",
            },
        )
        form.is_valid()
        saved_user, token, _ = form.save()

        assert token is not None
        assert len(token) == 36  # UUID format
        assert saved_user.email_verification_token == token

    def test_save_sets_expiration(self, user, user_password):
        """Save method sets token expiration to 24 hours."""
        before = timezone.now()

        form = EmailChangeForm(
            user,
            data={
                "password": user_password,
                "new_email": "newemail@example.com",
            },
        )
        form.is_valid()
        saved_user, _, _ = form.save()

        after = timezone.now()
        expected_min = before + timedelta(hours=24)
        expected_max = after + timedelta(hours=24)

        assert expected_min <= saved_user.email_verification_expires <= expected_max

    def test_original_email_unchanged_after_save(self, user, user_password):
        """Save does not change the user's current email."""
        original_email = user.email

        form = EmailChangeForm(
            user,
            data={
                "password": user_password,
                "new_email": "newemail@example.com",
            },
        )
        form.is_valid()
        form.save()

        user.refresh_from_db()
        assert user.email == original_email
