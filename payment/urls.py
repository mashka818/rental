from django.urls import path, include
from rest_framework.routers import DefaultRouter

from payment.views import TinkoffCallbackView, PaymentViewSet

router = DefaultRouter()
router.register(r'payments', PaymentViewSet, basename='payment')

urlpatterns = [
    path('callback/', TinkoffCallbackView.as_view(), name='tinkoff-callback'),
    path('', include(router.urls)),
]