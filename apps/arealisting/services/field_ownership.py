"""Ownership and manual override rules for fields populated by AREALISTING."""

from apps.arealisting.models import ArealistingListingGroup


PRICE_FIELDS = ('price_sale_thb', 'price_sale_usd', 'price_sale_rub')

SOURCE_FIELD_LABELS = {
    'title': 'Название',
    'title_ru': 'Название (RU)',
    'title_en': 'Название (EN)',
    'property_type': 'Тип недвижимости',
    'build_status': 'Стадия готовности',
    'description': 'Описание',
    'description_ru': 'Описание (RU)',
    'description_en': 'Описание (EN)',
    'developer': 'Застройщик',
    'district': 'Район',
    'location': 'Локация',
    'latitude': 'Широта',
    'longitude': 'Долгота',
    'bedrooms': 'Спальни',
    'bathrooms': 'Ванные',
    'area_total': 'Общая площадь',
    'area_land': 'Площадь участка',
    'floor': 'Этаж',
    'year_built': 'Год завершения',
    'furnished': 'С мебелью',
    'pool': 'Бассейн',
    'parking': 'Парковка',
    'security': 'Охрана',
    'gym': 'Спортзал',
    'complex_name': 'Название комплекса',
    'complex_name_ru': 'Название комплекса (RU)',
    'complex_name_en': 'Название комплекса (EN)',
    'price_sale_thb': 'Цена продажи (THB)',
    'price_sale_usd': 'Цена продажи (USD)',
    'price_sale_rub': 'Цена продажи (RUB)',
    'features': 'Характеристики и удобства',
    'images': 'Фотографии',
    'floorplans': 'Планировки',
}

DEFAULT_TRANSLATION_PAIRS = {
    'title': 'title_ru',
    'description': 'description_ru',
    'complex_name': 'complex_name_ru',
}


def ordered_source_fields(fields):
    """Return unique known fields in a stable, admin-friendly order."""
    values = set(fields or [])
    ordered = [field for field in SOURCE_FIELD_LABELS if field in values]
    ordered.extend(sorted(values - set(SOURCE_FIELD_LABELS)))
    return ordered


def protect_manual_changes(group, changed_fields):
    """Lock source-owned fields changed manually in the Property admin."""
    owned = set(group.source_owned_fields or [])
    changed = set(changed_fields or [])
    to_lock = owned & changed
    for base_field, translated_field in DEFAULT_TRANSLATION_PAIRS.items():
        if changed & {base_field, translated_field}:
            to_lock.update(owned & {base_field, translated_field})

    # The three converted prices are one atomic source value. Editing any one of
    # them protects the complete price triplet from the next conversion pass.
    if changed & set(PRICE_FIELDS) and owned & set(PRICE_FIELDS):
        to_lock.update(owned & set(PRICE_FIELDS))

    if not to_lock:
        return set()

    locked = set(group.locked_fields or [])
    added = to_lock - locked
    if added:
        locked.update(added)
        group.locked_fields = ordered_source_fields(locked)
        group.save(update_fields=('locked_fields', 'updated_at'))
    return added


def protect_property_manual_changes(prop, changed_fields):
    try:
        group = prop.arealisting_group
    except ArealistingListingGroup.DoesNotExist:
        return set()
    return protect_manual_changes(group, changed_fields)
