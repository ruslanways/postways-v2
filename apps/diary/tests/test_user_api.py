"""
Tests for User API endpoints.

Tests cover:
- User registration (create)
- User list (admin only)
- User detail retrieval
- User deletion
"""

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from apps.diary.models import CustomUser

pytestmark = pytest.mark.django_db


class TestUserRegistration:
    """Tests for user registration endpoint (POST /api/v1/users/)."""

    def test_register_success(self, api_client):
        """Valid data creates user and returns 201."""
        response = api_client.post(
            reverse("user-list-create-api"),
            {
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "securepass123",
                "password2": "securepass123",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert CustomUser.objects.filter(username="newuser").exists()
        user = CustomUser.objects.get(username="newuser")
        assert user.email == "newuser@example.com"
        assert user.check_password("securepass123")

    def test_register_duplicate_email(self, api_client, user):
        """Duplicate email returns 400."""
        response = api_client.post(
            reverse("user-list-create-api"),
            {
                "username": "newuser2",
                "email": user.email,  # existing email
                "password": "securepass123",
                "password2": "securepass123",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data

    def test_register_duplicate_username(self, api_client, user):
        """Duplicate username returns 400."""
        response = api_client.post(
            reverse("user-list-create-api"),
            {
                "username": user.username,  # existing username
                "email": "different@example.com",
                "password": "securepass123",
                "password2": "securepass123",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "username" in response.data

    def test_register_password_mismatch(self, api_client):
        """Password mismatch returns 400."""
        response = api_client.post(
            reverse("user-list-create-api"),
            {
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "securepass123",
                "password2": "differentpass123",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not CustomUser.objects.filter(username="newuser").exists()

    def test_register_password_too_simple(self, api_client):
        """Simple password returns 400 (Django password validation)."""
        response = api_client.post(
            reverse("user-list-create-api"),
            {
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "123",
                "password2": "123",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not CustomUser.objects.filter(username="newuser").exists()

    def test_register_password_similar_to_username(self, api_client):
        """Password similar to username returns 400."""
        response = api_client.post(
            reverse("user-list-create-api"),
            {
                "username": "testuser",
                "email": "test@example.com",
                "password": "testuser123",
                "password2": "testuser123",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not CustomUser.objects.filter(username="testuser").exists()

    def test_register_missing_required_fields(self, api_client):
        """Missing email or password2 returns 400."""
        # Missing email
        response = api_client.post(
            reverse("user-list-create-api"),
            {
                "username": "newuser",
                "password": "securepass123",
                "password2": "securepass123",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data

        # Missing password2
        response = api_client.post(
            reverse("user-list-create-api"),
            {
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "securepass123",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "password2" in response.data

    def test_register_invalid_email_format(self, api_client):
        """Invalid email format returns 400."""
        response = api_client.post(
            reverse("user-list-create-api"),
            {
                "username": "newuser",
                "email": "invalid-email",
                "password": "securepass123",
                "password2": "securepass123",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data

    def test_register_authenticated_forbidden(self, authenticated_api_client):
        """Authenticated users cannot register (must be anonymous)."""
        response = authenticated_api_client.post(
            reverse("user-list-create-api"),
            {
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "securepass123",
                "password2": "securepass123",
            },
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestUserList:
    """Tests for user list endpoint (GET /api/v1/users/)."""

    def test_list_users_admin_only(self, admin_api_client, user):
        """Admin user gets 200 with list of users."""
        response = admin_api_client.get(reverse("user-list-create-api"))

        assert response.status_code == status.HTTP_200_OK
        assert "results" in response.data

    def test_list_users_regular_user_forbidden(self, authenticated_api_client):
        """Regular user gets 403."""
        response = authenticated_api_client.get(reverse("user-list-create-api"))

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_users_anonymous_unauthorized(self, api_client):
        """Anonymous user gets 401."""
        response = api_client.get(reverse("user-list-create-api"))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestUserDetail:
    """Tests for user detail endpoint (GET /api/v1/users/{id}/)."""

    def test_view_own_profile(self, authenticated_api_client, user):
        """Owner can view their profile."""
        response = authenticated_api_client.get(
            reverse("user-detail-update-destroy-api", args=[user.id])
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["username"] == user.username
        assert response.data["email"] == user.email

    def test_view_other_profile_allowed(
        self, authenticated_api_client, user, other_user
    ):
        """Authenticated user can view other profiles."""
        response = authenticated_api_client.get(
            reverse("user-detail-update-destroy-api", args=[other_user.id])
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["username"] == other_user.username

    def test_admin_can_view_any_profile(self, admin_api_client, user):
        """Admin can view any user's profile."""
        response = admin_api_client.get(
            reverse("user-detail-update-destroy-api", args=[user.id])
        )

        assert response.status_code == status.HTTP_200_OK

    def test_view_profile_anonymous_unauthorized(self, api_client, user):
        """Anonymous user gets 401."""
        response = api_client.get(
            reverse("user-detail-update-destroy-api", args=[user.id])
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_view_profile_includes_posts_and_likes(
        self, authenticated_api_client, user, post, like
    ):
        """Profile includes posts and likes."""
        response = authenticated_api_client.get(
            reverse("user-detail-update-destroy-api", args=[user.id])
        )

        assert response.status_code == status.HTTP_200_OK
        assert "posts" in response.data
        assert "likes" in response.data

    def test_owner_sees_own_unpublished_posts(
        self, authenticated_api_client, user, unpublished_post
    ):
        """Profile owner can see their own unpublished posts in the API."""
        response = authenticated_api_client.get(
            reverse("user-detail-update-destroy-api", args=[user.id])
        )

        assert response.status_code == status.HTTP_200_OK
        # Check that unpublished post URL is in the posts list
        unpublished_post_url = reverse("post-detail-api", args=[unpublished_post.id])
        assert any(unpublished_post_url in url for url in response.data["posts"])

    def test_admin_sees_unpublished_posts_on_any_profile(
        self, admin_api_client, user, unpublished_post
    ):
        """Admin can see unpublished posts on any user's profile."""
        response = admin_api_client.get(
            reverse("user-detail-update-destroy-api", args=[user.id])
        )

        assert response.status_code == status.HTTP_200_OK
        # Check that unpublished post URL is in the posts list
        unpublished_post_url = reverse("post-detail-api", args=[unpublished_post.id])
        assert any(unpublished_post_url in url for url in response.data["posts"])

    def test_non_owner_cannot_see_unpublished_posts(
        self, other_user_api_client, user, unpublished_post
    ):
        """Non-owner cannot see unpublished posts on another user's profile."""
        response = other_user_api_client.get(
            reverse("user-detail-update-destroy-api", args=[user.id])
        )

        assert response.status_code == status.HTTP_200_OK
        # Check that unpublished post URL is NOT in the posts list
        unpublished_post_url = reverse("post-detail-api", args=[unpublished_post.id])
        assert not any(unpublished_post_url in url for url in response.data["posts"])


class TestUserUpdate:
    """Tests for user update (PUT/PATCH not allowed - use dedicated endpoints)."""

    def test_update_via_put_not_allowed(self, authenticated_api_client, user):
        """PUT method returns 405 (use dedicated endpoints)."""
        response = authenticated_api_client.put(
            reverse("user-detail-update-destroy-api", args=[user.id]),
            {"email": "newemail@example.com"},
        )

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_update_via_patch_not_allowed(self, authenticated_api_client, user):
        """PATCH method returns 405 (use dedicated endpoints)."""
        response = authenticated_api_client.patch(
            reverse("user-detail-update-destroy-api", args=[user.id]),
            {"email": "newemail@example.com"},
        )

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


class TestUserDelete:
    """Tests for user deletion endpoint (DELETE /api/v1/users/{id}/)."""

    def test_delete_own_account(self, authenticated_api_client, user):
        """Owner can delete their account."""
        user_id = user.id
        response = authenticated_api_client.delete(
            reverse("user-detail-update-destroy-api", args=[user_id])
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not CustomUser.objects.filter(id=user_id).exists()

    def test_delete_other_account_forbidden(
        self, authenticated_api_client, user, other_user
    ):
        """Non-owner cannot delete another user's account."""
        response = authenticated_api_client.delete(
            reverse("user-detail-update-destroy-api", args=[other_user.id])
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert CustomUser.objects.filter(id=other_user.id).exists()

    def test_admin_can_delete_any_account(self, admin_api_client, user):
        """Admin can delete any user's account."""
        user_id = user.id
        response = admin_api_client.delete(
            reverse("user-detail-update-destroy-api", args=[user_id])
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not CustomUser.objects.filter(id=user_id).exists()

    def test_delete_anonymous_unauthorized(self, api_client, user):
        """Anonymous user gets 401."""
        response = api_client.delete(
            reverse("user-detail-update-destroy-api", args=[user.id])
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert CustomUser.objects.filter(id=user.id).exists()

    def test_delete_cascades_posts_and_likes(
        self, authenticated_api_client, user, post, like
    ):
        """Deleting user cascades to their posts and likes."""
        from apps.diary.models import Like, Post

        user_id = user.id
        post_id = post.id
        like_id = like.id

        response = authenticated_api_client.delete(
            reverse("user-detail-update-destroy-api", args=[user_id])
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not CustomUser.objects.filter(id=user_id).exists()
        assert not Post.objects.filter(id=post_id).exists()
        assert not Like.objects.filter(id=like_id).exists()
