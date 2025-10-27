from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class InfluencerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'influencer'
    verbose_name = _("Партнерская программа")
