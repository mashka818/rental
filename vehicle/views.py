import os
import logging
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Q, Min, Prefetch
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.filters import OrderingFilter
from rest_framework.generics import get_object_or_404, ListAPIView
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

from RentalGuru import settings
from app.models import Lessor
from chat.models import Trip
from manager.permissions import ManagerObjectPermission, IsFranchiseDirector, VehiclesAccess
from notification.models import Notification
from .filters import AutoFilter, BikeFilter, ShipFilter, HelicopterFilter, SpecialTechnicFilter, BaseFilter, \
    VehicleModelFilter, VehicleBrandFilter
from .models import VehicleBrand, VehicleModel, Auto, Bike, Ship, Helicopter, SpecialTechnic, RatingUpdateLog, Vehicle, \
    AutoFeaturesAdditionally, BikeFeaturesAdditionally, ShipFeaturesAdditionally, \
    FeaturesForChildren, FeaturesEquipment, PaymentMethod, AutoFuelType, AutoTransmission, AutoBodyType, \
    BikeTransmission, VehicleClass, VehiclePhoto, VehicleDocument, AutoFeaturesFunctions, BikeFeaturesFunctions, \
    ShipFeaturesFunctions, ShipType, TechnicType, BikeBodyType
from .permission import IsAdminOrLessor, IsAdminOrReadOnly, IsAdminOrOwner
from .serializers.base import VehicleBrandSerializer, VehicleModelSerializer, \
    PaymentMethodSerializer, VehicleClassSerializer, VehicleSerializer, UpdatePhotoOrderSerializer
from .serializers.auto import AutoGetSerializer, AutoListSerializer, AutoCreateSerializer, \
    AutoUpdateSerializer, AutoFeaturesAdditionallySerializer, FeaturesForChildrenSerializer, AutoFuelTypeSerializer, \
    AutoTransmissionSerializer, AutoBodyTypeSerializer, AutoFeaturesFunctionsSerializer
from .serializers.bike import BikeGetSerializer, BikeListSerializer, BikeCreateSerializer, BikeUpdateSerializer, \
    BikeFeaturesAdditionallySerializer, BikeTransmissionSerializer, BikeFeaturesFunctionsSerializer, \
    BikeBodyTypeSerializer
from .serializers.rating import UpdateRatingSerializer
from .serializers.ship import ShipGetSerializer, ShipListSerializer, ShipCreateSerializer, ShipUpdateSerializer, \
    ShipFeaturesAdditionallySerializer, FeaturesEquipmentSerializer, ShipFeaturesFunctionsSerializer, ShipTypeSerializer
from .serializers.helicopter import HelicopterGetSerializer, HelicopterListSerializer, HelicopterCreateSerializer, \
    HelicopterUpdateSerializer
from .serializers.specialtechnic import SpecialTechnicGetSerializer, SpecialTechnicListSerializer, \
    SpecialTechnicCreateSerializer, SpecialTechnicUpdateSerializer, TechnicTypeSerializer
from .utils import update_photo_order


@extend_schema(summary="Марка транспорта", description="Марка транспорта")
class VehicleBrandViewSet(viewsets.ModelViewSet):
    queryset = VehicleBrand.objects.all()
    serializer_class = VehicleBrandSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_class = VehicleBrandFilter


@extend_schema(summary="Модель транспорта", description="Модель транспорта")
class VehicleModelViewSet(viewsets.ModelViewSet):
    queryset = VehicleModel.objects.all().select_related('brand')
    filter_backends = (DjangoFilterBackend,)
    filterset_class = VehicleModelFilter
    serializer_class = VehicleModelSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_permissions(self):
        if hasattr(self.request.user, 'manager') and self.request.user.manager:
            return [ManagerObjectPermission()]
        return super().get_permissions()


class BaseViewSet(viewsets.ModelViewSet):
    def get_permissions(self):
        if self.action == 'list':
            self.permission_classes = [AllowAny]
        elif self.action == 'retrieve':
            self.permission_classes = [AllowAny]
        elif self.action == 'create':
            self.permission_classes = [IsAuthenticated, (IsAdminOrLessor | VehiclesAccess)]
        elif self.action in ['update', 'partial_update', 'destroy']:
            self.permission_classes = [IsAuthenticated, (IsAdminOrOwner | VehiclesAccess)]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        try:
            logger.info(f"Creating vehicle. User: {request.user.id}, Data keys: {request.data.keys()}")
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            logger.info(f"Vehicle created successfully. ID: {serializer.instance.id}")
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        except Exception as e:
            logger.error(f"Error creating vehicle. User: {request.user.id}, Error: {str(e)}", exc_info=True)
            return Response(
                {"detail": f"Ошибка при создании транспорта: {str(e)}"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    def update(self, request, *args, **kwargs):
        try:
            partial = kwargs.pop('partial', False)
            instance = self.get_object()
            logger.info(f"Updating vehicle {instance.id}. User: {request.user.id}, Data keys: {request.data.keys()}")
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            logger.info(f"Vehicle {instance.id} updated successfully")
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error updating vehicle. Instance: {instance.id}, User: {request.user.id}, Error: {str(e)}", exc_info=True)
            return Response(
                {"detail": f"Ошибка при обновлении транспорта: {str(e)}"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    def perform_update(self, serializer):
        instance = serializer.save()
        if 'verified' in serializer.validated_data and not self.request.user.role in ['admin', 'manager']:
            instance.verified = False
            instance.save()


@extend_schema(summary="Автомобиль CRUD",
               description="Автомобили CRUD",
               parameters=[
                   OpenApiParameter(
                       name="ordering",
                       type=OpenApiTypes.STR,
                       location=OpenApiParameter.QUERY,
                       description=(
                               "Поле для сортировки. "
                               "Доступные значения: "
                               "`price`, `-price`, "
                               "`count_trip`, `-count_trip`, "
                               "`average_rating`, `-average_rating`, "
                               "`created_at`, `-created_at`."
                       ),
                       enum=[
                           "price", "-price",
                           "count_trip", "-count_trip",
                           "average_rating", "-average_rating",
                           "created_at", "-created_at"
                       ],
                   )
               ],
               )
class AutoViewSet(BaseViewSet):
    queryset = Auto.objects.all()
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = AutoFilter
    ordering_fields = ['price', 'count_trip', 'average_rating', 'created_at']
    ordering = ['-average_rating']

    def get_queryset(self):
        user = self.request.user
        queryset = (Auto.objects.annotate(price=Min('rent_prices__price'))
                    .select_related('owner', 'brand', 'model', 'transmission', 'fuel_type', 'body_type',
                                    'vehicle_class', 'city', 'owner__lessor')
                    .prefetch_related('payment_method', 'features_for_children', 'features_functions', 'photos',
                                      'features_additionally', 'availabilities', 'documents', 'rent_prices'))
        if user.is_authenticated:
            if user.role in ['admin', 'manager']:
                return queryset.distinct()
            else:
                is_renter = hasattr(user, 'renter')
                is_lessor = hasattr(user, 'lessor')
                if is_lessor:
                    queryset = queryset.filter(owner=user)
                elif is_renter:
                    queryset = queryset.filter(verified=True)
        else:
            queryset = queryset.filter(verified=True)
        if not self.request.query_params.get('ordering'):
            queryset = queryset.order_by('-average_rating')
        return queryset.distinct()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return AutoGetSerializer
        elif self.action == 'list':
            return AutoListSerializer
        elif self.action == 'create':
            return AutoCreateSerializer
        return AutoUpdateSerializer


@extend_schema(summary="Мотоцикл",
               description="Мотоцикл",
               parameters=[
                   OpenApiParameter(
                       name="ordering",
                       type=OpenApiTypes.STR,
                       location=OpenApiParameter.QUERY,
                       description=(
                               "Поле для сортировки. "
                               "Доступные значения: "
                               "`price`, `-price`, "
                               "`count_trip`, `-count_trip`, "
                               "`average_rating`, `-average_rating`, "
                               "`created_at`, `-created_at`."
                       ),
                       enum=[
                           "price", "-price",
                           "count_trip", "-count_trip",
                           "average_rating", "-average_rating",
                           "created_at", "-created_at"
                       ],
                   )
               ],
               )
class BikeViewSet(BaseViewSet):
    queryset = Bike.objects.all()
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = BikeFilter
    ordering_fields = ['price', 'count_trip', 'average_rating', 'created_at']
    ordering = ['-average_rating']

    def get_queryset(self):
        user = self.request.user
        queryset = (Bike.objects.annotate(price=Min('rent_prices__price'))
                    .select_related('owner', 'brand', 'model', 'transmission', 'vehicle_class', 'city', 'owner__lessor',
                                    'body_type')
                    .prefetch_related('payment_method', 'features_functions', 'features_additionally', 'availabilities',
                                      'documents', 'rent_prices', 'photos'))
        if user.is_authenticated:
            if user.role in ['admin', 'manager']:
                return queryset.distinct()
            else:
                is_renter = hasattr(user, 'renter')
                is_lessor = hasattr(user, 'lessor')
                if is_lessor:
                    queryset = queryset.filter(owner=user)
                elif is_renter:
                    queryset = queryset.filter(verified=True)
        else:
            queryset = queryset.filter(verified=True)
        return queryset.distinct()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return BikeGetSerializer
        elif self.action == 'list':
            return BikeListSerializer
        elif self.action == 'create':
            return BikeCreateSerializer
        return BikeUpdateSerializer


@extend_schema(summary="Судно",
               description="Судно",
               parameters=[
                   OpenApiParameter(
                       name="ordering",
                       type=OpenApiTypes.STR,
                       location=OpenApiParameter.QUERY,
                       description=(
                               "Поле для сортировки. "
                               "Доступные значения: "
                               "`price`, `-price`, "
                               "`count_trip`, `-count_trip`, "
                               "`average_rating`, `-average_rating`, "
                               "`created_at`, `-created_at`."
                       ),
                       enum=[
                           "price", "-price",
                           "count_trip", "-count_trip",
                           "average_rating", "-average_rating",
                           "created_at", "-created_at"
                       ],
                   )
               ],
               )
class ShipViewSet(BaseViewSet):
    queryset = Ship.objects.all()
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = ShipFilter
    ordering_fields = ['price', 'count_trip', 'average_rating', 'created_at']
    ordering = ['-average_rating']

    def get_queryset(self):
        user = self.request.user
        queryset = (Ship.objects.annotate(price=Min('rent_prices__price'))
                    .select_related('owner', 'brand', 'model', 'vehicle_class', 'city', 'owner__lessor', 'type_ship')
                    .prefetch_related('payment_method', 'features_functions', 'features_additionally',
                                      'features_equipment', 'availabilities', 'documents', 'rent_prices', 'photos'))
        if user.is_authenticated:
            if user.role in ['admin', 'manager']:
                return queryset.distinct()
            else:
                is_renter = hasattr(user, 'renter')
                is_lessor = hasattr(user, 'lessor')
                if is_lessor:
                    queryset = queryset.filter(owner=user)
                elif is_renter:
                    queryset = queryset.filter(verified=True)
        else:
            queryset = queryset.filter(verified=True)
            pass
        return queryset.distinct()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ShipGetSerializer
        elif self.action == 'list':
            return ShipListSerializer
        elif self.action == 'create':
            return ShipCreateSerializer
        return ShipUpdateSerializer


@extend_schema(summary="Вертолет",
               description="Вертолет",
               parameters=[
                   OpenApiParameter(
                       name="ordering",
                       type=OpenApiTypes.STR,
                       location=OpenApiParameter.QUERY,
                       description=(
                               "Поле для сортировки. "
                               "Доступные значения: "
                               "`price`, `-price`, "
                               "`count_trip`, `-count_trip`, "
                               "`average_rating`, `-average_rating`, "
                               "`created_at`, `-created_at`."
                       ),
                       enum=[
                           "price", "-price",
                           "count_trip", "-count_trip",
                           "average_rating", "-average_rating",
                           "created_at", "-created_at"
                       ],
                   )
               ],
               )
class HelicopterViewSet(BaseViewSet):
    queryset = Helicopter.objects.all()
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = HelicopterFilter
    ordering_fields = ['price', 'count_trip', 'average_rating', 'created_at']
    ordering = ['-average_rating']

    def get_queryset(self):
        user = self.request.user
        queryset = (Helicopter.objects.annotate(price=Min('rent_prices__price'))
                    .select_related('owner', 'brand', 'model', 'vehicle_class', 'city', 'owner__lessor')
                    .prefetch_related('payment_method', 'availabilities', 'documents', 'rent_prices', 'photos'))
        if user.is_authenticated:
            if user.role in ['admin', 'manager']:
                return queryset.distinct()
            else:
                is_renter = hasattr(user, 'renter')
                is_lessor = hasattr(user, 'lessor')
                if is_lessor:
                    queryset = queryset.filter(owner=user)
                elif is_renter:
                    queryset = queryset.filter(verified=True)
                    pass
        else:
            queryset = queryset.filter(verified=True)
            pass
        return queryset.distinct()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return HelicopterGetSerializer
        elif self.action == 'list':
            return HelicopterListSerializer
        elif self.action == 'create':
            return HelicopterCreateSerializer
        return HelicopterUpdateSerializer


@extend_schema(summary="Спецтехника",
               description="Спецтехника",
               parameters=[
                   OpenApiParameter(
                       name="ordering",
                       type=OpenApiTypes.STR,
                       location=OpenApiParameter.QUERY,
                       description=(
                               "Поле для сортировки. "
                               "Доступные значения: "
                               "`price`, `-price`, "
                               "`count_trip`, `-count_trip`, "
                               "`average_rating`, `-average_rating`, "
                               "`created_at`, `-created_at`."
                       ),
                       enum=[
                           "price", "-price",
                           "count_trip", "-count_trip",
                           "average_rating", "-average_rating",
                           "created_at", "-created_at"
                       ],
                   )
               ],
               )
class SpecialTechnicViewSet(BaseViewSet):
    queryset = SpecialTechnic.objects.all()
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = SpecialTechnicFilter
    ordering_fields = ['price', 'count_trip', 'average_rating', 'created_at']
    ordering = ['-average_rating']

    def get_queryset(self):
        user = self.request.user
        queryset = (SpecialTechnic.objects.annotate(price=Min('rent_prices__price'))
                    .select_related('owner', 'brand', 'model', 'city', 'owner__lessor', 'type_technic')
                    .prefetch_related('payment_method', 'availabilities', 'documents', 'rent_prices', 'photos'))
        if user.is_authenticated:
            if user.role in ['admin', 'manager']:
                return queryset.distinct()
            else:
                is_renter = hasattr(user, 'renter')
                is_lessor = hasattr(user, 'lessor')
                if is_lessor:
                    queryset = queryset.filter(owner=user)
                elif is_renter:
                    queryset = queryset.filter(verified=True)
                    pass
        else:
            queryset = queryset.filter(verified=True)
            pass
        return queryset.distinct()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return SpecialTechnicGetSerializer
        elif self.action == 'list':
            return SpecialTechnicListSerializer
        elif self.action == 'create':
            return SpecialTechnicCreateSerializer
        return SpecialTechnicUpdateSerializer


@extend_schema(summary="Обновление рейтинга", description="Обновить рейтинг может пользователь, который завершил "
                                                          "поездку. Доступно один раз для одного транспорта")
class UpdateRatingView(APIView):
    serializer_class = UpdateRatingSerializer

    def patch(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            vehicle_type = data['Vehicle_type']
            vehicle_id = data['Vehicle_id']

            model = {
                'Auto': Auto,
                'Bike': Bike,
                'Ship': Ship,
                'Helicopter': Helicopter,
                'SpecialTechnic': SpecialTechnic
            }.get(vehicle_type)

            if not model:
                return Response({"error": "Неверный тип транспорта"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                vehicle = model.objects.get(id=vehicle_id)
            except model.DoesNotExist:
                return Response({"error": "Транспорт не найден"}, status=status.HTTP_404_NOT_FOUND)

            content_type = ContentType.objects.get_for_model(vehicle)

            # Проверка, обновлял ли пользователь уже рейтинг
            if RatingUpdateLog.objects.filter(user=request.user, content_type=content_type,
                                              object_id=vehicle_id).exists():
                return Response({"error": "Вы уже обновили рейтинг этого автомобиля."},
                                status=status.HTTP_403_FORBIDDEN)

            try:
                trip = Trip.objects.filter(
                    organizer=request.user,
                    content_type=content_type,
                    object_id=vehicle_id,
                    status='finished'
                ).first()
            except Trip.DoesNotExist:
                return Response({"error": "Не найдено соответствующей поездки"}, status=status.HTTP_404_NOT_FOUND)

            # Обновляем рейтинги
            ratings_fields = ['Cleanliness', 'Maintenance', 'Communication', 'Convenience', 'Accuracy']
            for field in ratings_fields:
                rating = data.get(field)
                if rating is not None:
                    field_ratings = vehicle.ratings.get(field, {})
                    star_key = f"{rating}_stars"
                    field_ratings[star_key] = field_ratings.get(star_key, 0) + 1
                    vehicle.ratings[field] = field_ratings

            vehicle.save()

            try:
                lessor = Lessor.objects.get(user=vehicle.owner)
                lessor.count_trip += 1
                lessor.save()
            except Lessor.DoesNotExist:
                return Response({"error": "Арендодатель не найден"}, status=status.HTTP_404_NOT_FOUND)

            # Логируем обновление рейтинга
            RatingUpdateLog.objects.create(
                user=request.user,
                content_type=content_type,
                object_id=vehicle_id,
                cleanliness=data.get('Cleanliness'),
                maintenance=data.get('Maintenance'),
                communication=data.get('Communication'),
                convenience=data.get('Convenience'),
                accuracy=data.get('Accuracy')
            )

            # Отправка уведомлений
            content = f'Обновлен рейтинг для {vehicle}'
            url = f'{settings.HOST_URL}/vehicle/{content_type}s/{vehicle.id}'
            Notification.objects.create(user=vehicle.owner, content=content, url=url)

            return Response({"status": "Рейтинг успешно обновлен"}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(summary="Получение GPS данных", description="Получение GPS данных")
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_gps_location(request):
    vehicle_id = request.data.get('vehicle_id')
    latitude = request.data.get('latitude')
    longitude = request.data.get('longitude')

    vehicle = Vehicle.objects.get(id=vehicle_id)
    vehicle.latitude = latitude
    vehicle.longitude = longitude
    vehicle.save()

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'gps_tracking_{vehicle_id}',
        {
            'type': 'gps_update',
            'latitude': latitude,
            'longitude': longitude
        }
    )

    return Response({"status": "success"})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def gps_tracking_view(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, id=vehicle_id)

    # Проверка прав доступа. следует добавить еще пользователей. Пока непонятно каких
    if not request.user != vehicle.owner:
        return Response({"error": "У вас нет разрешения на отслеживание этого транспортного средства"}, status=403)

    data = {
        'vehicle_id': vehicle.id,
        'brand': vehicle.brand.name,
        'model': vehicle.model.name,
        'latitude': vehicle.latitude,
        'longitude': vehicle.longitude,
        'last_update': vehicle.last_update.isoformat(),
        'websocket_url': f'/ws/gps_tracking/{vehicle.id}/',
    }

    return Response(data)


@extend_schema(summary="Список функций автомобилей", description="Список функций автомобилей")
class AutoFeaturesFunctionsListView(ListAPIView):
    queryset = AutoFeaturesFunctions.objects.all()
    serializer_class = AutoFeaturesFunctionsSerializer


@extend_schema(summary="Список функций мотоциклов", description="Список функций мотоциклов")
class BikeFeaturesFunctionsListView(ListAPIView):
    queryset = BikeFeaturesFunctions.objects.all()
    serializer_class = BikeFeaturesFunctionsSerializer


@extend_schema(summary="Список функций суден", description="Список функций суден")
class ShipFeaturesFunctionsListView(ListAPIView):
    queryset = ShipFeaturesFunctions.objects.all()
    serializer_class = ShipFeaturesFunctionsSerializer


@extend_schema(summary="Список дополнительных особенностей авто", description="Список дополнительных особенностей авто")
class AutoFeaturesAdditionallyListView(ListAPIView):
    queryset = AutoFeaturesAdditionally.objects.all()
    serializer_class = AutoFeaturesAdditionallySerializer


@extend_schema(summary="Список дополнительных особенностей мотоциклов",
               description="Список дополнительных особенностей мотоциклов")
class BikeFeaturesAdditionallyListView(ListAPIView):
    queryset = BikeFeaturesAdditionally.objects.all()
    serializer_class = BikeFeaturesAdditionallySerializer


@extend_schema(summary="Список дополнительных особенностей суден",
               description="Список дополнительных особенностей суден")
class ShipFeaturesAdditionallyListView(ListAPIView):
    queryset = ShipFeaturesAdditionally.objects.all()
    serializer_class = ShipFeaturesAdditionallySerializer


@extend_schema(summary="Список особенностей авто для детей", description="Список особенностей авто для детей")
class FeaturesForChildrenListView(ListAPIView):
    queryset = FeaturesForChildren.objects.all()
    serializer_class = FeaturesForChildrenSerializer


@extend_schema(summary="Список оборудования для суден", description="Список оборудования для суден")
class FeaturesEquipmentListView(ListAPIView):
    queryset = FeaturesEquipment.objects.all()
    serializer_class = FeaturesEquipmentSerializer


@extend_schema(summary="Список способов платежей", description="Список способов платежей")
class PaymentMethodListView(ListAPIView):
    queryset = PaymentMethod.objects.all()
    serializer_class = PaymentMethodSerializer


@extend_schema(summary="Виды топлива авто", description="Виды топлива")
class AutoFuelTypeListView(ListAPIView):
    queryset = AutoFuelType.objects.all()
    serializer_class = AutoFuelTypeSerializer


@extend_schema(summary="Коробки передач авто", description="Коробки передач для авто")
class AutoTransmissionListView(ListAPIView):
    queryset = AutoTransmission.objects.all()
    serializer_class = AutoTransmissionSerializer


@extend_schema(summary="Типы кузова авто", description="Типы кузова авто")
class AutoBodyTypeListView(ListAPIView):
    queryset = AutoBodyType.objects.all()
    serializer_class = AutoBodyTypeSerializer


@extend_schema(summary="Типы мотоциклов", description="Типы мотоциклов")
class BikeBodyTypeListView(ListAPIView):
    queryset = BikeBodyType.objects.all()
    serializer_class = BikeBodyTypeSerializer


@extend_schema(summary="Типы суден", description="Типы суден")
class ShipTypeListView(ListAPIView):
    queryset = ShipType.objects.all()
    serializer_class = ShipTypeSerializer


@extend_schema(summary="Типы спецтехники", description="Типы спецтехники")
class TechnicTypeListView(ListAPIView):
    queryset = TechnicType.objects.all()
    serializer_class = TechnicTypeSerializer


@extend_schema(summary="Коробка передач мотоциклов", description="Коробка передач мотоциклов")
class BikeTransmissionListView(ListAPIView):
    queryset = BikeTransmission.objects.all()
    serializer_class = BikeTransmissionSerializer


@extend_schema(summary="Классы транспорта", description="Классы транспорта")
class VehicleClassListView(ListAPIView):
    queryset = VehicleClass.objects.all()
    serializer_class = VehicleClassSerializer


VEHICLE_MODELS = {
    'auto': (Auto, AutoListSerializer),
    'bike': (Bike, BikeListSerializer),
    'ship': (Ship, ShipListSerializer),
    'helicopter': (Helicopter, HelicopterListSerializer),
    'specialtechnic': (SpecialTechnic, SpecialTechnicListSerializer),
}


class AllVehiclesPagination(LimitOffsetPagination):
    default_limit = 10
    max_limit = 100


@extend_schema(summary="Список всего транспорта",
               description="Список всего транспорта",
               parameters=[
                   OpenApiParameter("super_host", type=OpenApiTypes.BOOL, description="Суперхост"),
                   OpenApiParameter("day_price", type=OpenApiTypes.STR, description="Дневная цена в формате 'min,max'"),
                   OpenApiParameter("verified_only", type=OpenApiTypes.BOOL,
                                    description="Сдается только верифицированным пользователям"),
                   OpenApiParameter("brand", type=OpenApiTypes.STR, description="Марка"),
                   OpenApiParameter("year", type=OpenApiTypes.STR, description="Год выпуска в формате 'min,max'"),
                   OpenApiParameter("rental_date_after", type=OpenApiTypes.STR,
                                    description="Выбор даты аренды в формате 'YYYY-MM-DD'"),
                   OpenApiParameter("rental_date_before", type=OpenApiTypes.STR,
                                    description="Выбор даты аренды в формате 'YYYY-MM-DD'"),
                   OpenApiParameter("city", type=OpenApiTypes.INT, description="Город"),
                   OpenApiParameter("lat", type=OpenApiTypes.NUMBER, description="Широта"),
                   OpenApiParameter("lon", type=OpenApiTypes.NUMBER, description="Долгота"),
                   OpenApiParameter("radius", type=OpenApiTypes.NUMBER, description="Радиус в км"),
                   OpenApiParameter('limit', type=int, location=OpenApiParameter.QUERY,
                                    description='Number of results to return.'),
                   OpenApiParameter('offset', type=int, location=OpenApiParameter.QUERY,
                                    description='The initial index from which to return the results.'),
                   OpenApiParameter("lessor_id", type=OpenApiTypes.INT, description="ID арендодателя"),
                   OpenApiParameter("vehicle_type", type=OpenApiTypes.STR,
                                    enum=['auto', 'bike', 'ship', 'helicopter', 'specialtechnic'],
                                    description="Тип транспорта"),
                   OpenApiParameter("long_distance", type=OpenApiTypes.BOOL, description="Междугородние поездки"),
                   OpenApiParameter("delivery", type=OpenApiTypes.BOOL, description="Доставка"),
                   OpenApiParameter("average_rating_min", type=OpenApiTypes.NUMBER, description="Минимальный рейтинг"),
                   OpenApiParameter("average_rating_max", type=OpenApiTypes.NUMBER, description="Максимальный рейтинг"),
                   OpenApiParameter("verified", type=OpenApiTypes.BOOL, description="Верифицированный транспорт"),
                   OpenApiParameter(
                                   name="ordering",
                                   type=OpenApiTypes.STR,
                                   location=OpenApiParameter.QUERY,
                                   description=(
                                           "Поле для сортировки. "
                                           "Доступные значения: "
                                           "`price`, `-price`, "
                                           "`count_trip`, `-count_trip`, "
                                           "`average_rating`, `-average_rating`, "
                                           "`created_at`, `-created_at`."
                                   ),
                                   enum=[
                                       "price", "-price",
                                       "count_trip", "-count_trip",
                                       "average_rating", "-average_rating",
                                       "created_at", "-created_at"
                                   ],
                               )
                           ],
                           )
class AllVehiclesListView(ListAPIView):
    permission_classes = [AllowAny]
    pagination_class = AllVehiclesPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = BaseFilter
    ordering_fields = ['price', 'count_trip', 'average_rating', 'created_at']
    ordering = ['-average_rating']

    def get_queryset(self):
        request = self.request
        user = request.user

        # если ordering передан — используем его, иначе из self.ordering
        ordering = request.GET.get('ordering') or self.ordering[0]

        vehicle_type = request.GET.get('vehicle_type')

        models_to_query = VEHICLE_MODELS.items() if not vehicle_type else [
            (vehicle_type.lower(), VEHICLE_MODELS.get(vehicle_type.lower()))
        ]

        all_vehicles = []
        for type_name, config in models_to_query:
            if config is None:
                continue
            model_cls, _ = config

            base_qs = model_cls.objects.all().annotate(price=Min('rent_prices__price'))

            # фильтрация по пользователю
            if user.is_authenticated:
                if hasattr(user, 'renter'):
                    base_qs = base_qs.filter(verified=True)
                elif hasattr(user, 'lessor'):
                    base_qs = base_qs.filter(owner=user)
                elif hasattr(user, 'manager'):
                    cities = user.manager.cities.all().values_list('id', flat=True)
                    if cities:
                        base_qs = base_qs.filter(city__in=cities)
            else:
                base_qs = base_qs.filter(verified=True)

            # фильтрация по lessor_id
            lessor_id = request.GET.get("lessor_id")
            if lessor_id:
                base_qs = base_qs.filter(owner__lessor__id=lessor_id)

            # фильтрация через BaseFilter
            filterset = self.filterset_class(request.GET, queryset=base_qs)
            if filterset.is_valid():
                base_qs = filterset.qs

            base_qs = base_qs.prefetch_related(
                'photos',
                'availabilities',
                'rent_prices',
            ).select_related(
                'brand', 'model', 'city', 'owner', 'owner__lessor'
            )

            base_qs = base_qs.order_by(ordering)
            all_vehicles.extend(list(base_qs))

        return sorted(
            all_vehicles,
            key=lambda obj: getattr(obj, ordering.strip('-')),
            reverse=ordering.startswith('-')
        )

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)

        # Сериализация с разными сериализаторами в зависимости от типа объекта
        serialized_data = []
        for obj in page:
            for model_cls, serializer_cls in VEHICLE_MODELS.values():
                if isinstance(obj, model_cls):
                    serialized_data.append(serializer_cls(obj).data)
                    break

        return paginator.get_paginated_response(serialized_data)


@extend_schema(summary="Удаление фото транспорта", description="Удаление фото транспорта по id")
class VehiclePhotoDeleteView(APIView):
    permission_classes = [IsAdminOrOwner | IsFranchiseDirector | VehiclesAccess]

    def get_object(self):
        photo = get_object_or_404(VehiclePhoto, id=self.kwargs['photo_id'])
        return photo.vehicle

    def delete(self, request, photo_id):
        photo = get_object_or_404(VehiclePhoto, id=photo_id)
        self.check_object_permissions(request, photo.vehicle)

        photo_path = photo.photo.path
        photo.delete()
        if os.path.isfile(photo_path):
            os.remove(photo_path)

        return Response({"detail": "Фото удалено"}, status=status.HTTP_204_NO_CONTENT)


class VehicleSearchViewSet(viewsets.ViewSet):
    pagination_class = LimitOffsetPagination

    def get_serializer_for_model(self, model_class):
        serializers = {
            Auto: AutoListSerializer,
            Bike: BikeListSerializer,
            Ship: ShipListSerializer,
            Helicopter: HelicopterListSerializer,
            SpecialTechnic: SpecialTechnicListSerializer,
        }
        return serializers.get(model_class, VehicleSerializer)

    @extend_schema(summary="Поиск транспорта",
                   parameters=[
                       OpenApiParameter(name='limit', type=int, location=OpenApiParameter.QUERY,
                                        description='Number of results to return.'),
                       OpenApiParameter(name='offset', type=int, location=OpenApiParameter.QUERY,
                                        description='The initial index from which to return the results.')
                   ],
                   description="""Поиск по всем типам транспорта: /vehicle-search/search/?q=поисковый_запрос\n
                                                               Поиск по конкретному типу транспорта: /vehicle-search/search/?q=поисковый_запрос&type=auto\n
                                                                                                     /vehicle-search/search/?q=поисковый_запрос&type=bike\n
                                                                                                     /vehicle-search/search/?q=поисковый_запрос&type=ship\n
                                                                                                     /vehicle-search/search/?q=поисковый_запрос&type=helicopter\n
                                                                                                     /vehicle-search/search/?q=поисковый_запрос&type=special_technic\n""")
    @action(detail=False, methods=['get'])
    def search(self, request):
        query = request.query_params.get('q', '')
        vehicle_type = request.query_params.get('type', None)

        if not query:
            return Response({
                'vehicles': []
            })

        query_parts = query.split()
        brand_query = query_parts[0]
        model_query = " ".join(query_parts[1:])

        matching_brands = VehicleBrand.objects.annotate(
            similarity=TrigramSimilarity('name', brand_query)
        ).filter(similarity__gt=0.3).order_by('-similarity')

        matching_models = VehicleModel.objects.annotate(
            similarity=TrigramSimilarity('name', model_query)
        ).filter(similarity__gt=0.3).order_by('-similarity')

        if matching_models.exists():
            model_ids = matching_models.values_list('id', flat=True)
            vehicle_query = Q(brand__in=matching_brands) & Q(model__in=matching_models)
        else:
            vehicle_query = Q(brand__in=matching_brands)

        vehicle_query &= Q(verified=True)

        vehicle_type_mapping = {
            'auto': Auto,
            'bike': Bike,
            'ship': Ship,
            'helicopter': Helicopter,
            'special_technic': SpecialTechnic
        }

        all_vehicles = []
        if vehicle_type and vehicle_type in vehicle_type_mapping:
            model_class = vehicle_type_mapping[vehicle_type]
            all_vehicles = model_class.objects.filter(vehicle_query)
        else:
            for model_class in vehicle_type_mapping.values():
                all_vehicles.extend(model_class.objects.filter(vehicle_query))

        paginator = self.pagination_class()
        paginated_vehicles = paginator.paginate_queryset(all_vehicles, request)

        if paginated_vehicles is None:
            return Response({"vehicles": []})

        result = []
        for vehicle in paginated_vehicles:
            serializer = self.get_serializer_for_model(type(vehicle))
            result.append(serializer(vehicle).data)

        return paginator.get_paginated_response(result)

    @extend_schema(summary="Автозаполнение поисковой строки", description="Автозаполнение поисковой строки")
    @action(detail=False, methods=['get'])
    def autocomplete(self, request):
        query = request.query_params.get('q', '').strip()
        if not query:
            return Response({"suggestions": []})

        exact_brand = VehicleBrand.objects.filter(name__iexact=query).first()
        if exact_brand:
            models = VehicleModel.objects.filter(brand=exact_brand).values_list('name', flat=True)
            return Response({"suggestions": [f"{exact_brand.name} {model}" for model in models]})

        matching_brands = VehicleBrand.objects.annotate(
            similarity=TrigramSimilarity('name', query)
        ).filter(similarity__gt=0.3).order_by('-similarity')[:5]

        suggestions = [brand.name for brand in matching_brands]
        return Response({"suggestions": suggestions})


@extend_schema(summary="Удаление документа", description="Удаление документа")
class DeleteVehicleDocumentView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrOwner]

    def delete(self, request, document_id):
        document = VehicleDocument.objects.filter(id=document_id).first()

        if not document:
            return Response({'detail': 'Документ не найден.'}, status=status.HTTP_404_NOT_FOUND)

        if document.vehicle.owner != request.user and request.user.role not in ['administrator', 'manager']:
            return Response({'detail': 'У вас нет прав для удаления этого документа.'},
                            status=status.HTTP_403_FORBIDDEN)

        document.delete()
        return Response({'detail': 'Документ успешно удален.'}, status=status.HTTP_204_NO_CONTENT)


@extend_schema(summary="Изменение порядка вывода фото", description="Изменение порядка вывода фото",
               request=UpdatePhotoOrderSerializer)
class UpdatePhotoOrderView(APIView):
    permission_classes = [IsAuthenticated, (IsAdminOrOwner | VehiclesAccess | IsFranchiseDirector)]

    def post(self, request, *args, **kwargs):
        serializer = UpdatePhotoOrderSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        photo_id = serializer.validated_data['photo_id']
        new_order = serializer.validated_data['new_order']

        photo = VehiclePhoto.objects.get(id=photo_id)
        old_order = photo.order

        update_photo_order(photo.vehicle, old_order, new_order)

        return Response({"detail": "Порядок фотографий обновлен"}, status=status.HTTP_200_OK)


@extend_schema(summary="Количество неверифицированного транспорта")
class UnverifiedVehicleCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Vehicle.objects.filter(verified=False).count()
        if request.user.role == 'manager':
            cities = request.user.manager.cities.values_list('id', flat=True)
            if cities:
                count = Vehicle.objects.filter(verified=False, city__in=cities).count()
        return Response({"unverified_vehicle_count": count})
