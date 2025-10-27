# Generated manually

from django.db import migrations


def create_access_types(apps, schema_editor):
    AccessType = apps.get_model('manager', 'AccessType')
    
    access_types = [
        ('lessors', 'Арендодатели'),
        ('departments', 'Подразделения'),
        ('partnership', 'Партнерская программа'),
        ('staff', 'Персонал'),
        ('rent_orders', 'Аренда и заказы'),
        ('rent_journal', 'Аренда журнал'),
        ('chats', 'Чаты'),
        ('reports', 'Отчеты')
    ]
    
    for name, verbose_name in access_types:
        AccessType.objects.get_or_create(name=name)


def reverse_create_access_types(apps, schema_editor):
    AccessType = apps.get_model('manager', 'AccessType')
    AccessType.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('manager', '0005_create_accesstype_model'),
    ]

    operations = [
        migrations.RunPython(create_access_types, reverse_create_access_types),
    ] 