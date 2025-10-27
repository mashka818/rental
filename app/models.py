from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver

from RentalGuru import settings
from app.manager import UserManager
from franchise.models import Franchise
from influencer.models import Influencer
from vehicle.models import Vehicle


def upload_avatar(instance, filename):
    return f'media/images/users/{instance.id}/avatar/{filename}'


class Currency(models.Model):
    code = models.CharField(max_length=3, unique=True, verbose_name="Код валюты")
    title = models.CharField(max_length=255, null=True, verbose_name='Название')

    def __str__(self):
        return self.code

    class Meta:
        verbose_name = "Валюта"
        verbose_name_plural = "Валюты"


class Language(models.Model):
    code = models.CharField(max_length=2, unique=True, verbose_name="Код языка")

    def __str__(self):
        return self.code

    class Meta:
        verbose_name = "Язык"
        verbose_name_plural = "Языки"


class User(AbstractUser):
    ROLES = (
        ('member', 'Пользователь'),
        ('manager', 'Менеджер'),
        ('admin', 'Администратор'),
    )
    PLATFORMS = (
        ('web', 'Веб'),
        ('android', 'Андроид'),
        ('ios', 'ios'),
        ('unknown', 'Неизвестно')
    )
    role = models.CharField(max_length=10, choices=ROLES, default='member', verbose_name='Роль')
    date_of_birth = models.DateField(null=True, blank=True, verbose_name='Дата рождения')
    telephone = models.CharField(max_length=15, null=True, blank=True, verbose_name='Телефон')
    telephone_verified = models.BooleanField(default=False, verbose_name='Телефон подтвержден')
    currency = models.ForeignKey(Currency, default=1, null=True, on_delete=models.SET_NULL, verbose_name='Валюта')
    language = models.ForeignKey(Language, default=1, null=True, on_delete=models.SET_NULL, verbose_name='Язык')
    avatar = models.ImageField(upload_to=upload_avatar, null=True, blank=True, verbose_name='Аватар')
    about = models.TextField(null=True, blank=True, verbose_name='О себе')
    email_notification = models.BooleanField(default=True, verbose_name='Email уведомления')
    push_notification = models.BooleanField(default=False, verbose_name='Push уведомления')
    telegram_id = models.CharField(max_length=100, unique=True, null=True, blank=True, verbose_name='Telegram ID')
    platform = models.CharField(choices=PLATFORMS, null=True, blank=True, verbose_name='Платформа')

    first_name = models.CharField(null=True, max_length=150, blank=True, verbose_name='Имя')
    last_name = models.CharField(null=True, max_length=150, blank=True, verbose_name='Фамилия')

    email = models.EmailField(unique=True, verbose_name='Email')
    email_verified = models.BooleanField(default=False)
    username = None
    objects = UserManager()
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'


class Lessor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='lessor')
    super_host = models.BooleanField(default=False, verbose_name='Суперхост')
    count_trip = models.PositiveIntegerField(default=0, verbose_name='Количество поездок')
    average_response_time = models.DurationField(null=True, blank=True, verbose_name='Среднее время ответа')
    commission = models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Комиссия', default=20.0)
    influencer = models.ForeignKey(Influencer, null=True, blank=True, on_delete=models.SET_NULL, related_name='lessors',
                                   verbose_name='Инфлюенсер')
    franchise = models.ForeignKey(Franchise, on_delete=models.SET_NULL, null=True, blank=True, related_name='lessors',
                                  verbose_name='Франшиза')

    def clean(self):
        if not (1 <= float(self.commission) <= 90):
            raise ValidationError('Комиссия должна быть в пределах от 1% до 90%.')

    @receiver(post_delete, sender=Franchise)
    def delete_related_vehicles(sender, instance, **kwargs):
        """
        Удаляет все транспортные средства пользователей, связанных с удаляемой франшизой через их записи Lessor
        """
        lessor_user_ids = Lessor.objects.filter(franchise=instance).values_list('user_id', flat=True)
        vehicles = Vehicle.objects.filter(owner_id__in=lessor_user_ids)
        vehicles_count = vehicles.count()
        vehicles.delete()

    def __str__(self):
        return str(self.user)

    class Meta:
        verbose_name = 'Арендодатель'
        verbose_name_plural = 'Арендодатели'


def default_rating():
    return {"5_stars": 0, "4_stars": 0, "3_stars": 0, "2_stars": 0, "1_stars": 0}


class Renter(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='renter')
    verification = models.BooleanField(default=False, verbose_name='Верифированный пользователь')
    rating = models.JSONField(default=default_rating, verbose_name='Рейтинг')
    influencer = models.ForeignKey(Influencer, null=True, blank=True, on_delete=models.SET_NULL, related_name='renters',
                                   verbose_name='Инфлюенсер')
    bonus_account = models.PositiveIntegerField(default=0, null=True, blank=True, verbose_name='Бонусный счет')

    def get_average_rating(self):
        total_ratings = sum(self.rating.values())
        if total_ratings == 0:
            return 0

        weighted_sum = (
            self.rating["5_stars"] * 5 +
            self.rating["4_stars"] * 4 +
            self.rating["3_stars"] * 3 +
            self.rating["2_stars"] * 2 +
            self.rating["1_stars"] * 1
        )
        return weighted_sum / total_ratings

    def __str__(self):
        return str(self.user)

    class Meta:
        verbose_name = 'Арендатор'
        verbose_name_plural = 'Арендаторы'


def upload_renter_document(instance, filename):
    return f'media/images/users/{instance.renter.user.id}/documents/{filename}'


class RenterDocuments(models.Model):
    STATUS_CHOICES = (
        ('pending', 'На проверке'),
        ('approved', 'Подтверждено'),
        ('rejected', 'Отклонено'),
    )

    DOCUMENT_TYPE_CHOICES = (
        ('passport', 'Паспорт'),
        ('license', 'Права'),
    )

    renter = models.ForeignKey(Renter, related_name='renter_documents', on_delete=models.CASCADE)
    title = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES, verbose_name='Вид документа')
    number = models.PositiveIntegerField(verbose_name='Номер')
    photo = models.ImageField(upload_to=upload_renter_document, verbose_name='Фото')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', verbose_name='Статус проверки')
    issue_date = models.DateField(null=True, blank=True, verbose_name='Дата выдачи')

    def clean(self):
        if self.title == 'license' and not self.issue_date:
            raise ValidationError({'issue_date': 'Дата выдачи обязательна для документов типа "права".'})

    def __str__(self):
        return f'{self.title}: {self.number}'

    class Meta:
        verbose_name = 'Документ'
        verbose_name_plural = 'Документы'


class Rating(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='given_ratings')
    renter = models.ForeignKey(Renter, on_delete=models.CASCADE, related_name='received_ratings')
    rating = models.PositiveSmallIntegerField(choices=[(1, '1 Star'), (2, '2 Stars'), (3, '3 Stars'), (4, '4 Stars'), (5, '5 Stars')])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'renter')
        verbose_name = 'Рейтинг'
        verbose_name_plural = 'Рейтинги'


class FavoriteList(models.Model):
    renter = models.ForeignKey(Renter, on_delete=models.CASCADE, related_name='favorite_lists')
    name = models.CharField(max_length=100, verbose_name='Название списка')
    vehicles = models.ManyToManyField(Vehicle, related_name='in_favorite_lists', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Список избранного'
        verbose_name_plural = 'Списки избранного'
        unique_together = ['renter', 'name']

    def __str__(self):
        return f"{self.name} - {self.renter}"
