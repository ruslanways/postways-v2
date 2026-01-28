"""
Tests for HTML home views.

Tests cover:
- Home page rendering
- Published posts filtering
- Pagination
- Like-ordered view
- has_liked annotation
"""

from django.urls import reverse

import pytest

pytestmark = pytest.mark.django_db


class TestHomeView:
    """Tests for the main home page view."""

    def test_home_renders_template(self, client):
        """GET / returns 200 with diary/index.html."""
        response = client.get(reverse("home"))

        assert response.status_code == 200
        template_names = [t.name for t in response.templates]
        assert "diary/index.html" in template_names

    @pytest.mark.parametrize(
        "client_fixture_name", ["client", "user_client", "admin_client"]
    )
    def test_home_shows_published_only(
        self, request, client_fixture_name, post, unpublished_post
    ):
        """Unpublished posts not in context for any user, including admins."""
        client = request.getfixturevalue(client_fixture_name)
        response = client.get(reverse("home"))

        # Check the full queryset (all pages), not just the current paginated page
        # This ensures we test filtering regardless of which page the post appears on
        all_posts = list(response.context["paginator"].object_list)
        assert post in all_posts
        assert unpublished_post not in all_posts

    def test_home_pagination(self, client, post_factory, user):
        """Page 2 works with ?page=2."""
        # Create more than one page of posts (paginate_by=6)
        for _ in range(10):
            post_factory(author=user)

        # First page
        response = client.get(reverse("home"))
        assert response.status_code == 200
        assert len(response.context["object_list"]) == 6
        assert response.context["is_paginated"] is True

        # Second page
        response = client.get(reverse("home"), {"page": 2})
        assert response.status_code == 200
        assert len(response.context["object_list"]) == 4  # remaining posts

    def test_home_authenticated_has_liked_true(self, client, user, post, like):
        """Authenticated user sees has_liked=True for posts they liked."""
        client.force_login(user)

        response = client.get(reverse("home"))

        assert response.status_code == 200
        post_in_context = next(
            p for p in response.context["object_list"] if p.id == post.id
        )
        assert hasattr(post_in_context, "has_liked")
        assert post_in_context.has_liked is True

    def test_home_authenticated_has_liked_false(
        self, client, user, post_factory, other_user
    ):
        """Authenticated user sees has_liked=False for posts they haven't liked."""
        unliked_post = post_factory(author=other_user)
        client.force_login(user)

        response = client.get(reverse("home"))

        assert response.status_code == 200
        post_in_context = next(
            p for p in response.context["object_list"] if p.id == unliked_post.id
        )
        assert post_in_context.has_liked is False

    def test_home_anonymous_has_liked_false(self, client, post):
        """Anonymous user sees has_liked=False for all posts."""
        response = client.get(reverse("home"))

        assert response.status_code == 200
        post_in_context = next(
            p for p in response.context["object_list"] if p.id == post.id
        )
        assert post_in_context.has_liked is False

    def test_home_posts_include_like_count(self, client, post, like_factory, user):
        """Posts have like_count annotation."""
        # Create likes
        like_factory(post=post, user=user)

        response = client.get(reverse("home"))

        assert response.status_code == 200
        post_in_context = next(
            p for p in response.context["object_list"] if p.id == post.id
        )
        assert hasattr(post_in_context, "like_count")
        assert post_in_context.like_count == 1


class TestHomeViewPopular:
    """Tests for the popular home page view."""

    def test_popular_renders_template(self, client):
        """GET /popular/ returns 200."""
        response = client.get(reverse("home-popular"))

        assert response.status_code == 200
        template_names = [t.name for t in response.templates]
        assert "diary/index.html" in template_names

    def test_popular_sorts_by_likes(self, client, post_factory, like_factory, user):
        """Posts are ordered by like count descending."""
        # Create posts with different like counts
        post_many_likes = post_factory(author=user)
        post_few_likes = post_factory(author=user)
        post_no_likes = post_factory(author=user)

        # Add likes
        for _ in range(5):
            like_factory(post=post_many_likes)
        for _ in range(2):
            like_factory(post=post_few_likes)

        response = client.get(reverse("home-popular"))

        assert response.status_code == 200
        posts = list(response.context["object_list"])

        # Find positions of our posts
        many_idx = next(i for i, p in enumerate(posts) if p.id == post_many_likes.id)
        few_idx = next(i for i, p in enumerate(posts) if p.id == post_few_likes.id)
        no_idx = next(i for i, p in enumerate(posts) if p.id == post_no_likes.id)

        # Most likes should come first
        assert many_idx < few_idx
        assert few_idx < no_idx

    @pytest.mark.parametrize(
        "client_fixture_name", ["client", "user_client", "admin_client"]
    )
    def test_popular_shows_published_only(
        self, request, client_fixture_name, post, unpublished_post
    ):
        """Popular view also filters unpublished posts."""
        client = request.getfixturevalue(client_fixture_name)
        response = client.get(reverse("home-popular"))

        assert response.status_code == 200
        posts_in_context = list(response.context["object_list"])
        assert post in posts_in_context
        assert unpublished_post not in posts_in_context
