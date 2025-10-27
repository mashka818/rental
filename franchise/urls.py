from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import VehicleParkViewSet, RequestsByParkView, ChatsByParkView, FranchiseViewSet, RequestsByFranchiseView, \
    ChatsByFranchiseView, LessorsByFranchiseView, VehiclesByFranchiseView, \
    vehicle_park_statistics, RequestFranchiseCreateView, RequestFranchiseListView, RequestFranchiseDeleteView, \
    CityView, RequestAddLessorViewSet, LessorListView, DeleteLessorFromFranchiseView, LessorStatisticsView, \
    FranchiseStatisticsView, CityRetrieve

router = DefaultRouter()
router.register(r'vehicle_park', VehicleParkViewSet, basename='vehicle_park')
router.register(r'franchise', FranchiseViewSet, basename='franchise')
router.register(r'lessor_add_franchise', RequestAddLessorViewSet, basename='lessor_add_franchise')

urlpatterns = [
    path('vehicle_park/<int:park_id>/chats/', ChatsByParkView.as_view(), name='chats-by-park'),
    path('vehicle_park/<int:park_id>/requests/', RequestsByParkView.as_view(), name='requests-by-park'),
    path('vehicle_park/<int:vehicle_park_id>/statistics/', vehicle_park_statistics, name='vehicle-park-statistics'),

    path('<int:franchise_id>/statistics/', FranchiseStatisticsView.as_view(), name='franchise-statistics'),
    path('<int:franchise_id>/requests/', RequestsByFranchiseView.as_view(), name='requests-by-franchise'),
    path('<int:franchise_id>/chats/', ChatsByFranchiseView.as_view(), name='chats-by-franchise'),
    path('<int:franchise_id>/lessors/', LessorsByFranchiseView.as_view(), name='lessors-by-franchise'),
    path('<int:franchise_id>/vehicles/', VehiclesByFranchiseView.as_view(), name='vehicles-by-franchise'),
    path('lessors/', LessorListView.as_view(), name='lessors'),
    path('delete_lessor/<int:lessor_id>/', DeleteLessorFromFranchiseView.as_view(), name='unlink-lessor'),
    path('lessors_statistic/<int:lessor_id>/', LessorStatisticsView.as_view(), name='lessor-statistic'),
    path('', include(router.urls)),

    path('request-franchise/create/', RequestFranchiseCreateView.as_view(), name='request-franchise-create'),
    path('request-franchise/', RequestFranchiseListView.as_view(), name='request-franchise-list'),
    path('request-franchise/delete/<int:pk>/', RequestFranchiseDeleteView.as_view(), name='request-franchise-delete'),
    path('city/', CityView.as_view(), name='city'),
    path('city/<int:city_id>/', CityRetrieve.as_view(), name='city')
]
