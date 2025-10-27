from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class FranchiseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'franchise'
    verbose_name = _("Франшиза")

    def ready(self):
        import franchise.signals
