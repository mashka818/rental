from rest_framework import permissions

from franchise.models import Franchise
from manager.permissions import RentOrdersAccess, RentJournalAccess


class IsAdminManagerOrFranchiseOwner(permissions.BasePermission):
    def has_permission(self, request, view):
        return Franchise.objects.filter(director=request.user).exists()


# Новые permissions для менеджеров с типами доступа
class RentOrdersPermission(RentOrdersAccess):
    """Permission для доступа к аренде и заказам"""
    pass


class RentJournalPermission(RentJournalAccess):
    """Permission для доступа к журналу аренды"""
    pass
