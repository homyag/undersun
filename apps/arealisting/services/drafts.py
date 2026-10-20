from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify

from apps.properties.models import (
    Developer,
    Property,
    PropertyFeature,
    PropertyFeatureRelation,
    PropertyType,
)

from ..models import (
    ArealistingAsset,
    ArealistingListingGroup,
    ArealistingLocationMapping,
    ArealistingProject,
    ArealistingSkippedUnit,
    ArealistingUnit,
)
from .field_ownership import (
    DEFAULT_TRANSLATION_PAIRS,
    PRICE_FIELDS,
    ordered_source_fields,
)
from .media import (
    MAX_SELECTED_MEDIA_ASSETS,
    candidate_media_assets,
    validate_selected_media_assets,
)
from .history import record_property_change


PROPERTY_TYPE_MAP = {
    'CONDO': 'condo',
    'VILLA': 'villa',
    'TOWNHOUSE': 'townhouse',
    'HOUSE': 'townhouse',
}

BUILD_STATUS_MAP = {
    'COMPLETED': 'completed',
    'READY': 'completed',
    'READY_TO_MOVE_IN': 'completed',
    'PLANNED': 'under_construction',
    'PRE_CONSTRUCTION': 'under_construction',
    'UNDER_CONSTRUCTION': 'under_construction',
    'FINISHING_WORKS': 'under_construction',
    'RENOVATION': 'under_construction',
}

FIELD_SYNC_ERROR_PREFIX = 'Поля AREALISTING: '
def _uniform_value(units, field):
    values = {getattr(unit, field) for unit in units}
    if len(values) == 1 and None not in values and '' not in values:
        return values.pop()
    return None


def _source_property_type(project, units):
    unit_types = {unit.property_type.strip().upper() for unit in units if unit.property_type.strip()}
    if len(unit_types) > 1:
        raise ValidationError('У выбранных предложений разные типы недвижимости.')
    source_type = next(iter(unit_types), project.project_type.strip().upper())
    project_type = project.project_type.strip().upper()
    if unit_types and project_type and source_type != project_type:
        raise ValidationError('Тип предложения не совпадает с типом комплекса AREALISTING.')
    local_type = PROPERTY_TYPE_MAP.get(source_type)
    if not local_type:
        raise ValidationError(
            f'Для типа AREALISTING «{source_type or "не указан"}» не настроен PropertyType.'
        )
    try:
        return PropertyType.objects.get(name=local_type)
    except PropertyType.DoesNotExist as exc:
        raise ValidationError(
            f'В Undersun отсутствует тип недвижимости «{local_type}».'
        ) from exc


def _location_options(project):
    source_ids = {
        item.get('external_id')
        for item in (project.districts or [])
        if (
            isinstance(item, dict)
            and isinstance(item.get('external_id'), str)
            and item.get('external_id').strip()
        )
    }
    mappings = list(
        ArealistingLocationMapping.objects.filter(
            external_id__in=source_ids,
            is_confirmed=True,
            is_deleted=False,
        )
        .exclude(mapping_mode__in=(
            ArealistingLocationMapping.MappingMode.UNMAPPED,
            ArealistingLocationMapping.MappingMode.IGNORE,
        ))
        .select_related('district', 'location__district')
    )
    location_mappings = [mapping for mapping in mappings if mapping.location_id]
    candidate_mappings = location_mappings or [mapping for mapping in mappings if mapping.district_id]
    options = {}
    for mapping in candidate_mappings:
        district = mapping.location.district if mapping.location_id else mapping.district
        location = mapping.location if mapping.location_id else None
        key = (district.pk, location.pk if location else None)
        if key not in options:
            options[key] = {
                'id': str(mapping.pk),
                'district': district,
                'location': location,
                'source_names': [],
            }
        source_name = mapping.source_name.strip() if mapping.source_name else ''
        if source_name and source_name not in options[key]['source_names']:
            options[key]['source_names'].append(source_name)
    return list(options.values())


def _mapped_location(project, location_choice=None, *, allow_choice=False):
    options = _location_options(project)
    if not options:
        raise ValidationError('Для комплекса не настроен подтверждённый район Undersun.')
    selected = None
    if location_choice not in (None, ''):
        selected = next(
            (option for option in options if option['id'] == str(location_choice)),
            None,
        )
        if selected is None:
            raise ValidationError(
                'Выбранная локация больше не доступна для этого комплекса. Обновите экран.'
            )
    elif len(options) == 1:
        selected = options[0]
    elif allow_choice:
        return None, None
    else:
        raise ValidationError(
            'Для комплекса подтверждено несколько локаций Undersun. '
            'Выберите локацию для этого черновика.'
        )
    return selected['district'], selected['location']


def _draft_title(project, units, language):
    project_name = (
        getattr(project, f'name_{language}', '')
        or project.name_en
        or project.name_ru
        or project.external_id
    )
    if len(units) == 1 and units[0].unit_number:
        suffix = f'№ {units[0].unit_number}'
    else:
        bedrooms = _uniform_value(units, 'bedrooms')
        area = _uniform_value(units, 'internal_area_sqm')
        details = []
        if bedrooms is not None:
            details.append(
                f'{bedrooms} сп.' if language == 'ru' else f'{bedrooms} bedroom'
            )
        if area is not None:
            details.append(f'{area} м²')
        suffix = ', '.join(details) or f'{len(units)} units'
    return f'{project_name} — {suffix}'[:200]


def _draft_slug(title, units):
    identity = '-'.join(unit.external_id for unit in units)
    suffix = slugify(identity)[:48] or str(units[0].pk)
    base = slugify(title)[: max(1, 150 - len(suffix) - 14)] or 'arealisting-property'
    candidate = f'{base}-arealisting-{suffix}'[:150]
    serial = 2
    while Property.objects.filter(slug=candidate).exists():
        marker = f'-{serial}'
        candidate = f'{base[:150 - len(suffix) - len(marker) - 14]}-arealisting-{suffix}{marker}'
        serial += 1
    return candidate


def _integer_bathrooms(units):
    value = _uniform_value(units, 'bathrooms')
    if value is None or value < 0 or value != value.to_integral_value():
        return None
    return int(value)


def _furnished_value(units):
    values = []
    for unit in units:
        options = unit.furnishing if isinstance(unit.furnishing, list) else []
        names = [
            str(option.get('name') or '').strip().lower()
            for option in options
            if isinstance(option, dict)
        ]
        if any('unfurnished' in name or 'без мебел' in name for name in names):
            values.append(False)
        elif any('furnished' in name or 'мебел' in name for name in names):
            values.append(True)
        else:
            values.append(None)
    return values[0] if values and len(set(values)) == 1 and values[0] is not None else None


def _amenity_flags(project):
    source_has_amenities = bool(project.amenities) or 'amenities' in (project.raw_payload or {})
    if not source_has_amenities:
        return {}
    names = ' '.join(
        str(value)
        for amenity in (project.amenities or [])
        if isinstance(amenity, dict)
        for value in (amenity.get('name_en'), amenity.get('name_ru'))
        if value
    ).lower()
    return {
        'pool': any(token in names for token in ('pool', 'бассейн')),
        'gym': any(token in names for token in ('gym', 'fitness', 'спортзал', 'фитнес')),
        'parking': any(token in names for token in ('parking', 'car park', 'парков')),
        'security': any(token in names for token in ('security', 'guard', 'охрана', 'безопасност')),
    }


def _mapped_developer(name):
    name = ' '.join(str(name or '').split()).strip()[:100]
    if not name:
        return None
    developer = (
        Developer.objects.filter(name__iexact=name).first()
        or Developer.objects.filter(name_en__iexact=name).first()
    )
    if developer:
        return developer
    base = slugify(name)[:50] or 'arealisting-developer'
    slug = base
    serial = 2
    while Developer.objects.filter(slug=slug).exists():
        marker = f'-{serial}'
        slug = f'{base[:50 - len(marker)]}{marker}'
        serial += 1
    return Developer.objects.create(name=name, name_en=name, slug=slug)


def _source_property_values(
    project,
    units,
    *,
    require_core=False,
    location_choice=None,
    allow_location_choice=False,
):
    values = {}
    if require_core or project.name_ru or project.name_en:
        title_ru = _draft_title(project, units, 'ru')
        title_en = _draft_title(project, units, 'en')
        values.update({
            'title': title_ru or title_en,
            'title_ru': title_ru,
            'title_en': title_en,
        })

    try:
        values['property_type'] = _source_property_type(project, units)
    except ValidationError:
        if require_core:
            raise

    try:
        district, location = _mapped_location(
            project,
            location_choice,
            allow_choice=allow_location_choice,
        )
        if district is not None:
            values['district'] = district
        if location is not None:
            values['location'] = location
    except ValidationError:
        if require_core:
            raise

    description_ru = (project.description_ru or '').strip()
    description_en = (project.description_en or '').strip()
    if description_ru or description_en:
        values['description'] = description_ru or description_en
    if description_ru:
        values['description_ru'] = description_ru
    if description_en:
        values['description_en'] = description_en

    complex_name_ru = (project.name_ru or project.name_en or '').strip()[:100]
    complex_name_en = (project.name_en or project.name_ru or '').strip()[:100]
    if complex_name_ru or complex_name_en:
        values['complex_name'] = complex_name_ru or complex_name_en
    if complex_name_ru:
        values['complex_name_ru'] = complex_name_ru
    if complex_name_en:
        values['complex_name_en'] = complex_name_en

    build_status = BUILD_STATUS_MAP.get((project.construction_status or '').strip().upper())
    if build_status:
        values['build_status'] = build_status
    if project.completion_date and build_status == 'completed':
        values['year_built'] = project.completion_date.year
    if project.latitude is not None:
        values['latitude'] = project.latitude
    if project.longitude is not None:
        values['longitude'] = project.longitude

    field_map = {
        'bedrooms': 'bedrooms',
        'floor': 'floor',
        'area_total': 'internal_area_sqm',
        'area_land': 'plot_size_sqm',
    }
    for target, source in field_map.items():
        value = _uniform_value(units, source)
        if value is not None and not (target == 'floor' and value < 0):
            values[target] = value
    bathrooms = _integer_bathrooms(units)
    if bathrooms is not None:
        values['bathrooms'] = bathrooms
    furnished = _furnished_value(units)
    if furnished is not None:
        values['furnished'] = furnished
    values.update(_amenity_flags(project))
    return values


def _feature_values(project, units):
    result = []
    for amenity in (project.amenities or []):
        if not isinstance(amenity, dict):
            continue
        name_en = ' '.join(str(amenity.get('name_en') or '').split()).strip()[:100]
        name_ru = ' '.join(str(amenity.get('name_ru') or '').split()).strip()[:100]
        if name_en or name_ru:
            result.append((name_ru, name_en))
    if any(unit.sea_view is True for unit in units):
        result.append(('Вид на море', 'Sea view'))
    return result


def _media_previews(project, units):
    candidates = candidate_media_assets(project, units)
    # Keep the canonical asset IDs chosen by candidate_media_assets for import,
    # but show a shared URL under its selected unit instead of the project.
    candidate_urls = {asset.source_url for asset, _role in candidates}
    unit_gallery_urls = {unit.pk: set() for unit in units}
    for unit_id, source_url in ArealistingAsset.objects.filter(
        unit__in=units,
        is_active=True,
        asset_type=ArealistingAsset.AssetType.UNIT_GALLERY,
    ).values_list('unit_id', 'source_url'):
        if source_url in candidate_urls:
            unit_gallery_urls[unit_id].add(source_url)
    unit_owner_by_url = {}
    for unit in units:
        for source_url in unit_gallery_urls[unit.pk]:
            unit_owner_by_url.setdefault(source_url, unit.pk)

    # Общая gallery проекта обычно гораздо больше gallery выбранного юнита.
    # Не даём ей целиком занять лимит preview: иначе планировка/изображение
    # конкретной виллы или квартиры не попадёт в создаваемый черновик, потому
    # что браузер отправляет на импорт только показанные и выбранные assets.
    # Сначала предлагаем явные планировки, затем материалы выбранных units;
    # относительный порядок внутри каждой категории остаётся исходным.
    displayed = sorted(
        candidates,
        key=lambda item: (
            0 if item[1] == 'FLOOR_PLAN'
            else (1 if item[0].source_url in unit_owner_by_url else 2),
        ),
    )[:MAX_SELECTED_MEDIA_ASSETS]

    def serialize(asset, role):
        return {
            'id': asset.pk,
            'url': asset.source_url,
            'role': role,
        }

    project_candidates = [
        item for item in candidates
        if item[0].source_url not in unit_owner_by_url
    ]
    project_displayed = [
        item for item in displayed
        if item[0].source_url not in unit_owner_by_url
    ]
    unit_previews = []
    for unit in units:
        unit_displayed = [
            item for item in displayed
            if unit_owner_by_url.get(item[0].source_url) == unit.pk
        ]
        unit_previews.append({
            'id': unit.pk,
            'number': unit.unit_number,
            'status': unit.availability_status,
            'images': [serialize(*item) for item in unit_displayed],
            'images_total': len(unit_gallery_urls[unit.pk]),
        })
    return {
        'project_images': [serialize(*item) for item in project_displayed],
        'project_images_total': len(project_candidates),
        'unit_images': unit_previews,
        'media_assets_total': len(candidates),
        'media_selection_limit': MAX_SELECTED_MEDIA_ASSETS,
    }


def _replace_source_features(prop, project, units):
    feature_ids = []
    for name_ru, name_en in _feature_values(project, units):
        feature = None
        if name_en:
            feature = PropertyFeature.objects.filter(name_en__iexact=name_en).first()
        if feature is None and name_ru:
            feature = PropertyFeature.objects.filter(name_ru__iexact=name_ru).first()
        if feature is None:
            feature = PropertyFeature.objects.create(
                name=name_ru or name_en,
                name_ru=name_ru or name_en,
                name_en=name_en or name_ru,
            )
        feature_ids.append(feature.pk)
    PropertyFeatureRelation.objects.filter(property=prop).exclude(
        feature_id__in=feature_ids
    ).delete()
    PropertyFeatureRelation.objects.bulk_create(
        [PropertyFeatureRelation(property=prop, feature_id=feature_id) for feature_id in feature_ids],
        ignore_conflicts=True,
    )


def _validate_units(project, unit_ids, *, for_update=False):
    if not isinstance(unit_ids, list) or not 1 <= len(unit_ids) <= 100:
        raise ValidationError('Выберите от 1 до 100 предложений AREALISTING.')
    try:
        normalized_ids = {int(value) for value in unit_ids}
    except (TypeError, ValueError) as exc:
        raise ValidationError('Некорректный список предложений AREALISTING.') from exc
    queryset = ArealistingUnit.objects.filter(
        pk__in=normalized_ids,
        project=project,
        is_deleted=False,
        listing_group__isnull=True,
    )
    if for_update:
        queryset = queryset.select_for_update()
    units = list(queryset.order_by('pk'))
    if len(units) != len(normalized_ids):
        raise ValidationError(
            'Черновик можно создать только из существующих, ещё не связанных предложений.'
        )
    supported_statuses = {
        ArealistingUnit.AvailabilityStatus.AVAILABLE,
        ArealistingUnit.AvailabilityStatus.SOLD,
    }
    if any(unit.availability_status not in supported_statuses for unit in units):
        raise ValidationError('У одного из предложений не указан поддерживаемый статус.')
    if not any(
        unit.availability_status == ArealistingUnit.AvailabilityStatus.AVAILABLE
        for unit in units
    ):
        raise ValidationError('Для нового черновика требуется хотя бы одно доступное предложение.')
    if ArealistingSkippedUnit.objects.filter(unit__in=units).exists():
        raise ValidationError('Сначала верните пропущенные предложения в очередь.')
    return units


def _preview_values(
    project,
    units,
    *,
    location_choice=None,
    allow_location_choice=False,
):
    source_values = _source_property_values(
        project,
        units,
        require_core=True,
        location_choice=location_choice,
        allow_location_choice=allow_location_choice,
    )
    bedrooms = source_values.get('bedrooms')
    area_total = source_values.get('area_total')
    if len(units) > 1 and (bedrooms is None or area_total is None):
        raise ValidationError(
            'Для одной карточки выберите предложения одной планировки '
            'с одинаковыми спальнями и площадью.'
        )
    prices = [unit.price for unit in units if unit.price and unit.price > 0]
    currencies = {unit.currency for unit in units if unit.currency}
    one_currency = len(currencies) == 1
    return {
        **source_values,
        'bedrooms': bedrooms,
        'area_total': area_total,
        'source_price': min(prices) if prices and one_currency else None,
        'source_currency': currencies.pop() if one_currency else 'разные валюты',
    }


def preview_draft(project_id, unit_ids, location_choice=None):
    project = ArealistingProject.objects.get(pk=project_id, is_deleted=False)
    units = _validate_units(project, unit_ids)
    location_options = _location_options(project)
    values = _preview_values(
        project,
        units,
        location_choice=location_choice,
        allow_location_choice=True,
    )
    media_previews = _media_previews(project, units)
    return {
        'title_ru': values['title_ru'],
        'title_en': values['title_en'],
        'property_type': str(values['property_type']),
        'district': str(values.get('district') or ''),
        'location': str(values.get('location')) if values.get('location') else '',
        'location_choice_required': len(location_options) > 1,
        'selected_location_choice': (
            str(location_choice)
            if location_choice not in (None, '')
            else (location_options[0]['id'] if len(location_options) == 1 else '')
        ),
        'location_options': [
            {
                'id': option['id'],
                'district': str(option['district']),
                'location': str(option['location']) if option['location'] else '',
                'source_names': option['source_names'],
            }
            for option in location_options
        ],
        'bedrooms': values.get('bedrooms'),
        'bathrooms': values.get('bathrooms'),
        'floor': values.get('floor'),
        'area_total': values.get('area_total'),
        'area_land': values.get('area_land'),
        'build_status': values.get('build_status', 'under_construction'),
        'developer': project.developer_name,
        'latitude': values.get('latitude'),
        'longitude': values.get('longitude'),
        'furnished': values.get('furnished'),
        'pool': values.get('pool'),
        'parking': values.get('parking'),
        'security': values.get('security'),
        'gym': values.get('gym'),
        'features_count': len(_feature_values(project, units)),
        'has_description_ru': bool(project.description_ru),
        'has_description_en': bool(project.description_en),
        'source_price': values['source_price'],
        'source_currency': values['source_currency'],
        'unit_count': len(units),
        **media_previews,
        'is_active': False,
    }


@transaction.atomic
def create_draft(
    project_id,
    unit_ids,
    location_choice=None,
    media_asset_ids=None,
):
    project = ArealistingProject.objects.select_for_update().get(
        pk=project_id,
        is_deleted=False,
    )
    units = _validate_units(project, unit_ids, for_update=True)
    if media_asset_ids is not None:
        validate_selected_media_assets(project, units, media_asset_ids)
    location_options = _location_options(project)
    values = _preview_values(project, units, location_choice=location_choice)
    source_values = {
        field: value
        for field, value in values.items()
        if field not in {'source_price', 'source_currency'} and value not in (None, '')
    }
    if project.developer_name:
        source_values['developer'] = _mapped_developer(project.developer_name)
    title_ru = source_values['title_ru']
    title_en = source_values['title_en']
    prop = Property.objects.create(
        slug=_draft_slug(title_en or title_ru, units),
        deal_type='sale',
        status='available',
        is_active=False,
        **source_values,
    )
    owned_fields = list(source_values)
    if len(location_options) > 1:
        owned_fields = [
            field for field in owned_fields if field not in {'district', 'location'}
        ]
    if values['source_price'] is not None:
        owned_fields.extend(PRICE_FIELDS)
    source_features_are_known = (
        bool(project.amenities)
        or 'amenities' in (project.raw_payload or {})
        or any(unit.sea_view is not None for unit in units)
    )
    if source_features_are_known:
        owned_fields.append('features')
    owned_fields.extend(('images', 'floorplans'))
    group = ArealistingListingGroup.objects.create(
        project=project,
        property=prop,
        name=f'Undersun #{prop.pk}',
        catalog_origin=ArealistingListingGroup.CatalogOrigin.AREALISTING_DRAFT,
        source_owned_fields=ordered_source_fields(owned_fields),
        grouping_mode=(
            ArealistingListingGroup.GroupingMode.UNIT
            if len(units) == 1
            else ArealistingListingGroup.GroupingMode.LAYOUT
        ),
    )
    ArealistingUnit.objects.filter(pk__in=[unit.pk for unit in units]).update(
        listing_group=group
    )
    if 'features' in group.source_owned_fields:
        _replace_source_features(prop, project, units)
    from .pricing import update_group_price
    from .sync import ArealistingSyncService

    ArealistingSyncService.recalculate_listing_group(group)
    update_group_price(group.pk)
    return prop


@transaction.atomic
def refresh_group_property(group_id, *, reports=None, sync_run=None):
    """Refresh only fields explicitly owned by AREALISTING for one linked card."""
    group = (
        ArealistingListingGroup.objects.select_for_update()
        .select_related('project')
        .get(pk=group_id)
    )
    report = {
        'project_id': group.project_id,
        'property_id': group.property_id,
        'updated_fields': [],
        'status': 'skipped',
        'reason': '',
    }
    if not group.property_id or not group.source_owned_fields:
        report['reason'] = 'нет полей под управлением AREALISTING'
        if reports is not None:
            reports.append(report)
        return False
    if group.project.is_deleted:
        report['reason'] = 'комплекс удалён в источнике'
        if reports is not None:
            reports.append(report)
        return False

    prop = Property.objects.select_for_update().get(pk=group.property_id)

    units = list(group.units.filter(is_deleted=False).order_by('pk'))
    if not units:
        report['reason'] = 'нет связанных актуальных предложений'
        if reports is not None:
            reports.append(report)
        return False

    errors = [
        error for error in (group.validation_errors or [])
        if not str(error).startswith(FIELD_SYNC_ERROR_PREFIX)
    ]
    try:
        values = _source_property_values(group.project, units, require_core=False)
        owned = set(group.source_owned_fields or [])
        locked = set(group.locked_fields or [])
        for base_field, translated_field in DEFAULT_TRANSLATION_PAIRS.items():
            if translated_field in locked:
                locked.add(base_field)
            if base_field in locked:
                locked.add(translated_field)
        update_values = {
            field: value
            for field, value in values.items()
            if field in owned and field not in locked and value not in (None, '')
        }
        if 'developer' in owned and 'developer' not in locked and group.project.developer_name:
            update_values['developer'] = _mapped_developer(group.project.developer_name)
        for field, value in update_values.items():
            model_field = Property._meta.get_field(field)
            clean_value = value.pk if model_field.many_to_one and value is not None else value
            model_field.clean(clean_value, prop)
        changed_fields = []
        for field, value in update_values.items():
            before = getattr(prop, field)
            if before != value:
                model_field = Property._meta.get_field(field)
                changed_fields.append({
                    'field': field,
                    'before': before.pk if model_field.many_to_one and before is not None else before,
                    'after': value.pk if model_field.many_to_one and value is not None else value,
                })
        if update_values:
            Property.objects.filter(pk=group.property_id).update(**update_values)
        if 'features' in owned and 'features' not in locked:
            features_before = set(PropertyFeatureRelation.objects.filter(property=prop).values_list('feature_id', flat=True))
            _replace_source_features(prop, group.project, units)
            update_values['features'] = True
            features_after = set(PropertyFeatureRelation.objects.filter(property=prop).values_list('feature_id', flat=True))
            if features_before != features_after:
                changed_fields.append({'field': 'features', 'before': sorted(features_before), 'after': sorted(features_after)})
    except (ValidationError, ValueError) as exc:
        reason = str(exc)
        errors.append(FIELD_SYNC_ERROR_PREFIX + reason)
        report['reason'] = reason
        group.validation_errors = errors
        group.save(update_fields=('validation_errors', 'updated_at'))
        if reports is not None:
            reports.append(report)
        return False

    group.validation_errors = errors
    group.save(update_fields=('validation_errors', 'updated_at'))
    report['updated_fields'] = sorted(update_values)
    report['status'] = 'updated' if update_values else 'unchanged'
    if changed_fields:
        record_property_change(
            property_id=prop.pk, project_id=group.project_id,
            kind='FIELDS', sync_run=sync_run,
            details={'changed_fields': changed_fields},
        )
    if reports is not None:
        reports.append(report)
    return bool(update_values)


@transaction.atomic
def skip_units(project_id, unit_ids, *, user, reason=''):
    project = ArealistingProject.objects.select_for_update().get(
        pk=project_id,
        is_deleted=False,
    )
    try:
        normalized_ids = {int(value) for value in unit_ids}
    except (TypeError, ValueError) as exc:
        raise ValidationError('Некорректный список предложений AREALISTING.') from exc
    if not 1 <= len(normalized_ids) <= 100:
        raise ValidationError('Выберите от 1 до 100 предложений AREALISTING.')
    units = list(
        ArealistingUnit.objects.select_for_update().filter(
            pk__in=normalized_ids,
            project=project,
            is_deleted=False,
            listing_group__isnull=True,
        )
    )
    if len(units) != len(normalized_ids):
        raise ValidationError('Можно пропустить только ещё не связанные предложения.')
    for unit in units:
        ArealistingSkippedUnit.objects.update_or_create(
            unit=unit,
            defaults={'skipped_by': user, 'reason': str(reason or '')[:255]},
        )
    return len(units)


@transaction.atomic
def restore_units(project_id, unit_ids):
    project = ArealistingProject.objects.select_for_update().get(
        pk=project_id,
        is_deleted=False,
    )
    try:
        normalized_ids = {int(value) for value in unit_ids}
    except (TypeError, ValueError) as exc:
        raise ValidationError('Некорректный список предложений AREALISTING.') from exc
    if not 1 <= len(normalized_ids) <= 100:
        raise ValidationError('Выберите от 1 до 100 предложений AREALISTING.')
    return ArealistingSkippedUnit.objects.filter(
        unit_id__in=normalized_ids,
        unit__project=project,
    ).delete()[0]
