from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TripViewSet, ChatViewSet, MessageViewSet, RequestRentViewSet, TopicSupportViewSet, \
    MessageSupportViewSet, IssueSupportViewSet, ChatSupportListView, ChatSupportRetrieveView, UnreadMessagesCountAPIView

router = DefaultRouter()
router.register(r'request_rents', RequestRentViewSet, basename='request')
router.register(r'trips', TripViewSet, basename='trip')
router.register(r'chat', ChatViewSet, basename='chat')
router.register(r'messages', MessageViewSet, basename='message')
router.register(r'topics', TopicSupportViewSet, basename='topic')
router.register(r'support_messages', MessageSupportViewSet, basename='support_message')
router.register(r'support_issue', IssueSupportViewSet, basename='support_issue')

urlpatterns = [
    path('support_chats/', ChatSupportListView.as_view(), name='chat_support_list'),
    path('support_chats/<int:pk>/', ChatSupportRetrieveView.as_view(), name='chat_support_detail'),
    path('count_messages/', UnreadMessagesCountAPIView.as_view(), name='count_unread_messages'),
    path('', include(router.urls)),
]
