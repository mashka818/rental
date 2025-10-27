from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class VehicleConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'vehicle'
    verbose_name = _("Транспорт")

    def ready(self):
        import vehicle.signals
