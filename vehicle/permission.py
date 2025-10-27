from rest_framework import permissions
from rest_framework.permissions import BasePermission

from franchise.models import Franchise
from manager.permissions import ManagerObjectPermission, IsFranchiseDirector, VehiclesAccess


class IsAdminOrReadOnly(ManagerObjectPermission):
    """
    Пользовательское разрешение, позволяющее создавать, редактировать и удалять объекты только администраторам.
    Доступ на чтение разрешен всем пользователям.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.role == 'admin'

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if super().has_object_permission(request, view, obj):
            return True


class IsAdminOrLessor(permissions.BasePermission):
    """
    Пользовательское разрешение, позволяющее создавать объекты только администраторам и арендодателям.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and (request.user.role == 'admin' or hasattr(request.user, 'lessor')) or hasattr(request.user, 'franchise')


class IsAdminOrOwner(BasePermission):
    """
    Пользовательское разрешение, позволяющее редактировать объект только администраторам или владельцам объекта.
    """
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'owner') and obj.owner == request.user:
            return True

        franchise = Franchise.objects.filter(director=request.user).first()
        if franchise and franchise == obj.owner.lessor.franchise:
            return True

        return False

