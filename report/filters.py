from datetime import timedelta
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.utils import timezone
from django.utils.timezone import now
from django_filters import rest_framework as filters

from app.models import Lessor, Renter, User
from chat.models import Trip
from franchise.models import City, Franchise
from influencer.models import Influencer
from vehicle.models import Vehicle


class LessorReportFilter(filters.FilterSet):
    period = filters.ChoiceFilter(
        choices=[('day', 'День'),
                 ('week', 'Неделя'),
                 ('month', 'Месяц'),
                 ('quarter', 'Квартал'),
                 ('year', 'Год')],
        method='filter_period'
    )
    city = filters.ModelChoiceFilter(
        queryset=City.objects.all(),
        field_name='user__vehicle__city'
    )
    lessor_id = filters.NumberFilter(field_name='id')

    def filter_period(self, queryset, name, value):
        return self.get_filtered_queryset(queryset, value)

    def get_filtered_queryset(self, queryset, period):
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
        else:
            return queryset

        vehicle_types = ['auto', 'bike', 'ship', 'helicopter', 'specialtechnic']

        vehicle_query = Q()
        for vehicle_type in vehicle_types:
            content_type = ContentType.objects.get(model=vehicle_type)
            vehicle_query |= Q(
                user__vehicle__polymorphic_ctype=content_type,
            )

        trips = Trip.objects.filter(
            end_date__gte=start_date,
            status='finished'
        ).values_list('object_id', 'content_type')

        lessor_query = Q()
        for object_id, content_type_id in trips:
            lessor_query |= Q(
                user__vehicle__polymorphic_ctype_id=content_type_id,
                user__vehicle__id=object_id
            )

        return queryset.filter(lessor_query).distinct()

    class Meta:
        model = Lessor
        fields = ['period', 'city', 'lessor_id']


class InfluencerReportFilter(filters.FilterSet):
    period = filters.ChoiceFilter(
        choices=[
            ('day', 'День'),
            ('week', 'Неделя'),
            ('month', 'Месяц'),
            ('quarter', 'Квартал'),
            ('year', 'Год')
        ],
        method='filter_period'
    )
    city = filters.ModelChoiceFilter(
        queryset=City.objects.all(),
        method='filter_by_city'
    )
    influencer_id = filters.NumberFilter(field_name='id')

    class Meta:
        model = Influencer
        fields = ['period', 'city', 'influencer_id']

    def filter_period(self, queryset, name, value):
        return queryset

    def filter_by_city(self, queryset, name, value):
        if not value:
            return queryset

        vehicle_types = ['auto', 'bike', 'ship', 'helicopter', 'specialtechnic']
        city_vehicles_query = Q()

        for vehicle_type in vehicle_types:
            content_type = ContentType.objects.get(model=vehicle_type)
            vehicles = Vehicle.objects.filter(
                city=value,
                polymorphic_ctype=content_type
            ).values_list('id', flat=True)

            if vehicles:
                city_vehicles_query |= Q(
                    content_type=content_type,
                    object_id__in=vehicles
                )

        trips_in_city = Trip.objects.filter(city_vehicles_query)

        renters_in_city = Renter.objects.filter(
            user__in=trips_in_city.values_list('organizer_id', flat=True)
        )

        return queryset.filter(renters__in=renters_in_city).distinct()


class FranchiseReportFilter(filters.FilterSet):
    period = filters.ChoiceFilter(
        choices=[
            ('day', 'День'),
            ('week', 'Неделя'),
            ('month', 'Месяц'),
            ('quarter', 'Квартал'),
            ('year', 'Год')
        ],
        method='filter_period'
    )
    city = filters.ModelChoiceFilter(queryset=City.objects.all(), field_name='city')
    franchise_id = filters.NumberFilter(field_name='id')

    class Meta:
        model = Franchise
        fields = ['period', 'city', 'franchise_id']

    def filter_period(self, queryset, name, value):
        return queryset


class UserRegistrationReportFilter(filters.FilterSet):
    period = filters.ChoiceFilter(
        choices=[
            ('day', 'День'),
            ('week', 'Неделя'),
            ('month', 'Месяц'),
            ('quarter', 'Квартал'),
            ('year', 'Год'),
        ],
        method='filter_by_period'
    )

    class Meta:
        model = User
        fields = ['period']

    def filter_by_period(self, queryset, name, value):
        date_lookup = {
            'day': now().date(),
            'week': now() - timedelta(days=7),
            'month': now() - timedelta(days=30),
            'quarter': now() - timedelta(days=90),
            'year': now() - timedelta(days=365),
        }
        return queryset.filter(date_joined__gte=date_lookup.get(value, now().date()))
