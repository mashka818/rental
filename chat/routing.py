from django.urls import re_path, path
from chat import consumers

websocket_urlpatterns = [
    re_path(r'ws/chat/(?P<chat_id>\d+)/$', consumers.ChatConsumer.as_asgi()),
    path('ws/support_chat/<int:chat_id>/', consumers.ChatSupportConsumer.as_asgi()),
]
