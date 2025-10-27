import json
import os
from datetime import timedelta

import requests
from celery import shared_task
from django.apps import apps
from django.core.mail import send_mail
from django.utils import timezone
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from pyfcm import FCMNotification
from django.db import models

from RentalGuru import settings
from RentalGuru.settings import DEFAULT_FROM_EMAIL, AUTH_USER_MODEL, HOST_URL


class Notification(models.Model):
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Пользователь')
    content = models.CharField(max_length=255, verbose_name='Сообщение')
    read_it = models.BooleanField(default=False, verbose_name='Прочитано')
    url = models.URLField(max_length=1000, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')

    class Meta:
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'

    def get_absolute_url(self):
        return f'{HOST_URL}/notifications/{self.pk}'

    def send_notification(self):
        if self.user.email_notification:
            send_email_notification.delay(self.id)
        if self.user.push_notification:
            url = self.get_absolute_url()
            self.content = f'{self.content}\n{url}'
            send_web_push_notification.delay(self.user.id, self.content, self.url)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.send_notification()

    def __str__(self):
        return str(self.content)


class FCMToken(models.Model):
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Пользователь')
    token = models.CharField(max_length=255, unique=True, verbose_name='Токен')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлен')
    last_used_at = models.DateTimeField(auto_now=True, verbose_name='Последнее использование')

    class Meta:
        verbose_name = 'FCM токен'
        verbose_name_plural = 'FCM токены'

    def __str__(self):
        return str(self.token)


@shared_task
def send_email_notification(notification_id):
    notification = Notification.objects.select_related('user').get(id=notification_id)
    if notification.url:
        message = f'{notification.content}\n{notification.url}'
    else:
        message = f'{notification.content}'
    send_mail(
        subject='Rental-Guru',
        message=message,
        from_email=DEFAULT_FROM_EMAIL,
        recipient_list=[notification.user.email],
        fail_silently=False,
    )
    return "Email notifications sent"


@shared_task
def send_web_push_notification(user_id, notification_body, notification_url=None):
    User = apps.get_model(settings.AUTH_USER_MODEL)

    try:
        user = User.objects.prefetch_related('fcmtoken_set').get(id=user_id)
        tokens = list(user.fcmtoken_set.values_list('token', flat=True))
    except User.DoesNotExist:
        return f"User with id {user_id} not found"

    if not tokens:
        return "No FCM tokens for user"

    # Получаем access_token через сервисный аккаунт
    try:
        credentials = service_account.Credentials.from_service_account_file(
            os.getenv("SERVICE_ACCOUNT_FILE"),
            scopes=["https://www.googleapis.com/auth/firebase.messaging"],
        )
        credentials.refresh(Request())
        access_token = credentials.token
    except Exception as e:
        return f"Failed to get access token: {str(e)}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }

    project_id = os.getenv('PROJECT_ID', 'rental-guru-465d7')
    fcm_url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"

    successful_sends = 0
    failed_sends = 0

    for token in tokens:
        message = {
            "message": {
                "token": token,
                "notification": {
                    "title": "Rental-Guru",
                    "body": notification_body
                },
                "webpush": {
                    "headers": {
                        "Urgency": "high",
                        "TTL": "86400"  # 24 часа
                    },
                    "notification": {
                        "title": "Rental-Guru",
                        "body": notification_body,
                        "icon": "https://rentalguru.ru/static/firebase-logo.png",
                        "badge": "https://rentalguru.ru/static/firebase-logo.png",
                        "click_action": notification_url or "https://rentalguru.ru",
                        "requireInteraction": True,
                        "actions": [
                            {
                                "action": "open",
                                "title": "Открыть"
                            }
                        ]
                    },
                    "data": {
                        "url": notification_url or "https://rentalguru.ru"
                    }
                }
            }
        }

        try:
            response = requests.post(fcm_url, headers=headers, json=message, timeout=30)

            if response.status_code == 200:
                successful_sends += 1
            elif response.status_code == 404:
                # Токен не найден - удаляем его
                from notification.models import FCMToken
                FCMToken.objects.filter(token=token).delete()
                print(f"Deleted invalid token: {token[:20]}...")
            elif response.status_code == 400:
                response_data = response.json()
                error_code = response_data.get('error', {}).get('details', [{}])[0].get('errorCode', '')

                if error_code in ['UNREGISTERED', 'INVALID_ARGUMENT']:
                    # Токен недействителен - удаляем его
                    from notification.models import FCMToken
                    FCMToken.objects.filter(token=token).delete()
                    print(f"Deleted unregistered token: {token[:20]}...")
                else:
                    failed_sends += 1
                    print(f"Failed to send to token {token[:20]}...: {response.text}")
            else:
                failed_sends += 1
                print(f"Failed to send notification to {token[:20]}...: {response.status_code} {response.text}")

        except requests.exceptions.Timeout:
            failed_sends += 1
            print(f"Timeout sending to token {token[:20]}...")
        except requests.exceptions.RequestException as e:
            failed_sends += 1
            print(f"Request error sending to token {token[:20]}...: {str(e)}")
        except Exception as e:
            failed_sends += 1
            print(f"Unexpected error sending to token {token[:20]}...: {str(e)}")

    return f"Push notifications sent: {successful_sends} successful, {failed_sends} failed"


@shared_task
def remove_old_tokens():
    expiration_date = timezone.now() - timedelta(days=90)
    FCMToken.objects.filter(last_used_at__lt=expiration_date).delete()
