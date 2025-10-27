from django.db.models import Q, Count
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.generics import ListAPIView
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from chat.models import Trip
from franchise.models import Franchise
from journal.filters import TripFilter
from journal.permissions import IsAdminManagerOrFranchiseOwner, RentOrdersPermission, RentJournalPermission
from journal.serializers import TripSerializer
from vehicle.models import Vehicle


class CustomLimitOffsetPagination(LimitOffsetPagination):
    def get_paginated_response(self, data):
        return Response({
            'count': self.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data
        })


class BaseTripView(ListAPIView):
    permission_classes = [IsAuthenticated, IsAdminManagerOrFranchiseOwner]
    serializer_class = TripSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = TripFilter
    pagination_class = CustomLimitOffsetPagination

    statuses = []  # задаётся в наследниках

    def get_queryset(self):
        user = self.request.user

        base_qs = Trip.objects.filter(
            status__in=self.statuses
        ).select_related(
            'organizer', 'content_type', 'chat'
        ).prefetch_related(
            'organizer__renter'
        )

        if user.role == 'admin':
            return base_qs
        if user.role == 'manager':
            cities = user.manager.cities.all().values_list('id', flat=True)
            if cities:
                vehicles = Vehicle.objects.filter(city__in=cities)
                return base_qs.filter(object_id__in=vehicles.values_list('id', flat=True))
            else:
                return base_qs
        try:
            franchise = Franchise.objects.get(director=user)
        except Franchise.DoesNotExist:
            return Trip.objects.none()

        vehicles = Vehicle.objects.filter(
            Q(owner__lessor__franchise=franchise) | Q(owner=franchise.director)
        )

        return base_qs.filter(object_id__in=vehicles.values_list('id', flat=True))

    def get_serializer_context(self):
        context = super().get_serializer_context()
        queryset = self.get_queryset()
        vehicle_ids = queryset.values_list('object_id', flat=True)

        vehicles_map = {
            v.id: v for v in Vehicle.objects.filter(
                id__in=vehicle_ids
            ).select_related('owner', 'owner__lessor')
        }

        context['vehicles_map'] = vehicles_map
        return context

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        count_query_params = request.query_params.copy()
        count_query_params.pop('type', None)

        count_filter = self.filterset_class(
            data=count_query_params,
            queryset=queryset,
            request=request
        )
        filtered_qs_for_counts = count_filter.qs

        type_counts = filtered_qs_for_counts.values('content_type__model').annotate(
            count=Count('content_type__model')
        )
        counts_dict = {item['content_type__model']: item['count'] for item in type_counts}

        counts = {
            'auto': counts_dict.get('auto', 0),
            'bike': counts_dict.get('bike', 0),
            'ship': counts_dict.get('ship', 0),
            'helicopter': counts_dict.get('helicopter', 0),
            'specialtechnic': counts_dict.get('specialtechnic', 0)
        }

        filtered_qs = self.filter_queryset(queryset)

        page = self.paginate_queryset(filtered_qs)
        serializer = self.get_serializer(page if page is not None else filtered_qs, many=True)

        response_data = {
            'counts': counts,
            'data': serializer.data
        }

        if page is not None:
            return self.get_paginated_response(response_data)

        return Response(response_data)


@extend_schema(
    summary="Журнал аренды",
    description="Журнал аренды",
    parameters=[
        OpenApiParameter("status", str, OpenApiParameter.QUERY, description="Статус поездки", enum=['finished', 'canceled']),
        OpenApiParameter("period", str, OpenApiParameter.QUERY, description="Период", enum=['day', 'week', 'month', 'quarter', 'year']),
        OpenApiParameter("type", str, OpenApiParameter.QUERY, description="Тип"),
        OpenApiParameter("lessor_id", int, OpenApiParameter.QUERY, description="ID арендодателя"),
        OpenApiParameter("city_id", int, OpenApiParameter.QUERY, description="ID города"),
    ]
)
class TripByCityView(BaseTripView):
    permission_classes = [IsAuthenticated, (RentJournalPermission | IsAdminManagerOrFranchiseOwner)]
    statuses = ['finished', 'canceled']


@extend_schema(
    summary="Аренда и заказы",
    description="Аренда и заказы",
    parameters=[
        OpenApiParameter("status", str, OpenApiParameter.QUERY, description="Статус поездки", enum=['current', 'started']),
        OpenApiParameter("period", str, OpenApiParameter.QUERY, description="Период", enum=['day', 'week', 'month', 'quarter', 'year']),
        OpenApiParameter("type", str, OpenApiParameter.QUERY, description="Тип"),
        OpenApiParameter("lessor_id", int, OpenApiParameter.QUERY, description="ID арендодателя"),
        OpenApiParameter("city_id", int, OpenApiParameter.QUERY, description="ID города"),
    ]
)
class CurrentTripByCityView(BaseTripView):
    permission_classes = [IsAuthenticated, (RentOrdersPermission | IsAdminManagerOrFranchiseOwner)]
    statuses = ['current', 'started']
