"""
Tests for email change API endpoints.

Tests cover:
- Email change initiation (sends verification email)
- Email verification (completes email change)
"""

import uuid
from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from apps.diary.models import CustomUser

pytestmark = pytest.mark.django_db


class TestEmailChange:
    """Tests for email change endpoint (POST /api/v1/auth/email/change/)."""

    @patch("apps.diary.views.api.send_email_verification.delay")
    def test_change_sends_verification(
        self, mock_send_email, authenticated_api_client, user, user_password
    ):
        """Valid request sends verification email."""
        new_email = "newemail@example.com"

        response = authenticated_api_client.post(
            reverse("email-change-api"),
            {
                "password": user_password,
                "new_email": new_email,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert "detail" in response.data

        # Verify Celery task was called
        mock_send_email.assert_called_once()
        call_args = mock_send_email.call_args[0]
        assert new_email in call_args

        # Verify pending_email was set
        user.refresh_from_db()
        assert user.pending_email == new_email
        assert user.email_verification_token
        assert user.email_verification_expires

    def test_change_duplicate_rejected(
        self, authenticated_api_client, user, user_password, other_user
    ):
        """Duplicate email returns 400."""
        response = authenticated_api_client.post(
            reverse("email-change-api"),
            {
                "password": user_password,
                "new_email": other_user.email,  # existing email
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "new_email" in response.data

    def test_change_same_email_rejected(
        self, authenticated_api_client, user, user_password
    ):
        """Same as current email returns 400."""
        response = authenticated_api_client.post(
            reverse("email-change-api"),
            {
                "password": user_password,
                "new_email": user.email,
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "new_email" in response.data

    def test_change_wrong_password(self, authenticated_api_client, user):
        """Wrong password returns 400."""
        response = authenticated_api_client.post(
            reverse("email-change-api"),
            {
                "password": "wrongpassword",
                "new_email": "newemail@example.com",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "password" in response.data

    def test_change_requires_auth(self, api_client):
        """Anonymous gets 401."""
        response = api_client.post(
            reverse("email-change-api"),
            {
                "password": "anypassword",
                "new_email": "newemail@example.com",
            },
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_change_invalid_email_format(
        self, authenticated_api_client, user, user_password
    ):
        """Invalid email format returns 400."""
        response = authenticated_api_client.post(
            reverse("email-change-api"),
            {
                "password": user_password,
                "new_email": "not-an-email",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "new_email" in response.data

    def test_change_missing_fields(self, authenticated_api_client, user):
        """Missing fields return 400."""
        # Missing password
        response = authenticated_api_client.post(
            reverse("email-change-api"),
            {"new_email": "newemail@example.com"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "password" in response.data

        # Missing new_email
        response = authenticated_api_client.post(
            reverse("email-change-api"),
            {"password": "testpass123"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "new_email" in response.data

    @patch("apps.diary.views.api.send_email_verification.delay")
    def test_change_email_case_insensitive_uniqueness(
        self, mock_send_email, authenticated_api_client, user, user_password, other_user
    ):
        """Email uniqueness is case-insensitive."""
        response = authenticated_api_client.post(
            reverse("email-change-api"),
            {
                "password": user_password,
                "new_email": other_user.email.upper(),  # same email, different case
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "new_email" in response.data


class TestEmailVerify:
    """Tests for email verification endpoint (POST /api/v1/auth/email/verify/)."""

    def test_verify_valid_token(self, api_client, user):
        """Valid token updates email."""
        old_email = user.email
        new_email = "verified@example.com"
        token = str(uuid.uuid4())

        # Set up pending email change
        user.pending_email = new_email
        user.email_verification_token = token
        user.email_verification_expires = timezone.now() + timedelta(hours=24)
        user.save()

        response = api_client.post(
            reverse("email-verify-api"),
            {"token": token},
        )

        assert response.status_code == status.HTTP_200_OK
        assert "detail" in response.data
        assert response.data["email"] == new_email

        # Verify email was changed
        user.refresh_from_db()
        assert user.email == new_email
        assert user.email != old_email

        # Verify pending fields were cleared
        assert user.pending_email == ""
        assert user.email_verification_token == ""
        assert user.email_verification_expires is None

    def test_verify_expired_token(self, api_client, user):
        """Expired token returns 400."""
        token = str(uuid.uuid4())

        # Set up expired pending email change
        user.pending_email = "expired@example.com"
        user.email_verification_token = token
        user.email_verification_expires = timezone.now() - timedelta(hours=1)
        user.save()

        response = api_client.post(
            reverse("email-verify-api"),
            {"token": token},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "token" in response.data

    def test_verify_invalid_token(self, api_client):
        """Invalid token returns 400."""
        response = api_client.post(
            reverse("email-verify-api"),
            {"token": "invalid-token-that-doesnt-exist"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "token" in response.data

    def test_verify_missing_token(self, api_client):
        """Missing token returns 400."""
        response = api_client.post(
            reverse("email-verify-api"),
            {},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "token" in response.data

    def test_verify_via_get_with_query_param(self, api_client, user):
        """GET request with token query param works."""
        new_email = "getverified@example.com"
        token = str(uuid.uuid4())

        # Set up pending email change
        user.pending_email = new_email
        user.email_verification_token = token
        user.email_verification_expires = timezone.now() + timedelta(hours=24)
        user.save()

        response = api_client.get(
            reverse("email-verify-api"),
            {"token": token},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == new_email

        user.refresh_from_db()
        assert user.email == new_email

    def test_verify_via_get_missing_token(self, api_client):
        """GET request without token returns 400."""
        response = api_client.get(reverse("email-verify-api"))

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data


class TestEmailChangeFlow:
    """Integration tests for complete email change flow."""

    @patch("apps.diary.views.api.send_email_verification.delay")
    def test_complete_flow(
        self, mock_send_email, api_client, authenticated_api_client, user, user_password
    ):
        """Test complete email change and verification flow."""
        old_email = user.email
        new_email = "brandnew@example.com"

        # Step 1: Request email change
        response = authenticated_api_client.post(
            reverse("email-change-api"),
            {
                "password": user_password,
                "new_email": new_email,
            },
        )
        assert response.status_code == status.HTTP_200_OK

        # Get the token that was set
        user.refresh_from_db()
        token = user.email_verification_token
        assert token

        # Step 2: Verify email
        response = api_client.post(
            reverse("email-verify-api"),
            {"token": token},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == new_email

        # Step 3: Verify email was actually changed
        user.refresh_from_db()
        assert user.email == new_email
        assert user.email != old_email

        # Step 4: Verify old email is now available for other users

        # This should not raise - old email is free
        new_user = CustomUser.objects.create_user(
            username="newuser", email=old_email, password="testpass123"
        )
        assert new_user.email == old_email

    @patch("apps.diary.views.api.send_email_verification.delay")
    def test_token_is_single_use(
        self, mock_send_email, api_client, authenticated_api_client, user, user_password
    ):
        """Token can only be used once."""
        new_email = "singleuse@example.com"

        # Request email change
        response = authenticated_api_client.post(
            reverse("email-change-api"),
            {
                "password": user_password,
                "new_email": new_email,
            },
        )
        assert response.status_code == status.HTTP_200_OK

        user.refresh_from_db()
        token = user.email_verification_token

        # First verification should succeed
        response = api_client.post(
            reverse("email-verify-api"),
            {"token": token},
        )
        assert response.status_code == status.HTTP_200_OK

        # Second verification with same token should fail
        response = api_client.post(
            reverse("email-verify-api"),
            {"token": token},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
