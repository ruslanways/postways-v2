"""
Tests for JWT authentication endpoints.

Tests cover:
- Login with valid/invalid credentials
- Token refresh with valid/blacklisted tokens
- Token verification
"""

import pytest
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

pytestmark = pytest.mark.django_db


class TestJWTLogin:
    """Tests for the JWT login endpoint."""

    def test_login_success(self, api_client, user, user_password):
        """Valid credentials return access and refresh tokens."""
        response = api_client.post(
            reverse("login-api"),
            {"username": user.username, "password": user_password},
        )

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data

    def test_login_invalid_password(self, api_client, user):
        """Wrong password returns 401."""
        response = api_client.post(
            reverse("login-api"),
            {"username": user.username, "password": "wrongpassword"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_invalid_username(self, api_client):
        """Non-existent username returns 401."""
        response = api_client.post(
            reverse("login-api"),
            {"username": "nonexistent", "password": "anypassword"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_missing_fields(self, api_client):
        """Missing username or password returns 400."""
        response = api_client.post(reverse("login-api"), {"username": "test"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestJWTRefresh:
    """Tests for the JWT token refresh endpoint."""

    def test_refresh_valid_token(self, api_client, user):
        """Valid refresh token returns new access and refresh tokens."""
        refresh = RefreshToken.for_user(user)

        response = api_client.post(
            reverse("token-refresh-api"),
            {"refresh": str(refresh)},
        )

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data
        # New refresh token should be different (rotation)
        assert response.data["refresh"] != str(refresh)

    def test_refresh_blacklisted_token(self, api_client, user):
        """Blacklisted refresh token returns 401."""
        refresh = RefreshToken.for_user(user)
        # Blacklist the token
        refresh.blacklist()

        response = api_client.post(
            reverse("token-refresh-api"),
            {"refresh": str(refresh)},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_invalid_token(self, api_client):
        """Invalid refresh token returns 401."""
        response = api_client.post(
            reverse("token-refresh-api"),
            {"refresh": "invalid_token_string"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_rotates_and_blacklists_old_token(self, api_client, user):
        """After refresh, old token should be blacklisted (rotation)."""
        refresh = RefreshToken.for_user(user)
        old_jti = refresh["jti"]

        response = api_client.post(
            reverse("token-refresh-api"),
            {"refresh": str(refresh)},
        )

        assert response.status_code == status.HTTP_200_OK
        # Old token should now be blacklisted
        assert BlacklistedToken.objects.filter(token__jti=old_jti).exists()


class TestJWTVerify:
    """Tests for the JWT token verification endpoint."""

    def test_verify_valid_access_token(self, api_client, user):
        """Valid access token returns 200."""
        refresh = RefreshToken.for_user(user)
        access = str(refresh.access_token)

        response = api_client.post(
            reverse("token-verify-api"),
            {"token": access},
        )

        assert response.status_code == status.HTTP_200_OK

    def test_verify_valid_refresh_token(self, api_client, user):
        """Valid refresh token returns 200."""
        refresh = RefreshToken.for_user(user)

        response = api_client.post(
            reverse("token-verify-api"),
            {"token": str(refresh)},
        )

        assert response.status_code == status.HTTP_200_OK

    def test_verify_invalid_token(self, api_client):
        """Invalid token returns 401."""
        response = api_client.post(
            reverse("token-verify-api"),
            {"token": "invalid_token_string"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_verify_blacklisted_refresh_token(self, api_client, user):
        """Blacklisted refresh token returns 400 (token is invalid/blacklisted)."""
        refresh = RefreshToken.for_user(user)
        refresh.blacklist()

        response = api_client.post(
            reverse("token-verify-api"),
            {"token": str(refresh)},
        )

        # Blacklisted tokens fail verification
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestMyTokenObtainPairView:
    """Tests for the custom login endpoint that sets refresh as cookie."""

    def test_my_login_returns_access_token(self, api_client, user, user_password):
        """Custom login returns access token in body."""
        response = api_client.post(
            reverse("my-login-api"),
            {"username": user.username, "password": user_password},
        )

        assert response.status_code == status.HTTP_200_OK
        assert "access_token" in response.data
        # Refresh token should be in cookie, not in body
        assert "refresh" not in response.data

    def test_my_login_sets_refresh_cookie(self, api_client, user, user_password):
        """Custom login sets refresh_token as httponly cookie."""
        response = api_client.post(
            reverse("my-login-api"),
            {"username": user.username, "password": user_password},
        )

        assert response.status_code == status.HTTP_200_OK
        assert "refresh_token" in response.cookies
        # Verify cookie attributes
        cookie = response.cookies["refresh_token"]
        assert cookie["httponly"]
        assert cookie["samesite"] == "Strict"

    def test_my_login_invalid_credentials(self, api_client, user):
        """Custom login returns 401 for invalid credentials."""
        response = api_client.post(
            reverse("my-login-api"),
            {"username": user.username, "password": "wrongpassword"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
