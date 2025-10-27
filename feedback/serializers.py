from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from app.models import Rating
from chat.models import Trip
from chat.serializers import VehicleRelatedField
from feedback.models import Feedback, FeedbackRenter
from vehicle.models import RatingUpdateLog


class FeedbackCreateSerializer(serializers.ModelSerializer):
    content_type = serializers.CharField()

    class Meta:
        model = Feedback
        fields = ['id', 'content', 'content_type', 'object_id']

    def validate_content_type(self, value):
        try:
            content_type = ContentType.objects.get(model=value.lower())
        except ContentType.DoesNotExist:
            raise serializers.ValidationError("Указанный тип контента не существует.")
        return content_type

    def create(self, validated_data):
        return super().create(validated_data)


class FeedbackUpdateSerializer(serializers.ModelSerializer):
    answer = serializers.CharField(required=True)

    class Meta:
        model = Feedback
        fields = ['answer']

    def validate_answer(self, value):
        request = self.context.get('request')
        if self.instance.vehicle.owner != request.user:
            raise serializers.ValidationError("Только владелец транспорта может оставлять ответы на отзывы.")
        return value


class FeedbackSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    answer = serializers.CharField(required=False, allow_blank=True)
    vehicle = VehicleRelatedField()
    average_ratings = serializers.SerializerMethodField()

    class Meta:
        model = Feedback
        fields = ['id', 'user', 'content', 'answer', 'content_type', 'object_id', 'vehicle', 'average_ratings', 'timestamp']

    def get_user(self, obj):
        if obj.user:
            return {
                "id": obj.user.id,
                "first_name": obj.user.first_name,
                "avatar": obj.user.avatar.url if obj.user.avatar else None
            }
        return None

    def get_average_ratings(self, obj):
        content_type = ContentType.objects.get_for_model(obj.vehicle)

        try:
            log = RatingUpdateLog.objects.get(
                user=obj.user,
                content_type=content_type,
                object_id=obj.vehicle.id
            )

            ratings_sum = (
                (log.cleanliness or 0) +
                (log.maintenance or 0) +
                (log.communication or 0) +
                (log.convenience or 0) +
                (log.accuracy or 0)
            )
            average_rating = ratings_sum / 5
            return round(average_rating, 2)
        except RatingUpdateLog.DoesNotExist:
            return None


class FeedbackRenterCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeedbackRenter
        fields = ['id', 'renter', 'content']

    def validate_renter(self, value):
        if value.user == self.context['request'].user:
            raise serializers.ValidationError("Нельзя оставить отзыв самому себе.")
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        renter_instance = validated_data['renter']

        trips = Trip.objects.filter(organizer=renter_instance.user, status='finished')
        if not trips.exists():
            raise serializers.ValidationError(
                "Для того чтобы оставить отзыв, необходимо, чтобы поездка была завершена."
            )

        trip_found = any(trip.vehicle and trip.vehicle.owner == user for trip in trips)

        if not trip_found:
            raise serializers.ValidationError("Вы не являетесь владельцем транспортного средства в завершенной поездке.")

        if FeedbackRenter.objects.filter(user=user, renter=renter_instance).exists():
            raise serializers.ValidationError("Вы уже оставили отзыв этому арендатору.")

        validated_data['user'] = user
        return FeedbackRenter.objects.create(**validated_data)


class FeedbackRenterSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    renter = serializers.SerializerMethodField()
    rating = serializers.SerializerMethodField()

    class Meta:
        model = FeedbackRenter
        fields = ['id', 'user', 'renter', 'content', 'answer', 'timestamp', 'rating']

    def get_rating(self, obj):
        try:
            rating = Rating.objects.get(user=obj.user, renter=obj.renter)
            return rating.rating
        except Rating.DoesNotExist:
            return None

    def get_user(self, obj):
        return {
            'id': obj.user.id,
            'first_name': obj.user.first_name,
            'avatar': obj.user.avatar.url if obj.user.avatar else None
        }

    def get_renter(self, obj):
        renter_user = obj.renter.user
        return {
            'id': obj.renter.id,
            'first_name': renter_user.first_name,
            'avatar': renter_user.avatar.url if renter_user.avatar else None
        }


class FeedbackRenterUpdateSerializer(serializers.ModelSerializer):
    answer = serializers.CharField(required=True)

    class Meta:
        model = FeedbackRenter
        fields = ['answer']

    def validate_answer(self, value):
        request = self.context.get('request')
        if self.instance.renter.user != request.user:
            raise serializers.ValidationError("Только арендатор может ответить на отзыв.")
        return value

    def update(self, instance, validated_data):
        instance.answer = validated_data.get('answer', instance.answer)
        instance.save()
        return instance
