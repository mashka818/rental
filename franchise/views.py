from datetime import timedelta
from enum import Enum

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q, Sum, Count
from django.db.models.expressions import RawSQL
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import viewsets, status, generics, filters
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import get_object_or_404
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from app.models import Lessor
from chat.models import Trip, Chat, RequestRent
from manager.permissions import IsDirector
from payment.models import Payment
from .serializers.franchise import PaymentSerializer
from vehicle.models import Vehicle, Auto, Bike, Ship, Helicopter, SpecialTechnic
from .add_lessor import RequestAddLessor
from .filters import LessorStatisticsFilter
from .models import VehiclePark, Franchise, RequestFranchise, City
from .permissions import IsOwnerOrAdmin, IsOwnerOrAdminForGet, IsDirectorOrAdminForGet, IsAdminOrManager, \
    IsAdminOrFranchiseOwner, IsLessorOrFranchiseDirector, IsAdminManagerOrLessorOrFranchiseDirector, \
    LessorsPermission, DepartmentsPermission, IsAdmin
from franchise.serializers.vehicle_park import VehicleParkRetrieveSerializer, VehicleParkListSerializer, \
    VehicleParkCreateSerializer, VehicleParkUpdateSerializer, ChatSerializer, RequestRentSerializer, VehicleSerializer, \
    VehicleParkStatisticsSerializer
from .serializers.franchise import FranchiseListSerializer, FranchiseRetrieveSerializer, \
    FranchiseCreateSerializer, FranchiseUpdateSerializer, FranchiseDeleteSerializer, LessorSerializer, \
    FranchiseStatisticsSerializer, RequestFranchiseSerializer, CitySerializer, RequestAddLessorUpdateSerializer, \
    RequestAddLessorCreateSerializer, LessorListSerializer


@extend_schema(summary="Автопарк CRUD", deprecated=True, description="CRUD Автопарка")
class VehicleParkViewSet(viewsets.ModelViewSet):
    queryset = VehiclePark.objects.all()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return VehicleParkRetrieveSerializer
        elif self.action == 'list':
            return VehicleParkListSerializer
        elif self.action == 'create':
            return VehicleParkCreateSerializer
        elif self.action in ['partial_update', 'update']:
            return VehicleParkUpdateSerializer
        return VehicleParkListSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsOwnerOrAdmin()]
        return [IsAuthenticated()]

    def perform_destroy(self, instance):
        instance.delete()

    def perform_update(self, serializer):
        serializer.save()

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


@extend_schema(summary="Все заявки на аренду автопарка", deprecated=True, description="Заявки на аренду автопарка")
class RequestsByParkView(APIView):
    permission_classes = [IsOwnerOrAdminForGet]

    def get(self, request, park_id, format=None):
        try:
            vehicles = Vehicle.objects.filter(vehicle_park_id=park_id)
        except VehiclePark.DoesNotExist:
            return Response({'detail': 'Vehicle park not found.'}, status=status.HTTP_404_NOT_FOUND)

        requests = (RequestRent.objects.filter(object_id__in=vehicles.values_list('id', flat=True))
                    .select_related('content_type'))

        serialized_requests = RequestRentSerializer(requests, many=True).data

        count_dict = {
            "auto": 0,
            "bike": 0,
            "ship": 0,
            "helicopter": 0,
            "special_technic": 0
        }

        for request in serialized_requests:
            content_type_name = request['type']
            if content_type_name in count_dict:
                count_dict[content_type_name] += 1

        data = {
            "auto": [],
            "bike": [],
            "ship": [],
            "helicopter": [],
            "special_technic": []
        }

        for request in serialized_requests:
            content_type_name = request['type']
            if content_type_name == "auto":
                data["auto"].append(request)
            elif content_type_name == "bike":
                data["bike"].append(request)
            elif content_type_name == "ship":
                data["ship"].append(request)
            elif content_type_name == "helicopter":
                data["helicopter"].append(request)
            elif content_type_name == "specialtechnic":
                data["special_technic"].append(request)

        result = {
            "counts": count_dict,
            "data": data
        }

        return Response(result, status=status.HTTP_200_OK)


@extend_schema(summary="Все чаты автопарка", deprecated=True, description="Чаты автопарка")
class ChatsByParkView(APIView):
    permission_classes = [IsAuthenticated, IsOwnerOrAdminForGet]

    def get(self, request, park_id, format=None):
        try:
            vehicles = (Vehicle.objects.filter(vehicle_park_id=park_id)
                        .select_related('owner', 'brand', 'model')
                        .prefetch_related('trips'))
        except VehiclePark.DoesNotExist:
            return Response({'detail': 'Vehicle park not found.'}, status=status.HTTP_404_NOT_FOUND)

        trips = Trip.objects.filter(object_id__in=vehicles.values_list('id', flat=True))
        chats = Chat.objects.filter(trip__in=trips)

        serializer = ChatSerializer(chats, many=True)
        return Response(serializer.data)


@extend_schema(summary="Франшиза CRUD", description="CRUD фарншизы")
class FranchiseViewSet(viewsets.ModelViewSet):
    queryset = Franchise.objects.all()
    permission_classes = [DepartmentsPermission | IsDirectorOrAdminForGet]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return self.queryset
        elif hasattr(user, 'manager'):
            cities = user.manager.cities.all().values_list('id', flat=True)
            if cities:
                return Franchise.objects.filter(city__in=cities)
            return self.queryset
        elif hasattr(user, 'franchise'):
            return Franchise.objects.filter(director=user)
        return Franchise.objects.none()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return FranchiseRetrieveSerializer
        elif self.action == 'create':
            return FranchiseCreateSerializer
        elif self.action == 'update' or self.action == 'partial_update':
            return FranchiseUpdateSerializer
        elif self.action == 'destroy':
            return FranchiseDeleteSerializer
        return FranchiseListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        franchise = serializer.save()
        return Response(FranchiseRetrieveSerializer(franchise).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        partial = kwargs.get('partial', False)

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        director = instance.director
        self.perform_destroy(instance)
        if director:
            director.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class CustomLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 10
    max_limit = 100


@extend_schema(
    summary="Все заявки на аренду франшизы",
    description="Заявки на аренду франшизы",
    parameters=[
            OpenApiParameter(
                name="type",
                description="Тип транспорта (Auto, Bike, Ship, Helicopter, SpecialTechnic)",
                type=str,
                enum=["auto", "bike", "ship", "helicopter", "special_technic"],
                required=False,
            )]
)
class RequestsByFranchiseView(APIView):
    permission_classes = [IsAuthenticated, (IsDirectorOrAdminForGet | DepartmentsPermission)]
    pagination_class = CustomLimitOffsetPagination

    def get(self, request, franchise_id, format=None):
        try:
            franchise = Franchise.objects.get(id=franchise_id)
        except Franchise.DoesNotExist:
            return Response({'detail': 'Франшиза не найдена.'}, status=status.HTTP_404_NOT_FOUND)

        vehicles = Vehicle.objects.filter(
            Q(owner__lessor__franchise=franchise) | Q(owner=franchise.director)
        )
        self.check_object_permissions(request, franchise)
        all_requests = RequestRent.objects.filter(
            object_id__in=vehicles.values_list('id', flat=True)
        ).select_related('content_type')

        count_dict = {
            "auto": 0,
            "bike": 0,
            "ship": 0,
            "helicopter": 0,
            "specialtechnic": 0
        }

        for request_rent in all_requests:
            content_type_name = request_rent.content_type.model
            if content_type_name in count_dict:
                count_dict[content_type_name] += 1

        vehicle_type = request.query_params.get('type')
        if vehicle_type:
            if vehicle_type == 'auto':
                vehicles = vehicles.instance_of(Auto)
            elif vehicle_type == 'bike':
                vehicles = vehicles.instance_of(Bike)
            elif vehicle_type == 'ship':
                vehicles = vehicles.instance_of(Ship)
            elif vehicle_type == 'helicopter':
                vehicles = vehicles.instance_of(Helicopter)
            elif vehicle_type == 'special_technic':
                vehicles = vehicles.instance_of(SpecialTechnic)

        requests = RequestRent.objects.filter(
            object_id__in=vehicles.values_list('id', flat=True)
        ).select_related('content_type')

        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(requests, request)
        serialized_requests = RequestRentSerializer(paginated_queryset, many=True).data

        result = {
            "counts": count_dict,
            "data": serialized_requests
        }

        return paginator.get_paginated_response(result)


@extend_schema(summary="Все чаты франшизы", description="Чаты франшизы")
class ChatsByFranchiseView(APIView):
    permission_classes = [IsAuthenticated, (IsDirectorOrAdminForGet | DepartmentsPermission)]
    pagination_class = CustomLimitOffsetPagination

    def get(self, request, franchise_id, format=None):
        try:
            franchise = Franchise.objects.get(id=franchise_id)
        except Franchise.DoesNotExist:
            return Response({'detail': 'Franchise not found.'}, status=status.HTTP_404_NOT_FOUND)

        vehicles = Vehicle.objects.filter(
            Q(owner__lessor__franchise=franchise) | Q(owner=franchise.director)
        )
        self.check_object_permissions(request, franchise)
        trips = Trip.objects.filter(object_id__in=vehicles.values_list('id', flat=True))
        chats = Chat.objects.filter(trip__in=trips)

        paginator = self.pagination_class()
        paginated_chats = paginator.paginate_queryset(chats, request, view=self)
        serializer = ChatSerializer(paginated_chats, many=True)
        return paginator.get_paginated_response(serializer.data)


@extend_schema(summary="Арендодатели франшизы", description="Арендодатели франшизы")
class LessorsByFranchiseView(APIView):
    permission_classes = [IsAuthenticated, (IsDirectorOrAdminForGet | DepartmentsPermission)]
    pagination_class = CustomLimitOffsetPagination

    def get(self, request, franchise_id, format=None):
        try:
            franchise = Franchise.objects.get(id=franchise_id)
        except Franchise.DoesNotExist:
            return Response({'detail': 'Franchise not found.'}, status=status.HTTP_404_NOT_FOUND)

        lessors = Lessor.objects.filter(franchise=franchise).select_related("user", "franchise").annotate(
            count_vehicles=Count("user__vehicle", distinct=True)
        )
        self.check_object_permissions(request, franchise)
        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(lessors, request)
        serializer = LessorListSerializer(paginated_queryset, many=True)
        return paginator.get_paginated_response(serializer.data)


@extend_schema(
    summary="Весь транспорт франшизы",
    description="",
    parameters=[
        OpenApiParameter(
            name="type",
            description="Тип транспорта (Auto, Bike, Ship, Helicopter, SpecialTechnic)",
            type=str,
            enum=["auto", "bike", "ship", "helicopter", "special_technic"],
            required=False,
        )]
)
class VehiclesByFranchiseView(APIView):
    permission_classes = [IsAuthenticated, (IsDirectorOrAdminForGet | DepartmentsPermission)]
    pagination_class = CustomLimitOffsetPagination

    def get(self, request, franchise_id, format=None):
        try:
            franchise = Franchise.objects.get(id=franchise_id)
        except Franchise.DoesNotExist:
            return Response({'detail': 'Franchise not found.'}, status=status.HTTP_404_NOT_FOUND)

        vehicles = Vehicle.objects.filter(
            Q(owner__lessor__franchise=franchise) | Q(owner=franchise.director)
        )
        self.check_object_permissions(request, franchise)
        vehicle_type = request.query_params.get('type')

        if vehicle_type:
            if vehicle_type == 'auto':
                vehicles = vehicles.instance_of(Auto)
            elif vehicle_type == 'bike':
                vehicles = vehicles.instance_of(Bike)
            elif vehicle_type == 'ship':
                vehicles = vehicles.instance_of(Ship)
            elif vehicle_type == 'helicopter':
                vehicles = vehicles.instance_of(Helicopter)
            elif vehicle_type == 'special_technic':
                vehicles = vehicles.instance_of(SpecialTechnic)

        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(vehicles, request)
        serializer = VehicleSerializer(paginated_queryset, many=True)
        return paginator.get_paginated_response(serializer.data)


@extend_schema(
    summary="Статистика франшизы",
    description="Статистика франшизы",
    parameters=[
            OpenApiParameter(
                name="period",
                type=str,
                location=OpenApiParameter.QUERY,
                description=(
                    "Период для фильтрации статистики по дате завершения поездок:\n"
                    "- `day`: за день\n"
                    "- `week`: за неделю\n"
                    "- `month`: за месяц\n"
                    "- `year`: за год\n"
                    "- `all` (по умолчанию): за весь период"
                ),
                required=False,
                default="all",
                enum=["day", "week", "month", "year", "all"],
            )
        ]
)
class FranchiseStatisticsView(APIView):
    permission_classes = [IsAuthenticated, (IsDirectorOrAdminForGet | DepartmentsPermission)]

    def get(self, request, franchise_id):
        try:
            franchise = Franchise.objects.get(pk=franchise_id)
        except Franchise.DoesNotExist:
            return Response({'detail': 'Franchise not found.'}, status=status.HTTP_404_NOT_FOUND)

        self.check_object_permissions(request, franchise)

        period = request.query_params.get('period', 'all')
        statistics = franchise.get_statistics(period=period)
        serializer = FranchiseStatisticsSerializer(statistics)

        return Response(serializer.data)


@extend_schema(summary="Статистика автопарка", deprecated=True, description="Статистика автопарка")
@api_view(['GET'])
def vehicle_park_statistics(request, vehicle_park_id):
    try:
        vehicle_park = VehiclePark.objects.get(pk=vehicle_park_id)
    except VehiclePark.DoesNotExist:
        return Response({'detail': 'VehiclePark not found.'}, status=status.HTTP_404_NOT_FOUND)

    statistics = vehicle_park.get_statistics()
    serializer = VehicleParkStatisticsSerializer(statistics)

    return Response(serializer.data)


@extend_schema(summary="Заявка на создание франшизы", description="Заявку может отправить любой пользователь")
class RequestFranchiseCreateView(generics.CreateAPIView):
    queryset = RequestFranchise.objects.all()
    serializer_class = RequestFranchiseSerializer


@extend_schema(summary="Получение списка заявок на создание франшизы",
               description="Получение списка заявок на создание франшизы")
class RequestFranchiseListView(generics.ListAPIView):
    queryset = RequestFranchise.objects.all()
    serializer_class = RequestFranchiseSerializer
    permission_classes = [IsAuthenticated, (IsAdmin | DepartmentsPermission)]


@extend_schema(summary="Удаление заявки на создание франшизы", description="Удаление заявки на создание франшизы")
class RequestFranchiseDeleteView(generics.DestroyAPIView):
    queryset = RequestFranchise.objects.all()
    serializer_class = RequestFranchiseSerializer
    permission_classes = [IsAuthenticated, (IsAdmin | DepartmentsPermission)]


class CityOrderingEnum(str, Enum):
    TITLE_ASC = "title"
    TITLE_DESC = "-title"
    FINISHED_COUNT_ASC = "finished_trips_count"
    FINISHED_COUNT_DESC = "-finished_trips_count"


@extend_schema(summary="Список городов",
               description="Список городов",
               parameters=[
                   OpenApiParameter(
                       name='ordering',
                       type=OpenApiTypes.STR,
                       location=OpenApiParameter.QUERY,
                       enum=[e.value for e in CityOrderingEnum],
                       description="Сортировка: `title`, `-title`, `finished_trips_count`, `-finished_trips_count`"
                   )
                ]
            )
class CityView(generics.ListAPIView):
    serializer_class = CitySerializer
    queryset = City.objects.annotate(
        finished_trips_count=RawSQL("""
                SELECT COUNT(DISTINCT t.id)
                FROM public.vehicle_vehicle v
                JOIN django_content_type ct ON v.polymorphic_ctype_id = ct.id
                JOIN public.chat_trip t ON t.object_id = v.id AND t.content_type_id = ct.id
                WHERE v.city_id = public.franchise_city.id AND t.status = 'finished'
            """, [])
    )
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['title', 'finished_trips_count']
    ordering = ['title']


@extend_schema(summary='Отображение города по ID', description='Отображение города по ID')
class CityRetrieve(APIView):
    def get(self, request, city_id):
        city = get_object_or_404(City, id=city_id)
        serializer = CitySerializer(city)
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(summary="Добавление арендодателей в франшизу", description="""Статусы: \n
                                                                          "'on_consideration', 'На рассмотрении',
        'approved', 'Подтверждено',
        'rejected', 'Отклонено'""")
class RequestAddLessorViewSet(viewsets.ModelViewSet):
    queryset = RequestAddLessor.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return RequestAddLessorUpdateSerializer
        return RequestAddLessorCreateSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), IsAdminOrFranchiseOwner()]
        elif self.action in ['update', 'partial_update']:
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        user = self.request.user

        if user.role == 'admin':
            return self.queryset
        if hasattr(user, 'franchise'):
            return self.queryset.filter(franchise=user.franchise)
        if hasattr(user, 'lessor'):
            return self.queryset.filter(lessor=user.lessor)

        return self.queryset.none()

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)

        if self.action in ['update', 'partial_update']:
            if not (
                    request.user.role == 'admin' or
                    (hasattr(request.user, 'lessor') and request.user.lessor == obj.lessor)
            ):
                raise PermissionDenied(
                    "Только администратор или указанный арендодатель могут изменять статус заявки."
                )


@extend_schema(summary="Список арендодателей", description="Список арендодателей")
class LessorListView(APIView):
    permission_classes = [LessorsPermission | IsDirectorOrAdminForGet]
    pagination_class = CustomLimitOffsetPagination

    def get(self, request, format=None):
        user = request.user
        lessors = Lessor.objects.all()
        if user.role == 'manager':
            cities = user.manager.cities.values_list('id', flat=True)
            if cities.exists():
                lessors = lessors.filter(user__vehicle__city__in=cities).distinct()

        lessors = lessors.select_related("user", "franchise").annotate(
            count_vehicles=Count("user__vehicle", distinct=True)
        )

        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(lessors, request)

        serializer = LessorListSerializer(paginated_queryset, many=True)
        return paginator.get_paginated_response(serializer.data)


@extend_schema(summary="Удаление арендодателя", description="Удаление арендодателя из франшизы")
class DeleteLessorFromFranchiseView(APIView):
    permission_classes = [IsLessorOrFranchiseDirector | DepartmentsPermission]

    def post(self, request, lessor_id):
        lessor = get_object_or_404(Lessor, id=lessor_id)
        self.check_object_permissions(request, lessor)
        lessor.franchise = None
        lessor.save()
        return Response({"detail": "Арендодатель успешно удален из франшизы."}, status=status.HTTP_200_OK)


class LessorStatisticsView(APIView):
    permission_classes = [IsAuthenticated, (IsAdminManagerOrLessorOrFranchiseDirector | DepartmentsPermission)]

    @extend_schema(
        summary="Статистика арендодателя",
        description="Вывод статистики",
        parameters=[
            OpenApiParameter(
                name="vehicle_type",
                description="Тип транспорта (Auto, Bike, Ship, Helicopter, SpecialTechnic)",
                type=str,
                enum=["auto", "bike", "ship", "helicopter", "special_technic"],
                required=False,
            ),
            OpenApiParameter(
                name="brand",
                description="ID бренда транспорта",
                type=int,
                required=False,
            ),
            OpenApiParameter(
                name="model",
                description="ID модели транспорта",
                type=int,
                required=False,
            ),
            OpenApiParameter(
                name="period",
                description="Период для фильтрации (day, week, month, quarter, year)",
                type=str,
                enum=["day", "week", "month", "quarter", "year"],
                required=False,
            ),
        ],
        responses={200: "Successfully filtered statistics"}
    )
    def get(self, request, lessor_id):
        lessor = get_object_or_404(Lessor, id=lessor_id)
        self.check_object_permissions(request, lessor)

        vehicle_cts = ContentType.objects.filter(
            model__in=['auto', 'bike', 'ship', 'helicopter', 'specialtechnic']
        )

        period = request.GET.get('period', 'all')
        today = timezone.now().date()

        if period == 'day':
            start_date = today
            previous_start = today - timedelta(days=1)
        elif period == 'week':
            start_date = today - timedelta(days=7)
            previous_start = start_date - timedelta(days=7)
        elif period == 'month':
            start_date = today - timedelta(days=30)
            previous_start = start_date - timedelta(days=30)
        elif period == 'quarter':
            start_date = today - timedelta(days=90)
            previous_start = start_date - timedelta(days=90)
        elif period == 'year':
            start_date = today - timedelta(days=365)
            previous_start = start_date - timedelta(days=365)
        elif period == 'all':
            start_date = None
            previous_start = None
        else:
            return Response({"error": "Неверный период"}, status=400)

        if start_date:
            trips = Trip.objects.filter(
                Q(content_type__in=vehicle_cts) &
                Q(object_id__in=Vehicle.objects.filter(owner=lessor.user).values_list('id', flat=True)) &
                Q(end_date__gte=start_date)
            )

            previous_trips = Trip.objects.filter(
                Q(content_type__in=vehicle_cts) &
                Q(object_id__in=Vehicle.objects.filter(owner=lessor.user).values_list('id', flat=True)) &
                Q(end_date__gte=previous_start, end_date__lt=start_date)
            )
        else:
            trips = Trip.objects.filter(
                Q(content_type__in=vehicle_cts) &
                Q(object_id__in=Vehicle.objects.filter(owner=lessor.user).values_list('id', flat=True))
            )

            previous_trips = trips

        filterset = LessorStatisticsFilter(request.GET, queryset=trips)
        if not filterset.is_valid():
            return Response(filterset.errors, status=400)
        trips = filterset.qs

        previous_filterset = LessorStatisticsFilter(request.GET, queryset=previous_trips)
        if not previous_filterset.is_valid():
            return Response(previous_filterset.errors, status=400)
        previous_trips = previous_filterset.qs

        total_revenue = trips.filter(status="finished").aggregate(total_revenue=Sum("total_cost"))["total_revenue"] or 0
        previous_total_revenue = previous_trips.filter(status="finished").aggregate(total_revenue=Sum("total_cost"))["total_revenue"] or 0

        finished_orders_count = trips.filter(status="finished").count()
        previous_finished_orders_count = previous_trips.filter(status="finished").count()

        canceled_orders_count = trips.filter(status="canceled").count()
        previous_canceled_orders_count = previous_trips.filter(status="canceled").count()

        def calculate_change(current, previous):
            if previous == 0:
                return 100 if current > 0 else 0
            return round(((current - previous) / previous) * 100, 2)

        change_total_revenue = calculate_change(total_revenue, previous_total_revenue)
        change_finished_orders_count = calculate_change(finished_orders_count, previous_finished_orders_count)
        change_canceled_orders_count = calculate_change(canceled_orders_count, previous_canceled_orders_count)

        payments = Payment.objects.filter(
            request_rent__content_type__in=vehicle_cts,
            request_rent__object_id__in=trips.filter(status="finished").values_list('object_id', flat=True)
        ).select_related("request_rent")

        if request.GET.get('vehicle_type') or request.GET.get('brand') or request.GET.get('model'):
            vehicle_ids = Vehicle.objects.filter(
                Q(model__vehicle_type=request.GET.get('vehicle_type', None)) if request.GET.get(
                    'vehicle_type') else Q(),
                Q(brand_id=request.GET.get('brand', None)) if request.GET.get('brand') else Q(),
                Q(model_id=request.GET.get('model', None)) if request.GET.get('model') else Q()
            ).values_list('id', flat=True)

            payments = payments.filter(
                request_rent__object_id__in=vehicle_ids
            )

        serialized_payments = PaymentSerializer(payments, many=True)

        result = {
            "lessor_id": lessor.id,
            "lessor_name": lessor.user.get_full_name(),
            "total_revenue": total_revenue,
            "change_total_revenue": change_total_revenue,
            "finished_orders_count": finished_orders_count,
            "change_finished_orders_count": change_finished_orders_count,
            "canceled_orders_count": canceled_orders_count,
            "change_canceled_orders_count": change_canceled_orders_count,
            "transactions": serialized_payments.data,
        }
        return Response(result)
