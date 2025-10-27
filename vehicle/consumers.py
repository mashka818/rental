import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class GPSTrackingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.vehicle_id = self.scope['url_route']['kwargs']['vehicle_id']
        self.room_group_name = f'gps_tracking_{self.vehicle_id}'

        # Присоединиться к группе
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Покинуть группу
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Получение сообщения от WebSocket
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        latitude = text_data_json['latitude']
        longitude = text_data_json['longitude']

        # Обновить координаты в базе данных
        await self.update_vehicle_location(latitude, longitude)

        # Отправить сообщение в группу
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'gps_update',
                'latitude': latitude,
                'longitude': longitude
            }
        )

    # Получение сообщения из группы
    async def gps_update(self, event):
        latitude = event['latitude']
        longitude = event['longitude']

        # Отправить сообщение в WebSocket
        await self.send(text_data=json.dumps({
            'latitude': latitude,
            'longitude': longitude
        }))

    @database_sync_to_async
    def update_vehicle_location(self, latitude, longitude):
        from .models import Vehicle
        Vehicle.objects.filter(id=self.vehicle_id).update(latitude=latitude, longitude=longitude)