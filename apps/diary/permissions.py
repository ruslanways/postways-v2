"""
Custom permissions for the diary application API.

This module defines DRF permission classes that control access to API endpoints
based on user roles and object ownership.
"""

from typing import Any

from rest_framework import permissions


class OwnerOrAdminOrReadOnly(permissions.BasePermission):
    """
    Object-level permission that allows:
    - Read access (GET, HEAD, OPTIONS) to everyone
    - Write access (POST, PUT, PATCH, DELETE) only to the object's author or staff

    Used for resources like Post where anyone can view, but only the author
    or admin can modify.
    """

    def has_object_permission(self, request, view, obj: Any) -> bool:
        """Check if user has permission to access the object."""
        # Allow read-only access to everyone
        if request.method in permissions.SAFE_METHODS:
            return True
        # Write access only for author or staff
        return obj.author == request.user or request.user.is_staff


class ReadForAdminCreateForAnonymous(permissions.BasePermission):
    """
    View-level permission that allows:
    - POST requests from anonymous users
    - All other requests only from staff

    Used for endpoints like user registration where anonymous users can create
    accounts, but only staff can view or modify user data.
    """

    def has_permission(self, request, view) -> bool:
        """Check if user has permission to access the view."""
        if request.method == "OPTIONS":
            return True
        if request.method == "POST":
            return request.user.is_anonymous
        return request.user.is_staff


class OwnerOrAdmin(permissions.BasePermission):
    """
    Object-level permission that allows access only to:
    - The object itself (when obj is a user object matching request.user)
    - Staff users

    Used for user-related endpoints where users can only access their own data,
    or staff can access any user's data.
    """

    def has_object_permission(self, request, view, obj: Any) -> bool:
        """Check if user has permission to access the object."""
        # For user objects, check if obj is the same as request.user
        # For other objects, this would need to be adapted based on the model
        return obj == request.user or request.user.is_staff


class AuthenticatedReadOwnerOrAdminWrite(permissions.BasePermission):
    """
    Permission that allows:
    - Read access (GET, HEAD, OPTIONS) to authenticated users only
    - Write access (DELETE) only to the object owner or staff

    Used for user detail endpoints where any authenticated user can view profiles,
    but only the user themselves or staff can delete the account.
    """

    def has_permission(self, request, view) -> bool:
        """Check if user is authenticated."""
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj: Any) -> bool:
        """Check if user has permission to access the object."""
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj == request.user or request.user.is_staff
