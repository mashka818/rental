from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from RentalGuru import settings
from notification.models import Notification
from .models import Complaint, ComplaintForFeedback, ComplaintForFeedbackRenter
from .permissions import PermissionVehicle
from .serializers import ComplaintSerializer, ComplaintFeedbackSerializer, ComplaintFeedbackRenterSerializer


class BaseComplaintViewSet(ModelViewSet):
    filter_backends = [DjangoFilterBackend]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
        complaint = serializer.instance
        self.create_notification(complaint)

    def create_notification(self, complaint):
        """
        Метод для создания уведомления. Реализуется в дочерних классах.
        """
        raise NotImplementedError("Метод create_notification должен быть реализован в дочернем классе.")


@extend_schema(summary="Жалобы на транспорт", description="CRUD для жалоб на транспорт")
class ComplaintViewSet(BaseComplaintViewSet):
    queryset = Complaint.objects.all()
    serializer_class = ComplaintSerializer
    filterset_fields = ['vehicle']
    permission_classes = [IsAuthenticated, PermissionVehicle]

    def create_notification(self, complaint):
        user = complaint.vehicle.owner
        content = f'Поступила жалоба на транспорт "{complaint.vehicle}"'
        url = f'{settings.HOST_URL}/complaint/vehicle/{complaint.id}'
        Notification.objects.create(user=user, content=content, url=url)


@extend_schema(summary="Жалобы на отзывы арендодателей", description="CRUD для жалоб на отзывы")
class ComplaintFeedbackViewSet(BaseComplaintViewSet):
    queryset = ComplaintForFeedback.objects.all()
    serializer_class = ComplaintFeedbackSerializer
    filterset_fields = ['feedback']

    def create_notification(self, complaint):
        user = complaint.feedback.user
        content = f'Поступила жалоба на отзыв "{complaint.feedback}"'
        url = f'{settings.HOST_URL}/complaint/feedback_lessor/{complaint.id}'
        Notification.objects.create(user=user, content=content, url=url)


@extend_schema(summary="Жалобы на отзывы арендаторов", description="CRUD для жалоб на отзывы арендаторов")
class ComplaintFeedbackRenterViewSet(BaseComplaintViewSet):
    queryset = ComplaintForFeedbackRenter.objects.all()
    serializer_class = ComplaintFeedbackRenterSerializer
    filterset_fields = ['feedback']

    def create_notification(self, complaint):
        user = complaint.feedback.user
        content = f'Поступила жалоба на отзыв "{complaint.feedback}"'
        url = f'{settings.HOST_URL}/complaint/feedback_renter/{complaint.id}'
        Notification.objects.create(user=user, content=content, url=url)
