# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('franchise', '0010_franchisedocuments'),  # Предполагается что в franchise есть модель City
        ('manager', '0006_populate_access_types'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='manager',
            name='franchise',
        ),
        migrations.AddField(
            model_name='manager',
            name='city',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='managers', to='franchise.city', verbose_name='Город'),
        ),
    ] 