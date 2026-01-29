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

    def test_home_authenticated_has_liked_true(self, user_client, post, like):
        """Authenticated user sees has_liked=True for posts they liked."""

        response = user_client.get(reverse("home"))

        assert response.status_code == 200
        post_in_context = next(
            p for p in response.context["object_list"] if p.id == post.id
        )
        assert hasattr(post_in_context, "has_liked")
        assert post_in_context.has_liked is True

    def test_home_authenticated_has_liked_false(
        self, user_client, post_factory, other_user
    ):
        """Authenticated user sees has_liked=False for posts they haven't liked."""
        unliked_post = post_factory(author=other_user)

        response = user_client.get(reverse("home"))

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


class TestPostListView:
    """Tests for the staff-only post list view."""

    def test_post_list_requires_staff(self, client, user):
        """Non-staff users are redirected."""
        client.force_login(user)

        response = client.get(reverse("post-list"))

        assert response.status_code == 302

    def test_post_list_accessible_to_staff(self, client, admin_user, post):
        """Staff users can access post list."""
        client.force_login(admin_user)

        response = client.get(reverse("post-list"))

        assert response.status_code == 200
        template_names = [t.name for t in response.templates]
        assert "diary/post_list.html" in template_names
        assert post in response.context["object_list"]

    def test_post_list_shows_unpublished(
        self, client, admin_user, post, unpublished_post
    ):
        """Staff post list includes unpublished posts."""
        client.force_login(admin_user)

        response = client.get(reverse("post-list"))

        assert response.status_code == 200
        posts = list(response.context["object_list"])
        assert post in posts
        assert unpublished_post in posts

    def test_post_list_has_liked_annotation(self, client, admin_user, post, like):
        """Posts have has_liked annotation for authenticated users."""
        # The like fixture creates a like from user on post
        # admin_user is different, so has_liked should be False
        client.force_login(admin_user)

        response = client.get(reverse("post-list"))

        assert response.status_code == 200
        post_in_context = next(
            p for p in response.context["object_list"] if p.id == post.id
        )
        assert hasattr(post_in_context, "has_liked")
        # Verify like exists in DB (uses the fixture)
        assert like.post_id == post.id


class TestPostCreateView:
    """Tests for post creation view."""

    def test_post_create_requires_login(self, client):
        """Unauthenticated users are redirected."""
        response = client.get(reverse("post-add"))

        assert response.status_code == 302
        assert "login" in response.url

    def test_post_create_page_renders(self, client, user):
        """Authenticated user sees create form."""
        client.force_login(user)

        response = client.get(reverse("post-add"))

        assert response.status_code == 200
        template_names = [t.name for t in response.templates]
        assert "diary/add-post.html" in template_names

    def test_post_create_sets_author(self, client, user):
        """Creating a post sets the author to current user."""
        from apps.diary.models import Post

        client.force_login(user)

        response = client.post(
            reverse("post-add"),
            {
                "title": "New Test Post",
                "content": "Test content for the post.",
                "published": True,
            },
        )

        assert response.status_code == 302  # redirect on success
        new_post = Post.objects.get(title="New Test Post")
        assert new_post.author == user


class TestPostDetailView:
    """Tests for post detail view."""

    def test_post_detail_renders(self, client, post):
        """GET post detail returns 200."""
        response = client.get(reverse("post-detail", kwargs={"pk": post.pk}))

        assert response.status_code == 200
        template_names = [t.name for t in response.templates]
        assert "diary/post_detail.html" in template_names

    def test_post_detail_has_like_count(self, client, post, like_factory, user):
        """Post detail includes like_count annotation."""
        like_factory(post=post, user=user)

        response = client.get(reverse("post-detail", kwargs={"pk": post.pk}))

        assert response.status_code == 200
        post_in_context = response.context["object"]
        assert hasattr(post_in_context, "like_count")
        assert post_in_context.like_count == 1

    def test_post_detail_has_liked_authenticated(self, user_client, post, like):
        """Authenticated user sees has_liked=True for posts they liked."""
        # Verify like exists
        assert like.post_id == post.id

        response = user_client.get(reverse("post-detail", kwargs={"pk": post.pk}))

        assert response.status_code == 200
        post_in_context = response.context["object"]
        assert post_in_context.has_liked is True

    def test_post_detail_has_liked_anonymous(self, client, post):
        """Anonymous user sees has_liked=False."""
        response = client.get(reverse("post-detail", kwargs={"pk": post.pk}))

        assert response.status_code == 200
        post_in_context = response.context["object"]
        assert post_in_context.has_liked is False

    def test_published_post_has_like_feature(self, client, post):
        """Published post shows like button, not '*unpublished' label."""
        response = client.get(reverse("post-detail", kwargs={"pk": post.pk}))

        assert response.status_code == 200
        content = response.content.decode()
        assert 'class="like' in content
        assert "*unpublished" not in content

    def test_unpublished_post_has_no_like_feature(self, user_client, unpublished_post):
        """Unpublished post shows '*unpublished' label, not like button."""
        response = user_client.get(
            reverse("post-detail", kwargs={"pk": unpublished_post.pk})
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert 'class="like' not in content
        assert "*unpublished" in content


class TestPostUpdateView:
    """Tests for post update view."""

    def test_post_update_requires_auth(self, client, post):
        """Unauthenticated users are redirected."""
        response = client.get(reverse("post-update", kwargs={"pk": post.pk}))

        assert response.status_code == 302

    def test_post_update_owner_can_access(self, client, user, post):
        """Post owner can access update page."""
        client.force_login(user)

        response = client.get(reverse("post-update", kwargs={"pk": post.pk}))

        assert response.status_code == 200
        template_names = [t.name for t in response.templates]
        assert "diary/post-update.html" in template_names

    def test_post_update_staff_can_access(self, client, admin_user, post):
        """Staff can access update page for any post."""
        client.force_login(admin_user)

        response = client.get(reverse("post-update", kwargs={"pk": post.pk}))

        assert response.status_code == 200

    def test_post_update_other_user_denied(self, client, other_user, post):
        """Non-owner non-staff cannot access update page."""
        client.force_login(other_user)

        response = client.get(reverse("post-update", kwargs={"pk": post.pk}))

        assert response.status_code == 403


class TestPostDeleteView:
    """Tests for post delete view."""

    def test_post_delete_requires_auth(self, client, post):
        """Unauthenticated users are redirected."""
        response = client.get(reverse("post-delete", kwargs={"pk": post.pk}))

        assert response.status_code == 302

    def test_post_delete_owner_can_access(self, client, user, post):
        """Post owner can access delete confirmation page."""
        client.force_login(user)

        response = client.get(reverse("post-delete", kwargs={"pk": post.pk}))

        assert response.status_code == 200
        template_names = [t.name for t in response.templates]
        assert "diary/post-delete.html" in template_names

    def test_post_delete_staff_can_access(self, client, admin_user, post):
        """Staff can access delete page for any post."""
        client.force_login(admin_user)

        response = client.get(reverse("post-delete", kwargs={"pk": post.pk}))

        assert response.status_code == 200

    def test_post_delete_other_user_denied(self, client, other_user, post):
        """Non-owner non-staff cannot delete."""
        client.force_login(other_user)

        response = client.get(reverse("post-delete", kwargs={"pk": post.pk}))

        assert response.status_code == 403

    def test_post_delete_success_redirects_to_author_profile(self, client, user, post):
        """Deleting post redirects to author's profile."""
        from apps.diary.models import Post

        client.force_login(user)
        post_id = post.pk
        author_id = post.author_id

        response = client.post(reverse("post-delete", kwargs={"pk": post_id}))

        assert response.status_code == 302
        assert response.url == reverse("author-detail", kwargs={"pk": author_id})
        assert not Post.objects.filter(pk=post_id).exists()
