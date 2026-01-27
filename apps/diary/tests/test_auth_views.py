"""
Tests for HTML authentication views.

Tests cover:
- Sign up
- Login
- Logout
- Username change
- Email change
- User delete
"""

from django.urls import reverse

import pytest

from apps.diary.models import CustomUser

pytestmark = pytest.mark.django_db


class TestSignUpView:
    """Tests for the sign up view."""

    def test_signup_page_renders(self, client):
        """GET /signup/ returns 200 with signup template."""
        response = client.get(reverse("signup"))

        assert response.status_code == 200
        template_names = [t.name for t in response.templates]
        assert "registration/signup.html" in template_names

    def test_signup_success(self, client):
        """POST creates user and logs in."""
        response = client.post(
            reverse("signup"),
            {
                "username": "newuser",
                "email": "newuser@example.com",
                "password1": "securepass123",
                "password2": "securepass123",
                "accept_terms": True,
            },
        )

        # Should redirect to profile page
        assert response.status_code == 302
        assert CustomUser.objects.filter(username="newuser").exists()

    def test_signup_auto_login(self, client):
        """User is authenticated after signup."""
        response = client.post(
            reverse("signup"),
            {
                "username": "newuser",
                "email": "newuser@example.com",
                "password1": "securepass123",
                "password2": "securepass123",
                "accept_terms": True,
            },
            follow=True,
        )

        assert response.status_code == 200
        # User should be authenticated
        assert response.wsgi_request.user.is_authenticated
        assert response.wsgi_request.user.username == "newuser"

    def test_signup_redirects_to_profile(self, client):
        """After signup, redirects to user's profile page."""
        response = client.post(
            reverse("signup"),
            {
                "username": "newuser",
                "email": "newuser@example.com",
                "password1": "securepass123",
                "password2": "securepass123",
                "accept_terms": True,
            },
        )

        user = CustomUser.objects.get(username="newuser")
        assert response.status_code == 302
        assert response.url == reverse("author-detail", args=[user.pk])

    def test_signup_password_mismatch(self, client):
        """Password mismatch shows error."""
        response = client.post(
            reverse("signup"),
            {
                "username": "newuser",
                "email": "newuser@example.com",
                "password1": "securepass123",
                "password2": "differentpass456",
            },
        )

        assert response.status_code == 200  # stays on page
        assert not CustomUser.objects.filter(username="newuser").exists()
        assert "password2" in response.context["form"].errors

    def test_signup_duplicate_username(self, client, user):
        """Duplicate username shows error."""
        response = client.post(
            reverse("signup"),
            {
                "username": user.username,
                "email": "different@example.com",
                "password1": "securepass123",
                "password2": "securepass123",
            },
        )

        assert response.status_code == 200
        assert "username" in response.context["form"].errors

    def test_signup_duplicate_email(self, client, user):
        """Duplicate email shows error."""
        response = client.post(
            reverse("signup"),
            {
                "username": "differentuser",
                "email": user.email,
                "password1": "securepass123",
                "password2": "securepass123",
            },
        )

        assert response.status_code == 200
        assert "email" in response.context["form"].errors


class TestLoginView:
    """Tests for the login view."""

    def test_login_page_renders(self, client):
        """GET /login/ returns 200 with login template."""
        response = client.get(reverse("login"))

        assert response.status_code == 200
        template_names = [t.name for t in response.templates]
        assert "registration/login.html" in template_names

    def test_login_success_redirects_to_profile(self, client, user, user_password):
        """Valid credentials redirect to profile."""
        response = client.post(
            reverse("login"),
            {
                "username": user.username,
                "password": user_password,
            },
        )

        assert response.status_code == 302
        assert response.url == reverse("author-detail", args=[user.pk])

    def test_login_invalid_credentials(self, client, user):
        """Invalid credentials show error."""
        response = client.post(
            reverse("login"),
            {
                "username": user.username,
                "password": "wrongpassword",
            },
        )

        assert response.status_code == 200  # stays on page
        assert response.context["form"].errors

    def test_login_authenticates_user(self, client, user, user_password):
        """After login, user is authenticated."""
        response = client.post(
            reverse("login"),
            {
                "username": user.username,
                "password": user_password,
            },
            follow=True,
        )

        assert response.status_code == 200
        assert response.wsgi_request.user.is_authenticated
        assert response.wsgi_request.user == user


class TestLogoutView:
    """Tests for the logout view."""

    def test_logout_unauthenticates_user(self, client, user):
        """Logout removes authentication."""
        client.force_login(user)

        # Verify logged in
        response = client.get(reverse("home"))
        assert response.wsgi_request.user.is_authenticated

        # Logout
        response = client.post(reverse("logout"), follow=True)

        # Verify logged out
        assert not response.wsgi_request.user.is_authenticated


class TestUsernameChangeView:
    """Tests for the username change view."""

    def test_username_change_requires_login(self, client):
        """Unauthenticated users are redirected."""
        response = client.get(reverse("username_change"))

        assert response.status_code == 302
        assert "login" in response.url

    def test_username_change_page_renders(self, client, user):
        """Authenticated user sees username change form."""
        client.force_login(user)

        response = client.get(reverse("username_change"))

        assert response.status_code == 200
        template_names = [t.name for t in response.templates]
        assert "registration/username_change.html" in template_names

    def test_username_change_success(self, client, user, user_password):
        """Valid data changes username."""
        client.force_login(user)
        old_username = user.username

        response = client.post(
            reverse("username_change"),
            {
                "password": user_password,
                "new_username": "changedusername",
            },
        )

        assert response.status_code == 302  # redirect on success
        user.refresh_from_db()
        assert user.username == "changedusername"
        assert user.username != old_username

    def test_username_change_wrong_password(self, client, user):
        """Wrong password shows error."""
        client.force_login(user)
        old_username = user.username

        response = client.post(
            reverse("username_change"),
            {
                "password": "wrongpassword",
                "new_username": "changedusername",
            },
        )

        assert response.status_code == 200  # stays on page
        user.refresh_from_db()
        assert user.username == old_username  # unchanged


class TestEmailChangeView:
    """Tests for the email change view."""

    def test_email_change_requires_login(self, client):
        """Unauthenticated users are redirected."""
        response = client.get(reverse("email_change"))

        assert response.status_code == 302
        assert "login" in response.url

    def test_email_change_page_renders(self, client, user):
        """Authenticated user sees email change form."""
        client.force_login(user)

        response = client.get(reverse("email_change"))

        assert response.status_code == 200
        template_names = [t.name for t in response.templates]
        assert "registration/email_change.html" in template_names


class TestUserDeleteView:
    """Tests for the user delete view."""

    def test_user_delete_requires_login(self, client, user):
        """Unauthenticated users are redirected to home (with warning)."""
        response = client.get(reverse("user-delete", args=[user.pk]))

        # UserDeleteView redirects unauthenticated users to home
        # (custom handle_no_permission behavior)
        assert response.status_code == 302
        assert response.url == reverse("home")

    def test_user_delete_only_own_account(self, client, user, other_user):
        """Can only delete own account."""
        client.force_login(user)

        response = client.get(reverse("user-delete", args=[other_user.pk]))

        # Should redirect with warning
        assert response.status_code == 302
        # other_user should still exist
        assert CustomUser.objects.filter(pk=other_user.pk).exists()

    def test_user_delete_page_renders(self, client, user):
        """User can see delete confirmation page for own account."""
        client.force_login(user)

        response = client.get(reverse("user-delete", args=[user.pk]))

        assert response.status_code == 200
        template_names = [t.name for t in response.templates]
        assert "diary/user-delete.html" in template_names

    def test_user_delete_success(self, client, user):
        """Confirming delete removes account."""
        client.force_login(user)
        user_id = user.pk

        response = client.post(reverse("user-delete", args=[user_id]))

        assert response.status_code == 302  # redirect
        assert not CustomUser.objects.filter(pk=user_id).exists()

    def test_user_delete_logs_out_user(self, client, user):
        """Deleting account logs out user."""
        client.force_login(user)
        user_id = user.pk

        response = client.post(reverse("user-delete", args=[user_id]), follow=True)

        # User should be logged out
        assert not response.wsgi_request.user.is_authenticated


class TestAuthorListView:
    """Tests for the author list view (staff only)."""

    def test_author_list_requires_staff(self, client, user):
        """Non-staff users are redirected."""
        client.force_login(user)

        response = client.get(reverse("author-list"))

        # Should redirect with warning
        assert response.status_code == 302

    def test_author_list_accessible_to_staff(self, client, admin_user):
        """Staff users can access author list."""
        client.force_login(admin_user)

        response = client.get(reverse("author-list"))

        assert response.status_code == 200
        template_names = [t.name for t in response.templates]
        assert "diary/customuser_list.html" in template_names


class TestAuthorDetailView:
    """Tests for the author detail view."""

    def test_author_detail_requires_login(self, client, user):
        """Unauthenticated users are redirected."""
        response = client.get(reverse("author-detail", args=[user.pk]))

        assert response.status_code == 302  # redirect to login

    def test_author_detail_accessible_when_logged_in(self, client, user, other_user):
        """Authenticated users can view any profile."""
        client.force_login(user)

        response = client.get(reverse("author-detail", args=[other_user.pk]))

        assert response.status_code == 200
        template_names = [t.name for t in response.templates]
        assert "diary/customuser_detail.html" in template_names

    def test_author_detail_shows_user_posts(self, client, user, post):
        """Author detail shows user's posts."""
        client.force_login(user)

        response = client.get(reverse("author-detail", args=[user.pk]))

        assert response.status_code == 200
        assert post in response.context["object_list"]
