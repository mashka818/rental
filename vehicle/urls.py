from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import VehicleBrandViewSet, VehicleModelViewSet, AutoViewSet, BikeViewSet, ShipViewSet, HelicopterViewSet, \
    SpecialTechnicViewSet, UpdateRatingView, gps_tracking_view, \
    AutoFeaturesAdditionallyListView, BikeFeaturesAdditionallyListView, ShipFeaturesAdditionallyListView, \
    FeaturesForChildrenListView, FeaturesEquipmentListView, PaymentMethodListView, BikeTransmissionListView, \
    AutoTransmissionListView, AutoFuelTypeListView, AutoBodyTypeListView, VehicleClassListView, AllVehiclesListView, \
    VehiclePhotoDeleteView, VehicleSearchViewSet, DeleteVehicleDocumentView, UpdatePhotoOrderView, \
    AutoFeaturesFunctionsListView, BikeFeaturesFunctionsListView, ShipFeaturesFunctionsListView, ShipTypeListView, \
    TechnicTypeListView, BikeBodyTypeListView, UnverifiedVehicleCountView

router = DefaultRouter()
router.register(r'brands', VehicleBrandViewSet)
router.register(r'models', VehicleModelViewSet)
router.register(r'autos', AutoViewSet)
router.register(r'bikes', BikeViewSet)
router.register(r'ships', ShipViewSet)
router.register(r'helicopters', HelicopterViewSet)
router.register(r'special-technics', SpecialTechnicViewSet)
router.register(r'vehicle_search', VehicleSearchViewSet, basename='search_vehicle')

urlpatterns = [
    path('', include(router.urls)),
    path('update-rating/', UpdateRatingView.as_view(), name='update-rating'),
    path('auto_functions/', AutoFeaturesFunctionsListView.as_view(), name='auto_functions'),
    path('auto_features/', AutoFeaturesAdditionallyListView.as_view(), name='auto_features'),
    path('bike_functions/', BikeFeaturesFunctionsListView.as_view(), name='bike_functions'),
    path('bike_features/', BikeFeaturesAdditionallyListView.as_view(), name='bike_features'),
    path('ship_features/', ShipFeaturesAdditionallyListView.as_view(), name='ship_features'),
    path('ship_functions/', ShipFeaturesFunctionsListView.as_view(), name='ship_functions'),
    path('auto_for_children/', FeaturesForChildrenListView.as_view(), name='for_children_features'),
    path('ship_equipment/', FeaturesEquipmentListView.as_view(), name='equipment_features'),
    path('payment_method/', PaymentMethodListView.as_view(), name='payment_method'),

    path('bike_transmission/', BikeTransmissionListView.as_view(), name='bike_transmission'),
    path('auto_fuel_type/', AutoFuelTypeListView.as_view(), name='auto_fuel_type'),
    path('auto_transmission/', AutoTransmissionListView.as_view(), name='auto_transmission'),
    path('auto_body_type/', AutoBodyTypeListView.as_view(), name='auto_body_type'),
    path('bike_body_type/', BikeBodyTypeListView.as_view(), name='bike_body_type'),
    path('ship_type/', ShipTypeListView.as_view(), name='ship_body_type'),
    path('technic_type/', TechnicTypeListView.as_view(), name='technic_body_type'),
    path('vehicle_class/', VehicleClassListView.as_view(), name='vehicle_class'),

    path('all_vehicles/', AllVehiclesListView.as_view(), name='all_vehicles'),
    path('ws/gps_tracking/<int:vehicle_id>/', gps_tracking_view, name='gps_tracking'),
    path('photos/<int:photo_id>/delete/', VehiclePhotoDeleteView.as_view(), name='delete_vehicle_photo'),
    path('photos/update_order/', UpdatePhotoOrderView.as_view(), name='update_order_photo'),
    path('documents/delete/<int:document_id>/', DeleteVehicleDocumentView.as_view(), name='delete-vehicle-document'),
    path('count_unverified/', UnverifiedVehicleCountView.as_view(), name='count_unverified'),
]
