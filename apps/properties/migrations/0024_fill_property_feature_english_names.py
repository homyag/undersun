from django.db import migrations


FEATURE_TRANSLATIONS = {
    'кондиционер': 'Air Conditioning',
    'Парковка': 'Parking',
    'Спортзал': 'Gym',
    'Рабочее место': 'Workspace',
    'Лифт': 'Elevator',
    'Огороженная территория': 'Gated Community',
    'Тренажерный зал': 'Fitness Center',
    'Зона барбекю': 'BBQ Area',
    'Балкон': 'Balcony',
    'Можно с животными': 'Pet Friendly',
    'Сауна': 'Sauna',
    'Стиральная машина': 'Washing Machine',
    'Кофеварка': 'Coffee Maker',
    'Гараж': 'Garage',
    'Телевизор': 'TV',
    'Микроволновая печь': 'Microwave',
    'Посудомоечная машина': 'Dishwasher',
    'Сейф': 'Safe',
}


def fill_property_feature_english_names(apps, schema_editor):
    PropertyFeature = apps.get_model('properties', 'PropertyFeature')

    for name_ru, name_en in FEATURE_TRANSLATIONS.items():
        queryset = PropertyFeature.objects.filter(name_ru=name_ru)
        queryset.filter(name_en__isnull=True).update(name_en=name_en)
        queryset.filter(name_en='').update(name_en=name_en)


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0023_propertyimage_alt_generation_fields'),
    ]

    operations = [
        migrations.RunPython(fill_property_feature_english_names, migrations.RunPython.noop),
    ]
