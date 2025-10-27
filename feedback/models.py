from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from RentalGuru import settings
from app.models import Renter


class Feedback(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Пользователь')
    content = models.CharField(max_length=255, verbose_name='Отзыв', null=True, blank=True)
    answer = models.CharField(max_length=255, verbose_name='Ответ', null=True, blank=True)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, limit_choices_to={
        'model__in': ('auto', 'bike', 'ship', 'helicopter', 'specialtechnic')}, verbose_name='Тип транспорта')
    object_id = models.PositiveIntegerField(verbose_name='id транспорта')
    vehicle = GenericForeignKey('content_type', 'object_id')
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Время')

    def __str__(self):
        return f"Отзыв от {self.user} к {self.vehicle}"

    class Meta:
        verbose_name = 'Отзыв о транспорте'
        verbose_name_plural = 'Отзывы о отранспорте'


class FeedbackRenter(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='given_feedbacks', verbose_name='Арендодатель')
    renter = models.ForeignKey(Renter, on_delete=models.CASCADE, related_name='received_feedbacks', verbose_name='Арендатор')
    content = models.CharField(max_length=255, null=True, blank=True, verbose_name='Отзыв')
    answer = models.CharField(max_length=255, verbose_name='Ответ', null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Время')

    def __str__(self):
        return f"Отзыв от {self.user} к {self.renter}"

    class Meta:
        verbose_name = 'Отзыв о пользователе'
        verbose_name_plural = 'Отзывы о пользователях'
        unique_together = ('user', 'renter')
