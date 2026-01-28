"""
Tests for model constraints and relationships.

Tests cover:
- Unique constraints (email, like)
- Cascade delete behavior
- Model field validation
"""

from django.db import IntegrityError

import pytest

from apps.diary.models import CustomUser, Like, Post

pytestmark = pytest.mark.django_db


class TestCustomUserModel:
    """Tests for CustomUser model constraints."""

    def test_email_unique_constraint(self, django_user_model):
        """Duplicate email raises IntegrityError."""
        django_user_model.objects.create_user(
            username="user1", email="test@example.com", password="pass123"
        )

        with pytest.raises(IntegrityError):
            django_user_model.objects.create_user(
                username="user2", email="test@example.com", password="pass123"
            )

    def test_username_unique_constraint(self, django_user_model):
        """Duplicate username raises IntegrityError."""
        django_user_model.objects.create_user(
            username="testuser", email="email1@example.com", password="pass123"
        )

        with pytest.raises(IntegrityError):
            django_user_model.objects.create_user(
                username="testuser", email="email2@example.com", password="pass123"
            )

    def test_user_str_representation(self, user):
        """User string representation is username."""
        assert str(user) == user.username

    def test_user_default_staff_status(self, user):
        """Regular users are not staff by default."""
        assert user.is_staff is False
        assert user.is_active is True

    def test_admin_user_is_staff(self, admin_user):
        """Admin users have is_staff=True."""
        assert admin_user.is_staff is True


class TestPostModel:
    """Tests for Post model constraints and behavior."""

    def test_post_str_representation(self, post):
        """Post string representation includes author and title."""
        assert post.author.username in str(post)
        assert post.title in str(post)

    def test_post_default_published(self, user):
        """Posts are published by default."""
        post = Post.objects.create(
            title="Test", content="Content", author=user
        )
        assert post.published is True

    def test_post_absolute_url(self, post):
        """Post.get_absolute_url returns correct URL."""
        from django.urls import reverse

        expected = reverse("post-detail", kwargs={"pk": post.id})
        assert post.get_absolute_url() == expected

    def test_post_cascade_delete_on_user(self, user, post):
        """Deleting user deletes their posts."""
        post_id = post.id
        user_id = user.id

        user.delete()

        assert not Post.objects.filter(id=post_id).exists()
        assert not CustomUser.objects.filter(id=user_id).exists()

    def test_post_ordering(self, user):
        """Posts are ordered by -updated by default."""
        import time

        post1 = Post.objects.create(title="First", content="Content", author=user)
        time.sleep(0.01)  # ensure different timestamps
        post2 = Post.objects.create(title="Second", content="Content", author=user)

        posts = list(Post.objects.all())
        # Most recently updated first
        assert posts[0] == post2
        assert posts[1] == post1


class TestLikeModel:
    """Tests for Like model constraints."""

    def test_like_unique_constraint(self, user, post):
        """Duplicate like (same user/post) raises IntegrityError."""
        Like.objects.create(user=user, post=post)

        with pytest.raises(IntegrityError):
            Like.objects.create(user=user, post=post)

    def test_like_str_representation(self, like):
        """Like string representation includes user and post title."""
        assert like.user.username in str(like)
        assert like.post.title in str(like)

    def test_like_cascade_delete_on_post(self, like):
        """Deleting post deletes its likes."""
        post = like.post
        like_id = like.id

        post.delete()

        assert not Like.objects.filter(id=like_id).exists()

    def test_like_cascade_delete_on_user(self, like):
        """Deleting user deletes their likes."""
        user = like.user
        like_id = like.id

        user.delete()

        assert not Like.objects.filter(id=like_id).exists()

    def test_like_ordering(self, user, post_factory, like_factory):
        """Likes are ordered by -created by default."""
        import time

        post = post_factory()
        other_user = CustomUser.objects.create_user(
            username="otheruser", email="other@test.com", password="pass123"
        )

        like1 = Like.objects.create(user=user, post=post)
        time.sleep(0.01)
        like2 = Like.objects.create(user=other_user, post=post)

        likes = list(Like.objects.filter(post=post))
        # Most recently created first
        assert likes[0] == like2
        assert likes[1] == like1

    def test_multiple_users_can_like_same_post(self, post, user_factory):
        """Multiple users can like the same post."""
        users = [user_factory() for _ in range(5)]

        for u in users:
            Like.objects.create(user=u, post=post)

        assert Like.objects.filter(post=post).count() == 5

    def test_user_can_like_multiple_posts(self, user, post_factory):
        """A user can like multiple posts."""
        posts = [post_factory() for _ in range(5)]

        for p in posts:
            Like.objects.create(user=user, post=p)

        assert Like.objects.filter(user=user).count() == 5


class TestModelRelationships:
    """Tests for model relationships and related managers."""

    def test_user_posts(self, user, post_factory):
        """User.posts contains all user's posts."""
        posts = [post_factory(author=user) for _ in range(3)]

        user_posts = list(user.posts.all())
        for p in posts:
            assert p in user_posts

    def test_user_likes(self, user, post_factory, like_factory):
        """User.likes contains all user's likes."""
        posts = [post_factory() for _ in range(3)]
        likes = [like_factory(user=user, post=p) for p in posts]

        user_likes = list(user.likes.all())
        for like in likes:
            assert like in user_likes

    def test_post_likes(self, post, user_factory, like_factory):
        """Post.likes contains all likes on the post."""
        users = [user_factory() for _ in range(3)]
        likes = [like_factory(user=u, post=post) for u in users]

        post_likes = list(post.likes.all())
        for like in likes:
            assert like in post_likes

    def test_post_author_relationship(self, post):
        """Post.author returns the correct user."""
        assert post.author is not None
        assert post in post.author.posts.all()


class TestEmailVerificationFields:
    """Tests for email verification model fields."""

    def test_pending_email_defaults_blank(self, user):
        """pending_email is blank by default."""
        assert user.pending_email == ""

    def test_email_verification_token_defaults_blank(self, user):
        """email_verification_token is blank by default."""
        assert user.email_verification_token == ""

    def test_email_verification_expires_defaults_null(self, user):
        """email_verification_expires is null by default."""
        assert user.email_verification_expires is None

    def test_can_set_email_verification_fields(self, user):
        """Email verification fields can be set."""
        import uuid
        from datetime import timedelta

        from django.utils import timezone

        user.pending_email = "new@example.com"
        user.email_verification_token = str(uuid.uuid4())
        user.email_verification_expires = timezone.now() + timedelta(hours=24)
        user.save()

        user.refresh_from_db()
        assert user.pending_email == "new@example.com"
        assert user.email_verification_token
        assert user.email_verification_expires is not None


class TestUsernameChangeFields:
    """Tests for username change tracking fields."""

    def test_username_changed_at_defaults_null(self, user):
        """username_changed_at is null by default."""
        assert user.username_changed_at is None

    def test_can_set_username_changed_at(self, user):
        """username_changed_at can be set."""
        from django.utils import timezone

        now = timezone.now()
        user.username_changed_at = now
        user.save()

        user.refresh_from_db()
        assert user.username_changed_at is not None
