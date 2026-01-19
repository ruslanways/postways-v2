"""
Serializers for the diary application REST API.

This module contains serializers for:
    - User management (registration, profile updates, profile details)
    - Post CRUD operations (list, detail views)
    - Like tracking and analytics (create/destroy, detail views, analytics)
    - JWT token refresh with proper blacklist tracking

All serializers follow DRF conventions and use HyperlinkedModelSerializer
for RESTful URL-based relationships where appropriate.
"""
import copy
from rest_framework import serializers
from .models import CustomUser, Like, Post
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.utils import datetime_from_epoch
from rest_framework.reverse import reverse


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
                try:
                    # Attempt to blacklist the given refresh token
                    refresh.blacklist()
                except AttributeError:
                    # If blacklist app not installed, `blacklist` method will
                    # not be present
                    pass

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


class UserSerializer(serializers.HyperlinkedModelSerializer):
    """
    Serializer for user registration.

    Used for creating new user accounts via POST /api/v1/users/.
    Requires both 'password' and 'password2' fields to match for validation.
    Automatically hashes passwords using Django's password hashing.

    Fields:
        - url: Hyperlink to user detail endpoint
        - id: User ID (read-only)
        - username: Required for registration
        - email: Required for registration
        - password: Write-only, validated against Django password validators
        - password2: Write-only, must match password
        - last_request, last_login, date_joined: Read-only timestamps
        - is_staff, is_active: Read-only admin flags
    """

    url = serializers.HyperlinkedIdentityField(
        view_name="user-detail-update-destroy-api"
    )
    password2 = serializers.CharField(style={"input_type": "password"}, write_only=True)

    class Meta:
        model = CustomUser
        fields = (
            "url",
            "id",
            "username",
            "email",
            "last_request",
            "last_login",
            "date_joined",
            "is_staff",
            "is_active",
            "password",
            "password2",
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
            "last_request",
            "last_login",
            "date_joined",
            "is_staff",
        )

    def validate(self, data):
        """
        Validate password using Django's password validators.

        Args:
            data: Dictionary containing all serializer fields including password

        Returns:
            dict: Validated data

        Raises:
            ValidationError: If password doesn't meet Django's password requirements
        """
        data_without_password2 = copy.deepcopy(data)
        del data_without_password2["password2"]
        validate_password(
            password=data.get("password"), user=CustomUser(**data_without_password2)
        )
        return data

    def create(self, validated_data):
        """
        Create a new user account with hashed password.

        Args:
            validated_data: Dictionary containing validated user data

        Returns:
            CustomUser: The newly created user instance

        Raises:
            ValidationError: If passwords don't match
        """
        password = validated_data["password"]
        password2 = validated_data["password2"]
        if password != password2:
            raise serializers.ValidationError({"Password": "Passwords must match."})
        instance = self.Meta.model._default_manager.create_user(
            email=validated_data["email"],
            username=validated_data["username"],
            password=validated_data["password"],
        )
        return instance


class UserDetailSerializer(serializers.HyperlinkedModelSerializer):
    """
    Serializer for user detail, update, and delete operations.

    Used for GET/PUT/PATCH/DELETE /api/v1/users/{id}/.
    Includes related posts and likes as hyperlinked relationships.
    All fields except password are optional for partial updates.

    Fields:
        - url: Hyperlink to user detail endpoint
        - id: User ID (read-only)
        - username: Optional for updates
        - email: Optional for updates
        - password: Optional for updates, write-only, validated if provided
        - post_set: Hyperlinked list of all posts by this user (read-only)
        - like_set: Hyperlinked list of all likes by this user (read-only)
        - last_request, last_login, date_joined: Read-only timestamps
        - is_staff, is_active: Read-only admin flags
    """

    url = serializers.HyperlinkedIdentityField(
        view_name="user-detail-update-destroy-api"
    )
    # Related posts and likes shown as hyperlinked relationships
    post_set = serializers.HyperlinkedRelatedField(
        many=True, read_only=True, view_name="post-detail-api"
    )
    like_set = serializers.HyperlinkedRelatedField(
        many=True, read_only=True, view_name="like-detail-api"
    )

    class Meta:
        model = CustomUser
        fields = (
            "url",
            "id",
            "username",
            "email",
            "last_request",
            "last_login",
            "date_joined",
            "is_staff",
            "is_active",
            "post_set",
            "like_set",
            "password",
        )
        extra_kwargs = {
            "username": {"required": False},
            "email": {"required": False},
            "password": {"required": False, "write_only": True},
        }
        read_only_fields = (
            "id",
            "is_active",
            "last_request",
            "last_login",
            "date_joined",
            "is_staff",
        )

    def validate(self, data):
        """
        Validate password if provided during update.

        Args:
            data: Dictionary containing fields to update

        Returns:
            dict: Validated data

        Raises:
            ValidationError: If password doesn't meet Django's password requirements

        Note:
            Uses existing user instance from context if password is not provided,
            or creates a temporary user object for password validation if password is provided.
        """
        user = (
            CustomUser(**data)
            if data.get("password", False) and len(data) > 1
            else self.context["obj"]
        )
        if data.get("password"):
            validate_password(password=data.get("password"), user=user)
        return data

    def update(self, instance, validated_data):
        """
        Update user instance with provided data.

        Args:
            instance: The existing CustomUser instance to update
            validated_data: Dictionary containing validated fields to update

        Returns:
            CustomUser: The updated user instance

        Note:
            Only updates fields that are provided. Password is hashed using
            Django's set_password() method if provided.
        """
        instance.username = validated_data.get("username", instance.username)
        instance.email = validated_data.get("email", instance.email)
        password_new = validated_data.get("password")
        if password_new:
            instance.set_password(password_new)
        instance.save()
        return instance


class TokenRecoverySerializer(serializers.Serializer):
    """
    Serializer for password recovery token request.

    Used for POST /api/v1/auth/token/recovery/ to request a password reset token.
    Accepts an email address and triggers an email with a recovery link.

    Fields:
        - email: User's email address (required, max 200 characters)
    """

    email = serializers.EmailField(max_length=200)


class PostSerializer(serializers.HyperlinkedModelSerializer):
    """
    Serializer for post list and create operations.

    Used for GET/POST /api/v1/posts/.
    Author is automatically set from the authenticated user in the view.
    Includes like count as a read-only field.

    Fields:
        - url: Hyperlink to post detail endpoint
        - id: Post ID (read-only)
        - author: Hyperlink to author's user detail (read-only, set automatically)
        - title: Post title (required)
        - content: Post content (required)
        - image: Post image file (optional)
        - created, updated: Read-only timestamps
        - published: Boolean flag (write-only, defaults to True)
        - likes: Total number of likes (read-only, computed field)

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
        read_only=True, view_name="user-detail-update-destroy-api"
    )
    # Alternative approach to associate post with current user:
    # author = serializers.HiddenField(write_only=True, default=serializers.CurrentUserDefault())
    # author_id = serializers.IntegerField(read_only=True, default=serializers.CurrentUserDefault())
    likes = serializers.IntegerField(read_only=True)

    class Meta:
        model = Post
        fields = (
            "id",
            "url",
            "author",
            "title",
            "content",
            "image",
            "created",
            "updated",
            "published",
            "likes",
        )


class PostDetailSerializer(serializers.HyperlinkedModelSerializer):
    """
    Serializer for post detail, update, and delete operations.

    Used for GET/PUT/PATCH/DELETE /api/v1/posts/{id}/.
    Includes all likes as hyperlinked relationships.
    Title and content are optional for partial updates.

    Fields:
        - url: Hyperlink to post detail endpoint
        - id: Post ID (read-only)
        - author: Hyperlink to author's user detail (read-only)
        - title: Post title (optional for updates)
        - content: Post content (optional for updates)
        - image: Post image file (optional)
        - created, updated: Read-only timestamps
        - published: Publication status
        - like_set: Hyperlinked list of all likes on this post (read-only)
    """

    url = serializers.HyperlinkedIdentityField(view_name="post-detail-api")
    author = serializers.HyperlinkedRelatedField(
        read_only=True, view_name="user-detail-update-destroy-api"
    )
    like_set = serializers.HyperlinkedRelatedField(
        many=True, read_only=True, view_name="like-detail-api"
    )

    class Meta:
        model = Post
        fields = (
            "id",
            "url",
            "author",
            "title",
            "content",
            "image",
            "created",
            "updated",
            "published",
            "like_set",
        )
        extra_kwargs = {
            "title": {"required": False},
            "content": {"required": False},
        }


class LikeSerializer(serializers.Serializer):
    """
    Serializer for like analytics/aggregation data.

    Used for analytics endpoints that return aggregated like counts by date.
    This is a simple serializer for read-only aggregated data, not a model serializer.

    Fields:
        - created__date: Date of the aggregation (from Like.created field)
        - likes: Count of likes on that date
    """

    created__date = serializers.DateField()
    likes = serializers.IntegerField()


class LikeDetailSerializer(serializers.HyperlinkedModelSerializer):
    """
    Serializer for like detail view (read-only).

    Used for GET /api/v1/likes/{id}/ to retrieve a specific like instance.
    All fields are read-only as likes are created/destroyed via toggle endpoint.

    Fields:
        - url: Hyperlink to like detail endpoint
        - id: Like ID (read-only)
        - created: Timestamp when like was created (read-only)
        - user: Hyperlink to user who created the like (read-only)
        - post: Hyperlink to the liked post (read-only)
    """

    url = serializers.HyperlinkedIdentityField(view_name="like-detail-api")
    user = serializers.HyperlinkedRelatedField(
        read_only=True, view_name="user-detail-update-destroy-api"
    )
    post = serializers.HyperlinkedRelatedField(
       read_only=True, view_name="post-detail-api"
    )

    class Meta:
        model = Like
        fields = "url", "id", "created", "user", "post"


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
        read_only=True, view_name="user-detail-update-destroy-api"
    )
    post = serializers.PrimaryKeyRelatedField(queryset=Post.objects.all())

    class Meta:
        model = Like
        fields = ("url", "id", "created", "user", "post")

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
