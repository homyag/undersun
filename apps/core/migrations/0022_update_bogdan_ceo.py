from django.db import migrations


def set_bogdan_ceo(apps, schema_editor):
    Team = apps.get_model('core', 'Team')
    members = Team.objects.filter(is_active=True, first_name_en__iexact='Bogdan')

    if not members.exists():
        members = Team.objects.filter(is_active=True, first_name_ru__iexact='Богдан')

    if not members.exists():
        members = Team.objects.filter(is_active=True, first_name__iexact='Bogdan')

    members.update(
        position='CEO',
        position_ru='CEO',
        position_en='CEO',
        position_th='CEO',
        role='other',
    )


def restore_bogdan_sales_director(apps, schema_editor):
    Team = apps.get_model('core', 'Team')
    members = Team.objects.filter(is_active=True, first_name_en__iexact='Bogdan')

    if not members.exists():
        members = Team.objects.filter(is_active=True, first_name_ru__iexact='Богдан')

    if not members.exists():
        members = Team.objects.filter(is_active=True, first_name__iexact='Bogdan')

    members.update(
        position='Sales Director',
        position_ru='Директор по продажам',
        position_en='Sales Director',
        position_th='Sales Director',
        role='sales_director',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0021_requestlog_asn_requestlog_asn_organization'),
    ]

    operations = [
        migrations.RunPython(set_bogdan_ceo, restore_bogdan_sales_director),
    ]
