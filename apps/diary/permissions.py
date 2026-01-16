from rest_framework import permissions

class OwnerOrAdminOrReadOnly(permissions.BasePermission):
    """
    Object level permission
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.method in ('PUT', 'PATCH', 'DELETE'):
            return obj.author == request.user or request.user.is_staff


class ReadForAdminCreateForAnonymous(permissions.BasePermission):
    """
    View level permission
    """
    def has_permission(self, request, view):
        return request.user.is_staff if request.method not in ('POST',) else request.user.is_anonymous


class OwnerOrAdmin(permissions.BasePermission):
    """
    Object level permission
    """
    def has_object_permission(self, request, view, obj):
        return obj == request.user or request.user.is_staff
