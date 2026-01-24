"""
Views package for the diary application.

This package contains two modules:
    - html: Traditional Django class-based views for HTML rendering (session auth)
    - api: Django REST Framework views for the REST API (JWT auth)

All views are re-exported here for backward compatibility.
"""

from .api import (
    EmailChangeAPIView,
    EmailVerifyAPIView,
    LikeAPIView,
    LikeBatchAPIView,
    LikeCreateDestroyAPIView,
    LikeDetailAPIView,
    MyTokenObtainPairView,
    MyTokenRefreshView,
    PasswordChangeAPIView,
    PostAPIView,
    PostDetailAPIView,
    RootAPIView,
    TokenRecoveryAPIView,
    UserDetailAPIView,
    UserListAPIView,
    UsernameChangeAPIView,
    error_400,
    error_403,
    error_404,
)
from .html import (
    AuthorDetailView,
    AuthorListView,
    CustomPasswordChangeView,
    CustomPasswordResetConfirmView,
    EmailChangeView,
    EmailVerifyView,
    HomeView,
    HomeViewLikeOrdered,
    Login,
    PasswordReset,
    PostCreateView,
    PostDeleteView,
    PostDetailView,
    PostListView,
    PostOwnerOrStaffMixin,
    PostUpdateView,
    SignUp,
    StaffRequiredMixin,
    UserDeleteView,
    UsernameChangeView,
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
