"""
Serializers for the diary application REST API.

This module contains serializers for:
    - Authentication & Tokens (JWT refresh, password recovery)
    - User management (registration, profile updates, profile details)
    - Post CRUD operations (list, detail views)
    - Like tracking and analytics (create/destroy, detail views, analytics)

All serializers follow DRF conventions and use HyperlinkedModelSerializer
for RESTful URL-based relationships where appropriate.
"""

from contextlib import suppress
from datetime import timedelta

from django.contrib.auth.password_validation import validate_password
from django.utils import timezone

from rest_framework import serializers
from rest_framework.reverse import reverse
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.utils import datetime_from_epoch

from .models import CustomUser, Like, Post
from .validators import MyUnicodeUsernameValidator

# ============================================================================
# User Serializers
# ============================================================================


class UserSerializer(serializers.HyperlinkedModelSerializer):
    """
    Serializer for user registration and admin user listing.

    Used for:
    - GET /api/v1/users/ (admin only): List users with stats
    - POST /api/v1/users/ (anonymous): Create new user account

    Requires both 'password' and 'password2' fields to match for validation.
    Automatically hashes passwords using Django's password hashing.

    Fields:
        - url: Hyperlink to user detail endpoint
        - id: User ID (read-only)
        - username: Required for registration
        - email: Required for registration
        - password: Write-only, validated against Django password validators
        - password2: Write-only, must match password
        - last_activity_at, last_login, date_joined: Read-only timestamps
        - is_staff, is_active: Read-only admin flags
        - stats: Object with posts_count and likes_received (read-only, admin list only)
    """

    url = serializers.HyperlinkedIdentityField(
        view_name="user-detail-update-destroy-api",
        lookup_field="pk",
        lookup_url_kwarg="user_id_or_username",
    )
    password2 = serializers.CharField(style={"input_type": "password"}, write_only=True)
    stats = serializers.SerializerMethodField(read_only=True)

    def get_stats(self, obj):
        """
        Return post count and likes received from annotated queryset.

        Only populated when queryset has posts_count and likes_received annotations
        (admin list view). Returns None for registration responses.
        """
        posts_count = getattr(obj, "posts_count", None)
        likes_received = getattr(obj, "likes_received", None)

        if posts_count is None and likes_received is None:
            return None

        return {
            "posts_count": posts_count or 0,
            "likes_received": likes_received or 0,
        }

    class Meta:
        model = CustomUser
        fields = (
            "url",
            "id",
            "username",
            "email",
            "last_activity_at",
            "last_login",
            "date_joined",
            "is_staff",
            "is_active",
            "password",
            "password2",
            "stats",
        )
        extra_kwargs = {
            "password": {
                "style": {"input_type": "password"},
                "write_only": True,
            },
        }
        read_only_fields = (
            "id",
            "is_active",
            "last_activity_at",
            "last_login",
            "date_joined",
            "is_staff",
        )

    def validate(self, data):
        """
        Validate password presence, match, and Django password rules.

        Runs Django's validate_password (length, common passwords, similarity
        to username/email, etc.) using a temporary user built from data.

        Returns:
            dict: Validated data.

        Raises:
            ValidationError: If password/password2 missing, don't match, or
                fail Django's password validators.
        """
        password = data.get("password")
        password2 = data.get("password2")

        # Explicit checks for clearer error messages (DRF may validate required earlier).
        if not password:
            raise serializers.ValidationError({"password": "This field is required."})
        if not password2:
            raise serializers.ValidationError({"password2": "This field is required."})

        if password != password2:
            raise serializers.ValidationError({"password2": "Passwords must match."})

        # Temporary user instance so validate_password can run similarity and other validators.
        user_kwargs = dict(data)
        user_kwargs.pop("password2", None)
        validate_password(password=password, user=CustomUser(**user_kwargs))

        return data

    def create(self, validated_data):
        """
        Create a new user with hashed password via the model manager.

        Returns:
            CustomUser: The newly created user instance.

        Raises:
            ValidationError: If user creation fails (e.g. duplicate email or username).
        """
        validated_data.pop("password2", None)
        instance = self.Meta.model._default_manager.create_user(
            email=validated_data["email"],
            username=validated_data["username"],
            password=validated_data["password"],
        )
        return instance


class UserDetailSerializer(serializers.HyperlinkedModelSerializer):
    """
    Serializer for user detail and delete operations.

    Used for GET/DELETE /api/v1/users/{id}/.
    Returns user info with stats and links to related resources.

    Fields:
        - id: User ID (read-only)
        - username: Read-only (use /api/v1/auth/username/change/ to change)
        - email: Read-only (use /api/v1/auth/email/change/ to change)
        - date_joined: Read-only timestamp
        - last_login, last_activity_at: Read-only timestamps (owner/staff only)
        - is_staff, is_active: Read-only admin flags (owner/staff only)
        - stats: Object with posts_count and likes_received
        - links: Object with self and posts URLs

    Stats visibility rules:
        - posts_count: Staff/owner see all posts, others see only published
        - likes_received: Staff/owner see likes on all posts, others only on published

    Note:
        Password, username, and email changes are NOT allowed via this endpoint.
        Use the dedicated endpoints instead:
        - Password: /api/v1/auth/password/change/
        - Username: /api/v1/auth/username/change/
        - Email: /api/v1/auth/email/change/
    """

    stats = serializers.SerializerMethodField()
    links = serializers.SerializerMethodField()

    def _is_owner_or_staff(self, obj):
        """Check if request user is profile owner or staff."""
        request = self.context.get("request")
        return (
            request
            and request.user
            and request.user.is_authenticated
            and (request.user.pk == obj.pk or request.user.is_staff)
        )

    def get_stats(self, obj):
        """
        Return post count and likes received.

        Visibility for non-owner/non-staff:
            - posts_count: only published posts
            - likes_received: only likes on published posts

        Visibility for owner/staff:
            - posts_count: all posts (including unpublished)
            - likes_received: likes on all posts
        """
        if self._is_owner_or_staff(obj):
            posts_qs = obj.posts.all()
        else:
            posts_qs = obj.posts.filter(published=True)

        posts_count = posts_qs.count()
        likes_received = Like.objects.filter(post__in=posts_qs).count()

        return {
            "posts_count": posts_count,
            "likes_received": likes_received,
        }

    def get_links(self, obj):
        """Return hypermedia links to related resources."""
        request = self.context.get("request")
        return {
            "self": reverse(
                "user-detail-update-destroy-api",
                kwargs={"user_id_or_username": obj.pk},
                request=request,
            ),
            "posts": f"{reverse('post-list-create-api', request=request)}?author={obj.pk}",
        }

    class Meta:
        model = CustomUser
        fields = (
            "id",
            "username",
            "email",
            "date_joined",
            "last_login",
            "last_activity_at",
            "is_staff",
            "is_active",
            "stats",
            "links",
        )
        read_only_fields = (
            "id",
            "username",
            "email",
            "is_active",
            "is_staff",
            "last_activity_at",
            "last_login",
            "date_joined",
        )

    def to_representation(self, instance):
        """
        Conditionally hide sensitive fields for non-owner, non-staff users.

        Fields hidden from other users:
            - email
            - last_activity_at
            - last_login
            - is_staff
            - is_active

        Visibility:
            - Owner (viewing own profile): all fields visible
            - Staff: all fields visible
            - Other authenticated users: sensitive fields hidden
        """
        ret = super().to_representation(instance)

        if not self._is_owner_or_staff(instance):
            for field in (
                "email",
                "last_activity_at",
                "last_login",
                "is_staff",
                "is_active",
            ):
                ret.pop(field, None)

        return ret


# ============================================================================
# Post Serializers
# ============================================================================


class PostListSerializer(serializers.HyperlinkedModelSerializer):
    """
    Serializer for post list operations (read-only).

    Used for GET /api/v1/posts/.
    Returns posts with truncated content (excerpt), author info, thumbnail, and stats.

    Fields:
        - url: Hyperlink to post detail endpoint
        - id: Post ID
        - author: Object with id, username, and URL
        - title: Post title
        - content_excerpt: Truncated content (max 200 chars with "...")
        - thumbnail: Thumbnail image URL
        - created_at, updated_at: Timestamps
        - likes: Hyperlink to likes filtered by this post
        - stats: Object with like_count and has_liked (for authenticated users)
    """

    url = serializers.HyperlinkedIdentityField(view_name="post-detail-api")
    author = serializers.SerializerMethodField()
    content_excerpt = serializers.SerializerMethodField()
    likes = serializers.SerializerMethodField()
    stats = serializers.SerializerMethodField()

    def get_author(self, obj):
        """Return author info with id, username, and URL."""
        request = self.context.get("request")
        return {
            "id": obj.author_id,
            "username": obj.author.username,
            "url": reverse(
                "user-detail-update-destroy-api",
                kwargs={"user_id_or_username": obj.author_id},
                request=request,
            ),
        }

    def get_content_excerpt(self, obj):
        """Return truncated content (max 200 chars with '...')."""
        if obj.content and len(obj.content) > 200:
            return obj.content[:200] + "..."
        return obj.content or ""

    def get_likes(self, obj):
        """Return hyperlink to likes filtered by this post."""
        request = self.context.get("request")
        return f"{reverse('like-list-api', request=request)}?post={obj.pk}"

    def get_stats(self, obj):
        """
        Return like statistics for the post.

        Includes:
            - like_count: Total number of likes
            - has_liked: Whether current user has liked (only for authenticated users)
        """
        request = self.context.get("request")
        stats = {"like_count": getattr(obj, "like_count", 0)}

        # Only include has_liked for authenticated users
        if request and request.user.is_authenticated:
            stats["has_liked"] = getattr(obj, "has_liked", False)

        return stats

    class Meta:
        model = Post
        fields = (
            "url",
            "id",
            "author",
            "title",
            "content_excerpt",
            "thumbnail",
            "created_at",
            "updated_at",
            "likes",
            "stats",
        )


class PostCreateSerializer(serializers.HyperlinkedModelSerializer):
    """
    Serializer for post create operations.

    Used for POST /api/v1/posts/.
    Author is automatically set from the authenticated user in the view.

    Fields:
        - url: Hyperlink to post detail endpoint (read-only)
        - id: Post ID (read-only)
        - author: Hyperlink to author's user detail (read-only, set automatically)
        - title: Post title (required)
        - content: Post content (required)
        - image: Post image file (optional)
        - created_at, updated_at: Read-only timestamps
        - published: Boolean flag (write-only, defaults to True)
        - likes: Hyperlink to likes filtered by this post (read-only)

    Note:
        Author is set in the view using perform_create(). Alternative approaches
        (commented below) could use HiddenField with CurrentUserDefault, but
        the current approach provides better control in the view layer.
    """

    url = serializers.HyperlinkedIdentityField(view_name="post-detail-api")
    published = serializers.BooleanField(
        write_only=True, required=False, default=True, initial=True
    )
    author = serializers.HyperlinkedRelatedField(
        read_only=True,
        view_name="user-detail-update-destroy-api",
        lookup_field="pk",
        lookup_url_kwarg="user_id_or_username",
    )
    likes = serializers.SerializerMethodField()

    def get_likes(self, obj):
        """Return hyperlink to likes filtered by this post."""
        request = self.context.get("request")
        return f"{reverse('like-list-api', request=request)}?post={obj.pk}"

    class Meta:
        model = Post
        fields = (
            "url",
            "id",
            "author",
            "title",
            "content",
            "image",
            "created_at",
            "updated_at",
            "published",
            "likes",
        )
        read_only_fields = ("url", "id", "author", "created_at", "updated_at")


class PostDetailSerializer(serializers.HyperlinkedModelSerializer):
    """
    Serializer for post detail, update, and delete operations.

    Used for GET/PUT/PATCH/DELETE /api/v1/posts/{id}/.
    Title and content are optional for partial updates.

    Fields:
        - url: Hyperlink to post detail endpoint
        - id: Post ID (read-only)
        - author: Object with id, username, and URL
        - title: Post title (optional for updates)
        - content: Post content (optional for updates)
        - image: Post image file (optional)
        - thumbnail: Thumbnail image URL (read-only)
        - created_at, updated_at: Read-only timestamps
        - published: Publication status (owner/admin only)
        - likes: Hyperlink to likes filtered by this post
        - stats: Object with likes_count and has_liked (for authenticated users)
    """

    url = serializers.HyperlinkedIdentityField(view_name="post-detail-api")
    author = serializers.SerializerMethodField()
    likes = serializers.SerializerMethodField()
    stats = serializers.SerializerMethodField()

    def _is_owner_or_staff(self, obj):
        """Check if request user is post owner or staff."""
        request = self.context.get("request")
        return (
            request
            and request.user
            and request.user.is_authenticated
            and (request.user.pk == obj.author_id or request.user.is_staff)
        )

    def get_author(self, obj):
        """Return author info with id, username, and URL."""
        request = self.context.get("request")
        return {
            "id": obj.author_id,
            "username": obj.author.username,
            "url": reverse(
                "user-detail-update-destroy-api",
                kwargs={"user_id_or_username": obj.author_id},
                request=request,
            ),
        }

    def get_likes(self, obj):
        """Return hyperlink to likes filtered by this post."""
        request = self.context.get("request")
        return f"{reverse('like-list-api', request=request)}?post={obj.pk}"

    def get_stats(self, obj):
        """
        Return like statistics for the post.

        Includes:
            - likes_count: Total number of likes
            - has_liked: Whether current user has liked (only for authenticated users)
        """
        request = self.context.get("request")
        stats = {"likes_count": getattr(obj, "likes_count", obj.likes.count())}

        # Only include has_liked for authenticated users
        if request and request.user.is_authenticated:
            stats["has_liked"] = getattr(obj, "has_liked", False)

        return stats

    class Meta:
        model = Post
        fields = (
            "url",
            "id",
            "author",
            "title",
            "content",
            "image",
            "thumbnail",
            "created_at",
            "updated_at",
            "published",
            "likes",
            "stats",
        )
        extra_kwargs = {
            "title": {"required": False},
            "content": {"required": False},
        }

    def to_representation(self, instance):
        """
        Conditionally hide published field for non-owner, non-staff users.

        The published field is only visible to:
            - Post owner
            - Staff users
        """
        ret = super().to_representation(instance)

        if not self._is_owner_or_staff(instance):
            ret.pop("published", None)

        return ret


# ============================================================================
# Like Serializers
# ============================================================================


class LikeByUserSerializer(serializers.HyperlinkedModelSerializer):
    """
    Serializer for likes filtered by user.

    Used for GET /api/v1/likes/?user={id} to show a user's likes.
    Returns likes with post title (truncated to 50 chars) and post URL.

    Fields:
        - url: Hyperlink to like detail endpoint
        - id: Like ID
        - created_at: Timestamp when like was created
        - post: Object with id, title (truncated), and URL
    """

    url = serializers.HyperlinkedIdentityField(view_name="like-detail-api")
    post = serializers.SerializerMethodField()

    def get_post(self, obj):
        """Return post info with id, truncated title, and URL."""
        request = self.context.get("request")
        title = obj.post.title
        if len(title) > 50:
            title = title[:50] + "..."
        return {
            "id": obj.post_id,
            "title": title,
            "url": reverse(
                "post-detail-api",
                kwargs={"pk": obj.post_id},
                request=request,
            ),
        }

    class Meta:
        model = Like
        fields = ("url", "id", "created_at", "post")


class LikeByPostSerializer(serializers.HyperlinkedModelSerializer):
    """
    Serializer for likes filtered by post.

    Used for GET /api/v1/likes/?post={id} to show a post's likes.
    Returns likes with username and user URL.

    Fields:
        - url: Hyperlink to like detail endpoint
        - id: Like ID
        - created_at: Timestamp when like was created
        - user: Object with id, username, and URL
    """

    url = serializers.HyperlinkedIdentityField(view_name="like-detail-api")
    user = serializers.SerializerMethodField()

    def get_user(self, obj):
        """Return user info with id, username, and URL."""
        request = self.context.get("request")
        return {
            "id": obj.user_id,
            "username": obj.user.username,
            "url": reverse(
                "user-detail-update-destroy-api",
                kwargs={"user_id_or_username": obj.user_id},
                request=request,
            ),
        }

    class Meta:
        model = Like
        fields = ("url", "id", "created_at", "user")


class LikeDetailSerializer(serializers.HyperlinkedModelSerializer):
    """
    Serializer for like detail view (read-only).

    Used for GET /api/v1/likes/{id}/ to retrieve a specific like instance.
    All fields are read-only as likes are created/destroyed via toggle endpoint.

    Fields:
        - url: Hyperlink to like detail endpoint
        - id: Like ID (read-only)
        - created_at: Timestamp when like was created (read-only)
        - user: Object with id, username, and URL
        - post: Object with id, title (truncated to 50 chars), and URL
    """

    url = serializers.HyperlinkedIdentityField(view_name="like-detail-api")
    user = serializers.SerializerMethodField()
    post = serializers.SerializerMethodField()

    def get_user(self, obj):
        """Return user info with id, username, and URL."""
        request = self.context.get("request")
        return {
            "id": obj.user_id,
            "username": obj.user.username,
            "url": reverse(
                "user-detail-update-destroy-api",
                kwargs={"user_id_or_username": obj.user_id},
                request=request,
            ),
        }

    def get_post(self, obj):
        """Return post info with id, truncated title, and URL."""
        request = self.context.get("request")
        title = obj.post.title
        if len(title) > 50:
            title = title[:50] + "..."
        return {
            "id": obj.post_id,
            "title": title,
            "url": reverse(
                "post-detail-api",
                kwargs={"pk": obj.post_id},
                request=request,
            ),
        }

    class Meta:
        model = Like
        fields = "url", "id", "created_at", "user", "post"


class LikeCreateDestroySerializer(serializers.HyperlinkedModelSerializer):
    """
    Serializer for toggling likes on posts.

    Input: {"post": <post_id>}
    Output (on create): Full like object with URLs

    Note: Accepts post ID for input but returns post URL in output
    for consistency with HyperlinkedModelSerializer pattern.
    """

    url = serializers.HyperlinkedIdentityField(view_name="like-detail-api")
    user = serializers.HyperlinkedRelatedField(
        read_only=True,
        view_name="user-detail-update-destroy-api",
        lookup_field="pk",
        lookup_url_kwarg="user_id_or_username",
    )
    post = serializers.PrimaryKeyRelatedField(queryset=Post.objects.all())

    class Meta:
        model = Like
        fields = ("url", "id", "created_at", "user", "post")

    def validate_post(self, value):
        """
        Validate that the post is published before allowing a like.

        Args:
            value: Post instance to validate

        Returns:
            Post: The validated post instance

        Raises:
            ValidationError: If the post is not published
        """
        if not value.published:
            raise serializers.ValidationError("Cannot like an unpublished post.")
        return value

    def to_representation(self, instance):
        """
        Convert post field from ID to hyperlinked URL in API response.

        This ensures the output follows HyperlinkedModelSerializer conventions
        even though we accept post ID as input for convenience.

        Args:
            instance: Like instance to serialize

        Returns:
            dict: Serialized representation with post as URL instead of ID
        """
        ret = super().to_representation(instance)
        ret["post"] = reverse(
            "post-detail-api",
            kwargs={"pk": instance.post_id},
            request=self.context["request"],
        )
        return ret


# ============================================================================
# Authentication & Token Serializers
# ============================================================================


class MyTokenRefreshSerializer(TokenRefreshSerializer):
    """
    Custom token refresh serializer with OutstandingToken tracking.

    The default SimpleJWT TokenRefreshSerializer doesn't add rotated refresh tokens
    to the OutstandingToken table, which breaks blacklist functionality. This
    serializer fixes that by creating an OutstandingToken record for each new
    refresh token issued during rotation.
    """

    def validate(self, attrs):
        """
        Validate and rotate tokens, tracking new refresh token in OutstandingToken.

        Args:
            attrs: Dictionary containing the refresh token string

        Returns:
            dict: Contains 'access' token and optionally 'refresh' token if rotation is enabled

        Process:
            1. Validates the provided refresh token
            2. Generates new access token
            3. If rotation is enabled:
               - Blacklists old refresh token (if blacklist app is installed)
               - Generates new refresh token with updated JTI, exp, and iat claims
               - Creates OutstandingToken record for proper blacklist tracking
        """
        refresh = self.token_class(attrs["refresh"])

        data = {"access": str(refresh.access_token)}

        if api_settings.ROTATE_REFRESH_TOKENS:
            if api_settings.BLACKLIST_AFTER_ROTATION:
                # Attempt to blacklist the given refresh token
                # If blacklist app not installed, `blacklist` method will not be present
                with suppress(AttributeError):
                    refresh.blacklist()

            refresh.set_jti()
            refresh.set_exp()
            refresh.set_iat()

            data["refresh"] = str(refresh)

            # Create OutstandingToken record for the new refresh token
            # This ensures proper blacklist tracking when token rotation is enabled
            user = CustomUser.objects.get(id=refresh["user_id"])
            jti = refresh[api_settings.JTI_CLAIM]
            exp = refresh["exp"]
            OutstandingToken.objects.create(
                user=user,
                jti=jti,
                token=str(refresh),
                created_at=refresh.current_time,
                expires_at=datetime_from_epoch(exp),
            )

        return data


class TokenRecoverySerializer(serializers.Serializer):
    """
    Serializer for password recovery token request.

    Used for POST /api/v1/auth/token/recovery/ to request a password reset token.
    Accepts an email address and triggers an email with a recovery link.

    Fields:
        - email: User's email address (required, max 200 characters)
    """

    email = serializers.EmailField(max_length=200)


class PasswordChangeSerializer(serializers.Serializer):
    """
    Serializer for authenticated password change.

    Used for POST /api/v1/auth/password/change/ to change password securely.
    Requires the current password for verification before allowing the change.

    Fields:
        - old_password: Current password (required, for verification)
        - new_password: New password (required, validated against Django validators)
        - new_password2: New password confirmation (required, must match new_password)
    """

    old_password = serializers.CharField(
        style={"input_type": "password"},
        write_only=True,
    )
    new_password = serializers.CharField(
        style={"input_type": "password"},
        write_only=True,
    )
    new_password2 = serializers.CharField(
        style={"input_type": "password"},
        write_only=True,
    )

    def validate_old_password(self, value):
        """
        Validate that old_password matches the current user's password.

        Args:
            value: The provided old password

        Returns:
            str: The validated old password

        Raises:
            ValidationError: If the old password is incorrect
        """
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, data):
        """
        Validate new password against Django validators and confirm match.

        Args:
            data: Dictionary containing old_password, new_password, new_password2

        Returns:
            dict: Validated data

        Raises:
            ValidationError: If passwords don't match or fail validation
        """
        if data["new_password"] != data["new_password2"]:
            raise serializers.ValidationError(
                {"new_password2": "New passwords must match."}
            )

        user = self.context["request"].user
        validate_password(password=data["new_password"], user=user)

        return data


class PasswordResetSerializer(serializers.Serializer):
    """
    Serializer for password reset (recovery flow).

    Used for POST /api/v1/auth/password/reset/ to reset password after receiving
    a recovery token via email. Does NOT require the old password since the user
    forgot it (that's why they're using recovery).

    Fields:
        - new_password: New password (required, validated against Django validators)
        - new_password2: New password confirmation (required, must match new_password)
    """

    new_password = serializers.CharField(
        style={"input_type": "password"},
        write_only=True,
    )
    new_password2 = serializers.CharField(
        style={"input_type": "password"},
        write_only=True,
    )

    def validate(self, data):
        """
        Validate new password against Django validators and confirm match.

        Args:
            data: Dictionary containing new_password, new_password2

        Returns:
            dict: Validated data

        Raises:
            ValidationError: If passwords don't match or fail validation
        """
        if data["new_password"] != data["new_password2"]:
            raise serializers.ValidationError(
                {"new_password2": "New passwords must match."}
            )

        user = self.context["request"].user
        validate_password(password=data["new_password"], user=user)

        return data


class UsernameChangeSerializer(serializers.Serializer):
    """
    Serializer for authenticated username change.

    Used for POST /api/v1/auth/username/change/ to change username securely.
    Requires the current password for verification before allowing the change.
    Enforces a 30-day cooldown between username changes.

    Fields:
        - password: Current password (required, for verification)
        - new_username: New username (required, validated for uniqueness and format)
    """

    password = serializers.CharField(
        style={"input_type": "password"},
        write_only=True,
    )
    new_username = serializers.CharField(max_length=150)

    # 30-day cooldown between username changes
    USERNAME_CHANGE_COOLDOWN_DAYS = 30

    def validate_password(self, value):
        """
        Validate that password matches the current user's password.

        Args:
            value: The provided password

        Returns:
            str: The validated password

        Raises:
            ValidationError: If the password is incorrect
        """
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Password is incorrect.")
        return value

    def validate_new_username(self, value):
        """
        Validate that new username is unique (case-insensitive) and properly formatted.

        Args:
            value: The proposed new username

        Returns:
            str: The validated username

        Raises:
            ValidationError: If username is taken or invalid format
        """
        user = self.context["request"].user

        # Check case-insensitive uniqueness (excluding current user)
        if (
            CustomUser.objects.filter(username__iexact=value)
            .exclude(pk=user.pk)
            .exists()
        ):
            raise serializers.ValidationError(
                "A user with that username already exists."
            )

        # Apply the custom username validator
        validator = MyUnicodeUsernameValidator()
        try:
            validator(value)
        except Exception as e:
            raise serializers.ValidationError(str(e)) from e

        return value

    def validate(self, data):
        """
        Validate that the 30-day cooldown has passed since last username change.

        Args:
            data: Dictionary containing password and new_username

        Returns:
            dict: Validated data

        Raises:
            ValidationError: If username was changed less than 30 days ago
        """
        user = self.context["request"].user

        if user.username_last_changed:
            cooldown_end = user.username_last_changed + timedelta(
                days=self.USERNAME_CHANGE_COOLDOWN_DAYS
            )
            if timezone.now() < cooldown_end:
                days_remaining = (cooldown_end - timezone.now()).days + 1
                raise serializers.ValidationError(
                    {
                        "new_username": f"You can only change your username once every "
                        f"{self.USERNAME_CHANGE_COOLDOWN_DAYS} days. "
                        f"Please wait {days_remaining} more day(s)."
                    }
                )

        return data


class EmailChangeSerializer(serializers.Serializer):
    """
    Serializer for initiating email change.

    Used for POST /api/v1/auth/email/change/ to request email change.
    Requires the current password for verification before allowing the change.
    Sends a verification email to the new address.

    Fields:
        - password: Current password (required, for verification)
        - new_email: New email address (required, must be unique and different from current)
    """

    password = serializers.CharField(
        style={"input_type": "password"},
        write_only=True,
    )
    new_email = serializers.EmailField(max_length=254)

    def validate_password(self, value):
        """
        Validate that password matches the current user's password.

        Args:
            value: The provided password

        Returns:
            str: The validated password

        Raises:
            ValidationError: If the password is incorrect
        """
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Password is incorrect.")
        return value

    def validate_new_email(self, value):
        """
        Validate that new email is unique (case-insensitive) and different from current.

        Args:
            value: The proposed new email

        Returns:
            str: The validated email (lowercased)

        Raises:
            ValidationError: If email is taken or same as current
        """
        user = self.context["request"].user
        normalized_email = value.lower()

        # Check if same as current email
        if user.email.lower() == normalized_email:
            raise serializers.ValidationError(
                "New email must be different from current email."
            )

        # Check case-insensitive uniqueness
        if CustomUser.objects.filter(email__iexact=normalized_email).exists():
            raise serializers.ValidationError("A user with that email already exists.")

        return normalized_email


class EmailVerifySerializer(serializers.Serializer):
    """
    Serializer for verifying email change token.

    Used for POST /api/v1/auth/email/verify/ to complete email change.
    Validates the token exists and is not expired.

    Fields:
        - token: UUID verification token (required)
    """

    token = serializers.CharField(max_length=36)

    def validate_token(self, value):
        """
        Validate that token exists and is not expired.

        Args:
            value: The verification token

        Returns:
            str: The validated token

        Raises:
            ValidationError: If token is invalid or expired
        """
        try:
            user = CustomUser.objects.get(email_verification_token=value)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("Invalid verification token.") from None

        if user.email_verification_expires < timezone.now():
            raise serializers.ValidationError("Verification token has expired.")

        # Store the user for later use in the view
        self.user = user
        return value
