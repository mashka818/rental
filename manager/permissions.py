import logging

from django.contrib.contenttypes.models import ContentType
from rest_framework.permissions import BasePermission, SAFE_METHODS

from franchise.models import Franchise
from manager.models import Manager

logger = logging.getLogger('payment')


class HasAccessType(BasePermission):
    """
    Проверяет, есть ли у менеджера доступ к определенному типу ресурсов.
    Используется как базовый класс для других permissions.
    """
    access_type = None

    METHOD_PERMISSION_MAP = {
        'GET': 'read',
        'HEAD': 'read',
        'OPTIONS': 'read',
        'POST': 'edit',
        'PUT': 'edit',
        'PATCH': 'edit',
        'DELETE': 'delete',
    }

    ACTION_PERMISSION_MAP = {
        'list': 'read',
        'retrieve': 'read',
        'create': 'edit',
        'update': 'edit',
        'partial_update': 'edit',
        'destroy': 'delete',
    }

    def has_permission(self, request, view):
        logger.info(f"Checking has_permission for user: {request.user}, role: {getattr(request.user, 'role', None)}")
        logger.info(f"Access type: {self.access_type}, Method: {request.method}")

        if not request.user.is_authenticated:
            logger.warning("User is not authenticated")
            return False

        if request.user.role == 'admin':
            logger.info("User is admin, granting access")
            return True

        if not hasattr(request.user, 'manager') or not request.user.manager:
            logger.warning(f"User {request.user} has no manager attribute or manager is None")
            return False

        manager = request.user.manager
        logger.info(f"Manager: {manager}, Manager ID: {manager.id}")

        if not self.access_type:
            logger.info("No access_type specified, granting access")
            return True

        required_permission = self._get_required_permission(request, view)
        logger.info(f"Required permission: {required_permission}")

        if not required_permission:
            logger.warning("Could not determine required permission")
            return False

        # Проверяем доступные типы доступа у менеджера
        available_access_types = manager.access_types.all()
        logger.info(f"Available access types: {[f'{at.name}:{at.permission}' for at in available_access_types]}")

        has_access = manager.access_types.filter(
            name=self.access_type,
            permission=required_permission
        ).exists()

        logger.info(f"Has access result: {has_access}")
        return has_access

    def _get_required_permission(self, request, view):
        """Определяет требуемый тип разрешения на основе метода или действия"""
        if hasattr(view, 'action') and view.action:
            permission = self.ACTION_PERMISSION_MAP.get(view.action)
            if permission:
                logger.info(f"Permission from action {view.action}: {permission}")
                return permission

        permission = self.METHOD_PERMISSION_MAP.get(request.method)
        logger.info(f"Permission from method {request.method}: {permission}")
        return permission


class VehiclesAccess(HasAccessType):
    """Доступ к арендодателям"""
    access_type = 'vehicles'


class LessorsAccess(HasAccessType):
    """Доступ к арендодателям"""
    access_type = 'lessors'


class DepartmentsAccess(HasAccessType):
    """Доступ к подразделениям"""
    access_type = 'departments'


class PartnershipAccess(HasAccessType):
    """Доступ к партнерской программе"""
    access_type = 'partnership'


class StaffAccess(HasAccessType):
    """Доступ к персоналу"""
    access_type = 'staff'


class RentOrdersAccess(HasAccessType):
    """Доступ к аренде и заказам"""
    access_type = 'rent_orders'


class RentJournalAccess(HasAccessType):
    """Доступ к журналу аренды"""
    access_type = 'rent_journal'


class ChatsAccess(HasAccessType):
    """Доступ к чатам"""
    access_type = 'chats'


class ReportsAccess(HasAccessType):
    """Доступ к отчетам"""
    access_type = 'reports'


class IsFranchiseDirector(BasePermission):
    """
    Разрешает доступ директору франшизы ко всем объектам, относящимся к его франшизе.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False

        # Получаем франшизу пользователя
        franchise = Franchise.objects.filter(director=request.user).first()
        if not franchise:
            return False

        # Проверяем, принадлежит ли объект этой франшизе
        return self._is_object_in_franchise(franchise, obj)

    def _is_object_in_franchise(self, franchise, obj):
        """
        Проверяет, принадлежит ли объект указанной франшизе.
        """
        model_checks = {
            'auto': lambda obj: obj.owner.lessor.franchise,
            'bike': lambda obj: obj.owner.lessor.franchise,
            'ship': lambda obj: obj.owner.lessor.franchise,
            'helicopter': lambda obj: obj.owner.lessor.franchise,
            'specialtechnic': lambda obj: obj.owner.lessor.franchise,
            'vehicle': lambda obj: obj.owner.lessor.franchise,
            'lessor': lambda obj: obj.franchise,
            'user': lambda obj: obj.lessor.franchise,
            'chat': lambda obj: obj.request_rent.vehicle.owner.lessor.franchise,
            'feedback': lambda obj: obj.vehicle.owner.lessor.franchise,
            'requestrent': lambda obj: obj.vehicle.owner.lessor.franchise,
            'trip': lambda obj: obj.vehicle.owner.lessor.franchise,
            'franchise': lambda obj: obj,
            'complaint': lambda obj: obj.vehicle.owner.lessor.franchise,
            'complaintforfeedback': lambda obj: obj.feedback.vehicle.owner.lessor.franchise
        }

        model_name = obj._meta.model_name.lower()
        check_function = model_checks.get(model_name)

        return check_function(obj) == franchise if check_function else False


class UniversalPermission(BasePermission):
    """
    Универсальный пермишн для проверки прав доступа менеджеров и директоров франшизы.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False

        if request.user.role == 'admin':
            return True

        # Получаем франшизу пользователя, если он является директором
        franchise = Franchise.objects.filter(director=request.user).first()

        if not franchise:
            logger.warning(f"User {request.user} is not a director of any franchise")

        # Если пользователь — директор франшизы, проверяем, принадлежит ли объект его франшизе
        if franchise and self._is_object_in_franchise(franchise, obj):
            logger.info(f"User {request.user} is a director and has access to {obj}")
            return True

        # Проверка, является ли пользователь менеджером
        if request.user.role != 'manager' or not hasattr(request.user, 'manager'):
            return False

        manager = request.user.manager
        if not manager or not manager.city:
            return False

        logger.info(f"Checking permissions for manager {manager} on {obj}")

        # Проверка принадлежности объекта городу менеджера (через франшизу)
        return self._is_object_in_manager_city(manager.city, obj)

    def _is_object_in_franchise(self, franchise, obj):
        """
        Проверяет, принадлежит ли объект указанной франшизе.
        """
        if not obj:
            return False

        model_name = ContentType.objects.get_for_model(obj).model.lower()

        model_checks = {
            'auto': lambda obj: getattr(obj.owner, 'lessor', None) and obj.owner.lessor.franchise,
            'bike': lambda obj: getattr(obj.owner, 'lessor', None) and obj.owner.lessor.franchise,
            'ship': lambda obj: getattr(obj.owner, 'lessor', None) and obj.owner.lessor.franchise,
            'helicopter': lambda obj: getattr(obj.owner, 'lessor', None) and obj.owner.lessor.franchise,
            'specialtechnic': lambda obj: getattr(obj.owner, 'lessor', None) and obj.owner.lessor.franchise,
            'vehicle': lambda obj: getattr(obj.owner, 'lessor', None) and obj.owner.lessor.franchise,
            'lessor': lambda obj: obj.franchise,
            'user': lambda obj: getattr(obj, 'lessor', None) and obj.lessor.franchise,
            'chat': lambda obj: getattr(obj.request_rent.vehicle.owner, 'lessor',
                                        None) and obj.request_rent.vehicle.owner.lessor.franchise,
            'feedback': lambda obj: getattr(obj.vehicle.owner, 'lessor', None) and obj.vehicle.owner.lessor.franchise,
            'requestrent': lambda obj: getattr(obj.vehicle.owner, 'lessor',
                                               None) and obj.vehicle.owner.lessor.franchise,
            'trip': lambda obj: getattr(obj.vehicle.owner, 'lessor', None) and obj.vehicle.owner.lessor.franchise,
            'franchise': lambda obj: obj,
            'complaint': lambda obj: getattr(obj.vehicle.owner, 'lessor', None) and obj.vehicle.owner.lessor.franchise,
            'complaintforfeedback': lambda obj: getattr(obj.feedback.vehicle.owner, 'lessor',
                                                        None) and obj.feedback.vehicle.owner.lessor.franchise,
        }

        check_function = model_checks.get(model_name)

        if not check_function:
            logger.warning(f"Model {model_name} is not found in permissions map")
            return False

        result = check_function(obj) == franchise
        logger.info(f"Checking franchise ownership: {result} for model {model_name} and user {franchise.director}")

        return result


class ManagerObjectPermission(BasePermission):
    """
    Упрощенный пермишн для менеджеров с глобальным доступом.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False

        if request.user.role == 'admin':
            return True

        # Директоры франшизы имеют доступ к объектам своей франшизы
        franchise = Franchise.objects.filter(director=request.user).first()
        if franchise:
            return UniversalPermission().has_object_permission(request, view, obj)

        # Менеджеры имеют глобальный доступ
        manager = getattr(request.user, 'manager', None)
        if manager and request.user.role == 'manager':
            return True

        return False


class WebSocketPermissionChecker:
    """
    Класс для проверки прав доступа пользователя к объектам через WebSocket.
    """

    @staticmethod
    def has_permission(user, obj):
        """
        Проверяет, есть ли у пользователя права на доступ к объекту.
        """
        if user.role == 'admin':
            return True

        if not user.is_authenticated or not hasattr(user, 'manager'):
            return False

        manager = user.manager
        if not manager:
            return False

        # Проверяем доступ к чатам (глобально, без привязки к городу)
        if manager.access_types.filter(name='chats').exists():
            return True

        return False

    @staticmethod
    def check_chat_permission(user, chat):
        """
        Проверка прав доступа пользователя к чату.
        """
        return WebSocketPermissionChecker.has_permission(user, chat)


class IsAdminOrReadOnly(BasePermission):
    """
    Разрешает чтение всем, а изменение только администраторам.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_authenticated and request.user.role == 'admin'


class IsAdminOrSelf(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.role == 'admin':
            return True
        if hasattr(request.user, 'franchise') and request.user.franchise == obj.city:
            return True
        if request.user.role == 'manager' and obj.user == request.user:
            # Менеджер не может изменять свои права доступа
            if 'access_types' in request.data:
                return False
            return True
        return False


class IsAdminOrDirector(BasePermission):
    def has_permission(self, request, view):
        if request.user.role == 'admin':
            return True
        elif hasattr(request.user, 'franchise') and request.user.franchise is not None:
            return True
        return False


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        if request.user.role == 'admin':
            return True
        return False


class IsDirector(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False

        if hasattr(user, 'franchise'):
            return view.action in ['list', 'retrieve']

        return True

    def has_object_permission(self, request, view, obj):
        user = request.user

        if not hasattr(user, 'franchise'):
            return True

        franchise = user.franchise
        if isinstance(obj, Manager):
            return obj.cities.filter(id=franchise.city.id).exists()

        return False

