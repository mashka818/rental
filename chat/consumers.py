import base64
import io
import logging
from decimal import Decimal

from asgiref.sync import sync_to_async
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import transaction
from django.utils import timezone
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
import json

from RentalGuru.settings import HOST_URL
from chat.models import MessageSupport, ChatSupport, Message, Chat, IssueSupport
from manager.permissions import WebSocketPermissionChecker
from notification.models import Notification
from .tasks import translate_message
import re

TRANSACTION_MESSAGE_PATTERN = re.compile(
    r'"status"\s*:\s*".+?"\s*,\s*"organizer_id"\s*:\s*\d+\s*,\s*"vehicle_id"\s*:\s*\d+\s*,\s*'
    r'"vehicle_type"\s*:\s*".+?"\s*,\s*"start_date"\s*:\s*".+?"\s*,\s*"end_date"\s*:\s*".+?"\s*,\s*'
    r'"start_time"\s*:\s*".+?"\s*,\s*"end_time"\s*:\s*".+?"\s*,\s*"total_cost"\s*:\s*\d+(\.\d+)?\s*,\s*'
    r'"deposit_cost"\s*:\s*\d+(\.\d+)?\s*,\s*"delivery_cost"\s*:\s*\d+(\.\d+)?\s*,\s*"delivery"\s*:\s*(true|false)'
)

logger = logging.getLogger(__name__)


class BaseChatConsumer(AsyncWebsocketConsumer):
    """ Базовый чат от кторого наследуются чат на аренду и чат с техподдержкой"""
    language_preferences = {}
    connected_users = {}

    async def connect(self):
        self.chat_id = self.scope['url_route']['kwargs']['chat_id']
        self.chat_group_name = f'chat_{self.chat_id}'

        query_params = dict(x.split('=') for x in self.scope['query_string'].decode().split('&'))
        token = query_params.get('token')
        self.language = query_params.get('lang', 'ru').lower()

        try:
            UntypedToken(token)
        except (InvalidToken, TokenError):
            await self.close()
            return

        self.scope['user'] = await self.get_user_from_token(token)

        if not await self.user_has_access():
            await self.close()
            return

        if self.chat_group_name not in BaseChatConsumer.language_preferences:
            BaseChatConsumer.language_preferences[self.chat_group_name] = {}

        BaseChatConsumer.language_preferences[self.chat_group_name][self.channel_name] = self.language

        if self.chat_group_name not in BaseChatConsumer.connected_users:
            BaseChatConsumer.connected_users[self.chat_group_name] = set()
        BaseChatConsumer.connected_users[self.chat_group_name].add(self.scope['user'].id)

        await self.channel_layer.group_add(
            self.chat_group_name,
            self.channel_name
        )

        await self.accept()
        await self.send_previous_messages()

    @database_sync_to_async
    def get_user_from_token(self, token):
        """ Проверка токена """
        validated_token = JWTAuthentication().get_validated_token(token)
        return JWTAuthentication().get_user(validated_token)

    async def disconnect(self, close_code):
        if self.chat_group_name in BaseChatConsumer.language_preferences:
            BaseChatConsumer.language_preferences[self.chat_group_name].pop(self.channel_name, None)
            if not BaseChatConsumer.language_preferences[self.chat_group_name]:
                BaseChatConsumer.language_preferences.pop(self.chat_group_name, None)

        if hasattr(self, 'scope') and 'user' in self.scope and self.chat_group_name in BaseChatConsumer.connected_users:
            BaseChatConsumer.connected_users[self.chat_group_name].discard(self.scope['user'].id)
            if not BaseChatConsumer.connected_users[self.chat_group_name]:
                BaseChatConsumer.connected_users.pop(self.chat_group_name, None)

        await self.channel_layer.group_discard(
            self.chat_group_name,
            self.channel_name
        )

    async def fetch_messages(self, offset=0, limit=20):
        """ Получение сообщений с пагинацией """
        chat = self.get_chat_instance()
        messages_queryset = self.get_messages_queryset(chat)

        messages = await database_sync_to_async(lambda: list(
            messages_queryset.order_by('-timestamp')[offset:offset + limit]
        ))()

        formatted_messages = [
            self.format_message(message, self.scope['user']) for message in messages
        ]
        return formatted_messages

    async def receive(self, text_data):
        """ Обработка сообщений в сокете """
        try:
            data = json.loads(text_data)

            if 'type' not in data:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Missing "type" field in message'
                }))
                return

            if data['type'] == 'load_previous_messages':
                offset = data.get('offset', 0)
                limit = data.get('limit', 20)
                previous_messages = await self.load_previous_messages(offset, limit)
                await self.send(text_data=json.dumps({
                    'type': 'previous_messages',
                    'messages': previous_messages,
                }))
            elif data['type'] == "mark_as_read":
                await self.mark_message_as_read(data)

            elif 'message' in data and isinstance(data['message'], str):
                await self.handle_send_message({'message': data['message']})
                return

            elif 'message' in data and isinstance(data['message'], dict):
                await self.handle_send_message(data['message'])
                return

            elif 'delete' in data:
                success = await self.handle_delete_message({'message_id': data['delete']})
                if not success:
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': 'Failed to delete message'
                    }))
                return

            elif 'update' in data and 'content' in data:
                success = await self.handle_update_message({
                    'message_id': data['update'],
                    'new_content': data['content']
                })
                if not success:
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': 'Failed to update message'
                    }))
                return

            action = data.get('action')
            if action:
                if action == 'send_message':
                    await self.handle_send_message(data)
                elif action == 'update_message':
                    await self.handle_update_message(data)
                elif action == 'delete_message':
                    await self.handle_delete_message(data)

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Internal server error'
            }))

    async def handle_send_message(self, data):
        message_content = data.get('message') if isinstance(data.get('message'), str) else data.get('content', '')
        user = self.scope['user']

        base64_file = data.get('file')
        file = None
        if base64_file:
            try:
                file_data = base64.b64decode(base64_file.split(',')[-1])
                file_name = data.get('name', 'unnamed_file')
                content_type = data.get('type', 'application/octet-stream')

                file = InMemoryUploadedFile(
                    file=io.BytesIO(file_data),
                    field_name=None,
                    name=file_name,
                    content_type=content_type,
                    size=len(file_data),
                    charset=None
                )
            except Exception as e:
                logger.error(f"Error decoding base64 file: {e}")
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Failed to decode the uploaded file'
                }))
                return False

        try:
            # Сохранение сообщения
            message = await self.save_message(user, message_content, file, self.language)
            message_data = self.format_message(message, user)

            # Уведомления для оффлайн пользователей
            await self.notify_offline_users(user.id)

            # Отправление сообщения всем участникам чата
            await self.channel_layer.group_send(
                self.chat_group_name,
                {
                    'type': 'chat_message',
                    'message': message_data,
                    'action': 'new'
                }
            )
            # Запуск асинхронных переводов для всех языков в группе
            if not TRANSACTION_MESSAGE_PATTERN.search(json.dumps(message_data)):
                if self.chat_group_name in BaseChatConsumer.language_preferences:
                    for channel, lang in BaseChatConsumer.language_preferences[self.chat_group_name].items():
                        if lang != 'original' and lang != self.language and channel != self.channel_name:
                            translate_message.delay(message.id, message_content, lang, channel)

            return True
        except Exception as e:
            logger.error(f"Error saving message: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Internal server error'
            }))
            return False

    async def notify_offline_users(self, sender_id):
        """ Создание уведомлений для оффлайн пользователей """

        chat_participants = await self.get_chat_participants()
        connected_users = BaseChatConsumer.connected_users.get(self.chat_group_name, set())
        offline_users = [user_id for user_id in chat_participants if
                         user_id != sender_id and user_id not in connected_users]

        if offline_users:
            await self.create_notifications_for_users(offline_users)

    @database_sync_to_async
    def get_chat_participants(self):
        """ Получение всех учатников чата """
        return self.get_chat_participant_ids()

    def get_chat_participant_ids(self):
        """
        Абстрактный метод, который будет реализован подклассами для возврата
        списка идентификаторов пользователей, являющихся участниками чата
        """
        raise NotImplementedError

    @database_sync_to_async
    def create_notifications_for_users(self, user_ids):
        """ Создание уведомления """
        from django.contrib.auth import get_user_model
        User = get_user_model()

        users = User.objects.filter(id__in=user_ids)
        for user in users:
            notification = Notification.objects.create(
                user=user,
                content="Получено новое сообщение"
            )
            # Отправляем push-уведомление
            notification.send_notification()

    async def handle_update_message(self, data):
        try:
            message_id = data.get('message_id')
            new_content = data.get('new_content')
            user = self.scope['user']

            updated_message = await self.update_message(message_id, user, new_content)
            if updated_message:
                message_data = self.format_message(updated_message, user)
                await self.channel_layer.group_send(
                    self.chat_group_name,
                    {
                        'type': 'chat_message',
                        'message': message_data,
                        'action': 'update'
                    }
                )
                return True
            return False
        except Exception as e:
            logger.error(f"Error updating message: {str(e)}")
            return False

    async def handle_delete_message(self, data):
        try:
            message_id = data.get('message_id')
            user = self.scope['user']

            if await self.delete_message(message_id, user):
                await self.channel_layer.group_send(
                    self.chat_group_name,
                    {
                        'type': 'chat_message',
                        'message_id': message_id,
                        'action': 'delete'
                    }
                )
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting message: {str(e)}")
            return False

    async def load_previous_messages(self, offset, limit):
        """ Загрузка предыдущих сообщений с учетом offset и limit """
        messages = await self.get_previous_messages(offset, limit)
        return messages

    @database_sync_to_async
    def save_message(self, user, message_content, file=None, language='ru'):
        chat = self.get_chat_instance()
        message = self.create_message_instance(chat, user, message_content, file, language)
        return message

    @database_sync_to_async
    def update_message(self, message_id, user, new_content):
        with transaction.atomic():
            try:
                message = self.get_messages_objects().objects.select_for_update().get(
                    id=message_id,
                    deleted=False
                )
                chat = message.chat
                if message.sender == user or WebSocketPermissionChecker.check_chat_permission(user, chat):
                    message.content = new_content
                    message.save()
                    return message
                return None
            except self.get_messages_objects().DoesNotExist:
                return None

    @database_sync_to_async
    def delete_message(self, message_id, user):
        with transaction.atomic():

            try:
                message = self.get_messages_objects().objects.select_for_update().get(
                    id=message_id,
                    deleted=False
                )
                chat = message.chat
                if message.sender == user or WebSocketPermissionChecker.check_chat_permission(user, chat):
                    message.deleted = True
                    message.save()
                    return True
                return False
            except self.get_messages_objects().DoesNotExist:
                return False

    async def chat_message(self, event):
        """ Обработчик входящих сообщений """
        action = event.get('action', 'new')

        if action == 'delete':
            await self.send(text_data=json.dumps({
                'type': 'delete',
                'message_id': event['message_id']
            }))
        else:
            await self.send(text_data=json.dumps({
                'type': action,
                'message': event['message']
            }, ensure_ascii=False))

    async def chat_message_translated(self, event):
        """ Обработчик для переведенных сообщений """
        await self.send(text_data=json.dumps({
            'type': 'message_translated',
            'message_id': event['message_id'],
            'translated_content': event['translated_content']
        }, ensure_ascii=False))

    @database_sync_to_async
    def user_has_access(self):
        user = self.scope['user']
        if user.is_anonymous:
            return False

        try:
            chat = self.get_chat_instance()
        except self.get_chat_model().DoesNotExist:
            return False

        return self.check_user_access(user, chat)

    @database_sync_to_async
    def get_previous_messages(self, offset=0, limit=20):
        """ Получение предыдущих сообщений с поддержкой пагинации """
        chat = self.get_chat_instance()
        user = self.scope['user']

        if hasattr(chat, 'request_rent'):
            show_all_messages = (
                    user.role in ['admin', 'manager'] or
                    (hasattr(chat.request_rent.vehicle, 'owner') and
                     chat.request_rent.vehicle.owner.lessor.franchise and
                     chat.request_rent.vehicle.owner.lessor.franchise.director == user)
            )
        else:
            show_all_messages = user.role in ['admin', 'manager']

        messages_queryset = self.get_messages_queryset(chat)

        if not show_all_messages:
            messages_queryset = messages_queryset.filter(deleted=False)

        messages = messages_queryset.order_by('-timestamp')[offset:offset + limit]

        message_data_list = []

        for message in reversed(messages):
            message_data = self.format_message(message, message.sender)
            message_data_list.append(message_data)

            if (self.language != 'original' and
                    self.language != getattr(message, 'language', 'ru') and
                    not TRANSACTION_MESSAGE_PATTERN.search(message.content)):
                translate_message.delay(message.id, message.content, self.language, self.channel_name)

        return message_data_list

    async def send_previous_messages(self):
        first_message = await self.get_first_message()
        initial_messages = []
        if first_message:
            initial_messages = [first_message]

        await self.send(text_data=json.dumps({
            'type': 'first_message',
            'messages': initial_messages
        }, ensure_ascii=False))

    @database_sync_to_async
    def get_first_message(self):
        """Получение только самого первого сообщения в чате"""
        chat = self.get_chat_instance()
        user = self.scope['user']
        messages_queryset = self.get_messages_queryset(chat)
        messages_queryset = messages_queryset.filter(deleted=False)
        first_message = messages_queryset.order_by('timestamp').first()

        if first_message:
            message_data = self.format_message(first_message, first_message.sender)
            return message_data
        return None

    async def mark_message_as_read(self, data):
        message_id = data.get("message_id")
        user = self.scope["user"]
        if not user.is_authenticated or not message_id:
            return
        try:
            @database_sync_to_async
            def get_message():
                return self.get_messages_objects().objects.get(id=message_id)
            @database_sync_to_async
            def update_message(message):
                if message.sender.id == user.id:
                    return False

                if not message.is_read:
                    message.is_read = True
                    message.save()
                    return True
                return False

            message = await get_message()
            updated = await update_message(message)

            if updated:
                await self.channel_layer.group_send(
                    self.chat_group_name,
                    {
                        'type': 'message_read',
                        'message_id': message.id
                    }
                )
        except Exception as e:
            logger.error(f"Error marking message as read: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Failed to mark message as read'
            }))

    async def message_read(self, event):
        """Обработчик для прочитанных сообщений"""
        await self.send(text_data=json.dumps({
            'type': 'message_read',
            'message_id': event['message_id']
        }, ensure_ascii=False))

    def format_message(self, message, user):
        """ Форматирование сообщений """
        return {
            'id': message.id,
            'sender': {
                'id': user.id,
                'first_name': user.first_name,
                'avatar': user.avatar.url if user.avatar else None,
            },
            'content': message.content,
            'timestamp': message.timestamp.isoformat(),
            'file': f"{HOST_URL}{message.file.url}" if message.file else None,
            'deleted': message.deleted,
            'is_read': message.is_read
        }

    def get_chat_instance(self):
        raise NotImplementedError

    def get_chat_model(self):
        raise NotImplementedError

    def create_message_instance(self, chat, user, message_content, file, language='ru'):
        raise NotImplementedError

    def get_messages_queryset(self, chat):
        raise NotImplementedError

    def check_user_access(self, user, chat):
        raise NotImplementedError

    def get_messages_objects(self):
        raise NotImplementedError


class ChatConsumer(BaseChatConsumer):
    """ Чат по аренде """
    async def connect(self):
        self.connected_at = timezone.now()
        await super().connect()

    async def receive(self, text_data):
        data = json.loads(text_data)

        if 'update_request_rent' in data:
            data['status'] = 'unknown'
            success = await self.handle_request_rent_update(data['update_request_rent'])
            if success:
                await self.send(text_data=json.dumps({
                    'type': 'update_success',
                    'message': 'RequestRent updated successfully.'
                }))
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Failed to update RequestRent.'
                }))
        elif 'update_status' in data:
            new_status = data['update_status']
            success = await self.handle_request_rent_status_update(new_status)
            if success:
                await self.send(text_data=json.dumps({
                    'type': 'status_update_success',
                    'message':  f"Status updated to {new_status}."
                }))
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Failed to update status.'
                }))
        else:
            await super().receive(text_data)
        await self.update_response_time()

    @database_sync_to_async
    def update_response_time(self):
        """ Обновление среднего времени ответа арендодателя"""
        user = self.scope['user']
        if hasattr(user, 'lessor'):
            response_time = timezone.now() - self.connected_at
            lessor = user.lessor

            if lessor.average_response_time is None:
                lessor.average_response_time = response_time
            elif lessor.count_trip == 0:
                lessor.average_response_time = response_time # Тут бы придумать что-то другое, но и так сойдет
            else:
                total_response_time = lessor.average_response_time * lessor.count_trip
                total_response_time += response_time
                lessor.average_response_time = total_response_time / lessor.count_trip

            lessor.save()

    async def handle_request_rent_update(self, update_data):
        """ Обновление заявки на аренду арендодателем """
        user = self.scope['user']
        chat = await database_sync_to_async(self.get_chat_instance)()
        request_rent = chat.request_rent

        current_status = await database_sync_to_async(lambda: request_rent.status)()
        if current_status == 'accept':
            return False

        vehicle_data = await self.get_vehicle_data(request_rent, user)

        if not vehicle_data['is_valid']:
            return False

        is_owner = vehicle_data['is_owner']
        has_availability = vehicle_data['has_availability']
        request_status = vehicle_data['valid_status']

        if is_owner and has_availability and request_status:
            await self.update_request_rent_fields(request_rent, update_data)

            message_content = await self.prepare_message_content(request_rent)

            await self.handle_send_message({'message': json.dumps(message_content, ensure_ascii=False)})

            return True
        return False

    @database_sync_to_async
    def get_vehicle_data(self, request_rent, user):
        """Получение все данных, связанных с транспортным средством, за одну транзакцию"""
        result = {
            'is_valid': False,
            'is_owner': False,
            'has_availability': False,
            'valid_status': False
        }

        try:
            content_type = request_rent.content_type
            if not content_type:
                return result

            vehicle_model = content_type.model_class()
            vehicle = vehicle_model.objects.get(id=request_rent.object_id)

            result['is_valid'] = True
            result['is_owner'] = user == vehicle.owner
            result['has_availability'] = vehicle.availabilities.filter(on_request=True).exists()
            result['valid_status'] = request_rent.status in ['unknown', 'denied']

            return result
        except Exception as e:
            logger.error(f"Error getting vehicle data: {str(e)}")
            return result

    @database_sync_to_async
    def update_request_rent_fields(self, request_rent, update_data):
        """Обновление полей request_rent"""
        request_rent.status = 'unknown'

        fields_to_update = ['start_time', 'end_time', 'start_date', 'end_date', 'total_cost']
        for field in fields_to_update:
            if field in update_data:
                setattr(request_rent, field, update_data[field])

        if 'content_type' in update_data:
            content_type = ContentType.objects.get(model=update_data['content_type'].lower())
            request_rent.content_type = content_type

        if 'object_id' in update_data:
            request_rent.object_id = update_data['object_id']

        request_rent.save()

    @database_sync_to_async
    def prepare_message_content(self, request_rent):
        """Подготовка данных сообщения"""
        content_type_model = request_rent.content_type.model if request_rent.content_type else "unknown"

        amount = 0
        try:
            content_type = request_rent.content_type
            vehicle_model = content_type.model_class()
            vehicle = vehicle_model.objects.get(id=request_rent.object_id)

            owner = vehicle.owner
            if hasattr(owner, 'lessor'):
                lessor = owner.lessor
                commission_rate = lessor.commission

                amount = Decimal(request_rent.total_cost) / Decimal(100) * Decimal(commission_rate)
                amount = round(float(amount), 2)
        except Exception as e:
            logger.error(f"Error calculating commission: {str(e)}")

        return {
            "start_time": request_rent.start_time,
            "end_time": request_rent.end_time,
            "start_date": request_rent.start_date,
            "end_date": request_rent.end_date,
            "total_cost": request_rent.total_cost,
            "status": request_rent.status,
            "vehicle_type": content_type_model,
            "vehicle_id": request_rent.object_id,
            "amount": amount
        }

    @database_sync_to_async
    def check_request_status(self, request_rent):
        return request_rent.status in ['unknown', 'denied']

    @database_sync_to_async
    def has_on_request_availability(self, vehicle):
        return vehicle.availabilities.filter(on_request=True).exists()

    async def handle_request_rent_status_update(self, update_data):
        """Обновляет статус заявки на аренду (только организатор может обновлять)."""
        user = self.scope['user']
        chat = await database_sync_to_async(self.get_chat_instance)()
        if not chat or not chat.request_rent:
            return False

        request_rent = chat.request_rent
        # проверка текущего статуса заявки
        current_status = await database_sync_to_async(lambda: request_rent.status)()
        if current_status == 'accept':
            return False
        # является ли пользователь организатором
        is_organizer = await database_sync_to_async(lambda: user == request_rent.organizer)()
        if not is_organizer:
            return False

        new_status = update_data.get('status')
        if new_status not in {'accept', 'denied'}:
            return False

        if new_status == 'accept':
            if not await self.check_request_rent_fields(request_rent):
                return False
            vehicle_owner = await database_sync_to_async(lambda: request_rent.vehicle.owner)()
            await self.create_notification(vehicle_owner, "Статус заявки обновлён на: Принято")

        request_rent.status = new_status
        await database_sync_to_async(request_rent.save)()

        message_content = (
            "Статус заявки обновлён на: Принято. Для оплаты перейдите в «Поездки» (Информационное сообщение, отвечать на него не требуется)"
            if new_status == 'accept'
            else "Заявка была отменена клиентом (Информационное сообщение, отвечать на него не требуется)."
        )
        await self.handle_send_message({'message': message_content})
        return True

    @database_sync_to_async
    def create_notification(self, user, content):
        """Создает уведомление для пользователя."""
        Notification.objects.create(user=user, content=content)

    @database_sync_to_async
    def check_request_rent_fields(self, request_rent):
        """Проверяет, что поля не равны None и total_cost больше 0."""
        return all([
            request_rent.start_time is not None,
            request_rent.end_time is not None,
            request_rent.start_date is not None,
            request_rent.end_date is not None,
            request_rent.total_cost > 0
        ])

    async def send_status_update_message(self, chat, message_content):
        """Создает и отправляет сообщение в чат о статусе заявки."""
        user = self.scope['user']
        message = await database_sync_to_async(self.create_message_instance)(chat, user, json.dumps(message_content, ensure_ascii=False), file=None)
        message_data = self.format_message(message, user)

        await self.channel_layer.group_send(
            self.chat_group_name,
            {
                'type': 'chat_message',
                'message': message_data,
                'action': 'status_update'
            }
        )

    @database_sync_to_async
    def get_content_type(self, model_name):
        return ContentType.objects.get(model=model_name.lower())

    def get_chat_instance(self):
        return Chat.objects.select_related(
            'request_rent__organizer', 'request_rent__content_type'
        ).only(
            'id', 'request_rent__id', 'request_rent__organizer__id', 'request_rent__content_type__id', 'request_rent__object_id'
        ).get(id=self.chat_id)

    def create_message_instance(self, chat, user, message_content, file, language):
        return Message.objects.create(chat=chat, sender=user, content=message_content, file=file, language=language)

    def get_messages_queryset(self, chat):
        return chat.messages.order_by('timestamp').select_related(
            'sender'
        ).only(
            'id', 'chat_id', 'sender_id', 'content', 'timestamp', 'file',
            'sender__id', 'sender__first_name', 'sender__avatar', 'deleted'
        )

    def check_user_access(self, user, chat):
        if WebSocketPermissionChecker.check_chat_permission(user, chat):
            return True

        is_franchise_director = (
            hasattr(chat.request_rent.vehicle, 'owner') and
            chat.request_rent.vehicle.owner.lessor.franchise and
            chat.request_rent.vehicle.owner.lessor.franchise.director == user
        )

        return (
            user in chat.participants.all() or
            user == chat.request_rent.organizer or
            user == chat.request_rent.vehicle.owner or
            is_franchise_director
        )

    async def chat_message_translated(self, event):
        """ Обработчик для переведенных сообщений """
        message_id = event['message_id']
        translated_content = event['translated_content']

        await self.send(text_data=json.dumps({
            'type': 'message_translated',
            'message_id': message_id,
            'translated_content': translated_content
        }, ensure_ascii=False))

    def get_messages_objects(self):
        return Message

    def get_chat_model(self):
        return Chat

    def get_chat_participant_ids(self):
        """ Получение ID организатора и владельца транспортного средства для участников чата """
        chat = self.get_chat_instance()
        request_rent = chat.request_rent

        participants = []

        if request_rent.organizer:
            participants.append(request_rent.organizer.id)

        if hasattr(request_rent, 'vehicle') and request_rent.vehicle and hasattr(request_rent.vehicle, 'owner'):
            participants.append(request_rent.vehicle.owner.id)

        return participants


class ChatSupportConsumer(BaseChatConsumer):
    """ Чат техподдержки """

    async def connect(self):
        # Вызываем родительский метод connect
        await super().connect()

        # Отправляем последнюю причину обращения после успешного подключения
        await self.send_last_issue()

    async def send_last_issue(self):
        """Отправка последней причины обращения в чат"""
        last_issue_data = await self.get_last_issue()
        if last_issue_data:
            await self.send(text_data=json.dumps({
                'type': 'last_issue',
                'last_issue': last_issue_data
            }, ensure_ascii=False))

    @database_sync_to_async
    def get_last_issue(self):
        """Получение последней причины обращения для текущего чата"""
        try:
            chat = self.get_chat_instance()
            last_issue = IssueSupport.objects.filter(
                chat=chat
            ).select_related('topic').order_by('-created_at').first()

            if last_issue:
                return {
                    "topic": last_issue.topic.name,
                    "description": last_issue.description or "",
                    "created_at": last_issue.created_at.isoformat()
                }
            return None
        except Exception as e:
            logger.error(f"Error getting last issue: {str(e)}")
            return None

    def get_chat_instance(self):
        return self.get_chat_model().objects.select_related('creator').get(id=self.chat_id)

    def get_chat_model(self):
        return ChatSupport

    def get_messages_objects(self):
        return MessageSupport

    def create_message_instance(self, chat, user, message_content, file, language):
        return MessageSupport.objects.create(chat=chat, sender=user, content=message_content, file=file,
                                             language=language)

    def get_messages_queryset(self, chat):
        return chat.message_support.select_related('sender').order_by('timestamp')

    def check_user_access(self, user, chat):
        if WebSocketPermissionChecker.check_chat_permission(user, chat):
            return True
        return chat.creator == user

    async def chat_message_translated(self, event):
        """ Обработчик для переведенных сообщений """
        message_id = event['message_id']
        translated_content = event['translated_content']

        await self.send(text_data=json.dumps({
            'type': 'message_translated',
            'message_id': message_id,
            'translated_content': translated_content
        }, ensure_ascii=False))

    def get_chat_participant_ids(self):
        """ Получение ID участников чата поддержки (создателя и службы поддержки) """
        chat = self.get_chat_instance()
        participants = []

        if chat.creator:
            participants.append(chat.creator.id)

        from django.contrib.auth import get_user_model
        User = get_user_model()
        support_staff = User.objects.filter(role__in=['admin']).values_list('id', flat=True)
        participants.extend(support_staff)

        return participants