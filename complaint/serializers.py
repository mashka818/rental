from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from .models import Complaint, ComplaintForFeedback, ComplaintForFeedbackRenter


class BaseComplaintSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)

    def create(self, validated_data):
        request_user = self.context['request'].user
        validated_data['user'] = request_user

        unique_filter = {field: validated_data[field] for field in self.Meta.unique_fields}
        unique_filter['user'] = request_user

        if self.Meta.model.objects.filter(**unique_filter).exists():
            raise serializers.ValidationError("Вы уже подали жалобу на данный объект.")

        return super().create(validated_data)

    def validate(self, data):
        return super().validate(data)


class ComplaintSerializer(BaseComplaintSerializer):
    class Meta:
        model = Complaint
        fields = ['id', 'user', 'vehicle', 'topic', 'description']
        unique_fields = ['vehicle']


class ComplaintFeedbackSerializer(BaseComplaintSerializer):
    class Meta:
        model = ComplaintForFeedback
        fields = ['id', 'user', 'feedback', 'topic', 'description']
        read_only_fields = ['user']
        unique_fields = ['feedback']

    def validate(self, attrs):
        """
        Проверяем, что жалобу может создать только владелец транспорта.
        """
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise PermissionDenied("Анонимные пользователи не могут создавать жалобы.")

        feedback = attrs.get('feedback')
        if not feedback:
            raise serializers.ValidationError("Поле feedback обязательно.")

        if feedback.vehicle.owner != request.user:
            raise PermissionDenied("Вы не являетесь владельцем транспортного средства, связанного с этим отзывом.")

        return attrs

    def create(self, validated_data):
        """
        Переопределяем метод create для автоматического заполнения user.
        """
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class ComplaintFeedbackRenterSerializer(BaseComplaintSerializer):
    class Meta:
        model = ComplaintForFeedbackRenter
        fields = ['id', 'user', 'feedback', 'topic', 'description']
        unique_fields = ['feedback']
        read_only_fields = ['user']

    def validate(self, attrs):
        """
        Проверяем, что жалобу может создать только владелец транспорта.
        """
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise PermissionDenied("Анонимные пользователи не могут создавать жалобы.")

        feedback = attrs.get('feedback')
        if not feedback:
            raise serializers.ValidationError("Поле feedback обязательно.")

        if feedback.renter.user != request.user:
            raise PermissionDenied("Вы не являетесь арендатором, связанным с этим отзывом.")

        return attrs