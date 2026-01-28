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


class TestPasswordResetView:
    """Tests for the password reset view."""

    def test_password_reset_page_renders(self, client):
        """GET /password_reset/ returns 200 with form."""
        response = client.get(reverse("password_reset"))

        assert response.status_code == 200
        template_names = [t.name for t in response.templates]
        assert "registration/password_reset_form.html" in template_names

    def test_password_reset_form_valid_queues_email(self, client, user, monkeypatch):
        """POST with valid email queues Celery task."""
        calls = []

        def mock_delay(**kwargs):
            calls.append(kwargs)

        monkeypatch.setattr(
            "apps.diary.views.html.send_password_reset_email.delay", mock_delay
        )

        response = client.post(
            reverse("password_reset"),
            {"email": user.email},
        )

        # Should redirect to done page
        assert response.status_code == 302
        assert response.url == reverse("password_reset_done")

        # Task should be called with correct args
        assert len(calls) == 1
        assert calls[0]["user_email"] == user.email
        assert calls[0]["username"] == user.username
        assert "reset_url" in calls[0]

    def test_password_reset_nonexistent_email_no_task(self, client, monkeypatch):
        """POST with nonexistent email still redirects but no task queued."""
        calls = []

        def mock_delay(**kwargs):
            calls.append(kwargs)

        monkeypatch.setattr(
            "apps.diary.views.html.send_password_reset_email.delay", mock_delay
        )

        response = client.post(
            reverse("password_reset"),
            {"email": "nonexistent@example.com"},
        )

        # Should still redirect (no information leak)
        assert response.status_code == 302
        # No task should be called
        assert len(calls) == 0


class TestCustomPasswordChangeView:
    """Tests for the password change view with JWT blacklisting."""

    def test_password_change_requires_login(self, client):
        """Unauthenticated users are redirected."""
        response = client.get(reverse("password_change"))

        assert response.status_code == 302
        assert "login" in response.url

    def test_password_change_page_renders(self, client, user):
        """Authenticated user sees password change form."""
        client.force_login(user)

        response = client.get(reverse("password_change"))

        assert response.status_code == 200

    def test_password_change_blacklists_jwt_tokens(
        self, client, user, user_password, monkeypatch
    ):
        """Password change blacklists all JWT tokens."""
        calls = []

        def mock_blacklist(user_arg):
            calls.append(user_arg)

        monkeypatch.setattr(
            "apps.diary.views.api.blacklist_user_tokens", mock_blacklist
        )
        client.force_login(user)

        response = client.post(
            reverse("password_change"),
            {
                "old_password": user_password,
                "new_password1": "newsecurepass123",
                "new_password2": "newsecurepass123",
            },
        )

        # Should redirect on success
        assert response.status_code == 302
        # Should blacklist tokens
        assert len(calls) == 1
        assert calls[0] == user

    def test_password_change_wrong_old_password(self, client, user):
        """Wrong old password shows error."""
        client.force_login(user)

        response = client.post(
            reverse("password_change"),
            {
                "old_password": "wrongpassword",
                "new_password1": "newsecurepass123",
                "new_password2": "newsecurepass123",
            },
        )

        assert response.status_code == 200  # stays on page
        assert "old_password" in response.context["form"].errors


class TestEmailChangeFormValid:
    """Tests for email change form_valid (verification email sending)."""

    def test_email_change_sends_verification(
        self, client, user, user_password, monkeypatch
    ):
        """Email change queues verification email via Celery."""
        calls = []

        def mock_delay(verification_link, new_email):
            calls.append((verification_link, new_email))

        monkeypatch.setattr(
            "apps.diary.views.html.send_email_verification.delay", mock_delay
        )
        client.force_login(user)

        response = client.post(
            reverse("email_change"),
            {
                "password": user_password,
                "new_email": "newemail@example.com",
            },
        )

        # Should redirect on success
        assert response.status_code == 302

        # Task should be called with verification link and new email
        assert len(calls) == 1
        verification_link, new_email = calls[0]
        assert new_email == "newemail@example.com"
        # First arg should be verification link
        assert "email_verify" in verification_link


class TestEmailVerifyView:
    """Tests for email verification view."""

    def test_email_verify_success(self, client, user):
        """Valid token verifies email."""
        from datetime import timedelta
        from uuid import uuid4

        from django.utils import timezone

        # Set up pending email verification
        token = uuid4()
        user.pending_email = "verified@example.com"
        user.email_verification_token = str(token)
        user.email_verification_expires = timezone.now() + timedelta(hours=24)
        user.save()

        response = client.get(reverse("email_verify", kwargs={"token": token}))

        # Should redirect to home
        assert response.status_code == 302
        assert response.url == reverse("home")

        # Email should be updated
        user.refresh_from_db()
        assert user.email == "verified@example.com"
        assert user.pending_email == ""
        assert user.email_verification_token == ""
        assert user.email_verification_expires is None

    def test_email_verify_invalid_token(self, client):
        """Invalid token redirects with error message."""
        from uuid import uuid4

        response = client.get(
            reverse("email_verify", kwargs={"token": uuid4()}), follow=True
        )

        assert response.status_code == 200
        # Should show error message
        messages = list(response.context["messages"])
        assert len(messages) == 1
        assert "Invalid" in str(messages[0])

    def test_email_verify_expired_token(self, client, user):
        """Expired token redirects with error message."""
        from datetime import timedelta
        from uuid import uuid4

        from django.utils import timezone

        # Set up expired verification
        token = uuid4()
        user.pending_email = "expired@example.com"
        user.email_verification_token = str(token)
        user.email_verification_expires = timezone.now() - timedelta(hours=1)
        user.save()

        response = client.get(
            reverse("email_verify", kwargs={"token": token}), follow=True
        )

        assert response.status_code == 200
        # Should show expiration message
        messages = list(response.context["messages"])
        assert len(messages) == 1
        assert "expired" in str(messages[0])

        # Email should NOT be updated
        user.refresh_from_db()
        assert user.email != "expired@example.com"


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

    def test_author_list_sorting_toggle(self, client, admin_user):
        """Clicking sort field toggles between asc and desc."""
        client.force_login(admin_user)

        # First click on username - should be descending
        response = client.get("/authors/username/")
        assert response.status_code == 200
        assert response.context["current_sort"] == "username"
        assert response.context["sort_direction"] == "desc"

        # Second click on same field - should toggle to ascending
        response = client.get("/authors/username/")
        assert response.status_code == 200
        assert response.context["current_sort"] == "username"
        assert response.context["sort_direction"] == "asc"

    def test_author_list_context_data(self, client, admin_user, post, like):
        """Context includes posts count, likes count, and sort info."""
        client.force_login(admin_user)

        response = client.get(reverse("author-list"))

        assert response.status_code == 200
        assert response.context["posts"] >= 1  # at least our post
        assert response.context["likes"] >= 1  # at least our like
        assert "current_sort" in response.context
        assert "sort_direction" in response.context


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
