"""
Tests for Like API endpoints.

Tests cover:
- Like toggle (create/remove)
- Like batch endpoint
- Like list (analytics)
- Like detail
"""

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from apps.diary.models import Like

pytestmark = pytest.mark.django_db


class TestLikeToggle:
    """Tests for like toggle endpoint (POST /api/v1/likes/toggle/)."""

    def test_toggle_creates_like(self, authenticated_api_client, user, post):
        """First toggle creates like (201)."""
        response = authenticated_api_client.post(
            reverse("like-toggle-api"),
            {"post": post.id},
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert Like.objects.filter(user=user, post=post).exists()

    def test_toggle_removes_like(self, authenticated_api_client, user, post, like):
        """Second toggle removes like (204)."""
        assert Like.objects.filter(user=user, post=post).exists()

        response = authenticated_api_client.post(
            reverse("like-toggle-api"),
            {"post": post.id},
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Like.objects.filter(user=user, post=post).exists()

    def test_toggle_requires_auth(self, api_client, post):
        """Anonymous gets 401."""
        response = api_client.post(
            reverse("like-toggle-api"),
            {"post": post.id},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert not Like.objects.filter(post=post).exists()

    def test_toggle_unpublished_rejected(
        self, authenticated_api_client, unpublished_post
    ):
        """Cannot like unpublished post."""
        response = authenticated_api_client.post(
            reverse("like-toggle-api"),
            {"post": unpublished_post.id},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not Like.objects.filter(post=unpublished_post).exists()

    def test_toggle_nonexistent_post(self, authenticated_api_client):
        """Non-existent post returns 400."""
        response = authenticated_api_client.post(
            reverse("like-toggle-api"),
            {"post": 99999},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_toggle_returns_like_data_on_create(
        self, authenticated_api_client, user, post
    ):
        """Like creation returns serialized like data."""
        response = authenticated_api_client.post(
            reverse("like-toggle-api"),
            {"post": post.id},
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert "id" in response.data
        assert "url" in response.data
        assert "user" in response.data
        assert "post" in response.data
        assert "created" in response.data

    def test_toggle_missing_post_field(self, authenticated_api_client):
        """Missing post field returns 400."""
        response = authenticated_api_client.post(
            reverse("like-toggle-api"),
            {},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "post" in response.data


class TestLikeBatch:
    """Tests for like batch endpoint (GET /api/v1/likes/batch/)."""

    def test_batch_returns_counts(self, api_client, post, like_factory, user):
        """Returns count for each post ID."""
        # Create 3 likes on post
        for _ in range(3):
            like_factory(post=post)

        response = api_client.get(
            reverse("like-batch-api"),
            {"ids": str(post.id)},
        )

        assert response.status_code == status.HTTP_200_OK
        assert str(post.id) in response.data
        assert response.data[str(post.id)]["count"] == 3

    def test_batch_returns_liked_status_authenticated(
        self, authenticated_api_client, user, post, like
    ):
        """Returns liked: true for auth user's liked posts."""
        response = authenticated_api_client.get(
            reverse("like-batch-api"),
            {"ids": str(post.id)},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data[str(post.id)]["liked"] is True

    def test_batch_returns_liked_false_for_unliked(
        self, authenticated_api_client, user, post
    ):
        """Returns liked: false for posts user hasn't liked."""
        response = authenticated_api_client.get(
            reverse("like-batch-api"),
            {"ids": str(post.id)},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data[str(post.id)]["liked"] is False

    def test_batch_multiple_posts(
        self, api_client, post_factory, like_factory, user_factory
    ):
        """Handles multiple post IDs."""
        posts = [post_factory() for _ in range(3)]
        # Add different number of likes to each
        for i, p in enumerate(posts):
            for _ in range(i + 1):
                like_factory(post=p)

        ids = ",".join(str(p.id) for p in posts)
        response = api_client.get(
            reverse("like-batch-api"),
            {"ids": ids},
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 3
        assert response.data[str(posts[0].id)]["count"] == 1
        assert response.data[str(posts[1].id)]["count"] == 2
        assert response.data[str(posts[2].id)]["count"] == 3

    def test_batch_empty_ids(self, api_client):
        """Empty ids returns empty object."""
        response = api_client.get(reverse("like-batch-api"), {"ids": ""})

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {}

    def test_batch_no_ids_param(self, api_client):
        """No ids param returns empty object."""
        response = api_client.get(reverse("like-batch-api"))

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {}

    def test_batch_invalid_ids(self, api_client):
        """Invalid IDs return 400."""
        response = api_client.get(
            reverse("like-batch-api"),
            {"ids": "invalid,abc"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_batch_nonexistent_post_excluded(self, api_client, post):
        """Non-existent post IDs are excluded from results."""
        response = api_client.get(
            reverse("like-batch-api"),
            {"ids": f"{post.id},99999"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert str(post.id) in response.data
        assert "99999" not in response.data


class TestLikeList:
    """Tests for like list endpoint (GET /api/v1/likes/) - analytics."""

    def test_list_returns_aggregated_data(self, api_client, like_factory):
        """Returns likes aggregated by date."""
        # Create some likes
        for _ in range(5):
            like_factory()

        response = api_client.get(reverse("like-list-api"))

        assert response.status_code == status.HTTP_200_OK
        assert "results" in response.data
        # Should have aggregated data with date and count
        for result in response.data["results"]:
            assert "created__date" in result
            assert "likes" in result

    def test_list_is_paginated(self, api_client):
        """Like list is paginated."""
        response = api_client.get(reverse("like-list-api"))

        assert response.status_code == status.HTTP_200_OK
        assert "count" in response.data
        assert "next" in response.data
        assert "previous" in response.data
        assert "results" in response.data


class TestLikeDetail:
    """Tests for like detail endpoint (GET /api/v1/likes/{id}/)."""

    def test_detail_returns_like(self, api_client, like):
        """Returns like detail with user and post references."""
        response = api_client.get(reverse("like-detail-api", args=[like.id]))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == like.id
        assert "user" in response.data
        assert "post" in response.data
        assert "created" in response.data
        assert "url" in response.data

    def test_detail_nonexistent_like(self, api_client):
        """Non-existent like returns 404."""
        response = api_client.get(reverse("like-detail-api", args=[99999]))

        assert response.status_code == status.HTTP_404_NOT_FOUND
