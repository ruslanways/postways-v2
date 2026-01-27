"""
Tests for HTML home views.

Tests cover:
- Home page rendering
- Published posts filtering
- Pagination
- Like-ordered view
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

    def test_home_shows_published_only(self, client, admin_client, post, unpublished_post):
        """Unpublished posts not in context for any user, including admins."""
        response = client.get(reverse("home"))

        # Check the full queryset (all pages), not just the current paginated page
        # This ensures we test filtering regardless of which page the post appears on
        all_posts = list(response.context["paginator"].object_list)
        assert post in all_posts
        assert unpublished_post not in all_posts
        
        # Admins also only see published posts on home page
        admin_response = admin_client.get(reverse("home"))
        admin_all_posts = list(admin_response.context["paginator"].object_list)
        assert post in admin_all_posts
        assert unpublished_post not in admin_all_posts
        

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

    def test_home_includes_ordering_context(self, client, post):
        """Context includes ordering indicator."""
        response = client.get(reverse("home"))

        assert response.status_code == 200
        assert response.context["ordering"] == "new"

    def test_home_authenticated_shows_liked_posts(self, client, user, post, like):
        """Authenticated user context includes liked_by_user set."""
        client.force_login(user)

        response = client.get(reverse("home"))

        assert response.status_code == 200
        assert "liked_by_user" in response.context
        assert post.id in response.context["liked_by_user"]

    def test_home_authenticated_unliked_post(
        self, client, user, post_factory, other_user
    ):
        """Post not in liked_by_user if user hasn't liked it."""
        unliked_post = post_factory(author=other_user)
        client.force_login(user)

        response = client.get(reverse("home"))

        assert response.status_code == 200
        assert unliked_post.id not in response.context.get("liked_by_user", set())

    def test_home_anonymous_liked_by_user_empty(self, client, post):
        """Anonymous user gets empty liked_by_user in template context."""
        response = client.get(reverse("home"))

        assert response.status_code == 200
        # For anonymous users, liked_by_user is empty (not a set of liked post IDs)
        # The template may still include it for convenience
        liked = response.context.get("liked_by_user", set())
        assert liked == "" or liked == set()

    def test_home_posts_include_like_count(self, client, post, like_factory, user):
        """Posts have like__count annotation."""
        # Create likes
        like_factory(post=post, user=user)

        response = client.get(reverse("home"))

        assert response.status_code == 200
        post_in_context = next(
            p for p in response.context["object_list"] if p.id == post.id
        )
        assert hasattr(post_in_context, "like__count")
        assert post_in_context.like__count == 1


class TestHomeViewPopular:
    """Tests for the popular home page view."""

    def test_popular_renders_template(self, client):
        """GET /popular/ returns 200."""
        response = client.get(reverse("home-popular"))

        assert response.status_code == 200
        template_names = [t.name for t in response.templates]
        assert "diary/index.html" in template_names

    def test_popular_context_indicator(self, client, post):
        """Context ordering is 'popular'."""
        response = client.get(reverse("home-popular"))

        assert response.status_code == 200
        assert response.context["ordering"] == "popular"

    def test_popular_sorts_by_likes(
        self, client, post_factory, like_factory, user
    ):
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

    def test_popular_shows_published_only(self, client, post, unpublished_post):
        """Popular view also filters unpublished posts."""
        response = client.get(reverse("home-popular"))

        assert response.status_code == 200
        posts_in_context = list(response.context["object_list"])
        assert post in posts_in_context
        assert unpublished_post not in posts_in_context


class TestHomeViewSwitching:
    """Tests for switching between new and popular ordering."""

    def test_switch_between_orderings(self, client, post):
        """Can switch between new and popular ordering."""
        # Start with new
        response = client.get(reverse("home"))
        assert response.context["ordering"] == "new"

        # Switch to popular
        response = client.get(reverse("home-popular"))
        assert response.context["ordering"] == "popular"

        # Back to new
        response = client.get(reverse("home"))
        assert response.context["ordering"] == "new"
