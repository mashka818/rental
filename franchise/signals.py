from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from vehicle.models import Vehicle


@receiver(post_save, sender=Vehicle)
@receiver(post_delete, sender=Vehicle)
def update_franchise_total_vehicles(sender, instance, **kwargs):
    if instance.owner:
        try:
            franchise = instance.owner.lessor.franchise
        except AttributeError:
            franchise = None

        if franchise:
            franchise.save_total_vehicles()
