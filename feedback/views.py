import logging

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from RentalGuru import settings
from app.models import Renter
from chat.models import Trip
from feedback.filters import FeedbackFilter, FeedbackRenterFilter
from feedback.models import Feedback, FeedbackRenter
from feedback.permissions import IsRenterOrAdminOrManager, IsOwnerOrAdminOrManager
from feedback.serializers import FeedbackSerializer, FeedbackCreateSerializer, FeedbackUpdateSerializer, \
    FeedbackRenterCreateSerializer, FeedbackRenterUpdateSerializer, FeedbackRenterSerializer
from notification.models import Notification


@extend_schema(summary="Отзывы", description="Отзывы к транспорту может оставлять только пользователь, который "
                                             "пользовался транспортом, только после завершения поездки и только один "
                                             "отзыв к одному транспорту. Отвечать на отзывы может только хозяин "
                                             "транспорта")
class FeedbackViewSet(viewsets.ModelViewSet):
    queryset = Feedback.objects.select_related('user', 'content_type').all()
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend]
    filterset_class = FeedbackFilter
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']

    def get_serializer_class(self):
        if self.action in ['create']:
            return FeedbackCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return FeedbackUpdateSerializer
        return FeedbackSerializer

    def perform_create(self, serializer):
        content_type = serializer.validated_data['content_type']
        object_id = serializer.validated_data['object_id']

        existing_feedback = Feedback.objects.filter(
            user=self.request.user,
            content_type=content_type,
            object_id=object_id
        ).exists()
        if existing_feedback:
            raise serializers.ValidationError("Вы уже оставили отзыв для данного транспортного средства.")

        try:
            trips = Trip.objects.filter(
                organizer=self.request.user,
                content_type=content_type,
                object_id=object_id
            )
        except Trip.DoesNotExist:
            raise serializers.ValidationError(
                "Для того чтобы оставить отзыв, нужно воспользоваться данным транспортом."
            )

        if not trips.filter(status='finished').exists():
            raise serializers.ValidationError("Поездка не была завершена.")

        serializer.save(user=self.request.user)
        model_class = content_type.model_class()
        try:
            vehicle_instance = model_class.objects.get(id=object_id)
        except model_class.DoesNotExist:
            raise serializers.ValidationError(f"Транспортное средство с идентификатором {object_id} не существует.")
        content = f'Добавлен отзыв для транспорта {vehicle_instance}'
        url = f'{settings.HOST_URL}/feedback/feedbacks/{object_id}'
        Notification.objects.create(user=vehicle_instance.owner, content=content, url=url)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if 'answer' in request.data:
            if instance.vehicle.owner != request.user:
                raise serializers.ValidationError("Только владелец транспорта может оставлять ответы на отзывы.")
            instance.answer = request.data['answer']
            instance.save()

            content = f'Добавлен ответ на отзыв для транспорта'
            url = f'{settings.HOST_URL}/feedback/feedbacks/{instance.id}'
            Notification.objects.create(user=instance.user, content=content, url=url)

            return Response(FeedbackSerializer(instance).data)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)


@extend_schema(
    summary="Отзывы о арендаторах",
    description="Отзывы о арендаторах могут оставлять только арендодатели, у которых они арендовали транспорт."
)
class FeedbackRenterViewSet(viewsets.ModelViewSet):
    queryset = FeedbackRenter.objects.select_related('user', 'renter').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = FeedbackRenterFilter
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']

    def get_permissions(self):
        if self.action in ['create']:
            return [IsAuthenticated()]
        elif self.action in ['update', 'partial_update']:
            return [IsRenterOrAdminOrManager()]
        elif self.action in ['destroy']:
            return [IsOwnerOrAdminOrManager()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == 'create':
            return FeedbackRenterCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return FeedbackRenterUpdateSerializer
        return FeedbackRenterSerializer

    def perform_create(self, serializer):
        renter_instance = serializer.validated_data.get('renter')
        if not renter_instance:
            raise serializers.ValidationError("Необходимо указать арендатора.")

        if FeedbackRenter.objects.filter(user=self.request.user, renter=renter_instance).exists():
            raise serializers.ValidationError("Вы уже оставили отзыв этому арендатору.")

        feedback = serializer.save(user=self.request.user)

        content = 'Добавлен отзыв'
        url = f'{settings.HOST_URL}/feedback/feedbacks_renter/{feedback.id}'
        Notification.objects.create(user=renter_instance.user, content=content, url=url)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if 'answer' in request.data:
            if instance.renter.user != request.user:
                raise serializers.ValidationError("Только арендатор может ответить на отзыв.")
            instance.answer = request.data['answer']
            instance.save()

            content = 'Добавлен ответ на отзыв'
            url = f'{settings.HOST_URL}/feedback/feedbacks_renter/{instance.id}'
            Notification.objects.create(user=instance.user, content=content, url=url)

            return Response(FeedbackRenterSerializer(instance).data)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)
