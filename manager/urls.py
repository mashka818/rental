from django.urls import path, include
from rest_framework.routers import DefaultRouter

from manager.views import AccessTypeViewSet, ManagerViewSet

router = DefaultRouter()
router.register(r'access-types', AccessTypeViewSet, basename='access-types')
router.register(r'managers', ManagerViewSet, basename='managers')

urlpatterns = [
    path('', include(router.urls))
]
