import json

from django.db.models.signals import post_save
from django.dispatch import receiver

from RentalGuru.settings import HOST_URL
from chat.models import RequestRent, Trip, Chat, Message
from notification.models import Notification


@receiver(post_save, sender=RequestRent)
def handle_request_rent_post_save(sender, instance, created, **kwargs):
    """Обработчик для создания чата и связанных записей поездок."""
    if created and instance.vehicle:
        if instance.vehicle.availabilities.filter(on_request=True).exists() and instance.status == 'unknown':
            instance.create_chat()

            chat = Chat.objects.get(request_rent=instance)

            Notification.objects.create(
                user=instance.vehicle.owner,
                content=f"Поступил запрос аренды на {instance.vehicle}",
                url=f"wss://{HOST_URL.split('//')[1]}/ws/chat/{chat.pk}/"
            )

    if instance.status == 'accept':
        instance.create_chat()

        chat = Chat.objects.get(request_rent=instance)

        # Проверяем, что есть успешный платеж перед созданием поездки
        from payment.models import Payment
        successful_payment = Payment.objects.filter(
            request_rent=instance, 
            status='success'
        ).exists()

        # Создаем Trip только если платеж успешно проведен
        if successful_payment and not Trip.objects.filter(
            object_id=instance.object_id,
            start_date=instance.start_date,
            end_date=instance.end_date,
            status__in=['current', 'started']
        ).exists():
            Trip.objects.create(
                organizer=instance.organizer,
                content_type=instance.content_type,
                object_id=instance.object_id,
                start_date=instance.start_date,
                end_date=instance.end_date,
                start_time=instance.start_time,
                end_time=instance.end_time,
                total_cost=instance.total_cost,
                chat=chat
            )
