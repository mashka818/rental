from decimal import Decimal

from django.db import models


class RentPriceManager(models.Manager):
    def bulk_create(self, objs, *args, **kwargs):
        for obj in objs:
            commission = (
                obj.vehicle.owner.lessor.commission
                if obj.vehicle.owner and hasattr(obj.vehicle.owner, 'lessor')
                else 20.0
            )
            obj.total = ((Decimal(obj.price) / (100 - commission) * commission + Decimal(obj.price))*
                        (100 - Decimal(obj.discount)) / 100
            )
        return super().bulk_create(objs, *args, **kwargs)
