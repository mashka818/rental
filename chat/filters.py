import django_filters
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend

from app.models import Lessor
from chat.models import Message, Trip, RequestRent
from vehicle.models import Auto, Bike, Ship, Helicopter, SpecialTechnic


class MessageFilter(django_filters.FilterSet):
    chat_id = django_filters.NumberFilter(field_name='chat__id')
    ordering = django_filters.OrderingFilter(fields=['timestamp'])

    class Meta:
        model = Message
        fields = ['chat_id']


class BaseFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name='status', label='Статус')
    lessor_id = django_filters.NumberFilter(method='filter_by_lessor', label='ID арендодателя')

    class Meta:
        abstract = True

    def filter_by_lessor(self, queryset, name, value):
        request = self.request

        if request.user.role not in ['admin', 'manager'] and not hasattr(request.user, 'franchise'):
            return queryset

        lessor = Lessor.objects.filter(id=value).first()
        if not lessor:
            return queryset.none()

        content_types = {
            model: ContentType.objects.get_for_model(model)
            for model in [Auto, Bike, Ship, Helicopter, SpecialTechnic]
        }

        vehicle_ids = {
            content_type: content_type.model_class().objects.filter(owner=lessor.user).values_list('id', flat=True)
            for model, content_type in content_types.items()
        }

        q_objects = Q()
        for content_type, ids in vehicle_ids.items():
            q_objects |= Q(content_type=content_type, object_id__in=ids)

        return queryset.filter(q_objects)


class TripFilter(BaseFilter):
    class Meta:
        model = Trip
        fields = ['status']


class RequestRentFilter(BaseFilter):
    class Meta:
        model = RequestRent
        fields = ['status']


class TripFilterBackend(DjangoFilterBackend):
    def get_filterset_kwargs(self, request, queryset, view):
        kwargs = super().get_filterset_kwargs(request, queryset, view)
        kwargs['request'] = request
        return kwargs

