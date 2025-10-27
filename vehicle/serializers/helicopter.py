from rest_framework import serializers

from vehicle.models import Helicopter, VehicleClass
from vehicle.serializers.base import BaseVehicleGetSerializer, BaseVehicleListSerializer, \
    BaseVehicleCreateSerializer, BaseVehicleUpdateSerializer, VehicleClassSerializer


class HelicopterCreateSerializer(BaseVehicleCreateSerializer):
    vehicle_class = serializers.PrimaryKeyRelatedField(queryset=VehicleClass.objects.all())

    class Meta(BaseVehicleCreateSerializer.Meta):
        model = Helicopter

    def validate_acceptable_mileage(self, value):
        if value < 10 or value > 100000:
            raise serializers.ValidationError('Допустимый пробег должен быть в пределах от 10 до 100000')
        return value

    def validate(self, data):
        return data

class HelicopterUpdateSerializer(BaseVehicleUpdateSerializer):
    vehicle_class = serializers.PrimaryKeyRelatedField(queryset=VehicleClass.objects.all())

    class Meta(BaseVehicleUpdateSerializer.Meta):
        model = Helicopter


class HelicopterGetSerializer(BaseVehicleGetSerializer):
    vehicle_class = VehicleClassSerializer()

    class Meta(BaseVehicleGetSerializer.Meta):
        model = Helicopter


class HelicopterListSerializer(BaseVehicleListSerializer):
    class Meta(BaseVehicleListSerializer.Meta):
        model = Helicopter
