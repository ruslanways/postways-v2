"""URL configuration for the diary application."""

from django.contrib.auth.views import LogoutView
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenVerifyView

from .views import (
    # Home
    HomeView,
    HomeViewLikeOrdered,
    # Auth (HTML)
    SignUp,
    Login,
    PasswordReset,
    CustomPasswordResetConfirmView,
    # Authors (HTML)
    AuthorListView,
    AuthorDetailView,
    UserDeleteView,
    # Posts (HTML)
    PostListView,
    PostCreateView,
    PostDetailView,
    PostUpdateView,
    PostDeleteView,
    # API root
    RootAPIView,
    # Users API
    UserListAPIView,
    UserDetailAPIView,
    TokenRecoveryAPIView,
    PasswordChangeAPIView,
    MyTokenObtainPairView,
    MyTokenRefreshView,
    # Posts API
    PostAPIView,
    PostDetailAPIView,
    # Likes API
    LikeAPIView,
    LikeBatchAPIView,
    LikeCreateDestroyAPIView,
    LikeDetailAPIView,
)

# ------------------------------------------------------------------------------
# HTML Views (Session Auth)
# ------------------------------------------------------------------------------
html_patterns = [
    # Home
    path("", HomeView.as_view(), name="home"),
    path("like_ordered/", HomeViewLikeOrdered.as_view(), name="home-like-ordering"),
    # Authors
    path("authors/", AuthorListView.as_view(), name="author-list"),
    path("authors/<sortfield>/", AuthorListView.as_view(), name="author-list"),
    path("author/<int:pk>/", AuthorDetailView.as_view(), name="author-detail"),
    path("author/<int:pk>/delete/", UserDeleteView.as_view(), name="user-delete"),
    # Posts
    path("posts/", PostListView.as_view(), name="post-list"),
    path("posts/add/", PostCreateView.as_view(), name="post-add"),
    path("posts/<int:pk>/", PostDetailView.as_view(), name="post-detail"),
    path("posts/<int:pk>/update/", PostUpdateView.as_view(), name="post-update"),
    path("posts/<int:pk>/delete/", PostDeleteView.as_view(), name="post-delete"),
]

# ------------------------------------------------------------------------------
# Auth Views (Session Auth)
# ------------------------------------------------------------------------------
auth_patterns = [
    path("signup/", SignUp.as_view(), name="signup"),
    path("login/", Login.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("password_reset/", PasswordReset.as_view(), name="password_reset"),
    path("reset/<uidb64>/<token>/", CustomPasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    # Include remaining Django auth views: password_change, password_change_done,
    # password_reset_done, password_reset_complete. Our custom views above take
    # precedence due to ordering.
    path("", include("django.contrib.auth.urls")),
]

# ------------------------------------------------------------------------------
# API Views (JWT Auth)
# ------------------------------------------------------------------------------
api_v1_patterns = [
    path("", RootAPIView.as_view(), name="root-api"),
    # Users
    path("users/", UserListAPIView.as_view(), name="user-list-create-api"),
    path("users/<int:pk>/", UserDetailAPIView.as_view(), name="user-detail-update-destroy-api"),
    # Auth
    path("auth/login/", TokenObtainPairView.as_view(), name="login-api"),
    path("auth/mylogin/", MyTokenObtainPairView.as_view(), name="my-login-api"),
    path("auth/token/verify/", TokenVerifyView.as_view(), name="token-verify-api"),
    path("auth/token/refresh/", MyTokenRefreshView.as_view(), name="token-refresh-api"),
    path("auth/token/recovery/", TokenRecoveryAPIView.as_view(), name="token-recovery-api"),
    path("auth/password/change/", PasswordChangeAPIView.as_view(), name="password-change-api"),
    # Posts
    path("posts/", PostAPIView.as_view(), name="post-list-create-api"),
    path("posts/<int:pk>/", PostDetailAPIView.as_view(), name="post-detail-api"),
    # Likes
    path("likes/", LikeAPIView.as_view(), name="like-list-api"),
    path("likes/<int:pk>/", LikeDetailAPIView.as_view(), name="like-detail-api"),
    path("likes/toggle/", LikeCreateDestroyAPIView.as_view(), name="like-toggle-api"),
    path("likes/batch/", LikeBatchAPIView.as_view(), name="like-batch-api"),
]

# ------------------------------------------------------------------------------
# URL Patterns
# ------------------------------------------------------------------------------
urlpatterns = (
    html_patterns
    + auth_patterns
    + [path("api/v1/", include(api_v1_patterns))]
)
