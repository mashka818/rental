from rest_framework import permissions

from manager.permissions import ManagerObjectPermission


class IsOwnerOrAdminOrManager(ManagerObjectPermission):
    """
    Разрешение для изменения/удаления отзыва только владельцем отзыва или пользователями с ролью 'admin' или 'manager'.
    """
    def has_object_permission(self, request, view, obj):
        if super().has_object_permission(request, view, obj):
            return True
        if request.user == obj.user:
            return True
        return False


class IsRenterOrAdminOrManager(permissions.BasePermission):
    """
    Разрешение для добавления/редактирования ответа только арендатором или пользователями с ролью 'admin' или 'manager'.
    """
    def has_object_permission(self, request, view, obj):
        if super().has_object_permission(request, view, obj):
            return True
        if request.user == obj.renter.user:
            return True
        return False
