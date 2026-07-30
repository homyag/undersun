from django.db import migrations


def hide_rent_and_land_properties(apps, schema_editor):
    Property = apps.get_model('properties', 'Property')
    Property.objects.filter(deal_type__in=['rent', 'both']).update(is_active=False)
    Property.objects.filter(property_type__name='land').update(is_active=False)


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0024_fill_property_feature_english_names'),
    ]

    operations = [
        migrations.RunPython(hide_rent_and_land_properties, migrations.RunPython.noop),
    ]
