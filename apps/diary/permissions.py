from rest_framework import permissions

class OwnerOrAdminOrReadOnly(permissions.BasePermission):
    """
    Object level permission
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.author == request.user or request.user.is_staff


class ReadForAdminCreateForAnonymous(permissions.BasePermission):
    """
    View level permission
    """
    def has_permission(self, request, view):
        if request.method == 'POST':
            return request.user.is_anonymous
        return request.user.is_staff


class OwnerOrAdmin(permissions.BasePermission):
    """
    Object level permission
    """
    def has_object_permission(self, request, view, obj):
        return obj == request.user or request.user.is_staff
