"""Explicit, transactional links. Source ingestion never expands these selections."""
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.properties.models import Property
from ..models import (
    ArealistingListingGroup,
    ArealistingManualProperty,
    ArealistingProject,
    ArealistingSkippedUnit,
    ArealistingUnit,
)
from .field_ownership import PRICE_FIELDS, ordered_source_fields
from .drafts import BUILD_STATUS_MAP, _integer_bathrooms
from .history import record_property_change


FIELDS = {
    'complex_name_ru': 'Название комплекса (RU)',
    'complex_name_en': 'Название комплекса (EN)',
    'bedrooms': 'Спальни',
    'bathrooms': 'Ванные',
    'floor': 'Этаж',
    'area_total': 'Площадь',
    'area_land': 'Площадь участка',
    'build_status': 'Стадия строительства',
    'year_built': 'Год завершения',
}

PROJECT_FIELD_KEYS = ('complex_name_ru', 'complex_name_en', 'build_status', 'year_built')
UNIT_FIELD_SOURCES = {
    'bedrooms': 'bedrooms',
    'bathrooms': 'bathrooms',
    'floor': 'floor',
    'area_total': 'internal_area_sqm',
    'area_land': 'plot_size_sqm',
}


def unavailable_reason(project, units, field):
    if field == 'year_built' and BUILD_STATUS_MAP.get(
        (project.construction_status or '').strip().upper()
    ) != 'completed':
        return 'Год доступен только для завершённого проекта.'
    if field in PROJECT_FIELD_KEYS:
        return 'У проекта нет значения для этого поля.'
    values = [getattr(unit, UNIT_FIELD_SOURCES[field]) for unit in units]
    if any(value is None or value == '' for value in values):
        return 'Нет значения у одного или нескольких выбранных предложений.'
    if len(set(values)) > 1:
        return 'У выбранных предложений разные значения.'
    if field == 'bathrooms':
        return 'Количество ванных должно быть целым числом.'
    if field == 'floor':
        return 'Этаж не может быть отрицательным.'
    return 'Нет допустимого значения для этого поля.'


def project_proposals(project):
    result = {'complex_name_ru': project.name_ru, 'complex_name_en': project.name_en}
    build_status = BUILD_STATUS_MAP.get((project.construction_status or '').strip().upper())
    if build_status:
        result['build_status'] = build_status
    if build_status == 'completed' and project.completion_date:
        result['year_built'] = project.completion_date.year
    return {key: value for key, value in result.items() if value != ''}


def unit_preview(unit):
    return {
        'bedrooms': unit.bedrooms,
        'bathrooms': _integer_bathrooms([unit]),
        'floor': unit.floor if unit.floor is not None and unit.floor >= 0 else None,
        'area_total': unit.internal_area_sqm,
        'area_land': unit.plot_size_sqm,
    }


def proposals(project, units):
    result = project_proposals(project)
    for target, source in [
        ('bedrooms', 'bedrooms'),
        ('floor', 'floor'),
        ('area_total', 'internal_area_sqm'),
        ('area_land', 'plot_size_sqm'),
    ]:
        values = {getattr(unit, source) for unit in units}
        if len(values) == 1 and None not in values:
            value = values.pop()
            if target != 'floor' or value >= 0:
                result[target] = value
    bathrooms = _integer_bathrooms(units)
    if bathrooms is not None:
        result['bathrooms'] = bathrooms
    return {key: value for key, value in result.items() if value != ''}


@transaction.atomic
def save_links(project_id, rows, *, reports=None, actor=None):
    project = ArealistingProject.objects.select_for_update().get(pk=project_id, is_deleted=False)
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
        raise ValidationError('Выберите от 1 до 100 карточек.')
    seen_properties, seen_units = set(), set()
    for row in rows:
        property_id = int(row['property'])
        unit_ids = {int(value) for value in row['units']}
        fields = set(row.get('fields', []))
        explicit_ownership = 'managed_fields' in row
        if explicit_ownership:
            requested_fields = row['managed_fields']
            original_fields = row.get('original_managed_fields')
            if (
                not isinstance(requested_fields, list)
                or not isinstance(original_fields, list)
                or any(not isinstance(field, str) for field in requested_fields + original_fields)
            ):
                raise ValidationError('Некорректный список полей под управлением AREALISTING.')
            managed_selection = set(requested_fields)
            original_selection = set(original_fields)
            if (managed_selection | original_selection) - FIELDS.keys() or fields - managed_selection:
                raise ValidationError('Недопустимые поля под управлением AREALISTING.')
        desired_active = row.get('is_active', None)
        expected_active = row.get('expected_is_active', None)
        if property_id in seen_properties or seen_units & unit_ids or not unit_ids:
            raise ValidationError('Карточки и юниты не должны повторяться; выберите юниты.')
        if fields - FIELDS.keys():
            raise ValidationError('Недопустимые поля обновления.')
        if desired_active is not None and not isinstance(desired_active, bool):
            raise ValidationError('Некорректное значение активности карточки.')
        if expected_active is not None and not isinstance(expected_active, bool):
            raise ValidationError('Некорректное исходное значение активности карточки.')
        seen_properties.add(property_id)
        seen_units.update(unit_ids)
        prop = Property.objects.select_for_update().get(pk=property_id)
        units = list(ArealistingUnit.objects.select_for_update().filter(pk__in=unit_ids, project=project, is_deleted=False))
        if len(units) != len(unit_ids):
            raise ValidationError('Юнит недоступен или относится к другому комплексу. Обновите экран.')
        group = ArealistingListingGroup.objects.select_for_update().filter(property=prop).first()
        if group and group.project_id != project.pk:
            raise ValidationError('Карточка уже связана с другим комплексом.')
        current_managed = set(group.source_owned_fields or []) & FIELDS.keys() if group else set()
        if explicit_ownership:
            if current_managed != original_selection:
                raise ValidationError(
                    'Поля под управлением AREALISTING изменились после открытия страницы. '
                    'Обновите страницу и повторите выбор.'
                )
            locked = set(group.locked_fields or []) if group else set()
            if any(
                field in locked or field.rsplit('_', 1)[0] in locked
                for field in managed_selection - current_managed
            ):
                raise ValidationError('Нельзя включить обновление защищённого поля.')
        if any(unit.listing_group_id and (not group or unit.listing_group_id != group.pk) for unit in units):
            raise ValidationError('Один из юнитов уже связан с другой группой. Обновите экран.')
        current_ids = set(group.units.values_list('pk', flat=True)) if group else set()
        if 'original_units' in row:
            if current_ids != {int(value) for value in row['original_units']}:
                raise ValidationError('Связь изменена после открытия страницы. Обновите страницу и повторите выбор.')
        elif group and current_ids != unit_ids:
            raise ValidationError('Обновите страницу перед изменением состава предложений.')
        if not group:
            group = ArealistingListingGroup.objects.create(
                property=prop, project=project, name=f'Undersun #{prop.pk}',
                grouping_mode='UNIT' if len(units) == 1 else 'LAYOUT',
            )
        if expected_active is not None and expected_active != prop.is_active:
            raise ValidationError(
                'Активность карточки изменена после открытия экрана. Обновите страницу.'
            )
        if (
            desired_active is not None
            and desired_active != prop.is_active
            and 'is_active' in group.locked_fields
        ):
            raise ValidationError('Активность карточки защищена от обновления.')
        changes = proposals(project, units)
        for field in fields:
            if field in group.locked_fields or field.rsplit('_', 1)[0] in group.locked_fields:
                raise ValidationError('Выбрано защищённое поле.')
            if field not in changes:
                raise ValidationError('Нет однозначного значения выбранного поля.')
            value = changes[field]
            if 'expected' in row:
                expected = row['expected'].get(field, {})
                if str(expected.get('before')) != str(getattr(prop, field)) or str(expected.get('after')) != str(value):
                    raise ValidationError('Данные изменились после открытия экрана. Обновите сравнение.')
            Property._meta.get_field(field).clean(value, prop)
        changed_fields = [
            {'field': field, 'before': getattr(prop, field), 'after': changes[field]}
            for field in FIELDS if field in fields and getattr(prop, field) != changes[field]
        ]
        unchanged_fields = [
            field for field in FIELDS
            if field in fields and getattr(prop, field) == changes[field]
        ]
        activity_change = None
        if desired_active is not None and desired_active != prop.is_active:
            activity_change = {'before': prop.is_active, 'after': desired_active}
        # Update only explicitly confirmed values; slug/SEO and other local fields stay untouched.
        updates = {field: changes[field] for field in fields}
        if desired_active is not None and desired_active != prop.is_active:
            updates['is_active'] = desired_active
        if updates:
            Property.objects.filter(pk=prop.pk).update(**updates)
        managed_fields = set(group.source_owned_fields or [])
        if explicit_ownership:
            managed_fields.difference_update(FIELDS)
            managed_fields.update(managed_selection)
        else:
            managed_fields.update(fields)
        managed_fields.update(PRICE_FIELDS)
        group.source_owned_fields = ordered_source_fields(managed_fields)
        managed_after = managed_fields & FIELDS.keys()
        not_applied = []
        for field in FIELDS:
            if field not in managed_after or field in fields:
                continue
            if field in group.locked_fields or field.rsplit('_', 1)[0] in group.locked_fields:
                reason = 'Поле защищено от обновления.'
            elif field not in changes:
                reason = unavailable_reason(project, units, field)
            else:
                reason = 'Изменение поля не было выбрано при сохранении.'
            not_applied.append({'field': field, 'reason': reason})
        group.units.exclude(pk__in=unit_ids).update(listing_group=None)
        ArealistingUnit.objects.filter(pk__in=unit_ids).update(listing_group=group)
        group.grouping_mode = 'UNIT' if len(unit_ids) == 1 else 'LAYOUT'
        group.save(update_fields=('grouping_mode', 'source_owned_fields', 'updated_at'))
        from .sync import ArealistingSyncService
        ArealistingSyncService.recalculate_listing_group(group)
        ArealistingManualProperty.objects.filter(property=prop).delete()
        ArealistingSkippedUnit.objects.filter(unit__in=units).delete()
        report = {
                'group_id': group.pk,
                'property_id': prop.pk,
                'title': str(prop),
                'changed_fields': changed_fields,
                'unchanged_fields': unchanged_fields,
                'managed_added': [field for field in FIELDS if field in managed_after - current_managed],
                'managed_removed': [field for field in FIELDS if field in current_managed - managed_after],
                'not_applied': not_applied,
                'unavailable_fields': [
                    {'field': field, 'reason': unavailable_reason(project, units, field)}
                    for field in FIELDS
                    if field not in changes and field not in managed_after
                ],
                'activity_change': activity_change,
        }
        if reports is not None:
            reports.append(report)
        if current_ids != unit_ids or changed_fields or managed_after != current_managed or activity_change:
            record_property_change(
                property_id=prop.pk, project_id=project.pk,
                kind='MATCH', actor=actor,
                details={
                    'units_before': sorted(current_ids),
                    'units_after': sorted(unit_ids),
                    'unit_labels_before': list(
                        ArealistingUnit.objects.filter(pk__in=current_ids)
                        .order_by('pk').values_list('external_id', flat=True)
                    ),
                    'unit_labels_after': [unit.external_id for unit in sorted(units, key=lambda item: item.pk)],
                    'changed_fields': changed_fields,
                    'managed_added': report['managed_added'],
                    'managed_removed': report['managed_removed'],
                    'activity_change': activity_change,
                },
            )
    return len(rows)
