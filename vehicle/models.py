import uuid
from decimal import Decimal

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from polymorphic.models import PolymorphicModel
from django.contrib.contenttypes.fields import GenericRelation, GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from RentalGuru import settings
from chat.models import RequestRent, Trip
from franchise.models import VehiclePark, City
from notification.models import Notification
from vehicle.manager import RentPriceManager
from vehicle.utils import merge_periods


class VehicleBrand(models.Model):
    TRANSPORT_CATEGORIES = [
        ('auto', 'Автомобили'),
        ('bike', 'Мотоциклы'),
        ('helicopter', 'Вертолёты'),
        ('ship', 'Судна'),
        ('special_technic', 'Спецтехника'),
    ]

    name = models.CharField(max_length=50, unique=True)
    logo = models.ImageField(upload_to='media/images/vehicle/brand_logo')
    search_vector = SearchVectorField(null=True, blank=True)

    transport_categories = models.ManyToManyField(
        'VehicleCategory',
        related_name='brands',
        verbose_name='Категории транспорта'
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Марка'
        verbose_name_plural = 'Марки'
        indexes = [
            GinIndex(fields=['name'], name='vehicle_brand_name_trgm', opclasses=['gin_trgm_ops']),
            GinIndex(fields=['search_vector'])
        ]


class VehicleCategory(models.Model):
    CATEGORY_CHOICES = [
        ('auto', 'Автомобили'),
        ('bike', 'Мотоциклы'),
        ('helicopter', 'Вертолёты'),
        ('ship', 'Судна'),
        ('special_technic', 'Спецтехника'),
    ]

    name = models.CharField(max_length=20, choices=CATEGORY_CHOICES, unique=True, verbose_name="Тип транспорта")

    def __str__(self):
        return self.get_name_display()

    class Meta:
        verbose_name = "Категория транспорта"
        verbose_name_plural = "Категории транспорта"


class VehicleModel(models.Model):
    VEHICLE_TYPES = (
        ('auto', 'Автомобиль'),
        ('bike', 'Мотоцикл'),
        ('ship', 'Судно'),
        ('helicopter', 'Вертолет'),
        ('special_technic', 'Спецтехника'),
    )
    name = models.CharField(max_length=50, unique=True, verbose_name='Название')
    brand = models.ForeignKey(VehicleBrand, on_delete=models.CASCADE, verbose_name='Марка')
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPES, null=True, blank=True, verbose_name='Тип транспорта')
    search_vector = SearchVectorField(null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Модель'
        verbose_name_plural = 'Модели'
        indexes = [
            GinIndex(fields=['name'], name='vehicle_model_name_trgm', opclasses=['gin_trgm_ops']),
            GinIndex(fields=['search_vector'])
        ]


class AutoFeaturesFunctions(models.Model):
    name = models.CharField(max_length=200, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Автомобиль, функция'
        verbose_name_plural = 'Автомобиль, функции'


class BikeFeaturesFunctions(models.Model):
    name = models.CharField(max_length=200, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Мотоцикл, функция'
        verbose_name_plural = 'Мотоцикл, функции'


class ShipFeaturesFunctions(models.Model):
    name = models.CharField(max_length=200, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Судно, функция'
        verbose_name_plural = 'Судно, функции'


class AutoFeaturesAdditionally(models.Model):
    name = models.CharField(max_length=200, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Автомобиль, дополнительная особенность'
        verbose_name_plural = 'Автомобиль, дополнительные особенности'


class BikeFeaturesAdditionally(models.Model):
    name = models.CharField(max_length=200, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Мотоцикл, Дополнительная особенность'
        verbose_name_plural = 'Мотоцикл, Дополнительные особенности'


class ShipFeaturesAdditionally(models.Model):
    name = models.CharField(max_length=200, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Судно, дополнительная особенность'
        verbose_name_plural = 'Судно, дополнительные особенности'


class FeaturesForChildren(models.Model):
    name = models.CharField(max_length=200, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Автомобиль, для детей'
        verbose_name_plural = 'Автомобиль, для детей'


class FeaturesEquipment(models.Model):
    name = models.CharField(max_length=200, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Судно, оборудование'
        verbose_name_plural = 'Судно, оборудование'


class PaymentMethod(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Способ платежа'
        verbose_name_plural = 'Способы платежей'


def year_validate(value):
    if value < 1900 or value > timezone.now().year:
        raise ValidationError(f'Год выпуска должен быть в пределах 1900 и {timezone.now().year} года.')


def default_rating():
    rating = {
        "Cleanliness": {"5_stars": 0, "4_stars": 0, "3_stars": 0, "2_stars": 0, "1_stars": 0},
        "Maintenance": {"5_stars": 0, "4_stars": 0, "3_stars": 0, "2_stars": 0, "1_stars": 0},
        "Communication": {"5_stars": 0, "4_stars": 0, "3_stars": 0, "2_stars": 0, "1_stars": 0},
        "Convenience": {"5_stars": 0, "4_stars": 0, "3_stars": 0, "2_stars": 0, "1_stars": 0},
        "Accuracy": {"5_stars": 0, "4_stars": 0, "3_stars": 0, "2_stars": 0, "1_stars": 0},
    }
    return rating


class Vehicle(PolymorphicModel):
    request_rents = GenericRelation(RequestRent, related_query_name='request_rent')
    trips = GenericRelation(Trip, related_query_name='trips')

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='vehicle', verbose_name='Владелец')
    brand = models.ForeignKey(VehicleBrand, on_delete=models.CASCADE, related_name='vehicle', verbose_name='Марка')
    model = models.ForeignKey(VehicleModel, on_delete=models.CASCADE, related_name='vehicle', verbose_name='Модель')
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, related_name='vehicle', verbose_name='Город')
    vehicle_park = models.ForeignKey(VehiclePark, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='vehicles', verbose_name='Автопарк')

    year = models.IntegerField(null=True, blank=True, validators=[year_validate], verbose_name='Год выпуска')
    description = models.TextField(null=True, blank=True, verbose_name='Описание')
    long_distance = models.BooleanField(default=False, verbose_name='Междугородние поездки')
    delivery = models.BooleanField(default=False, verbose_name='Доставка')
    ensurance = models.CharField(max_length=255, verbose_name='Страховка')
    drivers_rating = models.DecimalField(null=True, blank=True, decimal_places=1, max_digits=2, verbose_name='Рейтинг арендатора')
    drivers_only_verified = models.BooleanField(default=True, verbose_name='Сдавать только верифицированным пользователям')
    price_delivery = models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Стоимость доставки транспорта')
    price_deposit = models.DecimalField(decimal_places=2, max_digits=10, verbose_name='депозит')
    min_rent_day = models.PositiveIntegerField(default=1, verbose_name='Минимальный срок аренды')
    max_rent_day = models.PositiveIntegerField(default=365, verbose_name='Максимальный срок аренды')

    location = models.CharField(max_length=255, verbose_name='Местоположение')
    latitude = models.FloatField(null=True, blank=True, verbose_name='Широта')
    longitude = models.FloatField(null=True, blank=True, verbose_name='Долгота')
    ratings = models.JSONField(default=default_rating, verbose_name='Рейтинг транспорта')
    average_rating = models.FloatField(default=0, verbose_name='Средний рейтинг')
    verified = models.BooleanField(default=False, verbose_name='Верифицирован')
    last_update = models.DateTimeField(auto_now=True, verbose_name='Последнее обновление')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    payment_method = models.ManyToManyField(PaymentMethod, related_name='vehicles', verbose_name='Способ оплаты')
    count_trip = models.IntegerField(default=0, verbose_name='Количество поездок')

    def get_average_rating(self):
        average_ratings = {}
        overall_total_stars = 0
        overall_total_ratings = 0

        for category, ratings in self.ratings.items():
            total_stars = sum(int(stars.split('_')[0]) * count for stars, count in ratings.items())
            total_ratings = sum(ratings.values())
            average_rating = total_stars / total_ratings if total_ratings > 0 else 0
            average_ratings[category] = average_rating
            overall_total_stars += total_stars
            overall_total_ratings += total_ratings

        overall_average = overall_total_stars / overall_total_ratings if overall_total_ratings > 0 else 0
        average_ratings['rating'] = overall_average

        return average_ratings

    def save(self, *args, **kwargs):
        previous_instance = Vehicle.objects.filter(pk=self.pk).first()
        # Обновление рейтинга
        avg = self.get_average_rating().get('rating', 0) or 0
        self.average_rating = avg
        # Комиссия на доставку
        if self.price_delivery > 0:
            if previous_instance:
                if self.price_delivery != previous_instance.price_delivery:
                    commission = self.owner.lessor.commission
                    self.price_delivery *= Decimal(1) + Decimal(commission) / Decimal(100)
            else:
                commission = self.owner.lessor.commission
                self.price_delivery *= Decimal(1) + Decimal(commission) / Decimal(100)

        super().save(*args, **kwargs)
        # Отправка уведомления на регистрацию
        if previous_instance and not previous_instance.verified and self.verified:
            real_instance_class = self.get_real_instance_class()
            model_name = real_instance_class.__name__.lower()
            vehicle_url = f'{settings.HOST_URL}/vehicles/{model_name}/{self.pk}/'

            Notification.objects.create(
                user=self.owner,
                content=f'Ваше транспортное средство {self} было верифицировано!',
                url=vehicle_url
            )

        # Логика обработки периодов доступности
        on_request_availability = self.availabilities.filter(on_request=True).first()

        availabilities = list(self.availabilities.values('start_date', 'end_date'))
        if availabilities:
            merged_availabilities = merge_periods(availabilities)
            self.availabilities.all().delete()

            if on_request_availability:
                on_request_availability.pk = None
                on_request_availability.save()

            for availability in merged_availabilities:
                Availability.objects.create(vehicle=self, **availability)

    def __str__(self):
        return f'Vehicle id-{self.pk}'

    class Meta:
        verbose_name = 'Транспорт'
        verbose_name_plural = 'Транспорт'


class RentPrice(models.Model):
    RENT_PERIOD = (
        ('hour', 'Час'),
        ('day', 'День'),
        ('week', 'Неделя'),
        ('month', 'Месяц'),
        ('year', 'Год'),
    )
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='rent_prices')
    name = models.CharField(choices=RENT_PERIOD, max_length=5, verbose_name='Период')
    price = models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Стоимость')
    discount = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(90)], verbose_name='Скидка')
    total = models.DecimalField(decimal_places=2, max_digits=10, verbose_name='ИТОГО', editable=False)

    objects = RentPriceManager()

    def save(self, *args, **kwargs):
        commission = 20.0
        if self.vehicle.owner and hasattr(self.vehicle.owner, 'lessor'):
            commission = float(self.vehicle.owner.lessor.commission)

        self.total = float(self.price)/(100 - commission) * commission + float(self.price)
        # self.total = (float(self.price) + (float(self.price) * commission / 100)) * (100 - float(self.discount)) / 100
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Стоимость аренды на {self.name} - {self.total}'

    class Meta:
        verbose_name = 'Период'
        verbose_name_plural = 'Стоимость аренды'
        unique_together = ('vehicle', 'name')


class Availability(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='availabilities')
    start_date = models.DateField(verbose_name='Начало', null=True, blank=True)
    end_date = models.DateField(verbose_name='Конец', null=True, blank=True)
    on_request = models.BooleanField(default=False, verbose_name='По запросу')

    def __str__(self):
        if self.on_request:
            return f'Availability Request for {self.vehicle}'
        return f'Availability {self.start_date} to {self.end_date} for {self.vehicle}'

    def clean(self):
        if not self.on_request:
            if not self.start_date or not self.end_date:
                raise ValidationError('Поля start_date и end_date обязательны, если on_request=False.')
            if self.start_date > self.end_date:
                raise ValidationError('Дата начала не может быть позже даты окончания.')
        else:
            if self.start_date or self.end_date:
                raise ValidationError('Поля start_date и end_date не должны быть заполнены, если on_request=True.')

    def save(self, *args, **kwargs):
        if self.on_request:
            self.start_date = None
            self.end_date = None

        super().save(*args, **kwargs)

        if self.on_request:
            Availability.objects.filter(vehicle=self.vehicle).exclude(id=self.pk).delete()
        else:
            Availability.objects.filter(vehicle=self.vehicle, on_request=True).exclude(id=self.pk).delete()

    class Meta:
        verbose_name = 'Дата аренды'
        verbose_name_plural = 'Даты аренды'


def vehicle_documents_upload_to(instance, filename):
    vehicle_type = instance.vehicle._meta.model_name
    return f'media/images/vehicles/{vehicle_type}/{instance.vehicle.id}/documents/{filename}'


class VehicleDocument(models.Model):
    name = models.CharField(max_length=50, verbose_name='Вид документа')
    image = models.ImageField(upload_to=vehicle_documents_upload_to, verbose_name='Фото документа')
    number = models.IntegerField(verbose_name='Номер')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='documents')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Документ'
        verbose_name_plural = 'Документы'


def vehicle_photo_upload_to(instance, filename):
    vehicle_type = instance.vehicle._meta.model_name
    ext = filename.split('.')[-1]
    random_name = uuid.uuid4().hex[:10]
    return f'media/images/vehicles/{vehicle_type}/{instance.vehicle.id}/{random_name}.{ext}'


class VehiclePhoto(models.Model):
    vehicle = models.ForeignKey('Vehicle', related_name='photos', on_delete=models.CASCADE)
    photo = models.ImageField(upload_to=vehicle_photo_upload_to, verbose_name='Фото', max_length=255)
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок')

    class Meta:
        ordering = ['order']
        verbose_name = 'Фото'
        verbose_name_plural = 'Фото'

    def save(self, *args, **kwargs):
        if self._state.adding and self.order == 0:
            max_order = VehiclePhoto.objects.filter(vehicle=self.vehicle).aggregate(models.Max('order'))['order__max']
            self.order = (max_order or 0) + 1

        super().save(*args, **kwargs)

    def __str__(self):
        return f'Photo for vehicle id-{self.vehicle.pk}'


class AutoFuelType(models.Model):
    title = models.CharField(max_length=50, null=False, verbose_name='Вид топлива')
    slug = models.SlugField(max_length=50, unique=True, blank=True, verbose_name='Слаг')

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Автомобиль, вид топлива'
        verbose_name_plural = 'Автомобиль, виды топлива'


class AutoTransmission(models.Model):
    title = models.CharField(max_length=50, null=False, verbose_name='Коробка передач')
    slug = models.SlugField(max_length=50, unique=True, blank=True, verbose_name='Слаг')

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Автомобиль, коробка передач'
        verbose_name_plural = 'Автомобиль, коробки передач'


class AutoBodyType(models.Model):
    title = models.CharField(max_length=50, null=False, verbose_name='Тип кузова')
    slug = models.SlugField(max_length=50, unique=True, blank=True, verbose_name='Слаг')

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Автомобиль, тип кузова'
        verbose_name_plural = 'Автомобиль, типы кузова'


class VehicleClass(models.Model):
    title = models.CharField(max_length=50, null=False, verbose_name='Класс')
    slug = models.SlugField(max_length=50, unique=True, blank=True, verbose_name='Слаг')

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Класс'
        verbose_name_plural = 'Классы'


class Auto(Vehicle):

    transmission = models.ForeignKey(AutoTransmission, null=False, on_delete=models.PROTECT, verbose_name='Коробка передач')
    fuel_type = models.ForeignKey(AutoFuelType, null=False, on_delete=models.PROTECT,  verbose_name='Вид топлива')
    body_type = models.ForeignKey(AutoBodyType, null=False, on_delete=models.PROTECT, verbose_name='Тип кузова')
    vehicle_class = models.ForeignKey(VehicleClass, null=False, on_delete=models.PROTECT,  verbose_name='Класс')

    acceptable_mileage = models.IntegerField(verbose_name='Допустимый пробег, день')
    seats = models.PositiveIntegerField(default=4, verbose_name='Количество мест')
    drivers_age = models.PositiveIntegerField(null=True, blank=True, verbose_name='Возраст водителя')
    drivers_experience = models.PositiveIntegerField(null=True, blank=True, verbose_name='Стаж водителя')

    features_for_children = models.ManyToManyField(FeaturesForChildren, related_name='auto', blank=True, verbose_name='Для детей')
    features_functions = models.ManyToManyField(AutoFeaturesFunctions, related_name='auto', blank=True, verbose_name='Функции')
    features_additionally = models.ManyToManyField(AutoFeaturesAdditionally, related_name='auto', blank=True, verbose_name='Дополнительно')

    def __str__(self):
        return f'Автомобиль {self.brand.name} {self.model.name}'

    def clean(self):
        if self.seats and (self.seats < 1 or int(self.seats) > 50):
            raise ValidationError({'seats': 'Seats must be between 1 and 50.'})

    class Meta:
        verbose_name = 'Автомобиль'
        verbose_name_plural = 'Автомобили'


class BikeTransmission(models.Model):
    title = models.CharField(max_length=12, null=False, verbose_name='Коробка передач')
    slug = models.SlugField(max_length=50, unique=True, blank=True, verbose_name='Слаг')

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Мотоцикл, коробка передач'
        verbose_name_plural = 'Мотоцикл, коробки передач'


class BikeBodyType(models.Model):
    title = models.CharField(max_length=50, null=False, verbose_name='Тип мотоцикла')
    slug = models.SlugField(max_length=50, unique=True, blank=True, verbose_name='Слаг')

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Мотоцикл, тип'
        verbose_name_plural = 'Мотоцикл, типы'


class Bike(Vehicle):

    transmission = models.ForeignKey(BikeTransmission, null=False, on_delete=models.PROTECT, verbose_name='Коробка передач')
    vehicle_class = models.ForeignKey(VehicleClass, null=False, on_delete=models.PROTECT, verbose_name='Класс')
    body_type = models.ForeignKey(BikeBodyType, null=True, on_delete=models.PROTECT, verbose_name='Тип мотоцикла')

    engine_capacity = models.IntegerField(null=True, blank=True, verbose_name='Объем двигателя')
    seats = models.PositiveIntegerField(default=2, verbose_name='Количество мест')
    acceptable_mileage = models.IntegerField(verbose_name='Допустимый пробег, день')
    drivers_age = models.PositiveIntegerField(null=True, blank=True, verbose_name='Возраст водителя')
    drivers_experience = models.PositiveIntegerField(null=True, blank=True, verbose_name='Стаж водителя')

    features_functions = models.ManyToManyField(BikeFeaturesFunctions, related_name='bike', verbose_name='Функции')
    features_additionally = models.ManyToManyField(BikeFeaturesAdditionally, related_name='bike', verbose_name='Допольнительно')

    def __str__(self):
        return f'Мотоцикл {self.brand.name} {self.model.name}'

    def clean(self):
        if self.seats and (self.seats < 1 or int(self.seats) > 3):
            raise ValidationError({'seats': 'Seats must be between 1 and 3.'})

    class Meta:
        verbose_name = 'Мотоцикл'
        verbose_name_plural = 'Мотоциклы'


class ShipType(models.Model):
    title = models.CharField(max_length=50, null=False, verbose_name='Тип мотоцикла')
    slug = models.SlugField(max_length=50, unique=True, blank=True, verbose_name='Слаг')

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Судно, тип'
        verbose_name_plural = 'Судно, типы'


class Ship(Vehicle):

    vehicle_class = models.ForeignKey(VehicleClass, null=False, on_delete=models.PROTECT, verbose_name='Класс')

    type_ship = models.ForeignKey(ShipType, null=True, on_delete=models.PROTECT, verbose_name='Тип судна')
    grot = models.CharField(null=True, blank=True, verbose_name='Грот')
    length = models.FloatField(null=True, blank=True, verbose_name='Длина, м')
    width = models.FloatField(null=True, blank=True, verbose_name='Ширина, м')
    precipitation = models.FloatField(null=True, blank=True, verbose_name='Осадка, м')
    seats = models.PositiveIntegerField(default=2, verbose_name='Количество мест')
    sleeping_place = models.PositiveIntegerField(null=True, blank=True, verbose_name='Спальных мест')
    one_sleeping_place = models.PositiveIntegerField(null=True, blank=True, verbose_name='1-спальных кают')
    two_sleeping_place = models.PositiveIntegerField(null=True, blank=True, verbose_name='2-спальных кают')
    toilet = models.PositiveIntegerField(null=True, blank=True, verbose_name='Туалетов')
    engine_capacity = models.IntegerField(null=True, blank=True, verbose_name='Объем двигателя')
    water_tank = models.IntegerField(null=True, blank=True, verbose_name='Бак для воды, л')
    fuel_tank = models.IntegerField(null=True, blank=True, verbose_name='Топливный бак, л')
    acceptable_mileage = models.IntegerField(verbose_name='Допустимый пробег, день')

    features_functions = models.ManyToManyField(ShipFeaturesFunctions, related_name='ship', verbose_name='Функции')
    features_additionally = models.ManyToManyField(ShipFeaturesAdditionally, related_name='ship', verbose_name='Допольнительно')
    features_equipment = models.ManyToManyField(FeaturesEquipment, related_name='ship', verbose_name='Оборудование')

    def __str__(self):
        return f'Судно {self.brand.name} {self.model.name}'

    class Meta:
        verbose_name = 'Судно'
        verbose_name_plural = 'Судна'


class Helicopter(Vehicle):

    vehicle_class = models.ForeignKey(VehicleClass, null=False, on_delete=models.PROTECT, verbose_name='Класс')

    max_speed = models.IntegerField(null=True, blank=True, verbose_name='Максимальная скорость, км/ч')
    cruising_speed = models.IntegerField(null=True, blank=True, verbose_name='Крейсерская скорость, км/ч')
    flight_range = models.IntegerField(null=True, blank=True, verbose_name='Дальность полета,км')
    flight_duration = models.IntegerField(null=True, blank=True, verbose_name='Длительность полета, ч')
    power_cruising = models.IntegerField(null=True, blank=True, verbose_name='Мощность, крейсерская, л.с.')
    take_off_power = models.IntegerField(null=True, blank=True, verbose_name='Мощность взлетная, л.с.')
    full_take_weight = models.IntegerField(null=True, blank=True, verbose_name='Полный взлетный вес, кг')
    payload = models.IntegerField(verbose_name='Полезная нагрузка, кг')
    engine_capacity = models.IntegerField(null=True, blank=True, verbose_name='Объем двигателя')
    fuel_tank = models.IntegerField(null=True, blank=True, verbose_name='Объем топливного бака, л.')
    acceptable_mileage = models.IntegerField(verbose_name='Допустимый пробег, день')

    def __str__(self):
        return f'Вертолет {self.brand.name} {self.model.name}'

    class Meta:
        verbose_name = 'Вертолет'
        verbose_name_plural = 'Вертолеты'


class TechnicType(models.Model):
    title = models.CharField(max_length=50, null=False, verbose_name='Тип мотоцикла')
    slug = models.SlugField(max_length=50, unique=True, blank=True, verbose_name='Слаг')

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Спец техника, тип'
        verbose_name_plural = 'Спец техника, типы'


class SpecialTechnic(Vehicle):
    type_technic = models.ForeignKey(TechnicType, null=True, on_delete=models.PROTECT, verbose_name='Тип судна')
    engine_power = models.IntegerField(null=True, blank=True, verbose_name='Мощность двигателя, л.с.')
    length = models.FloatField(null=True, blank=True, verbose_name='Длина, м')
    width = models.FloatField(null=True, blank=True, verbose_name='Ширина, м')
    high = models.FloatField(null=True, blank=True, verbose_name='Высота, м')
    operating_weight = models.IntegerField(verbose_name='Эксплутационная масса, кг')

    def __str__(self):
        return f'Спец техника {self.brand.name} {self.model.name}'

    class Meta:
        verbose_name = 'Спец техника'
        verbose_name_plural = 'Спец техника'


class RatingUpdateLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    vehicle = GenericForeignKey('content_type', 'object_id')
    cleanliness = models.IntegerField(null=True, blank=True)
    maintenance = models.IntegerField(null=True, blank=True)
    communication = models.IntegerField(null=True, blank=True)
    convenience = models.IntegerField(null=True, blank=True)
    accuracy = models.IntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'content_type', 'object_id')
        verbose_name = 'Лог обновления рейтинга транспорта'
        verbose_name_plural = 'Логи обновления рейтингов транспорта'
