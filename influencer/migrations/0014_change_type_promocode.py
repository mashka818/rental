from django.db import migrations, models


def migrate_promo_type(apps, schema_editor):
    PromoCode = apps.get_model('influencer', 'PromoCode')
    for promo in PromoCode.objects.all():
        if promo.percent:
            promo.type = 'percent'
        elif promo.cash:
            promo.type = 'cash'
        promo.save()


class Migration(migrations.Migration):
    dependencies = [
        ('influencer', '0013_usedpromocode'),
    ]

    operations = [
        migrations.AddField(
            model_name='promocode',
            name='type',
            field=models.CharField(
                max_length=10,
                choices=[('percent', 'Процент'), ('cash', 'Бонусные рубли')],
                null=True,
                verbose_name='Тип промокода'
            ),
        ),
        migrations.RunPython(migrate_promo_type),
        migrations.RemoveField(model_name='promocode', name='percent'),
        migrations.RemoveField(model_name='promocode', name='cash'),
    ]
