from rest_framework import serializers

from vehicle.models import SpecialTechnic, TechnicType
from vehicle.serializers.base import BaseVehicleGetSerializer, BaseVehicleListSerializer, BaseVehicleCreateSerializer, BaseVehicleUpdateSerializer


class TechnicTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TechnicType
        fields = '__all__'


class SpecialTechnicCreateSerializer(BaseVehicleCreateSerializer):
    type_technic = serializers.PrimaryKeyRelatedField(queryset=TechnicType.objects.all())

    class Meta(BaseVehicleCreateSerializer.Meta):
        model = SpecialTechnic

    def validate(self, data):
        return data


class SpecialTechnicUpdateSerializer(BaseVehicleUpdateSerializer):
    type_technic = serializers.PrimaryKeyRelatedField(queryset=TechnicType.objects.all())

    class Meta(BaseVehicleUpdateSerializer.Meta):
        model = SpecialTechnic


class SpecialTechnicGetSerializer(BaseVehicleGetSerializer):
    type_technic = TechnicTypeSerializer()

    class Meta(BaseVehicleGetSerializer.Meta):
        model = SpecialTechnic


class SpecialTechnicListSerializer(BaseVehicleListSerializer):
    class Meta(BaseVehicleListSerializer.Meta):
        model = SpecialTechnic
