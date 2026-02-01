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
        assert "created_at" in response.data

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
    """Tests for like list endpoint (GET /api/v1/likes/)."""

    def test_list_no_filters_returns_total_count(self, api_client, like_factory):
        """No filters returns total like count."""
        for _ in range(5):
            like_factory()

        response = api_client.get(reverse("like-list-api"))

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"total_likes": 5}

    def test_list_by_user_returns_paginated_likes(
        self, api_client, like_factory, user, post_factory
    ):
        """Filter by user returns paginated likes with post titles."""
        posts = [post_factory(title=f"Post {i}") for i in range(3)]
        for p in posts:
            like_factory(user=user, post=p)

        response = api_client.get(reverse("like-list-api"), {"user": user.id})

        assert response.status_code == status.HTTP_200_OK
        assert "results" in response.data
        assert len(response.data["results"]) == 3
        for result in response.data["results"]:
            assert "url" in result
            assert "id" in result
            assert "created_at" in result
            assert "post" in result
            assert "title" in result["post"]
            assert "url" in result["post"]

    def test_list_by_user_truncates_long_titles(
        self, api_client, like_factory, user, post_factory
    ):
        """Long post titles are truncated to 50 chars."""
        long_title = "A" * 100
        post = post_factory(title=long_title)
        like_factory(user=user, post=post)

        response = api_client.get(reverse("like-list-api"), {"user": user.id})

        assert response.status_code == status.HTTP_200_OK
        title = response.data["results"][0]["post"]["title"]
        assert len(title) == 53  # 50 chars + "..."
        assert title.endswith("...")

    def test_list_by_post_returns_paginated_likes(
        self, api_client, like_factory, post, user_factory
    ):
        """Filter by post returns paginated likes with usernames."""
        users = [user_factory(username=f"user{i}") for i in range(3)]
        for u in users:
            like_factory(user=u, post=post)

        response = api_client.get(reverse("like-list-api"), {"post": post.id})

        assert response.status_code == status.HTTP_200_OK
        assert "results" in response.data
        assert len(response.data["results"]) == 3
        for result in response.data["results"]:
            assert "url" in result
            assert "id" in result
            assert "created_at" in result
            assert "user" in result
            assert "username" in result["user"]
            assert "url" in result["user"]

    def test_list_by_user_and_post_returns_liked_true(
        self, api_client, like, user, post
    ):
        """Filter by both user and post returns liked: true when like exists."""
        response = api_client.get(
            reverse("like-list-api"), {"user": user.id, "post": post.id}
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"liked": True}

    def test_list_by_user_and_post_returns_liked_false(self, api_client, user, post):
        """Filter by both user and post returns liked: false when no like."""
        response = api_client.get(
            reverse("like-list-api"), {"user": user.id, "post": post.id}
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"liked": False}

    def test_list_by_user_ordered_newest_first(
        self, api_client, like_factory, user, post_factory
    ):
        """Likes filtered by user are ordered by newest first."""
        import time

        posts = []
        for i in range(3):
            p = post_factory(title=f"Post {i}")
            like_factory(user=user, post=p)
            posts.append(p)
            time.sleep(0.01)  # Ensure different timestamps

        response = api_client.get(reverse("like-list-api"), {"user": user.id})

        assert response.status_code == status.HTTP_200_OK
        # Newest first means the last created post should be first
        assert response.data["results"][0]["post"]["id"] == posts[-1].id

    def test_list_by_user_is_paginated(
        self, api_client, like_factory, user, post_factory
    ):
        """Likes filtered by user are paginated."""
        for _ in range(3):
            like_factory(user=user, post=post_factory())

        response = api_client.get(reverse("like-list-api"), {"user": user.id})

        assert response.status_code == status.HTTP_200_OK
        assert "count" in response.data
        assert "next" in response.data
        assert "previous" in response.data
        assert "results" in response.data


class TestLikeDetail:
    """Tests for like detail endpoint (GET /api/v1/likes/{id}/)."""

    def test_detail_returns_like(self, api_client, like):
        """Returns like detail with user and post info."""
        response = api_client.get(reverse("like-detail-api", args=[like.id]))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == like.id
        assert "url" in response.data
        assert "created_at" in response.data
        # User should include id, username, and url
        assert "user" in response.data
        assert "id" in response.data["user"]
        assert "username" in response.data["user"]
        assert "url" in response.data["user"]
        # Post should include id, title, and url
        assert "post" in response.data
        assert "id" in response.data["post"]
        assert "title" in response.data["post"]
        assert "url" in response.data["post"]

    def test_detail_truncates_long_post_title(
        self, api_client, like_factory, post_factory
    ):
        """Long post titles are truncated to 50 chars."""
        long_title = "A" * 100
        post = post_factory(title=long_title)
        like = like_factory(post=post)

        response = api_client.get(reverse("like-detail-api", args=[like.id]))

        assert response.status_code == status.HTTP_200_OK
        title = response.data["post"]["title"]
        assert len(title) == 53  # 50 chars + "..."
        assert title.endswith("...")

    def test_detail_nonexistent_like(self, api_client):
        """Non-existent like returns 404."""
        response = api_client.get(reverse("like-detail-api", args=[99999]))

        assert response.status_code == status.HTTP_404_NOT_FOUND
