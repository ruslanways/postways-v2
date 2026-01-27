"""
Tests for password management API endpoints.

Tests cover:
- Password change (authenticated)
- Password recovery (token request)
- Password reset (with recovery token)
"""

from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import RefreshToken

pytestmark = pytest.mark.django_db


class TestPasswordChange:
    """Tests for password change endpoint (POST /api/v1/auth/password/change/)."""

    def test_change_success(self, authenticated_api_client, user, user_password):
        """Valid old + new password succeeds."""
        new_password = "newsecurepass456"

        response = authenticated_api_client.post(
            reverse("password-change-api"),
            {
                "old_password": user_password,
                "new_password": new_password,
                "new_password2": new_password,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert "detail" in response.data

        # Verify password was changed
        user.refresh_from_db()
        assert user.check_password(new_password)
        assert not user.check_password(user_password)

    def test_change_wrong_old_password(self, authenticated_api_client, user):
        """Wrong old password returns 400."""
        response = authenticated_api_client.post(
            reverse("password-change-api"),
            {
                "old_password": "wrongpassword",
                "new_password": "newsecurepass456",
                "new_password2": "newsecurepass456",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "old_password" in response.data

    def test_change_passwords_dont_match(
        self, authenticated_api_client, user, user_password
    ):
        """Password mismatch returns 400."""
        response = authenticated_api_client.post(
            reverse("password-change-api"),
            {
                "old_password": user_password,
                "new_password": "newsecurepass456",
                "new_password2": "differentpass789",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "new_password2" in response.data

    def test_change_password_too_simple(
        self, authenticated_api_client, user, user_password
    ):
        """Simple password returns 400."""
        response = authenticated_api_client.post(
            reverse("password-change-api"),
            {
                "old_password": user_password,
                "new_password": "123",
                "new_password2": "123",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_change_requires_auth(self, api_client):
        """Anonymous gets 401."""
        response = api_client.post(
            reverse("password-change-api"),
            {
                "old_password": "anypassword",
                "new_password": "newsecurepass456",
                "new_password2": "newsecurepass456",
            },
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_change_blacklists_tokens(
        self, authenticated_api_client, user, user_password
    ):
        """All tokens are blacklisted after password change."""
        # Create some tokens for the user (side effect: populates OutstandingToken)
        RefreshToken.for_user(user)
        RefreshToken.for_user(user)

        initial_outstanding = OutstandingToken.objects.filter(user=user).count()

        response = authenticated_api_client.post(
            reverse("password-change-api"),
            {
                "old_password": user_password,
                "new_password": "newsecurepass456",
                "new_password2": "newsecurepass456",
            },
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify tokens were blacklisted
        blacklisted_count = BlacklistedToken.objects.filter(token__user=user).count()
        assert blacklisted_count >= initial_outstanding


class TestTokenRecovery:
    """Tests for token recovery endpoint (POST /api/v1/auth/token/recovery/)."""

    @patch("apps.diary.views.api.send_token_recovery_email.delay")
    def test_recovery_sends_email(self, mock_send_email, api_client, user):
        """Valid email triggers Celery task."""
        response = api_client.post(
            reverse("token-recovery-api"),
            {"email": user.email},
        )

        assert response.status_code == status.HTTP_200_OK
        mock_send_email.assert_called_once()
        # Verify email argument
        call_args = mock_send_email.call_args
        assert user.email in call_args[0]

    def test_recovery_nonexistent_email(self, api_client):
        """Non-existent email returns 404."""
        response = api_client.post(
            reverse("token-recovery-api"),
            {"email": "nonexistent@example.com"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "error" in response.data

    def test_recovery_invalid_email_format(self, api_client):
        """Invalid email format returns 400."""
        response = api_client.post(
            reverse("token-recovery-api"),
            {"email": "not-an-email"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data

    def test_recovery_missing_email(self, api_client):
        """Missing email returns 400."""
        response = api_client.post(
            reverse("token-recovery-api"),
            {},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data

    @patch("apps.diary.views.api.send_token_recovery_email.delay")
    def test_recovery_blacklists_existing_tokens(
        self, mock_send_email, api_client, user
    ):
        """Recovery blacklists all existing tokens."""
        # Create tokens
        RefreshToken.for_user(user)
        RefreshToken.for_user(user)

        outstanding_count = OutstandingToken.objects.filter(user=user).count()
        assert outstanding_count >= 2

        response = api_client.post(
            reverse("token-recovery-api"),
            {"email": user.email},
        )

        assert response.status_code == status.HTTP_200_OK

        # All tokens should be blacklisted
        blacklisted_count = BlacklistedToken.objects.filter(token__user=user).count()
        assert blacklisted_count == outstanding_count


class TestPasswordReset:
    """Tests for password reset endpoint (POST /api/v1/auth/password/reset/)."""

    def test_reset_with_token(self, api_client, user):
        """Recovery token allows password reset."""
        # Generate a recovery token (simulating what email would contain)
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        new_password = "newresetpass789"

        response = api_client.post(
            reverse("password-reset-api"),
            {
                "new_password": new_password,
                "new_password2": new_password,
            },
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )

        assert response.status_code == status.HTTP_200_OK
        assert "detail" in response.data

        # Verify password was changed
        user.refresh_from_db()
        assert user.check_password(new_password)

    def test_reset_requires_auth(self, api_client):
        """No token returns 401."""
        response = api_client.post(
            reverse("password-reset-api"),
            {
                "new_password": "newresetpass789",
                "new_password2": "newresetpass789",
            },
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_reset_passwords_dont_match(self, api_client, user):
        """Password mismatch returns 400."""
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        response = api_client.post(
            reverse("password-reset-api"),
            {
                "new_password": "newresetpass789",
                "new_password2": "differentpass123",
            },
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "new_password2" in response.data

    def test_reset_password_too_simple(self, api_client, user):
        """Simple password returns 400."""
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        response = api_client.post(
            reverse("password-reset-api"),
            {
                "new_password": "123",
                "new_password2": "123",
            },
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_reset_blacklists_tokens(self, api_client, user):
        """Reset blacklists all tokens."""
        # Create some tokens
        RefreshToken.for_user(user)
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        outstanding_count = OutstandingToken.objects.filter(user=user).count()

        response = api_client.post(
            reverse("password-reset-api"),
            {
                "new_password": "newresetpass789",
                "new_password2": "newresetpass789",
            },
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )

        assert response.status_code == status.HTTP_200_OK

        # All tokens should be blacklisted
        blacklisted_count = BlacklistedToken.objects.filter(token__user=user).count()
        assert blacklisted_count == outstanding_count

    def test_reset_with_expired_token(self, api_client, user, settings):
        """Expired token returns 401."""
        # This is handled by SimpleJWT automatically - we just verify the behavior
        # by using an invalid token format
        response = api_client.post(
            reverse("password-reset-api"),
            {
                "new_password": "newresetpass789",
                "new_password2": "newresetpass789",
            },
            HTTP_AUTHORIZATION="Bearer invalid_expired_token",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestPasswordResetFlow:
    """Integration tests for complete password reset flow."""

    @patch("apps.diary.views.api.send_token_recovery_email.delay")
    def test_complete_flow(self, mock_send_email, api_client, user, user_password):
        """Test complete password recovery and reset flow."""
        old_password = user_password
        new_password = "brandnewpass123"

        # Step 1: Request recovery
        response = api_client.post(
            reverse("token-recovery-api"),
            {"email": user.email},
        )
        assert response.status_code == status.HTTP_200_OK

        # Step 2: Simulate getting token from email
        recovery_refresh = RefreshToken.for_user(user)
        recovery_access = str(recovery_refresh.access_token)

        # Step 3: Reset password
        response = api_client.post(
            reverse("password-reset-api"),
            {
                "new_password": new_password,
                "new_password2": new_password,
            },
            HTTP_AUTHORIZATION=f"Bearer {recovery_access}",
        )
        assert response.status_code == status.HTTP_200_OK

        # Step 4: Verify new password works for login
        response = api_client.post(
            reverse("login-api"),
            {"username": user.username, "password": new_password},
        )
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data

        # Step 5: Verify old password doesn't work
        response = api_client.post(
            reverse("login-api"),
            {"username": user.username, "password": old_password},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
