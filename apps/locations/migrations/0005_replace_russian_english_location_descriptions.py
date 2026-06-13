from django.db import migrations


LOCATION_EN_DESCRIPTIONS = {
    'cherng-talay': (
        'Cherng Talay is a high-demand west-coast Phuket area near Bang Tao '
        'and Laguna, popular for villas, condos, family living, and long-stay rentals.'
    ),
    'karon': (
        'Karon is a west-coast Phuket beach area in Mueang Phuket, known for '
        'resort living, sea-view condos, and access to Kata and Patong.'
    ),
    'rawai': (
        'Rawai is a southern Phuket residential area popular with expats, '
        'long-stay buyers, villa renters, and access to Nai Harn and Chalong.'
    ),
    'chalong': (
        'Chalong is a practical southern Phuket hub with marinas, schools, '
        'shopping, and access to Rawai, Nai Harn, Kata, and Phuket Town.'
    ),
    'wichit': (
        'Wichit connects Phuket Town with central shopping, hospitals, '
        'schools, and residential neighborhoods, with condos, houses, and investment properties.'
    ),
    'ratsada': (
        'Ratsada sits east of Phuket Town with access to piers, local '
        'services, and residential neighborhoods for buyers and renters.'
    ),
    'ko-kaeo': (
        'Ko Kaeo is a residential area in Mueang Phuket with access to '
        'Boat Lagoon, schools, shopping, and central routes across the island.'
    ),
    'talad-nuea': (
        'Talad Nuea is a central Phuket Town area with local services, '
        'schools, shops, and urban property options.'
    ),
    'talad-yai': (
        'Talad Yai is the historic core of Phuket Town, known for Old Town '
        'streets, city living, shops, offices, and boutique property demand.'
    ),
    'patong': (
        "Patong is Phuket's busiest west-coast resort area, known for "
        'nightlife, beach access, rental demand, condos, hotels, and commercial property.'
    ),
    'kamala': (
        'Kamala is a quieter west-coast Phuket area with beach access, '
        'hillside villas, sea-view homes, and family-friendly residential communities.'
    ),
    'kathu': (
        'Kathu is a central Phuket district area between Phuket Town and '
        'Patong, popular for everyday living, golf, schools, and value-focused homes.'
    ),
    'thep-krasasttri': (
        'Thep Krasattri is a northern Phuket residential area with access '
        'to the airport, schools, marinas, and Thalang amenities.'
    ),
    'si-sunthon': (
        'Si Sunthon is a Thalang residential area with access to Boat '
        'Lagoon, schools, shopping, and central routes across Phuket.'
    ),
    'pa-khlok': (
        'Pa Khlok is an eastern Phuket area known for marinas, quiet '
        'residential communities, land plots, villas, and access to Ao Po and Cape Yamu.'
    ),
    'mai-khao': (
        'Mai Khao is a northern Phuket beach area near the airport, known '
        'for long beach frontage, resorts, land, and investment properties.'
    ),
    'sakhu': (
        'Sakhu is a northern Phuket area covering Nai Yang and airport-side '
        'neighborhoods, with condos, villas, and rental demand near the beach.'
    ),
    'bangtao': (
        'Bang Tao is a premium west-coast Phuket area near Laguna, beach '
        'clubs, international schools, villas, condos, and strong rental demand.'
    ),
}


def replace_russian_english_location_descriptions(apps, schema_editor):
    Location = apps.get_model('locations', 'Location')

    for slug, description in LOCATION_EN_DESCRIPTIONS.items():
        Location.objects.filter(slug=slug).update(description_en=description)


class Migration(migrations.Migration):

    dependencies = [
        ('locations', '0004_fix_krabi_english_description'),
    ]

    operations = [
        migrations.RunPython(
            replace_russian_english_location_descriptions,
            migrations.RunPython.noop,
        ),
    ]
