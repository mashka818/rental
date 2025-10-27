from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.response import Response

from app.models import Lessor, User
from franchise.models import Franchise
from influencer.models import Influencer
from report.filters import LessorReportFilter, InfluencerReportFilter, FranchiseReportFilter, UserRegistrationReportFilter
from report.permissions import IsAdminRole, ReportsPermission
from report.serializers import LessorReportSerializer, InfluencerReportSerializer, FranchiseReportSerializer, \
    UserReportSerializer, FranchiseReportSerializerV2


@extend_schema(summary="Отчеты. Арендодатели", description="Отчеты. Арендодатели.")
class LessorReportView(ListAPIView):
    serializer_class = LessorReportSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = LessorReportFilter
    permission_classes = [ReportsPermission]

    def get_queryset(self):
        queryset = Lessor.objects.select_related('user').distinct()
        filters = {}

        city = self.request.query_params.get('city')
        if city:
            filters['user__vehicle__city'] = city

        lessor_id = self.request.query_params.get('lessor_id')
        if lessor_id:
            filters['id'] = lessor_id

        return queryset.filter(**filters) if filters else queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['period'] = self.request.query_params.get('period')
        return context

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if request.user.role == 'manager':
            cities = request.user.manager.cities.values_list('id', flat=True)
            if cities.exists():
                queryset = queryset.filter(user__vehicle__city__in=cities).distinct()
        page = self.paginate_queryset(queryset)
        if page is not None:
            queryset_to_serialize = page
        else:
            queryset_to_serialize = queryset

        serializer = self.get_serializer(queryset_to_serialize, many=True)
        data = serializer.data

        total_revenue = Decimal('0.00')
        total_commission = Decimal('0.00')

        for item in data:
            total_revenue += Decimal(str(item['total_revenue']))
            total_commission += Decimal(str(item['commission_amount']))

        response_data = {
            'total_revenue': round(float(total_revenue), 2),
            'total_commission': round(float(total_commission), 2),
            'lessors_count': queryset.count(),
        }

        if page is not None:
            result = self.get_paginated_response(data)
            result.data.update(response_data)
            return result

        return Response({
            **response_data,
            'results': data
        })


@extend_schema(summary="Отчеты. Партнеры", description="Отчеты. Партнеры.")
class InfluencerReportView(ListAPIView):
    serializer_class = InfluencerReportSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = InfluencerReportFilter
    permission_classes = [ReportsPermission]

    def get_queryset(self):
        return Influencer.objects.select_related('user').all()

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())

            # Передаем период и город в контекст сериализатора
            period = request.query_params.get('period')
            city = request.query_params.get('city')
            serializer_context = {
                'period': period,
                'city': city
            }

            # Считаем общие суммы
            total_revenue = Decimal('0.00')
            total_commission = Decimal('0.00')

            # Получаем данные по каждому инфлюенсеру
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True, context=serializer_context)
                result = self.get_paginated_response(serializer.data)
                data = result.data
            else:
                serializer = self.get_serializer(queryset, many=True, context=serializer_context)
                data = serializer.data

            # Подсчитываем общие суммы
            for item in serializer.data:
                total_revenue += Decimal(str(item['revenue']))
                total_commission += Decimal(str(item['commission']))

            # Формируем итоговый ответ
            response_data = {
                'total_revenue': float(total_revenue),
                'total_commission': float(total_commission),
                'lessors_count': queryset.count(),
            }

            # Если есть пагинация
            if isinstance(data, dict):
                data.update(response_data)
                return Response(data)

            # Если нет пагинации
            return Response({
                **response_data,
                'results': data
            })
        except Exception as e:
            raise


@extend_schema(summary="Отчеты. Франшизы", description="Отчеты. Франшизы.", deprecated=True)
class FranchiseReportView(ListAPIView):
    serializer_class = FranchiseReportSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = FranchiseReportFilter
    permission_classes = [ReportsPermission]

    def get_queryset(self):
        return Franchise.objects.all()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        period = self.request.query_params.get('period')
        context['period'] = period
        return context

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            result = self.get_paginated_response(serializer.data)
            data = result.data
        else:
            serializer = self.get_serializer(queryset, many=True)
            data = serializer.data

        total_completed_amount = sum(item['completed_orders_amount'] for item in serializer.data)
        total_lessors_commission = sum(item['lessors_commission'] for item in serializer.data)
        total_canceled_amount = sum(item['canceled_orders_amount'] for item in serializer.data)
        total_franchise_commission = sum(item['franchise_commission_amount'] for item in serializer.data)
        total_canceled_count = sum(item['canceled_orders_count'] for item in serializer.data)

        response_data = {
            'total_completed_amount': total_completed_amount,
            'total_lessors_commission': total_lessors_commission,
            'total_canceled_count': total_canceled_count,
            'total_canceled_amount': total_canceled_amount,
            'total_franchise_commission': total_franchise_commission
        }

        if isinstance(data, dict):
            data.update(response_data)
            return Response(data)

        return Response({
            **response_data,
            'results': data
        })


@extend_schema(summary="Отчеты. Франшизы", description="Отчеты. Франшизы.")
class FranchiseReportViewV2(ListAPIView):
    serializer_class = FranchiseReportSerializerV2
    filter_backends = [DjangoFilterBackend]
    filterset_class = FranchiseReportFilter
    permission_classes = [ReportsPermission]

    def get_queryset(self):
        return Franchise.objects.all()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        period = self.request.query_params.get('period')
        context['period'] = period
        return context

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        if request.user.role == 'manager':
            cities = request.user.manager.cities.all().values_list('id', flat=True)
            if cities:
                queryset = queryset.filter(city__in=cities)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            result = self.get_paginated_response(serializer.data)
            data = result.data
        else:
            serializer = self.get_serializer(queryset, many=True)
            data = serializer.data

        # Подсчет общих сумм по всем типам транспорта
        total_completed_amount = 0
        total_lessors_commission = 0
        total_canceled_count = 0
        total_canceled_amount = 0
        total_franchise_commission = 0

        vehicle_types = ['auto', 'bike', 'ship', 'helicopter', 'specialtechnic']

        for item in serializer.data:
            for vehicle_type in vehicle_types:
                vehicle_data = item[vehicle_type]
                total_completed_amount += vehicle_data['completed_orders_amount']
                total_lessors_commission += vehicle_data['lessors_commission']
                total_canceled_count += vehicle_data['canceled_orders_count']
                total_canceled_amount += vehicle_data['canceled_orders_amount']
                total_franchise_commission += vehicle_data['franchise_commission_amount']

        response_data = {
            'total_completed_amount': total_completed_amount,
            'total_lessors_commission': total_lessors_commission,
            'total_canceled_count': total_canceled_count,
            'total_canceled_amount': total_canceled_amount,
            'total_franchise_commission': total_franchise_commission
        }

        if isinstance(data, dict):
            data.update(response_data)
            return Response(data)

        return Response({
            **response_data,
            'results': data
        })


@extend_schema(summary="Отчеты. Регистрация пользователей", description="Отчеты. Регистрация пользователей.")
class UserRegistrationReportView(ListAPIView):
    serializer_class = UserReportSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = UserRegistrationReportFilter
    permission_classes = [ReportsPermission]

    def get_queryset(self):
        queryset = User.objects.all()
        return self.filter_queryset(queryset).values('platform').annotate(count=Count('id'))

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        total_users = sum(item['count'] for item in queryset)

        return Response({
            "total_users": total_users,
            "platforms": self.get_serializer(queryset, many=True).data
        })
