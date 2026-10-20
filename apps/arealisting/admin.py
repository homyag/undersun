from django.contrib import admin, messages
from django import forms
from django.conf import settings
from django.db.models import Case, Count, IntegerField, Q, Value, When
import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from urllib.parse import urlencode
from urllib.parse import urlsplit

from .exceptions import ArealistingError
from .models import (
    ArealistingAsset,
    ArealistingListingGroup,
    ArealistingManualProperty,
    ArealistingLocationMapping,
    ArealistingPaymentPlan,
    ArealistingProject,
    ArealistingPriceReview,
    ArealistingPropertyChange,
    ArealistingPropertyAsset,
    ArealistingMediaJob,
    ArealistingSkippedUnit,
    ArealistingSyncRun,
    ArealistingSyncJob,
    ArealistingSyncEvent,
    ArealistingSyncState,
    ArealistingUnit,
)
from .services.sync import ArealistingSyncService
from .services.sync_jobs import queue_sync_job, recover_stale_sync_jobs, start_sync_worker
from .services.matching import (FIELDS, PROJECT_FIELD_KEYS, project_proposals,
                                proposals, unavailable_reason, save_links, unit_preview)
from .services.drafts import create_draft, preview_draft, restore_units, skip_units
from .services.field_ownership import SOURCE_FIELD_LABELS, ordered_source_fields
from .services.history import record_property_change
from .services.readiness import publication_readiness
from .services.pricing import approve_price_review, reject_price_review
from apps.properties.models import Property, PropertyImage

UNIT_REVIEW_LABELS = {
    'bedrooms': 'Спальни', 'bathrooms': 'Ванные', 'floor': 'Этаж',
    'internal_area_sqm': 'Площадь, м²', 'plot_size_sqm': 'Участок, м²',
    'sea_view': 'Вид на море', 'property_type': 'Тип недвижимости',
    'furnishing': 'Меблировка',
}
UNIT_TO_PROPERTY_FIELD = {
    'bedrooms': 'bedrooms',
    'bathrooms': 'bathrooms',
    'floor': 'floor',
    'internal_area_sqm': 'area_total',
    'plot_size_sqm': 'area_land',
}


def _matching_action(request, project_id):
    required = ('arealisting.view_arealistingproject', 'arealisting.change_arealistingunit',
                'arealisting.add_arealistinglistinggroup',
                'arealisting.change_arealistinglistinggroup', 'properties.change_property')
    if project_id and request.user.has_perms(required):
        return {'label': 'Проверить выбранные предложения',
                'url': f"{reverse('admin:arealisting_matching')}?{urlencode({'project': project_id})}"}
    return None


def _group_action(request, group, label='Настроить связь и защиту полей'):
    if group and request.user.has_perm('arealisting.view_arealistinglistinggroup'):
        return {'label': label, 'url': reverse(
            'admin:arealisting_arealistinglistinggroup_change', args=[group.pk],
        )}
    return None


def _issue_guidance(reason, *, group, request):
    """Explain a stored skip/error with a destination allowed by the user's permissions."""
    raw = str(reason or '').strip()
    normalized = raw.removeprefix('Цена AREALISTING: ').removeprefix('Поля AREALISTING: ')
    lower = normalized.lower()
    action = _group_action(request, group)
    if 'mixed_unit_currencies' in lower:
        return {'reason': 'У выбранных предложений разные валюты.',
                'next_step': 'Проверьте состав предложений и их валюты.',
                'action': _matching_action(request, group.project_id if group else None) or action,
                'intentional': False}
    if 'защищен' in lower or 'защищён' in lower:
        active_lock = bool(group and set(group.locked_fields or []) &
                           {'price_sale_thb', 'price_sale_usd', 'price_sale_rub'})
        return {'reason': 'Цена карточки защищена от обновления AREALISTING.',
                'next_step': ('Если это намеренно, действий не требуется. Чтобы снова обновлять цену, снимите защиту.'
                              if active_lock else 'Защита уже снята. Запустите синхронизацию, чтобы проверить цену снова.'),
                'action': _group_action(request, group, 'Проверить защиту цены'),
                'intentional': active_lock}
    if 'нет доступных выбранных предложений' in lower or 'нет связанных актуальных предложений' in lower:
        return {'reason': 'Для карточки нет доступных выбранных предложений.',
                'next_step': 'Проверьте связь и статусы предложений.',
                'action': _matching_action(request, group.project_id if group else None) or action,
                'intentional': False}
    if 'нет курса валюты или цены' in lower:
        missing_source = bool(group and group.units.filter(
            is_deleted=False, availability_status=ArealistingUnit.AvailabilityStatus.AVAILABLE,
        ).filter(Q(price__isnull=True) | Q(price__lte=0) | Q(currency='')).exists())
        if missing_source:
            return {'reason': 'У одного из предложений нет положительной цены или валюты.',
                    'next_step': 'Проверьте исходные предложения AREALISTING.',
                    'action': _matching_action(request, group.project_id if group else None) or action,
                    'intentional': False}
        rates_action = ({'label': 'Проверить курсы валют',
                         'url': reverse('admin:currency_exchangerate_changelist')}
                        if request.user.has_perm('currency.view_exchangerate') else None)
        return {'reason': 'Не удалось пересчитать цену между валютами.',
                'next_step': 'Проверьте активные валюты и курсы для THB, USD и RUB.',
                'action': rates_action or action, 'intentional': False}
    if 'не предназначена для продажи' in lower:
        prop_action = ({'label': 'Проверить тип сделки',
                        'url': reverse('admin:properties_property_change', args=[group.property_id])}
                       if group and group.property_id and request.user.has_perm('properties.change_property') else None)
        return {'reason': 'Карточка не предназначена для продажи.',
                'next_step': 'Проверьте тип сделки в карточке.',
                'action': prop_action or action, 'intentional': False}
    if 'обновление выбранного предложения отключено' in lower:
        return {'reason': 'Синхронизация одного из выбранных предложений отключена или изменилась его связь.',
                'next_step': 'Проверьте состав связи и настройки предложений.',
                'action': _matching_action(request, group.project_id if group else None) or action,
                'intentional': False}
    if 'комплекс' in lower and ('недоступен' in lower or 'удалён' in lower):
        return {'reason': 'Комплекс больше не доступен в AREALISTING.',
                'next_step': 'Проверьте связь карточки с комплексом.',
                'action': action, 'intentional': False}
    return {'reason': normalized or 'Причина не указана.',
            'next_step': 'Проверьте группу и данные карточки.',
            'action': action, 'intentional': False}


def _unit_field_comparison(event, group, *, can_lock=False, request=None, proposed_values=None, units=None):
    """Compare one source snapshot with the current card without implying an automatic update."""
    rows = []
    linked = bool(group and event.unit_id and event.unit.listing_group_id == group.pk
                  and event.project_id == group.project_id)
    for item in (event.details or {}).get('changed_fields', []):
        source_field = item.get('field')
        target_field = UNIT_TO_PROPERTY_FIELD.get(source_field)
        current = getattr(group.property, target_field) if group and target_field else None
        source_current = getattr(event.unit, source_field, None) if event.unit_id else None
        source_is_current = str(source_current) == str(item.get('after'))
        if not target_field:
            status = 'Не переносится в карточку автоматически'
        elif not linked:
            status = 'Предложение больше не связано с этой карточкой'
        elif not source_is_current:
            status = 'Источник изменился снова; проверьте последнее событие'
        elif target_field in (group.locked_fields or []):
            status = 'Защищено от обновления'
        elif target_field in (group.source_owned_fields or []) and target_field not in (proposed_values or {}):
            status = ('Не обновилось: ' + unavailable_reason(group.project, units, target_field)
                      if units else 'Не обновилось: нет выбранных предложений')
        elif target_field in (group.source_owned_fields or []):
            status = 'Под управлением AREALISTING'
        else:
            status = 'Не обновилось: поле не выбрано для переноса в карточку'
        rows.append({
            'source_field': source_field,
            'label': UNIT_REVIEW_LABELS.get(source_field, source_field or 'Поле'),
            'before': item.get('before'), 'after': item.get('after'),
            'card_value': current, 'has_card_field': bool(target_field and group),
            'status': status,
            'action': (_group_action(request, group, 'Проверить защиту поля')
                       if request and group and target_field in (group.locked_fields or []) else
                       _matching_action(request, group.project_id)
                       if request and group and target_field and linked
                       and (target_field not in (proposed_values or {})
                            or target_field not in (group.source_owned_fields or [])) else None),
            'can_lock': bool(can_lock and linked and source_is_current and target_field
                             and target_field in (group.source_owned_fields or [])
                             and target_field not in (group.locked_fields or [])),
            'expected_card_value': str(current),
            'expected_source_value': str(item.get('after')),
        })
    return rows


def _source_navigation_params(data):
    """Keep the user's place in the unlinked-property queue."""
    state = 'manual' if data.get('source_state') == 'manual' else 'pending'
    activity = data.get('source_activity', 'all')
    if activity not in ('all', 'active', 'inactive'):
        activity = 'all'
    page = data.get('source_page', '')
    return {
        'source_state': state,
        'source_activity': activity,
        'source_q': data.get('source_q', '').strip()[:200],
        'source_page': page if str(page).isdigit() else '',
        'source_project_q': data.get('source_project_q', '').strip()[:200],
    }


def _unlinked_back_url(property_id, source):
    params = {
        'property': property_id,
        'state': source['source_state'],
        'activity': source['source_activity'],
    }
    if source['source_q']:
        params['q'] = source['source_q']
    if source['source_page']:
        params['page'] = source['source_page']
    if source['source_project_q']:
        params['project_q'] = source['source_project_q']
    return f"{reverse('admin:arealisting_unlinked')}?{urlencode(params)}"


def _workspace_back_url(project_id, data):
    params = {}
    query = data.get('return_q', '').strip()[:200]
    page = data.get('return_page', '')
    if query:
        params['q'] = query
    if str(page).isdigit():
        params['page'] = page
    destination = reverse('admin:arealisting_arealistingproject_changelist')
    if params:
        destination += f'?{urlencode(params)}'
    return f'{destination}#project-{project_id}'


def price_report_context(project):
    run = ArealistingSyncRun.objects.filter(
        summary__price_updates__contains=[{'project_id': project.pk}],
    ).order_by('-started_at').first()
    if not run:
        return {}
    rows = []
    for row in run.summary.get('price_updates', []):
        if row.get('project_id') != project.pk:
            continue
        rows.append({**row, 'checked_at': parse_datetime(row['checked_at']),
                     'url': reverse('admin:properties_property_change', args=[row['property_id']]),
                     'review_url': (reverse('admin:arealisting_arealistingpricereview_review', args=[row['review_id']])
                                    if row.get('review_id') else ''),
                     'prices': [{'currency': currency, 'before': row['before'].get(field),
                                 'after': row.get('proposed', row['after']).get(field)}
                                for field, currency in [('price_sale_thb', 'THB'), ('price_sale_usd', 'USD'), ('price_sale_rub', 'RUB')]]})
    return {'price_report': rows, 'price_report_run': run}


def _format_summary(summary):
    parts = []
    for resource, stats in summary.items():
        if resource == 'price_updates':
            continue
        parts.append(
            f'{resource}: seen={stats["seen"]}, created={stats["created"]}, '
            f'updated={stats["updated"]}, deleted={stats["deleted"]}, '
            f'errors={stats["errors"]}'
        )
    return '; '.join(parts)


def _sync_event_detail(event):
    details = event.details or {}
    reason = details.get('reason')
    if reason:
        return reason
    if event.kind == ArealistingSyncEvent.Kind.UNIT_PRICE:
        before, after = details.get('before') or {}, details.get('after') or {}
        return f"{before.get('price') or '—'} {before.get('currency') or ''} → {after.get('price') or '—'} {after.get('currency') or ''}"
    if event.kind == ArealistingSyncEvent.Kind.CARD_PRICE:
        before, after = details.get('before') or {}, details.get('after') or {}
        return f"{before.get('price_sale_thb') or '—'} → {after.get('price_sale_thb') or '—'} THB"
    if event.kind == ArealistingSyncEvent.Kind.UNIT_FIELDS:
        return 'Изменились: ' + ', '.join(
            UNIT_REVIEW_LABELS.get(item.get('field'), item.get('field', 'поле'))
            for item in details.get('changed_fields', [])
        )
    unit_label = details.get('unit_number') or details.get('unit_external_id')
    return f'Предложение {unit_label}' if unit_label else ''


def dashboard_context(request):
    """Build a concise operational snapshot for the integration workspace."""
    recover_stale_sync_jobs()
    latest_run = ArealistingSyncRun.objects.filter(
        status=ArealistingSyncRun.Status.SUCCESS,
    ).first()
    latest_attempt = ArealistingSyncRun.objects.first()
    latest_sync_job = ArealistingSyncJob.objects.first()
    sync_lock = ArealistingSyncState.objects.filter(key=ArealistingSyncService.LOCK_KEY).first()
    summary = latest_run.summary if latest_run and isinstance(latest_run.summary, dict) else {}
    unit_stats = summary.get('units') if isinstance(summary.get('units'), dict) else {}
    project_stats = (
        summary.get('projects') if isinstance(summary.get('projects'), dict) else {}
    )
    price_updates = summary.get('price_updates')
    if not isinstance(price_updates, list):
        price_updates = []
    sync_events = []
    sync_event_count = 0
    if latest_run and request.user.has_perm('arealisting.view_arealistingsyncevent'):
        events = ArealistingSyncEvent.objects.filter(run=latest_run)
        sync_event_count = events.count()
        priority = Case(
            When(kind=ArealistingSyncEvent.Kind.PRICE_REVIEW, then=Value(0)),
            When(kind=ArealistingSyncEvent.Kind.ACTIVE_WITHOUT_UNITS, then=Value(0)),
            When(kind=ArealistingSyncEvent.Kind.PRICE_SKIPPED, then=Value(1)),
            When(kind=ArealistingSyncEvent.Kind.SOLD, then=Value(2)),
            When(kind=ArealistingSyncEvent.Kind.UNIT_PRICE, then=Value(3)),
            When(kind=ArealistingSyncEvent.Kind.NEW_UNIT, then=Value(4)),
            default=Value(5), output_field=IntegerField(),
        )
        for event in events.select_related('project', 'unit', 'property').annotate(
            _priority=priority,
        ).order_by('_priority', '-pk')[:8]:
            if (event.kind == ArealistingSyncEvent.Kind.PRICE_REVIEW
                    and event.details.get('review_id')
                    and request.user.has_perm('arealisting.view_arealistingpricereview')):
                url = reverse('admin:arealisting_arealistingpricereview_review',
                              args=[event.details['review_id']])
                action = 'Проверить цену'
            elif event.property_id and request.user.has_perm('properties.change_property'):
                url = reverse('admin:properties_property_change', args=[event.property_id])
                action = 'Проверить карточку'
            elif event.project_id and request.user.has_perms((
                'arealisting.view_arealistingproject', 'arealisting.change_arealistingunit',
                'arealisting.add_arealistinglistinggroup', 'arealisting.change_arealistinglistinggroup',
                'properties.change_property',
            )):
                url = f"{reverse('admin:arealisting_matching')}?{urlencode({'project': event.project_id})}"
                action = 'Открыть предложения'
            else:
                url = reverse('admin:arealisting_arealistingsyncevent_change', args=[event.pk])
                action = 'Посмотреть событие'
            label = (event.property.title_ru or event.property.title_en or str(event.property)) if event.property else str(event.project or 'AREALISTING')
            detail = _sync_event_detail(event)
            sync_events.append({'kind': event.get_kind_display(), 'title': label,
                                'detail': detail, 'url': url, 'action': action})

    units = ArealistingUnit.objects.filter(is_deleted=False).aggregate(
        available=Count(
            'id',
            filter=Q(
                availability_status=ArealistingUnit.AvailabilityStatus.AVAILABLE,
            ),
        ),
        sold=Count(
            'id',
            filter=Q(availability_status=ArealistingUnit.AvailabilityStatus.SOLD),
        ),
    )
    unlinked = Property.objects.filter(arealisting_group__isnull=True).aggregate(
        pending=Count('id', filter=Q(arealisting_manual__isnull=True)),
        manual=Count('id', filter=Q(arealisting_manual__isnull=False)),
    )
    mapping_required = ArealistingLocationMapping.objects.filter(
        Q(is_confirmed=False)
        | Q(mapping_mode=ArealistingLocationMapping.MappingMode.UNMAPPED),
        is_deleted=False,
    ).count()
    asset_errors = ArealistingAsset.objects.filter(
        is_active=True,
    ).exclude(last_error='').count()

    work_items = []
    pending_price_reviews = []
    pending_price_review_count = 0
    if request.user.has_perm('arealisting.view_arealistingpricereview'):
        pending = ArealistingPriceReview.objects.filter(status=ArealistingPriceReview.Status.PENDING)
        pending_price_review_count = pending.count()
        pending_price_reviews = list(pending.select_related('property', 'project').order_by('-created_at')[:6])
    if request.user.has_perm('properties.change_property'):
        pending_properties = (
            Property.objects.filter(
                arealisting_group__isnull=True,
                arealisting_manual__isnull=True,
            ).order_by('-is_active', 'pk')[:4]
        )
        for prop in pending_properties:
            work_items.append({
                'kind': 'Карточка без связи',
                'title': str(prop),
                'detail': f'#{prop.pk} · {"Активна" if prop.is_active else "Неактивна"}',
                'url': f"{reverse('admin:arealisting_unlinked')}?{urlencode({'property': prop.pk})}",
                'action': 'Подобрать комплекс',
            })
        drafts = (
            ArealistingListingGroup.objects.filter(
                catalog_origin=ArealistingListingGroup.CatalogOrigin.AREALISTING_DRAFT,
                property__isnull=False,
                property__is_active=False,
            ).select_related('property', 'project').order_by('created_at')[:4]
        )
        for group in drafts:
            can_check = request.user.has_perm('arealisting.view_arealistinglistinggroup')
            work_items.append({
                'kind': 'Черновик',
                'title': str(group.property),
                'detail': f'{group.project} · #{group.property_id}',
                'url': (reverse('admin:arealisting_arealistinglistinggroup_readiness', args=[group.pk])
                        if can_check else reverse('admin:properties_property_change', args=[group.property_id])),
                'action': 'Проверить перед публикацией' if can_check else 'Проверить карточку',
            })
    if request.user.has_perm('arealisting.change_arealistinglocationmapping'):
        mappings = (
            ArealistingLocationMapping.objects.filter(
                Q(is_confirmed=False)
                | Q(mapping_mode=ArealistingLocationMapping.MappingMode.UNMAPPED),
                is_deleted=False,
            ).order_by('pk')[:4]
        )
        for mapping in mappings:
            work_items.append({
                'kind': 'Локация',
                'title': mapping.source_name or mapping.external_id,
                'detail': mapping.source_type or mapping.external_id,
                'url': reverse('admin:arealisting_arealistinglocationmapping_change', args=[mapping.pk]),
                'action': 'Сопоставить локацию',
            })
    if request.user.has_perm('arealisting.view_arealistingasset'):
        broken_assets = (
            ArealistingAsset.objects.filter(is_active=True)
            .exclude(last_error='')
            .select_related('project', 'unit').order_by('-updated_at')[:4]
        )
        for asset in broken_assets:
            work_items.append({
                'kind': 'Материал',
                'title': str(asset.project) if asset.project_id else asset.source_key,
                'detail': asset.last_error[:140],
                'url': reverse('admin:arealisting_arealistingasset_change', args=[asset.pk]),
                'action': 'Посмотреть ошибку',
            })

    latest_error = None
    if latest_attempt and latest_attempt.status == ArealistingSyncRun.Status.FAILED:
        latest_error = latest_attempt.error or 'Синхронизация завершилась с ошибкой.'

    return {
        'latest_successful_run': latest_run,
        'latest_sync_error': latest_error,
        'latest_sync_job': latest_sync_job,
        'sync_running': bool(
            (sync_lock and sync_lock.status == ArealistingSyncState.Status.RUNNING
             and sync_lock.current_started_at
             and sync_lock.current_started_at >= timezone.now() - ArealistingSyncService.LOCK_STALE_AFTER)
            or (latest_attempt and latest_attempt.status == ArealistingSyncRun.Status.RUNNING
                and latest_attempt.started_at >= timezone.now() - ArealistingSyncService.LOCK_STALE_AFTER)
            or (latest_sync_job and latest_sync_job.status in (
                ArealistingSyncJob.Status.PENDING, ArealistingSyncJob.Status.RUNNING,
            ))
        ),
        'recent_changes': {
            'new_projects': project_stats.get('created', 0),
            'new_available_units': unit_stats.get('available_created', 0),
            'price_changed': unit_stats.get('price_changed', 0),
            'became_sold': unit_stats.get('became_sold', 0),
            'property_prices_updated': sum(
                row.get('status') == 'updated'
                for row in price_updates
                if isinstance(row, dict)
            ),
        },
        'source_totals': {
            'projects': ArealistingProject.objects.filter(is_deleted=False).count(),
            'available_units': units['available'],
            'sold_units': units['sold'],
            'linked_properties': ArealistingListingGroup.objects.filter(
                property__isnull=False,
            ).count(),
        },
        'attention': {
            'mapping_required': mapping_required,
            'asset_errors': asset_errors,
            'unlinked_pending': unlinked['pending'],
            'manual_properties': unlinked['manual'],
        },
        'work_items': work_items,
        'pending_price_reviews': pending_price_reviews,
        'pending_price_review_count': pending_price_review_count,
        'price_review_percent': settings.AREALISTING_PRICE_REVIEW_PERCENT,
        'price_reviews_url': reverse('admin:arealisting_arealistingpricereview_changelist'),
        'can_view_price_reviews': request.user.has_perm('arealisting.view_arealistingpricereview'),
        'sync_events': sync_events,
        'sync_event_count': sync_event_count,
        'sync_events_url': (
            f"{reverse('admin:arealisting_arealistingsyncevent_changelist')}?run={latest_run.pk}"
            if latest_run else ''
        ),
        'can_view_sync_events': request.user.has_perm('arealisting.view_arealistingsyncevent'),
        'dashboard_links': {
            'runs': reverse('admin:arealisting_arealistingsyncrun_changelist'),
            'groups': reverse('admin:arealisting_arealistinglistinggroup_changelist'),
            'mappings': reverse(
                'admin:arealisting_arealistinglocationmapping_changelist'
            ),
            'assets': reverse('admin:arealisting_arealistingasset_changelist'),
            'unlinked': reverse('admin:arealisting_unlinked'),
        },
        'can_view_runs': request.user.has_perm('arealisting.view_arealistingsyncrun'),
        'can_view_groups': request.user.has_perm('arealisting.view_arealistinglistinggroup'),
        'can_view_mappings': request.user.has_perm(
            'arealisting.view_arealistinglocationmapping'
        ),
        'can_view_assets': request.user.has_perm('arealisting.view_arealistingasset'),
        'can_view_unlinked': request.user.has_perm('properties.change_property'),
        'review_queue_url': reverse('admin:arealisting_review_queue'),
        'review_queue_count': (
            ArealistingSyncEvent.objects.filter(reviewed_at__isnull=True)
            .exclude(kind=ArealistingSyncEvent.Kind.PRICE_REVIEW).count()
            if request.user.has_perm('arealisting.view_arealistingsyncevent') else 0
        ),
        'can_view_review_queue': request.user.has_perm('arealisting.view_arealistingsyncevent'),
    }


class InternalAdminMixin:
    """Keep direct admin URLs and permissions, but omit secondary menu entries."""

    def get_model_perms(self, request):
        return {}


class SourceReadOnlyAdmin(InternalAdminMixin, admin.ModelAdmin):
    """Prevent accidental edits to source-owned records."""

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ArealistingProject)
class ArealistingProjectAdmin(SourceReadOnlyAdmin):
    change_list_template = 'admin/arealisting/arealistingproject/change_list.html'

    def get_model_perms(self, request):
        return admin.ModelAdmin.get_model_perms(self, request)

    def changelist_view(self, request, extra_context=None):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        sections = []
        for model, label in (
            (ArealistingUnit, 'Юниты'),
            (ArealistingListingGroup, 'Связи с карточками'),
            (ArealistingLocationMapping, 'Настройка локаций'),
            (ArealistingPaymentPlan, 'Планы оплаты'),
            (ArealistingAsset, 'Материалы'),
            (ArealistingSkippedUnit, 'Пропущенные предложения'),
            (ArealistingSyncRun, 'История обновлений'),
            (ArealistingSyncEvent, 'События синхронизации'),
            (ArealistingPropertyChange, 'Изменения карточек'),
            (ArealistingPriceReview, 'Проверка изменений цен'),
            (ArealistingSyncState, 'Состояние синхронизации'),
        ):
            model_admin = self.admin_site._registry[model]
            if model_admin.has_view_or_change_permission(request):
                sections.append({'label': label, 'url': reverse(
                    f'admin:{model._meta.app_label}_{model._meta.model_name}_changelist'
                )})
        query = request.GET.get('q', '').strip()
        projects = self.get_queryset(request).filter(is_deleted=False)
        if query:
            projects = projects.filter(Q(name_ru__icontains=query) | Q(name_en__icontains=query) | Q(developer_name__icontains=query))
        page = Paginator(projects.order_by('name_en', 'pk'), 24).get_page(request.GET.get('page'))
        cards = []
        for project in page:
            cards.append({'project': project, 'location': self.source_locations(project),
                          'available': project._available_units, 'sold': project._sold_units,
                          'loaded': project.units.exists(),
                          'linked': project.listing_groups.filter(property__isnull=False).count(),
                          'photo': next((url for url in project.gallery if isinstance(url, str) and url.startswith('https://')), '')})
        return TemplateResponse(request, 'admin/arealisting/workspace.html', {
            **self.admin_site.each_context(request), **(extra_context or {}),
            **dashboard_context(request),
            'title': 'Обновление карточек из AREALISTING', 'opts': self.model._meta,
            'arealisting_sections': sections, 'cards': cards, 'page': page, 'query': query,
            'can_sync': self.has_change_permission(request),
            'can_load': self.has_change_permission(request) and request.user.has_perm('arealisting.change_arealistingunit'),
        })
    list_display = (
        'display_name',
        'developer_name',
        'project_type',
        'construction_status',
        'source_locations',
        'available_units',
        'sold_units',
        'location_mapping_ready',
        'synced_at',
        'is_deleted',
    )
    list_filter = ('project_type', 'construction_status', 'is_deleted')
    search_fields = (
        'external_id',
        'name_en',
        'name_ru',
        'developer_name',
    )
    actions = ('sync_selected_projects', 'sync_selected_inventory')
    readonly_fields = tuple(field.name for field in ArealistingProject._meta.fields)
    fieldsets = (
        ('Проект', {
            'fields': (
                'external_id',
                'name_en',
                'name_ru',
                'developer_name',
                'project_type',
                'construction_status',
                'completion_date',
                'is_deleted',
            )
        }),
        ('Описание', {'fields': ('description_en', 'description_ru')}),
        ('Владение и платежи', {
            'fields': (
                'freehold_available',
                'leasehold_available',
                'maintenance_fee',
                'maintenance_fee_mode',
                'sinking_fund',
                'sinking_fund_mode',
            )
        }),
        ('География', {'fields': ('latitude', 'longitude', 'districts')}),
        ('Материалы', {'fields': ('amenities', 'gallery', 'documents')}),
        ('Синхронизация', {
            'classes': ('collapse',),
            'fields': (
                'remote_updated_at',
                'last_seen_at',
                'synced_at',
                'raw_payload',
            ),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _available_units=Count(
                'units',
                filter=Q(
                    units__availability_status=ArealistingUnit.AvailabilityStatus.AVAILABLE,
                    units__is_deleted=False,
                ),
            ),
            _sold_units=Count(
                'units',
                filter=Q(
                    units__availability_status=ArealistingUnit.AvailabilityStatus.SOLD,
                    units__is_deleted=False,
                ),
            ),
        )

    def get_urls(self):
        custom_urls = [
            path('review-queue/', self.admin_site.admin_view(self.review_queue_view), name='arealisting_review_queue'),
            path('review-queue/<int:event_id>/checked/', self.admin_site.admin_view(self.review_event_view),
                 name='arealisting_review_event'),
            path('review-queue/<int:event_id>/keep-card-value/', self.admin_site.admin_view(self.keep_card_value_view),
                 name='arealisting_keep_card_value'),
            path('unlinked/', self.admin_site.admin_view(self.unlinked_view), name='arealisting_unlinked'),
            path('unlinked/<int:property_id>/manual/', self.admin_site.admin_view(self.manual_property_view), name='arealisting_manual_property'),
            path('unlinked/<int:property_id>/detach/', self.admin_site.admin_view(self.detach_property_view), name='arealisting_detach_property'),
            path('<int:project_id>/load/', self.admin_site.admin_view(self.load_inventory_view), name='arealisting_load_inventory'),
            path('matching/', self.admin_site.admin_view(self.matching_view), name='arealisting_matching'),
            path(
                'sync-projects/',
                self.admin_site.admin_view(self.sync_projects_view),
                name='arealisting_arealistingproject_sync_projects',
            ),
        ]
        return custom_urls + super().get_urls()

    def review_queue_view(self, request):
        if not request.user.has_perm('arealisting.view_arealistingsyncevent'):
            raise PermissionDenied
        state = 'checked' if request.GET.get('state') == 'checked' else 'open'
        kind = request.GET.get('kind', '')
        allowed_kinds = {value for value, _label in ArealistingSyncEvent.Kind.choices}
        events = ArealistingSyncEvent.objects.exclude(kind=ArealistingSyncEvent.Kind.PRICE_REVIEW)
        if state == 'open':
            events = events.filter(reviewed_at__isnull=True)
        else:
            events = events.filter(reviewed_at__isnull=False)
        if kind in allowed_kinds and kind != ArealistingSyncEvent.Kind.PRICE_REVIEW:
            events = events.filter(kind=kind)
        else:
            kind = ''
        events = events.select_related('project', 'unit', 'property', 'reviewed_by').order_by('-created_at', '-pk')
        page = Paginator(events, 30).get_page(request.GET.get('page'))
        groups_by_property = {
            group.property_id: group
            for group in ArealistingListingGroup.objects.filter(
                property_id__in=[event.property_id for event in page if event.property_id],
            ).select_related('property', 'project').prefetch_related('units')
        }
        group_unit_data = {}
        for group in groups_by_property.values():
            units = [unit for unit in group.units.all() if not unit.is_deleted]
            group_unit_data[group.pk] = {
                'units': units,
                'proposed': proposals(group.project, units) if units else {},
            }
        can_lock = request.user.has_perms((
            'arealisting.change_arealistinglistinggroup',
            'arealisting.change_arealistingsyncevent',
            'properties.change_property',
        ))
        rows = []
        for event in page:
            group = groups_by_property.get(event.property_id)
            if event.property_id and request.user.has_perm('properties.change_property'):
                action_url = reverse('admin:properties_property_change', args=[event.property_id])
                action = 'Открыть карточку'
            elif event.project_id and request.user.has_perm('arealisting.view_arealistingproject'):
                action_url = reverse('admin:arealisting_arealistingproject_change', args=[event.project_id])
                action = 'Открыть комплекс'
            else:
                action_url = reverse('admin:arealisting_arealistingsyncevent_change', args=[event.pk])
                action = 'Посмотреть событие'
            field_changes = (
                _unit_field_comparison(
                    event, group, can_lock=can_lock, request=request,
                    proposed_values=group_unit_data.get(group.pk, {}).get('proposed') if group else None,
                    units=group_unit_data.get(group.pk, {}).get('units') if group else None,
                )
                if event.kind == ArealistingSyncEvent.Kind.UNIT_FIELDS else []
            )
            guidance = None
            if event.kind == ArealistingSyncEvent.Kind.PRICE_SKIPPED:
                current_error = next((error for error in (group.validation_errors or [])
                                      if str(error).startswith('Цена AREALISTING: ')), None) if group else None
                guidance = _issue_guidance(current_error or (event.details or {}).get('reason'),
                                           group=group, request=request)
                guidance['is_current'] = bool(current_error)
                if not current_error:
                    guidance['next_step'] = 'Причина больше не числится в замечаниях группы. Проверьте итог следующей синхронизации.'
            elif event.kind == ArealistingSyncEvent.Kind.ACTIVE_WITHOUT_UNITS:
                guidance = _issue_guidance('нет доступных выбранных предложений', group=group, request=request)
                guidance['is_current'] = bool(group and group.available_units_count == 0
                                               and group.property and group.property.is_active)
            rows.append({'event': event, 'detail': _sync_event_detail(event),
                         'field_changes': field_changes, 'guidance': guidance,
                         'url': action_url, 'action': action})
        pending_reviews = []
        if request.user.has_perm('arealisting.view_arealistingpricereview'):
            pending_reviews = list(ArealistingPriceReview.objects.filter(
                status=ArealistingPriceReview.Status.PENDING,
            ).select_related('property', 'project').order_by('-created_at')[:20])
        group_errors = []
        if request.user.has_perm('arealisting.view_arealistinglistinggroup'):
            groups_with_errors = list(ArealistingListingGroup.objects.exclude(
                validation_errors=[],
            ).filter(property__isnull=False).select_related('property', 'project').order_by('-updated_at')[:20])
            group_errors = [
                {'group': group,
                 'issues': [_issue_guidance(error, group=group, request=request)
                            for error in group.validation_errors or []]}
                for group in groups_with_errors
            ]
        return TemplateResponse(request, 'admin/arealisting/review_queue.html', {
            **self.admin_site.each_context(request),
            'title': 'Проверка изменений AREALISTING', 'opts': self.model._meta,
            'rows': rows, 'page': page, 'state': state, 'kind': kind,
            'kinds': [(value, label) for value, label in ArealistingSyncEvent.Kind.choices
                      if value != ArealistingSyncEvent.Kind.PRICE_REVIEW],
            'pending_reviews': pending_reviews, 'group_errors': group_errors,
            'can_mark_checked': request.user.has_perm('arealisting.change_arealistingsyncevent'),
        })

    @method_decorator(require_POST)
    def review_event_view(self, request, event_id):
        if not request.user.has_perm('arealisting.change_arealistingsyncevent'):
            raise PermissionDenied
        event = get_object_or_404(ArealistingSyncEvent, pk=event_id)
        if event.kind == ArealistingSyncEvent.Kind.PRICE_REVIEW:
            raise PermissionDenied
        ArealistingSyncEvent.objects.filter(pk=event.pk, reviewed_at__isnull=True).update(
            reviewed_at=timezone.now(), reviewed_by=request.user,
        )
        return HttpResponseRedirect(reverse('admin:arealisting_review_queue'))

    @method_decorator(require_POST)
    def keep_card_value_view(self, request, event_id):
        if not request.user.has_perms((
            'arealisting.change_arealistinglistinggroup',
            'arealisting.change_arealistingsyncevent',
            'properties.change_property',
        )):
            raise PermissionDenied
        event = get_object_or_404(ArealistingSyncEvent.objects.select_related('unit'),
                                  pk=event_id, kind=ArealistingSyncEvent.Kind.UNIT_FIELDS)
        source_field = request.POST.get('source_field', '')
        target_field = UNIT_TO_PROPERTY_FIELD.get(source_field)
        source_change = next((item for item in (event.details or {}).get('changed_fields', [])
                              if item.get('field') == source_field), None)
        if not target_field or source_change is None:
            raise Http404('Это поле не относится к изменению предложения.')
        if event.reviewed_at:
            self.message_user(request, 'Событие уже проверено. Откройте актуальное изменение.', messages.WARNING)
            return HttpResponseRedirect(reverse('admin:arealisting_review_queue'))
        with transaction.atomic():
            group = get_object_or_404(
                ArealistingListingGroup.objects.select_for_update().select_related('property'),
                property_id=event.property_id, project_id=event.project_id,
            )
            prop = Property.objects.select_for_update().get(pk=group.property_id)
            unit = ArealistingUnit.objects.filter(pk=event.unit_id).first() if event.unit_id else None
            if not unit or unit.listing_group_id != group.pk:
                self.message_user(request, 'Предложение больше не связано с карточкой. Обновите очередь.', messages.WARNING)
            elif (str(getattr(unit, source_field)) != str(source_change.get('after'))
                  or str(source_change.get('after')) != request.POST.get('expected_source_value')):
                self.message_user(request, 'Данные AREALISTING изменились. Проверьте последнее событие.', messages.WARNING)
            elif str(getattr(prop, target_field)) != request.POST.get('expected_card_value'):
                self.message_user(request, 'Значение карточки изменилось. Проверьте сравнение заново.', messages.WARNING)
            elif target_field not in (group.source_owned_fields or []):
                self.message_user(request, 'Это поле уже не находится под управлением AREALISTING.', messages.WARNING)
            elif target_field in (group.locked_fields or []):
                self.message_user(request, 'Значение карточки уже защищено.', messages.INFO)
            else:
                group.locked_fields = ordered_source_fields([*(group.locked_fields or []), target_field])
                group.save(update_fields=('locked_fields', 'updated_at'))
                record_property_change(
                    property_id=prop.pk, project_id=group.project_id,
                    kind=ArealistingPropertyChange.Kind.FIELDS, actor=request.user,
                    details={'locked_fields_added': [target_field], 'sync_event_id': event.pk},
                )
                self.message_user(request, 'Значение карточки сохранено и защищено от следующих синхронизаций.', messages.SUCCESS)
        return HttpResponseRedirect(reverse('admin:arealisting_review_queue') + f'#event-{event.pk}')

    def unlinked_view(self, request):
        if not self.has_view_or_change_permission(request) or not request.user.has_perm('properties.change_property'):
            raise PermissionDenied
        base = Property.objects.filter(arealisting_group__isnull=True)
        state = 'manual' if request.GET.get('state') == 'manual' else 'pending'
        activity = request.GET.get('activity', 'all')
        if activity not in ('all', 'active', 'inactive'):
            activity = 'all'
        query = request.GET.get('q', '').strip()
        properties = base.filter(arealisting_manual__isnull=state == 'pending')
        activity_counts = {
            'all': properties.count(),
            'active': properties.filter(is_active=True).count(),
            'inactive': properties.filter(is_active=False).count(),
        }
        if activity == 'active':
            properties = properties.filter(is_active=True)
        elif activity == 'inactive':
            properties = properties.filter(is_active=False)
        if query:
            condition = Q(title_ru__icontains=query) | Q(title_en__icontains=query) | Q(complex_name_ru__icontains=query) | Q(complex_name_en__icontains=query)
            if query.isdigit():
                condition |= Q(pk=int(query))
            properties = properties.filter(condition)
        selected = None
        project_page = None
        submitted_project_query = request.GET.get('project_q')
        project_query = (submitted_project_query or '').strip()
        if request.GET.get('property', '').isdigit():
            selected = get_object_or_404(base, pk=request.GET['property'])
            if submitted_project_query is None:
                # Подскажем название в поле, но не будем автоматически
                # выводить десятки комплексов до явного поиска администратора.
                project_query = (
                    selected.complex_name_en or selected.complex_name_ru or ''
                ).strip()
            if submitted_project_query is not None and project_query:
                projects = ArealistingProject.objects.filter(is_deleted=False).annotate(
                    unit_count=Count(
                        'units',
                        filter=Q(units__is_deleted=False),
                    ),
                    available_count=Count(
                        'units',
                        filter=Q(
                            units__is_deleted=False,
                            units__availability_status=ArealistingUnit.AvailabilityStatus.AVAILABLE,
                        ),
                    ),
                    sold_count=Count(
                        'units',
                        filter=Q(
                            units__is_deleted=False,
                            units__availability_status=ArealistingUnit.AvailabilityStatus.SOLD,
                        ),
                    ),
                )
                projects = projects.filter(Q(name_en__icontains=project_query) | Q(name_ru__icontains=project_query) | Q(developer_name__icontains=project_query))
                project_page = Paginator(projects.order_by('name_en', 'pk'), 20).get_page(request.GET.get('project_page'))
        property_page = Paginator(
            properties.select_related('property_type', 'district', 'location').order_by('pk'),
            24,
        ).get_page(request.GET.get('page'))
        photos = {}
        for image in PropertyImage.objects.filter(
            property_id__in=[prop.pk for prop in property_page.object_list],
        ).order_by('property_id', '-is_main', 'order', 'pk'):
            if image.property_id not in photos and image.original_url:
                photos[image.property_id] = image.original_url
        property_cards = [
            {'property': prop, 'photo': photos.get(prop.pk, '')}
            for prop in property_page.object_list
        ]
        return TemplateResponse(request, 'admin/arealisting/unlinked.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': 'Объекты Undersun без связи', 'state': state, 'query': query,
            'activity': activity, 'activity_counts': activity_counts,
            'pending_count': base.filter(arealisting_manual__isnull=True).count(),
            'manual_count': base.filter(arealisting_manual__isnull=False).count(),
            'page': property_page, 'property_cards': property_cards,
            'selected': selected, 'project_query': project_query, 'project_page': project_page,
            'can_load': self.has_change_permission(request) and request.user.has_perm('arealisting.change_arealistingunit'),
        })

    @method_decorator(require_POST)
    def manual_property_view(self, request, property_id):
        if not self.has_view_or_change_permission(request) or not request.user.has_perm('properties.change_property'):
            raise PermissionDenied
        action = request.POST.get('action')
        if action not in ('manual', 'pending'):
            return JsonResponse({'error': 'Неизвестное действие.'}, status=400)
        activity = request.POST.get('activity', 'all')
        if activity not in ('all', 'active', 'inactive'):
            activity = 'all'
        query = request.POST.get('q', '').strip()[:200]
        page = request.POST.get('page', '')
        with transaction.atomic():
            prop = get_object_or_404(Property.objects.select_for_update(), pk=property_id)
            if ArealistingListingGroup.objects.filter(property=prop).exists():
                self.message_user(request, 'Карточка уже связана с AREALISTING. Обновите список.', messages.WARNING)
            else:
                if action == 'manual':
                    ArealistingManualProperty.objects.get_or_create(property=prop)
                    message = 'Отмечено: ведём вручную.'
                else:
                    ArealistingManualProperty.objects.filter(property=prop).delete()
                    message = 'Карточка возвращена в список для подбора комплекса.'
                self.admin_site._registry[Property].log_change(request, prop, message)
                self.message_user(request, message, messages.SUCCESS)
        state = 'manual' if action == 'pending' else 'pending'
        params = {'state': state, 'activity': activity}
        if query:
            params['q'] = query
        if page.isdigit():
            params['page'] = page
        return HttpResponseRedirect(
            reverse('admin:arealisting_unlinked')
            + f'?{urlencode(params)}'
        )

    def detach_property_view(self, request, property_id):
        if not (
            request.user.has_perm('properties.change_property')
            and request.user.has_perm('arealisting.change_arealistinglistinggroup')
            and request.user.has_perm('arealisting.delete_arealistinglistinggroup')
        ):
            raise PermissionDenied
        prop = get_object_or_404(Property, pk=property_id)
        group = get_object_or_404(
            ArealistingListingGroup.objects.select_related('project'), property=prop,
        )
        if request.method == 'POST':
            group_id = request.POST.get('group_id', '')
            if not group_id.isdigit():
                raise Http404
            with transaction.atomic():
                prop = get_object_or_404(Property.objects.select_for_update(), pk=property_id)
                group = get_object_or_404(
                    ArealistingListingGroup.objects.select_for_update(),
                    pk=int(group_id), property=prop,
                )
                project_name = str(group.project)
                details = {
                    'project': project_name,
                    'units_before': list(group.units.values_list('pk', flat=True)),
                    'unit_labels_before': list(group.units.values_list('external_id', flat=True)),
                    'managed_before': group.source_owned_fields or [],
                }
                record_property_change(
                    property_id=prop.pk, project_id=group.project_id,
                    kind='DETACH', actor=request.user, details=details,
                )
                ArealistingPriceReview.objects.filter(
                    group=group, status=ArealistingPriceReview.Status.PENDING,
                ).update(status=ArealistingPriceReview.Status.SUPERSEDED)
                group.delete()
                self.admin_site._registry[Property].log_change(
                    request, prop, f'Отвязана от AREALISTING: {project_name}.',
                )
            self.message_user(request, 'Карточка отвязана. Теперь можно выбрать другой комплекс.', messages.SUCCESS)
            return HttpResponseRedirect(
                f"{reverse('admin:arealisting_unlinked')}?{urlencode({'property': prop.pk})}"
            )
        return TemplateResponse(request, 'admin/arealisting/detach_property.html', {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': 'Отвязать карточку от AREALISTING',
            'property': prop,
            'group': group,
        })

    @method_decorator(require_POST)
    def load_inventory_view(self, request, project_id):
        if not self.has_change_permission(request) or not request.user.has_perm('arealisting.change_arealistingunit'):
            raise PermissionDenied
        project = get_object_or_404(ArealistingProject, pk=project_id, is_deleted=False)
        selected = None
        if request.POST.get('property', '').isdigit():
            if not request.user.has_perm('properties.change_property'):
                raise PermissionDenied
            selected = get_object_or_404(Property, pk=request.POST['property'])
        self._run_sync(
            request,
            resources=('units',),
            project_ids=[project.external_id],
        )
        if selected:
            source = _source_navigation_params(request.POST)
            destination = _unlinked_back_url(selected.pk, source)
        else:
            destination = _workspace_back_url(project.pk, request.POST)
        return HttpResponseRedirect(destination)

    def matching_view(self, request):
        required = ('arealisting.view_arealistingproject', 'arealisting.change_arealistingunit',
                    'arealisting.add_arealistinglistinggroup', 'arealisting.change_arealistinglistinggroup',
                    'properties.change_property')
        if not request.user.has_perms(required):
            raise PermissionDenied
        if request.method == 'POST':
            payload = None
            try:
                payload = json.loads(request.body)
                if not isinstance(payload, dict):
                    raise ValueError
                action = payload.get('action', 'save_links')
                if action == 'preview_draft':
                    if not request.user.has_perm('properties.add_property'):
                        raise PermissionDenied
                    return JsonResponse(
                        {'preview': preview_draft(
                            payload['project'],
                            payload['units'],
                            payload.get('location_choice'),
                        )}
                    )
                if action == 'create_draft':
                    if not request.user.has_perm('properties.add_property'):
                        raise PermissionDenied
                    prop = create_draft(
                        payload['project'],
                        payload['units'],
                        payload.get('location_choice'),
                        payload.get('media_assets', []),
                    )
                    from .services.media_jobs import queue_media_job, start_media_worker

                    selected_media = payload.get('media_assets', [])
                    media_job = None
                    if selected_media:
                        media_job, created = queue_media_job(
                            prop.arealisting_group.pk,
                            selected_asset_ids=selected_media,
                            actor=request.user,
                        )
                        if created:
                            try:
                                start_media_worker(limit=1)
                            except OSError:
                                pass
                    self.admin_site._registry[Property].log_addition(
                        request,
                        prop,
                        'Создан неактивный черновик из AREALISTING.',
                    )
                    return JsonResponse({
                        'property': prop.pk,
                        'title': str(prop),
                        'url': reverse('admin:properties_property_change', args=[prop.pk]),
                        'media_job_url': (reverse(
                            'admin:arealisting_arealistinglistinggroup_media_job',
                            args=[prop.arealisting_group.pk, media_job.pk],
                        ) if media_job else ''),
                    })
                if action == 'skip_units':
                    count = skip_units(
                        payload['project'],
                        payload['units'],
                        user=request.user,
                        reason=payload.get('reason', ''),
                    )
                    self.log_change(
                        request,
                        ArealistingProject.objects.get(pk=payload['project']),
                        f'Пропущено предложений: {count}',
                    )
                    return JsonResponse({'count': count})
                if action == 'restore_units':
                    count = restore_units(payload['project'], payload['units'])
                    self.log_change(
                        request,
                        ArealistingProject.objects.get(pk=payload['project']),
                        f'Возвращено предложений в очередь: {count}',
                    )
                    return JsonResponse({'count': count})
                if action != 'save_links' or not isinstance(payload.get('rows'), list):
                    raise ValueError
                if any(not isinstance(row, dict) or not isinstance(row.get('expected'), dict) for row in payload['rows']):
                    raise ValueError
                reports = []
                count = save_links(payload['project'], payload['rows'], reports=reports, actor=request.user)
            except (ValueError, TypeError, KeyError, ValidationError, IntegrityError,
                    Property.DoesNotExist, ArealistingProject.DoesNotExist) as exc:
                message = ' '.join(exc.messages) if isinstance(exc, ValidationError) else 'Не удалось сохранить. Проверьте выбор и обновите экран.'
                return JsonResponse({'error': message}, status=400)
            for row in payload['rows']:
                if (
                    'is_active' in row
                    and row.get('expected_is_active') != row.get('is_active')
                ):
                    prop = Property.objects.get(pk=row['property'])
                    state = 'активна' if prop.is_active else 'неактивна'
                    self.admin_site._registry[Property].log_change(
                        request,
                        prop,
                        f'Активность изменена через AREALISTING: карточка {state}.',
                    )
            self.log_change(request, ArealistingProject.objects.get(pk=payload['project']), f'Сопоставлено карточек: {count}')
            return JsonResponse({
                'count': count,
                'rows': [
                    {
                        **report,
                        'url': reverse('admin:properties_property_change', args=[report['property_id']]),
                        'media_preview_url': reverse(
                            'admin:arealisting_arealistinglistinggroup_preview_media',
                            args=[report['group_id']],
                        ),
                    }
                    for report in reports
                ],
            })
        project = ArealistingProject.objects.filter(pk=request.GET.get('project'), is_deleted=False).first() if request.GET.get('project', '').isdigit() else None
        if not project:
            return HttpResponseRedirect(reverse('admin:arealisting_arealistingproject_changelist'))
        context = {**self.admin_site.each_context(request), 'title': 'Сопоставление с AREALISTING',
                   'opts': self.model._meta, 'projects': ArealistingProject.objects.filter(is_deleted=False),
                   'project': project, 'search': request.GET.get('q', '')}
        if project:
            context.update(price_report_context(project))
            query = request.GET.get('q', '').strip()
            candidates = Property.objects.select_related('arealisting_group')
            if request.GET.get('property', '').isdigit():
                selected = get_object_or_404(Property, pk=request.GET['property'])
                context['selected_property'] = selected
                source = _source_navigation_params(request.GET)
                context.update(source)
                context['unlinked_back_url'] = _unlinked_back_url(selected.pk, source)
                candidates = candidates.filter(pk=selected.pk)
            elif query:
                candidates = candidates.filter(Q(title_ru__icontains=query) | Q(title_en__icontains=query) | Q(complex_name_ru__icontains=query) | Q(complex_name_en__icontains=query))
            else:
                names = [name for name in (project.name_ru, project.name_en) if name.strip()]
                condition = Q(pk__in=[])
                for name in names:
                    condition |= Q(complex_name_ru__icontains=name) | Q(complex_name_en__icontains=name) | Q(title_ru__icontains=name) | Q(title_en__icontains=name)
                candidates = candidates.filter(condition)
            properties = list(candidates.order_by('pk')[:100])
            units = list(
                project.units.filter(is_deleted=False)
                .select_related('listing_group', 'skip_decision')
                .order_by('unit_number')
            )
            context['matching_data'] = {
                'project': project.pk, 'user': request.user.pk,
                'project_values': project_proposals(project),
                'project_field_keys': PROJECT_FIELD_KEYS,
                'can_create_draft': request.user.has_perm('properties.add_property'),
                'fields': FIELDS,
                'properties': [{'id': p.pk, 'title': p.title_ru or p.title_en or p.title,
                                'is_active': p.is_active,
                                'original_units': list(ArealistingUnit.objects.filter(listing_group__property_id=p.pk).values_list('pk', flat=True)),
                                'managed_fields': [field for field in (p.arealisting_group.source_owned_fields or []) if field in FIELDS] if hasattr(p, 'arealisting_group') else [],
                                'locked_fields': (p.arealisting_group.locked_fields or []) if hasattr(p, 'arealisting_group') else [],
                                'photo': p.get_main_image_url(),
                                'url': reverse('admin:properties_property_change', args=[p.pk]),
                                'values': {key: getattr(p, key) for key in FIELDS}} for p in properties],
                'units': [{'id': u.pk, 'number': u.unit_number, **unit_preview(u),
                           'price': u.price, 'currency': u.currency,
                           'property_type': u.property_type,
                           'status': u.availability_status,
                           'skipped': hasattr(u, 'skip_decision'),
                           'skip_reason': (
                               u.skip_decision.reason if hasattr(u, 'skip_decision') else ''
                           ),
                           'property': u.listing_group.property_id if u.listing_group_id else None,
                           'occupied': bool(u.listing_group_id)} for u in units],
            }
            context['can_create_draft'] = request.user.has_perm('properties.add_property')
        return TemplateResponse(request, 'admin/arealisting/matching.html', context)

    @admin.display(description='Проект', ordering='name_en')
    def display_name(self, obj):
        return obj.name_en or obj.name_ru or obj.external_id

    @admin.display(description='География')
    def source_locations(self, obj):
        names = [
            str(item.get('name'))
            for item in (obj.districts or [])
            if isinstance(item, dict) and item.get('name')
        ]
        return ', '.join(names) or '—'

    @admin.display(description='AVAILABLE', ordering='_available_units')
    def available_units(self, obj):
        return obj._available_units

    @admin.display(description='SOLD', ordering='_sold_units')
    def sold_units(self, obj):
        return obj._sold_units

    @admin.display(description='Локации сопоставлены', boolean=True)
    def location_mapping_ready(self, obj):
        external_ids = {
            item.get('external_id')
            for item in (obj.districts or [])
            if isinstance(item, dict) and item.get('external_id')
        }
        if not external_ids:
            return False
        confirmed = ArealistingLocationMapping.objects.filter(
            external_id__in=external_ids,
            is_confirmed=True,
        ).exclude(
            mapping_mode=ArealistingLocationMapping.MappingMode.UNMAPPED
        ).count()
        return confirmed == len(external_ids)

    def _run_sync(self, request, *, resources, project_ids=None, full=True):
        try:
            job, created = queue_sync_job(
                resources=resources, project_ids=project_ids, full=full,
                actor=request.user,
            )
            if created:
                try:
                    start_sync_worker(job.pk)
                except OSError:
                    job.status = ArealistingSyncJob.Status.FAILED
                    job.error = 'Не удалось запустить фоновый обработчик. Повторите обновление.'
                    job.finished_at = timezone.now()
                    job.save(update_fields=('status', 'error', 'finished_at'))
                    raise ArealistingError(job.error)
        except (ArealistingError, ValueError) as exc:
            self.message_user(request, f'Ошибка AREALISTING: {exc}', messages.ERROR)
            return False
        if created:
            self.message_user(
                request,
                'Обновление AREALISTING запущено в фоне. Статус и результат появятся на этой странице.',
                messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                f'Обновление AREALISTING уже ожидает или выполняется (задание №{job.pk}).',
                messages.INFO,
            )
        return True

    def sync_projects_view(self, request):
        if not self.has_change_permission(request):
            raise PermissionDenied
        if request.method != 'POST':
            self.message_user(
                request,
                'Обновление списка проектов запускается только POST-запросом.',
                messages.ERROR,
            )
        else:
            self._run_sync(request, resources=('projects',), full=True)
        return HttpResponseRedirect(
            reverse('admin:arealisting_arealistingproject_changelist')
        )

    @admin.action(description='Обновить выбранные проекты из AREALISTING')
    def sync_selected_projects(self, request, queryset):
        project_ids = list(queryset.values_list('external_id', flat=True))
        self._run_sync(
            request,
            resources=('projects',),
            project_ids=project_ids,
            full=True,
        )

    @admin.action(description='Получить предложения выбранных проектов')
    def sync_selected_inventory(self, request, queryset):
        project_ids = list(queryset.values_list('external_id', flat=True))
        self._run_sync(
            request,
            resources=('units',),
            project_ids=project_ids,
            full=True,
        )


@admin.register(ArealistingUnit)
class ArealistingUnitAdmin(SourceReadOnlyAdmin):
    list_display = (
        'unit_number',
        'project',
        'availability_status',
        'bedrooms',
        'floor',
        'internal_area_sqm',
        'price',
        'currency',
        'listing_group',
        'synced_at',
        'is_deleted',
    )
    list_filter = (
        'availability_status',
        'property_type',
        'currency',
        'is_deleted',
        'sync_enabled',
    )
    search_fields = (
        'external_id',
        'unit_number',
        'project__name_en',
        'project__name_ru',
    )
    autocomplete_fields = ('listing_group',)
    readonly_fields = tuple(
        field.name
        for field in ArealistingUnit._meta.fields
        if field.name not in {'listing_group', 'sync_enabled'}
    )
    fields = (
        'external_id',
        'project',
        'listing_group',
        'sync_enabled',
        'unit_number',
        'availability_status',
        'property_type',
        'bedrooms',
        'bathrooms',
        'floor',
        'internal_area_sqm',
        'plot_size_sqm',
        'sea_view',
        'price',
        'currency',
        'price_per_sqm',
        'maintenance_fee',
        'maintenance_fee_mode',
        'sinking_fund',
        'sinking_fund_mode',
        'furnishing',
        'gallery',
        'remote_updated_at',
        'last_seen_at',
        'synced_at',
        'is_deleted',
        'raw_payload',
    )


class ArealistingListingGroupAdminForm(forms.ModelForm):
    protected_fields = forms.MultipleChoiceField(
        label='Защищено от обновления AREALISTING',
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text=(
            'Ручное изменение карточки включает защиту автоматически. '
            'Чтобы снова разрешить обновление из AREALISTING, снимите нужную галочку.'
        ),
    )

    class Meta:
        model = ArealistingListingGroup
        exclude = ('locked_fields', 'source_owned_fields', 'excluded_media_source_keys')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        fields = set(self.instance.source_owned_fields or [])
        fields.update(self.instance.locked_fields or [])
        ordered = ordered_source_fields(fields)
        self.fields['protected_fields'].choices = [
            (field, SOURCE_FIELD_LABELS.get(field, field)) for field in ordered
        ]
        if not self.is_bound:
            self.initial['protected_fields'] = self.instance.locked_fields or []

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.locked_fields = ordered_source_fields(
            self.cleaned_data.get('protected_fields', [])
        )
        if commit:
            instance.save()
            self.save_m2m()
        return instance


@admin.register(ArealistingListingGroup)
class ArealistingListingGroupAdmin(InternalAdminMixin, admin.ModelAdmin):
    form = ArealistingListingGroupAdminForm
    change_form_template = 'admin/arealisting/arealistinglistinggroup/change_form.html'
    list_display = (
        'name',
        'project',
        'grouping_mode',
        'available_units_count',
        'price_range',
        'property',
        'catalog_origin',
        'is_ready_for_publication',
        'is_active',
        'updated_at',
    )
    list_filter = (
        'catalog_origin', 'grouping_mode', 'is_ready_for_publication', 'is_active', 'currency'
    )
    search_fields = ('name', 'project__name_en', 'project__name_ru', 'project__external_id')
    autocomplete_fields = ('project', 'property')
    readonly_fields = (
        'available_units_count',
        'currency',
        'min_price',
        'max_price',
        'min_area_sqm',
        'max_area_sqm',
        'catalog_origin',
        'source_fields_display',
        'created_at',
        'updated_at',
    )
    actions = ('recalculate_groups', 'import_media')

    def save_model(self, request, obj, form, change):
        if change and 'property' in form.changed_data:
            ArealistingPriceReview.objects.filter(
                group=obj, status=ArealistingPriceReview.Status.PENDING,
            ).update(status=ArealistingPriceReview.Status.SUPERSEDED)
        super().save_model(request, obj, form, change)

    def get_urls(self):
        return [
            path(
                '<path:object_id>/readiness/',
                self.admin_site.admin_view(self.readiness_view),
                name='arealisting_arealistinglistinggroup_readiness',
            ),
            path(
                '<path:object_id>/preview-media/',
                self.admin_site.admin_view(self.preview_media_view),
                name='arealisting_arealistinglistinggroup_preview_media',
            ),
            path(
                '<path:object_id>/media-job/<int:job_id>/',
                self.admin_site.admin_view(self.media_job_view),
                name='arealisting_arealistinglistinggroup_media_job',
            ),
            path(
                '<path:object_id>/media-job/<int:job_id>/retry/',
                self.admin_site.admin_view(self.retry_media_job_view),
                name='arealisting_arealistinglistinggroup_retry_media_job',
            ),
            path(
                '<path:object_id>/import-media/',
                self.admin_site.admin_view(self.import_media_view),
                name='arealisting_arealistinglistinggroup_import_media',
            ),
        ] + super().get_urls()

    def readiness_view(self, request, object_id):
        group = get_object_or_404(
            ArealistingListingGroup.objects.select_related('project', 'property'),
            pk=object_id, property__isnull=False,
        )
        if not self.has_view_or_change_permission(request, group):
            raise PermissionDenied
        report = publication_readiness(group)
        can_change_property = request.user.has_perm('properties.change_property')
        matching_perms = (
            'arealisting.view_arealistingproject', 'arealisting.change_arealistingunit',
            'arealisting.add_arealistinglistinggroup', 'arealisting.change_arealistinglistinggroup',
            'properties.change_property',
        )
        actions = {
            'property': (reverse('admin:properties_property_change', args=[group.property_id])
                         if can_change_property else ''),
            'group': (reverse('admin:arealisting_arealistinglistinggroup_change', args=[group.pk])
                      if self.has_change_permission(request, group) else ''),
            'matching': (f"{reverse('admin:arealisting_matching')}?{urlencode({'project': group.project_id, 'property': group.property_id})}"
                         if request.user.has_perms(matching_perms) else ''),
        }
        for check in report['checks']:
            if check['action'] == 'price_review' and check.get('review_id'):
                check['action_url'] = (
                    reverse('admin:arealisting_arealistingpricereview_review', args=[check['review_id']])
                    if request.user.has_perm('arealisting.view_arealistingpricereview') else ''
                )
            else:
                check['action_url'] = actions.get(check['action'], '')
        return TemplateResponse(request, 'admin/arealisting/readiness.html', {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': 'Проверка карточки перед публикацией',
            'group': group, 'property': group.property,
            'report': report, 'property_url': actions['property'],
        })

    def change_view(self, request, object_id, form_url='', extra_context=None):
        group = self.get_object(request, object_id)
        context = {'can_import_group_media': bool(
            group and group.property_id and self.has_change_permission(request, group)
        )}
        if group:
            from .services.media import candidate_media_assets, preview_group_media

            candidates = candidate_media_assets(group.project, list(group.units.all()))
            media_preview = preview_group_media(group.pk, enable=True) if group.property_id else None
            context['can_import_group_media'] = bool(
                context['can_import_group_media'] and media_preview
                and (media_preview['available'] or media_preview['removals'])
            )
            context['media_candidate_count'] = len(candidates)
            context['media_error_assets'] = [
                asset for asset, _role in candidates if asset.last_error
            ][:10]
            context['media_error_count'] = sum(
                bool(asset.last_error) for asset, _role in candidates
            )
            context['media_link_count'] = group.property_assets.filter(
                property_image__isnull=False
            ).count()
            context['latest_media_job'] = group.media_jobs.order_by('-created_at').first()
            context['can_view_media_assets'] = request.user.has_perm('arealisting.view_arealistingasset')
        context.update(extra_context or {})
        return super().change_view(request, object_id, form_url, context)

    def preview_media_view(self, request, object_id):
        from .services.media import preview_group_media

        group = get_object_or_404(ArealistingListingGroup, pk=object_id, property__isnull=False)
        if not self.has_change_permission(request, group):
            raise PermissionDenied
        selected_ids = request.POST.getlist('asset') if request.method == 'POST' else None
        try:
            preview = preview_group_media(group.pk, enable=True, selected_asset_ids=selected_ids,
                                          preferred_main_asset_id=request.POST.get('preferred_main_asset_id') if request.method == 'POST' else None)
        except ValidationError:
            self.message_user(request, 'Список фото изменился. Выберите изображения заново.', messages.WARNING)
            return HttpResponseRedirect(request.path)
        return TemplateResponse(request, 'admin/arealisting/media_preview.html', {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': 'Проверка импорта фото AREALISTING',
            'previews': [preview],
            'preview_url': reverse('admin:arealisting_arealistinglistinggroup_preview_media', args=[group.pk]),
            'confirm_url': reverse('admin:arealisting_arealistinglistinggroup_import_media', args=[group.pk]),
            'back_url': reverse('admin:arealisting_arealistinglistinggroup_change', args=[group.pk]),
        })

    @method_decorator(require_POST)
    def import_media_view(self, request, object_id):
        from .services.media import preview_group_media

        group = get_object_or_404(ArealistingListingGroup, pk=object_id)
        if not self.has_change_permission(request, group):
            raise PermissionDenied
        if not group.property_id:
            self.message_user(
                request,
                'Сначала свяжите группу с карточкой Undersun.',
                messages.ERROR,
            )
        else:
            if request.POST.get('selection_confirmed') != '1':
                self.message_user(request, 'Сначала выберите фото на странице предпросмотра.', messages.WARNING)
                return HttpResponseRedirect(reverse(
                    'admin:arealisting_arealistinglistinggroup_preview_media', args=[group.pk]
                ))
            selected_ids = request.POST.getlist('asset')
            try:
                preview = preview_group_media(
                    group.pk, enable=True, selected_asset_ids=selected_ids,
                    preferred_main_asset_id=request.POST.get('preferred_main_asset_id'),
                )
            except ValidationError:
                self.message_user(request, 'Список фото изменился. Выберите изображения заново.', messages.WARNING)
                return HttpResponseRedirect(reverse(
                    'admin:arealisting_arealistinglistinggroup_preview_media', args=[group.pk]
                ))
            if request.POST.get('preview_fingerprint') != preview['fingerprint']:
                self.message_user(request, 'Состав фото изменился. Проверьте обновлённый предпросмотр.', messages.WARNING)
                return self.preview_media_view(request, object_id)
            active_job = group.media_jobs.filter(
                status__in=(ArealistingMediaJob.Status.PENDING,
                            ArealistingMediaJob.Status.RUNNING),
            ).order_by('-pk').first()
            if active_job:
                self.message_user(request, 'Импорт этой группы уже выполняется. Дождитесь результата.', messages.WARNING)
                return HttpResponseRedirect(reverse(
                    'admin:arealisting_arealistinglistinggroup_media_job',
                    args=[group.pk, active_job.pk],
                ))
            selected = set(preview['selected_ids'])
            excluded = set(group.excluded_media_source_keys or [])
            for item in preview['available']:
                if item['asset'].pk in selected:
                    excluded.discard(item['asset'].source_key)
                else:
                    excluded.add(item['asset'].source_key)
            group.excluded_media_source_keys = sorted(excluded)
            group.save(update_fields=('excluded_media_source_keys', 'updated_at'))
            if not preview['can_import']:
                self.message_user(
                    request,
                    'Выбор фото сохранён. Для импорта сейчас ничего не выбрано.',
                    messages.SUCCESS,
                )
            else:
                jobs = self._queue_media_groups(
                    request, [group], selected_by_group={group.pk: selected_ids},
                    preferred_main_by_group={group.pk: preview['preferred_main_asset_id']},
                )
                if jobs:
                    return HttpResponseRedirect(reverse(
                        'admin:arealisting_arealistinglistinggroup_media_job',
                        args=[group.pk, jobs[0].pk],
                    ))
        return HttpResponseRedirect(reverse(
            'admin:arealisting_arealistinglistinggroup_change', args=[group.pk]
        ))

    def media_job_view(self, request, object_id, job_id):
        from .services.media_jobs import recover_stale_media_jobs

        recover_stale_media_jobs()
        group = get_object_or_404(ArealistingListingGroup, pk=object_id)
        if not self.has_view_or_change_permission(request, group):
            raise PermissionDenied
        job = get_object_or_404(ArealistingMediaJob, pk=job_id, group=group)
        failed_asset_ids = [row['asset_id'] for row in job.results if row['status'] == 'error']
        return TemplateResponse(request, 'admin/arealisting/media_job.html', {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': f'Импорт фото #{job.pk}',
            'group': group,
            'job': job,
            'preferred_main_failed': any(row['asset_id'] == job.preferred_main_asset_id
                                         and row['status'] == 'error' for row in job.results),
            'failed_asset_ids': failed_asset_ids,
            'can_retry': bool(failed_asset_ids and self.has_change_permission(request, group)
                              and job.status in (ArealistingMediaJob.Status.PARTIAL,
                                                 ArealistingMediaJob.Status.FAILED)),
        })

    @method_decorator(require_POST)
    def retry_media_job_view(self, request, object_id, job_id):
        from .services.media_jobs import queue_media_job, start_media_worker

        group = get_object_or_404(ArealistingListingGroup, pk=object_id)
        if not self.has_change_permission(request, group):
            raise PermissionDenied
        previous = get_object_or_404(ArealistingMediaJob, pk=job_id, group=group)
        failed_ids = [row['asset_id'] for row in previous.results if row['status'] == 'error']
        if not failed_ids or previous.status not in (ArealistingMediaJob.Status.PARTIAL,
                                                       ArealistingMediaJob.Status.FAILED):
            self.message_user(request, 'Нет фото с ошибками для повторной загрузки.', messages.WARNING)
            return HttpResponseRedirect(reverse(
                'admin:arealisting_arealistinglistinggroup_media_job', args=[group.pk, previous.pk]
            ))
        try:
            job, created = queue_media_job(
                group.pk, selected_asset_ids=failed_ids, actor=request.user, prune_missing=False,
                preferred_main_asset_id=(previous.preferred_main_asset_id
                                         if previous.preferred_main_asset_id in failed_ids else None),
            )
        except ValidationError:
            self.message_user(request, 'Исходные фото изменились. Проверьте выбор заново.', messages.WARNING)
            return HttpResponseRedirect(reverse(
                'admin:arealisting_arealistinglistinggroup_preview_media', args=[group.pk]
            ))
        if created:
            try:
                start_media_worker(limit=1)
            except OSError:
                self.message_user(request, 'Задание сохранено, но обработчик не запустился. Проверьте журнал сервера.', messages.ERROR)
        return HttpResponseRedirect(reverse(
            'admin:arealisting_arealistinglistinggroup_media_job', args=[group.pk, job.pk]
        ))

    @staticmethod
    def _has_importable_media(group, candidates):
        locked = set(group.locked_fields or [])
        return any(
            (role == ArealistingPropertyAsset.Role.GALLERY and 'images' not in locked)
            or (role == ArealistingPropertyAsset.Role.FLOOR_PLAN and 'floorplans' not in locked)
            for _asset, role in candidates
        )

    @admin.display(description='Поля под управлением AREALISTING')
    def source_fields_display(self, obj):
        if not obj or not obj.source_owned_fields:
            return 'Нет — связанная карточка не обновляется по полям автоматически.'
        return ', '.join(
            SOURCE_FIELD_LABELS.get(field, field)
            for field in ordered_source_fields(obj.source_owned_fields)
        )

    @admin.display(description='Цена')
    def price_range(self, obj):
        if obj.min_price is None:
            return '—'
        if obj.max_price is None or obj.min_price == obj.max_price:
            return f'{obj.min_price} {obj.currency}'.strip()
        return f'{obj.min_price}–{obj.max_price} {obj.currency}'.strip()

    @admin.action(description='Пересчитать выбранные группы')
    def recalculate_groups(self, request, queryset):
        for group in queryset:
            ArealistingSyncService.recalculate_listing_group(group)
        self.message_user(request, f'Пересчитано групп: {queryset.count()}.')

    @admin.action(description='Проверить и импортировать фотографии и планировки')
    def import_media(self, request, queryset):
        from .services.media import preview_group_media

        if queryset.count() > 10:
            self.message_user(
                request,
                'За один запуск можно обработать не более 10 групп.',
                messages.ERROR,
            )
            return
        previews = [preview_group_media(group.pk, enable=True) for group in queryset]
        fingerprints = {str(preview['group'].pk): preview['fingerprint'] for preview in previews}
        if request.POST.get('confirm_media_import') != '1':
            return TemplateResponse(request, 'admin/arealisting/media_preview.html', {
                **self.admin_site.each_context(request),
                'opts': self.model._meta,
                'title': 'Проверка импорта фото AREALISTING',
                'previews': previews,
                'bulk': True,
                'back_url': reverse('admin:arealisting_arealistinglistinggroup_changelist'),
            })
        if any(request.POST.get(f'fingerprint_{pk}') != fingerprint
               for pk, fingerprint in fingerprints.items()):
            self.message_user(request, 'Состав фото изменился. Выберите группы и проверьте импорт заново.', messages.WARNING)
            return
        queryset = [preview['group'] for preview in previews if preview['can_import']]
        if not queryset:
            self.message_user(request, 'Нет подходящих фото для импорта.', messages.WARNING)
            return
        jobs = self._queue_media_groups(request, queryset)
        if len(jobs) == 1:
            return HttpResponseRedirect(reverse(
                'admin:arealisting_arealistinglistinggroup_media_job',
                args=[jobs[0].group_id, jobs[0].pk],
            ))
        return TemplateResponse(request, 'admin/arealisting/media_jobs_queued.html', {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': 'Фото поставлены в очередь',
            'jobs': jobs,
        })

    def _queue_media_groups(self, request, groups, *, selected_by_group=None, preferred_main_by_group=None):
        from .services.media_jobs import queue_media_job, start_media_worker
        from .services.media import preview_group_media

        jobs = []
        for group in groups:
            selected = (selected_by_group[group.pk] if selected_by_group is not None
                        else preview_group_media(group.pk, enable=True)['selected_ids'])
            job, _created = queue_media_job(
                group.pk, selected_asset_ids=selected, actor=request.user,
                preferred_main_asset_id=(preferred_main_by_group or {}).get(group.pk),
            )
            jobs.append(job)
        pending_count = sum(job.status == ArealistingMediaJob.Status.PENDING for job in jobs)
        if pending_count:
            try:
                start_media_worker(limit=pending_count)
            except OSError:
                self.message_user(request, 'Задания сохранены, но обработчик не запустился. Проверьте журнал сервера.', messages.ERROR)
        return jobs


@admin.register(ArealistingLocationMapping)
class ArealistingLocationMappingAdmin(InternalAdminMixin, admin.ModelAdmin):
    list_display = (
        'source_name',
        'source_type',
        'mapping_mode',
        'district',
        'location',
        'is_confirmed',
        'synced_at',
    )
    list_filter = ('mapping_mode', 'is_confirmed', 'is_deleted')
    search_fields = ('external_id', 'source_name', 'description_en', 'description_ru')
    raw_id_fields = ('district', 'location')
    readonly_fields = (
        'external_id',
        'source_name',
        'source_type',
        'parent_external_id',
        'description_en',
        'description_ru',
        'gallery',
        'raw_payload',
        'remote_updated_at',
        'last_seen_at',
        'synced_at',
        'is_deleted',
    )
    fieldsets = (
        ('Источник', {
            'fields': (
                'external_id',
                'source_name',
                'source_type',
                'parent_external_id',
                'description_en',
                'description_ru',
                'gallery',
            )
        }),
        ('Сопоставление Undersun', {
            'fields': ('mapping_mode', 'district', 'location', 'is_confirmed')
        }),
        ('Синхронизация', {
            'classes': ('collapse',),
            'fields': (
                'remote_updated_at',
                'last_seen_at',
                'synced_at',
                'is_deleted',
                'raw_payload',
            ),
        }),
    )


@admin.register(ArealistingPaymentPlan)
class ArealistingPaymentPlanAdmin(SourceReadOnlyAdmin):
    list_display = ('name', 'project', 'remote_updated_at', 'synced_at', 'is_deleted')
    list_filter = ('is_deleted',)
    search_fields = ('external_id', 'name', 'project__name_en', 'project__name_ru')
    readonly_fields = tuple(field.name for field in ArealistingPaymentPlan._meta.fields)


class AssetDownloadStatusFilter(admin.SimpleListFilter):
    title = 'состояние загрузки'
    parameter_name = 'download_state'

    def lookups(self, request, model_admin):
        return (('error', 'С ошибкой'), ('downloaded', 'Загружено'), ('url', 'Только URL'))

    def queryset(self, request, queryset):
        if self.value() == 'error':
            return queryset.exclude(last_error='')
        if self.value() == 'downloaded':
            return queryset.filter(last_error='', downloaded_at__isnull=False)
        if self.value() == 'url':
            return queryset.filter(last_error='', downloaded_at__isnull=True)
        return queryset


@admin.register(ArealistingAsset)
class ArealistingAssetAdmin(SourceReadOnlyAdmin):
    change_list_template = 'admin/arealisting/arealistingasset/change_list.html'
    change_form_template = 'admin/arealisting/arealistingasset/change_form.html'
    list_display = (
        'asset_type',
        'project',
        'unit',
        'position',
        'download_status',
        'error_summary',
        'linked_card',
        'is_active',
        'updated_at',
    )
    list_filter = (AssetDownloadStatusFilter, 'asset_type', 'is_active')
    search_fields = (
        'source_url',
        'source_key',
        'project__name_en',
        'unit__unit_number',
    )
    readonly_fields = tuple(field.name for field in ArealistingAsset._meta.fields)
    actions = ('retry_download',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('project', 'unit').prefetch_related(
            'property_links__listing_group__property'
        )

    def get_urls(self):
        return [
            path('<path:object_id>/retry-download/', self.admin_site.admin_view(self.retry_download_view),
                 name='arealisting_arealistingasset_retry_download'),
        ] + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        context = {
            'can_retry_assets': self.has_change_permission(request),
            'can_view_asset_groups': request.user.has_perm('arealisting.view_arealistinglistinggroup'),
        }
        context.update(extra_context or {})
        return super().changelist_view(request, context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        asset = self.get_object(request, object_id)
        context = {
            'can_retry_asset': bool(
                asset and self.has_change_permission(request) and self._can_download(asset)
            ),
            'can_view_asset_groups': request.user.has_perm('arealisting.view_arealistinglistinggroup'),
        }
        if asset and context['can_view_asset_groups']:
            groups = self._candidate_groups(asset)
            context['asset_group_count'] = groups.count()
            context['asset_groups'] = list(groups[:20])
        context.update(extra_context or {})
        return super().change_view(request, object_id, form_url, context)

    @staticmethod
    def _candidate_groups(asset):
        groups = ArealistingListingGroup.objects.select_related('property', 'project')
        if not asset.is_active:
            return groups.none()
        if asset.asset_type == ArealistingAsset.AssetType.UNIT_GALLERY and asset.unit_id:
            return groups.filter(pk=asset.unit.listing_group_id) if asset.unit.listing_group_id else groups.none()
        if asset.unit_id is None and asset.project_id and asset.asset_type in {
            ArealistingAsset.AssetType.PROJECT_GALLERY,
            ArealistingAsset.AssetType.FLOOR_PLAN,
            ArealistingAsset.AssetType.MASTER_PLAN,
            ArealistingAsset.AssetType.PHOTOS_RENDERS,
        }:
            return groups.filter(project_id=asset.project_id).order_by('name', 'pk')
        return groups.none()

    @method_decorator(require_POST)
    def retry_download_view(self, request, object_id):
        if not self.has_change_permission(request):
            raise PermissionDenied
        asset = get_object_or_404(self.get_queryset(request), pk=object_id)
        self._retry_assets(request, [asset])
        return HttpResponseRedirect(reverse('admin:arealisting_arealistingasset_change', args=[asset.pk]))

    @admin.action(description='Повторить скачивание выбранных изображений', permissions=['change'])
    def retry_download(self, request, queryset):
        if queryset.count() > 10:
            self.message_user(request, 'За один запуск можно скачать не более 10 изображений.', messages.ERROR)
            return
        self._retry_assets(request, queryset)

    def _retry_assets(self, request, assets):
        import requests
        from .services.media import download_asset

        downloaded = failed = skipped = 0
        with requests.Session() as session:
            for asset in assets:
                if not self._can_download(asset):
                    skipped += 1
                    continue
                if download_asset(asset, session=session):
                    downloaded += 1
                else:
                    failed += 1
        if not downloaded and not failed:
            self.message_user(
                request,
                'Скачивать нечего: выбранные материалы уже загружены, неактивны '
                'или относятся к документам.',
                messages.INFO,
            )
            return
        level = messages.WARNING if failed else messages.SUCCESS
        self.message_user(
            request,
            f'Скачано: {downloaded}; ошибок: {failed}; пропущено: {skipped}. '
            'Чтобы добавить фото в карточку, откройте «Связи с карточками» и выполните '
            '«Импортировать/обновить фотографии и планировки» для нужной группы.',
            level,
        )

    @staticmethod
    def _can_download(asset):
        from .services.media import NON_IMAGE_DOCUMENT_SUFFIXES

        image_types = {
            ArealistingAsset.AssetType.PROJECT_GALLERY,
            ArealistingAsset.AssetType.UNIT_GALLERY,
            ArealistingAsset.AssetType.FLOOR_PLAN,
            ArealistingAsset.AssetType.MASTER_PLAN,
            ArealistingAsset.AssetType.PHOTOS_RENDERS,
        }
        path = urlsplit(asset.source_url).path.lower()
        if not asset.is_active or asset.asset_type not in image_types:
            return False
        if any(path.endswith(suffix) for suffix in NON_IMAGE_DOCUMENT_SUFFIXES):
            return False
        if asset.file and asset.downloaded_at:
            try:
                if asset.file.storage.exists(asset.file.name):
                    return False
            except OSError:
                pass
        return True

    @admin.display(description='Загрузка')
    def download_status(self, obj):
        if obj.last_error:
            return format_html('<span style="color:#b91c1c">Ошибка</span>')
        if obj.downloaded_at:
            return format_html('<span style="color:#15803d">Загружено</span>')
        return 'Только URL'

    @admin.display(description='Причина ошибки')
    def error_summary(self, obj):
        return obj.last_error[:120] + ('…' if len(obj.last_error) > 120 else '') if obj.last_error else '—'

    @admin.display(description='Карточка Undersun')
    def linked_card(self, obj):
        links = [link for link in obj.property_links.all() if link.listing_group.property_id]
        if not links:
            return 'Не добавлено'
        group = links[0].listing_group
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:arealisting_arealistinglistinggroup_change', args=[group.pk]),
            group.property,
        )


@admin.register(ArealistingPropertyAsset)
class ArealistingPropertyAssetAdmin(SourceReadOnlyAdmin):
    list_display = ('listing_group', 'role', 'asset', 'property_image', 'updated_at')
    list_filter = ('role',)
    search_fields = (
        'listing_group__name',
        'listing_group__property__title',
        'asset__source_url',
    )
    readonly_fields = tuple(field.name for field in ArealistingPropertyAsset._meta.fields)


@admin.register(ArealistingSkippedUnit)
class ArealistingSkippedUnitAdmin(SourceReadOnlyAdmin):
    list_display = ('unit', 'skipped_by', 'reason', 'created_at')
    search_fields = (
        'unit__external_id',
        'unit__unit_number',
        'unit__project__name_en',
        'unit__project__name_ru',
        'reason',
    )
    readonly_fields = tuple(field.name for field in ArealistingSkippedUnit._meta.fields)


@admin.register(ArealistingSyncRun)
class ArealistingSyncRunAdmin(SourceReadOnlyAdmin):
    list_display = ('started_at', 'mode', 'status', 'finished_at', 'resource_names')
    list_filter = ('mode', 'status')
    search_fields = ('error',)
    readonly_fields = tuple(field.name for field in ArealistingSyncRun._meta.fields)

    @admin.display(description='Ресурсы')
    def resource_names(self, obj):
        return ', '.join(obj.resources or [])


@admin.register(ArealistingPriceReview)
class ArealistingPriceReviewAdmin(SourceReadOnlyAdmin):
    list_display = ('created_at', 'property_link', 'project', 'change_percent',
                    'status', 'reviewed_by', 'review_action')
    list_filter = ('status', 'created_at')
    search_fields = ('property__title', 'property__title_ru', 'project__name_en', 'project__name_ru')
    list_select_related = ('property', 'project', 'reviewed_by')
    readonly_fields = tuple(field.name for field in ArealistingPriceReview._meta.fields)

    def get_urls(self):
        return [path(
            '<int:review_id>/review/', self.admin_site.admin_view(self.review_view),
            name='arealisting_arealistingpricereview_review',
        )] + super().get_urls()

    @admin.display(description='Карточка')
    def property_link(self, obj):
        return format_html('<a href="{}">{}</a>',
                           reverse('admin:properties_property_change', args=[obj.property_id]),
                           obj.property)

    @admin.display(description='Действие')
    def review_action(self, obj):
        return format_html('<a href="{}">Проверить цену</a>',
                           reverse('admin:arealisting_arealistingpricereview_review', args=[obj.pk]))

    def review_view(self, request, review_id):
        review = get_object_or_404(
            ArealistingPriceReview.objects.select_related('property', 'project', 'group', 'reviewed_by'),
            pk=review_id,
        )
        if not self.has_view_or_change_permission(request, review):
            raise PermissionDenied
        can_decide = (
            self.has_change_permission(request, review)
            and request.user.has_perm('properties.change_property')
        )
        if request.method == 'POST':
            if not can_decide:
                raise PermissionDenied
            decision = request.POST.get('decision')
            try:
                if decision == 'approve':
                    approve_price_review(review.pk, user=request.user)
                    self.message_user(request, 'Новая цена применена к карточке.', messages.SUCCESS)
                elif decision == 'reject':
                    reject_price_review(review.pk, user=request.user)
                    self.message_user(request, 'Предложение цены отклонено. Прежняя цена сохранена.', messages.SUCCESS)
                else:
                    raise ValidationError('Выберите действие с предложением цены.')
            except ValidationError as exc:
                self.message_user(request, ' '.join(exc.messages), messages.ERROR)
            return HttpResponseRedirect(reverse(
                'admin:arealisting_arealistingpricereview_review', args=[review.pk],
            ))
        return TemplateResponse(request, 'admin/arealisting/price_review.html', {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': 'Проверка изменения цены',
            'review': review,
            'can_decide': can_decide and review.status == ArealistingPriceReview.Status.PENDING,
            'property_url': reverse('admin:properties_property_change', args=[review.property_id]),
        })


class SyncEventRunFilter(admin.SimpleListFilter):
    title = 'Запуск'
    parameter_name = 'run'

    def lookups(self, request, model_admin):
        return [
            (str(run.pk), run.started_at.strftime('%d.%m.%Y %H:%M'))
            for run in ArealistingSyncRun.objects.order_by('-started_at')[:10]
        ]

    def queryset(self, request, queryset):
        return queryset.filter(run_id=self.value()) if self.value() else queryset


@admin.register(ArealistingSyncEvent)
class ArealistingSyncEventAdmin(SourceReadOnlyAdmin):
    list_display = ('created_at', 'kind', 'project', 'unit', 'property_link', 'next_step', 'reviewed_at')
    list_filter = ('kind', SyncEventRunFilter)
    search_fields = ('unit__external_id', 'unit__unit_number',
                     'project__name_ru', 'project__name_en', 'property__title_ru')
    list_select_related = ('run', 'project', 'unit', 'property')
    readonly_fields = ('created_at', 'run', 'kind', 'project', 'unit', 'property',
                       'details_display', 'reviewed_at', 'reviewed_by')
    fields = readonly_fields
    ordering = ('-created_at', '-pk')

    @admin.display(description='Карточка')
    def property_link(self, obj):
        if not obj.property_id:
            return '—'
        return format_html('<a href="{}">{}</a>',
                           reverse('admin:properties_property_change', args=[obj.property_id]),
                           obj.property)

    @admin.display(description='Что сделать')
    def next_step(self, obj):
        if obj.kind == ArealistingSyncEvent.Kind.ACTIVE_WITHOUT_UNITS:
            return 'Проверить публикацию и предложения'
        if obj.kind == ArealistingSyncEvent.Kind.PRICE_SKIPPED:
            return obj.details.get('reason') or 'Проверить причину'
        if obj.kind == ArealistingSyncEvent.Kind.NEW_UNIT:
            return 'Проверить, нужна ли связь с карточкой'
        if obj.kind == ArealistingSyncEvent.Kind.UNIT_FIELDS:
            return 'Сверить характеристики предложения с карточкой'
        if obj.kind == ArealistingSyncEvent.Kind.SOLD:
            return 'Проверить связанные карточки'
        return 'Сверить изменение'

    @admin.display(description='Подробности')
    def details_display(self, obj):
        return format_html('<pre style="white-space:pre-wrap">{}</pre>',
                           json.dumps(obj.details, ensure_ascii=False, indent=2))


class PropertyHistoryFilter(admin.SimpleListFilter):
    title = 'Карточка'
    parameter_name = 'card'

    def lookups(self, request, model_admin):
        return ()

    def queryset(self, request, queryset):
        return queryset.filter(property_id=self.value()) if self.value() else queryset


@admin.register(ArealistingPropertyChange)
class ArealistingPropertyChangeAdmin(SourceReadOnlyAdmin):
    list_display = ('created_at', 'kind', 'property_link', 'project', 'actor', 'change_summary')
    list_filter = ('kind', 'created_at', PropertyHistoryFilter)
    search_fields = ('property__title', 'property__title_ru', 'project__name_en', 'project__name_ru')
    list_select_related = ('property', 'project', 'actor')
    readonly_fields = ('created_at', 'kind', 'property', 'project', 'actor', 'sync_run', 'details_display')
    fields = readonly_fields
    ordering = ('-created_at', '-pk')

    @admin.display(description='Карточка')
    def property_link(self, obj):
        url = reverse('admin:properties_property_change', args=[obj.property_id])
        return format_html('<a href="{}">{}</a>', url, obj.property)

    @admin.display(description='Что изменилось')
    def change_summary(self, obj):
        details = obj.details or {}
        fields = details.get('changed_fields') or []
        labels = [SOURCE_FIELD_LABELS.get(item['field'], item['field']) for item in fields]
        if obj.kind == ArealistingPropertyChange.Kind.MATCH:
            if details.get('units_before') != details.get('units_after'):
                labels.append('связанные предложения')
            if details.get('managed_added') or details.get('managed_removed'):
                labels.append('управление полями')
            if details.get('activity_change'):
                labels.append('активность')
        if obj.kind == ArealistingPropertyChange.Kind.DETACH:
            return 'Связь с комплексом удалена'
        if details.get('locked_fields_added'):
            return 'Защищено от синхронизации: ' + ', '.join(
                SOURCE_FIELD_LABELS.get(field, field) for field in details['locked_fields_added']
            )
        return ', '.join(labels) or 'Изменение связи'

    @admin.display(description='Подробности')
    def details_display(self, obj):
        details = obj.details or {}
        lines = []
        for item in details.get('changed_fields') or []:
            label = SOURCE_FIELD_LABELS.get(item['field'], item['field'])
            lines.append((label, item.get('before'), item.get('after')))
        activity = details.get('activity_change')
        if activity:
            lines.append(('Активность', activity['before'], activity['after']))
        if details.get('units_before') != details.get('units_after'):
            lines.append((
                'Предложения',
                ', '.join(details.get('unit_labels_before') or map(str, details.get('units_before') or [])) or 'нет',
                ', '.join(details.get('unit_labels_after') or map(str, details.get('units_after') or [])) or 'нет',
            ))
        for key, label in [('managed_added', 'Передано AREALISTING'),
                           ('managed_removed', 'Возвращено редактору'),
                           ('locked_fields_added', 'Защищено от синхронизации')]:
            fields = details.get(key) or []
            if fields:
                lines.append((label, '—', ', '.join(SOURCE_FIELD_LABELS.get(field, field) for field in fields)))
        if obj.kind == ArealistingPropertyChange.Kind.DETACH:
            lines.append(('Комплекс', details.get('project', '—'), 'Связь удалена'))
        return format_html('<ul>{}</ul>', format_html_join('', '<li><strong>{}</strong>: {} → {}</li>', lines))


@admin.register(ArealistingSyncState)
class ArealistingSyncStateAdmin(SourceReadOnlyAdmin):
    list_display = ('key', 'status', 'last_successful_sync_at', 'updated_at')
    list_filter = ('status',)
    readonly_fields = tuple(field.name for field in ArealistingSyncState._meta.fields)
