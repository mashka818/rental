import hashlib
import hmac
import json
import random
from datetime import datetime, timedelta, date
from urllib.parse import urlparse
import requests
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.base import ContentFile
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.utils.timezone import now
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import status, viewsets, serializers, generics
from rest_framework.generics import get_object_or_404, ListAPIView, CreateAPIView
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from RentalGuru import settings
from RentalGuru.settings import redis_1
from chat.models import Trip, RequestRent
from influencer.models import Influencer, RegistrationSource, ReferralLink, QRCode, PromoCode, UsedPromoCode
from manager.permissions import ManagerObjectPermission
from notification.models import Notification, FCMToken
from vehicle.models import Vehicle
from .filters import RenterDocumentsFilter
from .models import User, RenterDocuments, Renter, Rating, FavoriteList, Lessor, Currency, Language
from .permissions import IsAdminOrSelf, IsAdminOrOwner, HasRenter, IsAdminOrSelfOrDirector
from .serializers import RegisterSerializer, ChangePasswordSerializer, UserListSerializer, UserDetailSerializer, \
    RenterDocumentsSerializer, VehicleListSerializer, UpdateRatingSerializer, CustomTokenObtainPairSerializer, \
    PasswordResetRequestSerializer, FavoriteListSerializer, VerifyCodeSerializer, SetPasswordSerializer, \
    BecomeLessorSerializer, CurrencySerializer, LanguageSerializer, CodeVerificationSerializer, \
    TelegramRegisterSerializer, EmailVerifiedSerializer, VehicleFavoriteList, OauthProviderSerializer, \
    UserCreateSerializer, PasswordChangeSerializer
from .task import send_verification_email, send_sms
from .utils import referal_check


@extend_schema(summary="Смена пароля", description="Смена пароля")
class ChangePasswordView(APIView):
    """Смена пароля"""
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def put(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Пароль успешно обновлен'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Восстановление пароля",
    description="Восстановление пароля по email",
    request=PasswordResetRequestSerializer,
    responses={200: None}
)
class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email'].lower()

        try:
            User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"message": "Пользователя с таким Email не существует"}, status=status.HTTP_404_NOT_FOUND)

        verification_code = str(random.randint(1000, 9999))

        cache_data = {
            'action': 'reset_password',
            'email': email,
            'code': verification_code,
            'attempts': 0,
            'last_attempt': datetime.now().isoformat()
        }

        redis_1.set(f"auth_{email}", json.dumps(cache_data), ex=1800)  # 30 минут
        send_verification_email.delay(email, verification_code)

        return Response({"message": "Код для сброса пароля отправлен на вашу почту."}, status=status.HTTP_200_OK)


@extend_schema(
    summary="Проверка кода для пароля",
    description="Проверка кода для пароля",
    request=VerifyCodeSerializer,
    responses={200: None}
)
class VerifyCodeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email'].lower()
        code = serializer.validated_data['code']

        cached_data = redis_1.get(f"auth_{email}")
        if cached_data is None:
            return Response({"error": "Недействительный или просроченный код."}, status=status.HTTP_400_BAD_REQUEST)

        cache_data = json.loads(cached_data.decode('utf-8'))

        last_attempt = datetime.fromisoformat(cache_data['last_attempt'])
        if cache_data['attempts'] >= 3 and (datetime.now() - last_attempt) < timedelta(minutes=10):
            time_left = timedelta(minutes=10) - (datetime.now() - last_attempt)
            return Response(
                {"error": f"Слишком много попыток. Пожалуйста, попробуйте через {time_left.seconds // 60} минут."},
                status=status.HTTP_400_BAD_REQUEST)

        if cache_data['code'] != code:
            cache_data['attempts'] += 1
            cache_data['last_attempt'] = datetime.now().isoformat()
            redis_1.set(f"auth_{email}", json.dumps(cache_data), ex=1800)
            return Response({"error": "Неверный код."}, status=status.HTTP_400_BAD_REQUEST)

        cache_data['status'] = 'confirmed'
        cache_data['attempts'] = 0
        redis_1.set(f"auth_{email}", json.dumps(cache_data), ex=1800)
        return Response({"message": "Код успешно подтвержден."}, status=status.HTTP_200_OK)


@extend_schema(
    summary="Создание пароля",
    description="Создание пароля",
    request=SetPasswordSerializer,
    responses={200: None}
)
class SetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email'].lower()
        password = serializer.validated_data['password']

        cached_data = redis_1.get(f"auth_{email}")
        if cached_data is None:
            return Response({"error": "Недействительный или просроченный запрос."}, status=status.HTTP_400_BAD_REQUEST)

        cache_data = json.loads(cached_data.decode('utf-8'))

        if cache_data.get('status') != 'confirmed':
            return Response({"error": "Код не подтвержден."}, status=status.HTTP_400_BAD_REQUEST)

        if cache_data['action'] == 'registration':

            # Создание пользователя
            date_of_birth = date.fromisoformat(cache_data['date_of_birth'])
            user = User.objects.create_user(
                email=cache_data['email'],
                email_verified=True,
                password=password,
                first_name=cache_data['first_name'],
                last_name=cache_data['last_name'],
                date_of_birth=date_of_birth,
                role='member',
                platform=cache_data['platform']
            )

            # Привязка к франшизе или инфлюенсеру
            member_type = cache_data.get('member_type')
            influencer_id = cache_data.get('influencer_id')

            if member_type == 'lessor':
                influencer = Influencer.objects.filter(id=influencer_id).first()
                Lessor.objects.create(user=user, influencer=influencer)
            elif member_type == 'renter':
                influencer = Influencer.objects.filter(id=influencer_id).first()
                Renter.objects.create(user=user, influencer=influencer)

            if influencer_id:
                influencer = Influencer.objects.get(id=influencer_id)
                RegistrationSource.objects.create(
                    user=user,
                    influencer=influencer,
                    source_type=cache_data.get('source_type'),
                    source_details=cache_data.get('source_details', '')
                )
                if cache_data['source_type'] == 'referral':
                    link = ReferralLink.objects.get(link=cache_data.get('source_details'))
                    link.count += 1
                    link.save()
                elif cache_data['source_type'] == 'qr_code':
                    qr = QRCode.objects.get(referral_link=cache_data.get('source_details'))
                    qr.count += 1
                    qr.save()
            if cache_data.get('source_type') == 'promo':
                promocode = PromoCode.objects.get(title=cache_data.get('source_details'))
                promocode.count += 1
                promocode.save()
                if promocode.type == 'cash' and member_type == 'renter':
                    renter = Renter.objects.get(user=user)
                    renter.bonus_account += promocode.total
                    renter.save()
                else:
                    UsedPromoCode.objects.create(user=user, promo_code=promocode)
            message = "Пользователь успешно зарегистрирован."

        elif cache_data['action'] == 'reset_password':
            user = User.objects.get(email=email)
            user.set_password(password)
            user.save()
            message = "Пароль успешно изменен."
        else:
            return Response({"error": "Неверный тип действия."}, status=status.HTTP_400_BAD_REQUEST)

        redis_1.delete(f"auth_{email}")
        
        # Автоматическая авторизация после регистрации
        refresh = RefreshToken.for_user(user)
        response_data = {
            "message": message,
            "user_id": user.id,
            "email": user.email,
            "refresh": str(refresh),
            "access": str(refresh.access_token)
        }
        
        return Response(response_data, status=status.HTTP_200_OK if cache_data['action'] == 'reset_password' else status.HTTP_201_CREATED)


@extend_schema(summary="Пользователи CRUD", description="""\nРегистрация, получение списка пользователей, 
                                                            получение пользователя по ID, обновление, удаление.
                                                            Метод пост может принимать параметры:\n
                            /?ref=<referral_code>&code=<link_code>
                            /?promocode=<promocode>""")
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()

    def get_queryset(self):
        if self.action == 'list':
            return User.objects.only("id", "first_name", "last_name", "email", "role", "avatar")
        return User.objects.all()

    def get_serializer_class(self):
        if self.action == 'create':
            return RegisterSerializer
        elif self.action == 'list':
            return UserListSerializer
        return UserDetailSerializer

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [AllowAny]
        elif self.action in ['update', 'partial_update']:
            permission_classes = [IsAuthenticated, IsAdminOrSelfOrDirector]
        elif self.action == 'destroy':
            permission_classes = [IsAuthenticated, IsAdminOrSelf]
        elif self.action == 'retrieve':
            permission_classes = [AllowAny]
        elif self.action == 'list':
            permission_classes = [IsAuthenticated, ManagerObjectPermission]
        else:
            permission_classes = [IsAuthenticated, IsAdminOrSelf]
        return [permission() for permission in permission_classes]

    def perform_update(self, serializer):
        serializer.save(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({"message": "Код подтверждения отправлен на вашу почту."}, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        if hasattr(instance, 'lessor'):
            from vehicle.models import Auto, Bike, Ship, Helicopter, SpecialTechnic

            Auto.objects.filter(owner=instance).delete()
            Bike.objects.filter(owner=instance).delete()
            Ship.objects.filter(owner=instance).delete()
            Helicopter.objects.filter(owner=instance).delete()
            SpecialTechnic.objects.filter(owner=instance).delete()

            print(f"Удален транспорт пользователя {instance.id}")

        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

@extend_schema(summary="Документы арендатора", description="title принимает passport или "
                                                           "license(Водительское уд.). Для license обязательно "
                                                           "указывать issue_date(Дата выдачи)")
class RenterDocumentsViewSet(viewsets.ModelViewSet):
    serializer_class = RenterDocumentsSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = RenterDocumentsFilter
    permission_classes = [IsAuthenticated, IsAdminOrSelf]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin' or user.role == 'manager':
            return RenterDocuments.objects.all()
        else:
            try:
                renter = user.renter
            except ObjectDoesNotExist:
                return RenterDocuments.objects.none()
            return RenterDocuments.objects.filter(renter=renter)

    def perform_create(self, serializer):
        user = self.request.user
        try:
            renter = user.renter
        except ObjectDoesNotExist:
            raise serializers.ValidationError({'detail': 'Пользователь не является арендатором'})
        serializer.save(renter=renter)

    def perform_update(self, serializer):
        user = self.request.user
        document = self.get_object()

        if user.role == 'admin' or user.role == 'manager':
            if serializer.validated_data.get('status') == 'approved':
                url = f'{settings.HOST_URL}/documents/{document.id}/'
                content = 'Ваш документ проверен'
                Notification.objects.create(user=document.renter.user, url=url, content=content)
            elif serializer.validated_data.get('status') == 'rejected':
                url = f'{settings.HOST_URL}/documents/{document.id}/'
                content = 'Ваш документ отклонен'
                Notification.objects.create(user=document.renter.user, url=url, content=content)
            serializer.save()
        else:
            if 'status' in serializer.validated_data:
                raise serializers.ValidationError({'detail': 'Изменение статуса запрещено'}, code=status.HTTP_403_FORBIDDEN)

            serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        try:
            renter = user.renter
        except ObjectDoesNotExist:
            raise serializers.ValidationError({'detail': 'Пользователь не является арендатором'})
        if instance.renter != renter:
            raise serializers.ValidationError({'detail': 'Документ не принадлежит текущему арендатору'})
        instance.delete()


@extend_schema(summary="Списки избранного",
               parameters=[
                       OpenApiParameter(name='limit', type=int, location=OpenApiParameter.QUERY,
                                        description='Number of results to return.'),
                       OpenApiParameter(name='offset', type=int, location=OpenApiParameter.QUERY,
                                        description='The initial index from which to return the results.')
                   ],
               description="Получение всех списков избранного пользователя")
class FavoriteListView(ListAPIView, CreateAPIView):
    """Получить все списки избранного пользователя"""
    permission_classes = [IsAuthenticated, HasRenter, IsAdminOrOwner]
    serializer_class = FavoriteListSerializer
    pagination_class = LimitOffsetPagination

    def get_queryset(self):
        return FavoriteList.objects.filter(renter=self.request.user.renter)

    @extend_schema(
        summary="Создание нового списка избранного",
        description="Создаёт пустой список избранного с указанным названием",
        request=FavoriteListSerializer,
        responses={201: FavoriteListSerializer},
    )
    def create(self, request, *args, **kwargs):
        list_name = request.data.get('name')
        if not list_name:
            return Response({'detail': 'Название списка обязательно'}, status=status.HTTP_400_BAD_REQUEST)

        favorite_list, created = FavoriteList.objects.get_or_create(renter=request.user.renter, name=list_name)

        if created:
            serializer = self.get_serializer(favorite_list)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response({'detail': 'Список с таким названием уже существует'}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(summary="Удаление списка избранного", description="Удаляет список избранного")
class FavoriteListDeleteView(generics.DestroyAPIView):
    """Удалить список избранного"""
    permission_classes = [IsAuthenticated, HasRenter, IsAdminOrOwner]
    queryset = FavoriteList.objects.all()

    def get_queryset(self):
        return super().get_queryset().filter(renter=self.request.user.renter)


class AddVehicleToFavoriteListView(APIView):
    """ Добавление транспорта в список """
    permission_classes = [IsAuthenticated, HasRenter, IsAdminOrOwner]

    @extend_schema(
        summary="Добавление транспорта в список",
        description="Добавляет транспорт в список. Если нет списка с переданным названием, то создастся новый список",
        request=FavoriteListSerializer,
        responses={201: FavoriteListSerializer},
    )
    def post(self, request, vehicle_id):
        list_name = request.data.get('name')
        if not list_name:
            return Response({'detail': 'Название списка обязательно'}, status=status.HTTP_400_BAD_REQUEST)

        vehicle = get_object_or_404(Vehicle, id=vehicle_id)
        favorite_list, created = FavoriteList.objects.get_or_create(renter=request.user.renter, name=list_name)
        favorite_list.vehicles.add(vehicle)

        return Response({'detail': 'Транспорт добавлен в список избранного', 'created': created}, status=status.HTTP_200_OK)


@extend_schema(summary="Удаление транспорта из избранного", description="Находит транспорт по id в списках избранного и удаляет его")
class RemoveVehicleFromFavoriteListView(APIView):
    """ Удаление транспорта из избранного """
    permission_classes = [IsAuthenticated, HasRenter, IsAdminOrOwner]

    def post(self, request, vehicle_id):
        vehicle = get_object_or_404(Vehicle, id=vehicle_id)
        favorite_lists = FavoriteList.objects.filter(renter=request.user.renter)
        vehicle_found = False

        for favorite_list in favorite_lists:
            if vehicle in favorite_list.vehicles.all():
                favorite_list.vehicles.remove(vehicle)
                vehicle_found = True

        if not vehicle_found:
            return Response({'detail': 'Транспорт не найден в избранном'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'detail': 'Транспорт удалён из всех списков избранного'}, status=status.HTTP_200_OK)


@extend_schema(summary="Получение ID всего транспорта", description="Возвращает массив из ID всего транспорта из всех списков избранного")
class FavoriteListAllVehiclesView(APIView):
    permission_classes = [IsAuthenticated, HasRenter, IsAdminOrOwner]

    @extend_schema(summary="Получить весь транспорт из всех списков избранного",
                   description="Возвращает транспорт из всех списков избранного пользователя")
    def get(self, request):
        favorite_lists = FavoriteList.objects.filter(renter=request.user.renter)
        vehicles = Vehicle.objects.filter(in_favorite_lists__in=favorite_lists)
        serializer = VehicleFavoriteList(vehicles, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class FavoriteListDetailView(APIView):
    permission_classes = [IsAuthenticated, HasRenter, IsAdminOrOwner]

    @extend_schema(summary="Вывод транспорта из списка избранного",
                   description="Выводит весь список транспорта из списка")
    def get(self, request, id):
        favorite_list = get_object_or_404(FavoriteList, id=id, renter=request.user.renter)
        vehicles = favorite_list.vehicles.all()
        serializer = VehicleListSerializer(vehicles, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Изменение названия списка",
        description="Изменяет название списка",
        request=FavoriteListSerializer,
        responses={201: FavoriteListSerializer},
    )
    def patch(self, request, id):
        favorite_list = get_object_or_404(FavoriteList, id=id, renter=request.user.renter)
        serializer = FavoriteListSerializer(favorite_list, data=request.data, partial=True,
                                            context={'request': request})

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(summary="Обновление рейтинга арендатора",
               request=UpdateRatingSerializer,
               description="Выставляется владельцем транспорта, после завершения поездки.")
class UpdateRatingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, renter_id):
        renter = get_object_or_404(Renter.objects.select_related('user'), id=renter_id)
        owner = request.user
        trips = Trip.objects.filter(organizer=renter.user).select_related(
            'content_type').prefetch_related('vehicle')
        is_owner = any(trip.vehicle.owner == owner for trip in trips)

        if not is_owner:
            return Response({
                                "detail": "Вы не являетесь владельцем транспортного средства в завершённых поездках данного арендатора."},
                            status=status.HTTP_403_FORBIDDEN)

        if Rating.objects.filter(user=owner, renter=renter).exists():
            return Response({"detail": "Вы уже оставляли рейтинг этому арендатору."},
                            status=status.HTTP_400_BAD_REQUEST)

        serializer = UpdateRatingSerializer(data=request.data)

        if serializer.is_valid():
            serializer.update(renter, serializer.validated_data)
            Rating.objects.create(user=owner, renter=renter, rating=serializer.validated_data['rating'])
            return Response({"average_rating": renter.get_average_rating()}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(summary="Получение JWT токенов", description="Принимает email и password (опционально fcm_token для "
                                                            "пуш уведомлений). При первом входе предлагает сменить "
                                                            "пароль")
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


@extend_schema(summary="Стать арендодателем", description="Удаление арендатора и создание арендодателя")
class BecomeLessorView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrSelf]

    def post(self, request):
        user = request.user

        try:
            renter = Renter.objects.get(user=user)
        except Renter.DoesNotExist:
            return Response({"detail": "Пользователь не является арендатором"}, status=status.HTTP_400_BAD_REQUEST)

        if Trip.objects.filter(organizer=user, status__in=['started', 'current']).exists():
            return Response({"detail": "Остались незавершенные поездки"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = BecomeLessorSerializer(data=request.data)
        if serializer.is_valid():
            renter.delete()
            Trip.objects.filter(organizer=user).delete()
            RequestRent.objects.filter(organizer=user).delete()

            Lessor.objects.create(user=user, **serializer.validated_data)
            return Response({"detail": "Пользователь был успешно переведен в арендодателя"}, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(summary="Список валют", description="Список валют")
class CurrencyListView(ListAPIView):
    queryset = Currency.objects.all()
    serializer_class = CurrencySerializer


@extend_schema(summary="Список языков", description="Список языков")
class LanguageListView(ListAPIView):
    queryset = Language.objects.all()
    serializer_class = LanguageSerializer


@extend_schema(summary="Отправка кода на номер телефона", description="Отправка кода на номер телефона")
class PhoneSendCode(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if not user.telephone:
            return Response({"detail": "Номер телефона пользователя не найден."}, status=status.HTTP_400_BAD_REQUEST)
        elif user.telephone_verified:
            return Response({"detail": "Номер телефона уже верифицирован"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            verification_code = random.randint(1000, 9999)
            redis_1.set(f'phone_{user.telephone}', json.dumps(verification_code), ex=1800)
            send_sms.delay(user.telephone, verification_code)
            return Response({"detail": "Код подтверждения отправлен."}, status=status.HTTP_200_OK)


@extend_schema(summary="Верификация номера телефона", description="Верификация номера телефона")
class PhoneVerifyCode(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CodeVerificationSerializer

    def post(self, request):
        user = request.user
        serializer = CodeVerificationSerializer(data=request.data)

        if serializer.is_valid():
            verification_code = serializer.validated_data['verification_code']
            stored_code = redis_1.get(f'phone_{user.telephone}')

            if stored_code is None:
                return Response({"detail": "Срок действия кода подтверждения истек или он недействителен."}, status=status.HTTP_400_BAD_REQUEST)

            if str(json.loads(stored_code)) == str(verification_code):
                user.telephone_verified = True
                user.save()
                redis_1.delete(f'phone_{user.telephone}')
                return Response({"detail": "Номер телефона подтвержден"}, status=status.HTTP_200_OK)
            else:
                return Response({"detail": "Неверный код подтверждения."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Callback для телеграма",
    description="Callback для телеграма"
)
class TelegramCallbackView(APIView):
    def post(self, request):
        data = request.data
        if not self.verify_telegram_data(data):
            return Response({"error": "Недопустимый хэш"}, status=status.HTTP_400_BAD_REQUEST)

        telegram_id = data.get('id')

        if not telegram_id:
            return Response({"error": "Требуется идентификатор Telegram ID"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(telegram_id=telegram_id)

            refresh = RefreshToken.for_user(user)
            return Response({
                "status": "login",
                "user_id": user.id,
                "email": user.email,
                "refresh": str(refresh),
                "access": str(refresh.access_token)
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:

            return Response({
                "status": "registration_required",
                "telegram_data": {
                    "telegram_id": telegram_id,
                    "first_name": data.get('first_name', ''),
                    "last_name": data.get('last_name', ''),
                },
                "required_fields": ["email", "role"]
            }, status=status.HTTP_200_OK)

    def verify_telegram_data(self, data):
        if 'hash' not in data:
            return False

        auth_data = data.copy()
        hash_value = auth_data.pop('hash')

        data_check_list = []
        for key in sorted(auth_data.keys()):
            if auth_data[key] is not None:
                data_check_list.append(f"{key}={auth_data[key]}")

        data_check_string = '\n'.join(data_check_list)

        secret_key = hashlib.sha256(settings.TELEGRAM_BOT_TOKEN.encode('utf-8')).digest()
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return calculated_hash == hash_value


@extend_schema(
    summary="Регистрация пользователя Telegram",
    description="Регистрация нового пользователя, пришедшего из Telegram"
)
class TelegramRegisterView(APIView):
    @transaction.atomic
    def post(self, request):
        serializer = TelegramRegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            role = serializer.validated_data['role']

            if role == 'lessor':
                Lessor.objects.create(user=user)
            else:
                Renter.objects.create(user=user)

            refresh = RefreshToken.for_user(user)

            return Response({
                "message": "Пользователь зарегистрирован",
                "user_id": user.id,
                "email": user.email,
                "role": role,
                "refresh": str(refresh),
                "access": str(refresh.access_token)
            }, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Отправка кода на почту для подтверждения email",
    description="Отправка кода на почту для подтверждения email, для пользователей зарегистрированных Telegram"
)
class SendCodeToEmailView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        verification_code = str(random.randint(1000, 9999))
        redis_1.set(f"verify_{user.email}", json.dumps(verification_code), ex=1800)
        send_verification_email.delay(user.email, verification_code)

        return Response({"message": "Код для подтверждения почты отправлен на вашу почту."}, status=status.HTTP_200_OK)


@extend_schema(
    summary="Подтверждение email",
    description="Подтверждение email, для пользователей зарегистрированных Telegram"
)
class VerifiedEmailView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = EmailVerifiedSerializer

    def post(self, request):
        user = request.user
        verification_code = request.data.get('verification_code')
        stored_code = redis_1.get(f"verify_{user.email}")
        if stored_code is None:
            return Response({"message": "Код истек или не был найден"}, status=status.HTTP_404_NOT_FOUND)

        if verification_code == json.loads(stored_code.decode('utf-8')):
            user.email_verified = True
            user.save()
            redis_1.delete(f"verify_{user.email}")
            return Response({"message": "Код успешно подтвержден"}, status=status.HTTP_200_OK)
        else:
            return Response({"message": "Неверный код"}, status=status.HTTP_403_FORBIDDEN)


@extend_schema(
    summary="Аутентификация через соцсети",
    description=(
        "Используется для аутентификации пользователей через социальные сети "
        "VK и Mail.ru. Принимает квери параметр provider = mailru, vk, yandex "
    ),
    parameters=[OauthProviderSerializer]
)
class OauthCallback(APIView):
    def post(self, request):

        serializer = OauthProviderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        ref = request.data.get('ref')
        referral_code = request.data.get('referral_code')
        promocode = request.data.get('promocode')
        fcm_token = request.data.get('fcm_token', '')
        provider = serializer.validated_data['provider']
        code = serializer.validated_data['code']
        platform = serializer.validated_data.get('platform', 'unknown')

        if not code or not provider:
            return Response({"error": "Код или провайдер не переданы"}, status=400)

        handler = getattr(self, f"handle_{provider}", None)
        if handler:
            return handler(code, fcm_token, ref, referral_code, promocode, platform)
        else:
            return Response({"error": "Неправильный провайдер"}, status=400)

    def handle_mailru(self, code, fcm_token, ref, referral_code, promocode, platform):
        token_url = 'https://oauth.mail.ru/token'

        auth = (settings.SOCIAL_AUTH_MAILRU_OAUTH2_KEY, settings.SOCIAL_AUTH_MAILRU_OAUTH2_SECRET)
        data = {
            'grant_type': 'authorization_code',
            'redirect_uri': settings.MAILRU_REDIRECT_URI,
            'code': code,
        }

        try:
            token_response = requests.post(token_url, data=data, auth=auth)
            token_response.raise_for_status()
            token_data = token_response.json()
            access_token = token_data.get('access_token')

            if not access_token:
                return Response({"error": "Ошибка получения токена"}, status=400)

            user_info_url = f'https://oauth.mail.ru/userinfo?access_token={access_token}'
            user_response = requests.get(user_info_url)
            user_response.raise_for_status()
            user_data = user_response.json()

            email = user_data.get('email')
            if not email:
                return Response({"error": "Email не передан от Mail.ru"}, status=400)

            birthday = user_data.get('birthday')
            formatted_birthday = None
            if birthday:
                try:
                    formatted_birthday = datetime.strptime(birthday, "%d.%m.%Y").date()
                except ValueError:
                    return Response({"error": "Неверный формат даты рождения"}, status=400)

            user, created = User.objects.get_or_create(email=email, defaults={
                'first_name': user_data.get('first_name', ''),
                'last_name': user_data.get('last_name', ''),
                'date_of_birth': formatted_birthday,
                'role': 'member',
                'platform': platform,
                'email_verified': True,
                'last_login': timezone.now()
            })

            if created:
                Renter.objects.create(user=user)
                referal_check(user, ref, referral_code, promocode)  # Проверка реферрала
            if not created:
                user.last_login = timezone.now()
                user.save()

            self.update_fcm_token(user=user, fcm_token=fcm_token)

            if 'image' in user_data and not user.avatar:
                avatar_url = user_data['image']
                avatar_response = requests.get(avatar_url)
                avatar_response.raise_for_status()
                parsed_url = urlparse(avatar_url)
                filename = parsed_url.path.split('/')[-1]
                user.avatar.save(filename, ContentFile(avatar_response.content))
                user.save()

            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)

            return Response({
                'access_token': access_token,
                'refresh_token': str(refresh),
                'user': {
                    'user_id': user.id,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                }
            },
                content_type='application/json')

        except requests.exceptions.RequestException as e:
            return Response({"error": f"Request failed: {str(e)}"}, status=400)

    def handle_vk(self, code, fcm_token, ref, referral_code, promocode, platform):
        token_url = 'https://oauth.vk.com/access_token'

        data = {
            'client_id': settings.SOCIAL_AUTH_VK_OAUTH2_KEY,
            'client_secret': settings.SOCIAL_AUTH_VK_OAUTH2_SECRET,
            'redirect_uri': settings.VK_REDIRECT_URI,
            'code': code,
        }

        try:
            token_response = requests.post(token_url, data=data)
            token_response.raise_for_status()
            token_data = token_response.json()
            access_token = token_data.get('access_token')
            email = token_data.get('email')

            if not email:
                return Response({"error": "Email не передан от VK"}, status=400)

            if not access_token:
                return Response({"error": "Ошибка получения токена"}, status=400)

            user_id = token_data.get('user_id')

            user_info_url = 'https://api.vk.com/method/users.get'
            user_data = {
                'user_ids': user_id,
                'fields': 'photo_200,bdate',
                'access_token': access_token,
                'v': '5.199'
            }

            user_response = requests.get(user_info_url, params=user_data)
            user_response.raise_for_status()
            user_data_response = user_response.json()

            if 'response' in user_data_response and len(user_data_response['response']) > 0:
                vk_user = user_data_response['response'][0]
                first_name = vk_user.get('first_name', '')
                last_name = vk_user.get('last_name', '')
                birthday = vk_user.get('bdate')
                avatar_url = vk_user.get('photo_200')

                formatted_birthday = None
                if birthday:
                    try:
                        formatted_birthday = datetime.strptime(birthday, "%d.%m.%Y").date()
                    except ValueError:
                        pass

            else:
                return Response({"error": "Ошибка получения данных пользователя VK"}, status=400)

            user, created = User.objects.get_or_create(email=email, defaults={
                'first_name': first_name,
                'last_name': last_name,
                'date_of_birth': formatted_birthday,
                'role': 'member',
                'email_verified': True,
                'last_login': timezone.now(),
                'platform': platform
            })

            if created:
                Renter.objects.create(user=user)
                referal_check(user, ref, referral_code, promocode)  # Проверка реферрала

            if not created:
                user.last_login = timezone.now()
                user.save()

            self.update_fcm_token(user=user, fcm_token=fcm_token)

            if avatar_url:
                avatar_response = requests.get(avatar_url)
                avatar_response.raise_for_status()
                parsed_url = urlparse(avatar_url)
                filename = parsed_url.path.split('/')[-1]
                user.avatar.save(filename, ContentFile(avatar_response.content))
            else:
                return Response({"error": "Аватар не найден"}, status=400)

            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)

            return Response({
                'access_token': access_token,
                'refresh_token': str(refresh),
                'user': {
                    'user_id': user.id,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                }
            },
                content_type='application/json')

        except requests.exceptions.RequestException as e:
            return Response({"error": f"Request failed: {str(e)}"}, status=400)

    def handle_yandex(self, code, fcm_token, ref, referral_code, promocode, platform):
        token_url = 'https://oauth.yandex.com/token'
        redirect_uri = settings.YANDEX_REDIRECT_URI

        data = {
            'grant_type': 'authorization_code',
            'client_id': settings.SOCIAL_AUTH_YANDEX_OAUTH2_KEY,
            'client_secret': settings.SOCIAL_AUTH_YANDEX_OAUTH2_SECRET,
            'code': code,
            'redirect_uri': redirect_uri,
        }

        try:
            token_response = requests.post(token_url, data=data)
            token_response.raise_for_status()
            token_data = token_response.json()
            access_token = token_data.get('access_token')

            if not access_token:
                return Response({"error": "Ошибка получения токена"}, status=400)

            user_info_url = 'https://login.yandex.ru/info'
            headers = {'Authorization': f'Bearer {access_token}'}
            user_response = requests.get(user_info_url, headers=headers)
            user_response.raise_for_status()
            user_data_response = user_response.json()

            email = user_data_response.get('default_email')
            first_name = user_data_response.get('first_name', '')
            last_name = user_data_response.get('last_name', '')
            avatar_url = user_data_response.get('default_avatar_id', None)
            birthday = user_data_response.get('birthday', None)
            phone_data = user_data_response.get('default_phone', {})
            phone = phone_data.get('number', '')

            if not email:
                return Response({"error": "Email не передан от Яндекс"}, status=400)

            user, created = User.objects.get_or_create(email=email, defaults={
                'first_name': first_name,
                'last_name': last_name,
                'role': 'member',
                'email_verified': True,
                'last_login': timezone.now(),
                'date_of_birth': birthday,
                'telephone': phone,
                'platform': platform
            })

            if created:
                Renter.objects.create(user=user)
                referal_check(user, ref, referral_code, promocode)  # Проверка реферрала

            if not created:
                user.last_login = timezone.now()
                user.save()

            self.update_fcm_token(user=user, fcm_token=fcm_token)

            if avatar_url:
                avatar_url_full = f"https://avatars.yandex.net/get-yapic/{avatar_url}/islands-retina-50"
                avatar_response = requests.get(avatar_url_full)
                avatar_response.raise_for_status()
                filename = f"yandex_avatar_{user.id}.jpg"
                user.avatar.save(filename, ContentFile(avatar_response.content))

            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)

            return Response({
                'access_token': access_token,
                'refresh_token': str(refresh),
                'user': {
                    'user_id': user.id,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                }
            },
                content_type='application/json')

        except requests.exceptions.RequestException as e:
            return Response({"error": f"Request failed: {str(e)}"}, status=400)

    def update_fcm_token(self, user, fcm_token):
        """
        Обновление или создание FCM токена.
        """
        if fcm_token:
            try:
                FCMToken.objects.update_or_create(
                    user=user,
                    token=fcm_token,
                    defaults={'last_used_at': now()}
                )
            except IntegrityError:
                pass


@extend_schema(
    summary="Регистрация пользователей от имени администратора или менеджера",
    request=UserCreateSerializer)
class UserCreateView(APIView):
    """
    Вью для создания пользователя от имени администратора.
    """
    permission_classes = [ManagerObjectPermission]

    def post(self, request, *args, **kwargs):
        serializer = UserCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {
                    "message": "Пользователь успешно создан.",
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "role": user.role,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                    },
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Представление для смены пароля пользователя",
    request=PasswordChangeSerializer)
class PasswordChangeView(APIView):
    permission_classes = [ManagerObjectPermission]

    def post(self, request):
        """ Обработка запроса на смену пароля """
        serializer = PasswordChangeSerializer(data=request.data)

        if serializer.is_valid():
            user_id = serializer.validated_data['user_id']
            new_password = serializer.validated_data['new_password']
            user = get_user_model().objects.get(id=user_id)
            user.set_password(new_password)
            user.save()
            return Response({"detail": "Пароль успешно изменен."}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
