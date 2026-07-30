from django.db import migrations


def hide_rent_and_land_services(apps, schema_editor):
    Service = apps.get_model('core', 'Service')
    Service.objects.filter(slug__in=['renting-property', 'land-sale']).update(is_active=False)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0024_team_market_since_year_team_prea_role_and_more'),
    ]

    operations = [
        migrations.RunPython(hide_rent_and_land_services, migrations.RunPython.noop),
    ]
