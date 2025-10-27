from django.core.exceptions import ValidationError
from django.db import models

from app.models import User
from feedback.models import Feedback, FeedbackRenter
from vehicle.models import Vehicle


class BaseComplaint(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='Пользователь')
    topic = models.CharField(max_length=300, null=True, blank=True, verbose_name='Причина жалобы')
    description = models.CharField(max_length=300, null=True, blank=True, verbose_name='Описание')

    def clean(self):
        if not self.topic and not self.description:
            raise ValidationError('Описание обязательно, если причина жалобы не указана.')

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        if self.topic:
            return str(self.topic)
        return f"{self.description[0:30]}..."

    class Meta:
        abstract = True


class Complaint(BaseComplaint):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, verbose_name='Транспорт')

    class Meta:
        unique_together = ('user', 'vehicle')
        verbose_name = 'Жалоба на транспорт'
        verbose_name_plural = 'Жалобы на транспорт'


class ComplaintForFeedback(BaseComplaint):
    feedback = models.ForeignKey(Feedback, on_delete=models.CASCADE, verbose_name='Транспорт')

    class Meta:
        unique_together = ('user', 'feedback')
        verbose_name = 'Жалоба на отзыв арендодателя'
        verbose_name_plural = 'Жалобы на отзывы арендодателей'


class ComplaintForFeedbackRenter(BaseComplaint):
    feedback = models.ForeignKey(FeedbackRenter, on_delete=models.CASCADE, verbose_name='Транспорт')

    class Meta:
        unique_together = ('user', 'feedback')
        verbose_name = 'Жалоба на отзыв арендатора'
        verbose_name_plural = 'Жалобы на отзывы арендаторов'
