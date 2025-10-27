from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/gps_tracking/(?P<vehicle_id>\w+)/$', consumers.GPSTrackingConsumer.as_asgi())
]