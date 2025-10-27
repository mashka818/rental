from datetime import timedelta
import django_filters
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.utils import timezone

from chat.models import Trip
from vehicle.models import Vehicle



class TripFilter(django_filters.FilterSet):
    period = django_filters.ChoiceFilter(
        choices=[
            ('day', 'День'),
            ('week', 'Неделя'),
            ('month', 'Месяц'),
            ('quarter', 'Квартал'),
            ('year', 'Год')
        ],
        method='filter_by_period',
        label='Период',
        help_text='Фильтрация по периоду: день, неделя, месяц, квартал, год'
    )
    type = django_filters.CharFilter(
        method='filter_by_type',
        label='Тип',
        help_text='Тип транспортного средства: auto, bike, ship и т.д.'
    )

    lessor_id = django_filters.NumberFilter(
        method='filter_by_owner',
        label='ID арендодателя',
        help_text='Фильтрация по арендодателю'
    )

    city_id = django_filters.NumberFilter(
        method='filter_by_city',
        label='ID города',
        help_text='Фильтрация по городу'
    )

    class Meta:
        model = Trip
        fields = ['status', 'period', 'type', 'lessor_id', 'city_id']

    def filter_by_period(self, queryset, name, value):
        today = timezone.localdate()

        if value == 'day':
            start_date = today
        elif value == 'week':
            start_date = today - timedelta(days=7)
        elif value == 'month':
            start_date = today - timedelta(days=30)
        elif value == 'quarter':
            start_date = today - timedelta(days=90)
        elif value == 'year':
            start_date = today - timedelta(days=365)
        else:
            return queryset
        return queryset.filter(end_date__gte=start_date)

    def filter_by_type(self, queryset, name, value):
        try:
            content_type = ContentType.objects.get(model=value.lower())
            return queryset.filter(content_type=content_type)
        except ContentType.DoesNotExist:
            return queryset.none()

    def filter_by_owner(self, queryset, name, value):
        vehicles = Vehicle.objects.filter(owner__lessor=value)
        return queryset.filter(object_id__in=vehicles.values_list('id', flat=True))

    def filter_by_city(self, queryset, name, value):
        vehicles = Vehicle.objects.filter(city_id=value)
        return queryset.filter(object_id__in=vehicles.values_list('id', flat=True))