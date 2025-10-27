from rest_framework import serializers

from chat.models import Trip
from vehicle.models import Vehicle
import logging

logger = logging.getLogger(__name__)


class TripSerializer(serializers.ModelSerializer):
    organizer = serializers.StringRelatedField()
    organizer_user_id = serializers.IntegerField(source='organizer.id')
    organizer_renter_id = serializers.IntegerField(source='organizer.renter.id')
    organizer_telephone = serializers.CharField(source='organizer.telephone')
    organizer_avatar = serializers.ImageField(source='organizer.avatar', allow_null=True)
    organizer_rating = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()
    object = serializers.SerializerMethodField()
    owner_user_id = serializers.SerializerMethodField()
    owner_lessor_id = serializers.SerializerMethodField()
    owner = serializers.SerializerMethodField()
    owner_telephone = serializers.SerializerMethodField()
    owner_avatar = serializers.SerializerMethodField()
    chat_id = serializers.SerializerMethodField()

    class Meta:
        model = Trip
        fields = ['id', 'type', 'status', 'object', 'object_id', 'start_date', 'end_date', 'total_cost',
                  'owner_user_id', 'owner_lessor_id', 'owner', 'owner_telephone', 'owner_avatar', 'chat_id',
                  'organizer', 'organizer_user_id', 'organizer_renter_id', 'organizer_telephone', 'organizer_avatar',
                  'organizer_rating']

    def get_chat_id(self, obj):
        if obj.chat:
            return obj.chat.id
        else:
            return None

    def get_organizer_rating(self, obj):
        renter = getattr(obj.organizer, 'renter', None)
        if renter:
            return renter.get_average_rating()

        logger.warning(f"User {obj.organizer} has no related Renter object.")
        return 0

    def get_type(self, obj):
        return obj.content_type.model

    def get_object(self, obj):
        vehicle = Vehicle.objects.filter(id=obj.object_id).first()
        return str(vehicle) if vehicle else None

    def get_owner(self, obj):
        vehicle = Vehicle.objects.filter(id=obj.object_id).first()
        return str(vehicle.owner) if vehicle and vehicle.owner else None

    def get_owner_user_id(self, obj):
        vehicle = Vehicle.objects.filter(id=obj.object_id).first()
        return vehicle.owner.id if vehicle and vehicle.owner else None

    def get_owner_lessor_id(self, obj):
        vehicle = Vehicle.objects.filter(id=obj.object_id).first()
        return vehicle.owner.lessor.id if vehicle and vehicle.owner else None
    
    def get_owner_telephone(self, obj):
        vehicle = Vehicle.objects.filter(id=obj.object_id).first()
        return vehicle.owner.telephone if vehicle and vehicle.owner else None

    def get_owner_avatar(self, obj):
        vehicle = Vehicle.objects.filter(id=obj.object_id).first()
        if vehicle and vehicle.owner and vehicle.owner.avatar:
            return vehicle.owner.avatar.url
        return None
