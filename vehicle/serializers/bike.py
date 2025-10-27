from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from vehicle.models import Bike, BikeFeaturesAdditionally, BikeTransmission, VehicleClass, \
    BikeFeaturesFunctions, BikeBodyType
from vehicle.serializers.base import BaseVehicleGetSerializer, BaseVehicleListSerializer, BaseVehicleCreateSerializer, \
    BaseVehicleUpdateSerializer, VehicleClassSerializer


class BikeTransmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = BikeTransmission
        fields = '__all__'


class BikeBodyTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BikeBodyType
        fields = '__all__'


class BikeCreateSerializer(BaseVehicleCreateSerializer):
    features_functions = serializers.PrimaryKeyRelatedField(many=True, queryset=BikeFeaturesFunctions.objects.all(), required=False)
    features_additionally = serializers.PrimaryKeyRelatedField(many=True, queryset=BikeFeaturesAdditionally.objects.all(), required=False)
    transmission = serializers.PrimaryKeyRelatedField(queryset=BikeTransmission.objects.all())
    vehicle_class = serializers.PrimaryKeyRelatedField(queryset=VehicleClass.objects.all())
    body_type = serializers.PrimaryKeyRelatedField(queryset=BikeBodyType.objects.all())

    class Meta(BaseVehicleCreateSerializer.Meta):
        model = Bike

    def validate_seats(self, value):
        if value < 1 or value > 3:
            raise serializers.ValidationError('Количество сидений должно быть в пределах от 1 до 3.')
        return value

    def validate_drivers_age(self, value):
        if value < 18 or value > 80:
            raise serializers.ValidationError('Возраст водителя должен быть в пределах от 18 до 80 лет.')
        return value

    def validate_drivers_experience(self, value):
        if value < 0 or value > 70:
            raise serializers.ValidationError('Стаж водителя должен быть в пределах от 0 до 70 лет.')
        return value

    def validate_acceptable_mileage(self, value):
        if value < 10 or value > 10000:
            raise serializers.ValidationError('Допустимый пробег должен быть в пределах от 10 до 10000')
        return value

    def create(self, validated_data):
        features_functions_data = validated_data.pop('features_functions', [])
        features_additionally_data = validated_data.pop('features_additionally', [])

        vehicle = super().create(validated_data)

        vehicle.features_functions.set(features_functions_data)
        vehicle.features_additionally.set(features_additionally_data)

        return vehicle

    def validate(self, data):
        return data


class BikeUpdateSerializer(BaseVehicleUpdateSerializer):
    features_functions = serializers.PrimaryKeyRelatedField(many=True, queryset=BikeFeaturesFunctions.objects.all())
    features_additionally = serializers.PrimaryKeyRelatedField(many=True, queryset=BikeFeaturesAdditionally.objects.all())
    transmission = serializers.PrimaryKeyRelatedField(queryset=BikeTransmission.objects.all())
    vehicle_class = serializers.PrimaryKeyRelatedField(queryset=VehicleClass.objects.all())
    body_type = serializers.PrimaryKeyRelatedField(queryset=BikeBodyType.objects.all())

    class Meta(BaseVehicleUpdateSerializer.Meta):
        model = Bike


class BikeFeaturesAdditionallySerializer(serializers.ModelSerializer):
    class Meta:
        model = BikeFeaturesAdditionally
        fields = '__all__'


class BikeFeaturesFunctionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BikeFeaturesFunctions
        fields = '__all__'


class BikeGetSerializer(BaseVehicleGetSerializer):
    features_functions = serializers.SerializerMethodField()
    features_additionally = serializers.SerializerMethodField()
    transmission = BikeTransmissionSerializer()
    vehicle_class = VehicleClassSerializer()
    body_type = BikeBodyTypeSerializer()

    class Meta(BaseVehicleGetSerializer.Meta):
        model = Bike

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_features_functions(self, obj):
        return [feature.name for feature in obj.features_functions.all()]

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_features_additionally(self, obj):
        return [feature.name for feature in obj.features_additionally.all()]


class BikeListSerializer(BaseVehicleListSerializer):
    class Meta(BaseVehicleListSerializer.Meta):
        model = Bike
