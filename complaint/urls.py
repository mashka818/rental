from django.urls import path, include
from rest_framework.routers import DefaultRouter

from complaint.views import ComplaintViewSet, ComplaintFeedbackViewSet, ComplaintFeedbackRenterViewSet

router = DefaultRouter()
router.register(r'vehicle', ComplaintViewSet)
router.register(r'feedback_lessor', ComplaintFeedbackViewSet)
router.register(r'feedback_renter', ComplaintFeedbackRenterViewSet)

urlpatterns = [
    path('', include(router.urls))
]
