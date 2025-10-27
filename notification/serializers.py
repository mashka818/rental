from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'user', 'content', 'read_it', 'url', 'created_at']
        read_only_fields = ['user', 'read_it', 'created_at']

    def create(self, validated_data):
        request = self.context.get('request')
        notification = Notification.objects.create(user=request.user, **validated_data)
        notification.send_notification()
        return notification
