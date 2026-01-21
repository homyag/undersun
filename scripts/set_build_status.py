import sys

from django.conf import settings
from django import setup

settings.configure(default_settings=None)
setup()

from apps.properties.models import Property

updated = Property.objects.update(build_status='under_construction')
print(f"Updated {updated} properties")
