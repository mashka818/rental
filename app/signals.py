from django.db.models.signals import pre_delete
from django.dispatch import receiver

from app.models import User


@receiver(pre_delete, sender=User)
def delete_user_vehicles(sender, instance, **kwargs):
    """
    Удаляет все транспортные средства пользователя ДО его удаления
    """
    if hasattr(instance, 'lessor'):
        from vehicle.models import Vehicle
        Vehicle.objects.filter(owner=instance).delete()