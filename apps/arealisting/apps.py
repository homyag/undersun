from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ArealistingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.arealisting'
    verbose_name = _('AREALISTING')
