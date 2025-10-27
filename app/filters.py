from django_filters import rest_framework as filters
from .models import RenterDocuments


class RenterDocumentsFilter(filters.FilterSet):
    status = filters.ChoiceFilter(choices=RenterDocuments.STATUS_CHOICES)

    class Meta:
        model = RenterDocuments
        fields = ['status']
