from datetime import timedelta, datetime
import datetime
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from rest_framework import serializers
from decimal import Decimal
from django.db.models import Sum, Max, Q, Avg

from app.models import Lessor, User
from chat.models import Trip
from franchise.models import Franchise
from influencer.models import Influencer
from vehicle.models import Vehicle


class LessorReportSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField()
    last_name = serializers.CharField(source='user.last_name')
    first_name = serializers.CharField(source='user.first_name')
    avatar = serializers.ImageField(source='user.avatar')
    telephone = serializers.CharField(source='user.telephone')
    total_revenue = serializers.SerializerMethodField()
    commission_amount = serializers.SerializerMethodField()
    last_rent_date = serializers.SerializerMethodField()

    class Meta:
        model = Lessor
        fields = ['id', 'last_name', 'first_name', 'avatar', 'telephone', 'franchise',
                  'total_revenue', 'commission_amount', 'last_rent_date']

    def get_trips_for_lessor(self, lessor):
        vehicle_types = ['auto', 'bike', 'ship', 'helicopter', 'specialtechnic']
        period = self.context.get('period')

        print(f"\nProcessing lessor: {lessor.id} - {lessor.user.first_name} {lessor.user.last_name}")

        trips_query = None

        # Собираем все транспортные средства арендодателя по типам
        for vehicle_type in vehicle_types:
            content_type = ContentType.objects.get(model=vehicle_type)
            vehicles = Vehicle.objects.filter(
                owner=lessor.user,
                polymorphic_ctype=content_type
            )

            if vehicles.exists():
                print(f"Found {vehicle_type} vehicles: {list(vehicles.values_list('id', flat=True))}")

                current_query = Q(
                    content_type=content_type,
                    object_id__in=vehicles.values_list('id', flat=True)
                )

                if trips_query is None:
                    trips_query = current_query
                else:
                    trips_query |= current_query

        if trips_query is None:
            print("No vehicles found for lessor")
            return Trip.objects.none()

        # Базовый запрос поездок для конкретного арендодателя
        trips = Trip.objects.filter(trips_query, status='finished')
        print(f"Initial trips query: {trips.query}")
        print(f"Found trips count: {trips.count()}")

        # Применяем фильтр по периоду
        if period:
            today = timezone.now().date()
            if period == 'day':
                start_date = today
            elif period == 'week':
                start_date = today - timedelta(days=7)
            elif period == 'month':
                start_date = today - timedelta(days=30)
            elif period == 'quarter':
                start_date = today - timedelta(days=90)
            elif period == 'year':
                start_date = today - timedelta(days=365)

            trips = trips.filter(end_date__gte=start_date)
            print(f"After period filter trips count: {trips.count()}")

        # Выводим детали найденных поездок
        for trip in trips:
            print(
                f"Trip id: {trip.id}, content_type: {trip.content_type}, object_id: {trip.object_id}, total_cost: {trip.total_cost}")

        return trips

    def get_total_revenue(self, obj):
        trips = self.get_trips_for_lessor(obj)
        total = trips.aggregate(total=Sum('total_cost'))['total'] or Decimal('0.00')
        print(f"Total revenue for lessor {obj.id}: {total}")
        return total

    def get_commission_amount(self, obj):
        total_revenue = self.get_total_revenue(obj)
        commission = Decimal(str(total_revenue * obj.commission / 100))
        print(f"Commission for lessor {obj.id}: {commission}")
        return commission

    def get_last_rent_date(self, obj):
        trips = self.get_trips_for_lessor(obj)
        last_date = trips.aggregate(last_date=Max('end_date'))['last_date']
        print(f"Last rent date for lessor {obj.id}: {last_date}")
        return last_date


class InfluencerReportSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField()
    last_name = serializers.CharField(source='user.last_name')
    first_name = serializers.CharField(source='user.first_name')
    avatar = serializers.ImageField(source='user.avatar')
    telephone = serializers.CharField(source='user.telephone')
    revenue = serializers.SerializerMethodField()
    commission = serializers.SerializerMethodField()
    last_rent_date = serializers.SerializerMethodField()

    class Meta:
        model = Influencer
        fields = ['id', 'last_name', 'first_name', 'avatar', 'telephone',
                  'revenue', 'commission', 'last_rent_date']

    def get_revenue(self, obj):
        filters = {}
        context = self.context
        period = context.get('period')
        city = context.get('city')

        if period:
            today = timezone.now().date()
            if period == 'day':
                start_date = today
            elif period == 'week':
                start_date = today - timedelta(days=7)
            elif period == 'month':
                start_date = today - timedelta(days=30)
            elif period == 'quarter':
                start_date = today - timedelta(days=90)
            elif period == 'year':
                start_date = today - timedelta(days=365)

            filters['end_date__gte'] = start_date

        renter_users = obj.renters.values_list('user_id', flat=True)

        # Базовый запрос для поездок
        trips_query = Trip.objects.filter(
            organizer_id__in=renter_users,
            status='finished'
        )

        # Добавляем фильтр по городу
        if city:
            vehicle_types = ['auto', 'bike', 'ship', 'helicopter', 'specialtechnic']
            city_query = Q()

            for vehicle_type in vehicle_types:
                content_type = ContentType.objects.get(model=vehicle_type)
                city_query |= Q(
                    content_type=content_type,
                    object_id__in=Vehicle.objects.filter(
                        city=city,
                        polymorphic_ctype=content_type
                    ).values_list('id', flat=True)
                )

            trips_query = trips_query.filter(city_query)

        # Применяем остальные фильтры и получаем сумму
        total_revenue = trips_query.filter(**filters).aggregate(
            total=Sum('total_cost')
        )['total']

        return float(total_revenue) if total_revenue else 0.00

    def get_commission(self, obj):
        revenue = self.get_revenue(obj)
        return (revenue * obj.commission) / 100

    def get_last_rent_date(self, obj):
        renter_users = obj.renters.values_list('user_id', flat=True)
        city = self.context.get('city')

        trips_query = Trip.objects.filter(
            organizer_id__in=renter_users,
            status='finished'
        )

        if city:
            vehicle_types = ['auto', 'bike', 'ship', 'helicopter', 'specialtechnic']
            city_query = Q()

            for vehicle_type in vehicle_types:
                content_type = ContentType.objects.get(model=vehicle_type)
                city_query |= Q(
                    content_type=content_type,
                    object_id__in=Vehicle.objects.filter(
                        city=city,
                        polymorphic_ctype=content_type
                    ).values_list('id', flat=True)
                )

            trips_query = trips_query.filter(city_query)

        last_date = trips_query.aggregate(
            last_date=Max('end_date')
        )['last_date']

        return last_date


class FranchiseReportSerializer(serializers.ModelSerializer):
    completed_orders_amount = serializers.SerializerMethodField()
    lessors_commission = serializers.SerializerMethodField()
    avg_lessors_commission = serializers.SerializerMethodField()
    canceled_orders_count = serializers.SerializerMethodField()
    canceled_orders_amount = serializers.SerializerMethodField()
    franchise_commission_amount = serializers.SerializerMethodField()

    class Meta:
        model = Franchise
        fields = ['id', 'name', 'city', 'completed_orders_amount',
                  'lessors_commission', 'avg_lessors_commission',
                  'canceled_orders_count', 'canceled_orders_amount',
                  'franchise_commission_amount']

    def get_trips_for_franchise(self, obj, status=None):
        """Получает все поездки для транспортных средств в городе франшизы с учетом периода"""
        vehicle_types = ['auto', 'bike', 'ship', 'helicopter', 'specialtechnic']
        trips_query = Q()

        for vehicle_type in vehicle_types:
            content_type = ContentType.objects.get(model=vehicle_type)
            vehicles = Vehicle.objects.filter(
                city=obj.city,
                polymorphic_ctype=content_type
            ).values_list('id', flat=True)

            if vehicles:
                trips_query |= Q(
                    content_type=content_type,
                    object_id__in=vehicles
                )

        filters = {'status': status} if status else {}

        period = self.context.get('period')
        if period:
            start_date, end_date = obj.get_date_range(period)
            if start_date and end_date:
                filters.update({
                    'end_date__gte': start_date,
                    'end_date__lte': end_date
                })

        return Trip.objects.filter(trips_query, **filters)

    def get_completed_orders_amount(self, obj):
        """Сумма выполненных заказов"""
        completed_trips = self.get_trips_for_franchise(obj, status='finished')
        total = completed_trips.aggregate(
            total=Sum('total_cost')
        )['total']
        return float(total) if total else 0.00

    def get_lessors_commission(self, obj):
        """Комиссия арендодателей"""
        completed_trips = self.get_trips_for_franchise(obj, status='finished')

        total_commission = Decimal('0.00')
        for trip in completed_trips:
            vehicle = trip.vehicle
            if hasattr(vehicle, 'owner') and hasattr(vehicle.owner, 'lessor'):
                lessor = vehicle.owner.lessor
                commission = (Decimal(str(trip.total_cost)) * lessor.commission) / 100
                total_commission += commission

        return float(total_commission)

    def get_avg_lessors_commission(self, obj):
        """Средний процент комиссии у lessors"""
        lessors = Lessor.objects.filter(
            user__vehicle__city=obj.city
        ).distinct()

        avg_commission = lessors.aggregate(
            avg_commission=Avg('commission')
        )['avg_commission']

        return float(avg_commission) if avg_commission else 0.00

    def get_canceled_orders_count(self, obj):
        """Количество отмененных заказов"""
        return self.get_trips_for_franchise(obj, status='canceled').count()

    def get_canceled_orders_amount(self, obj):
        """Сумма отмененных заказов"""
        canceled_trips = self.get_trips_for_franchise(obj, status='canceled')
        total = canceled_trips.aggregate(
            total=Sum('total_cost')
        )['total']
        return float(total) if total else 0.00

    def get_franchise_commission_amount(self, obj):
        """Комиссия франшизы от всех заказов"""
        all_trips = self.get_trips_for_franchise(obj, status='finished')
        total_cost = all_trips.aggregate(
            total=Sum('total_cost')
        )['total'] or Decimal('0.00')

        return float((Decimal(str(total_cost)) * obj.commission) / 100)


class FranchiseReportSerializerV2(serializers.ModelSerializer):
    auto = serializers.SerializerMethodField()
    bike = serializers.SerializerMethodField()
    ship = serializers.SerializerMethodField()
    helicopter = serializers.SerializerMethodField()
    specialtechnic = serializers.SerializerMethodField()

    class Meta:
        model = Franchise
        fields = ['id', 'name', 'city', 'auto', 'bike', 'ship', 'helicopter', 'specialtechnic']

    def get_trips_for_vehicle_type(self, obj, vehicle_type, status=None):
        """Получает поездки для конкретного типа транспорта"""
        content_type = ContentType.objects.get(model=vehicle_type)
        vehicles = Vehicle.objects.filter(
            city=obj.city,
            polymorphic_ctype=content_type
        ).values_list('id', flat=True)

        filters = {'status': status} if status else {}
        filters.update({
            'content_type': content_type,
            'object_id__in': vehicles
        })

        period = self.context.get('period')
        if period:
            start_date, end_date = obj.get_date_range(period)
            if start_date and end_date:
                filters.update({
                    'end_date__gte': start_date,
                    'end_date__lte': end_date
                })

        return Trip.objects.filter(**filters)

    def get_vehicle_type_data(self, obj, vehicle_type):
        """Получает все метрики для конкретного типа транспорта"""
        # Получаем завершенные поездки
        completed_trips = self.get_trips_for_vehicle_type(obj, vehicle_type, status='finished')
        completed_amount = completed_trips.aggregate(
            total=Sum('total_cost')
        )['total']
        completed_amount = float(completed_amount) if completed_amount else 0.00

        # Комиссия арендодателей
        total_commission = Decimal('0.00')
        for trip in completed_trips:
            vehicle = trip.vehicle
            if hasattr(vehicle, 'owner') and hasattr(vehicle.owner, 'lessor'):
                lessor = vehicle.owner.lessor
                commission = (Decimal(str(trip.total_cost)) * lessor.commission) / 100
                total_commission += commission

        # Средний процент комиссии
        lessors = Lessor.objects.filter(
            user__vehicle__city=obj.city,
            user__vehicle__polymorphic_ctype=ContentType.objects.get(model=vehicle_type)
        ).distinct()
        avg_commission = lessors.aggregate(
            avg_commission=Avg('commission')
        )['avg_commission']
        avg_commission = float(avg_commission) if avg_commission else 0.00

        # Отмененные заказы
        canceled_trips = self.get_trips_for_vehicle_type(obj, vehicle_type, status='canceled')
        canceled_amount = canceled_trips.aggregate(
            total=Sum('total_cost')
        )['total']
        canceled_amount = float(canceled_amount) if canceled_amount else 0.00

        # Комиссия франшизы
        franchise_commission = float((Decimal(str(total_commission)) * obj.commission) / 100)
        # Процент отмененных поездок
        total_trips = canceled_trips.count() + completed_trips.count()
        percent_canceled_trips = (
            (canceled_trips.count() / total_trips) * 100 if total_trips > 0 else 0
        )
        return {
            'completed_orders_amount': completed_amount,
            'lessors_commission': float(total_commission),
            'avg_lessors_commission': avg_commission,
            'canceled_orders_count': canceled_trips.count(),
            'canceled_orders_amount': canceled_amount,
            'franchise_commission_amount': franchise_commission,
            'percent_canceled_trips': percent_canceled_trips
        }

    def get_auto(self, obj):
        return self.get_vehicle_type_data(obj, 'auto')

    def get_bike(self, obj):
        return self.get_vehicle_type_data(obj, 'bike')

    def get_ship(self, obj):
        return self.get_vehicle_type_data(obj, 'ship')

    def get_helicopter(self, obj):
        return self.get_vehicle_type_data(obj, 'helicopter')

    def get_specialtechnic(self, obj):
        return self.get_vehicle_type_data(obj, 'specialtechnic')


class UserReportSerializer(serializers.ModelSerializer):
    platform = serializers.ChoiceField(choices=User.PLATFORMS)
    count = serializers.IntegerField()

    class Meta:
        model = User
        fields = ['platform', 'count']
