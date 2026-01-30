"""
REST API views for the diary application.

This module contains Django REST Framework views for the REST API
with JWT authentication.

API Views (under /api/v1/):
    - UserListAPIView, UserDetailAPIView: User endpoints
    - PostAPIView, PostDetailAPIView: Post endpoints
    - LikeAPIView, LikeDetailAPIView, LikeCreateDestroyAPIView: Like endpoints
    - TokenRecoveryAPIView: Password recovery via email
"""

import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, permissions, status
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from ..models import CustomUser, Like, Post
from ..permissions import (
    OwnerOrAdmin,
    OwnerOrAdminOrReadOnly,
    ReadForAdminCreateForAnonymous,
)
from ..serializers import (
    EmailChangeSerializer,
    EmailVerifySerializer,
    LikeCreateDestroySerializer,
    LikeDetailSerializer,
    LikeSerializer,
    MyTokenRefreshSerializer,
    PasswordChangeSerializer,
    PasswordResetSerializer,
    PostDetailSerializer,
    PostSerializer,
    TokenRecoverySerializer,
    UserDetailSerializer,
    UsernameChangeSerializer,
    UserSerializer,
)
from ..tasks import send_email_verification, send_token_recovery_email

logger = logging.getLogger(__name__)


def blacklist_user_tokens(user):
    """
    Blacklist all outstanding JWT refresh tokens for a user.

    This prevents further API access using any previously issued tokens.
    Used during account deletion and password recovery flows.

    Args:
        user: The CustomUser instance whose tokens should be blacklisted.
    """
    blacklisted_token_ids = BlacklistedToken.objects.filter(
        token__user=user
    ).values_list("token_id", flat=True)
    tokens_to_blacklist = OutstandingToken.objects.filter(user=user).exclude(
        id__in=blacklisted_token_ids
    )
    BlacklistedToken.objects.bulk_create(
        [BlacklistedToken(token=token) for token in tokens_to_blacklist],
        ignore_conflicts=True,
    )


def broadcast_like_update(post_id, user_id, like_count):
    """
    Broadcast like count update to all WebSocket clients.

    Sends a message to the "likes" channel group containing:
    - post_id: ID of the affected post
    - like_count: Current total like count
    - user_id: ID of user who triggered the update (for deduplication)

    Args:
        post_id: ID of the post that was liked/unliked.
        user_id: ID of the user who triggered the action.
        like_count: Current like count for the post.

    Failures are logged but don't affect the caller.
    """
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "likes",
            {
                "type": "like.message",
                "post_id": str(post_id),
                "like_count": str(like_count),
                "user_id": user_id,
            },
        )
    except Exception as e:
        logger.warning("Failed to broadcast like update: %s", e)


class UserListAPIView(generics.ListCreateAPIView):
    """
    List all users or create a new user.

    GET: List users (admin only), ordered by last_activity_at descending.
    POST: Create new user (anonymous only - registration endpoint).
    """

    queryset = CustomUser.objects.all().order_by("-last_activity_at")
    serializer_class = UserSerializer
    permission_classes = (ReadForAdminCreateForAnonymous,)


class UserDetailAPIView(generics.RetrieveDestroyAPIView):
    """
    Retrieve or delete a user.

    GET: Retrieve user details with their posts and likes.
    DELETE: Delete user (owner or admin only). Blacklists all JWT tokens before deletion.

    Note:
        User profile updates (password, username, email) are handled by dedicated endpoints:
        - Password: POST /api/v1/auth/password/change/
        - Username: POST /api/v1/auth/username/change/
        - Email: POST /api/v1/auth/email/change/
    """

    queryset = CustomUser.objects.all()
    serializer_class = UserDetailSerializer
    permission_classes = (OwnerOrAdmin,)

    def destroy(self, request, *args, **kwargs):
        """
        Delete a user account after blacklisting all their JWT tokens.

        Uses atomic transaction to ensure token blacklisting and user deletion
        succeed or fail together. Blacklists all outstanding refresh tokens
        to prevent further API access, then performs user deletion which
        cascades to related posts and likes.
        """
        user = self.get_object()

        with transaction.atomic():
            blacklist_user_tokens(user)
            self.perform_destroy(user)

        return Response(status=status.HTTP_204_NO_CONTENT)


class PostAPIView(generics.ListCreateAPIView):
    """
    List published posts or create a new post.

    GET: List published posts with like counts. Supports ordering by id/updated_at/created_at.
    Supports filtering by author, created_at date, and updated_at date.
    POST: Create new post (authenticated users only). Author set automatically.
    """

    serializer_class = PostSerializer
    filter_backends = DjangoFilterBackend, OrderingFilter
    filterset_fields = {
        "author": ["exact"],
        "created_at": ["gte", "lte", "date__range"],
        "updated_at": ["gte", "lte"],
    }
    ordering_fields = "id", "updated_at", "created_at"
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

    def get_queryset(self):
        """Return only published posts with like count annotation."""
        return (
            Post.objects.exclude(published=False)
            .annotate(like_count=Count("likes"))
            .order_by("-updated_at")
        )

    def perform_create(self, serializer):
        """Set the post author to the current user."""
        serializer.save(author=self.request.user)


class PostDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a post.

    GET: Retrieve post (published only, unless owner/admin).
    PUT/PATCH: Update post (owner only).
    DELETE: Delete post (owner or admin).
    """

    queryset = Post.objects.all()
    serializer_class = PostDetailSerializer
    permission_classes = (OwnerOrAdminOrReadOnly,)

    def retrieve(self, request, *args, **kwargs):
        """Return 403 for unpublished posts unless user is owner or admin."""
        instance = self.get_object()
        if (
            not instance.published
            and instance.author != request.user
            and not request.user.is_staff
        ):
            return Response(
                {"Forbidden": "Unpublished post can be retrieved by owner only!"},
                status=403,
            )
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class LikeAPIView(generics.ListAPIView):
    """
    Analytics endpoint: list likes aggregated by date.

    Returns daily like counts for analytics purposes.
    Supports filtering by date range and ordering.
    """

    queryset = (
        Like.objects.values("created_at__date")
        .annotate(likes=Count("id"))
        .order_by("-created_at__date")
    )
    serializer_class = LikeSerializer
    filter_backends = DjangoFilterBackend, OrderingFilter
    filterset_fields = {
        "created_at": ["gte", "lte", "date__range"],
    }
    ordering_fields = "created_at", "likes"


class LikeDetailAPIView(generics.RetrieveAPIView):
    """Retrieve a single like by ID with user and post references."""

    queryset = Like.objects.all()
    serializer_class = LikeDetailSerializer


class LikeCreateDestroyAPIView(generics.CreateAPIView):
    """
    Toggle like on a post.

    POST with {"post": <id>}:
    - If user hasn't liked the post → creates like → 201
    - If user already liked the post → removes like → 204

    Uses select_for_update() for atomicity and broadcasts updates via WebSocket.
    """

    permission_classes = (permissions.IsAuthenticated,)
    queryset = Like.objects.all()
    serializer_class = LikeCreateDestroySerializer

    def create(self, request, *args, **kwargs):
        """
        Toggle like status for the authenticated user on a post.

        Uses atomic transaction with select_for_update() to handle
        concurrent requests safely. After toggling, broadcasts the
        updated like count to all connected WebSocket clients.

        Returns:
            201 Created: Like was added (includes serialized like data)
            204 No Content: Like was removed
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        post = serializer.validated_data["post"]
        user = request.user

        with transaction.atomic():
            # Lock existing like row if present to prevent race conditions
            existing_like = (
                self.get_queryset()
                .select_for_update()
                .filter(post=post, user=user)
                .first()
            )

            if existing_like:
                existing_like.delete()
                response = Response(status=status.HTTP_204_NO_CONTENT)
            else:
                try:
                    serializer.save(user=user)
                    headers = self.get_success_headers(serializer.data)
                    response = Response(
                        serializer.data, status=status.HTTP_201_CREATED, headers=headers
                    )
                except IntegrityError:
                    # Race condition: another request created the like concurrently
                    # Treat as toggle: delete the just-created like
                    self.get_queryset().filter(post=post, user=user).delete()
                    response = Response(status=status.HTTP_204_NO_CONTENT)

            # Query inside transaction to ensure consistency
            like_count = Like.objects.filter(post=post).count()

        broadcast_like_update(post.id, user.id, like_count)

        return response


class LikeBatchAPIView(generics.GenericAPIView):
    """
    Batch endpoint to get like counts for multiple posts in a single request.

    Used by the frontend to refresh like data after browser back/forward
    navigation (bfcache restoration) or when reconnecting WebSocket.

    URL: GET /api/v1/likes/batch/?ids=1,2,3
    Returns: {"1": {"count": 5, "liked": true}, "2": {"count": 3, "liked": false}}
    """

    def get(self, request):
        """
        Return like counts and user's liked status for requested posts.

        Query Parameters:
            ids: Comma-separated list of post IDs (e.g., "1,2,3")

        Returns:
            JSON object mapping post IDs to {count, liked} objects.
            Returns empty object if no IDs provided.
            Returns 400 if IDs are not valid integers.
        """
        ids_param = request.query_params.get("ids", "")
        if not ids_param:
            return Response({})

        try:
            post_ids = [int(id.strip()) for id in ids_param.split(",") if id.strip()]
        except ValueError:
            return Response(
                {"error": "Invalid post IDs"}, status=status.HTTP_400_BAD_REQUEST
            )

        if not post_ids:
            return Response({})

        posts = Post.objects.filter(id__in=post_ids).annotate(like_count=Count("likes"))

        user_liked_ids = set()
        if request.user.is_authenticated:
            user_liked_ids = set(
                Like.objects.filter(
                    user=request.user, post_id__in=post_ids
                ).values_list("post_id", flat=True)
            )

        result = {
            str(post.id): {"count": post.like_count, "liked": post.id in user_liked_ids}
            for post in posts
        }

        return Response(result)


class MyTokenRefreshView(TokenRefreshView):
    """
    Refresh JWT access token.

    Uses custom serializer that properly tracks rotated refresh tokens
    in the OutstandingToken table for blacklist support.
    """

    serializer_class = MyTokenRefreshSerializer


class TokenRecoveryAPIView(generics.GenericAPIView):
    """
    Recover access for users who forgot their password.

    This endpoint:
    1. Validates the provided email exists
    2. Blacklists all existing refresh tokens for that user
    3. Generates a new access token
    4. Sends the token to the user's email (via Celery task)

    The user can then use the access token to reset their password
    via POST /api/v1/auth/password/reset/.

    Security:
        - All existing tokens are blacklisted before sending recovery token
        - Access token has default short lifetime (configured in SIMPLE_JWT settings)
    """

    serializer_class = TokenRecoverySerializer

    def post(self, request, *args, **kwargs):
        """
        Process token recovery request.

        Request Body:
            email: User's registered email address

        Returns:
            200: Recovery email sent successfully
            404: No user found with the provided email
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            return Response(
                {"error": "No user found with this email"},
                status=status.HTTP_404_NOT_FOUND,
            )

        blacklist_user_tokens(user)

        # Generate access token for password reset
        refresh = RefreshToken.for_user(user)

        password_reset_url = reverse("password-reset-api", request=request)

        # invoke celery task
        send_token_recovery_email.delay(
            password_reset_url, str(refresh.access_token), user.email
        )

        return Response({"Recovery email send": "Success"}, status=status.HTTP_200_OK)


class PasswordChangeAPIView(generics.GenericAPIView):
    """
    Change password for authenticated users.

    This endpoint requires the current password for verification before
    allowing a password change. This is more secure than the user update
    endpoint as it prevents unauthorized password changes.

    POST /api/v1/auth/password/change/
        - old_password: Current password (required)
        - new_password: New password (required)
        - new_password2: New password confirmation (required)

    Security: After successful password change, the user is logged out from
    ALL devices and sessions:
        - All JWT refresh tokens are blacklisted
        - All sessions are invalidated (by not calling update_session_auth_hash,
          Django's session auth hash verification will fail on next request)
    """

    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = PasswordChangeSerializer

    def post(self, request, *args, **kwargs):
        """
        Process password change request.

        Request Body:
            old_password: User's current password
            new_password: New password (validated against Django validators)
            new_password2: New password confirmation

        Returns:
            200: Password changed successfully
            400: Validation error (wrong current password, passwords don't match, etc.)

        Security Note:
            This intentionally does NOT call update_session_auth_hash() to ensure
            all existing sessions are invalidated. Combined with JWT blacklisting,
            this forces re-authentication on all devices after password change.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user

        with transaction.atomic():
            user.set_password(serializer.validated_data["new_password"])
            user.save()

            # Blacklist all JWT refresh tokens to force API re-authentication
            blacklist_user_tokens(user)

        # Note: Sessions are automatically invalidated because we don't call
        # update_session_auth_hash(). Django's session auth stores a password
        # hash that will no longer match, logging out all sessions on next request.

        return Response(
            {"detail": "Password changed successfully."},
            status=status.HTTP_200_OK,
        )


class PasswordResetAPIView(generics.GenericAPIView):
    """
    Reset password using a recovery token (no old password required).

    This endpoint is for users who forgot their password and received a
    recovery token via email from TokenRecoveryAPIView.

    POST /api/v1/auth/password/reset/
        - new_password: New password (required)
        - new_password2: New password confirmation (required)

    Security:
        - Requires valid JWT access token (from recovery email)
        - All existing tokens are blacklisted after successful reset
        - Sessions are invalidated (by not calling update_session_auth_hash)

    Flow:
        1. User requests recovery via POST /api/v1/auth/token/recovery/
        2. User receives email with access token
        3. User calls this endpoint with the token in Authorization header
        4. Password is reset and all sessions/tokens are invalidated
    """

    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = PasswordResetSerializer

    def post(self, request, *args, **kwargs):
        """
        Process password reset request.

        Request Body:
            new_password: New password (validated against Django validators)
            new_password2: New password confirmation

        Headers:
            Authorization: Bearer <access_token>

        Returns:
            200: Password reset successfully
            400: Validation error (passwords don't match, etc.)
            401: Invalid or expired token
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user

        with transaction.atomic():
            user.set_password(serializer.validated_data["new_password"])
            user.save()

            # Blacklist all JWT refresh tokens to force API re-authentication
            blacklist_user_tokens(user)

        return Response(
            {"detail": "Password reset successfully."},
            status=status.HTTP_200_OK,
        )


class UsernameChangeAPIView(generics.GenericAPIView):
    """
    Change username for authenticated users.

    This endpoint requires the current password for verification before
    allowing a username change. Enforces a 30-day cooldown between changes.

    POST /api/v1/auth/username/change/
        - password: Current password (required)
        - new_username: New username (required)

    Validation:
        - Password must be correct
        - New username must be unique (case-insensitive)
        - Username must follow format rules (letters, numbers, @.+-_)
        - 30-day cooldown between username changes
    """

    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = UsernameChangeSerializer

    def post(self, request, *args, **kwargs):
        """
        Process username change request.

        Request Body:
            password: User's current password
            new_username: New username (validated for uniqueness and format)

        Returns:
            200: Username changed successfully, includes new username
            400: Validation error (wrong password, username taken, cooldown active, etc.)
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user

        with transaction.atomic():
            user.username = serializer.validated_data["new_username"]
            user.username_last_changed = timezone.now()
            user.save()

        return Response(
            {
                "detail": "Username changed successfully.",
                "username": user.username,
            },
            status=status.HTTP_200_OK,
        )


class EmailChangeAPIView(generics.GenericAPIView):
    """
    Initiate email change for authenticated users.

    This endpoint requires the current password for verification before
    allowing an email change request. A verification email is sent to the
    new address with a link that expires in 24 hours.

    POST /api/v1/auth/email/change/
        - password: Current password (required)
        - new_email: New email address (required)

    Validation:
        - Password must be correct
        - New email must be unique (case-insensitive)
        - New email must be different from current email
    """

    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = EmailChangeSerializer

    def post(self, request, *args, **kwargs):
        """
        Process email change request.

        Request Body:
            password: User's current password
            new_email: New email address to verify

        Returns:
            200: Verification email sent successfully
            400: Validation error (wrong password, email taken, etc.)
        """
        import uuid
        from datetime import timedelta

        from django.utils import timezone

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        new_email = serializer.validated_data["new_email"]

        # Generate verification token and expiry
        token = str(uuid.uuid4())
        expires = timezone.now() + timedelta(hours=24)

        # Store pending email change
        user.pending_email = new_email
        user.email_verification_token = token
        user.email_verification_expires = expires
        user.save()

        # Build verification link
        verification_link = (
            request.build_absolute_uri(reverse("email-verify-api")) + f"?token={token}"
        )

        # Send verification email via Celery
        send_email_verification.delay(verification_link, new_email)

        return Response(
            {"detail": "Verification email sent to your new email address."},
            status=status.HTTP_200_OK,
        )


class EmailVerifyAPIView(generics.GenericAPIView):
    """
    Verify email change token and update user's email.

    This endpoint validates the verification token and completes the email
    change by updating the user's email to the pending email address.

    POST /api/v1/auth/email/verify/
        - token: Verification token from email link (required)

    GET /api/v1/auth/email/verify/?token=<token>
        - Also accepts token as query parameter for convenience

    Returns:
        200: Email updated successfully
        400: Invalid or expired token
    """

    serializer_class = EmailVerifySerializer

    def post(self, request, *args, **kwargs):
        """
        Verify token and update email.

        Request Body:
            token: UUID verification token

        Returns:
            200: Email changed successfully, includes new email
            400: Validation error (invalid or expired token)
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.user

        with transaction.atomic():
            # Update email
            user.email = user.pending_email

            # Clear pending fields
            user.pending_email = ""
            user.email_verification_token = ""
            user.email_verification_expires = None
            user.save()

        return Response(
            {
                "detail": "Email changed successfully.",
                "email": user.email,
            },
            status=status.HTTP_200_OK,
        )

    def get(self, request, *args, **kwargs):
        """
        Handle GET request with token as query parameter.

        This allows users to click the verification link directly
        instead of making a POST request.
        """
        token = request.query_params.get("token")
        if not token:
            return Response(
                {"error": "Token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Reuse POST logic
        request._full_data = {"token": token}
        return self.post(request, *args, **kwargs)


class MyTokenObtainPairView(TokenObtainPairView):
    """
    Custom JWT login endpoint for HTML/JavaScript clients.

    Instead of returning both tokens in the response body, this view:
    - Returns access token in response body (for JS to store in memory)
    - Sets refresh token as HTTP-only cookie (more secure storage)

    This approach prevents XSS attacks from stealing the refresh token
    while keeping the access token accessible to JavaScript for API calls.
    """

    def post(self, request, *args, **kwargs):
        """
        Authenticate user and return JWT tokens.

        Returns access token in response body and sets refresh token
        as an HTTP-only, SameSite=Strict cookie. In production (DEBUG=False),
        the cookie is also marked as Secure (HTTPS only).

        Returns:
            200: {"access_token": "..."} with refresh_token cookie set
            401: Invalid credentials
        """
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0]) from e
        response = Response(
            {"access_token": serializer.validated_data["access"]},
            status=status.HTTP_200_OK,
        )
        response.set_cookie(
            key="refresh_token",
            value=serializer.validated_data["refresh"],
            httponly=True,
            samesite="Strict",
            secure=not settings.DEBUG,
        )
        return response


class RootAPIView(generics.GenericAPIView):
    """
    API root endpoint.

    Returns links to the main API endpoints for discoverability.
    """

    def get(self, request):
        """Return hyperlinks to main API endpoints."""
        return Response(
            {
                "posts": reverse("post-list-create-api", request=request),
                "users": reverse("user-list-create-api", request=request),
                "likes": reverse("like-list-api", request=request),
            }
        )


# ------------------------------------------------------------------------------
# Error handlers
# ------------------------------------------------------------------------------
def error_403(request, exception=None):
    """Custom 403 Forbidden handler."""
    if request.path.startswith("/api/"):
        return JsonResponse({"error": "Forbidden"}, status=403)
    return render(request, "403.html", status=403)


def error_400(request, exception=None):
    """Custom 400 Bad Request handler."""
    if request.path.startswith("/api/"):
        return JsonResponse({"error": "Bad request"}, status=400)
    return render(request, "400.html", status=400)


def error_404(request, exception=None):
    """Custom 404 Not Found handler."""
    if request.path.startswith("/api/"):
        return JsonResponse({"error": "Not found"}, status=404)
    return render(request, "404.html", status=404)
