import django_filters
from django.contrib.contenttypes.models import ContentType

from feedback.models import Feedback, FeedbackRenter


class FeedbackFilter(django_filters.FilterSet):
    content_type = django_filters.CharFilter(method='filter_by_content_type')
    object_id = django_filters.NumberFilter()

    class Meta:
        model = Feedback
        fields = ['content_type', 'object_id']

    def filter_by_content_type(self, queryset, name, value):
        try:
            content_type = ContentType.objects.get(model=value.lower())
        except ContentType.DoesNotExist:
            return queryset.none()
        return queryset.filter(content_type=content_type)


class FeedbackRenterFilter(django_filters.FilterSet):
    renter_id = django_filters.NumberFilter(field_name='renter__id', lookup_expr='exact', label="Renter ID")

    class Meta:
        model = FeedbackRenter
        fields = ['renter_id']
