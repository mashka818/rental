# Generated manually to fix Thai Baht currency name

from django.db import migrations


def fix_thai_currency(apps, schema_editor):
    """
    Исправляет название тайской валюты с 'Батов' на 'Бат'
    """
    Currency = apps.get_model('app', 'Currency')
    
    # Исправляем тайский бат
    thb = Currency.objects.filter(code='THB').first()
    if thb:
        if thb.title and 'Батов' in thb.title:
            thb.title = thb.title.replace('Батов', 'Бат')
            thb.save()
            print(f"✓ Исправлено название валюты THB: {thb.title}")
        elif not thb.title:
            thb.title = 'Тайский Бат'
            thb.save()
            print(f"✓ Добавлено название для THB: {thb.title}")


def reverse_fix(apps, schema_editor):
    """Откат изменений"""
    pass  # Не откатываем, так как это исправление бага


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0025_alter_user_options'),  # Последняя миграция
    ]

    operations = [
        migrations.RunPython(fix_thai_currency, reverse_fix),
    ]

