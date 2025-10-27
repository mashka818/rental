from django.urls import path
from .views import TripByCityView, CurrentTripByCityView

urlpatterns = [
    path('', TripByCityView.as_view(), name='finished_trip'),
    path('current/', CurrentTripByCityView.as_view(), name='current_trip')
]
