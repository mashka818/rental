from django.db import migrations, models


def rename_unn_to_inn(apps, schema_editor):
    Franchise = apps.get_model('franchise', 'Franchise')
    for franchise in Franchise.objects.all():
        franchise.inn = franchise.unn
        franchise.save()


class Migration(migrations.Migration):

    dependencies = [
        ('franchise', '0008_alter_franchise_date_register'),
    ]

    operations = [
        migrations.AddField(
            model_name='franchise',
            name='inn',
            field=models.CharField(max_length=12, unique=True, verbose_name='ИНН', null=True),
        ),
        migrations.RunPython(rename_unn_to_inn),
        migrations.RemoveField(
            model_name='franchise',
            name='unn',
        ),
        migrations.AlterField(
            model_name='franchise',
            name='inn',
            field=models.CharField(max_length=12, unique=True, verbose_name='ИНН'),
        ),
    ]