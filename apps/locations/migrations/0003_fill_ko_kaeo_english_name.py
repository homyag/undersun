from django.db import migrations


DISTRICT_TRANSLATIONS = {
    'thalang': {
        'name_en': 'Thalang',
        'description_en': 'Thalang District',
    },
    'mueang-phuket': {
        'name_en': 'Mueang Phuket',
        'description_en': 'Mueang Phuket District',
    },
    'kathu-district': {
        'name_en': 'Kathu District',
        'description_en': 'Kathu District',
    },
    'krabi': {
        'name_en': 'Krabi',
    },
}


LOCATION_TRANSLATIONS = {
    'cherng-talay': {
        'name_en': 'Cherng Talay',
        'description_en': 'Cherng Talay location in Thalang District',
    },
    'karon': {
        'name_en': 'Karon',
        'description_en': 'Karon location in Mueang Phuket District',
    },
    'rawai': {
        'name_en': 'Rawai',
        'description_en': 'Rawai location in Mueang Phuket District',
    },
    'chalong': {
        'name_en': 'Chalong',
        'description_en': 'Chalong location in Mueang Phuket District',
    },
    'wichit': {
        'name_en': 'Wichit',
        'description_en': 'Wichit location in Mueang Phuket District',
    },
    'ratsada': {
        'name_en': 'Ratsada',
        'description_en': 'Ratsada location in Mueang Phuket District',
    },
    'ko-kaeo': {
        'name_en': 'Ko Kaeo',
        'description_en': 'Ko Kaeo location in Mueang Phuket District',
    },
    'talad-nuea': {
        'name_en': 'Talad Nuea',
        'description_en': 'Talad Nuea location in Mueang Phuket District',
    },
    'talad-yai': {
        'name_en': 'Talad Yai',
        'description_en': 'Talad Yai location in Mueang Phuket District',
    },
    'patong': {
        'name_en': 'Patong',
        'description_en': 'Patong location in Kathu District',
    },
    'kamala': {
        'name_en': 'Kamala',
        'description_en': 'Kamala location in Kathu District',
    },
    'kathu': {
        'name_en': 'Kathu',
        'description_en': 'Kathu location in Kathu District',
    },
    'thep-krasasttri': {
        'name_en': 'Thep Krasattri',
        'description_en': 'Thep Krasattri location in Thalang District',
    },
    'si-sunthon': {
        'name_en': 'Si Sunthon',
        'description_en': 'Si Sunthon location in Thalang District',
    },
    'pa-khlok': {
        'name_en': 'Pa Khlok',
        'description_en': 'Pa Khlok location in Thalang District',
    },
    'mai-khao': {
        'name_en': 'Mai Khao',
        'description_en': 'Mai Khao location in Thalang District',
    },
    'sakhu': {
        'name_en': 'Sakhu',
        'description_en': 'Sakhu location in Thalang District',
    },
    'bangtao': {
        'name_en': 'Bang Tao',
        'description_en': 'Bang Tao location in Thalang District',
    },
}


def update_empty_fields(queryset, field_values):
    for field_name, value in field_values.items():
        queryset.filter(**{f'{field_name}__isnull': True}).update(**{field_name: value})
        queryset.filter(**{field_name: ''}).update(**{field_name: value})


def fill_english_geo_translations(apps, schema_editor):
    District = apps.get_model('locations', 'District')
    Location = apps.get_model('locations', 'Location')

    for slug, field_values in DISTRICT_TRANSLATIONS.items():
        update_empty_fields(District.objects.filter(slug=slug), field_values)

    for slug, field_values in LOCATION_TRANSLATIONS.items():
        update_empty_fields(Location.objects.filter(slug=slug), field_values)


class Migration(migrations.Migration):

    dependencies = [
        ('locations', '0002_district_image_location_image'),
    ]

    operations = [
        migrations.RunPython(fill_english_geo_translations, migrations.RunPython.noop),
    ]
