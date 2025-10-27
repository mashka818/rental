from rest_framework.permissions import SAFE_METHODS, BasePermission

from feedback.models import Feedback


class PermissionVehicle(BasePermission):
    """ Разрешение для жалоб на транспорт. """
    def has_permission(self, request, view):
        if view.action in ['destroy', 'update']:
            complaint = view.get_object()
            if request.user == complaint.user or request.user.role in ['administrator', 'manager']:
                return True
            return False
        return True
