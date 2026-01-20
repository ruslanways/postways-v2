"""
Views package for the diary application.

This package contains two modules:
    - html: Traditional Django class-based views for HTML rendering (session auth)
    - api: Django REST Framework views for the REST API (JWT auth)

All views are re-exported here for backward compatibility.
"""

from .html import (
    HomeView,
    HomeViewLikeOrdered,
    SignUp,
    Login,
    PasswordReset,
    CustomPasswordResetConfirmView,
    CustomPasswordChangeView,
    UsernameChangeView,
    EmailChangeView,
    EmailVerifyView,
    StaffRequiredMixin,
    AuthorListView,
    AuthorDetailView,
    PostListView,
    PostCreateView,
    PostDetailView,
    PostOwnerOrStaffMixin,
    PostUpdateView,
    PostDeleteView,
    UserDeleteView,
)

from .api import (
    UserListAPIView,
    UserDetailAPIView,
    PostAPIView,
    PostDetailAPIView,
    LikeAPIView,
    LikeDetailAPIView,
    LikeCreateDestroyAPIView,
    LikeBatchAPIView,
    MyTokenRefreshView,
    TokenRecoveryAPIView,
    PasswordChangeAPIView,
    UsernameChangeAPIView,
    EmailChangeAPIView,
    EmailVerifyAPIView,
    MyTokenObtainPairView,
    RootAPIView,
    error_400,
    error_403,
    error_404,
)

__all__ = [
    # HTML views
    "HomeView",
    "HomeViewLikeOrdered",
    "SignUp",
    "Login",
    "PasswordReset",
    "CustomPasswordResetConfirmView",
    "CustomPasswordChangeView",
    "UsernameChangeView",
    "EmailChangeView",
    "EmailVerifyView",
    "StaffRequiredMixin",
    "AuthorListView",
    "AuthorDetailView",
    "PostListView",
    "PostCreateView",
    "PostDetailView",
    "PostOwnerOrStaffMixin",
    "PostUpdateView",
    "PostDeleteView",
    "UserDeleteView",
    # API views
    "UserListAPIView",
    "UserDetailAPIView",
    "PostAPIView",
    "PostDetailAPIView",
    "LikeAPIView",
    "LikeDetailAPIView",
    "LikeCreateDestroyAPIView",
    "LikeBatchAPIView",
    "MyTokenRefreshView",
    "TokenRecoveryAPIView",
    "PasswordChangeAPIView",
    "UsernameChangeAPIView",
    "EmailChangeAPIView",
    "EmailVerifyAPIView",
    "MyTokenObtainPairView",
    "RootAPIView",
    # Error handlers
    "error_400",
    "error_403",
    "error_404",
]
