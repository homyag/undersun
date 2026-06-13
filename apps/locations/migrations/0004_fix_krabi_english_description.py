from django.db import migrations


def fix_krabi_english_description(apps, schema_editor):
    District = apps.get_model('locations', 'District')
    District.objects.filter(
        slug='krabi',
        description_en__in=['', 'krabi huyabi'],
    ).update(description_en='Krabi Province')
    District.objects.filter(
        slug='krabi',
        description_en__isnull=True,
    ).update(description_en='Krabi Province')


class Migration(migrations.Migration):

    dependencies = [
        ('locations', '0003_fill_ko_kaeo_english_name'),
    ]

    operations = [
        migrations.RunPython(fix_krabi_english_description, migrations.RunPython.noop),
    ]
