"""
Pytest fixtures and factories for diary application tests.

This module provides:
- Factory classes for User, Post, and Like models using pytest-factoryboy
- Custom fixtures for API testing with DRF's APIClient
- JWT authentication fixtures for authenticated API requests
"""

import factory
import pytest
from factory.django import DjangoModelFactory
from pytest_factoryboy import register
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.diary.models import CustomUser, Like, Post

# =============================================================================
# Factories
# =============================================================================


class UserFactory(DjangoModelFactory):
    """Factory for creating regular users with unique usernames and emails."""

    class Meta:
        model = CustomUser
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"testuser{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override create to properly use create_user method."""
        password = kwargs.pop("password", "testpass123")
        instance = super()._create(model_class, *args, **kwargs)
        instance.set_password(password)
        instance.save()
        return instance


class AdminUserFactory(UserFactory):
    """Factory for creating admin/staff users."""

    class Meta:
        model = CustomUser
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"admin{n}")
    is_staff = True


class PostFactory(DjangoModelFactory):
    """Factory for creating published posts."""

    class Meta:
        model = Post
        skip_postgeneration_save = True

    title = factory.Sequence(lambda n: f"Test Post {n}")
    content = factory.Faker("paragraph")
    author = factory.SubFactory(UserFactory)
    published = True


class UnpublishedPostFactory(PostFactory):
    """Factory for creating unpublished (draft) posts."""

    class Meta:
        model = Post
        skip_postgeneration_save = True

    title = factory.Sequence(lambda n: f"Draft Post {n}")
    published = False


class LikeFactory(DjangoModelFactory):
    """Factory for creating likes on posts."""

    class Meta:
        model = Like
        skip_postgeneration_save = True

    user = factory.SubFactory(UserFactory)
    post = factory.SubFactory(PostFactory)


# =============================================================================
# Register factories with pytest-factoryboy
# =============================================================================

register(UserFactory)
register(AdminUserFactory, _name="admin_factory")
register(PostFactory)
register(UnpublishedPostFactory)
register(LikeFactory)


# =============================================================================
# Custom Fixtures
# =============================================================================


@pytest.fixture
def api_client():
    """Return an unauthenticated DRF APIClient."""
    return APIClient()


@pytest.fixture
def user_password():
    """Return the default password used in UserFactory."""
    return "testpass123"


@pytest.fixture
def user(user_password):
    """Create and return a regular user."""
    return UserFactory(password=user_password)


@pytest.fixture
def admin_user(user_password):
    """Create and return an admin user."""
    return AdminUserFactory(password=user_password)


@pytest.fixture
def other_user(user_password):
    """Create and return another regular user (for permission tests)."""
    return UserFactory(password=user_password)


@pytest.fixture
def post(user):
    """Create and return a published post owned by the user fixture."""
    return PostFactory(author=user)


@pytest.fixture
def unpublished_post(user):
    """Create and return an unpublished post owned by the user fixture."""
    return UnpublishedPostFactory(author=user)


@pytest.fixture
def other_user_post(other_user):
    """Create and return a post owned by other_user."""
    return PostFactory(author=other_user)


@pytest.fixture
def like(user, post):
    """Create and return a like from user on post."""
    return LikeFactory(user=user, post=post)


def get_jwt_token(user):
    """Generate JWT access token for a user."""
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token)


@pytest.fixture
def authenticated_api_client(api_client, user):
    """Return an APIClient authenticated with the user fixture."""
    token = get_jwt_token(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api_client


@pytest.fixture
def admin_api_client(api_client, admin_user):
    """Return an APIClient authenticated with the admin_user fixture."""
    token = get_jwt_token(admin_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api_client


@pytest.fixture
def other_user_api_client(api_client, other_user):
    """Return an APIClient authenticated with the other_user fixture."""
    token = get_jwt_token(other_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api_client


@pytest.fixture
def user_with_token(user):
    """Return a tuple of (user, access_token)."""
    return user, get_jwt_token(user)


@pytest.fixture
def admin_with_token(admin_user):
    """Return a tuple of (admin_user, access_token)."""
    return admin_user, get_jwt_token(admin_user)
