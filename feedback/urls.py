from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FeedbackViewSet, FeedbackRenterViewSet

router = DefaultRouter()
router.register(r'feedbacks', FeedbackViewSet)
router.register(r'feedbacks_renter', FeedbackRenterViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
