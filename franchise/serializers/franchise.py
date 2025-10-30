from django.db import models, transaction
from rest_framework import serializers

from app.models import Lessor, User
from chat.models import RequestRent
from franchise.add_lessor import RequestAddLessor
from franchise.models import Franchise, VehiclePark, Category, RequestFranchise, City, FranchiseDocuments
from franchise.serializers.vehicle_park import VehicleParkRetrieveSerializer, VehicleSerializer
from manager.utils import generate_secure_password
from notification.models import Notification
from payment.models import Payment
from vehicle.models import Vehicle


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id']


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id',
            'avatar',
            'telephone',
            'email',
            'first_name',
            'last_name',
            'date_of_birth'
        ]
        read_only_fields = ['id', 'email',]


class FranchiseDocumentsSerializer(serializers.ModelSerializer):
    class Meta:
        model = FranchiseDocuments
        fields = ['number', 'photo', 'status']


class FranchiseListSerializer(serializers.ModelSerializer):
    director = serializers.StringRelatedField()
    categories = CategorySerializer(many=True)
    avatar = serializers.ImageField(source='director.avatar', read_only=True)
    total_vehicles = serializers.SerializerMethodField()
    telephone = serializers.CharField(source='director.telephone', read_only=True)
    email = serializers.CharField(source='director.email', read_only=True)

    class Meta:
        model = Franchise
        fields = [
            'id',
            'avatar',
            'director',
            'name',
            'inn',
            'date_register',
            'telephone',
            'email',
            'country',
            'city',
            'commission',
            'total_vehicles',
            'categories'
        ]

    def get_total_vehicles(self, obj):
        return obj.get_total_vehicles()


class FranchiseRetrieveSerializer(serializers.ModelSerializer):
    director = UserSerializer()
    document = FranchiseDocumentsSerializer()

    class Meta:
        model = Franchise
        fields = [
            'id',
            'director',
            'document',
            'name',
            'date_register',
            'country',
            'city',
            'address',
            'inn',
            'ogrn',
            'account_number',
            'account_owner',
            'commission',
            'email_1',
            'email_2',
            'telephone_1',
            'telephone_2',
            'total_vehicles',
        ]


class FranchiseCreateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email')
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    telephone = serializers.CharField(source='user.telephone')
    city = serializers.PrimaryKeyRelatedField(queryset=City.objects.all())

    class Meta:
        model = Franchise
        fields = ['id', 'name', 'inn', 'telephone', 'country', 'city', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']

    def validate_city(self, value):
        """Проверка, что для города нет уже зарегистрированной франшизы"""
        if Franchise.objects.filter(city=value).exists():
            raise serializers.ValidationError(f'Для города {value.title} уже зарегистрирована франшиза.')
        return value

    def create(self, validated_data):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        user_data = validated_data.pop('user', None)
        if not user_data:
            raise serializers.ValidationError({"user": "Данные пользователя обязательны."})

        email = user_data.get('email')
        if not email:
            raise serializers.ValidationError({"email": "Поле email обязательно для заполнения."})

        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError({"email": "Пользователь с таким email уже зарегистрирован."})

        city = validated_data.get('city')
        country = validated_data.get('country')
        if not city:
            raise serializers.ValidationError({"city": "Поле city обязательно для заполнения."})
        if not country:
            raise serializers.ValidationError({"country": "Поле country обязательно для заполнения."})

        password = generate_secure_password()
        with transaction.atomic():
            user = User.objects.create_user(
                email=email,
                first_name=user_data.get('first_name'),
                last_name=user_data.get('last_name'),
                password=password,
                telephone=user_data.get('telephone'),
                role='member',
            )

            franchise = Franchise.objects.create(
                director=user,
                telephone_1=user.telephone,
                email_1=email,
                name=validated_data["name"],
                inn=validated_data["inn"],
                city=city,
                country=country
            )

            Notification.objects.create(
                user=user,
                content=f"Добро пожаловать, {user.first_name}! Вы зарегистрированы как директор франшизы '{franchise.name}'. Ваш пароль: {password}",
            )

        return franchise


class FranchiseUpdateSerializer(serializers.ModelSerializer):
    director = UserSerializer(required=False)
    document = FranchiseDocumentsSerializer(required=False)

    class Meta:
        model = Franchise
        fields = [
            'director',
            'document',
            'name',
            'date_register',
            'country',
            'city',
            'address',
            'inn',
            'ogrn',
            'account_number',
            'account_owner',
            'email_1',
            'email_2',
            'telephone_1',
            'telephone_2'
        ]

    def update(self, instance, validated_data):
        director_data = validated_data.pop('director', None)
        if director_data:
            director_serializer = UserSerializer(instance.director, data=director_data, partial=True)
            if director_serializer.is_valid(raise_exception=True):
                director_serializer.save()

        document_data = validated_data.pop('document', None)
        if document_data:
            self.update_document(instance, document_data)

        instance = super().update(instance, validated_data)
        instance.save()
        return instance

    def update_document(self, instance, document_data):
        """Обновление документа"""
        request = self.context.get('request')
        user_role = getattr(request.user, 'role', None) if request else None

        if document_data.get('status') != 'pending' and user_role not in ['admin', 'manager']:
            document_data['status'] = 'pending'

        document, created = FranchiseDocuments.objects.get_or_create(franchise=instance, defaults=document_data)

        if not created:
            for attr, value in document_data.items():
                setattr(document, attr, value)
            document.save()

    def validate_city(self, value):
        if Franchise.objects.filter(city=value).exclude(id=self.instance.id if self.instance else None).exists():
            raise serializers.ValidationError(f'Для города {value} уже зарегистрирована франшиза.')
        return value


class FranchiseDeleteSerializer(serializers.Serializer):
    pass


class RequestRentSerializer(serializers.ModelSerializer):
    organizer = serializers.StringRelatedField()
    type = serializers.SerializerMethodField()
    object = serializers.SerializerMethodField()

    class Meta:
        model = RequestRent
        fields = ['id', 'organizer', 'type', 'status', 'object', 'start_date', 'end_date', 'total_cost']

    def get_type(self, obj):
        return obj.content_type.model

    def get_object(self, obj):
        vehicle = Vehicle.objects.filter(id=obj.object_id).first()
        return str(vehicle) if vehicle else None

    def get_queryset(self):
        franchise = self.context['franchise']
        return RequestRent.objects.filter(
            models.Q(vehicle__owner__lessor__franchise=franchise) | models.Q(vehicle__owner=franchise.director)
        )


class LessorSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()

    class Meta:
        model = Lessor
        fields = [
            'id',
            'user',
            'super_host',
            'count_trip',
            'average_response_time',
            'franchise'
        ]


class FranchiseStatisticsSerializer(serializers.Serializer):
    total_vehicles = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_margin = serializers.DecimalField(max_digits=10, decimal_places=2)
    royalty = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_orders = serializers.IntegerField()
    total_completed_orders = serializers.IntegerField()
    total_cancelled_orders = serializers.IntegerField()
    active_users_count = serializers.IntegerField()

    change_revenue = serializers.FloatField()
    change_margin = serializers.FloatField()
    change_royalty = serializers.FloatField()
    change_completed_orders = serializers.FloatField()
    change_cancelled_orders = serializers.FloatField()


class RequestFranchiseSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestFranchise
        fields = '__all__'


class CitySerializer(serializers.ModelSerializer):
    finished_trips_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = City
        fields = ['id', 'title', 'latitude', 'longitude', 'finished_trips_count']


class RequestAddLessorCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestAddLessor
        fields = ['id', 'franchise', 'lessor']
        read_only_fields = ['id']

    def validate(self, attrs):
        request = self.context['request']

        if hasattr(request.user, 'franchise'):
            attrs['franchise'] = request.user.franchise
        elif not attrs.get('franchise'):
            raise serializers.ValidationError(
                "Франшиза обязательна, если пользователь не является директором."
            )

        if RequestAddLessor.objects.filter(
                franchise=attrs['franchise'],
                lessor=attrs['lessor'],
                status='on_consideration'
        ).exists():
            raise serializers.ValidationError(
                "Активная заявка для данного арендодателя уже существует."
            )

        return attrs

    def create(self, validated_data):
        instance = super().create(validated_data)
        content = f"Новая заявка # {instance.id} на добавление в франшизу {instance.franchise.name}."
        Notification.objects.create(user=instance.lessor.user, content=content)

        return instance


class RequestAddLessorUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestAddLessor
        fields = ['status']

    def validate_status(self, value):
        if value not in ['approved', 'rejected']:
            raise serializers.ValidationError(
                "Статус может быть изменен только на 'approved' или 'rejected'."
            )
        return value

    def validate(self, attrs):
        if self.instance and attrs.get('status') == 'approved':
            if self.instance.lessor.franchise and \
                    self.instance.lessor.franchise != self.instance.franchise:
                raise serializers.ValidationError(
                    "Арендодатель уже привязан к другой франшизе."
                )
        return attrs

    def update(self, instance, validated_data):
        if validated_data['status'] == 'approved':
            instance.lessor.franchise = instance.franchise
            instance.lessor.save()
            RequestAddLessor.objects.filter(lessor=instance.lessor).delete()
            content = f"Ваша заявка на добавление в франшизу {instance.franchise.name} была подтверждена."
            Notification.objects.create(user=instance.franchise.director, content=content)
        elif validated_data['status'] == 'rejected':
            instance.status = validated_data['status']
            instance.save()
            content = f"Ваша заявка на добавление в франшизу {instance.franchise.name} была отклонена."
            Notification.objects.create(user=instance.franchise.director, content=content)

        return instance


class LessorListSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    avatar = serializers.ImageField(source='user.avatar')
    telephone = serializers.CharField(source='user.telephone')
    count_vehicles = serializers.IntegerField(read_only=True)
    user_id = serializers.IntegerField(source='user.id')

    class Meta:
        model = Lessor
        fields = [
            'id', 'user_id', 'first_name', 'last_name', 'avatar', 'telephone', 'count_trip', 'franchise',
            'commission', 'count_vehicles'
                  ]


class PaymentSerializer(serializers.ModelSerializer):
    date = serializers.SerializerMethodField()
    time = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = ['id', 'amount', 'status', 'payment_id', 'date', 'time']

    def get_date(self, obj):
        return obj.created_at.strftime('%d.%m.%Y')

    def get_time(self, obj):
        return obj.created_at.strftime('%H:%M')
