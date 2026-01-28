"""
Tests for crucial serializers validation logic.

Tests cover:
- UserSerializer: Registration with password matching and Django validation
- PasswordChangeSerializer: Old password verification, new password matching
- UsernameChangeSerializer: Password verification, uniqueness, 30-day cooldown
- EmailChangeSerializer: Password verification, email uniqueness
- LikeCreateDestroySerializer: Post must be published validation
"""

from datetime import timedelta
from unittest.mock import Mock

from django.utils import timezone

import pytest
from rest_framework.exceptions import ValidationError

from apps.diary.serializers import (
    EmailChangeSerializer,
    LikeCreateDestroySerializer,
    PasswordChangeSerializer,
    UserSerializer,
    UsernameChangeSerializer,
)

pytestmark = pytest.mark.django_db


class TestUserSerializer:
    """Tests for UserSerializer (registration)."""

    def test_valid_registration_data(self):
        """Valid registration data passes validation."""
        data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "password2": "SecurePass123!",
        }
        serializer = UserSerializer(data=data)

        assert serializer.is_valid(), serializer.errors

    def test_password_mismatch_raises_error(self):
        """Mismatched passwords raise validation error on create."""
        data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "password2": "DifferentPass123!",
        }
        serializer = UserSerializer(data=data)
        assert serializer.is_valid()

        with pytest.raises(ValidationError) as exc_info:
            serializer.save()

        assert "Password" in str(exc_info.value.detail)

    def test_weak_password_raises_error(self):
        """Weak password fails Django password validation."""
        data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "123",
            "password2": "123",
        }
        serializer = UserSerializer(data=data)

        assert not serializer.is_valid()
        assert "password" in serializer.errors or "non_field_errors" in serializer.errors

    def test_common_password_raises_error(self):
        """Common password fails Django password validation."""
        data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "password123",
            "password2": "password123",
        }
        serializer = UserSerializer(data=data)

        assert not serializer.is_valid()

    def test_password_similar_to_username_raises_error(self):
        """Password similar to username fails validation."""
        data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "testuser123",
            "password2": "testuser123",
        }
        serializer = UserSerializer(data=data)

        assert not serializer.is_valid()

    def test_creates_user_with_hashed_password(self):
        """Created user has properly hashed password."""
        data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "password2": "SecurePass123!",
        }
        serializer = UserSerializer(data=data)
        assert serializer.is_valid()

        user = serializer.save()

        assert user.pk is not None
        assert user.check_password("SecurePass123!")
        # Password should not be stored in plain text
        assert user.password != "SecurePass123!"


class TestPasswordChangeSerializer:
    """Tests for PasswordChangeSerializer."""

    def test_valid_password_change(self, user, user_password):
        """Valid password change data passes validation."""
        request = Mock()
        request.user = user
        data = {
            "old_password": user_password,
            "new_password": "NewSecurePass123!",
            "new_password2": "NewSecurePass123!",
        }
        serializer = PasswordChangeSerializer(data=data, context={"request": request})

        assert serializer.is_valid(), serializer.errors

    def test_wrong_old_password_raises_error(self, user):
        """Wrong old password raises validation error."""
        request = Mock()
        request.user = user
        data = {
            "old_password": "wrongpassword",
            "new_password": "NewSecurePass123!",
            "new_password2": "NewSecurePass123!",
        }
        serializer = PasswordChangeSerializer(data=data, context={"request": request})

        assert not serializer.is_valid()
        assert "old_password" in serializer.errors

    def test_new_passwords_mismatch_raises_error(self, user, user_password):
        """Mismatched new passwords raise validation error."""
        request = Mock()
        request.user = user
        data = {
            "old_password": user_password,
            "new_password": "NewSecurePass123!",
            "new_password2": "DifferentPass123!",
        }
        serializer = PasswordChangeSerializer(data=data, context={"request": request})

        assert not serializer.is_valid()
        assert "new_password2" in serializer.errors

    def test_weak_new_password_raises_error(self, user, user_password):
        """Weak new password fails Django validation."""
        request = Mock()
        request.user = user
        data = {
            "old_password": user_password,
            "new_password": "123",
            "new_password2": "123",
        }
        serializer = PasswordChangeSerializer(data=data, context={"request": request})

        assert not serializer.is_valid()


class TestUsernameChangeSerializer:
    """Tests for UsernameChangeSerializer."""

    def test_valid_username_change(self, user, user_password):
        """Valid username change data passes validation."""
        request = Mock()
        request.user = user
        data = {
            "password": user_password,
            "new_username": "brandnewname",
        }
        serializer = UsernameChangeSerializer(data=data, context={"request": request})

        assert serializer.is_valid(), serializer.errors

    def test_wrong_password_raises_error(self, user):
        """Wrong password raises validation error."""
        request = Mock()
        request.user = user
        data = {
            "password": "wrongpassword",
            "new_username": "newname",
        }
        serializer = UsernameChangeSerializer(data=data, context={"request": request})

        assert not serializer.is_valid()
        assert "password" in serializer.errors

    def test_duplicate_username_raises_error(self, user, other_user, user_password):
        """Username already taken raises validation error."""
        request = Mock()
        request.user = user
        data = {
            "password": user_password,
            "new_username": other_user.username,
        }
        serializer = UsernameChangeSerializer(data=data, context={"request": request})

        assert not serializer.is_valid()
        assert "new_username" in serializer.errors

    def test_duplicate_username_case_insensitive(self, user, other_user, user_password):
        """Username check is case-insensitive."""
        request = Mock()
        request.user = user
        data = {
            "password": user_password,
            "new_username": other_user.username.upper(),
        }
        serializer = UsernameChangeSerializer(data=data, context={"request": request})

        assert not serializer.is_valid()
        assert "new_username" in serializer.errors

    def test_cooldown_period_enforced(self, user, user_password):
        """Cannot change username within 30-day cooldown."""
        user.username_changed_at = timezone.now() - timedelta(days=10)
        user.save()

        request = Mock()
        request.user = user
        data = {
            "password": user_password,
            "new_username": "newname",
        }
        serializer = UsernameChangeSerializer(data=data, context={"request": request})

        assert not serializer.is_valid()
        assert "new_username" in serializer.errors
        assert "30 days" in str(serializer.errors["new_username"])

    def test_cooldown_expired_allows_change(self, user, user_password):
        """Can change username after 30-day cooldown expires."""
        user.username_changed_at = timezone.now() - timedelta(days=31)
        user.save()

        request = Mock()
        request.user = user
        data = {
            "password": user_password,
            "new_username": "newname",
        }
        serializer = UsernameChangeSerializer(data=data, context={"request": request})

        assert serializer.is_valid(), serializer.errors

    def test_first_username_change_allowed(self, user, user_password):
        """First username change allowed (no previous change)."""
        assert user.username_changed_at is None

        request = Mock()
        request.user = user
        data = {
            "password": user_password,
            "new_username": "newname",
        }
        serializer = UsernameChangeSerializer(data=data, context={"request": request})

        assert serializer.is_valid(), serializer.errors


class TestEmailChangeSerializer:
    """Tests for EmailChangeSerializer."""

    def test_valid_email_change(self, user, user_password):
        """Valid email change data passes validation."""
        request = Mock()
        request.user = user
        data = {
            "password": user_password,
            "new_email": "newemail@example.com",
        }
        serializer = EmailChangeSerializer(data=data, context={"request": request})

        assert serializer.is_valid(), serializer.errors

    def test_wrong_password_raises_error(self, user):
        """Wrong password raises validation error."""
        request = Mock()
        request.user = user
        data = {
            "password": "wrongpassword",
            "new_email": "newemail@example.com",
        }
        serializer = EmailChangeSerializer(data=data, context={"request": request})

        assert not serializer.is_valid()
        assert "password" in serializer.errors

    def test_same_email_raises_error(self, user, user_password):
        """Same email as current raises validation error."""
        request = Mock()
        request.user = user
        data = {
            "password": user_password,
            "new_email": user.email,
        }
        serializer = EmailChangeSerializer(data=data, context={"request": request})

        assert not serializer.is_valid()
        assert "new_email" in serializer.errors
        assert "different" in str(serializer.errors["new_email"]).lower()

    def test_duplicate_email_raises_error(self, user, other_user, user_password):
        """Email already taken raises validation error."""
        request = Mock()
        request.user = user
        data = {
            "password": user_password,
            "new_email": other_user.email,
        }
        serializer = EmailChangeSerializer(data=data, context={"request": request})

        assert not serializer.is_valid()
        assert "new_email" in serializer.errors

    def test_duplicate_email_case_insensitive(self, user, other_user, user_password):
        """Email check is case-insensitive."""
        request = Mock()
        request.user = user
        data = {
            "password": user_password,
            "new_email": other_user.email.upper(),
        }
        serializer = EmailChangeSerializer(data=data, context={"request": request})

        assert not serializer.is_valid()
        assert "new_email" in serializer.errors

    def test_email_normalized_to_lowercase(self, user, user_password):
        """Email is normalized to lowercase."""
        request = Mock()
        request.user = user
        data = {
            "password": user_password,
            "new_email": "NewEmail@EXAMPLE.COM",
        }
        serializer = EmailChangeSerializer(data=data, context={"request": request})

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["new_email"] == "newemail@example.com"


class TestLikeCreateDestroySerializer:
    """Tests for LikeCreateDestroySerializer."""

    def test_valid_like_on_published_post(self, post):
        """Valid like on published post passes validation."""
        data = {"post": post.pk}
        serializer = LikeCreateDestroySerializer(data=data)

        assert serializer.is_valid(), serializer.errors

    def test_like_on_unpublished_post_raises_error(self, unpublished_post):
        """Like on unpublished post raises validation error."""
        data = {"post": unpublished_post.pk}
        serializer = LikeCreateDestroySerializer(data=data)

        assert not serializer.is_valid()
        assert "post" in serializer.errors
        assert "unpublished" in str(serializer.errors["post"]).lower()

    def test_like_on_nonexistent_post_raises_error(self):
        """Like on nonexistent post raises validation error."""
        data = {"post": 99999}
        serializer = LikeCreateDestroySerializer(data=data)

        assert not serializer.is_valid()
        assert "post" in serializer.errors
