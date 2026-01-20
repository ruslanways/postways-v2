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

from django.shortcuts import render
from django.http import JsonResponse
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.conf import settings

from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.filters import OrderingFilter
from rest_framework.reverse import reverse
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.token_blacklist.models import (
    OutstandingToken,
    BlacklistedToken,
)
from rest_framework_simplejwt.tokens import RefreshToken
from django_filters.rest_framework import DjangoFilterBackend
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from ..models import Post, CustomUser, Like
from ..serializers import (
    LikeCreateDestroySerializer,
    LikeSerializer,
    LikeDetailSerializer,
    MyTokenRefreshSerializer,
    PostDetailSerializer,
    PostSerializer,
    TokenRecoverySerializer,
    UserDetailSerializer,
    UserSerializer,
)
from ..permissions import (
    OwnerOrAdmin,
    OwnerOrAdminOrReadOnly,
    ReadForAdminCreateForAnonymous,
)
from ..tasks import send_token_recovery_email

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


class UserListAPIView(generics.ListCreateAPIView):
    """
    List all users or create a new user.

    GET: List users (admin only), ordered by last_request descending.
    POST: Create new user (anonymous only - registration endpoint).
    """

    queryset = CustomUser.objects.all().order_by("-last_request")
    serializer_class = UserSerializer
    permission_classes = (ReadForAdminCreateForAnonymous,)


class UserDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a user.

    GET: Retrieve user details with their posts and likes.
    PUT/PATCH: Update user (owner or admin only).
    DELETE: Delete user (owner or admin only). Blacklists all JWT tokens before deletion.
    """

    queryset = CustomUser.objects.all()
    serializer_class = UserDetailSerializer
    permission_classes = (OwnerOrAdmin,)

    def get_object(self):
        """Cache the object to avoid duplicate database queries."""
        if not hasattr(self, "_cached_object"):
            self._cached_object = super().get_object()
        return self._cached_object

    def get_serializer_context(self):
        """
        Extend parent's context with the current object for serializer validators.

        The 'obj' context is used by serializers that need to validate
        unique constraints while excluding the current instance.
        """
        context = super().get_serializer_context()
        context["obj"] = self.get_object()
        return context

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
            return super().destroy(request, *args, **kwargs)


class PostAPIView(generics.ListCreateAPIView):
    """
    List published posts or create a new post.

    GET: List published posts with like counts. Supports ordering by id/updated/created.
    Supports filtering by author, created date, and updated date.
    POST: Create new post (authenticated users only). Author set automatically.
    """

    serializer_class = PostSerializer
    filter_backends = DjangoFilterBackend, OrderingFilter
    filterset_fields = {
        "author": ["exact"],
        "created": ["gte", "lte", "date__range"],
        "updated": ["gte", "lte"],
    }
    ordering_fields = "id", "updated", "created"
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

    def get_queryset(self):
        """Return only published posts with like count annotation."""
        return (
            Post.objects.exclude(published=False)
            .annotate(likes=Count("like"))
            .order_by("-updated")
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
        Like.objects.values("created__date")
        .annotate(likes=Count("id"))
        .order_by("-created__date")
    )
    serializer_class = LikeSerializer
    filter_backends = DjangoFilterBackend, OrderingFilter
    filterset_fields = {
        "created": ["gte", "lte", "date__range"],
    }
    ordering_fields = "created", "likes"


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

        like_count = Like.objects.filter(post=post).count()
        self._broadcast_like_update(post, user, like_count)

        return response

    def _broadcast_like_update(self, post, user, like_count):
        """
        Broadcast like count update to all WebSocket clients.

        Sends a message to the "likes" channel group containing:
        - post_id: ID of the affected post
        - like_count: Current total like count
        - user_id: ID of user who triggered the update (for deduplication)

        Args:
            post: The Post instance that was liked/unliked.
            user: The user who triggered the action.
            like_count: Pre-computed like count to avoid extra query.

        Failures are logged but don't affect the HTTP response.
        """
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "likes",
                {
                    "type": "like.message",
                    "post_id": str(post.id),
                    "like_count": str(like_count),
                    "user_id": user.id,
                },
            )
        except Exception as e:
            logger.warning("Failed to broadcast like update: %s", e)


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
            return Response({"error": "Invalid post IDs"}, status=status.HTTP_400_BAD_REQUEST)

        if not post_ids:
            return Response({})

        posts = Post.objects.filter(id__in=post_ids).annotate(like_count=Count("like"))

        user_liked_ids = set()
        if request.user.is_authenticated:
            user_liked_ids = set(
                Like.objects.filter(user=request.user, post_id__in=post_ids).values_list(
                    "post_id", flat=True
                )
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
    3. Generates a new token pair
    4. Sends the access token to the user's email (via Celery task)

    The user can then use the access token to update their password
    via the UserDetailAPIView endpoint.
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

        refresh = RefreshToken.for_user(user)

        link_to_change_user = reverse(
            "user-detail-update-destroy-api", request=request, args=[user.id]
        )

        # invoke celery task
        send_token_recovery_email.delay(
            link_to_change_user, str(refresh.access_token), user.email
        )

        return Response({"Recovery email send": "Success"}, status=status.HTTP_200_OK)


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
            raise InvalidToken(e.args[0])
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
