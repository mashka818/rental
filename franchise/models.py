from datetime import timedelta
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q, Sum, F
from django.db.models.functions import Coalesce
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.forms import DecimalField
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from RentalGuru import settings
from chat.models import Trip


class City(models.Model):
    title = models.CharField(max_length=50, unique=True, verbose_name='Город')

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = 'Город'
        verbose_name_plural = 'Города'


class Category(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name='Категория')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'


class Franchise(models.Model):
    name = models.CharField(max_length=50, verbose_name='Имя компании')
    date_register = models.DateField(null=True, blank=True, verbose_name='Дата регистрации')
    country = models.CharField(max_length=50, verbose_name='Страна')
    city = models.ForeignKey(City, on_delete=models.PROTECT, null=True, verbose_name='Город')
    address = models.CharField(max_length=255, null=True, blank=True, verbose_name="Адрес")

    inn = models.CharField(max_length=12, unique=True, verbose_name='ИНН')
    ogrn = models.CharField(max_length=15, null=True, blank=True, verbose_name="ОГРН")
    account_number = models.CharField(max_length=20, null=True, blank=True, verbose_name="Расчетный счет")
    account_owner = models.CharField(max_length=255, null=True, blank=True, verbose_name="ФИО владельца счета")

    director = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Директор', related_name='franchise')
    commission = models.PositiveIntegerField(default=3, verbose_name='Комиссия')
    total_vehicles = models.PositiveIntegerField(default=0, verbose_name='Общее количество транспортных средств')
    categories = models.ManyToManyField(Category, related_name='franchises', verbose_name='Категории')

    email_1 = models.EmailField(max_length=50, null=True, blank=True, verbose_name='Почта №1')
    email_2 = models.EmailField(max_length=100, null=True, blank=True, verbose_name='Почта №2')
    telephone_1 = models.CharField(max_length=13, null=True, blank=True, verbose_name='Телефон №1')
    telephone_2 = models.CharField(max_length=20, null=True, blank=True, verbose_name='Телефон №2')

    def save_total_vehicles(self):
        self.total_vehicles = self.get_total_vehicles()
        super().save(update_fields=['total_vehicles'])

    def get_vehicles(self):
        from vehicle.models import Vehicle
        return Vehicle.objects.filter(
            Q(owner__lessor__franchise=self) | Q(owner=self.director)
        ).select_related('owner__lessor__franchise', 'owner__lessor')

    def get_total_vehicles(self):
        return self.get_vehicles().count()

    def get_date_range(self, period):
        today = timezone.now().date()
        end_date = today
        if period == 'day':
            start_date = today
        elif period == 'week':
            start_date = today - timedelta(days=7)
        elif period == 'month':
            start_date = today - timedelta(days=30)
        elif period == 'quarter':
            start_date = today - timedelta(days=90)
        elif period == 'year':
            start_date = today - timedelta(days=365)
        else:
            return None, None

        return start_date, end_date

    def get_previous_date_range(self, period):
        today = timezone.now().date()
        if period == 'day':
            end_date = today - timedelta(days=1)
            start_date = end_date
        elif period == 'week':
            end_date = today - timedelta(days=7)
            start_date = today - timedelta(days=14)
        elif period == 'month':
            end_date = today - timedelta(days=31)
            start_date = today - timedelta(days=62)
        elif period == 'year':
            end_date = today - timedelta(days=365)
            start_date = today - timedelta(days=730)
        else:
            return None, None
        return start_date, end_date

    def calculate_change_percentage(self, current_value, previous_value):
        if previous_value == 0:
            return 0 if current_value == 0 else 100
        return ((current_value - previous_value) / previous_value) * 100

    def _get_total_revenue_query(self):
        """Получает все завершенные поездки для транспорта франшизы"""
        return Trip.objects.filter(
            content_type__in=ContentType.objects.filter(
                model__in=['auto', 'bike', 'ship', 'helicopter', 'specialtechnic']),
            object_id__in=self.get_vehicles().values('id'),
            status='finished'
        )

    def get_total_revenue(self, period='all', is_previous=False):
        date_range = self.get_previous_date_range(period) if is_previous else self.get_date_range(period)

        query = self._get_total_revenue_query()

        if date_range != (None, None):
            start_date, end_date = date_range
            query = query.filter(end_date__gte=start_date, end_date__lte=end_date)

        trips = query.select_related('content_type').prefetch_related('vehicle__owner__lessor')

        total_revenue = Decimal('0.00')
        for trip in trips:
            owner = trip.vehicle.owner
            try:
                if hasattr(owner, 'lessor') and owner.lessor:
                    commission_percent = owner.lessor.commission
                    trip_revenue = trip.total_cost * (commission_percent / 100)
                    total_revenue += trip_revenue
            except Exception:
                continue

        return total_revenue

    def get_total_margin(self, period='all', is_previous=False):
        """
        Рассчитывает общую маржу франшизы за указанный период.
        Маржа = общая выручка - роялти
        """
        revenue = self.get_total_revenue(period, is_previous)
        return  revenue * (1 - Decimal(self.commission) / 100)

    def get_total_orders(self, period='all'):
        start_date, end_date = self.get_date_range(period)

        query = Trip.objects.filter(
            content_type__in=ContentType.objects.filter(
                model__in=['auto', 'bike', 'ship', 'helicopter', 'specialtechnic']),
            object_id__in=self.get_vehicles().values('id')
        )

        if start_date and end_date:
            query = query.filter(end_date__gte=start_date, end_date__lte=end_date)

        return query.count()

    def get_royalty(self, period='all', is_previous=False):
        """ 
        Роялти - процент от выручки, который платит франчайзи
        Формула: revenue * commission / 100
        """
        revenue = self.get_total_revenue(period, is_previous)
        return (revenue * Decimal(self.commission)) / Decimal(100)

    def get_total_completed_orders(self, period='all', is_previous=False):
        date_range = self.get_previous_date_range(period) if is_previous else self.get_date_range(period)
        if date_range == (None, None):
            return self._get_completed_orders_query().count()

        start_date, end_date = date_range
        query = self._get_completed_orders_query()
        query = query.filter(end_date__gte=start_date, end_date__lte=end_date)
        return query.count()

    def _get_completed_orders_query(self):
        return Trip.objects.filter(
            content_type__in=ContentType.objects.filter(
                model__in=['auto', 'bike', 'ship', 'helicopter', 'specialtechnic']),
            object_id__in=self.get_vehicles().values('id'),
            status='finished'
        )

    def get_total_cancelled_orders(self, period='all', is_previous=False):
        date_range = self.get_previous_date_range(period) if is_previous else self.get_date_range(period)
        if date_range == (None, None):
            return self._get_cancelled_orders_query().count()

        start_date, end_date = date_range
        query = self._get_cancelled_orders_query()
        query = query.filter(end_date__gte=start_date, end_date__lte=end_date)
        return query.count()

    def _get_cancelled_orders_query(self):
        return Trip.objects.filter(
            content_type__in=ContentType.objects.filter(
                model__in=['auto', 'bike', 'ship', 'helicopter', 'specialtechnic']),
            object_id__in=self.get_vehicles().values('id'),
            status='canceled'
        )

    def get_active_users_count(self):
        from app.models import User
        return User.objects.filter(
            lessor__franchise=self
        ).only('id').count()

    def get_statistics(self, period='all'):
        # Текущие значения
        current_revenue = self.get_total_revenue(period)
        current_margin = self.get_total_margin(period)
        current_royalty = self.get_royalty(period)
        current_completed = self.get_total_completed_orders(period)
        current_cancelled = self.get_total_cancelled_orders(period)

        # Значения за предыдущий период
        previous_revenue = self.get_total_revenue(period, True)
        previous_margin = self.get_total_margin(period, True)
        previous_royalty = self.get_royalty(period, True)
        previous_completed = self.get_total_completed_orders(period, True)
        previous_cancelled = self.get_total_cancelled_orders(period, True)

        # Расчет изменений в процентах
        revenue_change = self.calculate_change_percentage(current_revenue, previous_revenue)
        margin_change = self.calculate_change_percentage(current_margin, previous_margin)
        royalty_change = self.calculate_change_percentage(current_royalty, previous_royalty)
        completed_change = self.calculate_change_percentage(current_completed, previous_completed)
        cancelled_change = self.calculate_change_percentage(current_cancelled, previous_cancelled)

        return {
            'total_vehicles': self.get_total_vehicles(),
            'total_revenue': self.get_total_revenue(period),
            'total_margin': current_margin,
            'total_orders': self.get_total_orders(period),
            'total_completed_orders': current_completed,
            'total_cancelled_orders': current_cancelled,
            'royalty': self.get_royalty(period),
            'active_users_count': self.get_active_users_count(),
            'change_revenue': round(revenue_change, 1),
            'change_margin': round(margin_change, 1),
            'change_royalty': round(royalty_change, 1),
            'change_completed_orders': round(completed_change, 1),
            'change_cancelled_orders': round(cancelled_change, 1),
        }

    def __str__(self):
        return f"{self.name} ({self.country}, {self.city})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if not is_new and not kwargs.get('update_fields'):
            self.save_total_vehicles()

        super().save(*args, **kwargs)

        if is_new:
            self.save_total_vehicles()

    class Meta:
        verbose_name = 'Франшиза'
        verbose_name_plural = 'Франшизы'


def upload_franchise_document(instance, filename):
    return f'media/images/users/{instance.franchise.director.id}/documents/{filename}'


class FranchiseDocuments(models.Model):
    STATUS_CHOICES = (
        ('pending', 'На проверке'),
        ('approved', 'Подтверждено'),
        ('rejected', 'Отклонено'),
    )

    franchise = models.OneToOneField(Franchise, on_delete=models.CASCADE, verbose_name='Партнер', related_name='document')
    number = models.CharField(verbose_name='Серия и номер')
    photo = models.ImageField(upload_to=upload_franchise_document, verbose_name='Фото')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', verbose_name='Статус проверки')

    def __str__(self):
        return f'Паспорт: {self.number}'

    class Meta:
        verbose_name = 'Паспортные данные'
        verbose_name_plural = 'Паспортные данные'


class VehiclePark(models.Model):
    name = models.CharField(max_length=50, verbose_name='Название автопарка')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='vehicle_parks', verbose_name='Автопарк')
    franchise = models.ForeignKey(Franchise, on_delete=models.SET_NULL, null=True, blank=True, related_name='vehicle_parks', verbose_name='Франшиза')

    class Meta:
        verbose_name = 'Автопарк'
        verbose_name_plural = 'Автопарки'

    def __str__(self):
        return str(self.name)

    @receiver(post_delete, sender=Franchise)
    def delete_related_vehicles(sender, instance, **kwargs):
        VehiclePark.objects.filter(franchise=instance).delete()

    def get_vehicles(self):
        """Метод для получения всех транспортных средств, связанных с данным автопарком."""
        from vehicle.models import Vehicle
        return Vehicle.objects.filter(vehicle_park=self)

    def get_total_vehicles(self):
        return self.get_vehicles().count()

    def get_total_revenue(self):
        return Trip.objects.filter(
            content_type__in=ContentType.objects.filter(
                model__in=['auto', 'bike', 'ship', 'helicopter', 'specialtechnic']),
            object_id__in=self.get_vehicles().values('id'),
            status='finished'
        ).aggregate(total_revenue=Sum('total_cost'))['total_revenue'] or 0.00

    def get_total_orders(self):
        return Trip.objects.filter(
            content_type__in=ContentType.objects.filter(
                model__in=['auto', 'bike', 'ship', 'helicopter', 'specialtechnic']),
            object_id__in=self.get_vehicles().values('id')
        ).count()

    def get_total_completed_orders(self):
        return Trip.objects.filter(
            content_type__in=ContentType.objects.filter(
                model__in=['auto', 'bike', 'ship', 'helicopter', 'specialtechnic']),
            object_id__in=self.get_vehicles().values('id'),
            status='finished'
        ).count()

    def get_total_cancelled_orders(self):
        return Trip.objects.filter(
            content_type__in=ContentType.objects.filter(
                model__in=['auto', 'bike', 'ship', 'helicopter', 'specialtechnic']),
            object_id__in=self.get_vehicles().values('id'),
            status='canceled'
        ).count()

    def get_statistics(self):
        return {
            'total_vehicles': self.get_total_vehicles(),
            'total_revenue': self.get_total_revenue(),
            'total_orders': self.get_total_orders(),
            'total_completed_orders': self.get_total_completed_orders(),
            'total_cancelled_orders': self.get_total_cancelled_orders(),
        }


class RequestFranchise(models.Model):
    name = models.CharField(max_length=50, verbose_name='Имя компании')
    telephone = models.CharField(max_length=20, verbose_name='Телефон')
    email = models.EmailField(max_length=50, verbose_name='Эл. почта')
    city = models.CharField(max_length=50, verbose_name='Город')

    class Meta:
        verbose_name = 'Заявка на франшизу'
        verbose_name_plural = 'Заявки на франшизы'

    def __str__(self):
        return f'Имя: {self.name}, телефон: {self.telephone}'
