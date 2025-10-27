from django.urls import path, include
from rest_framework.routers import DefaultRouter


from .views import ChangePasswordView, UserViewSet, RenterDocumentsViewSet, UpdateRatingView, \
    CustomTokenObtainPairView, PasswordResetRequestView, VerifyCodeView, \
    SetPasswordView, BecomeLessorView, CurrencyListView, LanguageListView, PhoneSendCode, PhoneVerifyCode, \
    TelegramCallbackView, TelegramRegisterView, SendCodeToEmailView, VerifiedEmailView, \
    FavoriteListView, FavoriteListDeleteView, AddVehicleToFavoriteListView, RemoveVehicleFromFavoriteListView, \
    FavoriteListDetailView, FavoriteListAllVehiclesView, OauthCallback, UserCreateView, PasswordChangeView

from rest_framework_simplejwt.views import TokenRefreshView


router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'renter-documents', RenterDocumentsViewSet, basename='renter-documents')

urlpatterns = [
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('renter/<int:renter_id>/update_rating/', UpdateRatingView.as_view(), name='update_rating'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='password-reset'),
    path('verify_code/', VerifyCodeView.as_view(), name='verify_code'),
    path('password-set/', SetPasswordView.as_view(), name='password-set'),
    path('become_lessor/', BecomeLessorView.as_view(), name='become_lessor'),
    path('currency/', CurrencyListView.as_view(), name='currency'),
    path('language/', LanguageListView.as_view(), name='language'),
    path('phone_send_code/', PhoneSendCode.as_view(), name='phone_send_code'),
    path('phone_verify_code/', PhoneVerifyCode.as_view(), name='phone_verify_code'),
    path('telegram_callback/', TelegramCallbackView.as_view(), name='telegram_callback'),
    path('telegram_register/', TelegramRegisterView.as_view(), name='telegram_register'),
    path('telegram_send_code/', SendCodeToEmailView.as_view(), name='send_code'),
    path('telegram_verified_email/', VerifiedEmailView.as_view(), name='verified_email'),
    path('admin_register_user/', UserCreateView.as_view(), name='register_user'),
    path('admin_change_password/', PasswordChangeView.as_view(), name='change_password'),

    path('favorite_list/', FavoriteListView.as_view(), name='favorite_list'),
    path('favorite_list/all_vehicles/', FavoriteListAllVehiclesView.as_view(), name='all_vehicles_from_favorite_lists'),
    path('favorite_list/<int:id>/', FavoriteListDetailView.as_view(), name='favorite_list_detail'),
    path('favorite_list/<int:pk>/delete/', FavoriteListDeleteView.as_view(), name='delete_favorite_list'),
    path('favorite_list/<int:vehicle_id>/add_vehicle/', AddVehicleToFavoriteListView.as_view(), name='add_vehicle_to_favorite_list'),
    path('favorite_list/<int:vehicle_id>/remove_vehicle/', RemoveVehicleFromFavoriteListView.as_view(), name='remove_vehicle_from_favorite_list'),

    path('oauth_social/', OauthCallback.as_view(), name='oauth_social'),

    path('', include(router.urls))
]
