"""
Tests for username change API endpoint.

Tests cover:
- Username change validation
- Password verification
- Uniqueness check (case-insensitive)
- 30-day cooldown enforcement
"""

from datetime import timedelta

from django.utils import timezone

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

pytestmark = pytest.mark.django_db


class TestUsernameChange:
    """Tests for username change endpoint (POST /api/v1/auth/username/change/)."""

    def test_change_success(self, authenticated_api_client, user, user_password):
        """Valid password and unique username succeeds."""
        response = authenticated_api_client.post(
            reverse("username-change-api"),
            {
                "password": user_password,
                "new_username": "NewUsername",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert "detail" in response.data
        assert response.data["username"] == "NewUsername"

        # Verify username was changed
        user.refresh_from_db()
        assert user.username == "NewUsername"

    def test_change_requires_auth(self, api_client):
        """Anonymous gets 401."""
        response = api_client.post(
            reverse("username-change-api"),
            {
                "password": "anypassword",
                "new_username": "NewUsername",
            },
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_change_wrong_password(self, authenticated_api_client, user):
        """Wrong password returns 400."""
        old_username = user.username

        response = authenticated_api_client.post(
            reverse("username-change-api"),
            {
                "password": "wrongpassword",
                "new_username": "NewUsername",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "password" in response.data

        # Username should remain unchanged
        user.refresh_from_db()
        assert user.username == old_username

    def test_change_duplicate_rejected(
        self, authenticated_api_client, user, user_password, other_user
    ):
        """Duplicate username returns 400."""
        response = authenticated_api_client.post(
            reverse("username-change-api"),
            {
                "password": user_password,
                "new_username": other_user.username,
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "new_username" in response.data

    def test_change_duplicate_case_insensitive(
        self, authenticated_api_client, user, user_password, other_user
    ):
        """Duplicate username check is case-insensitive."""
        response = authenticated_api_client.post(
            reverse("username-change-api"),
            {
                "password": user_password,
                "new_username": other_user.username.upper(),  # same, different case
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "new_username" in response.data

    def test_change_sets_timestamp(self, authenticated_api_client, user, user_password):
        """Successful change updates username_last_changed."""
        assert user.username_last_changed is None

        response = authenticated_api_client.post(
            reverse("username-change-api"),
            {
                "password": user_password,
                "new_username": "NewUsername",
            },
        )

        assert response.status_code == status.HTTP_200_OK

        user.refresh_from_db()
        assert user.username_last_changed is not None

    def test_change_cooldown_enforced(
        self, authenticated_api_client, user, user_password
    ):
        """30-day cooldown prevents immediate second change."""
        # First change
        response = authenticated_api_client.post(
            reverse("username-change-api"),
            {
                "password": user_password,
                "new_username": "FirstChange",
            },
        )
        assert response.status_code == status.HTTP_200_OK

        # Immediate second change should fail
        response = authenticated_api_client.post(
            reverse("username-change-api"),
            {
                "password": user_password,
                "new_username": "SecondChange",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "new_username" in response.data
        assert "30 days" in str(response.data["new_username"])

        # Username should remain at first change
        user.refresh_from_db()
        assert user.username == "FirstChange"

    def test_change_after_cooldown_expires(
        self, authenticated_api_client, user, user_password
    ):
        """Change succeeds after 30-day cooldown."""
        # Set username_last_changed to 31 days ago
        user.username_last_changed = timezone.now() - timedelta(days=31)
        user.save()

        response = authenticated_api_client.post(
            reverse("username-change-api"),
            {
                "password": user_password,
                "new_username": "AfterCooldown",
            },
        )

        assert response.status_code == status.HTTP_200_OK

        user.refresh_from_db()
        assert user.username == "AfterCooldown"

    def test_change_cooldown_at_boundary(
        self, authenticated_api_client, user, user_password
    ):
        """Change succeeds at exactly 30 days (cooldown has passed)."""
        # Set username_last_changed to exactly 30 days ago
        # The cooldown check is `now < cooldown_end`, so at exactly 30 days
        # the check fails (now == cooldown_end), meaning cooldown has passed
        user.username_last_changed = timezone.now() - timedelta(days=30)
        user.save()

        response = authenticated_api_client.post(
            reverse("username-change-api"),
            {
                "password": user_password,
                "new_username": "AtBoundary",
            },
        )

        # At exactly 30 days, the change should succeed
        assert response.status_code == status.HTTP_200_OK

    def test_change_cooldown_just_before_boundary(
        self, authenticated_api_client, user, user_password
    ):
        """Change fails just before 30 days (still within cooldown)."""
        # Set username_last_changed to 29 days ago (still within cooldown)
        user.username_last_changed = timezone.now() - timedelta(days=29)
        user.save()

        response = authenticated_api_client.post(
            reverse("username-change-api"),
            {
                "password": user_password,
                "new_username": "BeforeBoundary",
            },
        )

        # Should still fail - cooldown not complete
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_change_missing_password(self, authenticated_api_client, user):
        """Missing password returns 400."""
        response = authenticated_api_client.post(
            reverse("username-change-api"),
            {"new_username": "NewUsername"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "password" in response.data

    def test_change_missing_username(
        self, authenticated_api_client, user, user_password
    ):
        """Missing new_username returns 400."""
        response = authenticated_api_client.post(
            reverse("username-change-api"),
            {"password": user_password},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "new_username" in response.data

    def test_change_username_too_long(
        self, authenticated_api_client, user, user_password
    ):
        """Username longer than 150 chars returns 400."""
        response = authenticated_api_client.post(
            reverse("username-change-api"),
            {
                "password": user_password,
                "new_username": "a" * 151,
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "new_username" in response.data

    def test_change_username_invalid_chars(
        self, authenticated_api_client, user, user_password
    ):
        """Username with invalid characters returns 400."""
        response = authenticated_api_client.post(
            reverse("username-change-api"),
            {
                "password": user_password,
                "new_username": "user name with spaces",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "new_username" in response.data

    def test_change_to_same_username_allowed(
        self, authenticated_api_client, user, user_password
    ):
        """Changing to same username (case change) is allowed."""
        old_username = user.username

        response = authenticated_api_client.post(
            reverse("username-change-api"),
            {
                "password": user_password,
                "new_username": old_username.upper(),  # Same username, different case
            },
        )

        # This should succeed - user is changing their own username's case
        assert response.status_code == status.HTTP_200_OK

        user.refresh_from_db()
        assert user.username == old_username.upper()
