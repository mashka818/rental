import hashlib
import logging
import time

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from RentalGuru import settings
from chat.models import Trip
from influencer.models import UsedPromoCode
from notification.models import Notification
from payment.TinkoffClient import TinkoffAPI
from payment.models import Payment
from payment.serializers import PaymentSerializer

logger = logging.getLogger('payment')


@extend_schema(summary="Платежи")
class PaymentViewSet(viewsets.ViewSet):
    """
    ViewSet для работы с платежами
    """
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """
        Получение списка всех платежей текущего пользователя
        """
        payments = Payment.objects.filter(request_rent__organizer=request.user)
        serializer = PaymentSerializer(payments, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        """
        Инициализация оплаты платежа через Тинькофф
        """
        try:
            payment = Payment.objects.get(pk=pk, request_rent__organizer=request.user)

            if payment.status in ['canceled', 'success']:
                return Response({'detail': 'Платеж уже обработан или отменен.'}, status=status.HTTP_400_BAD_REQUEST)

            if not payment.request_rent.vehicle:
                return Response({'detail': 'Транспорт не найден для данной заявки.'},
                                status=status.HTTP_400_BAD_REQUEST)

            if not payment.request_rent.id:
                return Response({'detail': 'Некорректная заявка на аренду.'}, status=status.HTTP_400_BAD_REQUEST)

            tinkoff = TinkoffAPI()
            if payment.payment_id:
                status_response = tinkoff.get_state(payment.payment_id)
                if status_response.get("Status") in ["NEW", "FORM_SHOWED", "AUTHORIZED"]:
                    return Response({
                        'detail': 'Платеж уже инициирован.',
                        'payment_url': payment.url
                    }, status=status.HTTP_200_OK)

                payment.payment_id = None
                payment.url = None
                payment.status = 'pending'

            receipt = {
                "Email": request.user.email,
                "Phone": request.user.telephone if hasattr(request.user, 'telephone') else None,
                "Taxation": "osn",
                "Items": [
                    {
                        "Name": f"Аренда транспорта {payment.request_rent.vehicle}",
                        "Price": int(payment.amount * 100),
                        "Quantity": 1,
                        "Amount": int(payment.amount * 100),
                        "Tax": "vat20"
                    }
                ]
            }
            order_id = f"{payment.id}_{int(time.time())}"

            response = tinkoff.create_payment(
                order_id=order_id,
                amount=int(payment.amount * 100),
                description=f'Аренда транспорта {payment.request_rent.vehicle} (заявка #{payment.request_rent.id})',
                receipt=receipt,
                lang=payment.request_rent.organizer.language.code
            )

            logger.info(f"Tinkoff API response: {response}")

            if not response.get('PaymentId') or not response.get('PaymentURL'):
                return Response({'detail': 'Ошибка инициализации платежа в Тинькофф.'},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            payment.payment_id = response['PaymentId']
            payment.url = response.get('PaymentURL')
            payment.save()

            return Response({'detail': 'Платеж успешно инициализирован.', 'payment_url': response['PaymentURL']})
        except Payment.DoesNotExist:
            return Response({'detail': 'Платеж не найден.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Payment error for payment_id={pk}: {str(e)}")
            logger.exception(e)
            return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
@extend_schema(summary="Коллбэк для Т", deprecated=True)
class TinkoffCallbackView(APIView):
    """
    Обрабатывает callback'и от Тинькофф.
    """

    def verify_signature(self, data):
        logger.debug(data)
        token = data.pop('Token')
        if not token:
            return False

        secret_key = settings.TINYPAY_PASSWORD

        for key, value in data.items():
            if isinstance(value, bool):
                data[key] = "true" if value else "false"
            else:
                data[key] = str(value)

        data["Password"] = secret_key
        sorted_params = ''.join(data[key] for key in sorted(data.keys()))

        calculated_token = hashlib.sha256(sorted_params.encode("utf-8")).hexdigest()
        return calculated_token == token

    def post(self, request, *args, **kwargs):
        data = request.data

        # Проверяем подпись
        if not self.verify_signature(data):
            return Response({"error": "Недействительная подпись"}, status=status.HTTP_403_FORBIDDEN)

        required_fields = {'PaymentId', 'Status', 'Amount'}
        missing_fields = required_fields - data.keys()
        if missing_fields:
            return Response(
                {"error": f"Отсутствуют обязательные поля: {', '.join(missing_fields)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        payment_id = data['PaymentId']
        status_from_tinkoff = data['Status']

        try:
            payment = get_object_or_404(Payment, payment_id=payment_id)
        except Http404:
            logger.error(f"Платеж с ID {payment_id} не найден.")
            raise

        if payment.status == 'success' and status_from_tinkoff == 'CONFIRMED':
            logger.info(f"Платеж {payment_id} уже обработан, повторное подтверждение игнорируется.")
            return Response({"message": "Платеж уже подтвержден"}, status=status.HTTP_200_OK)

        if status_from_tinkoff == 'CONFIRMED':
            payment.status = 'success'
            payment.paid_at = now()
            payment.save()

            if payment.promo_code:
                UsedPromoCode.objects.filter(user=payment.request_rent.organizer, promo_code=payment.promo_code).update(
                    used=True)

            trip = Trip.objects.filter(chat=payment.request_rent.chat).first()
            if trip:
                trip.status = 'started'  # TODO: Поменять статус
                trip.save()
                try:
                    content = f"Оплачена заявка на аренду {trip.vehicle}. Начало аренды: {trip.start_date}/{trip.start_time}"
                    Notification.objects.get_or_create(
                        user=trip.organizer,
                        content=content
                    )
                    Notification.objects.get_or_create(
                        user=trip.vehicle.owner,
                        content=content
                    )
                except Exception as e:
                    logger.error(f"Ошибка создания уведомления: {e}")
            else:
                logger.warning(f"Trip для чата {payment.request_rent.chat} не найден.")
            return Response({"message": "Платеж успешно подтвержден"}, status=status.HTTP_200_OK)

        elif status_from_tinkoff in ['CANCELLED', 'REJECTED']:
            payment.status = 'failed'
            payment.save()
            try:
                Notification.objects.get_or_create(
                    user=payment.request_rent.organizer,
                    content=f"Не удалось обработать платеж #{payment_id} по заявке #{payment.request_rent.id}"
                )
            except Exception as e:
                logger.error(f"Ошибка создания уведомления: {e}")
            return Response(
                {"message": f"Не удалось выполнить платеж со статусом {status_from_tinkoff}"},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )

        logger.warning(f"Необработанный статус платежа: {status_from_tinkoff}")
        return Response({"message": "Необработанный статус"}, status=status.HTTP_400_BAD_REQUEST)
