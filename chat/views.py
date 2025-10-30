from datetime import datetime
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q, Prefetch, OuterRef, Exists, Subquery, Max
from django.db.models.functions import Coalesce
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import viewsets, permissions, status, filters
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from RentalGuru import settings
from app.models import Lessor, Renter
from manager.permissions import ManagerObjectPermission, ChatsAccess
from notification.models import Notification
from payment.models import Payment
from vehicle.models import Auto, Bike, Ship, Helicopter, SpecialTechnic, Availability, Vehicle
from .filters import MessageFilter, TripFilter, TripFilterBackend, RequestRentFilter
from .models import Trip, Chat, Message, RequestRent, TopicSupport, ChatSupport, MessageSupport, IssueSupport
from .permissions import IsAdminOrOwner, ChatsPermission, ForChatPermission
from .serializers import TripSerializer, ChatSerializer, MessageSerializer, RequestRentSerializer, \
    TopicSupportSerializer, ChatSupportSerializer, MessageSupportSerializer, IssueSupportSerializer, \
    ChatSupportRetrieveSerializer
from rest_framework.exceptions import ValidationError as DRFValidationError, PermissionDenied
from .utils import is_period_contained, subtract_periods


@extend_schema(summary="Поездка",
               description='Поездка',
               parameters=[
                   OpenApiParameter(
                       name="status",
                       description="Статус поездки ('current', 'started', 'finished', 'canceled')",
                       type=str,
                       enum=['current', 'started', 'finished', 'canceled'],
                       required=False,
                   ),
                   OpenApiParameter(
                       name='lessor_id', type=int,
                       description='ID арендодателя (доступно только для admin/manager)'
                   )
               ]
               )
class TripViewSet(viewsets.ModelViewSet):
    serializer_class = TripSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [TripFilterBackend, DjangoFilterBackend]
    filterset_class = TripFilter

    def get_queryset(self):
        user = self.request.user
        queryset = Trip.objects.all()

        # Если админ или менеджер без франшизы, отдаем все поездки
        if user.role == 'admin' or (hasattr(user, 'manager') and not hasattr(user, 'franchise')):
            return queryset

        # Если директор франшизы или менеджер франшизы, показываем поездки, связанные с франшизой
        if hasattr(user, 'franchise') and user.franchise:
            lessor_ids = Lessor.objects.filter(franchise=user.franchise).values_list('id', flat=True)
            vehicle_ids = Vehicle.objects.filter(owner__lessor__id__in=lessor_ids).values_list('id', flat=True)
            return queryset.filter(object_id__in=vehicle_ids)

        # Если арендатор, показываем только его поездки
        if hasattr(user, 'renter'):
            return queryset.filter(organizer=user)

        # Если арендодатель, показываем поездки по его транспорту
        if hasattr(user, 'lessor'):
            vehicle_ids = Vehicle.objects.filter(owner=user).values_list('id', flat=True)
            return queryset.filter(object_id__in=vehicle_ids)

        return Trip.objects.none()

    @action(detail=True, methods=['post'], url_path='cancel-by-client')
    def cancel_by_client(self, request, pk=None):
        """
        Отмена поездки клиентом с автоматическим созданием обращения в техподдержку
        """
        trip = self.get_object()
        
        # Проверяем, что это клиент (арендатор)
        if trip.organizer != request.user:
            return Response(
                {"detail": "Только арендатор может отменить свою поездку."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Проверяем, что поездка еще не отменена/завершена
        if trip.status in ['canceled', 'finished']:
            return Response(
                {"detail": "Поездка уже завершена или отменена."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Обновляем статус через сериализатор для корректной обработки
        serializer = self.get_serializer(trip, data={'status': 'canceled'}, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        # Создаем обращение в техподдержку
        chat_support, _ = ChatSupport.objects.get_or_create(creator=request.user)
        topic, _ = TopicSupport.objects.get_or_create(name="Отмена поездки")
        topic.count += 1
        topic.save()
        
        IssueSupport.objects.create(
            chat=chat_support,
            topic=topic,
            description=f"Отменена поездка #{trip.id} с транспортом {trip.vehicle}"
        )
        
        return Response(
            {"detail": "Поездка отменена. Создано обращение в техподдержку."},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'], url_path='finish-by-client')
    def finish_by_client(self, request, pk=None):
        """
        Завершение поездки клиентом
        """
        trip = self.get_object()
        
        # Проверяем, что это клиент (арендатор)
        if trip.organizer != request.user:
            return Response(
                {"detail": "Только арендатор может завершить свою поездку."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Проверяем, что поездка еще не завершена/отменена
        if trip.status in ['canceled', 'finished']:
            return Response(
                {"detail": "Поездка уже завершена или отменена."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Обновляем статус через сериализатор для корректной обработки
        serializer = self.get_serializer(trip, data={'status': 'finished'}, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(
            {"detail": "Поездка завершена."},
            status=status.HTTP_200_OK
        )


@extend_schema(summary="Чат между арендатором и арендодателем",
               description="""\nЧат между арендатором и арендодателем. 
                                                                                Создается автоматически при создании 
                                                                                заявки на аренду с открытой датой, либо 
                                                                                при принятии заявки на аренду 
                                                                                арендодателем. Чат доступен по адресу:\n 
                    wss://<host_name>/ws/chat/<chat_id>/?token=<JWT>&lang=<lang>\n
                    Пометить сообщение как прочитанное: {"type": "mark_as_read", "message_id": 82}
                    Получение предыдущих сообщений: {"type": "load_previous_messages", "offset": 20, "limit": 10}
                    Отправка сообщения: {"type": "send_message", "message": "hello"}
                    Обновление сообщения: {"type": "update_message", "update": 74, "content": "Hello" }
                    Удаление сообщения: {"type": "delete_message", "delete": 74}
                    Отправка сообщения с файлом: {"type": "send_message", 
                                                  "message": {
                                                              "content": "Hello!",
                                                              "file": "data:image/jpeg;base64,/9j/4AAQS..."
                                                              "name": "example.jpg"                                                              
                                                             }
                                                  }  

                        Обновление заявки со стороны арендодателя: {
                                                                    "update_request_rent": {
                                                                        "content_type": "Auto",
                                                                        "object_id": 7,
                                                                        "start_time": "09:00",
                                                                        "end_time": "18:00",
                                                                        "start_date": "2024-11-01",
                                                                        "end_date": "2024-11-10",
                                                                        "total_cost": "500.00"
                                                                        }
                                                                    }
                        Обновление статуса заявки со стороны арендатора: {
                                                                          "update_status": {
                                                                             "status": "accept"
                                                                             }
                                                                        }""",
               parameters=[
                   OpenApiParameter(
                       name="lessor_id",
                       description="ID арендодателя",
                       type=int,
                       required=False,
                   )]
               )
class ChatViewSet(viewsets.ModelViewSet):
    serializer_class = ChatSerializer
    permission_classes = [IsAuthenticated, (IsAdminOrOwner | ChatsPermission)]

    def get_queryset(self):
        user = self.request.user
        lessor_id = self.request.query_params.get('lessor_id')

        # 1. Админ и обычный менеджер (имеют полный доступ)
        if user.role == 'admin' or (hasattr(user, 'manager') and not hasattr(user, 'franchise')):
            queryset = Chat.objects.all()
            if lessor_id:
                queryset = queryset.filter(
                    Q(request_rent__content_type__model='auto',
                      request_rent__object_id__in=Auto.objects.filter(owner__lessor__id=lessor_id).values('id')) |
                    Q(request_rent__content_type__model='bike',
                      request_rent__object_id__in=Bike.objects.filter(owner__lessor__id=lessor_id).values('id')) |
                    Q(request_rent__content_type__model='ship',
                      request_rent__object_id__in=Ship.objects.filter(owner__lessor__id=lessor_id).values('id')) |
                    Q(request_rent__content_type__model='helicopter',
                      request_rent__object_id__in=Helicopter.objects.filter(owner__lessor__id=lessor_id).values('id')) |
                    Q(request_rent__content_type__model='specialtechnic',
                      request_rent__object_id__in=SpecialTechnic.objects.filter(owner__lessor__id=lessor_id).values(
                          'id'))
                )

        # 2. Директор франшизы или франшизный менеджер (ограничение по франшизе)
        elif hasattr(user, 'franchise') and user.franchise:
            queryset = Chat.objects.filter(
                Q(request_rent__content_type__model='auto',
                  request_rent__object_id__in=Auto.objects.filter(owner__lessor__franchise=user.franchise).values(
                      'id')) |
                Q(request_rent__content_type__model='bike',
                  request_rent__object_id__in=Bike.objects.filter(owner__lessor__franchise=user.franchise).values(
                      'id')) |
                Q(request_rent__content_type__model='ship',
                  request_rent__object_id__in=Ship.objects.filter(owner__lessor__franchise=user.franchise).values(
                      'id')) |
                Q(request_rent__content_type__model='helicopter',
                  request_rent__object_id__in=Helicopter.objects.filter(owner__lessor__franchise=user.franchise).values(
                      'id')) |
                Q(request_rent__content_type__model='specialtechnic',
                  request_rent__object_id__in=SpecialTechnic.objects.filter(
                      owner__lessor__franchise=user.franchise).values('id'))
            )
            if lessor_id:
                queryset = queryset.filter(
                    Q(request_rent__content_type__model='auto',
                      request_rent__object_id__in=Auto.objects.filter(owner__lessor__id=lessor_id).values('id')) |
                    Q(request_rent__content_type__model='bike',
                      request_rent__object_id__in=Bike.objects.filter(owner__lessor__id=lessor_id).values('id')) |
                    Q(request_rent__content_type__model='ship',
                      request_rent__object_id__in=Ship.objects.filter(owner__lessor__id=lessor_id).values('id')) |
                    Q(request_rent__content_type__model='helicopter',
                      request_rent__object_id__in=Helicopter.objects.filter(owner__lessor__id=lessor_id).values('id')) |
                    Q(request_rent__content_type__model='specialtechnic',
                      request_rent__object_id__in=SpecialTechnic.objects.filter(owner__lessor__id=lessor_id).values(
                          'id'))
                )

        # 3. Обычный пользователь (только его чаты)
        else:
            queryset = Chat.objects.filter(participants=user)
        queryset = queryset.annotate(
            last_message_timestamp=Max('messages__timestamp')
        ).order_by('-last_message_timestamp')
        return queryset.distinct()

    def get_permissions(self):
        if hasattr(self.request.user, 'manager') and self.request.user.manager:
            return [ManagerObjectPermission()]
        return super().get_permissions()


@extend_schema(summary="Сообщения чата арендодателя и арендатора", description="Сообщения чата арендодателя и "
                                                                               "арендатора")
class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated, IsAdminOrOwner]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = MessageFilter
    ordering_fields = ['timestamp']

    def get_queryset(self):
        user = self.request.user
        return Message.objects.filter(chat__participants=user)


@extend_schema(summary="Заявка на аренду", description="Заявка на аренду. Создать может только пользователь renter.\
                                                После создания пользователь, который является владельцем транспорта,\
                                                может обновить статус заявки - принять или отклонить (accept|denied).\
                                                При изменении статуса на accept автоматически создается поездка Trip)",
               parameters=[
                   OpenApiParameter(
                       name="status",
                       description="Статус заявки ('accept', 'denied', 'unknown')",
                       type=str,
                       enum=['accept', 'denied', 'unknown'],
                       required=False,
                   ),
                   OpenApiParameter(
                       name='lessor_id', type=int,
                       description='ID арендодателя (доступно только для admin/manager)'
                   )
               ]
               )
class RequestRentViewSet(viewsets.ModelViewSet):
    serializer_class = RequestRentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [TripFilterBackend]
    filterset_class = RequestRentFilter

    def get_queryset(self):
        user = self.request.user
        base_queryset = RequestRent.objects.filter(is_deleted=False)

        payments_subquery = Payment.objects.filter(
            request_rent=OuterRef('pk')
        ).order_by('id')[:1]

        trip_subquery = Trip.objects.filter(
            content_type=OuterRef('content_type'),
            object_id=OuterRef('object_id'),
            status='current'
        ).order_by('id')[:1]

        optimized_queryset = base_queryset.select_related(
            'content_type',
            'promocode'
        ).prefetch_related(
            'chat'
        ).annotate(

            prefetched_payment_id=Subquery(payments_subquery.values('id')),
            prefetched_payment_amount=Subquery(payments_subquery.values('amount')),

            trip_id=Subquery(trip_subquery.values('id')),
            renter_id=Subquery(trip_subquery.values('organizer_id')),
        )

        renter_ids = optimized_queryset.exclude(renter_id=None).values_list('renter_id', flat=True)

        if renter_ids:
            optimized_queryset = optimized_queryset.prefetch_related(
                Prefetch(
                    'organizer__renter',
                    queryset=Renter.objects.filter(user_id__in=renter_ids),
                    to_attr='_prefetched_renter'
                )
            )

        if user.role == 'admin' or (hasattr(user, 'manager') and not hasattr(user, 'franchise')):
            return optimized_queryset

        if hasattr(user, 'franchise') and user.franchise:
            lessor_ids = Lessor.objects.filter(franchise=user.franchise).values_list('id', flat=True)
            vehicle_ids = Vehicle.objects.filter(owner__lessor__id__in=lessor_ids).values_list('id', flat=True)
            return optimized_queryset.filter(object_id__in=vehicle_ids)

        if hasattr(user, 'renter'):
            return optimized_queryset.filter(organizer=user)

        if hasattr(user, 'lessor'):
            content_types = [
                ContentType.objects.get_for_model(model)
                for model in [Auto, Bike, Ship, Helicopter, SpecialTechnic]
            ]

            vehicle_ids = {
                content_type: content_type.model_class().objects.filter(owner=user).values_list('id', flat=True)
                for content_type in content_types
            }

            q_objects = Q()
            for content_type, ids in vehicle_ids.items():
                q_objects |= Q(content_type=content_type, object_id__in=ids)

            return optimized_queryset.filter(q_objects)

        return RequestRent.objects.none()

    def check_permissions(self, request):
        user = self.request.user
        if hasattr(user, 'lessor') and request.method in ['POST']:
            raise PermissionDenied("Арендодатели не могут создавать заявки на аренду.")
        if hasattr(user, 'renter') and request.method in ['PATCH', 'PUT']:
            raise PermissionDenied("Арендаторы не могут обновлять заявки на аренду.")
        super().check_permissions(request)

    def create(self, request, *args, **kwargs):
        self.check_permissions(request)
        vehicle_type = request.data.get('vehicle_type')
        object_id = request.data.get('vehicle_id')

        if not vehicle_type:
            raise DRFValidationError("Требуется указать тип транспортного средства.")
        if not object_id:
            raise DRFValidationError("Требуется идентификатор объекта.")

        vehicle_type = vehicle_type.lower()
        model_mapping = {
            'auto': Auto,
            'bike': Bike,
            'ship': Ship,
            'helicopter': Helicopter,
            'specialtechnic': SpecialTechnic
        }

        model = model_mapping.get(vehicle_type)

        if not model:
            raise DRFValidationError(f"Недопустимый тип транспортного средства: {vehicle_type}")

        try:
            vehicle_instance = model.objects.get(id=object_id)
        except model.DoesNotExist:
            raise DRFValidationError(f"Транспортное средство с идентификатором {object_id} не существует.")

        availabilities = vehicle_instance.availabilities.all()

        # Проверка - сдается ли транспорт только верифицированным пользователям
        # if vehicle_instance.drivers_only_verified and not request.user.renter.verification:
        #     raise DRFValidationError("Транспорт сдается только верифицированным пользователям")

        # Проверка рейтинга арендатора
        renter_rating = request.user.renter.get_average_rating()
        vehicle_rating = vehicle_instance.drivers_rating

        if (
                vehicle_rating is not None and
                renter_rating is not None and
                renter_rating != 0 and
                vehicle_rating > Decimal(renter_rating)
        ):
            raise DRFValidationError("Низкий рейтинг арендатора для данного транспорта")

        if availabilities.filter(on_request=True).exists():
            request_start_date = None
            request_end_date = None
        else:
            request_start_date = request.data.get('start_date')
            request_end_date = request.data.get('end_date')

            if not request_start_date:
                raise DRFValidationError("Обязательна дата начала.")
            if not request_end_date:
                raise DRFValidationError("Обязательна дата окончания.")

            # Преобразование строк в объекты даты
            if isinstance(request_start_date, str):
                request_start_date = datetime.strptime(request_start_date, '%Y-%m-%d').date()
            if isinstance(request_end_date, str):
                request_end_date = datetime.strptime(request_end_date, '%Y-%m-%d').date()

            # Преобразование дат в строки перед передачей в is_period_contained
            sub_period = {
                'start_date': request_start_date.strftime('%Y-%m-%d'),
                'end_date': request_end_date.strftime('%Y-%m-%d')
            }

            # Проверка доступных дат
            availabilities_dates = [
                {
                    'start_date': availability.start_date.strftime('%Y-%m-%d'),
                    'end_date': availability.end_date.strftime('%Y-%m-%d')
                }
                for availability in availabilities
            ]

            if not is_period_contained(availabilities_dates, sub_period):
                raise DRFValidationError("Запрашиваемый период недоступен для данного транспортного средства.")

            # Проверка на минимальное и максимальное количество дней аренды
            # Используем ту же логику что и в RequestRent.rental_days
            rental_days = max(1, (request_end_date - request_start_date).days)
            min_days = vehicle_instance.min_rent_day
            max_days = vehicle_instance.max_rent_day

            # Проверяем, является ли это почасовой арендой
            request_start_time = request.data.get('start_time')
            request_end_time = request.data.get('end_time')
            
            is_hourly_rental = False
            
            if request_start_time and request_end_time and vehicle_instance.rent_prices.filter(name='hour').exists():
                # Считаем количество часов
                if isinstance(request_start_time, str):
                    start_time_obj = datetime.strptime(request_start_time, '%H:%M:%S').time()
                else:
                    start_time_obj = request_start_time
                    
                if isinstance(request_end_time, str):
                    end_time_obj = datetime.strptime(request_end_time, '%H:%M:%S').time()
                else:
                    end_time_obj = request_end_time
                
                start_dt = datetime.combine(request_start_date, start_time_obj)
                end_dt = datetime.combine(request_end_date, end_time_obj)
                total_hours = (end_dt - start_dt).total_seconds() / 3600
                
                # Если < 8 часов - всегда почасовая аренда
                if total_hours < 8:
                    is_hourly_rental = True
                # Если >= 8 часов, проверяем наличие дневного тарифа
                elif total_hours >= 8:
                    has_daily_price = vehicle_instance.rent_prices.filter(name='day').exists()
                    if not has_daily_price:
                        # Нет дневного тарифа - считаем почасовой
                        is_hourly_rental = True

            # Если это НЕ почасовая аренда, проверяем min/max дней
            if not is_hourly_rental:
                if rental_days < min_days or rental_days > max_days:
                    warning_message = (
                        f"Период аренды должен быть между {min_days} и {max_days} днями. "
                        f"Текущий период: {rental_days} дней."
                    )
                    return Response({'warning': warning_message}, status=status.HTTP_400_BAD_REQUEST)

        # Создание записи аренды после всех проверок
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_rent = serializer.save()

        # Отправка уведомлений
        url = f'{settings.HOST_URL}/chat/request_rents/{request_rent.id}'
        content = f'Вам поступила заявка на аренду {vehicle_instance}'
        Notification.objects.create(user=vehicle_instance.owner, content=content, url=url)

        response_data = serializer.data

        if request_rent.on_request:
            chat = Chat.objects.filter(request_rent=request_rent).first()
            if chat:
                response_data['chat_id'] = chat.id

        return Response(response_data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        instance = self.get_object()
        if 'status' in self.request.data:
            new_status = self.request.data['status']

            if new_status not in ['denied', 'accept', 'unknown']:
                raise DRFValidationError("Недопустимый статус.")

            # Обработка отказа заявки
            if new_status == 'denied':
                if instance.owner != self.request.user:
                    raise DRFValidationError("Только владелец транспортного средства может отклонить запрос.")
                denied_reason = self.request.data.get('denied_reason')
                if not denied_reason:
                    raise DRFValidationError("Причина отказа обязательна, если статус заявки — 'denied'.")
                content = f'Вам отказано в аренде транспорта {instance.vehicle} по причине: {denied_reason}'
                url = ''
                Notification.objects.create(user=instance.organizer, content=content, url=url)
                serializer.save(user=self.request.user)

            # Обработка принятия заявки
            if new_status == 'accept':
                if instance.owner != self.request.user:
                    raise DRFValidationError("Только владелец транспортного средства может принять запрос.")

                model = instance.content_type.model_class()
                object_id = instance.object_id
                try:
                    vehicle_instance = model.objects.get(id=object_id)
                except model.DoesNotExist:
                    raise DRFValidationError(f"Транспорт с ID {object_id} не найден.")

                availabilities = list(vehicle_instance.availabilities.values('start_date', 'end_date'))
                if not availabilities:
                    raise DRFValidationError(
                        "Данных о наличии свободных периодов аренды для этого транспорта не найдено.")

                # Преобразование дат в строки
                for availability in availabilities:
                    availability['start_date'] = availability['start_date'].strftime('%Y-%m-%d')
                    availability['end_date'] = availability['end_date'].strftime('%Y-%m-%d')

                sub_period = {'start_date': instance.start_date.strftime('%Y-%m-%d'),
                              'end_date': instance.end_date.strftime('%Y-%m-%d')}
                new_availabilities = subtract_periods(availabilities, sub_period)

                if isinstance(new_availabilities, str):
                    raise DRFValidationError(new_availabilities)

                # Обновление или создание новых объектов Availability
                vehicle_instance.availabilities.all().delete()
                for availability in new_availabilities:
                    Availability.objects.create(
                        vehicle=vehicle_instance,
                        start_date=availability['start_date'],
                        end_date=availability['end_date']
                    )

                # Здесь Trip будет создан в модели RequestRent
                serializer.save(user=self.request.user)

                url = f'{settings.HOST_URL}/chat/request_rents/{instance.id}'
                content = f'Заявка на аренду {vehicle_instance} одобрена. Дата начала {instance.start_date}'
                Notification.objects.create(user=instance.organizer, content=content, url=url)
        else:
            serializer.save(user=self.request.user)

    def partial_update(self, request, *args, **kwargs):
        self.check_permissions(request)
        return super().partial_update(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        self.check_permissions(request)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.save()
        return Response({'detail': 'Заявка удалена.'}, status=status.HTTP_204_NO_CONTENT)


@extend_schema(summary="Тема чата с техподдержкой", description="Тема чата с техподдержкой")
class TopicSupportViewSet(viewsets.ModelViewSet):
    queryset = TopicSupport.objects.all()
    serializer_class = TopicSupportSerializer
    permissions = [IsAuthenticated]


class ChatSupportPagination(LimitOffsetPagination):
    default_limit = 10
    max_limit = 100


@extend_schema(summary="Список чатов техподдержки",
               parameters=[
                   OpenApiParameter(
                       name="limit",
                       description="Количество объектов на странице",
                       required=False,
                       type=int
                   ),
                   OpenApiParameter(
                       name="offset",
                       description="Начальная позиция (смещение)",
                       required=False,
                       type=int
                   ),
               ],

               description="""\nЧат с техподдержкой. Доступен по адресу:\n
                    wss://<host_name>/ws/support_chat/<chat_id>/?token=<JWT>&lang=<lang>\n
                    Чат создается при создании обращения\n
                    Получение предыдущих сообщений: {"type": "load_previous_messages", "offset": 20, "limit": 10}
                    Отправка сообщения: {"type": "send_message", "message": "hello"}
                    Обновление сообщения: {"type": "update_message", "update": 74, "content": "Hello" }
                    Удаление сообщения: {"type": "delete_message", "delete": 74}
                    Отправка сообщения с файлом: {"type": "send_message", 
                                                  "message": {
                                                              "content": "Hello!",
                                                              "file": "data:image/jpeg;base64,/9j/4AAQS..."
                                                              "name": "example.jpg"                                                              
                                                             }
                                                  }  
                    """)
class ChatSupportListView(APIView):
    permission_classes = [ForChatPermission | ChatsAccess]
    ordering = ('-timestamp',)
    def get(self, request, *args, **kwargs):
        user = request.user
        if user.role in ['admin', 'manager']:
            last_message_subquery = MessageSupport.objects.filter(chat_id=OuterRef('pk')).order_by('-timestamp').values("timestamp")[:1]
            chats = ChatSupport.objects.annotate(last_message_timestemp=Coalesce(Subquery(last_message_subquery), datetime(1970, 1, 1))).order_by("-last_message_timestemp").select_related(
                'creator',
                'creator__lessor',
                'creator__renter',
                'creator__influencer',
                'creator__franchise'
            ).all()
            paginator = ChatSupportPagination()
            paginated_chats = paginator.paginate_queryset(chats, request)
            if paginated_chats is None:
                return Response({"detail": "На этой странице нет доступных чатов."}, status=status.HTTP_404_NOT_FOUND)
            serializer = ChatSupportSerializer(paginated_chats, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)
        else:
            chats = ChatSupport.objects.select_related(
                'creator',
                'creator__lessor',
                'creator__renter',
                'creator__influencer',
                'creator__franchise'
            ).filter(creator=user)
            serializer = ChatSupportSerializer(chats, many=True, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(summary="Детальное отображение чата", description="""\nЧат с техподдержкой. Доступен по адресу:\n
                    wss://<host_name>/ws/support_chat/<chat_id>/?token=<JWT>&lang=<lang>\n
                    Получение предыдущих сообщений: {"type": "load_previous_messages", "offset": 20, "limit": 10}
                    Отправка сообщения: {"type": "send_message", "message": "hello"}
                    Обновление сообщения: {"type": "update_message", "update": 74, "content": "Hello" }
                    Удаление сообщения: {"type": "delete_message", "delete": 74}
                    Отправка сообщения с файлом: {"type": "send_message", 
                                                  "message": {
                                                              "content": "Hello!",
                                                              "file": "data:image/jpeg;base64,/9j/4AAQS..."
                                                              "name": "example.jpg"                                                              
                                                             }
                                                  }
                    """)
class ChatSupportRetrieveView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        try:
            chat = ChatSupport.objects.get(pk=pk)
            if request.user.role not in ['admin', 'manager'] and chat.creator != request.user:
                return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

            serializer = ChatSupportRetrieveSerializer(chat)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except ChatSupport.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)


@extend_schema(summary="Обращение в техподдержку", description="""\nЧат с техподдержкой. Доступен по адресу:\n
                    wss://<host_name>/ws/support_chat/<chat_id>/?token=<JWT>&lang=<lang>\n
                    Получение предыдущих сообщений: {"type": "load_previous_messages", "offset": 20, "limit": 10}
                    Отправка сообщения: {"type": "send_message", "message": "hello"}
                    Обновление сообщения: {"type": "update_message", "update": 74, "content": "Hello" }
                    Удаление сообщения: {"type": "delete_message", "delete": 74}
                    Отправка сообщения с файлом: {"type": "send_message", 
                                                  "message": {
                                                              "content": "Hello!",
                                                              "file": "data:image/jpeg;base64,/9j/4AAQS..."
                                                              "name": "example.jpg"                                                              
                                                             }
                                                  }                
                    """)
class IssueSupportViewSet(viewsets.ModelViewSet):
    queryset = IssueSupport.objects.all()
    serializer_class = IssueSupportSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['admin', 'manager']:
            return IssueSupport.objects.all()
        return IssueSupport.objects.filter(chat__creator=user)


@extend_schema(summary="Сообщения чата техподдержки", description="Сообщения чата техподдержки")
class MessageSupportViewSet(viewsets.ModelViewSet):
    queryset = MessageSupport.objects.all()
    serializer_class = MessageSupportSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)


@extend_schema(summary="Количество непрочитанных сообщений",
               description="Возвращает количество непрочитанных сообщений во всех чатах пользователя, включая чат техподдержки.",
               responses={200: {'application/json': {'example': {'unread_messages': 5}}}}
               )
class UnreadMessagesCountAPIView(APIView):
    def get(self, request, *args, **kwargs):
        user = request.user
        user_chats = Chat.objects.filter(participants=user).values_list('id', flat=True)
        unread_in_chats = (
            Message.objects
            .filter(chat_id__in=user_chats, is_read=False, deleted=False)
            .exclude(sender=user)
            .count()
        )

        unread_in_support = 0

        if user.role in ['admin', 'manager']:
            unread_in_support = (
                MessageSupport.objects
                .filter(
                    is_read=False,
                    deleted=False,
                    sender_id__in=ChatSupport.objects.values_list('creator_id', flat=True)
                )
                .count()
            )
        else:
            chat_support_id = (
                ChatSupport.objects
                .filter(creator=user)
                .values_list('id', flat=True)
                .first()
            )
            if chat_support_id:
                unread_in_support = (
                    MessageSupport.objects
                    .filter(chat_id=chat_support_id, is_read=False, deleted=False)
                    .exclude(sender=user)
                    .count()
                )

        total_unread = unread_in_chats + unread_in_support

        return Response({'unread_messages': total_unread}, status=status.HTTP_200_OK)