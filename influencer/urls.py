from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ReferralLinkViewSet, InfluencerRequestCreateView, InfluencerRequestListView, \
    InfluencerRequestDeleteView, InfluencerViewSet, QRCodeViewSet, PromoCodeViewSet, ApplyPromoCodeView, \
    InfluencerPaymentsView, InfluencerStatsView, RequestWithdrawViewSet, PromoCodeByTitleAPIView

router = DefaultRouter()
router.register(r'referral-links', ReferralLinkViewSet)
router.register('influencers', InfluencerViewSet)
router.register(r'qr-codes', QRCodeViewSet, basename='qr-code')
router.register(r'promocodes', PromoCodeViewSet, basename='promocode')
router.register(r'request_withdraw', RequestWithdrawViewSet, basename='request_withdraw')


urlpatterns = [
    path('influencer_requests/', InfluencerRequestCreateView.as_view(), name='influencer-request-create'),
    path('influencer_requests/list/', InfluencerRequestListView.as_view(), name='influencer-request-list'),
    path('influencer_requests/delete/<int:pk>/', InfluencerRequestDeleteView.as_view(), name='influencer-request-delete'),
    path('promocodes/apply/', ApplyPromoCodeView.as_view(), name='apply_promocode'),
    path('transactions/<int:influencer_id>/', InfluencerPaymentsView.as_view(), name='transactions'),
    path('statistic/', InfluencerStatsView.as_view(), name='statistic'),
    path('promocode/', PromoCodeByTitleAPIView.as_view(), name='promo-by-title'),
    path('', include(router.urls)),
]
