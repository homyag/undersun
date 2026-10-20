"""Small, durable audit records for changes made through AREALISTING."""
import json

from django.core.serializers.json import DjangoJSONEncoder

from ..models import ArealistingPropertyChange


def record_property_change(*, property_id, project_id, kind, details, actor=None, sync_run=None):
    return ArealistingPropertyChange.objects.create(
        property_id=property_id,
        project_id=project_id,
        kind=kind,
        actor=actor,
        sync_run=sync_run,
        details=json.loads(json.dumps(details, cls=DjangoJSONEncoder)),
    )
