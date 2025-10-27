from django.db import models

from app.models import Lessor
from franchise.models import Franchise


class RequestAddLessor(models.Model):
    STATUS_CHOICES = (
        ('on_consideration', 'На рассмотрении'),
        ('approved', 'Подтверждено'),
        ('rejected', 'Отклонено'),
    )
    franchise = models.ForeignKey(Franchise, on_delete=models.CASCADE, related_name='request_lessor', verbose_name='Франшиза')
    lessor = models.ForeignKey(Lessor, on_delete=models.CASCADE, related_name='request_lessor', verbose_name='Арендодатель')
    status = models.CharField(choices=STATUS_CHOICES, default='on_consideration', verbose_name='Статус')

    class Meta:
        unique_together = ('franchise', 'lessor')
