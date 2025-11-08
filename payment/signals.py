from django.db.models.signals import post_save
from django.dispatch import receiver
from payment.models import Payment
from chat.models import Trip


@receiver(post_save, sender=Payment)
def update_trip_status_on_payment_success(sender, instance, created, **kwargs):
    """
    При успешной оплате меняем статус Trip с 'started' на 'current'
    НЕ меняем статус, если поездка уже отменена или завершена
    """
    if instance.status == 'success':
        # Найти Trip для этой заявки
        trip = Trip.objects.filter(
            chat__request_rent=instance.request_rent,
            status='started'
        ).first()
        
        # Проверяем, что поездка найдена и она не отменена/завершена
        if trip and trip.status not in ['canceled', 'finished']:
            trip.status = 'current'
            trip.save()

