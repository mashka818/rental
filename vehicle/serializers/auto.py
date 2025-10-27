from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .base import BaseVehicleGetSerializer, BaseVehicleListSerializer, \
    BaseVehicleCreateSerializer, BaseVehicleUpdateSerializer, VehicleClassSerializer
from ..models import FeaturesForChildren, AutoFeaturesAdditionally, Auto, AutoFuelType, \
    AutoTransmission, AutoBodyType, VehicleClass, AutoFeaturesFunctions


class AutoFuelTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutoFuelType
        fields = '__all__'


class AutoTransmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutoTransmission
        fields = '__all__'


class AutoBodyTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutoBodyType
        fields = '__all__'


class AutoCreateSerializer(BaseVehicleCreateSerializer):
    features_for_children = serializers.PrimaryKeyRelatedField(many=True, queryset=FeaturesForChildren.objects.all(), required=False)
    features_functions = serializers.PrimaryKeyRelatedField(many=True, queryset=AutoFeaturesFunctions.objects.all(), required=False)
    features_additionally = serializers.PrimaryKeyRelatedField(many=True, queryset=AutoFeaturesAdditionally.objects.all(), required=False)
    fuel_type = serializers.PrimaryKeyRelatedField(queryset=AutoFuelType.objects.all())
    transmission = serializers.PrimaryKeyRelatedField(queryset=AutoTransmission.objects.all())
    body_type = serializers.PrimaryKeyRelatedField(queryset=AutoBodyType.objects.all())
    vehicle_class = serializers.PrimaryKeyRelatedField(queryset=VehicleClass.objects.all())

    class Meta(BaseVehicleCreateSerializer.Meta):
        model = Auto

    def validate_seats(self, value):
        if value < 2 or value > 50:
            raise serializers.ValidationError('Количество сидений должно быть в пределах от 2 до 50.')
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

        features_for_children_data = validated_data.pop('features_for_children', [])
        features_functions_data = validated_data.pop('features_functions', [])
        features_additionally_data = validated_data.pop('features_additionally', [])

        vehicle = super().create(validated_data)

        vehicle.features_for_children.set(features_for_children_data)
        vehicle.features_functions.set(features_functions_data)
        vehicle.features_additionally.set(features_additionally_data)

        return vehicle

    def validate(self, data):
        return data


class AutoUpdateSerializer(BaseVehicleUpdateSerializer):
    features_for_children = serializers.PrimaryKeyRelatedField(many=True, queryset=FeaturesForChildren.objects.all())
    features_functions = serializers.PrimaryKeyRelatedField(many=True, queryset=AutoFeaturesFunctions.objects.all())
    features_additionally = serializers.PrimaryKeyRelatedField(many=True, queryset=AutoFeaturesAdditionally.objects.all())
    fuel_type = serializers.PrimaryKeyRelatedField(queryset=AutoFuelType.objects.all())
    transmission = serializers.PrimaryKeyRelatedField(queryset=AutoTransmission.objects.all())
    body_type = serializers.PrimaryKeyRelatedField(queryset=AutoBodyType.objects.all())
    vehicle_class = serializers.PrimaryKeyRelatedField(queryset=VehicleClass.objects.all())

    class Meta(BaseVehicleUpdateSerializer.Meta):
        model = Auto


class FeaturesForChildrenSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeaturesForChildren
        fields = '__all__'


class AutoFeaturesAdditionallySerializer(serializers.ModelSerializer):
    class Meta:
        model = AutoFeaturesAdditionally
        fields = '__all__'


class AutoFeaturesFunctionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutoFeaturesFunctions
        fields = '__all__'


class AutoGetSerializer(BaseVehicleGetSerializer):
    features_for_children = serializers.SerializerMethodField()
    features_functions = serializers.SerializerMethodField()
    features_additionally = serializers.SerializerMethodField()

    fuel_type = AutoFuelTypeSerializer()
    transmission = AutoTransmissionSerializer()
    body_type = AutoBodyTypeSerializer()
    vehicle_class = VehicleClassSerializer()

    class Meta(BaseVehicleGetSerializer.Meta):
        model = Auto

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_features_for_children(self, obj):
        return [feature.name for feature in obj.features_for_children.all()]

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_features_functions(self, obj):
        return [feature.name for feature in obj.features_functions.all()]

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_features_additionally(self, obj):
        return [feature.name for feature in obj.features_additionally.all()]


class AutoListSerializer(BaseVehicleListSerializer):
    class Meta(BaseVehicleListSerializer.Meta):
        model = Auto
