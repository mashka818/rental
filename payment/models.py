from django.db import models
from chat.models import RequestRent
from influencer.models import PromoCode, Influencer


class Payment(models.Model):
    """Модель платежей"""
    STATUS_CHOICES = (
        ('pending', 'В ожидании'),
        ('success', 'Оплачен'),
        ('failed', 'Ошибка'),
        ('canceled', 'Отменен')
    )
    request_rent = models.ForeignKey(RequestRent, on_delete=models.CASCADE, related_name='payments', verbose_name='Заявка на аренду')
    payment_id = models.CharField(max_length=255, verbose_name='ID платежа в системе Тиньков')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Сумма платежа')
    deposite = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name='Депозит')
    delivery = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name='Стоимость доставки')
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default='pending', verbose_name='Статус платежа')
    promo_code = models.ForeignKey(PromoCode, null=True, blank=True, on_delete=models.SET_NULL, verbose_name='Примененный промокод')
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name='Сумма скидки')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')
    influencer = models.ForeignKey(Influencer, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Партнер')
    url = models.CharField(null=True, blank=True, max_length=255, verbose_name='Ссылка')

    class Meta:
        verbose_name = 'Платеж'
        verbose_name_plural = 'Платежи'

    def __str__(self):
        return f'Платеж {self.payment_id} для заявки на аренду №{self.request_rent.id}'
