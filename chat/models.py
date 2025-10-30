import json
from datetime import datetime, timedelta, time, date
from decimal import Decimal
import pytz
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction

from RentalGuru import settings
from influencer.models import PromoCode, UsedPromoCode


class RequestRent(models.Model):
    """ Заявки на аренду """
    STATUS_CHOICES = (
        ('accept', 'Принять'),
        ('denied', 'Отказать'),
        ('unknown', 'Не рассмотрено')
    )
    status = models.CharField(max_length=8, default='unknown', choices=STATUS_CHOICES, verbose_name='Статус')
    denied_reason = models.TextField(null=True, blank=True, verbose_name='Причина отказа', max_length=300)

    organizer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name='request_rent_organized_trips', verbose_name='Арендатор')

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, limit_choices_to={
        'model__in': ('auto', 'bike', 'ship', 'helicopter', 'specialtechnic')}, verbose_name='Тип транспорта')
    object_id = models.PositiveIntegerField(verbose_name='id транспорта')
    vehicle = GenericForeignKey('content_type', 'object_id')

    start_time = models.TimeField(null=True, blank=True, verbose_name='Время начала аренды')
    end_time = models.TimeField(null=True, blank=True, verbose_name='Время окончания аренды')
    start_date = models.DateField(verbose_name='Начало аренды', null=True, blank=True)
    end_date = models.DateField(verbose_name='Конец аренды', null=True, blank=True)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Итоговая стоимость', default=0.00)
    deposit_cost = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Депозит', default=0.00)
    delivery_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00,
                                        verbose_name='Стоимость доставки')
    delivery = models.BooleanField(default=False, verbose_name='Доставка')
    on_request = models.BooleanField(null=True, blank=True, verbose_name='Заявка по запросу')
    is_deleted = models.BooleanField(default=False, verbose_name='Удалена')
    promocode = models.ForeignKey(PromoCode, on_delete=models.SET_NULL, blank=True, null=True,
                                  verbose_name="Активный промокод", related_name='request_rents')
    bonus = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True,
                                verbose_name="Использованные бонусные рубли")

    @property
    def owner(self):
        return self.vehicle.owner

    @property
    def rental_days(self):
        """Подсчитывает количество дней аренды."""
        if self.start_date and self.end_date:
            # Считаем календарные дни: 23-24 число = 1 день, 23-25 = 2 дня
            calendar_days = (self.end_date - self.start_date).days
            
            # Для почасовой аренды (аренда меньше суток)
            if self.start_time and self.end_time and calendar_days == 0:
                # Аренда в пределах одного календарного дня
                from datetime import datetime
                start_datetime = datetime.combine(self.start_date, self.start_time)
                end_datetime = datetime.combine(self.end_date, self.end_time)
                delta = end_datetime - start_datetime
                total_hours = delta.total_seconds() / 3600
                # Возвращаем дробное количество часов для почасового тарифа
                return max(total_hours / 24, 0.01)  # Минимум 0.01 дня для корректных расчетов
            
            # Для обычной аренды: количество календарных дней
            # 29 окт → 30 окт = 1 день (независимо от времени)
            return max(1, calendar_days if calendar_days > 0 else 1)
        return 0

    def create_chat(self):
        """Создание чата при подаче заявки или подтверждении аренды."""
        if not Chat.objects.filter(request_rent=self).exists():
            chat = Chat.objects.create(request_rent=self)
            chat.participants.add(self.organizer, self.vehicle.owner)
            chat.save()
            amount = self.calculate_amount()

            message_content = json.dumps({
                "status": self.status,
                "organizer_id": self.organizer.id,
                "vehicle_id": self.object_id,
                "vehicle_type": str(self.content_type),
                "start_date": str(self.start_date),
                "end_date": str(self.end_date),
                "start_time": str(self.start_time),
                "end_time": str(self.end_time),
                "total_cost": float(self.total_cost),
                "deposit_cost": float(self.deposit_cost),
                "delivery_cost": float(self.delivery_cost),
                "delivery": self.delivery,
                "amount": round(float(amount), 2),
                "on_request": self.on_request
            }, ensure_ascii=False)

            Message.objects.create(
                chat=chat,
                sender=self.organizer,
                content=message_content
            )

    def calculate_rent_price(self):
        """Подсчитывает итоговую стоимость аренды с поддержкой почасовой оплаты."""
        from vehicle.models import RentPrice
        from datetime import datetime

        # Проверяем наличие почасового тарифа
        hourly_price = RentPrice.objects.filter(vehicle=self.vehicle, name='hour').first()

        # Если есть почасовой тариф и указано время, используем почасовую логику
        if hourly_price and self.start_time and self.end_time and self.start_date and self.end_date:
            start_datetime = datetime.combine(self.start_date, self.start_time)
            end_datetime = datetime.combine(self.end_date, self.end_time)

            if end_datetime <= start_datetime:
                raise ValueError("Время окончания должно быть больше времени начала.")

            total_duration = end_datetime - start_datetime
            total_hours = total_duration.total_seconds() / 3600

            # Если аренда >= 8 часов, проверяем наличие дневного тарифа
            if total_hours >= 8:
                daily_price = RentPrice.objects.filter(vehicle=self.vehicle, name='day').first()
                if daily_price:
                    # Есть дневной тариф - используем его вместо почасового
                    # Считаем как 1 день и переходим к обычной логике расчета
                    rental_days = 1
                    total_cost = float(daily_price.total)
                    
                    if self.delivery:
                        total_cost += float(self.vehicle.price_delivery)
                    
                    return total_cost
                else:
                    # Нет дневного тарифа - продолжаем считать по часам
                    total_cost = total_hours * float(hourly_price.total)
                    
                    if self.delivery and self.delivery_cost > 0:
                        total_cost += float(self.vehicle.price_delivery)
                    
                    return total_cost
            else:
                # Меньше 8 часов - всегда почасовой тариф
                total_cost = total_hours * float(hourly_price.total)

                # Добавление стоимости доставки
                if self.delivery and self.delivery_cost > 0:
                    total_cost += float(self.vehicle.price_delivery)

                return total_cost

        # Иначе используем оригинальную логику для дневных тарифов
        rental_days = self.rental_days
        if rental_days <= 0:
            raise ValueError("Количество дней аренды должно быть положительным.")

        period_priorities = [
            ('year', 365),
            ('month', 30),
            ('week', 7),
            ('day', 1),
        ]

        suitable_periods = [(period, days) for period, days in period_priorities if rental_days >= days]

        if not suitable_periods:
            raise ValueError("Не найден подходящий период аренды для текущего количества дней.")

        for period, period_days in suitable_periods:
            rent_price = RentPrice.objects.filter(vehicle=self.vehicle, name=period).first()
            if rent_price:
                break
        else:
            raise ValueError("Не найдена цена аренды для указанного транспортного средства.")

        total_cost = (rental_days / period_days) * float(rent_price.total)

        if self.delivery:
            total_cost += float(self.vehicle.price_delivery)

        return total_cost


    def clean(self):
        super().clean()

    def save(self, *args, **kwargs):
        if not self.pk:
            if self.vehicle and not self.deposit_cost:
                self.deposit_cost = self.vehicle.price_deposit
            self.delivery_cost = self.vehicle.price_delivery if self.delivery else 0.00
            # Рассчитываем итоговую стоимость при создании
            self.total_cost = self.calculate_rent_price()
            # Проверка является ли заявки по запросу
            from vehicle.models import Availability
            availabilities = Availability.objects.filter(vehicle=self.vehicle)
            for availability in availabilities:
                if availability.on_request:
                    self.on_request = True
                    break
                else:
                    self.on_request = False

        else:
            original = RequestRent.objects.get(pk=self.pk)
            if original.status != 'accept' and self.status == 'accept':
                # ИЗМЕНЕНИЕ: Сначала сохраняем, потом создаем платеж
                super(RequestRent, self).save(*args, **kwargs)
                with transaction.atomic():
                    self.create_payment()
                return  # Выходим, чтобы избежать двойного сохранения

        super(RequestRent, self).save(*args, **kwargs)

    def create_payment(self):
        """Создание платежа через Тиньков API"""
        from payment.models import Payment

        # Рассчитываем комиссию (сумму к оплате)
        commission_amount = self.calculate_amount()
        discount_amount = 0

        # Обработка промокода - скидка применяется к комиссии
        if self.promocode:
            discount_amount = commission_amount * Decimal(self.promocode.total) / Decimal(100)
            commission_amount -= discount_amount

            # Отмечаем промокод как использованный
            used_promo = UsedPromoCode.objects.filter(
                user=self.organizer,
                promo_code=self.promocode
            ).first()

            if used_promo:
                if used_promo.used:
                    # Промокод уже был использован - это не должно происходить
                    raise ValueError("Промокод уже был использован ранее")
                else:
                    # Отмечаем как использованный
                    used_promo.used = True
                    used_promo.save()
            else:
                # Если записи нет (что странно, но возможно), создаем новую
                UsedPromoCode.objects.create(
                    user=self.organizer,
                    promo_code=self.promocode,
                    used=True
                )

        # Обработка бонусов - вычитаются из итоговой суммы к оплате
        final_amount = commission_amount
        if self.bonus:
            renter = self.organizer.renter
            bonus_to_use = min(Decimal(self.bonus), final_amount)  # Не можем использовать больше, чем сумма к оплате

            if renter.bonus_account < bonus_to_use:
                raise ValueError("Недостаточно бонусов на счете")

            renter.bonus_account -= bonus_to_use
            final_amount -= bonus_to_use
            renter.save()

        influencer = getattr(self.organizer.renter, 'influencer', None)

        # Создание записи о платеже
        Payment.objects.create(
            request_rent=self,
            amount=final_amount,
            deposite=self.deposit_cost,
            delivery=self.delivery_cost,
            promo_code=self.promocode,
            discount_amount=discount_amount,
            influencer=influencer
        )

    def calculate_amount(self):
        """ Расчет стоимости суммы к оплате (комиссия от общей стоимости) """
        commission = self.vehicle.owner.lessor.commission
        return Decimal(self.total_cost) * commission / Decimal(100)

    def __str__(self):
        return f'Заявка на аренду №-{self.pk}'

    class Meta:
        verbose_name = 'Заявка на аренду'
        verbose_name_plural = 'Заявки на аренду'


class Chat(models.Model):
    request_rent = models.OneToOneField(RequestRent, null=True, on_delete=models.SET_NULL, verbose_name='Заявка на аренду', related_name='chat')
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, verbose_name='Участники')

    class Meta:
        verbose_name = 'Чат'
        verbose_name_plural = 'Чаты'

    def __str__(self):
        return f'chat_id_{self.pk}'


def file_chat_upload_to(instance, filename):
    return f'media/files/chat/{instance.chat}/{filename}'


class Trip(models.Model):
    """ Поездки """
    STATUS_CHOICES = (
        ('current', 'Текущая поездка'),
        ('started', 'В процессе'),
        ('finished', 'Завершить'),
        ('canceled', 'Отменить')
    )
    status = models.CharField(max_length=8, default='started', choices=STATUS_CHOICES, verbose_name='Статус')
    organizer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name='trip_organized_trips', verbose_name='Арендатор')

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, limit_choices_to={
        'model__in': ('auto', 'bike', 'ship', 'helicopter', 'specialtechnic')}, verbose_name='Тип транспорта')
    object_id = models.PositiveIntegerField(verbose_name='id транспорта')
    vehicle = GenericForeignKey('content_type', 'object_id')

    start_time = models.TimeField(null=True, blank=True, verbose_name='Время начала аренды')
    end_time = models.TimeField(null=True, blank=True, verbose_name='Время окончания аренды')

    chat = models.OneToOneField(Chat, on_delete=models.SET_NULL, null=True, blank=True)

    start_date = models.DateField(verbose_name='Начало поездки')
    end_date = models.DateField(verbose_name='Конец поездки')
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Стоимость аренды', default=0.00)

    @property
    def owner(self):
        return self.vehicle.owner

    def save(self, *args, **kwargs):
        if self.pk:
            previous_trip = Trip.objects.get(pk=self.pk)
        else:
            previous_trip = None

        super(Trip, self).save(*args, **kwargs)

        if previous_trip and previous_trip.status != 'finished' and self.status == 'finished':
            self.vehicle.count_trip += 1
            self.vehicle.save(update_fields=['count_trip'])
            self.owner.lessor.count_trip += 1
            self.owner.lessor.save(update_fields=['count_trip'])

    def get_time_until_start(self):
        """
        Вычисляет, сколько осталось времени до начала аренды.
        """
        if not isinstance(self.start_date, date):
            return None

        start_time = self.start_time if isinstance(self.start_time, time) else time(0, 0)
        start_datetime = datetime.combine(self.start_date, start_time)
        timezone = pytz.UTC
        start_datetime = timezone.localize(start_datetime)
        now = datetime.now(timezone)
        time_until = start_datetime - now
        return max(time_until, timedelta(0))

    def __str__(self):
        return f'Поездка id-{self.pk}'

    class Meta:
        verbose_name = 'Поездка'
        verbose_name_plural = 'Поездки'


class Message(models.Model):
    chat = models.ForeignKey(Chat, related_name='messages', on_delete=models.CASCADE, verbose_name='Чат')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Отправитель')
    content = models.TextField(verbose_name='Сообщение')
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Время')
    file = models.FileField(upload_to=file_chat_upload_to, blank=True, null=True, verbose_name='Файл')
    deleted = models.BooleanField(default=False, verbose_name='Удалено')
    is_read = models.BooleanField(default=False, verbose_name='Прочитано')
    language = models.CharField(max_length=10, default='ru')

    class Meta:
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'

    def __str__(self):
        return self.content


class TopicSupport(models.Model):
    name = models.CharField(null=False, verbose_name='Тема')
    count = models.IntegerField(default=0, verbose_name='Количество')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Тема чата с техподдержкой'
        verbose_name_plural = 'Темы чатов с техподдержкой'
        ordering = ['-count']


class ChatSupport(models.Model):
    creator = models.OneToOneField(settings.AUTH_USER_MODEL, related_name='created_chats', on_delete=models.CASCADE,
                                   verbose_name='Создатель')

    class Meta:
        verbose_name = 'Чат с техподдержкой'
        verbose_name_plural = 'Чаты с техподдержкой'

    def __str__(self):
        return f'support_chat_id_{self.pk}'


class IssueSupport(models.Model):
    chat = models.ForeignKey(ChatSupport, null=False, on_delete=models.CASCADE, related_name='issue_chat',
                             verbose_name='Чат техподдержки')
    topic = models.ForeignKey(TopicSupport, null=False, related_name='chat_support', on_delete=models.CASCADE,
                              verbose_name='Тема')
    description = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Время создания')

    class Meta:
        verbose_name = 'Обращение в техподдержку'
        verbose_name_plural = 'Обращения в техподдержку'

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new:
            from .tasks import send_issue_email
            send_issue_email.delay(self.id)


def file_support_chat_upload_to(instance, filename):
    return f'media/files/chat_support/{instance.chat}/{filename}'


class MessageSupport(models.Model):
    chat = models.ForeignKey(ChatSupport, related_name='message_support', on_delete=models.CASCADE, verbose_name='Чат')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Отправитель')
    content = models.TextField(verbose_name='Сообщение')
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Время')
    file = models.FileField(upload_to=file_support_chat_upload_to, blank=True, null=True, verbose_name='Файл')
    deleted = models.BooleanField(default=False, verbose_name='Удалено')
    is_read = models.BooleanField(default=False, verbose_name='Прочитано')
    language = models.CharField(max_length=10, default='ru')

    class Meta:
        verbose_name = 'Сообщение чата техподдержки'
        verbose_name_plural = 'Сообщения чата техподдержки'

    def __str__(self):
        return self.content