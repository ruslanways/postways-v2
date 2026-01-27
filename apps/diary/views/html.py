"""
HTML views for the diary application.

This module contains traditional Django class-based views for HTML rendering
with session-based authentication.

Views:
    - HomeView, HomeViewPopular: Public post listing with pagination
    - SignUp, Login, PasswordReset: Authentication views
    - AuthorListView, AuthorDetailView: User management (staff only)
    - PostCreateView, PostDetailView, PostUpdateView, PostDeleteView: Post CRUD
"""

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import (
    LoginView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetView,
)
from django.db.models import Count
from django.shortcuts import redirect, resolve_url
from django.urls import reverse, reverse_lazy
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.views.generic import DetailView, FormView, ListView
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from django.views.generic.list import MultipleObjectMixin

from ..forms import (
    AddPostForm,
    CustomAuthenticationForm,
    CustomPasswordChangeForm,
    CustomPasswordResetForm,
    CustomSetPasswordForm,
    CustomUserCreationForm,
    EmailChangeForm,
    UpdatePostForm,
    UsernameChangeForm,
)
from ..models import CustomUser, Like, Post
from ..tasks import send_email_verification, send_password_reset_email


class HomeView(ListView):
    """
    Public homepage displaying published posts.

    Posts are ordered by most recently updated, with like counts annotated.
    Authenticated users see which posts they've liked.
    """

    paginate_by = 6
    template_name = "diary/index.html"
    queryset = (
        Post.objects.annotate(Count("like"))
        .select_related("author")
        .filter(published=True)
    )
    ordering = ["-updated", "-like__count"]

    def get_context_data(self, **kwargs):
        """
        Add ordering indicator and liked posts set to context.

        Context additions:
            ordering: Current sort mode ("new" for this view)
            liked_by_user: Set of post IDs the user has liked (authenticated only)
        """
        context = super().get_context_data(**kwargs)
        context["ordering"] = "new"
        if self.request.user.is_authenticated:
            page_post_ids = [post.id for post in context["object_list"]]
            context["liked_by_user"] = set(
                Like.objects.filter(
                    user=self.request.user, post_id__in=page_post_ids
                ).values_list("post_id", flat=True)
            )
        return context


class HomeViewPopular(HomeView):
    """
    Alternative homepage with posts ordered by popularity.

    Inherits from HomeView but changes the ordering to prioritize
    posts with the highest like counts, then by most recently updated.
    """

    ordering = ["-like__count", "-updated"]

    def get_context_data(self, **kwargs):
        """Set ordering indicator to 'popular' for template toggle link."""
        context = super().get_context_data(**kwargs)
        context["ordering"] = "popular"
        return context


class SignUp(CreateView):
    """
    User registration view.

    After successful signup, automatically logs in the user
    and redirects to their profile page.
    """

    form_class = CustomUserCreationForm
    template_name = "registration/signup.html"

    def form_valid(self, form):
        """Save user, log them in, and redirect to their profile."""
        self.object = form.save()
        login(self.request, self.object)
        return redirect("author-detail", self.object.pk)


class Login(LoginView):
    """User login view. Redirects to user's profile on success."""

    template_name = "registration/login.html"
    form_class = CustomAuthenticationForm

    def get_default_redirect_url(self):
        """Redirect to user's profile page after login."""
        return resolve_url("author-detail", self.request.user.pk)


class PasswordReset(PasswordResetView):
    """
    Password reset request view. Sends reset email via Celery.

    Overrides the default behavior to queue password reset emails asynchronously
    instead of sending them synchronously, preventing request timeouts if the
    SMTP server is slow or unresponsive.
    """

    form_class = CustomPasswordResetForm
    template_name = "registration/password_reset_form.html"
    success_url = reverse_lazy("password_reset_done")

    def get_site_name(self) -> str:
        """Get site name from Django Sites framework or fallback to default."""
        try:
            from django.contrib.sites.models import Site

            return Site.objects.get_current().name
        except Exception:
            # Sites framework not installed, not configured, or no current site
            return "Postways"

    def form_valid(self, form):
        """Queue password reset emails via Celery instead of sending synchronously."""
        email = form.cleaned_data["email"]
        site_name = self.get_site_name()

        for user in form.get_users(email):
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            reset_url = self.request.build_absolute_uri(
                reverse(
                    "password_reset_confirm", kwargs={"uidb64": uid, "token": token}
                )
            )

            send_password_reset_email.delay(
                user_email=email,
                reset_url=reset_url,
                username=user.get_username(),
                site_name=site_name,
            )

        return redirect(self.success_url)


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    """Password reset confirmation view. Allows user to set new password."""

    form_class = CustomSetPasswordForm


class CustomPasswordChangeView(PasswordChangeView):
    """
    Password change view that also blacklists JWT tokens.

    Extends Django's built-in PasswordChangeView to ensure that when a user
    changes their password via the HTML interface, all their JWT tokens are
    also invalidated. This provides consistent security behavior with the
    API password change endpoint.

    Security: After successful password change:
        - All JWT refresh tokens are blacklisted (forces API re-authentication)
        - All sessions are invalidated (Django's default behavior when
          update_session_auth_hash is not called, but we call it to keep
          the current session valid while invalidating others)
    """

    form_class = CustomPasswordChangeForm

    def form_valid(self, form):
        """
        Save the new password and blacklist all JWT tokens.

        Note: The parent's form_valid() calls update_session_auth_hash() which
        keeps the current session valid. Other sessions will be invalidated
        because their stored password hash won't match.
        """
        from .api import blacklist_user_tokens

        # Blacklist all JWT tokens before changing password
        blacklist_user_tokens(self.request.user)

        # Call parent which saves password and updates current session
        return super().form_valid(form)


class UsernameChangeView(LoginRequiredMixin, FormView):
    """
    Username change view with password confirmation.

    Requires login and validates:
        - Current password is correct
        - New username is unique (case-insensitive)
        - 30-day cooldown between username changes

    Redirects to user's profile page on success.
    """

    template_name = "registration/username_change.html"
    form_class = UsernameChangeForm

    def get_form_kwargs(self):
        """Pass the current user to the form."""
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        """Save the new username and show success message."""
        form.save()
        messages.success(self.request, "Username changed successfully.")
        return redirect("author-detail", self.request.user.pk)


class EmailChangeView(LoginRequiredMixin, FormView):
    """
    Email change view with password confirmation.

    Requires login and validates:
        - Current password is correct
        - New email is unique (case-insensitive)
        - New email is different from current

    Sends verification email to new address on success.
    """

    template_name = "registration/email_change.html"
    form_class = EmailChangeForm

    def get_form_kwargs(self):
        """Pass the current user to the form."""
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        """Save pending email, send verification, and show success message."""
        user, token, new_email = form.save()

        # Build verification link
        verification_link = self.request.build_absolute_uri(
            reverse_lazy("email_verify", kwargs={"token": token})
        )

        # Send verification email via Celery
        send_email_verification.delay(verification_link, new_email)

        messages.success(
            self.request,
            "Verification email sent. Please check your new email address.",
        )
        return redirect("author-detail", self.request.user.pk)


class EmailVerifyView(FormView):
    """
    Email verification view.

    Validates the token from the URL and completes the email change.
    Redirects to home on success with a success message.
    """

    template_name = "registration/email_verify_error.html"

    def get(self, request, token, *args, **kwargs):
        """
        Verify token and update email.

        Args:
            token: UUID verification token from URL

        Returns:
            Redirect to home on success, error page on failure
        """
        from django.utils import timezone

        try:
            user = CustomUser.objects.get(email_verification_token=token)
        except CustomUser.DoesNotExist:
            messages.error(request, "Invalid verification link.")
            return redirect("home")

        if user.email_verification_expires < timezone.now():
            messages.error(request, "Verification link has expired.")
            return redirect("home")

        # Update email
        user.email = user.pending_email

        # Clear pending fields
        user.pending_email = ""
        user.email_verification_token = ""
        user.email_verification_expires = None
        user.save()

        messages.success(request, "Email changed successfully.")
        return redirect("home")


class StaffRequiredMixin(UserPassesTestMixin):
    """
    Mixin that requires staff (is_staff=True) access.

    Unlike the default UserPassesTestMixin behavior (403 response),
    this mixin redirects unauthorized users to the homepage with
    a warning message. This provides better UX for non-staff users.
    """

    permission_denied_message = "Access for staff only!"

    def test_func(self):
        """Return True if user is a staff member."""
        return self.request.user.is_staff

    def handle_no_permission(self):
        """Redirect to home with a warning message instead of raising 403."""
        messages.warning(self.request, self.permission_denied_message)
        return redirect("home")


class AuthorListView(StaffRequiredMixin, ListView):
    """
    Staff-only view listing all users with statistics.

    Displays user counts for posts, likes given, and likes received.
    Supports sortable columns with toggle between ascending/descending order.
    Sort preference is stored in session.
    """

    template_name = "diary/customuser_list.html"

    def get_queryset(self):
        """
        Implement user-ordering using session to store per-user sort preference.
        Toggle between ascending/descending when clicking the same field.
        """
        sortfield = self.kwargs.get("sortfield")
        session_key = "author_list_ordering"

        if sortfield:
            current_ordering = self.request.session.get(session_key, "id")
            if "-" + sortfield == current_ordering:
                ordering = sortfield
            else:
                ordering = "-" + sortfield
            self.request.session[session_key] = ordering
        else:
            ordering = self.request.session.get(session_key, "id")

        return CustomUser.objects.annotate(
            Count("post", distinct=True),
            Count("like", distinct=True),
            Count("post__like", distinct=True),
        ).order_by(ordering)

    def get_context_data(self, **kwargs):
        """
        Add site-wide statistics to context.

        Context additions:
            posts: Total post count across all users
            likes: Total like count across all posts
            current_sort: Current sort field (without - prefix)
            sort_direction: 'desc' or 'asc'
        """
        context = super().get_context_data(**kwargs)
        context["posts"] = Post.objects.count()
        context["likes"] = Like.objects.count()

        ordering = self.request.session.get("author_list_ordering", "id")
        if ordering.startswith("-"):
            context["current_sort"] = ordering[1:]
            context["sort_direction"] = "desc"
        else:
            context["current_sort"] = ordering
            context["sort_direction"] = "asc"

        return context


class AuthorDetailView(UserPassesTestMixin, DetailView, MultipleObjectMixin):
    """
    User profile page showing user details and their posts.

    Access restricted to authenticated users.
    Displays paginated list of user's posts with like counts.
    """

    template_name = "diary/customuser_detail.html"
    model = CustomUser
    paginate_by = 6
    permission_denied_message = "Please log in to view profiles."

    def test_func(self):
        """Allow access only to authenticated users."""
        return self.request.user.is_authenticated

    def get_queryset(self):
        """Annotate user with total likes received on their posts."""
        return CustomUser.objects.annotate(
            likes_received=Count("post__like", distinct=True)
        )

    def get_context_data(self, **kwargs):
        """
        Add paginated post list and liked posts set to context.

        Context additions:
            object_list: Paginated list of user's posts with like counts
            liked_by_user: Set of post IDs the user has liked (authenticated only)
        """
        object_list = (
            self.object.post_set.all()
            .annotate(Count("like"))
            .order_by("-updated", "-like__count")
        )
        context = super().get_context_data(object_list=object_list, **kwargs)
        if self.request.user.is_authenticated:
            # Get post IDs from the paginated object list
            page_post_ids = [post.id for post in context["object_list"]]
            context["liked_by_user"] = set(
                Like.objects.filter(
                    user=self.request.user, post_id__in=page_post_ids
                ).values_list("post_id", flat=True)
            )
        return context


class PostListView(StaffRequiredMixin, HomeView, ListView):
    """
    Staff-only view listing all posts (including unpublished).

    Unlike the public HomeView, this view shows all posts regardless
    of published status, allowing staff to moderate or review drafts.
    """

    template_name = "diary/post_list.html"
    queryset = Post.objects.annotate(Count("like")).select_related("author")


class PostCreateView(LoginRequiredMixin, CreateView):
    """Create a new post. Requires authentication."""

    form_class = AddPostForm
    template_name = "diary/add-post.html"
    success_url = reverse_lazy("home")

    def form_valid(self, form):
        """Set the post author to the current user before saving."""
        form.instance.author = self.request.user
        return super().form_valid(form)


class PostDetailView(DetailView):
    """Public view for a single post with like count and status."""

    template_name = "diary/post_detail.html"
    queryset = Post.objects.annotate(Count("like")).select_related("author")

    def get_context_data(self, **kwargs):
        """Add liked_by_user set for authenticated users."""
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context["liked_by_user"] = (
                {self.object.id}
                if Like.objects.filter(
                    user=self.request.user, post=self.object
                ).exists()
                else set()
            )
        return context


class PostOwnerOrStaffMixin(UserPassesTestMixin):
    """
    Mixin for views that require post owner or staff access.

    Used by PostUpdateView and PostDeleteView to ensure only the
    post author or a staff member can modify/delete a post.
    """

    permission_denied_message = "Access for staff or profile owner!"

    def test_func(self):
        """Return True if user is staff or owns the post."""
        return (
            self.request.user.is_staff
            or self.request.user.pk == self.get_object().author_id
        )


class PostUpdateView(PostOwnerOrStaffMixin, UpdateView):
    """
    Edit a post. Only the post owner or staff can access.

    Redirects to post detail page on success (via model's get_absolute_url).
    """

    model = Post
    form_class = UpdatePostForm
    template_name = "diary/post-update.html"


class PostDeleteView(PostOwnerOrStaffMixin, DeleteView):
    """
    Delete a post with confirmation page.

    Only the post owner or staff can access. Redirects to the
    author's profile page after successful deletion.
    """

    model = Post
    template_name = "diary/post-delete.html"

    def get_success_url(self):
        """Redirect to the author's profile after deletion."""
        return reverse_lazy("author-detail", kwargs={"pk": self.object.author_id})


class UserDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """
    Delete user account with confirmation page.

    Only allows users to delete their own account (not staff deleting others).
    Logs out the user before deletion and redirects to home page.
    """

    model = CustomUser
    template_name = "diary/user-delete.html"
    permission_denied_message = "You can only delete your own account!"

    def test_func(self):
        """Only allow users to delete their own account."""
        return self.request.user.id == self.kwargs["pk"]

    def handle_no_permission(self):
        """Redirect with warning message instead of raising 403."""
        messages.warning(self.request, self.permission_denied_message)
        return redirect("home")

    def form_valid(self, form):
        """
        Log out the user and invalidate tokens before deleting their account.
        """
        from .api import blacklist_user_tokens

        self.object = self.get_object()
        # Blacklist any JWT tokens (if user used the API)
        blacklist_user_tokens(self.object)
        # Log out before deletion to avoid session issues
        logout(self.request)
        # Perform the actual deletion
        self.object.delete()
        return redirect(self.get_success_url())

    def get_success_url(self):
        """Redirect to home page after account deletion."""
        return reverse_lazy("home")
