from django.db import migrations
from django.db.models import Q
from django.core.management.color import no_style


def ensure_sea_view_feature(apps, schema_editor):
    Feature = apps.get_model('properties', 'PropertyFeature')
    if Feature.objects.filter(
        Q(name_ru__iexact='Вид на море') | Q(name_en__iexact='Sea view')
    ).exists():
        return
    # Some imported databases have an ID sequence behind their existing rows.
    for statement in schema_editor.connection.ops.sequence_reset_sql(no_style(), [Feature]):
        schema_editor.execute(statement)
    Feature.objects.create(
        name='Вид на море',
        name_ru='Вид на море',
        name_en='Sea view',
        name_th='วิวทะเล',
    )


class Migration(migrations.Migration):
    dependencies = [('properties', '0025_hide_rent_and_land_properties')]

    operations = [migrations.RunPython(ensure_sea_view_feature, migrations.RunPython.noop)]
