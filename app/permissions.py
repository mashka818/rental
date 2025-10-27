from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from manager.permissions import ManagerObjectPermission


class IsManager(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.role == 'manager'


class IsAdminOrSelf(ManagerObjectPermission):
    """
    Пермишн для проверки прав администратора или принадлежности объекта пользователю.
    """

    def has_object_permission(self, request, view, obj):
        if super().has_object_permission(request, view, obj):
            return True
        if hasattr(request.user, 'renter') and obj.renter == request.user.renter:
            return True
        if hasattr(request.user, 'lessor') and obj.lessor == request.user.lessor:
            return True
        return False


class IsAdminOrSelfOrDirector(ManagerObjectPermission):
    """
    Пермишн для проверки прав администратора или принадлежности объекта пользователю.
    """
    def has_object_permission(self, request, view, obj):
        if super().has_object_permission(request, view, obj):
            return True
        if obj == request.user:
            return True
        if hasattr(request.user, 'franchise') and hasattr(obj, 'lessor') and obj.lessor.franchise.director == request.user:
            return True
        return False


class IsAdminOrOwner(ManagerObjectPermission):
    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
        if super().has_object_permission(request, view, obj):
            return True
        if hasattr(request.user, 'renter') and obj.renter == request.user.renter:
            return True
        return False


class HasRenter(BasePermission):
    """
    Проверяет, что у пользователя есть привязанный объект renter.
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if not hasattr(request.user, 'renter'):
            raise PermissionDenied("Пользователь не авторизован либо не является арендатором")
        return True