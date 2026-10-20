"""Update existing linked sale offers only after a successful source pass."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.currency.services import CurrencyService
from apps.properties.models import Property
from ..models import ArealistingListingGroup, ArealistingPriceReview
from .history import record_property_change


PRICE_FIELDS = ('price_sale_thb', 'price_sale_usd', 'price_sale_rub')
ERROR_PREFIX = 'Цена AREALISTING: '


def money(value):
    if value is None:
        raise ValueError('нет курса валюты или цены')
    value = Decimal(str(value))
    if not value.is_finite() or value <= 0:
        raise ValueError('цена или курс должны быть положительными')
    value = value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if value <= 0:
        raise ValueError('цена после округления должна быть положительной')
    return value


def _current_price_proposal(group, prop):
    if prop.deal_type not in ('sale', 'both'):
        raise ValueError('карточка не предназначена для продажи')
    if set(PRICE_FIELDS) & set(group.locked_fields):
        raise ValueError('цена защищена от обновлений')
    if group.project.is_deleted:
        raise ValueError('комплекс недоступен')
    units = list(group.units.filter(is_deleted=False, availability_status='AVAILABLE').order_by('pk'))
    if not units:
        raise ValueError('нет доступных выбранных предложений')
    if any(not unit.sync_enabled or unit.project_id != group.project_id for unit in units):
        raise ValueError('обновление выбранного предложения отключено или комплекс изменился')
    snapshots = []
    for unit in units:
        thb = money(CurrencyService.convert_price(money(unit.price), unit.currency, 'THB'))
        snapshots.append({
            'id': unit.pk, 'number': unit.unit_number, 'external_id': unit.external_id,
            'source_price': str(unit.price), 'currency': unit.currency,
            'price_thb': str(thb),
        })
    thb = min(Decimal(item['price_thb']) for item in snapshots)
    values = {
        'price_sale_thb': thb,
        'price_sale_usd': money(CurrencyService.convert_price(thb, 'THB', 'USD')),
        'price_sale_rub': money(CurrencyService.convert_price(thb, 'THB', 'RUB')),
    }
    for field, value in values.items():
        Property._meta.get_field(field).clean(value, prop)
    return values, snapshots


def _supersede_pending(group):
    ArealistingPriceReview.objects.filter(
        group=group, status=ArealistingPriceReview.Status.PENDING,
    ).update(status=ArealistingPriceReview.Status.SUPERSEDED)


@transaction.atomic
def update_group_price(group_id, *, reports=None, sync_run=None):
    group = ArealistingListingGroup.objects.select_for_update().select_related('project').get(pk=group_id)
    if not group.property_id:
        return False
    prop = Property.objects.select_for_update().get(pk=group.property_id)
    before = {field: str(getattr(prop, field)) if getattr(prop, field) is not None else None for field in PRICE_FIELDS}
    report = {'project_id': group.project_id, 'property_id': prop.pk,
              'title': prop.title_ru or prop.title_en or prop.title,
              'checked_at': timezone.now().isoformat(), 'before': before, 'after': before.copy()}
    errors = [e for e in group.validation_errors if not str(e).startswith(ERROR_PREFIX)]
    try:
        values, snapshots = _current_price_proposal(group, prop)
    except (ValueError, InvalidOperation, ValidationError) as exc:
        _supersede_pending(group)
        reason = str(exc) if isinstance(exc, ValueError) else 'цена не соответствует допустимому формату или размеру'
        errors.append(ERROR_PREFIX + reason + '. Сохранена прежняя цена.')
        report.update(status='skipped', reason=reason)
        group.validation_errors = errors
        group.save(update_fields=('validation_errors', 'updated_at'))
        if reports is not None:
            reports.append(report)
        return False

    after = {field: str(value) for field, value in values.items()}
    pending = ArealistingPriceReview.objects.select_for_update().filter(
        group=group, status=ArealistingPriceReview.Status.PENDING,
    ).first()
    old_thb = Decimal(before['price_sale_thb']) if before['price_sale_thb'] is not None else None
    threshold = Decimal(str(settings.AREALISTING_PRICE_REVIEW_PERCENT))
    if threshold <= 0:
        raise ValueError('AREALISTING_PRICE_REVIEW_PERCENT must be positive.')
    percent = (abs(values['price_sale_thb'] - old_thb) / old_thb * 100) if old_thb and old_thb > 0 else Decimal('0')
    if before != after and old_thb and old_thb > 0 and percent >= threshold:
        if pending and pending.before == before and pending.after == after and pending.units == snapshots:
            review = pending
        else:
            if pending:
                pending.status = ArealistingPriceReview.Status.SUPERSEDED
                pending.save(update_fields=['status'])
            rejected = ArealistingPriceReview.objects.filter(
                group=group, status=ArealistingPriceReview.Status.REJECTED,
                before=before, after=after, units=snapshots,
            ).exists()
            if rejected:
                report.update(status='rejected', reason='Предложение цены ранее отклонено. Сохранена прежняя цена.')
                if reports is not None:
                    reports.append(report)
                group.validation_errors = errors
                group.save(update_fields=('validation_errors', 'updated_at'))
                return False
            review = ArealistingPriceReview.objects.create(
                group=group, project=group.project, property=prop, sync_run=sync_run,
                before=before, after=after, units=snapshots,
                change_percent=percent.quantize(Decimal('0.01')),
            )
        report.update(
            status='review', proposed=after, review_id=review.pk,
            change_percent=str(review.change_percent),
            reason=f'Цена изменилась на {review.change_percent}% — требуется подтверждение.',
        )
        group.validation_errors = errors
        group.save(update_fields=('validation_errors', 'updated_at'))
        if reports is not None:
            reports.append(report)
        return False

    if pending:
        pending.status = ArealistingPriceReview.Status.SUPERSEDED
        pending.save(update_fields=['status'])
    if before != after:
        Property.objects.filter(pk=prop.pk).update(**values)
        record_property_change(
            property_id=prop.pk, project_id=group.project_id,
            kind='PRICE', sync_run=sync_run,
            details={'changed_fields': [
                {'field': field, 'before': before[field], 'after': after[field]}
                for field in PRICE_FIELDS if before[field] != after[field]
            ]},
        )
    group.validation_errors = errors
    group.save(update_fields=('validation_errors', 'updated_at'))
    report.update(after=after, status='unchanged' if before == after else 'updated', reason='')
    if reports is not None:
        reports.append(report)
    return True


@transaction.atomic
def approve_price_review(review_id, *, user):
    original = ArealistingPriceReview.objects.get(pk=review_id)
    if not original.group_id:
        raise ValidationError('Связь с карточкой удалена. Подтверждение недоступно.')
    group = ArealistingListingGroup.objects.select_for_update().select_related('project').get(pk=original.group_id)
    if not group.property_id:
        raise ValidationError('Карточка больше не связана с AREALISTING.')
    prop = Property.objects.select_for_update().get(pk=group.property_id)
    review = ArealistingPriceReview.objects.select_for_update().get(pk=review_id)
    if review.status != ArealistingPriceReview.Status.PENDING or review.property_id != prop.pk:
        raise ValidationError('Это предложение цены больше не ожидает подтверждения.')
    try:
        values, snapshots = _current_price_proposal(group, prop)
    except (ValueError, InvalidOperation, ValidationError) as exc:
        raise ValidationError('Данные источника изменились. Обновите предложения и проверьте новую цену.') from exc
    before = {field: str(getattr(prop, field)) if getattr(prop, field) is not None else None for field in PRICE_FIELDS}
    after = {field: str(value) for field, value in values.items()}
    if before != review.before or after != review.after or snapshots != review.units:
        raise ValidationError('Цена, курс или выбранные предложения изменились. Обновите данные и проверьте новое предложение.')
    Property.objects.filter(pk=prop.pk).update(**values)
    review.status = ArealistingPriceReview.Status.APPROVED
    review.reviewed_by = user
    review.reviewed_at = timezone.now()
    review.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
    record_property_change(
        property_id=prop.pk, project_id=group.project_id, kind='PRICE',
        actor=user, sync_run=review.sync_run,
        details={'review_id': review.pk, 'changed_fields': [
            {'field': field, 'before': before[field], 'after': after[field]}
            for field in PRICE_FIELDS if before[field] != after[field]
        ]},
    )
    return review


@transaction.atomic
def reject_price_review(review_id, *, user):
    review = ArealistingPriceReview.objects.select_for_update().get(pk=review_id)
    if review.status != ArealistingPriceReview.Status.PENDING:
        raise ValidationError('Это предложение цены больше не ожидает решения.')
    review.status = ArealistingPriceReview.Status.REJECTED
    review.reviewed_by = user
    review.reviewed_at = timezone.now()
    review.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
    return review
