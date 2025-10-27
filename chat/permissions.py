from datetime import date

from rest_framework import permissions

from manager.permissions import ManagerObjectPermission, ChatsAccess
from vehicle.models import Auto, Bike, Ship, Helicopter, SpecialTechnic
from .models import Trip, Chat, Message


class IsAdminOrOwner(ManagerObjectPermission):
    """
    Разрешение позволяет доступ только пользователям с ролью 'admin' или владельцам ресурса.
    """

    def has_object_permission(self, request, view, obj):
        if super().has_object_permission(request, view, obj):
            return True
        # Проверка принадлежности ресурса пользователю
        if isinstance(obj, Trip):
            return obj.organizer == request.user
        elif isinstance(obj, Chat):
            return request.user in obj.participants.all()
        elif isinstance(obj, Message):
            return request.user in obj.chat.participants.all()

        return False


class UpdateTripPermission(permissions.BasePermission):
    """
    Права доступа для обновления поездок: пользователи с истекшими поездками могут обновлять только поле 'review'.
    """

    def has_object_permission(self, request, view, obj):
        today = date.today()
        if obj.end_date < today and request.method in ['PUT', 'PATCH']:
            allowed_fields = {'review'}
            return allowed_fields.issuperset(set(request.data.keys()))
        return True


class IsChatCreatorOrAdmin(ManagerObjectPermission):
    """
    Разрешение для разрешения доступа к действиям чата только создателю чата или администратору.
    """
    def has_permission(self, request, view):
        if request.method == 'POST':
            return True
        return True

    def has_object_permission(self, request, view, obj):
        if super().has_object_permission(request, view, obj):
            return True
        return obj.creator == request.user


# Новые permissions для менеджеров с типами доступа
class ChatsPermission(ChatsAccess):
    """Permission для доступа к чатам"""
    
    def has_object_permission(self, request, view, obj):
        if not self.has_permission(request, view):
            return False
        return ManagerObjectPermission().has_object_permission(request, view, obj)


class IsOrganizerAndEndDateToday(permissions.BasePermission):
    def has_permission(self, request, view):
        vehicle_id = request.data.get('Vehicle_id')
        vehicle_type = request.data.get('Vehicle_type')

        if not vehicle_id or not vehicle_type:
            return False

        model = {
            'Auto': Auto,
            'Bike': Bike,
            'Ship': Ship,
            'Helicopter': Helicopter,
            'SpecialTechnic': SpecialTechnic
        }.get(vehicle_type)

        if not model:
            return False

        try:
            trip = Trip.objects.get(vehicle__id=vehicle_id, vehicle__polymorphic_ctype__model=model.__name__.lower())
        except Trip.DoesNotExist:
            return False

        if trip.organizer == request.user and trip.end_date == date.today():
            return True

        return False

class ForChatPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role != 'manager'
