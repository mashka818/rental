from rest_framework import permissions
from rest_framework.permissions import BasePermission

from influencer.models import Influencer
from manager.permissions import ManagerObjectPermission, PartnershipAccess


class IsAdminOrManager(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in ['GET', 'POST', 'LIST']:
            return request.user.is_authenticated and (request.user.role == 'admin' or request.user.role == 'manager')
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class IsAdminOrInfluencer(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (request.user.role == 'admin' or hasattr(request.user, 'influencer'))

    def has_object_permission(self, request, view, obj):
        if request.user.role == 'admin':
            return True
        if hasattr(request.user, 'influencer'):
            return obj == request.user.influencer
        return False


class IsAdminOrManagerForRequest(ManagerObjectPermission):
    def has_permission(self, request, view):
        if super().has_permission(request, view):
            return True
        return request.user.is_authenticated and request.user.role in ['admin', 'manager']


class IsAdminOrOwner(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.user.role == 'admin':
            return True
        if hasattr(obj, 'influencer'):
            return obj.influencer.user == request.user
        return False


class PartnershipPermission(PartnershipAccess):
    """Permission для доступа к партнерской программе"""
    
    def has_object_permission(self, request, view, obj):
        if self.has_permission(request, view):
            return True
        return False
