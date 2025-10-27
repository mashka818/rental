from rest_framework.permissions import BasePermission

from manager.permissions import ManagerObjectPermission


class IsAdminOrOwner(ManagerObjectPermission):
    """
    Пользовательское разрешение, позволяющее редактировать объект только администраторам или владельцам объекта.
    """
    def has_object_permission(self, request, view, obj):
        if super().has_object_permission(request, view, obj):
            return True
        return obj.user == request.user


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.role == 'admin' or request.user.role == 'manager'


class IsAdminOrManager(BasePermission):
    """
    Разрешение только для пользователей с ролями 'admin' или 'manager'.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            hasattr(request.user, 'role') and
            request.user.role in ['admin', 'manager']
        )
