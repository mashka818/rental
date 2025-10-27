from celery import shared_task
from django.core.mail import send_mail

from RentalGuru import settings


@shared_task
def withdraw_request(amount, influencer):
    send_mail(
        subject="Запрос на вывод средств",
        message=f'Поступил запрос на вывод средств от партнера {influencer} на сумму {amount}',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=['13can13@mail.ru'],
    )
