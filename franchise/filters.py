import django_filters
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from chat.models import Trip
from vehicle.models import VehicleModel, VehicleBrand, Vehicle


class LessorStatisticsFilter(django_filters.FilterSet):
    vehicle_type = django_filters.ChoiceFilter(
        method='filter_vehicle_type',
        choices=VehicleModel.VEHICLE_TYPES
    )
    brand = django_filters.ModelChoiceFilter(
        queryset=VehicleBrand.objects.all(),
        method='filter_vehicle_brand'
    )
    model = django_filters.ModelChoiceFilter(
        queryset=VehicleModel.objects.all(),
        method='filter_vehicle_model'
    )

    def filter_vehicle_type(self, queryset, name, value):
        vehicle_cts = ContentType.objects.filter(
            model__in=[model[0] for model in VehicleModel.VEHICLE_TYPES if model[0] == value]
        )

        return queryset.filter(
            content_type__in=vehicle_cts
        )

    def filter_vehicle_brand(self, queryset, name, value):
        vehicle_cts = ContentType.objects.filter(
            model__in=['auto', 'bike', 'ship', 'helicopter', 'specialtechnic']
        )

        return queryset.filter(
            Q(content_type__in=vehicle_cts) &
            Q(object_id__in=Vehicle.objects.filter(brand=value).values_list('id', flat=True))
        )

    def filter_vehicle_model(self, queryset, name, value):
        vehicle_cts = ContentType.objects.filter(
            model__in=['auto', 'bike', 'ship', 'helicopter', 'specialtechnic']
        )

        return queryset.filter(
            Q(content_type__in=vehicle_cts) &
            Q(object_id__in=Vehicle.objects.filter(model=value).values_list('id', flat=True))
        )

    class Meta:
        model = Trip
        fields = ['vehicle_type', 'brand', 'model']
