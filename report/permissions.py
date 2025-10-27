from rest_framework import permissions

from manager.permissions import ReportsAccess


class IsAdminRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['admin', 'manager']


# Новые permissions для менеджеров с типами доступа
class ReportsPermission(ReportsAccess):
    """Permission для доступа к отчетам"""
    pass
