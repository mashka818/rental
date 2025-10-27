from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from vehicle.models import ShipFeaturesAdditionally, FeaturesEquipment, Ship, VehicleClass, ShipFeaturesFunctions, \
    ShipType
from vehicle.serializers.base import BaseVehicleGetSerializer, BaseVehicleListSerializer, \
    BaseVehicleCreateSerializer, BaseVehicleUpdateSerializer, VehicleClassSerializer


class ShipTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShipType
        fields = '__all__'


class ShipCreateSerializer(BaseVehicleCreateSerializer):
    features_functions = serializers.PrimaryKeyRelatedField(many=True, queryset=ShipFeaturesFunctions.objects.all(), required=False)
    features_additionally = serializers.PrimaryKeyRelatedField(many=True, queryset=ShipFeaturesAdditionally.objects.all(), required=False)
    features_equipment = serializers.PrimaryKeyRelatedField(many=True, queryset=FeaturesEquipment.objects.all(), required=False)
    vehicle_class = serializers.PrimaryKeyRelatedField(queryset=VehicleClass.objects.all())
    type_ship = serializers.PrimaryKeyRelatedField(queryset=ShipType.objects.all())

    class Meta(BaseVehicleCreateSerializer.Meta):
        model = Ship

    def validate_seats(self, value):
        if value < 1 or value > 50:
            raise serializers.ValidationError('Количество сидений должно быть в пределах от 1 до 50.')
        return value

    def validate_acceptable_mileage(self, value):
        if value < 10 or value > 10000:
            raise serializers.ValidationError('Допустимый пробег должен быть в пределах от 10 до 10000')
        return value

    def create(self, validated_data):
        features_functions_data = validated_data.pop('features_functions', [])
        features_additionally_data = validated_data.pop('features_additionally', [])
        features_equipment_data = validated_data.pop('features_equipment', [])

        vehicle = super().create(validated_data)

        vehicle.features_functions.set(features_functions_data)
        vehicle.features_additionally.set(features_additionally_data)
        vehicle.features_equipment.set(features_equipment_data)

        return vehicle

    def validate(self, data):
        return data


class ShipUpdateSerializer(BaseVehicleUpdateSerializer):
    features_functions = serializers.PrimaryKeyRelatedField(many=True, queryset=ShipFeaturesFunctions.objects.all())
    features_additionally = serializers.PrimaryKeyRelatedField(many=True, queryset=ShipFeaturesAdditionally.objects.all())
    features_equipment = serializers.PrimaryKeyRelatedField(many=True, queryset=FeaturesEquipment.objects.all())
    vehicle_class = serializers.PrimaryKeyRelatedField(queryset=VehicleClass.objects.all())
    type_ship = serializers.PrimaryKeyRelatedField(queryset=ShipType.objects.all())

    class Meta(BaseVehicleUpdateSerializer.Meta):
        model = Ship


class ShipFeaturesAdditionallySerializer(serializers.ModelSerializer):
    class Meta:
        model = ShipFeaturesAdditionally
        fields = '__all__'


class FeaturesEquipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeaturesEquipment
        fields = '__all__'


class ShipFeaturesFunctionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShipFeaturesFunctions
        fields = '__all__'


class ShipGetSerializer(BaseVehicleGetSerializer):
    features_functions = serializers.SerializerMethodField()
    features_additionally = serializers.SerializerMethodField()
    features_equipment = serializers.SerializerMethodField()
    vehicle_class = VehicleClassSerializer()
    type_ship = ShipTypeSerializer()

    class Meta(BaseVehicleGetSerializer.Meta):
        model = Ship

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_features_functions(self, obj):
        return [feature.name for feature in obj.features_functions.all()]

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_features_additionally(self, obj):
        return [feature.name for feature in obj.features_additionally.all()]

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_features_equipment(self, obj):
        return [feature.name for feature in obj.features_equipment.all()]


class ShipListSerializer(BaseVehicleListSerializer):
    class Meta(BaseVehicleListSerializer.Meta):
        model = Ship
