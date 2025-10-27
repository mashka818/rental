from rest_framework.permissions import BasePermission

from app.models import Lessor
from manager.permissions import ManagerObjectPermission, LessorsAccess, DepartmentsAccess


class IsOwnerOrAdmin(ManagerObjectPermission):
    def has_object_permission(self, request, view, obj):
        if super().has_object_permission(request, view, obj):
            return True
        return request.user == obj.owner

    def has_permission(self, request, view):
        if view.action in ['list', 'retrieve']:
            return request.user and request.user.is_authenticated
        return True


class IsOwnerOrAdminForGet(ManagerObjectPermission):
    def has_object_permission(self, request, view, obj):
        if super().has_object_permission(request, view, obj):
            return True
        if request.method not in ['GET']:
            return request.user == obj.owner
        if hasattr(obj, 'franchise'):
            if obj.franchise and request.user == obj.franchise.director:
                return True
        return request.user == obj.owner

    def has_permission(self, request, view):
        if request.user.role == 'admin':
            return True
        return super().has_permission(request, view)


class IsDirectorOrAdminForGet(ManagerObjectPermission):
    def has_object_permission(self, request, view, obj):
        if super().has_object_permission(request, view, obj):
            return True
        return request.user == obj.director


class IsAdminOrManager(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin' or request.user.role == 'manager'


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'


class IsAdminOrFranchiseOwner(ManagerObjectPermission):
    def has_permission(self, request, view):
        if request.user.role in ['admin', 'manager']:
            return True
        if request.method == 'POST':
            return hasattr(request.user, 'franchise')
        return True

    def has_object_permission(self, request, view, obj):
        if super().has_object_permission(request, view, obj):
            return True
        if hasattr(request.user, 'franchise'):
            return obj.franchise == request.user.franchise
        if hasattr(request.user, 'lessor'):
            return obj.lessor == request.user.lessor
        return False


class IsLessorOrFranchiseDirector(ManagerObjectPermission):
    def has_object_permission(self, request, view, obj):
        if super().has_object_permission(request, view, obj):
            return True
        if not hasattr(obj, 'franchise') or not hasattr(obj, 'user'):
            return False
        if obj.user == request.user:
            return True
        if obj.franchise and obj.franchise.director == request.user:
            return True
        return False


class IsAdminManagerOrLessorOrFranchiseDirector(BasePermission):
    def has_permission(self, request, view):
        if request.user.role in ['admin', 'manager']:
            return True

        lessor_id = view.kwargs.get('lessor_id')
        try:
            lessor = Lessor.objects.get(id=lessor_id)
        except Lessor.DoesNotExist:
            return False
        if request.user == lessor.user:
            return True
        if request.user == lessor.franchise.director:
            return True
        return False


class LessorsPermission(LessorsAccess):
    """Permission для доступа к арендодателям"""
    
    def has_object_permission(self, request, view, obj):
        if not self.has_permission(request, view):
            return False
        return ManagerObjectPermission().has_object_permission(request, view, obj)


class DepartmentsPermission(DepartmentsAccess):
    """Permission для доступа к подразделениям"""
    
    def has_object_permission(self, request, view, obj):
        if not self.has_permission(request, view):
            return False
        return ManagerObjectPermission().has_object_permission(request, view, obj)
