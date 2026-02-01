"""
Tests for Post API endpoints.

Tests cover:
- Post listing (published only)
- Post creation (authenticated users only)
- Post detail retrieval (permission checks for unpublished)
- Post update (owner only)
- Post deletion (owner or admin)
- Profanity validation
"""

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from apps.diary.models import Post

pytestmark = pytest.mark.django_db


class TestPostList:
    """Tests for post list endpoint (GET /api/v1/posts/)."""

    def test_list_published_only(self, api_client, post, unpublished_post):
        """Anonymous sees only published posts."""
        response = api_client.get(reverse("post-list-create-api"))

        assert response.status_code == status.HTTP_200_OK
        post_ids = [p["id"] for p in response.data["results"]]
        assert post.id in post_ids
        assert unpublished_post.id not in post_ids

    def test_list_authenticated_sees_published_only(
        self, authenticated_api_client, post, unpublished_post
    ):
        """Authenticated user also sees only published posts in list."""
        response = authenticated_api_client.get(reverse("post-list-create-api"))

        assert response.status_code == status.HTTP_200_OK
        post_ids = [p["id"] for p in response.data["results"]]
        assert post.id in post_ids
        assert unpublished_post.id not in post_ids

    def test_list_includes_like_count(self, api_client, post, like_factory, user):
        """Post list includes like_count in stats."""
        # Create some likes
        like_factory(post=post, user=user)

        response = api_client.get(reverse("post-list-create-api"))

        assert response.status_code == status.HTTP_200_OK
        post_data = next(p for p in response.data["results"] if p["id"] == post.id)
        assert "stats" in post_data
        assert post_data["stats"]["like_count"] == 1
        # Anonymous users should not see has_liked field at all
        assert "has_liked" not in post_data["stats"]

    def test_list_is_paginated(self, api_client, post_factory, user):
        """Post list is paginated."""
        # Create more posts than one page
        for _ in range(15):
            post_factory(author=user)

        response = api_client.get(reverse("post-list-create-api"))

        assert response.status_code == status.HTTP_200_OK
        assert "count" in response.data
        assert "next" in response.data
        assert "previous" in response.data
        assert "results" in response.data

    def test_list_has_liked_authenticated(
        self,
        authenticated_api_client,
        post,
        like_factory,
        user,
        other_user,
        post_factory,
    ):
        """Authenticated user sees has_liked correctly."""
        # User has liked this post
        like_factory(post=post, user=user)
        # Create another post that user hasn't liked
        other_post = post_factory(author=other_user)

        response = authenticated_api_client.get(reverse("post-list-create-api"))

        assert response.status_code == status.HTTP_200_OK
        liked_post = next(p for p in response.data["results"] if p["id"] == post.id)
        unliked_post = next(
            p for p in response.data["results"] if p["id"] == other_post.id
        )
        assert liked_post["stats"]["has_liked"] is True
        assert unliked_post["stats"]["has_liked"] is False

    def test_list_content_excerpt(self, api_client, post_factory, user):
        """Content is truncated to 200 chars with ellipsis."""
        long_content = "A" * 300
        post = post_factory(author=user, content=long_content)

        response = api_client.get(reverse("post-list-create-api"))

        assert response.status_code == status.HTTP_200_OK
        post_data = next(p for p in response.data["results"] if p["id"] == post.id)
        assert "content_excerpt" in post_data
        assert len(post_data["content_excerpt"]) == 203  # 200 + "..."
        assert post_data["content_excerpt"].endswith("...")

    def test_list_author_username(self, api_client, post):
        """Author includes username and URL."""
        response = api_client.get(reverse("post-list-create-api"))

        assert response.status_code == status.HTTP_200_OK
        post_data = next(p for p in response.data["results"] if p["id"] == post.id)
        assert "author" in post_data
        assert "username" in post_data["author"]
        assert "url" in post_data["author"]
        assert "id" in post_data["author"]

    def test_list_search_by_title(self, api_client, post_factory, user):
        """Can search posts by title."""
        post1 = post_factory(author=user, title="Unique Searchable Title")
        post_factory(author=user, title="Other Post")

        response = api_client.get(
            reverse("post-list-create-api"), {"search": "Unique Searchable"}
        )

        assert response.status_code == status.HTTP_200_OK
        post_ids = [p["id"] for p in response.data["results"]]
        assert post1.id in post_ids
        assert len(post_ids) == 1

    def test_list_search_by_content(self, api_client, post_factory, user):
        """Can search posts by content."""
        post1 = post_factory(author=user, content="special keyword here")
        post_factory(author=user, content="normal content")

        response = api_client.get(
            reverse("post-list-create-api"), {"search": "special keyword"}
        )

        assert response.status_code == status.HTTP_200_OK
        post_ids = [p["id"] for p in response.data["results"]]
        assert post1.id in post_ids

    def test_list_filter_by_author_username(self, api_client, post, other_user_post):
        """Can filter posts by author username."""
        response = api_client.get(
            reverse("post-list-create-api"),
            {"author__username": post.author.username},
        )

        assert response.status_code == status.HTTP_200_OK
        post_ids = [p["id"] for p in response.data["results"]]
        assert post.id in post_ids
        assert other_user_post.id not in post_ids

    def test_list_has_likes_hyperlink(self, api_client, post):
        """Post list includes likes hyperlink for each post."""
        response = api_client.get(reverse("post-list-create-api"))

        assert response.status_code == status.HTTP_200_OK
        post_data = next(p for p in response.data["results"] if p["id"] == post.id)
        assert "likes" in post_data
        assert f"?post={post.id}" in post_data["likes"]


class TestPostCreate:
    """Tests for post creation endpoint (POST /api/v1/posts/)."""

    def test_create_requires_auth(self, api_client):
        """Anonymous gets 401."""
        response = api_client.post(
            reverse("post-list-create-api"),
            {"title": "Test", "content": "Test content"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_success(self, authenticated_api_client, user):
        """Authenticated user can create post."""
        response = authenticated_api_client.post(
            reverse("post-list-create-api"),
            {"title": "New Post", "content": "New content here"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert Post.objects.filter(title="New Post").exists()

    def test_create_sets_author(self, authenticated_api_client, user):
        """Author is set to current user."""
        response = authenticated_api_client.post(
            reverse("post-list-create-api"),
            {"title": "New Post", "content": "New content here"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        post = Post.objects.get(title="New Post")
        assert post.author == user

    def test_create_cannot_override_author(
        self, authenticated_api_client, user, other_user
    ):
        """Attempting to set author is ignored."""
        response = authenticated_api_client.post(
            reverse("post-list-create-api"),
            {
                "title": "New Post",
                "content": "New content here",
                "author": other_user.id,
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        post = Post.objects.get(title="New Post")
        # Author should be the authenticated user, not other_user
        assert post.author == user

    def test_create_published_by_default(self, authenticated_api_client):
        """Posts are published by default."""
        response = authenticated_api_client.post(
            reverse("post-list-create-api"),
            {"title": "New Post", "content": "New content here"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        post = Post.objects.get(title="New Post")
        assert post.published is True

    def test_create_unpublished(self, authenticated_api_client):
        """Can create unpublished (draft) post."""
        response = authenticated_api_client.post(
            reverse("post-list-create-api"),
            {"title": "Draft Post", "content": "Draft content", "published": False},
        )

        assert response.status_code == status.HTTP_201_CREATED
        post = Post.objects.get(title="Draft Post")
        assert post.published is False

    def test_create_missing_title(self, authenticated_api_client):
        """Missing title returns 400."""
        response = authenticated_api_client.post(
            reverse("post-list-create-api"),
            {"content": "Content without title"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "title" in response.data

    def test_create_missing_content(self, authenticated_api_client):
        """Missing content returns 400."""
        response = authenticated_api_client.post(
            reverse("post-list-create-api"),
            {"title": "Title without content"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "content" in response.data

    def test_create_profanity_rejected(self, authenticated_api_client):
        """Title with profanity returns 400."""
        response = authenticated_api_client.post(
            reverse("post-list-create-api"),
            {"title": "fuck this", "content": "Some content"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "title" in response.data

    def test_create_profanity_in_content_rejected(self, authenticated_api_client):
        """Content with profanity returns 400."""
        response = authenticated_api_client.post(
            reverse("post-list-create-api"),
            {"title": "Valid Title", "content": "This is bullshit content"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "content" in response.data

    def test_create_response_no_stats(self, authenticated_api_client):
        """Post create response does not include stats (no has_liked)."""
        response = authenticated_api_client.post(
            reverse("post-list-create-api"),
            {"title": "New Post", "content": "New content here"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        # Create response should not have stats field
        assert "stats" not in response.data

    def test_create_response_has_likes_hyperlink(self, authenticated_api_client):
        """Post create response includes likes hyperlink."""
        response = authenticated_api_client.post(
            reverse("post-list-create-api"),
            {"title": "New Post", "content": "New content here"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert "likes" in response.data
        post_id = response.data["id"]
        assert f"?post={post_id}" in response.data["likes"]


class TestPostDetail:
    """Tests for post detail endpoint (GET /api/v1/posts/{id}/)."""

    def test_view_published_post(self, api_client, post):
        """Anyone can view a published post."""
        response = api_client.get(reverse("post-detail-api", args=[post.id]))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == post.id
        assert response.data["title"] == post.title

    def test_view_unpublished_owner_only(self, api_client, unpublished_post):
        """Non-owner gets 403 for unpublished post."""
        response = api_client.get(
            reverse("post-detail-api", args=[unpublished_post.id])
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_view_unpublished_by_owner(
        self, authenticated_api_client, unpublished_post
    ):
        """Owner can view their unpublished post."""
        response = authenticated_api_client.get(
            reverse("post-detail-api", args=[unpublished_post.id])
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == unpublished_post.id

    def test_view_unpublished_by_admin(self, admin_api_client, unpublished_post):
        """Admin can view any unpublished post."""
        response = admin_api_client.get(
            reverse("post-detail-api", args=[unpublished_post.id])
        )

        assert response.status_code == status.HTTP_200_OK

    def test_view_includes_likes_count(self, api_client, post, like):
        """Post detail includes likes_count in stats."""
        response = api_client.get(reverse("post-detail-api", args=[post.id]))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["stats"]["likes_count"] == 1

    def test_view_has_liked_authenticated(
        self, authenticated_api_client, post, like_factory, user
    ):
        """Authenticated user sees has_liked correctly."""
        # User has liked this post
        like_factory(post=post, user=user)

        response = authenticated_api_client.get(
            reverse("post-detail-api", args=[post.id])
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["stats"]["has_liked"] is True

    def test_view_has_liked_not_liked(self, authenticated_api_client, post):
        """Authenticated user sees has_liked=False when not liked."""
        response = authenticated_api_client.get(
            reverse("post-detail-api", args=[post.id])
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["stats"]["has_liked"] is False

    def test_view_has_liked_not_shown_anonymous(self, api_client, post):
        """Anonymous user does not see has_liked field."""
        response = api_client.get(reverse("post-detail-api", args=[post.id]))

        assert response.status_code == status.HTTP_200_OK
        assert "has_liked" not in response.data["stats"]

    def test_view_published_hidden_for_others(self, other_user_api_client, post):
        """Non-owner does not see published field."""
        response = other_user_api_client.get(reverse("post-detail-api", args=[post.id]))

        assert response.status_code == status.HTTP_200_OK
        assert "published" not in response.data

    def test_view_published_hidden_for_anonymous(self, api_client, post):
        """Anonymous user does not see published field."""
        response = api_client.get(reverse("post-detail-api", args=[post.id]))

        assert response.status_code == status.HTTP_200_OK
        assert "published" not in response.data

    def test_view_published_visible_for_owner(self, authenticated_api_client, post):
        """Owner sees published field."""
        response = authenticated_api_client.get(
            reverse("post-detail-api", args=[post.id])
        )

        assert response.status_code == status.HTTP_200_OK
        assert "published" in response.data
        assert response.data["published"] is True

    def test_view_published_visible_for_admin(self, admin_api_client, post):
        """Admin sees published field."""
        response = admin_api_client.get(reverse("post-detail-api", args=[post.id]))

        assert response.status_code == status.HTTP_200_OK
        assert "published" in response.data

    def test_view_has_url_field(self, api_client, post):
        """Post detail has url as the first field."""
        response = api_client.get(reverse("post-detail-api", args=[post.id]))

        assert response.status_code == status.HTTP_200_OK
        assert "url" in response.data
        # Should NOT have links section
        assert "links" not in response.data

    def test_view_has_likes_hyperlink(self, api_client, post):
        """Post detail has likes hyperlink field."""
        response = api_client.get(reverse("post-detail-api", args=[post.id]))

        assert response.status_code == status.HTTP_200_OK
        assert "likes" in response.data
        assert f"?post={post.id}" in response.data["likes"]

    def test_view_nonexistent_post(self, api_client):
        """Non-existent post returns 404."""
        response = api_client.get(reverse("post-detail-api", args=[99999]))

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestPostUpdate:
    """Tests for post update endpoint (PUT/PATCH /api/v1/posts/{id}/)."""

    def test_update_owner_only(self, other_user_api_client, post):
        """Non-owner gets 403."""
        response = other_user_api_client.put(
            reverse("post-detail-api", args=[post.id]),
            {"title": "Updated", "content": "Updated content"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_unauthorized(self, api_client, post):
        """Anonymous gets 401."""
        response = api_client.put(
            reverse("post-detail-api", args=[post.id]),
            {"title": "Updated", "content": "Updated content"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_by_owner_put(self, authenticated_api_client, post):
        """Owner can update their post via PUT."""
        response = authenticated_api_client.put(
            reverse("post-detail-api", args=[post.id]),
            {"title": "Updated Title", "content": "Updated content"},
        )

        assert response.status_code == status.HTTP_200_OK
        post.refresh_from_db()
        assert post.title == "Updated Title"
        assert post.content == "Updated content"

    def test_update_by_owner_patch(self, authenticated_api_client, post):
        """Owner can partially update their post via PATCH."""
        original_content = post.content
        response = authenticated_api_client.patch(
            reverse("post-detail-api", args=[post.id]),
            {"title": "Patched Title"},
        )

        assert response.status_code == status.HTTP_200_OK
        post.refresh_from_db()
        assert post.title == "Patched Title"
        assert post.content == original_content

    def test_update_by_admin(self, admin_api_client, post):
        """Admin can update any post."""
        response = admin_api_client.patch(
            reverse("post-detail-api", args=[post.id]),
            {"title": "Admin Updated"},
        )

        assert response.status_code == status.HTTP_200_OK
        post.refresh_from_db()
        assert post.title == "Admin Updated"

    def test_update_profanity_rejected(self, authenticated_api_client, post):
        """Update with profanity returns 400."""
        response = authenticated_api_client.patch(
            reverse("post-detail-api", args=[post.id]),
            {"title": "fuck this"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestPostDelete:
    """Tests for post deletion endpoint (DELETE /api/v1/posts/{id}/)."""

    def test_delete_owner_can_delete(self, authenticated_api_client, post):
        """Owner can delete their post."""
        post_id = post.id
        response = authenticated_api_client.delete(
            reverse("post-detail-api", args=[post_id])
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Post.objects.filter(id=post_id).exists()

    def test_delete_admin_can_delete(self, admin_api_client, post):
        """Admin can delete any post."""
        post_id = post.id
        response = admin_api_client.delete(reverse("post-detail-api", args=[post_id]))

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Post.objects.filter(id=post_id).exists()

    def test_delete_non_owner_forbidden(self, other_user_api_client, post):
        """Non-owner gets 403."""
        response = other_user_api_client.delete(
            reverse("post-detail-api", args=[post.id])
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Post.objects.filter(id=post.id).exists()

    def test_delete_unauthorized(self, api_client, post):
        """Anonymous gets 401."""
        response = api_client.delete(reverse("post-detail-api", args=[post.id]))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert Post.objects.filter(id=post.id).exists()

    def test_delete_cascades_likes(self, authenticated_api_client, post, like):
        """Deleting post cascades to its likes."""
        from apps.diary.models import Like

        post_id = post.id
        like_id = like.id

        response = authenticated_api_client.delete(
            reverse("post-detail-api", args=[post_id])
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Post.objects.filter(id=post_id).exists()
        assert not Like.objects.filter(id=like_id).exists()
