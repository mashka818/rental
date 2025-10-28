import json
from decimal import Decimal

from django.db.models import Max
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from RentalGuru.settings import HOST_URL
from app.models import Lessor
from vehicle.models import VehicleDocument, Availability, RentPrice, VehiclePhoto, PaymentMethod, VehicleModel, \
    VehicleBrand, VehicleClass, Auto, Bike, Ship, Helicopter, SpecialTechnic, Vehicle
from vehicle.utils import merge_periods


class AvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Availability
        fields = ['vehicle', 'start_date', 'end_date', 'on_request']
        extra_kwargs = {
            'vehicle': {'required': False},
            'start_date': {'required': False, 'allow_null': True},
            'end_date': {'required': False, 'allow_null': True},
            'on_request': {'required': False}
        }

    def validate(self, data):
        on_request = data.get('on_request', None)
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        if on_request is None:
            data['on_request'] = True if not start_date and not end_date else False
            on_request = data['on_request']

        if on_request:
            data['start_date'] = None
            data['end_date'] = None
        else:
            if not start_date or not end_date:
                raise serializers.ValidationError('Поля start_date и end_date обязательны, если on_request=False.')
            if start_date > end_date:
                raise serializers.ValidationError('Дата начала не может быть позже даты окончания.')

        return data

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.on_request:
            return {'vehicle': representation['vehicle'], 'on_request': representation['on_request']}
        return representation


class VehicleDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleDocument
        fields = ['id', 'name', 'image', 'number']
        extra_kwargs = {
            'vehicle': {'required': False}
        }


class VehiclePhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehiclePhoto
        fields = ['photo']
        extra_kwargs = {
            'vehicle': {'required': False}
        }


class RentPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = RentPrice
        fields = ['name', 'price', 'discount', 'total']
        read_only_fields = ['total']

    def validate_discount(self, value):
        if value < 0 or value > 90:
            raise serializers.ValidationError('Скидка должна быть в диапазоне от 0 до 90.')
        return value


class VehicleBrandSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = VehicleBrand
        fields = ['id', 'name', 'logo_url']

    def get_logo_url(self, obj):
        request = self.context.get('request', None)
        if obj.logo and request is not None:
            return request.build_absolute_uri(obj.logo.url)
        return obj.logo.url if obj.logo else None


class VehicleModelGetSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleModel
        exclude = ['search_vector']


class VehicleModelSerializer(serializers.ModelSerializer):
    brand = serializers.PrimaryKeyRelatedField(
        queryset=VehicleBrand.objects.all(),
        required=True
    )

    class Meta:
        model = VehicleModel
        fields = ['id', 'name', 'brand']

    def create(self, validated_data):
        brand = validated_data['brand']
        name = validated_data['name']
        vehicle_model = VehicleModel.objects.create(brand=brand, name=name)
        return vehicle_model

    def update(self, instance, validated_data):
        instance.brand = validated_data.get('brand', instance.brand)
        instance.name = validated_data.get('name', instance.name)
        instance.save()
        return instance


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = ['id', 'name']


class BaseVehicleSerializer(serializers.ModelSerializer):
    payment_method = serializers.PrimaryKeyRelatedField(many=True, queryset=PaymentMethod.objects.all())
    availabilities = AvailabilitySerializer(many=True)
    # documents = VehicleDocumentSerializer(many=True)
    photos = VehiclePhotoSerializer(many=True)
    rent_prices = RentPriceSerializer(many=True)
    average_ratings = serializers.SerializerMethodField()

    @extend_schema_field(serializers.FloatField())
    def get_average_ratings(self, obj):
        return obj.get_average_rating()


class BaseVehicleUpdateSerializer(BaseVehicleSerializer):
    class Meta:
        fields = '__all__'
        read_only_fields = ['owner', 'ratings', 'average_ratings', 'count_trip']

    def to_internal_value(self, data):
        internal_value = super().to_internal_value(data)
        internal_value.pop('verified', None)
        return internal_value

    def update(self, instance, validated_data):
        request = self.context.get('request')
        original_verified = instance.verified

        safe_fields = {
            'long_distance',
            'delivery',
            'ensurance',
            'price_delivery',
            'payment_method',
            'drivers_rating',
            'acceptable_mileage',
            'drivers_age',
            'drivers_experience',
            'rent_prices',
            'availabilities',
            'price_deposit',
            'drivers_only_verified'
        }

        should_reset_verified = False

        prices_data = validated_data.pop('rent_prices', None)
        availabilities_data = validated_data.pop('availabilities', None)
        photos_data = validated_data.pop('photos', None)

        for field, new_value in validated_data.items():
            if field in safe_fields:
                continue
            old_value = getattr(instance, field, None)
            if old_value != new_value:
                should_reset_verified = True
                break

        if prices_data:
            if isinstance(prices_data, str):
                try:
                    prices_data = json.loads(prices_data)
                except json.JSONDecodeError:
                    prices_data = []

        if availabilities_data:
            if isinstance(availabilities_data, str):
                try:
                    availabilities_data = json.loads(availabilities_data)
                except json.JSONDecodeError:
                    availabilities_data = []

        if request and request.user.role in ['admin', 'manager']:
            instance.verified = True
        elif should_reset_verified:
            instance.verified = False
        else:
            instance.verified = original_verified

        instance = super().update(instance, validated_data)

        if prices_data is not None:
            instance.rent_prices.all().delete()
            RentPrice.objects.bulk_create([
                RentPrice(
                    vehicle=instance,
                    name=p['name'],
                    price=Decimal(str(p['price'])),
                    discount=Decimal(str(p.get('discount', 0)))
                )
                for p in prices_data
            ])

        if availabilities_data is not None:
            instance.availabilities.all().delete()
            Availability.objects.bulk_create([
                Availability(vehicle=instance, **availability_data)
                for availability_data in availabilities_data
            ])

        if photos_data is not None:
            existing_max_order = VehiclePhoto.objects.filter(vehicle=instance).aggregate(Max('order'))['order__max'] or 0
            new_photos = []
            for i, photo_data in enumerate(photos_data):
                if 'order' not in photo_data or photo_data['order'] is None:
                    photo_data['order'] = existing_max_order + i + 1
                new_photos.append(VehiclePhoto(vehicle=instance, **photo_data))
            VehiclePhoto.objects.bulk_create(new_photos)

        return instance


class BaseVehicleCreateSerializer(BaseVehicleSerializer):
    class Meta:
        fields = '__all__'
        read_only_fields = ['owner', 'ratings', 'average_ratings', 'verified', 'count_trip']

    def validate_year(self, value):
        current_year = timezone.now().year
        if value < 1900 or value > current_year:
            raise serializers.ValidationError(f'Год выпуска должен быть в пределах от 1900 до {current_year}.')
        return value

    def validate(self, data):
        model_id = data.get('model')

        if not model_id:
            raise serializers.ValidationError("Модель транспортного средства не указана.")
        
        try:
            vehicle_model = VehicleModel.objects.get(id=model_id.id if hasattr(model_id, 'id') else model_id)
        except VehicleModel.DoesNotExist:
            raise serializers.ValidationError(f"Модель с ID {model_id} не найдена.")

        # Определяем тип транспорта по классу сериализатора
        serializer_class_name = self.__class__.__name__
        if 'Auto' in serializer_class_name:
            expected_vehicle_type = 'auto'
        elif 'Bike' in serializer_class_name:
            expected_vehicle_type = 'bike'
        elif 'Ship' in serializer_class_name:
            expected_vehicle_type = 'ship'
        elif 'Helicopter' in serializer_class_name:
            expected_vehicle_type = 'helicopter'
        elif 'SpecialTechnic' in serializer_class_name:
            expected_vehicle_type = 'special_technic'
        else:
            raise serializers.ValidationError("Неизвестный тип транспортного средства.")

        if vehicle_model.vehicle_type and vehicle_model.vehicle_type != expected_vehicle_type:
            raise serializers.ValidationError(
                f"Модель {vehicle_model.name} не подходит для типа транспорта '{expected_vehicle_type}'."
            )

        return data

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['owner'] = request.user

        availabilities_data = validated_data.pop('availabilities', [])
        # documents_data = validated_data.pop('documents', [])
        prices_data = validated_data.pop('rent_prices', [])
        photos_data = validated_data.pop('photos', [])
        min_rent_day = validated_data.get('min_rent_day', '')
        max_rent_day = validated_data.get('max_rent_day', '')

        if min_rent_day is not None and max_rent_day is not None:
            try:
                min_rent_day = int(min_rent_day)
                max_rent_day = int(max_rent_day)

                if min_rent_day > max_rent_day:
                    raise serializers.ValidationError(
                        f"Минимальное количество дней для аренды должно быть меньше "
                        f"максимального количества дней. min_rent_day = {min_rent_day}, "
                        f"max_rent_day = {max_rent_day}"
                    )

                validated_data['min_rent_day'] = min_rent_day
                validated_data['max_rent_day'] = max_rent_day
            except (ValueError, TypeError):
                raise serializers.ValidationError(
                    "min_rent_day и max_rent_day должны быть числами"
                )

        if any(not availability.get('on_request', True) for availability in availabilities_data):
            availabilities_data = merge_periods(availabilities_data)

        vehicle = super().create(validated_data)

        for availability_data in availabilities_data:
            Availability.objects.create(vehicle=vehicle, **availability_data)

        # for document_data in documents_data:
        #     VehicleDocument.objects.create(vehicle=vehicle, **document_data)

        for price_data in prices_data:
            RentPrice.objects.create(vehicle=vehicle, **price_data)

        for i, photo_data in enumerate(photos_data, start=1):
            if 'order' not in photo_data or photo_data['order'] is None:
                photo_data['order'] = i
            VehiclePhoto.objects.create(vehicle=vehicle, **photo_data)

        return vehicle


class BaseVehicleGetSerializer(serializers.ModelSerializer):
    payment_method = serializers.SerializerMethodField()
    availabilities = AvailabilitySerializer(many=True)
    # documents = VehicleDocumentSerializer(many=True)
    photos = serializers.SerializerMethodField()
    rent_prices = RentPriceSerializer(many=True)
    average_ratings = serializers.SerializerMethodField()
    brand = VehicleBrandSerializer(read_only=True)
    model = VehicleModelGetSerializer(read_only=True)
    commission = serializers.SerializerMethodField()
    city_title = serializers.SerializerMethodField()

    class Meta:
        fields = '__all__'
        read_only_fields = ['owner', 'average_ratings', 'verified']

    def get_city_title(self, obj):
        return obj.city.title

    def get_commission(self, obj):
        if obj.owner.lessor.franchise:
            return obj.owner.lessor.commission + Decimal(obj.owner.lessor.franchise.commission)
        return obj.owner.lessor.commission

    @extend_schema_field(serializers.FloatField())
    def get_average_ratings(self, obj):
        return obj.get_average_rating()

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_payment_method(self, obj):
        return [payment.name for payment in obj.payment_method.all()]

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_photos(self, obj):
        return [
            {"id": i.id, "url": f"{HOST_URL}/{i.photo.url}", "order": i.order}
            for i in obj.photos.all()
        ]


class BaseVehicleListSerializer(serializers.ModelSerializer):
    availabilities = AvailabilitySerializer(many=True)
    photos = serializers.SerializerMethodField()
    rent_prices = RentPriceSerializer(many=True)
    brand = VehicleBrandSerializer(read_only=True)
    model = VehicleModelGetSerializer(read_only=True)
    vehicle_type = serializers.SerializerMethodField()
    free_delivery = serializers.SerializerMethodField()
    free_deposit = serializers.SerializerMethodField()
    is_super_host = serializers.SerializerMethodField()
    city = serializers.StringRelatedField()
    average_rating = serializers.FloatField(read_only=True)
    lessor = serializers.SerializerMethodField()


    class Meta:
        fields = [
            'id', 'brand', 'model', 'average_rating', 'rent_prices', 'availabilities', 'is_super_host',
            'photos', 'vehicle_type', 'free_delivery', 'free_deposit', 'latitude', 'longitude', 'city', 'verified',
            'lessor']

    def get_city(self, obj):
        return obj.city.title if obj.city else None

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_photos(self, obj):
        return [f"{HOST_URL}/{i.photo.url}" for i in obj.photos.all()]

    @extend_schema_field(serializers.CharField())
    def get_vehicle_type(self, obj):
        """Определяем тип транспорта по классу объекта"""
        if isinstance(obj, Auto):
            return 'auto'
        elif isinstance(obj, Bike):
            return 'bike'
        elif isinstance(obj, Ship):
            return 'ship'
        elif isinstance(obj, Helicopter):
            return 'helicopter'
        elif isinstance(obj, SpecialTechnic):
            return 'special_technic'
        return 'unknown'

    @extend_schema_field(serializers.BooleanField())
    def get_free_delivery(self, obj):
        return obj.delivery and obj.price_delivery == 0

    @extend_schema_field(serializers.BooleanField())
    def get_free_deposit(self, obj):
        return obj.price_deposit == 0

    @extend_schema_field(serializers.BooleanField())
    def get_is_super_host(self, obj):
        return obj.owner.lessor.super_host

    @extend_schema_field(serializers.DictField())
    def get_lessor(self, obj):
        owner = obj.owner
        return {
            "id": owner.lessor.id,
            "user_id": owner.id,
            "first_name": owner.first_name,
            "last_name": owner.last_name,
            "telephone": owner.telephone if owner.telephone else None,
            "avatar": owner.avatar.url if getattr(owner, "avatar", None) and owner.avatar.name else None
        }


class VehicleClassSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleClass
        fields = '__all__'


class VehicleSerializer(serializers.ModelSerializer):
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    model_name = serializers.CharField(source='model.name', read_only=True)
    vehicle_type = serializers.CharField(source='get_vehicle_type_display', read_only=True)

    class Meta:
        model = Vehicle
        fields = ['id', 'brand_name', 'model_name', 'vehicle_type']


class UpdatePhotoOrderSerializer(serializers.Serializer):
    photo_id = serializers.IntegerField(required=True, help_text="ID фотографии")
    new_order = serializers.IntegerField(required=True, min_value=1, help_text="Новый порядок фотографии")

    def validate_photo_id(self, value):
        if not VehiclePhoto.objects.filter(id=value).exists():
            raise serializers.ValidationError("Фото с таким ID не существует.")
        return value
