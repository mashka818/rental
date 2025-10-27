# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('manager', '0004_manager_franchise'),
    ]

    operations = [
        migrations.CreateModel(
            name='AccessType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(choices=[('lessors', 'Арендодатели'), ('departments', 'Подразделения'), ('partnership', 'Партнерская программа'), ('staff', 'Персонал'), ('rent_orders', 'Аренда и заказы'), ('rent_journal', 'Аренда журнал'), ('chats', 'Чаты'), ('reports', 'Отчеты')], max_length=50, unique=True, verbose_name='Тип доступа')),
            ],
            options={
                'verbose_name': 'Тип доступа',
                'verbose_name_plural': 'Типы доступов',
            },
        ),
        migrations.AddField(
            model_name='manager',
            name='access_types',
            field=models.ManyToManyField(blank=True, related_name='managers', to='manager.accesstype', verbose_name='Типы доступа'),
        ),
    ]