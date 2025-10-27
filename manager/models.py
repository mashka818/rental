from datetime import timedelta
from django.db import models
from django.utils import timezone
from django.utils.timezone import now

from RentalGuru import settings
from franchise.models import City


"""
Нужно переписать сериализаторы и вью в соответствии с новой моделью доступов AccessType (старая модель доступов закоментированна).
Создавать и изменять права менеджеров может только пользователь user.role=='admin'
Нужно удалить старые пермишены для менеджеров, основанные на старой модели доступа, в файле permissions.py
Нужно перепроверить и исправить пермишены по всему проекту, в том числе и в вебсокетах в файле /chat/consumers.py
Нужно сделать новые пермишены для менеджеров в следующих вьюсетах и вью:
Арендодатели		https://rentalguru.ru/franchise/lessors
Подразделения		https://rentalguru.ru/franchise/franchise/
Партнерская программа	https://rentalguru.ru/influencer/influencers/, https://rentalguru.ru/influencer/influencer_requests/, https://rentalguru.ru/influencer/referral-links/, https://rentalguru.ru/influencer/request_withdraw/
Персонал		https://rentalguru.ru/manager/managers/
Аренда и заказы 	https://rentalguru.ru/journal/current/
Аренда журнал 		https://rentalguru.ru/journal/
Чаты			https://rentalguru.ru/chat/support_chats/
Отчеты			https://rentalguru.ru/report/franchise_report_v2/, https://rentalguru.ru/report/influencer_report/, https://rentalguru.ru/report/user-registration-report/
Если у менеджера в доступах указан соответствующий раздел, то разрешать доступ
Если для каких то вью нет инструкций по доступам для менеджеров, то предоставить доступ 
"""


class AccessType(models.Model):
    TYPE_CHOICES = (
        ('vehicles', 'Транспорт'),
        ('lessors', 'Арендодатели'),
        ('departments', 'Подразделения'),
        ('partnership', 'Партнерская программа'),
        ('staff', 'Персонал'),
        ('rent_orders', 'Аренда и заказы'),
        ('rent_journal', 'Аренда журнал'),
        ('chats', 'Чаты'),
        ('reports', 'Отчеты')
    )

    PERMISSION_CHOICES = (
        ('read', 'Чтение'),
        ('edit', 'Редактирование'),
        ('delete', 'Удаление')
    )

    name = models.CharField(max_length=50, choices=TYPE_CHOICES, verbose_name="Тип доступа")
    permission = models.CharField(max_length=10, default='read', choices=PERMISSION_CHOICES, verbose_name="Тип действия")

    class Meta:
        unique_together = ('name', 'permission')
        verbose_name = "Тип доступа"
        verbose_name_plural = "Типы доступов"

    def __str__(self):
        return f"{dict(self.TYPE_CHOICES).get(self.name, self.name)} — {dict(self.PERMISSION_CHOICES).get(self.permission, self.permission)}"


class Manager(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='manager')
    password_updated_at = models.DateTimeField(default=now, verbose_name="Дата изменения пароля")
    cities = models.ManyToManyField(City, blank=True, verbose_name='Города', related_name='managers')
    access_types = models.ManyToManyField(AccessType, blank=True, verbose_name='Типы доступа', related_name='managers')

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"

    def check_password_expiry(self):
        if not self.password_updated_at:
            return "Пароль никогда не обновлялся. Рекомендуем сменить пароль."
        if self.password_updated_at + timedelta(days=90) < timezone.now():
            return "Пароль устарел. Пожалуйста, обновите пароль."
        return None

    class Meta:
        verbose_name = 'Менеджер'
        verbose_name_plural = 'Менеджеры'


def upload_manager_document(instance, filename):
    return f'media/images/users/{instance.manager.user.id}/documents/{filename}'


class ManagerDocuments(models.Model):
    manager = models.OneToOneField(Manager, related_name='manager_document', on_delete=models.CASCADE, verbose_name='Менеджер')
    number = models.CharField(max_length=50, verbose_name='Серия и номер')
    photo = models.ImageField(upload_to=upload_manager_document, verbose_name='Фото')

    def __str__(self):
        return self.number

    class Meta:
        verbose_name = 'Паспортные данные'
        verbose_name_plural = 'Паспортные данные'
