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
from django.utils.formats import date_format
from datetime import timedelta
from urllib.parse import urlencode
from urllib.parse import parse_qsl, urlsplit, urlunsplit

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
from apps.locations.models import District, Location

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

SYNC_RESOURCE_LABELS = {
    'projects': 'Комплексы', 'units': 'Предложения',
    'payment_plans': 'Планы оплаты', 'deletions': 'Удаления',
}


def _vue_preview_link(request, url):
    """Keep local Vue preview on links inside the AREALISTING workspace."""
    if not request or not (settings.DEBUG and request.GET.get('vue') == '1') or not url:
        return url
    parts = urlsplit(url)
    if not parts.path.startswith('/admin/arealisting/'):
        return url
    params = dict(parse_qsl(parts.query, keep_blank_values=True))
    params['vue'] = '1'
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), parts.fragment))


def _sync_resource_label(resource):
    return SYNC_RESOURCE_LABELS.get(str(resource), str(resource))


def _matching_action(request, project_id):
    required = ('arealisting.view_arealistingproject', 'arealisting.change_arealistingunit',
                'arealisting.add_arealistinglistinggroup',
                'arealisting.change_arealistinglistinggroup', 'properties.change_property')
    if project_id and request.user.has_perms(required):
        return {'label': 'Проверить выбранные предложения',
                'url': _vue_preview_link(request, f"{reverse('admin:arealisting_matching')}?{urlencode({'project': project_id})}")}
    return None


def _group_action(request, group, label='Настроить связь и защиту полей'):
    if group and request.user.has_perm('arealisting.view_arealistinglistinggroup'):
        return {'label': label, 'url': reverse(
            'admin:arealisting_arealistinglistinggroup_change', args=[group.pk],
        ) + ('?vue=1' if settings.DEBUG and request.GET.get('vue') == '1' else '')}
    return None


def _media_preview_vue_data(preview, *, preview_url, confirm_url, back_url):
    """Serializable bootstrap for the single-group Vue media review."""
    main_image = preview['main_image']
    main_asset = preview['main_asset']
    if preview['preferred_main_asset_id']:
        main_message = (f'Выбрано главное фото из источника: {main_asset}. '
                        'Оно станет главным после успешной загрузки. При ошибке сохранится текущее главное фото.')
    elif main_image and not preview['main_changes']:
        main_message = f'Сохранится текущее главное фото: {main_image.title or "без названия"}.'
    elif main_image:
        main_message = f'После импорта главным станет {main_image.title or "первое оставшееся фото"}.'
    elif main_asset:
        main_message = (f'Если загрузка пройдёт успешно, первым главным станет фото из источника: '
                        f'{main_asset}. Проверьте результат после импорта.')
    else:
        main_message = 'Главное фото пока не определено. Проверьте галерею после импорта.'
    group = preview['group']
    return {
        'group_name': group.name,
        'property_name': str(group.property),
        'property_url': reverse('admin:properties_property_change', args=[group.property_id]),
        'available': [{
            'id': item['asset'].pk, 'title': str(item['asset']),
            'url': item['asset'].source_url, 'role': item['role'],
            'selected': item['selected'], 'existing': bool(item['image']),
            'last_error': (item['asset'].last_error or '')[:120],
        } for item in preview['available']],
        'additions': len(preview['additions']), 'updates': len(preview['updates']),
        'removals': len(preview['removals']), 'manual_count': preview['manual_count'],
        'missing_removals': [item['image'].title or str(item['asset'])
                             for item in preview['missing_removals']],
        'preferred_main_asset_id': preview['preferred_main_asset_id'],
        'main_message': main_message,
        'fingerprint': preview['fingerprint'], 'can_import': preview['can_import'],
        'preview_url': preview_url, 'confirm_url': confirm_url, 'back_url': back_url,
    }


def _media_job_vue_data(group, job, *, can_retry, preferred_main_failed, vue_suffix=''):
    job_url = reverse('admin:arealisting_arealistinglistinggroup_media_job', args=[group.pk, job.pk])
    return {
        'id': job.pk, 'status': job.status, 'status_label': job.get_status_display(),
        'group_name': str(group), 'property_name': str(group.property) if group.property_id else '',
        'group_url': reverse('admin:arealisting_arealistinglistinggroup_change', args=[group.pk]) + vue_suffix,
        'property_url': (reverse('admin:properties_property_change', args=[group.property_id])
                         if group.property_id else ''),
        'preview_url': reverse('admin:arealisting_arealistinglistinggroup_preview_media', args=[group.pk]) + vue_suffix,
        'retry_url': reverse('admin:arealisting_arealistinglistinggroup_retry_media_job', args=[group.pk, job.pk]) + vue_suffix,
        'job_url': job_url + vue_suffix,
        'poll_url': f'{job_url}?format=json',
        'total': job.total, 'processed': job.processed,
        'totals': {key: (job.totals or {}).get(key) or 0 for key in ('created', 'updated', 'deleted', 'errors')},
        'error': job.error or '',
        'results': [{key: row.get(key) for key in ('asset_id', 'title', 'source_url', 'role', 'status', 'error')}
                    for row in (job.results or []) if isinstance(row, dict)],
        'preferred_main_asset_id': job.preferred_main_asset_id,
        'preferred_main_failed': preferred_main_failed, 'can_retry': can_retry,
    }


def _bulk_media_preview_vue_data(previews, *, action_url, back_url, vue_suffix=''):
    groups = []
    for preview in previews:
        group = preview['group']
        groups.append({
            'id': group.pk, 'name': group.name, 'property_name': str(group.property),
            'property_url': (reverse('admin:properties_property_change', args=[group.property_id])
                             if group.property_id else ''),
            'preview_url': reverse('admin:arealisting_arealistinglistinggroup_preview_media', args=[group.pk]) + vue_suffix,
            'available_count': len(preview['available']), 'selected_count': len(preview['selected_ids']),
            'additions': len(preview['additions']), 'updates': len(preview['updates']),
            'removals': len(preview['removals']), 'missing_removals': len(preview['missing_removals']),
            'manual_count': preview['manual_count'], 'can_import': preview['can_import'],
            'fingerprint': preview['fingerprint'],
            'sample_images': [{'url': item['asset'].source_url, 'title': str(item['asset'])}
                              for item in preview['available'] if item['selected']][:4],
        })
    return {'groups': groups, 'action_url': action_url, 'back_url': back_url,
            'vue_preview': bool(vue_suffix)}


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
        'source_vue': '1' if settings.DEBUG and data.get('source_vue') == '1' else '',
    }


def _review_queue_return_url(data, *, event_id=None):
    """Return only to known queue filters after a review action."""
    params = {}
    if data.get('return_state') == 'checked':
        params['state'] = 'checked'
    kind = data.get('return_kind', '')
    if kind in {value for value, _ in ArealistingSyncEvent.Kind.choices} and kind != ArealistingSyncEvent.Kind.PRICE_REVIEW:
        params['kind'] = kind
    page = str(data.get('return_page', ''))
    if page.isdigit() and int(page) > 0:
        params['page'] = page
    if settings.DEBUG and data.get('return_vue') == '1':
        params['vue'] = '1'
    url = reverse('admin:arealisting_review_queue')
    if params:
        url += '?' + urlencode(params)
    if event_id is not None:
        url += f'#event-{event_id}'
    return url


def _price_review_list_params(data):
    """Whitelisted list state carried through a price decision form."""
    if data.get('return_list') != '1':
        return {}
    status = data.get('return_status', '')
    allowed = {value for value, _ in ArealistingPriceReview.Status.choices}
    period = data.get('return_period', 'all')
    order = data.get('return_order', 'newest')
    page = str(data.get('return_page', ''))
    params = {
        'return_list': '1',
        'return_status': status if status in allowed else '',
        'return_period': period if period in ('all', '7d', '30d') else 'all',
        'return_q': data.get('return_q', '').strip()[:200],
        'return_order': order if order in ('newest', 'oldest', 'largest') else 'newest',
    }
    if page.isdigit() and int(page) > 0:
        params['return_page'] = page
    return params


def _asset_list_return_params(data):
    if data.get('return_list') != '1':
        return {}
    state = data.get('return_state', '')
    asset_type = data.get('return_type', '')
    activity = data.get('return_activity', '')
    page = str(data.get('return_page', ''))
    project = str(data.get('return_project', ''))
    params = {
        'return_list': '1',
        'return_state': state if state in ('error', 'downloaded', 'url') else '',
        'return_type': asset_type if asset_type in {value for value, _ in ArealistingAsset.AssetType.choices} else '',
        'return_activity': activity if activity in ('0', '1') else '',
        'return_q': data.get('return_q', '').strip()[:200],
        'return_project': project if project.isdigit() else '',
    }
    if page.isdigit() and int(page) > 0:
        params['return_page'] = page
    return params


def _location_mapping_return_params(data):
    mode = data.get('return_mode', '')
    confirmed = data.get('return_confirmed', '')
    deleted = data.get('return_deleted', '0')
    page = str(data.get('return_page', ''))
    params = {
        'is_confirmed__exact': confirmed if confirmed in ('0', '1') else '',
        'mapping_mode__exact': (mode if mode in {value for value, _ in ArealistingLocationMapping.MappingMode.choices}
                                else ''),
        'is_deleted__exact': deleted if deleted in ('0', '1', 'all') else '0',
        'q': data.get('return_q', '').strip()[:200],
    }
    if page.isdigit() and int(page) > 0:
        params['page'] = page
    return params


def _unit_return_params(data):
    status = data.get('return_status', '')
    linked = data.get('return_linked', '')
    enabled = data.get('return_enabled', '')
    deleted = data.get('return_deleted', '0')
    project = str(data.get('return_project', ''))
    page = str(data.get('return_page', ''))
    params = {
        'availability_status__exact': (status if status in {value for value, _ in ArealistingUnit.AvailabilityStatus.choices}
                                       else ''),
        'linked': linked if linked in ('0', '1') else '',
        'sync_enabled__exact': enabled if enabled in ('0', '1') else '',
        'is_deleted__exact': deleted if deleted in ('0', '1', 'all') else '0',
        'project': project if project.isdigit() else '',
        'q': data.get('return_q', '').strip()[:200],
    }
    if page.isdigit() and int(page) > 0:
        params['page'] = page
    return params


def _skipped_unit_return_params(data):
    project = str(data.get('return_project', ''))
    page = str(data.get('return_page', ''))
    params = {'project': project if project.isdigit() else '',
              'q': data.get('return_q', '').strip()[:200]}
    if page.isdigit() and int(page) > 0:
        params['page'] = page
    return params


def _payment_plan_return_params(data):
    project = str(data.get('return_project', ''))
    deleted = data.get('return_deleted', '0')
    page = str(data.get('return_page', ''))
    params = {'project': project if project.isdigit() else '',
              'q': data.get('return_q', '').strip()[:200],
              'is_deleted__exact': deleted if deleted in ('0', '1', 'all') else '0'}
    if page.isdigit() and int(page) > 0:
        params['page'] = page
    return params


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
    if source['source_vue']:
        params['vue'] = '1'
    return f"{reverse('admin:arealisting_unlinked')}?{urlencode(params)}"


def _workspace_back_url(project_id, data):
    params = {}
    query = data.get('return_q', '').strip()[:200]
    page = data.get('return_page', '')
    if query:
        params['q'] = query
    if str(page).isdigit():
        params['page'] = page
    if settings.DEBUG and data.get('vue') == '1':
        params['vue'] = '1'
    destination = reverse('admin:arealisting_arealistingproject_changelist')
    if params:
        destination += f'?{urlencode(params)}'
    return f'{destination}#project-{project_id}'


def price_report_context(project, request=None):
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
                     'review_url': (_vue_preview_link(request, reverse(
                         'admin:arealisting_arealistingpricereview_review', args=[row['review_id']],
                     ))
                                    if row.get('review_id') else ''),
                     'prices': [{'currency': currency, 'before': row['before'].get(field),
                                 'after': row.get('proposed', row['after']).get(field)}
                                for field, currency in [('price_sale_thb', 'THB'), ('price_sale_usd', 'USD'), ('price_sale_rub', 'RUB')]]})
    return {
        'price_report': rows,
        'price_report_run': run,
        'price_report_review_count': sum(row.get('status') == 'review' for row in rows),
    }


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
    pending_drafts_count = 0
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
        draft_queryset = (
            ArealistingListingGroup.objects.filter(
                catalog_origin=ArealistingListingGroup.CatalogOrigin.AREALISTING_DRAFT,
                property__isnull=False,
                property__is_active=False,
            )
        )
        pending_drafts_count = draft_queryset.count()
        drafts = draft_queryset.select_related('property', 'project').order_by('created_at')[:4]
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

    for item in work_items:
        item['url'] = _vue_preview_link(request, item['url'])
    for event in sync_events:
        event['url'] = _vue_preview_link(request, event['url'])

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
        'attention_actionable_count': (
            (unlinked['pending'] + pending_drafts_count
             if request.user.has_perm('properties.change_property') else 0)
            + (mapping_required if request.user.has_perm('arealisting.change_arealistinglocationmapping') else 0)
            + (asset_errors if request.user.has_perm('arealisting.view_arealistingasset') else 0)
        ),
        'work_items': work_items,
        'pending_price_reviews': pending_price_reviews,
        'pending_price_review_count': pending_price_review_count,
        'price_review_percent': settings.AREALISTING_PRICE_REVIEW_PERCENT,
        'price_reviews_url': reverse('admin:arealisting_arealistingpricereview_changelist'),
        'can_view_price_reviews': request.user.has_perm('arealisting.view_arealistingpricereview'),
        'sync_events': sync_events,
        'sync_event_count': sync_event_count,
        'sync_events_url': (_vue_preview_link(
            request, f"{reverse('admin:arealisting_arealistingsyncevent_changelist')}?run={latest_run.pk}"
        ) if latest_run else ''),
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
            (ArealistingPropertyAsset, 'Фото в карточках'),
            (ArealistingSkippedUnit, 'Пропущенные предложения'),
            (ArealistingSyncRun, 'История обновлений'),
            (ArealistingSyncEvent, 'События синхронизации'),
            (ArealistingPropertyChange, 'Изменения карточек'),
            (ArealistingPriceReview, 'Проверка изменений цен'),
            (ArealistingSyncState, 'Состояние синхронизации'),
        ):
            model_admin = self.admin_site._registry[model]
            if model_admin.has_view_or_change_permission(request):
                section_url = reverse(f'admin:{model._meta.app_label}_{model._meta.model_name}_changelist')
                if settings.DEBUG and request.GET.get('vue') == '1' and model in {
                    ArealistingUnit, ArealistingListingGroup, ArealistingLocationMapping,
                    ArealistingAsset, ArealistingSyncRun, ArealistingPropertyChange,
                    ArealistingSkippedUnit, ArealistingPaymentPlan,
                    ArealistingPriceReview, ArealistingSyncEvent, ArealistingSyncState,
                    ArealistingPropertyAsset,
                }:
                    section_url += '?vue=1'
                sections.append({'label': label, 'url': section_url})
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
            'shell_active': 'overview',
            'vue_preview': settings.DEBUG and request.GET.get('vue') == '1',
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

    def change_view(self, request, object_id, form_url='', extra_context=None):
        from .templatetags.arealisting_vite import matching_vue_available
        vue_preview = settings.DEBUG and request.GET.get('vue') == '1'
        if not ((settings.AREALISTING_VUE_ENABLED or vue_preview) and matching_vue_available()):
            return super().change_view(request, object_id, form_url, extra_context)
        if request.method != 'GET':
            raise PermissionDenied
        project = self.get_object(request, object_id)
        if project is None:
            raise Http404
        if not self.has_view_or_change_permission(request, project):
            raise PermissionDenied
        back_params = {'q': request.GET.get('return_q', '').strip()[:200]}
        return_page = str(request.GET.get('return_page', ''))
        if return_page.isdigit() and int(return_page) > 0:
            back_params['page'] = return_page
        if vue_preview:
            back_params['vue'] = '1'
        suffix = {'vue': '1'} if vue_preview else {}
        groups = project.listing_groups.all()
        gallery = [url for url in (project.gallery or [])
                   if isinstance(url, str) and url.startswith('https://')][:12]
        data = {
            'id': project.pk, 'name': str(project), 'external_id': project.external_id,
            'name_ru': project.name_ru, 'name_en': project.name_en,
            'developer': project.developer_name,
            'project_type': project.get_project_type_display() if project.project_type else '',
            'construction_status': project.construction_status,
            'completion_date': date_format(project.completion_date, 'd.m.Y')
                               if project.completion_date else '',
            'description_ru': project.description_ru,
            'description_en': project.description_en,
            'freehold': project.freehold_available, 'leasehold': project.leasehold_available,
            'maintenance_fee': str(project.maintenance_fee) if project.maintenance_fee is not None else '',
            'maintenance_fee_mode': project.maintenance_fee_mode,
            'sinking_fund': str(project.sinking_fund) if project.sinking_fund is not None else '',
            'sinking_fund_mode': project.sinking_fund_mode,
            'latitude': str(project.latitude) if project.latitude is not None else '',
            'longitude': str(project.longitude) if project.longitude is not None else '',
            'districts': json.dumps(project.districts or [], ensure_ascii=False, indent=2),
            'amenities': json.dumps(project.amenities or [], ensure_ascii=False, indent=2),
            'documents': json.dumps(project.documents or [], ensure_ascii=False, indent=2),
            'gallery': gallery, 'gallery_count': len(project.gallery or []),
            'available_units': project._available_units,
            'sold_units': project._sold_units,
            'group_count': groups.count(),
            'linked_count': groups.filter(property__isnull=False).count(),
            'payment_count': project.payment_plans.filter(is_deleted=False).count(),
            'asset_count': project.assets.filter(is_active=True).count(),
            'is_deleted': project.is_deleted,
            'vue_preview': vue_preview,
            'remote_updated_at': date_format(project.remote_updated_at, 'd.m.Y H:i')
                                 if project.remote_updated_at else '',
            'last_seen_at': date_format(project.last_seen_at, 'd.m.Y H:i')
                            if project.last_seen_at else '',
            'synced_at': date_format(project.synced_at, 'd.m.Y H:i'),
            'back_url': reverse('admin:arealisting_arealistingproject_changelist')
                        + '?' + urlencode(back_params),
            'matching_url': (reverse('admin:arealisting_matching')
                             + '?' + urlencode({'project': project.pk, **suffix})
                             if _matching_action(request, project.pk) else ''),
            'load_url': reverse('admin:arealisting_load_inventory', args=[project.pk])
                        if self.has_change_permission(request)
                        and request.user.has_perm('arealisting.change_arealistingunit') else '',
            'units_url': (reverse('admin:arealisting_arealistingunit_changelist')
                          + '?' + urlencode({'project': project.pk, **suffix})
                          if request.user.has_perm('arealisting.view_arealistingunit') else ''),
            'groups_url': (reverse('admin:arealisting_arealistinglistinggroup_changelist')
                           + '?' + urlencode({'project': project.pk, **suffix})
                           if request.user.has_perm('arealisting.view_arealistinglistinggroup') else ''),
            'payments_url': (reverse('admin:arealisting_arealistingpaymentplan_changelist')
                             + '?' + urlencode({'project': project.pk, **suffix})
                             if request.user.has_perm('arealisting.view_arealistingpaymentplan') else ''),
            'assets_url': (reverse('admin:arealisting_arealistingasset_changelist')
                           + '?' + urlencode({'project': project.pk, **suffix})
                           if request.user.has_perm('arealisting.view_arealistingasset') else ''),
            'card_photos_url': (reverse('admin:arealisting_arealistingpropertyasset_changelist')
                                + '?' + urlencode({'project': project.pk, **suffix})
                                if request.user.has_perm('arealisting.view_arealistingpropertyasset') else ''),
        }
        return TemplateResponse(request, 'admin/arealisting/project_detail_vue.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': 'Комплекс AREALISTING', 'shell_active': 'project',
            'vue_preview': vue_preview, 'project_detail_data': data,
        })

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
        context = {
            **self.admin_site.each_context(request),
            'title': 'Проверка изменений AREALISTING', 'opts': self.model._meta,
            'rows': rows, 'page': page, 'state': state, 'kind': kind,
            'kinds': [(value, label) for value, label in ArealistingSyncEvent.Kind.choices
                      if value != ArealistingSyncEvent.Kind.PRICE_REVIEW],
            'pending_reviews': pending_reviews, 'group_errors': group_errors,
            'can_mark_checked': request.user.has_perm('arealisting.change_arealistingsyncevent'),
        }
        from .templatetags.arealisting_vite import matching_vue_available
        vue_preview = settings.DEBUG and request.GET.get('vue') == '1'
        vue_available = matching_vue_available()
        use_vue = bool((settings.AREALISTING_VUE_ENABLED or vue_preview) and vue_available)
        preview_query = {'state': state, 'kind': kind, 'page': page.number, 'vue': '1'}
        context['vue_preview_url'] = (
            request.path + '?' + urlencode(preview_query)
            if settings.DEBUG and vue_available and not use_vue else ''
        )
        if use_vue:
            vue_suffix = {'vue': '1'} if vue_preview else {}
            context['vue_preview'] = vue_preview
            queue_url = reverse('admin:arealisting_review_queue')
            def page_url(number):
                return queue_url + '?' + urlencode({'state': state, 'kind': kind, 'page': number, **vue_suffix})
            context['shell_active'] = 'review'
            context['review_queue_data'] = {
                'state': state, 'kind': kind,
                'kinds': [{'value': value, 'label': label} for value, label in context['kinds']],
                'filter_url': queue_url, 'vue_preview': vue_preview,
                'return_fields': {'return_state': state, 'return_kind': kind,
                                  'return_page': str(page.number), 'return_vue': '1' if vue_preview else ''},
                'event_count': page.paginator.count,
                'page': {'number': page.number, 'total': page.paginator.num_pages,
                         'previous_url': page_url(page.previous_page_number()) if page.has_previous() else '',
                         'next_url': page_url(page.next_page_number()) if page.has_next() else ''},
                'can_mark_checked': context['can_mark_checked'],
                'price_list_url': reverse('admin:arealisting_arealistingpricereview_changelist')
                                  + '?status__exact=PENDING' + ('&vue=1' if vue_preview else ''),
                'price_reviews': [{
                    'id': review.pk, 'property': str(review.property),
                    'percent': str(review.change_percent),
                    'before': str((review.before or {}).get('price_sale_thb') or '—'),
                    'after': str((review.after or {}).get('price_sale_thb') or '—'),
                    'created_at': date_format(review.created_at, 'd.m.Y H:i'),
                    'url': reverse('admin:arealisting_arealistingpricereview_review', args=[review.pk])
                           + ('?vue=1' if vue_preview else ''),
                } for review in pending_reviews],
                'group_errors': [{
                    'id': entry['group'].pk, 'property': str(entry['group'].property),
                    'project': str(entry['group'].project), 'issues': entry['issues'],
                    'url': (reverse('admin:arealisting_arealistinglistinggroup_change', args=[entry['group'].pk])
                            + ('?vue=1' if vue_preview else '')),
                } for entry in group_errors],
                'events': [{
                    'id': row['event'].pk, 'kind': row['event'].get_kind_display(),
                    'title': str(row['event'].property or row['event'].project or 'Предложение AREALISTING'),
                    'created_at': date_format(row['event'].created_at, 'd.m.Y H:i'),
                    'unit': str(row['event'].unit) if row['event'].unit else '',
                    'detail': str(row['detail'] or ''), 'guidance': row['guidance'],
                    'field_changes': [{**change,
                                       'before': '—' if change['before'] is None else str(change['before']),
                                       'after': '—' if change['after'] is None else str(change['after']),
                                       'card_value': '—' if change['card_value'] is None else str(change['card_value'])}
                                      for change in row['field_changes']],
                    'reviewed_at': date_format(row['event'].reviewed_at, 'd.m.Y H:i') if row['event'].reviewed_at else '',
                    'reviewed_by': str(row['event'].reviewed_by) if row['event'].reviewed_by else '',
                    'url': row['url'], 'action': row['action'],
                    'checked_url': reverse('admin:arealisting_review_event', args=[row['event'].pk]),
                    'keep_url': reverse('admin:arealisting_keep_card_value', args=[row['event'].pk]),
                } for row in rows],
            }
        return TemplateResponse(request, 'admin/arealisting/review_queue_vue.html'
                                if use_vue else 'admin/arealisting/review_queue.html', context)

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
        return HttpResponseRedirect(_review_queue_return_url(request.POST))

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
            return HttpResponseRedirect(_review_queue_return_url(request.POST, event_id=event.pk))
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
        return HttpResponseRedirect(_review_queue_return_url(request.POST, event_id=event.pk))

    def unlinked_view(self, request):
        if not self.has_view_or_change_permission(request) or not request.user.has_perm('properties.change_property'):
            raise PermissionDenied
        base = Property.objects.filter(arealisting_group__isnull=True)
        state = 'manual' if request.GET.get('state') == 'manual' else 'pending'
        activity = request.GET.get('activity', 'all')
        if activity not in ('all', 'active', 'inactive'):
            activity = 'all'
        query = request.GET.get('q', '').strip()[:200]
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
        project_query = (submitted_project_query or '').strip()[:200]
        if request.GET.get('property', '').isdigit():
            selected = get_object_or_404(base, pk=request.GET['property'])
            if submitted_project_query is None:
                # Подскажем название в поле, но не будем автоматически
                # выводить десятки комплексов до явного поиска администратора.
                project_query = (
                    selected.complex_name_en or selected.complex_name_ru or ''
                ).strip()[:200]
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
        context = {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': 'Объекты Undersun без связи', 'state': state, 'query': query,
            'activity': activity, 'activity_counts': activity_counts,
            'pending_count': base.filter(arealisting_manual__isnull=True).count(),
            'manual_count': base.filter(arealisting_manual__isnull=False).count(),
            'page': property_page, 'property_cards': property_cards,
            'selected': selected, 'project_query': project_query, 'project_page': project_page,
            'can_load': self.has_change_permission(request) and request.user.has_perm('arealisting.change_arealistingunit'),
        }
        from .templatetags.arealisting_vite import matching_vue_available
        vue_preview = settings.DEBUG and request.GET.get('vue') == '1'
        vue_available = matching_vue_available()
        use_vue = bool((settings.AREALISTING_VUE_ENABLED or vue_preview) and vue_available)
        if settings.DEBUG and vue_available and not use_vue:
            preview_query = request.GET.copy()
            preview_query['vue'] = '1'
            context['vue_preview_url'] = request.path + '?' + preview_query.urlencode()
        if use_vue:
            base_url = reverse('admin:arealisting_unlinked')
            def url_for(**changes):
                params = {'state': state, 'activity': activity, 'q': query}
                if vue_preview:
                    params['vue'] = '1'
                params.update(changes)
                return base_url + '?' + urlencode(params)
            can_match = request.user.has_perms((
                'arealisting.view_arealistingproject', 'arealisting.change_arealistingunit',
                'arealisting.add_arealistinglistinggroup',
                'arealisting.change_arealistinglistinggroup', 'properties.change_property',
            ))
            source = {
                'property': selected.pk if selected else None,
                'source_state': state, 'source_activity': activity, 'source_q': query,
                'source_page': str(property_page.number), 'source_project_q': project_query,
            }
            if vue_preview:
                source['source_vue'] = '1'
            context['shell_active'] = 'unlinked'
            context['vue_preview'] = vue_preview
            context['unlinked_data'] = {
                'base_url': base_url, 'vue_preview': vue_preview,
                'state': state, 'activity': activity, 'query': query,
                'pending_count': context['pending_count'], 'manual_count': context['manual_count'],
                'activity_counts': activity_counts, 'result_count': property_page.paginator.count,
                'pending_url': url_for(state='pending'), 'manual_url': url_for(state='manual'),
                'activity_urls': {key: url_for(activity=key) for key in ('all', 'active', 'inactive')},
                'reset_search_url': url_for(q=''),
                'page': {'number': property_page.number, 'total': property_page.paginator.num_pages,
                         'previous_url': url_for(page=property_page.previous_page_number()) if property_page.has_previous() else '',
                         'next_url': url_for(page=property_page.next_page_number()) if property_page.has_next() else ''},
                'cards': [{
                    'id': card['property'].pk, 'title': str(card['property']),
                    'property_url': reverse('admin:properties_property_change', args=[card['property'].pk]),
                    'photo': card['photo'], 'is_active': card['property'].is_active,
                    'type': card['property'].property_type.get_name_display() if card['property'].property_type_id else '',
                    'bedrooms': str(card['property'].bedrooms) if card['property'].bedrooms is not None else '',
                    'area': str(card['property'].area_total) if card['property'].area_total is not None else '',
                    'complex': card['property'].complex_name_ru or card['property'].complex_name_en or 'Комплекс не указан',
                    'select_url': url_for(page=property_page.number, property=card['property'].pk),
                    'manual_url': reverse('admin:arealisting_manual_property', args=[card['property'].pk]),
                } for card in property_cards],
                'selected': ({
                    'id': selected.pk, 'title': str(selected), 'is_active': selected.is_active,
                    'close_url': url_for(page=property_page.number),
                    'project_query': project_query,
                    'project_search_fields': {'property': str(selected.pk), 'state': state,
                                              'activity': activity, 'q': query,
                                              'page': str(property_page.number),
                                              **({'vue': '1'} if vue_preview else {})},
                    'project_count': project_page.paginator.count if project_page else None,
                    'project_page': ({'number': project_page.number, 'total': project_page.paginator.num_pages,
                                     'previous_url': url_for(property=selected.pk, page=property_page.number,
                                                             project_q=project_query,
                                                             project_page=project_page.previous_page_number())
                                     if project_page.has_previous() else '',
                                     'next_url': url_for(property=selected.pk, page=property_page.number,
                                                         project_q=project_query,
                                                         project_page=project_page.next_page_number())
                                     if project_page.has_next() else ''} if project_page else None),
                    'projects': [{
                        'id': project.pk, 'title': str(project),
                        'type': 'Таунхаус' if project.project_type == 'HOUSE'
                                else (project.get_project_type_display() or 'Тип не указан'),
                        'developer': project.developer_name or 'Застройщик не указан',
                        'unit_count': project.unit_count, 'available_count': project.available_count,
                        'sold_count': project.sold_count,
                        'matching_url': reverse('admin:arealisting_matching') + '?'
                                        + urlencode({'project': project.pk, **source,
                                                     **({'vue': '1'} if vue_preview else {})}),
                        'load_url': reverse('admin:arealisting_load_inventory', args=[project.pk]),
                    } for project in project_page] if project_page else [],
                } if selected else None),
                'source_fields': source,
                'can_load': context['can_load'], 'can_match': can_match,
            }
        return TemplateResponse(request, 'admin/arealisting/unlinked_vue.html'
                                if use_vue else 'admin/arealisting/unlinked.html', context)

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
        if settings.DEBUG and request.POST.get('vue') == '1':
            params['vue'] = '1'
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
        vue_preview = settings.DEBUG and (request.GET.get('vue') == '1' or request.POST.get('vue') == '1')
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
            redirect_params = {'property': prop.pk}
            if vue_preview:
                redirect_params['vue'] = '1'
            return HttpResponseRedirect(
                f"{reverse('admin:arealisting_unlinked')}?{urlencode(redirect_params)}"
            )
        from .templatetags.arealisting_vite import matching_vue_available
        if (settings.AREALISTING_VUE_ENABLED or vue_preview) and matching_vue_available():
            suffix = '?vue=1' if vue_preview else ''
            data = {
                'property_title': str(prop), 'property_id': prop.pk,
                'project_title': str(group.project), 'group_id': group.pk,
                'unit_count': group.units.count(),
                'action_url': reverse('admin:arealisting_detach_property', args=[prop.pk]) + suffix,
                'group_url': reverse('admin:arealisting_arealistinglistinggroup_change', args=[group.pk]) + suffix,
                'property_url': reverse('admin:properties_property_change', args=[prop.pk]),
                'vue_preview': vue_preview,
            }
            return TemplateResponse(request, 'admin/arealisting/detach_property_vue.html', {
                **self.admin_site.each_context(request), 'opts': self.model._meta,
                'title': 'Отвязать карточку от AREALISTING', 'shell_active': 'groups',
                'project': group.project, 'vue_preview': vue_preview,
                'detach_property_data': data,
            })
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
                        ) + ('?vue=1' if settings.DEBUG and request.GET.get('vue') == '1' else '')
                          if media_job else ''),
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
                        ) + ('?vue=1' if settings.DEBUG and request.GET.get('vue') == '1' else ''),
                    }
                    for report in reports
                ],
            })
        project = ArealistingProject.objects.filter(pk=request.GET.get('project'), is_deleted=False).first() if request.GET.get('project', '').isdigit() else None
        if not project:
            from .templatetags.arealisting_vite import matching_vue_available
            vue_preview = settings.DEBUG and request.GET.get('vue') == '1'
            if (settings.AREALISTING_VUE_ENABLED or vue_preview) and matching_vue_available():
                query = request.GET.get('q', '').strip()[:200]
                projects = ArealistingProject.objects.filter(is_deleted=False)
                if query:
                    projects = projects.filter(
                        Q(name_ru__icontains=query) | Q(name_en__icontains=query)
                        | Q(developer_name__icontains=query) | Q(external_id__icontains=query)
                    )
                page = Paginator(projects.order_by('name_en', 'pk'), 24).get_page(request.GET.get('page'))
                suffix = '&vue=1' if vue_preview else ''
                return TemplateResponse(request, 'admin/arealisting/matching_select_vue.html', {
                    **self.admin_site.each_context(request),
                    'title': 'Выберите комплекс для сопоставления',
                    'opts': self.model._meta,
                    'shell_active': 'matching',
                    'vue_preview': vue_preview,
                    'matching_select_data': {
                        'query': query,
                        'page': page.number,
                        'pages': page.paginator.num_pages,
                        'base_url': reverse('admin:arealisting_matching'),
                        'vue_preview': vue_preview,
                        'rows': [{
                            'id': item.pk,
                            'name': str(item),
                            'developer': item.developer_name,
                            'external_id': item.external_id,
                            'url': f"{reverse('admin:arealisting_matching')}?project={item.pk}{suffix}",
                        } for item in page],
                    },
                })
            return HttpResponseRedirect(
                reverse('admin:arealisting_arealistingproject_changelist')
                + ('?vue=1' if settings.DEBUG and request.GET.get('vue') == '1' else '')
            )
        context = {**self.admin_site.each_context(request), 'title': 'Сопоставление с AREALISTING',
                   'opts': self.model._meta, 'projects': ArealistingProject.objects.filter(is_deleted=False),
                   'project': project, 'search': request.GET.get('q', ''), 'shell_active': 'matching'}
        if project:
            context.update(price_report_context(project, request))
            query = request.GET.get('q', '').strip()
            candidates = Property.objects.select_related('arealisting_group')
            if request.GET.get('property', '').isdigit():
                selected = get_object_or_404(Property, pk=request.GET['property'])
                context['selected_property'] = selected
                source = _source_navigation_params(request.GET)
                context.update(source)
                context['unlinked_back_url'] = _unlinked_back_url(selected.pk, source)
                done_params = {'state': source['source_state'], 'activity': source['source_activity']}
                if source['source_q']:
                    done_params['q'] = source['source_q']
                if source['source_page']:
                    done_params['page'] = source['source_page']
                if source['source_vue']:
                    done_params['vue'] = '1'
                context['unlinked_done_url'] = (
                    reverse('admin:arealisting_unlinked') + '?' + urlencode(done_params)
                )
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
        from .templatetags.arealisting_vite import matching_vue_available
        if settings.DEBUG and matching_vue_available():
            vue_query = request.GET.copy()
            vue_query['vue'] = '1'
            context['vue_preview_url'] = f'{request.path}?{vue_query.urlencode()}'
        use_vue = (
            settings.AREALISTING_VUE_ENABLED
            or (settings.DEBUG and request.GET.get('vue') == '1')
        )
        context['vue_preview'] = settings.DEBUG and request.GET.get('vue') == '1'
        if use_vue and project:
            if matching_vue_available():
                return TemplateResponse(request, 'admin/arealisting/matching_vue.html', context)
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
            + ('?vue=1' if settings.DEBUG and request.POST.get('vue') == '1' else '')
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


class ArealistingUnitSettingsForm(forms.ModelForm):
    class Meta:
        model = ArealistingUnit
        fields = ('listing_group', 'sync_enabled')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['listing_group'].queryset = ArealistingListingGroup.objects.filter(
            project_id=self.instance.project_id,
        ).select_related('project').order_by('name', 'pk')


@admin.register(ArealistingUnit)
class ArealistingUnitAdmin(SourceReadOnlyAdmin):
    change_list_template = 'admin/arealisting/arealistingunit/change_list.html'
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

    def changelist_view(self, request, extra_context=None):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        from .templatetags.arealisting_vite import matching_vue_available
        vue_preview = settings.DEBUG and request.GET.get('vue') == '1'
        vue_available = matching_vue_available()
        use_vue = bool((settings.AREALISTING_VUE_ENABLED or vue_preview) and vue_available)
        if not use_vue:
            context = {**(extra_context or {})}
            if settings.DEBUG and vue_available:
                params = request.GET.copy()
                params['vue'] = '1'
                context['vue_preview_url'] = request.path + '?' + params.urlencode()
            return super().changelist_view(request, context)

        status = request.GET.get('availability_status__exact', '')
        if status not in {value for value, _ in ArealistingUnit.AvailabilityStatus.choices}:
            status = ''
        linked = request.GET.get('linked', '')
        if linked not in ('', '0', '1'):
            linked = ''
        enabled = request.GET.get('sync_enabled__exact', '')
        if enabled not in ('', '0', '1'):
            enabled = ''
        deleted = request.GET.get('is_deleted__exact', '0')
        if deleted not in ('0', '1', 'all'):
            deleted = '0'
        query = request.GET.get('q', '').strip()[:200]
        project = str(request.GET.get('project', ''))
        if not project.isdigit():
            project = ''
        units = self.get_queryset(request).select_related(
            'project', 'listing_group', 'listing_group__property', 'skip_decision',
        )
        if deleted != 'all':
            units = units.filter(is_deleted=deleted == '1')
        if project:
            units = units.filter(project_id=int(project))
        if enabled:
            units = units.filter(sync_enabled=enabled == '1')
        if query:
            units = units.filter(
                Q(external_id__icontains=query) | Q(unit_number__icontains=query)
                | Q(project__name_en__icontains=query) | Q(project__name_ru__icontains=query)
            )
        counts = {'all': units.count(),
                  'available': units.filter(availability_status=ArealistingUnit.AvailabilityStatus.AVAILABLE).count(),
                  'sold': units.filter(availability_status=ArealistingUnit.AvailabilityStatus.SOLD).count(),
                  'unlinked': units.filter(listing_group__isnull=True).count()}
        if status:
            units = units.filter(availability_status=status)
        if linked:
            units = units.filter(listing_group__isnull=linked == '0')
        page = Paginator(units.order_by('project__name_en', 'unit_number', 'pk'), 30).get_page(request.GET.get('page'))
        list_url = reverse('admin:arealisting_arealistingunit_changelist')
        def filter_url(*, next_status=status, next_linked=linked, number=None):
            params = {'availability_status__exact': next_status, 'linked': next_linked,
                      'sync_enabled__exact': enabled, 'is_deleted__exact': deleted,
                      'project': project, 'q': query}
            if number is not None:
                params['page'] = number
            if vue_preview:
                params['vue'] = '1'
            return list_url + '?' + urlencode(params)
        can_view_skipped = request.user.has_perm('arealisting.view_arealistingskippedunit')
        data = {
            'filter_url': list_url, 'vue_preview': vue_preview,
            'status': status, 'linked': linked, 'enabled': enabled,
            'deleted': deleted, 'project': project, 'query': query, 'counts': counts,
            'status_urls': {'all': filter_url(next_status='', next_linked=''),
                            'available': filter_url(next_status='AVAILABLE', next_linked=''),
                            'sold': filter_url(next_status='SOLD', next_linked=''),
                            'unlinked': filter_url(next_status='', next_linked='0')},
            'result_count': page.paginator.count,
            'page': {'number': page.number, 'total': page.paginator.num_pages,
                     'previous_url': filter_url(number=page.previous_page_number()) if page.has_previous() else '',
                     'next_url': filter_url(number=page.next_page_number()) if page.has_next() else ''},
            'units': [{
                'id': unit.pk, 'number': unit.unit_number or unit.external_id,
                'project': str(unit.project), 'status': unit.get_availability_status_display() or 'Не указан',
                'availability_status': unit.availability_status, 'price': str(unit.price) if unit.price is not None else '',
                'currency': unit.currency, 'area': str(unit.internal_area_sqm) if unit.internal_area_sqm is not None else '',
                'group': str(unit.listing_group) if unit.listing_group_id else '',
                'property': str(unit.listing_group.property) if unit.listing_group_id and unit.listing_group.property_id else '',
                'sync_enabled': unit.sync_enabled, 'is_deleted': unit.is_deleted,
                'is_skipped': hasattr(unit, 'skip_decision'),
                'skipped_url': (reverse('admin:arealisting_arealistingskippedunit_change',
                                        args=[unit.skip_decision.pk]) + ('?vue=1' if vue_preview else '')
                                if can_view_skipped and hasattr(unit, 'skip_decision') else ''),
                'url': reverse('admin:arealisting_arealistingunit_change', args=[unit.pk])
                       + '?' + urlencode({'return_status': status, 'return_linked': linked,
                                          'return_enabled': enabled, 'return_deleted': deleted,
                                          'return_project': project, 'return_q': query,
                                          'return_page': page.number,
                                          **({'vue': '1'} if vue_preview else {})}),
            } for unit in page],
        }
        return TemplateResponse(request, 'admin/arealisting/unit_list_vue.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': 'Предложения AREALISTING', 'shell_active': 'units',
            'vue_preview': vue_preview, 'unit_list_data': data,
        })

    def change_view(self, request, object_id, form_url='', extra_context=None):
        from .templatetags.arealisting_vite import matching_vue_available
        vue_preview = settings.DEBUG and (request.GET.get('vue') == '1' or request.POST.get('vue') == '1')
        use_vue = bool((settings.AREALISTING_VUE_ENABLED or vue_preview) and matching_vue_available())
        if not use_vue:
            return super().change_view(request, object_id, form_url, extra_context)
        unit = self.get_object(request, object_id)
        if unit is None:
            raise Http404
        if not self.has_view_or_change_permission(request, unit):
            raise PermissionDenied
        can_change = self.has_change_permission(request, unit)
        form = ArealistingUnitSettingsForm(request.POST if request.method == 'POST' else None, instance=unit)
        return_params = _unit_return_params(request.POST if request.method == 'POST' else request.GET)
        return_fields = {'return_status': return_params['availability_status__exact'],
                         'return_linked': return_params['linked'],
                         'return_enabled': return_params['sync_enabled__exact'],
                         'return_deleted': return_params['is_deleted__exact'],
                         'return_project': return_params['project'], 'return_q': return_params['q'],
                         'return_page': return_params.get('page', '')}
        if request.method == 'POST':
            if not can_change:
                raise PermissionDenied
            old_group_id = unit.listing_group_id
            if form.is_valid():
                with transaction.atomic():
                    updated = form.save()
                    if old_group_id != updated.listing_group_id:
                        for group_id in {old_group_id, updated.listing_group_id} - {None}:
                            group = ArealistingListingGroup.objects.get(pk=group_id)
                            ArealistingSyncService.recalculate_listing_group(group)
                    self.log_change(request, updated, 'Изменены связь с группой или флаг синхронизации предложения.')
                self.message_user(request, 'Настройки предложения сохранены.', messages.SUCCESS)
                if old_group_id != updated.listing_group_id:
                    self.message_user(request, 'Связанные группы пересчитаны. Проверьте цену карточки.', messages.WARNING)
                return HttpResponseRedirect(request.path + '?' + urlencode({
                    **return_fields, **({'vue': '1'} if vue_preview else {}),
                }))
        if vue_preview:
            return_params['vue'] = '1'
        choices = [{'id': str(group.pk), 'label': str(group)}
                   for group in form.fields['listing_group'].queryset]
        values = form.cleaned_data if form.is_bound and form.is_valid() else (
            {'listing_group': form.data.get('listing_group', ''),
             'sync_enabled': form.data.get('sync_enabled') == 'on'}
            if form.is_bound else {'listing_group': unit.listing_group_id, 'sync_enabled': unit.sync_enabled}
        )
        group_value = values['listing_group']
        can_view_group = request.user.has_perm('arealisting.view_arealistinglistinggroup')
        can_view_skipped = request.user.has_perm('arealisting.view_arealistingskippedunit')
        can_view_property = request.user.has_perm('properties.view_property') or request.user.has_perm('properties.change_property')
        data = {
            'id': unit.pk, 'number': unit.unit_number or unit.external_id,
            'external_id': unit.external_id, 'project': str(unit.project),
            'availability_status': unit.availability_status,
            'status': unit.get_availability_status_display() or 'Не указан',
            'is_deleted': unit.is_deleted, 'can_change': can_change,
            'vue_preview': vue_preview, 'sync_enabled': values['sync_enabled'],
            'listing_group': str(getattr(group_value, 'pk', group_value) or ''),
            'group_choices': choices,
            'group_url': (reverse('admin:arealisting_arealistinglistinggroup_change', args=[unit.listing_group_id])
                          + ('?vue=1' if vue_preview else '')
                          if unit.listing_group_id and can_view_group else ''),
            'property': (str(unit.listing_group.property)
                         if unit.listing_group_id and unit.listing_group.property_id else ''),
            'property_url': (reverse('admin:properties_property_change', args=[unit.listing_group.property_id])
                             if unit.listing_group_id and unit.listing_group.property_id and can_view_property else ''),
            'is_skipped': hasattr(unit, 'skip_decision'),
            'skipped_url': (reverse('admin:arealisting_arealistingskippedunit_change',
                                    args=[unit.skip_decision.pk]) + ('?vue=1' if vue_preview else '')
                            if can_view_skipped and hasattr(unit, 'skip_decision') else ''),
            'skip_reason': unit.skip_decision.reason if hasattr(unit, 'skip_decision') else '',
            'project_url': reverse('admin:arealisting_arealistingproject_change', args=[unit.project_id])
                           if request.user.has_perm('arealisting.view_arealistingproject') else '',
            'source_fields': [
                {'label': 'Спальни', 'value': unit.bedrooms},
                {'label': 'Ванные', 'value': str(unit.bathrooms) if unit.bathrooms is not None else ''},
                {'label': 'Этаж', 'value': unit.floor},
                {'label': 'Площадь, м²', 'value': str(unit.internal_area_sqm) if unit.internal_area_sqm is not None else ''},
                {'label': 'Участок, м²', 'value': str(unit.plot_size_sqm) if unit.plot_size_sqm is not None else ''},
                {'label': 'Вид на море', 'value': ('Да' if unit.sea_view else 'Нет') if unit.sea_view is not None else ''},
                {'label': 'Тип', 'value': unit.property_type},
                {'label': 'Цена', 'value': (f'{unit.price} {unit.currency}' if unit.price is not None else '')},
                {'label': 'Цена за м²', 'value': str(unit.price_per_sqm) if unit.price_per_sqm is not None else ''},
                {'label': 'Плата за обслуживание', 'value': str(unit.maintenance_fee) if unit.maintenance_fee is not None else ''},
                {'label': 'Режим платы', 'value': unit.maintenance_fee_mode},
                {'label': 'Sinking fund', 'value': str(unit.sinking_fund) if unit.sinking_fund is not None else ''},
                {'label': 'Режим sinking fund', 'value': unit.sinking_fund_mode},
            ],
            'furnishing': json.dumps(unit.furnishing, ensure_ascii=False) if unit.furnishing else '',
            'gallery_count': len(unit.gallery or []),
            'last_seen_at': date_format(unit.last_seen_at, 'd.m.Y H:i') if unit.last_seen_at else '',
            'synced_at': date_format(unit.synced_at, 'd.m.Y H:i') if unit.synced_at else '',
            'errors': {key: [str(error) for error in errors] for key, errors in form.errors.items()},
            'save_url': request.path,
            'back_url': reverse('admin:arealisting_arealistingunit_changelist') + '?' + urlencode(return_params),
            'return_fields': return_fields,
        }
        return TemplateResponse(request, 'admin/arealisting/unit_detail_vue.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': 'Предложение AREALISTING', 'shell_active': 'units',
            'vue_preview': vue_preview, 'unit_detail_data': data,
        })


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


class ArealistingGroupSettingsForm(forms.Form):
    """Fields moderators may edit on the focused group screen."""
    name = forms.CharField(label='Название группы', max_length=255, required=False)
    is_active = forms.BooleanField(label='Активная группа', required=False)
    protected_fields = forms.MultipleChoiceField(required=False)

    def __init__(self, *args, group, **kwargs):
        self.group = group
        super().__init__(*args, **kwargs)
        managed = ordered_source_fields(set(group.source_owned_fields or []) | set(group.locked_fields or []))
        self.fields['protected_fields'].choices = [
            (field, SOURCE_FIELD_LABELS.get(field, field)) for field in managed
        ]

    def clean_name(self):
        name = self.cleaned_data['name']
        if ArealistingListingGroup.objects.filter(
            project_id=self.group.project_id, grouping_mode=self.group.grouping_mode, name=name,
        ).exclude(pk=self.group.pk).exists():
            raise forms.ValidationError('Группа с таким названием уже есть в этом комплексе.')
        return name


class ArealistingGroupCreateForm(forms.ModelForm):
    class Meta:
        model = ArealistingListingGroup
        fields = ('project', 'property', 'grouping_mode', 'name', 'is_active')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['project'].queryset = ArealistingProject.objects.filter(is_deleted=False)
        self.fields['property'].queryset = Property.objects.filter(arealisting_group__isnull=True)


@admin.register(ArealistingListingGroup)
class ArealistingListingGroupAdmin(InternalAdminMixin, admin.ModelAdmin):
    form = ArealistingListingGroupAdminForm
    change_list_template = 'admin/arealisting/arealistinglistinggroup/change_list.html'
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

    def changelist_view(self, request, extra_context=None):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        from .templatetags.arealisting_vite import matching_vue_available
        vue_preview = settings.DEBUG and (request.GET.get('vue') == '1' or request.POST.get('vue') == '1')
        vue_available = matching_vue_available()
        use_vue = bool((settings.AREALISTING_VUE_ENABLED or vue_preview) and vue_available)
        if not use_vue or request.method != 'GET':
            context = {**(extra_context or {})}
            if settings.DEBUG and vue_available and not use_vue:
                preview_query = request.GET.copy()
                preview_query['vue'] = '1'
                context['vue_preview_url'] = request.path + '?' + preview_query.urlencode()
            if request.method == 'POST' and vue_preview:
                # Django's ChangeList treats the local Vue switch as an invalid model lookup.
                request.GET = request.GET.copy()
                request.GET.pop('vue', None)
            return super().changelist_view(request, context)

        origin = request.GET.get('catalog_origin__exact', '')
        if origin not in {value for value, _ in ArealistingListingGroup.CatalogOrigin.choices}:
            origin = ''
        mode = request.GET.get('grouping_mode__exact', '')
        if mode not in {value for value, _ in ArealistingListingGroup.GroupingMode.choices}:
            mode = ''
        ready = request.GET.get('is_ready_for_publication__exact', '')
        if ready not in ('0', '1'):
            ready = ''
        activity = request.GET.get('is_active__exact', '')
        if activity not in ('0', '1'):
            activity = ''
        currency = request.GET.get('currency__exact', '').upper()
        if len(currency) != 3 or not currency.isalpha():
            currency = ''
        attention = request.GET.get('attention', '')
        if attention not in ('', 'issues', 'unlinked'):
            attention = ''
        project_id = str(request.GET.get('project', ''))
        if not project_id.isdigit():
            project_id = ''
        query = request.GET.get('q', '').strip()[:200]
        groups = self.get_queryset(request).select_related('project', 'property')
        if project_id:
            groups = groups.filter(project_id=int(project_id))
        if origin:
            groups = groups.filter(catalog_origin=origin)
        if mode:
            groups = groups.filter(grouping_mode=mode)
        if ready:
            groups = groups.filter(is_ready_for_publication=ready == '1')
        if activity:
            groups = groups.filter(is_active=activity == '1')
        if currency:
            groups = groups.filter(currency=currency)
        if query:
            groups = groups.filter(
                Q(name__icontains=query) | Q(project__name_en__icontains=query)
                | Q(project__name_ru__icontains=query) | Q(project__external_id__icontains=query)
            )
        counts = {
            'all': groups.count(),
            'issues': groups.exclude(validation_errors=[]).count(),
            'unlinked': groups.filter(property__isnull=True).count(),
            'ready': groups.filter(is_ready_for_publication=True).count(),
        }
        if attention == 'issues':
            groups = groups.exclude(validation_errors=[])
        elif attention == 'unlinked':
            groups = groups.filter(property__isnull=True)
        page = Paginator(groups.order_by('-updated_at', '-pk'), 30).get_page(request.GET.get('page'))
        list_url = reverse('admin:arealisting_arealistinglistinggroup_changelist')
        def filter_url(*, next_attention=attention, number=None):
            params = {'attention': next_attention, 'catalog_origin__exact': origin,
                      'grouping_mode__exact': mode,
                      'is_ready_for_publication__exact': ready,
                      'is_active__exact': activity, 'currency__exact': currency,
                      'project': project_id, 'q': query}
            if number is not None:
                params['page'] = number
            if vue_preview:
                params['vue'] = '1'
            return list_url + '?' + urlencode(params)
        can_change = self.has_change_permission(request)
        matching_perms = (
            'arealisting.view_arealistingproject', 'arealisting.change_arealistingunit',
            'arealisting.add_arealistinglistinggroup', 'arealisting.change_arealistinglistinggroup',
            'properties.change_property',
        )
        can_match = request.user.has_perms(matching_perms)
        can_view_property = request.user.has_perm('properties.view_property') or request.user.has_perm('properties.change_property')
        data = {
            'base_url': list_url, 'action_url': list_url + ('?vue=1' if vue_preview else ''),
            'overview_url': (reverse('admin:arealisting_arealistingproject_changelist')
                             + ('?vue=1' if vue_preview else '')
                             if request.user.has_perm('arealisting.view_arealistingproject')
                             or request.user.has_perm('arealisting.change_arealistingproject') else ''),
            'vue_preview': vue_preview, 'origin': origin, 'mode': mode,
            'ready': ready, 'activity': activity, 'currency': currency,
            'attention': attention, 'query': query, 'project': project_id, 'counts': counts,
            'attention_urls': {key: filter_url(next_attention=key) for key in ('', 'issues', 'unlinked')},
            'origins': [{'value': value, 'label': label} for value, label in ArealistingListingGroup.CatalogOrigin.choices],
            'modes': [{'value': value, 'label': label} for value, label in ArealistingListingGroup.GroupingMode.choices],
            'currencies': list(ArealistingListingGroup.objects.exclude(currency='').order_by('currency')
                               .values_list('currency', flat=True).distinct()),
            'result_count': page.paginator.count,
            'page': {'number': page.number, 'total': page.paginator.num_pages,
                     'previous_url': filter_url(number=page.previous_page_number()) if page.has_previous() else '',
                     'next_url': filter_url(number=page.next_page_number()) if page.has_next() else ''},
            'can_change': can_change, 'add_url': (reverse('admin:arealisting_arealistinglistinggroup_add')
                                                  + '?' + urlencode({'project': project_id, **({'vue': '1'} if vue_preview else {})})
                                                  if self.has_add_permission(request) and (
                                                      request.user.has_perm('arealisting.view_arealistingproject')
                                                      or request.user.has_perm('arealisting.change_arealistingproject')
                                                  ) else ''),
            'groups': [{
                'id': group.pk, 'title': str(group), 'project': str(group.project),
                'grouping': group.get_grouping_mode_display(),
                'origin': group.get_catalog_origin_display(),
                'property': str(group.property) if group.property else '',
                'property_url': reverse('admin:properties_property_change', args=[group.property_id])
                                if group.property_id and can_view_property else '',
                'available_units': group.available_units_count,
                'price': self.price_range(group), 'currency': group.currency,
                'is_ready': group.is_ready_for_publication, 'is_active': group.is_active,
                'updated_at': date_format(group.updated_at, 'd.m.Y H:i'),
                'issues': [_issue_guidance(error, group=group, request=request)
                           for error in (group.validation_errors or [])[:3]],
                'issue_count': len(group.validation_errors or []),
                'detail_url': (reverse('admin:arealisting_arealistinglistinggroup_change', args=[group.pk])
                               + ('?vue=1' if vue_preview else '')),
                'readiness_url': (reverse('admin:arealisting_arealistinglistinggroup_readiness', args=[group.pk])
                                  + ('?vue=1' if vue_preview else '')) if group.property_id else '',
                'preview_url': (reverse('admin:arealisting_arealistinglistinggroup_preview_media', args=[group.pk])
                                + ('?vue=1' if vue_preview else ''))
                               if group.property_id and can_change else '',
                'matching_url': (reverse('admin:arealisting_matching') + '?'
                                 + urlencode({'project': group.project_id, 'property': group.property_id,
                                              **({'vue': '1'} if vue_preview else {})}))
                                if group.property_id and can_match else '',
            } for group in page],
        }
        return TemplateResponse(request, 'admin/arealisting/group_list_vue.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': 'Связи AREALISTING с карточками', 'shell_active': 'groups',
            'vue_preview': vue_preview, 'group_list_data': data,
        })

    def save_model(self, request, obj, form, change):
        if change and 'property' in form.changed_data:
            ArealistingPriceReview.objects.filter(
                group=obj, status=ArealistingPriceReview.Status.PENDING,
            ).update(status=ArealistingPriceReview.Status.SUPERSEDED)
        super().save_model(request, obj, form, change)

    def add_view(self, request, form_url='', extra_context=None):
        from .templatetags.arealisting_vite import matching_vue_available
        vue_preview = settings.DEBUG and (request.GET.get('vue') == '1' or request.POST.get('vue') == '1')
        use_vue = bool((settings.AREALISTING_VUE_ENABLED or vue_preview) and matching_vue_available())
        if not use_vue:
            return super().add_view(request, form_url, extra_context)
        if not self.has_add_permission(request):
            raise PermissionDenied
        if not (request.user.has_perm('arealisting.view_arealistingproject')
                or request.user.has_perm('arealisting.change_arealistingproject')):
            raise PermissionDenied
        can_choose_property = (request.user.has_perm('properties.view_property')
                               or request.user.has_perm('properties.change_property'))
        if request.method == 'POST' and request.POST.get('property') and not can_choose_property:
            raise PermissionDenied

        if request.method == 'GET' and request.GET.get('lookup') in {'projects', 'properties'}:
            query = request.GET.get('q', '').strip()[:100]
            if request.GET['lookup'] == 'projects':
                matches = ArealistingProject.objects.filter(is_deleted=False)
                if query:
                    matches = matches.filter(
                        Q(name_en__icontains=query) | Q(name_ru__icontains=query)
                        | Q(external_id__icontains=query)
                    )
            else:
                if not can_choose_property:
                    raise PermissionDenied
                matches = Property.objects.filter(arealisting_group__isnull=True)
                if query:
                    matches = matches.filter(Q(title__icontains=query) | Q(slug__icontains=query))
            return JsonResponse({'results': [
                {'id': item.pk, 'label': str(item)} for item in matches.order_by('-pk')[:20]
            ]})

        initial = {}
        project_id = request.GET.get('project', '')
        if project_id.isdigit() and ArealistingProject.objects.filter(pk=project_id, is_deleted=False).exists():
            initial['project'] = int(project_id)
        form = ArealistingGroupCreateForm(request.POST if request.method == 'POST' else None, initial=initial)
        if request.method == 'POST' and form.is_valid():
            group = form.save()
            self.log_addition(request, group, 'Группа создана в рабочем пространстве AREALISTING.')
            self.message_user(request, 'Группа создана. Подберите предложения для неё на экране сопоставления.', messages.SUCCESS)
            return HttpResponseRedirect(
                reverse('admin:arealisting_arealistinglistinggroup_change', args=[group.pk])
                + ('?vue=1' if vue_preview else '')
            )

        project = form['project'].value()
        property_id = form['property'].value()
        selected_project = ArealistingProject.objects.filter(pk=project).first() if str(project or '').isdigit() else None
        selected_property = (Property.objects.filter(pk=property_id).first()
                             if can_choose_property and str(property_id or '').isdigit() else None)
        suffix = '?vue=1' if vue_preview else ''
        data = {
            'action_url': reverse('admin:arealisting_arealistinglistinggroup_add') + suffix,
            'lookup_url': reverse('admin:arealisting_arealistinglistinggroup_add') + suffix,
            'back_url': (reverse('admin:arealisting_arealistinglistinggroup_changelist') + '?'
                         + urlencode({'project': initial.get('project', ''), **({'vue': '1'} if vue_preview else {})})),
            'vue_preview': vue_preview,
            'can_choose_property': can_choose_property,
            'project': {'id': selected_project.pk, 'label': str(selected_project)} if selected_project else None,
            'property': {'id': selected_property.pk, 'label': str(selected_property)} if selected_property else None,
            'grouping_mode': form['grouping_mode'].value() or ArealistingListingGroup.GroupingMode.PROJECT,
            'name': form['name'].value() or '',
            'is_active': bool(form['is_active'].value()),
            'modes': [{'value': value, 'label': label} for value, label in ArealistingListingGroup.GroupingMode.choices],
            'errors': {key: [str(error) for error in errors] for key, errors in form.errors.items()},
        }
        return TemplateResponse(request, 'admin/arealisting/group_create_vue.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': 'Создать группу AREALISTING', 'shell_active': 'groups',
            'vue_preview': vue_preview, 'group_create_data': data,
        })

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
        from .templatetags.arealisting_vite import matching_vue_available
        vue_preview = settings.DEBUG and request.GET.get('vue') == '1'
        use_vue = bool((settings.AREALISTING_VUE_ENABLED or vue_preview) and matching_vue_available())
        if use_vue:
            if request.method != 'GET':
                raise PermissionDenied
            suffix = '?vue=1' if vue_preview else ''
            for check in report['checks']:
                if check['action_url'] and check['action'] in {'group', 'price_review'}:
                    check['action_url'] += suffix
                elif check['action_url'] and check['action'] == 'matching' and vue_preview:
                    check['action_url'] += '&vue=1'
            data = {
                'property_title': str(group.property),
                'property_id': group.property_id,
                'property_active': group.property.is_active,
                'project_title': str(group.project),
                'group_url': (reverse('admin:arealisting_arealistinglistinggroup_change', args=[group.pk])
                              + suffix),
                'property_url': actions['property'],
                'ready': report['ready'],
                'required_missing': report['required_missing'],
                'warnings': report['warnings'],
                'checks': report['checks'],
            }
            return TemplateResponse(request, 'admin/arealisting/readiness_vue.html', {
                **self.admin_site.each_context(request),
                'opts': self.model._meta, 'title': 'Проверка карточки перед публикацией',
                'shell_active': 'groups', 'vue_preview': vue_preview,
                'readiness_data': data,
            })
        return TemplateResponse(request, 'admin/arealisting/readiness.html', {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': 'Проверка карточки перед публикацией',
            'group': group, 'property': group.property,
            'report': report, 'property_url': actions['property'],
        })

    def change_view(self, request, object_id, form_url='', extra_context=None):
        group = self.get_object(request, object_id)
        from .templatetags.arealisting_vite import matching_vue_available
        vue_preview = settings.DEBUG and (request.GET.get('vue') == '1' or request.POST.get('vue') == '1')
        vue_available = matching_vue_available()
        use_vue = bool((settings.AREALISTING_VUE_ENABLED or vue_preview) and vue_available)
        if use_vue and group:
            if not self.has_view_or_change_permission(request, group):
                raise PermissionDenied
            can_change = self.has_change_permission(request, group)
            initial = {'name': group.name, 'is_active': group.is_active,
                       'protected_fields': group.locked_fields or []}
            form = ArealistingGroupSettingsForm(
                request.POST if request.method == 'POST' else None, group=group, initial=initial,
            )
            if request.method == 'POST':
                if not can_change:
                    raise PermissionDenied
                if form.is_valid():
                    group.name = form.cleaned_data['name']
                    group.is_active = form.cleaned_data['is_active']
                    group.locked_fields = ordered_source_fields(form.cleaned_data['protected_fields'])
                    group.save(update_fields=('name', 'is_active', 'locked_fields', 'updated_at'))
                    self.log_change(request, group, 'Изменены название, активность или защита полей группы.')
                    self.message_user(request, 'Настройки группы сохранены.', messages.SUCCESS)
                    detail_url = reverse('admin:arealisting_arealistinglistinggroup_change', args=[group.pk])
                    return HttpResponseRedirect(detail_url + ('?vue=1' if vue_preview else ''))
            return self._vue_group_detail(request, group, form, can_change, vue_preview)

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

    def _vue_group_detail(self, request, group, form, can_change, vue_preview):
        from .services.media import candidate_media_assets, preview_group_media

        units = list(group.units.all())
        candidates = candidate_media_assets(group.project, units)
        media_preview = preview_group_media(group.pk, enable=True) if group.property_id else None
        media_errors = [asset for asset, _role in candidates if asset.last_error]
        latest_job = group.media_jobs.order_by('-created_at').first()
        suffix = '?vue=1' if vue_preview else ''
        can_view_property = (request.user.has_perm('properties.view_property')
                             or request.user.has_perm('properties.change_property'))
        can_match = request.user.has_perms((
            'arealisting.view_arealistingproject', 'arealisting.change_arealistingunit',
            'arealisting.add_arealistinglistinggroup', 'arealisting.change_arealistinglistinggroup',
            'properties.change_property',
        ))
        settings_values = form.cleaned_data if form.is_bound and form.is_valid() else (
            {'name': form.data.get('name', ''), 'is_active': form.data.get('is_active') == 'on',
             'protected_fields': form.data.getlist('protected_fields')}
            if form.is_bound else form.initial
        )
        data = {
            'id': group.pk, 'title': str(group), 'project': str(group.project),
            'grouping': group.get_grouping_mode_display(), 'origin': group.get_catalog_origin_display(),
            'property': str(group.property) if group.property_id else '',
            'property_url': (reverse('admin:properties_property_change', args=[group.property_id])
                             if group.property_id and can_view_property else ''),
            'available_units': group.available_units_count, 'price': self.price_range(group),
            'currency': group.currency, 'is_ready': group.is_ready_for_publication,
            'updated_at': date_format(group.updated_at, 'd.m.Y H:i'),
            'issues': [_issue_guidance(error, group=group, request=request)
                       for error in (group.validation_errors or [])],
            'can_change': can_change, 'vue_preview': vue_preview,
            'name': settings_values['name'], 'is_active': settings_values['is_active'],
            'protected_fields': settings_values['protected_fields'],
            'protection_choices': [{'value': value, 'label': label}
                                   for value, label in form.fields['protected_fields'].choices],
            'errors': {key: [str(error) for error in errors]
                       for key, errors in form.errors.items()},
            'save_url': reverse('admin:arealisting_arealistinglistinggroup_change', args=[group.pk]),
            'back_url': reverse('admin:arealisting_arealistinglistinggroup_changelist') + suffix,
            'readiness_url': (reverse('admin:arealisting_arealistinglistinggroup_readiness', args=[group.pk])
                              + suffix if group.property_id else ''),
            'detach_url': (reverse('admin:arealisting_detach_property', args=[group.property_id]) + suffix
                           if group.property_id and request.user.has_perm('properties.change_property')
                           and request.user.has_perm('arealisting.change_arealistinglistinggroup')
                           and request.user.has_perm('arealisting.delete_arealistinglistinggroup') else ''),
            'preview_url': (reverse('admin:arealisting_arealistinglistinggroup_preview_media', args=[group.pk])
                            + suffix if can_change and group.property_id and media_preview
                            and (media_preview['available'] or media_preview['removals']) else ''),
            'matching_url': (reverse('admin:arealisting_matching') + '?' + urlencode({
                'project': group.project_id, 'property': group.property_id or '',
                **({'vue': '1'} if vue_preview else {}),
            }) if can_match else ''),
            'history_url': (reverse('admin:arealisting_arealistingpropertychange_changelist')
                            + '?' + urlencode({'card': group.property_id,
                                               **({'vue': '1'} if vue_preview else {})})
                            if group.property_id and request.user.has_perm('arealisting.view_arealistingpropertychange')
                            else ''),
            'media_candidate_count': len(candidates),
            'media_link_count': (group.property_assets.filter(property_image__isnull=False).count()
                                 if group.property_id else 0),
            'media_error_count': len(media_errors),
            'media_errors': ([{'title': str(asset), 'error': asset.last_error[:160],
                              'url': reverse('admin:arealisting_arealistingasset_change', args=[asset.pk]) + suffix}
                             for asset in media_errors[:10]]
                             if request.user.has_perm('arealisting.view_arealistingasset') else []),
            'latest_job': ({'status': latest_job.get_status_display(),
                            'url': reverse('admin:arealisting_arealistinglistinggroup_media_job',
                                           args=[group.pk, latest_job.pk]) + suffix}
                           if latest_job else None),
        }
        return TemplateResponse(request, 'admin/arealisting/group_detail_vue.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': 'Группа AREALISTING', 'shell_active': 'groups',
            'vue_preview': vue_preview, 'group_detail_data': data,
        })

    def preview_media_view(self, request, object_id):
        from .services.media import preview_group_media
        from .templatetags.arealisting_vite import matching_vue_available

        group = get_object_or_404(ArealistingListingGroup, pk=object_id, property__isnull=False)
        if not self.has_change_permission(request, group):
            raise PermissionDenied
        selected_ids = request.POST.getlist('asset') if request.method == 'POST' else None
        try:
            preview = preview_group_media(group.pk, enable=True, selected_asset_ids=selected_ids,
                                          preferred_main_asset_id=request.POST.get('preferred_main_asset_id') if request.method == 'POST' else None)
        except ValidationError:
            self.message_user(request, 'Список фото изменился. Выберите изображения заново.', messages.WARNING)
            preview_url = reverse('admin:arealisting_arealistinglistinggroup_preview_media', args=[group.pk])
            if settings.DEBUG and request.GET.get('vue') == '1':
                preview_url += '?vue=1'
            return HttpResponseRedirect(preview_url)
        vue_preview = settings.DEBUG and request.GET.get('vue') == '1'
        use_vue = bool((settings.AREALISTING_VUE_ENABLED or vue_preview) and matching_vue_available())
        vue_suffix = '?vue=1' if vue_preview else ''
        preview_url = reverse('admin:arealisting_arealistinglistinggroup_preview_media', args=[group.pk]) + vue_suffix
        confirm_url = reverse('admin:arealisting_arealistinglistinggroup_import_media', args=[group.pk]) + vue_suffix
        back_url = reverse('admin:arealisting_arealistinglistinggroup_change', args=[group.pk]) + vue_suffix
        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': 'Проверка импорта фото AREALISTING',
            'previews': [preview],
            'preview_url': preview_url,
            'confirm_url': confirm_url,
            'back_url': back_url,
            'shell_active': 'media', 'project': group.project,
            'vue_preview_url': preview_url if settings.DEBUG and not vue_preview and matching_vue_available() else '',
        }
        if use_vue:
            context['media_preview_data'] = _media_preview_vue_data(
                preview, preview_url=preview_url, confirm_url=confirm_url, back_url=back_url,
            )
        return TemplateResponse(request, 'admin/arealisting/media_preview_vue.html'
                                if use_vue else 'admin/arealisting/media_preview.html', context)

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
            preview_url = reverse('admin:arealisting_arealistinglistinggroup_preview_media', args=[group.pk])
            if settings.DEBUG and request.GET.get('vue') == '1':
                preview_url += '?vue=1'
            if request.POST.get('selection_confirmed') != '1':
                self.message_user(request, 'Сначала выберите фото на странице предпросмотра.', messages.WARNING)
                return HttpResponseRedirect(preview_url)
            selected_ids = request.POST.getlist('asset')
            try:
                preview = preview_group_media(
                    group.pk, enable=True, selected_asset_ids=selected_ids,
                    preferred_main_asset_id=request.POST.get('preferred_main_asset_id'),
                )
            except ValidationError:
                self.message_user(request, 'Список фото изменился. Выберите изображения заново.', messages.WARNING)
                return HttpResponseRedirect(preview_url)
            if request.POST.get('preview_fingerprint') != preview['fingerprint']:
                self.message_user(request, 'Состав фото изменился. Проверьте обновлённый предпросмотр.', messages.WARNING)
                return self.preview_media_view(request, object_id)
            active_job = group.media_jobs.filter(
                status__in=(ArealistingMediaJob.Status.PENDING,
                            ArealistingMediaJob.Status.RUNNING),
            ).order_by('-pk').first()
            if active_job:
                self.message_user(request, 'Импорт этой группы уже выполняется. Дождитесь результата.', messages.WARNING)
                job_url = reverse(
                    'admin:arealisting_arealistinglistinggroup_media_job',
                    args=[group.pk, active_job.pk],
                )
                return HttpResponseRedirect(job_url + ('?vue=1' if settings.DEBUG and request.GET.get('vue') == '1' else ''))
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
                    job_url = reverse(
                        'admin:arealisting_arealistinglistinggroup_media_job',
                        args=[group.pk, jobs[0].pk],
                    )
                    return HttpResponseRedirect(job_url + ('?vue=1' if settings.DEBUG and request.GET.get('vue') == '1' else ''))
        return HttpResponseRedirect(reverse(
            'admin:arealisting_arealistinglistinggroup_change', args=[group.pk]
        ) + ('?vue=1' if settings.DEBUG and request.GET.get('vue') == '1' else ''))

    def media_job_view(self, request, object_id, job_id):
        from .services.media_jobs import recover_stale_media_jobs
        from .templatetags.arealisting_vite import matching_vue_available

        recover_stale_media_jobs()
        group = get_object_or_404(ArealistingListingGroup, pk=object_id)
        if not self.has_view_or_change_permission(request, group):
            raise PermissionDenied
        job = get_object_or_404(ArealistingMediaJob, pk=job_id, group=group)
        failed_asset_ids = [row['asset_id'] for row in job.results if row['status'] == 'error']
        preferred_main_failed = any(row['asset_id'] == job.preferred_main_asset_id
                                    and row['status'] == 'error' for row in job.results)
        can_retry = bool(failed_asset_ids and self.has_change_permission(request, group)
                         and job.status in (ArealistingMediaJob.Status.PARTIAL,
                                            ArealistingMediaJob.Status.FAILED))
        vue_preview = settings.DEBUG and request.GET.get('vue') == '1'
        job_data = _media_job_vue_data(
            group, job, can_retry=can_retry, preferred_main_failed=preferred_main_failed,
            vue_suffix='?vue=1' if vue_preview else '',
        )
        if request.GET.get('format') == 'json':
            response = JsonResponse(job_data)
            response['Cache-Control'] = 'no-store'
            return response
        use_vue = bool((settings.AREALISTING_VUE_ENABLED or vue_preview) and matching_vue_available())
        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': f'Импорт фото #{job.pk}',
            'group': group,
            'job': job,
            'preferred_main_failed': preferred_main_failed,
            'failed_asset_ids': failed_asset_ids,
            'can_retry': can_retry,
            'media_job_data': job_data if use_vue else None,
            'shell_active': 'media', 'project': group.project,
            'vue_job_url': (job_data['job_url'] + '?vue=1'
                            if settings.DEBUG and not vue_preview and matching_vue_available() else ''),
        }
        return TemplateResponse(request, 'admin/arealisting/media_job_vue.html'
                                if use_vue else 'admin/arealisting/media_job.html', context)

    @method_decorator(require_POST)
    def retry_media_job_view(self, request, object_id, job_id):
        from .services.media_jobs import queue_media_job, start_media_worker

        vue_suffix = '?vue=1' if settings.DEBUG and request.GET.get('vue') == '1' else ''
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
            ) + vue_suffix)
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
            ) + vue_suffix)
        if created:
            try:
                start_media_worker(limit=1)
            except OSError:
                self.message_user(request, 'Задание сохранено, но обработчик не запустился. Проверьте журнал сервера.', messages.ERROR)
        return HttpResponseRedirect(reverse(
            'admin:arealisting_arealistinglistinggroup_media_job', args=[group.pk, job.pk]
        ) + vue_suffix)

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
        from .templatetags.arealisting_vite import matching_vue_available

        if queryset.count() > 10:
            self.message_user(
                request,
                'За один запуск можно обработать не более 10 групп.',
                messages.ERROR,
            )
            return
        previews = [preview_group_media(group.pk, enable=True) for group in queryset]
        fingerprints = {str(preview['group'].pk): preview['fingerprint'] for preview in previews}
        vue_preview = settings.DEBUG and request.POST.get('vue') == '1'
        vue_available = matching_vue_available()
        use_vue = bool((settings.AREALISTING_VUE_ENABLED or vue_preview) and vue_available)
        vue_suffix = '?vue=1' if vue_preview else ''
        list_url = reverse('admin:arealisting_arealistinglistinggroup_changelist')

        def render_bulk_preview():
            context = {
                **self.admin_site.each_context(request),
                'opts': self.model._meta,
                'title': 'Проверка импорта фото AREALISTING',
                'previews': previews, 'bulk': True,
                'back_url': list_url + vue_suffix, 'shell_active': 'media',
                'vue_bulk_available': bool(settings.DEBUG and vue_available and not vue_preview),
            }
            if use_vue:
                context['bulk_media_preview_data'] = _bulk_media_preview_vue_data(
                    previews, action_url=list_url, back_url=list_url + vue_suffix, vue_suffix=vue_suffix,
                )
            return TemplateResponse(request, 'admin/arealisting/media_preview_bulk_vue.html'
                                    if use_vue else 'admin/arealisting/media_preview.html', context)

        if request.POST.get('confirm_media_import') != '1':
            return render_bulk_preview()
        if any(request.POST.get(f'fingerprint_{pk}') != fingerprint
               for pk, fingerprint in fingerprints.items()):
            self.message_user(request, 'Состав фото изменился. Проверьте обновлённый предпросмотр.', messages.WARNING)
            return render_bulk_preview()
        queryset = [preview['group'] for preview in previews if preview['can_import']]
        if not queryset:
            self.message_user(request, 'Нет подходящих фото для импорта.', messages.WARNING)
            return
        jobs = self._queue_media_groups(request, queryset)
        if len(jobs) == 1:
            return HttpResponseRedirect(reverse(
                'admin:arealisting_arealistinglistinggroup_media_job',
                args=[jobs[0].group_id, jobs[0].pk],
            ) + vue_suffix)
        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': 'Фото поставлены в очередь',
            'jobs': jobs,
            'shell_active': 'media',
        }
        if use_vue:
            context['queued_media_data'] = {
                'jobs': [{'id': job.pk, 'group_name': str(job.group),
                          'url': reverse('admin:arealisting_arealistinglistinggroup_media_job',
                                         args=[job.group_id, job.pk]) + vue_suffix} for job in jobs],
                'back_url': list_url + vue_suffix,
            }
        return TemplateResponse(request, 'admin/arealisting/media_jobs_queued_vue.html'
                                if use_vue else 'admin/arealisting/media_jobs_queued.html', context)

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


class ArealistingLocationMappingForm(forms.ModelForm):
    class Meta:
        model = ArealistingLocationMapping
        fields = ('mapping_mode', 'district', 'location', 'is_confirmed')


@admin.register(ArealistingLocationMapping)
class ArealistingLocationMappingAdmin(InternalAdminMixin, admin.ModelAdmin):
    change_list_template = 'admin/arealisting/arealistinglocationmapping/change_list.html'

    def has_add_permission(self, request):
        # Source locations are created by project sync with their external_id.
        return False

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

    def changelist_view(self, request, extra_context=None):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        from .templatetags.arealisting_vite import matching_vue_available
        vue_preview = settings.DEBUG and request.GET.get('vue') == '1'
        vue_available = matching_vue_available()
        use_vue = bool((settings.AREALISTING_VUE_ENABLED or vue_preview) and vue_available)
        if not use_vue:
            context = {**(extra_context or {})}
            if settings.DEBUG and vue_available:
                params = request.GET.copy()
                params['vue'] = '1'
                context['vue_preview_url'] = request.path + '?' + params.urlencode()
            return super().changelist_view(request, context)

        mode = request.GET.get('mapping_mode__exact', '')
        if mode not in {value for value, _ in ArealistingLocationMapping.MappingMode.choices}:
            mode = ''
        confirmed = request.GET.get('is_confirmed__exact', '')
        if confirmed not in ('0', '1'):
            confirmed = ''
        deleted = request.GET.get('is_deleted__exact', '0')
        if deleted not in ('0', '1', 'all'):
            deleted = '0'
        query = request.GET.get('q', '').strip()[:200]
        mappings = self.get_queryset(request).select_related('district', 'location')
        if deleted != 'all':
            mappings = mappings.filter(is_deleted=deleted == '1')
        if mode:
            mappings = mappings.filter(mapping_mode=mode)
        if query:
            mappings = mappings.filter(
                Q(source_name__icontains=query) | Q(external_id__icontains=query)
                | Q(description_en__icontains=query) | Q(description_ru__icontains=query)
            )
        counts = {'all': mappings.count(), 'pending': mappings.filter(is_confirmed=False).count(),
                  'confirmed': mappings.filter(is_confirmed=True).count()}
        if confirmed:
            mappings = mappings.filter(is_confirmed=confirmed == '1')
        page = Paginator(mappings.order_by('is_confirmed', 'source_name', 'pk'), 30).get_page(request.GET.get('page'))
        list_url = reverse('admin:arealisting_arealistinglocationmapping_changelist')
        def filter_url(*, next_confirmed=confirmed, number=None):
            params = {'is_confirmed__exact': next_confirmed, 'mapping_mode__exact': mode,
                      'is_deleted__exact': deleted, 'q': query}
            if number is not None:
                params['page'] = number
            if vue_preview:
                params['vue'] = '1'
            return list_url + '?' + urlencode(params)
        data = {
            'filter_url': list_url, 'vue_preview': vue_preview, 'mode': mode,
            'sync_overview_url': (reverse('admin:arealisting_arealistingproject_changelist')
                                  + ('?vue=1' if vue_preview else '')
                                  if request.user.has_perm('arealisting.change_arealistingproject') else ''),
            'confirmed': confirmed, 'deleted': deleted, 'query': query, 'counts': counts,
            'confirmed_urls': {key: filter_url(next_confirmed=key) for key in ('', '0', '1')},
            'modes': [{'value': value, 'label': label}
                      for value, label in ArealistingLocationMapping.MappingMode.choices],
            'result_count': page.paginator.count,
            'page': {'number': page.number, 'total': page.paginator.num_pages,
                     'previous_url': filter_url(number=page.previous_page_number()) if page.has_previous() else '',
                     'next_url': filter_url(number=page.next_page_number()) if page.has_next() else ''},
            'mappings': [{
                'id': mapping.pk, 'source_name': str(mapping), 'source_type': mapping.source_type,
                'external_id': mapping.external_id, 'parent_external_id': mapping.parent_external_id,
                'mode': mapping.get_mapping_mode_display(),
                'target': (str(mapping.location) if mapping.location_id else
                           str(mapping.district) if mapping.district_id else ''),
                'is_confirmed': mapping.is_confirmed, 'is_deleted': mapping.is_deleted,
                'synced_at': date_format(mapping.synced_at, 'd.m.Y H:i') if mapping.synced_at else '',
                'url': reverse('admin:arealisting_arealistinglocationmapping_change', args=[mapping.pk])
                       + '?' + urlencode({'return_confirmed': confirmed, 'return_mode': mode,
                                          'return_deleted': deleted, 'return_q': query,
                                          'return_page': page.number,
                                          **({'vue': '1'} if vue_preview else {})}),
            } for mapping in page],
        }
        return TemplateResponse(request, 'admin/arealisting/location_mapping_list_vue.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': 'Сопоставление локаций AREALISTING', 'shell_active': 'locations',
            'vue_preview': vue_preview, 'location_mapping_list_data': data,
        })

    def change_view(self, request, object_id, form_url='', extra_context=None):
        from .templatetags.arealisting_vite import matching_vue_available
        vue_preview = settings.DEBUG and (request.GET.get('vue') == '1' or request.POST.get('vue') == '1')
        use_vue = bool((settings.AREALISTING_VUE_ENABLED or vue_preview) and matching_vue_available())
        if not use_vue:
            return super().change_view(request, object_id, form_url, extra_context)
        mapping = self.get_object(request, object_id)
        if mapping is None:
            raise Http404
        if not self.has_view_or_change_permission(request, mapping):
            raise PermissionDenied
        can_change = self.has_change_permission(request, mapping)
        form = ArealistingLocationMappingForm(
            request.POST if request.method == 'POST' else None, instance=mapping,
        )
        return_params = _location_mapping_return_params(request.POST if request.method == 'POST' else request.GET)
        return_fields = {'return_confirmed': return_params['is_confirmed__exact'],
                         'return_mode': return_params['mapping_mode__exact'],
                         'return_deleted': return_params['is_deleted__exact'],
                         'return_q': return_params['q'],
                         'return_page': return_params.get('page', '')}
        if request.method == 'POST':
            if not can_change:
                raise PermissionDenied
            if form.is_valid():
                updated = form.save()
                self.log_change(request, updated, 'Изменено сопоставление локации AREALISTING.')
                self.message_user(request, 'Сопоставление локации сохранено.', messages.SUCCESS)
                return HttpResponseRedirect(request.path + '?' + urlencode({
                    **return_fields, **({'vue': '1'} if vue_preview else {}),
                }))

        if vue_preview:
            return_params['vue'] = '1'
        back_url = reverse('admin:arealisting_arealistinglocationmapping_changelist') + '?' + urlencode(return_params)
        values = form.cleaned_data if form.is_bound and form.is_valid() else (
            {'mapping_mode': form.data.get('mapping_mode', mapping.mapping_mode),
             'district': form.data.get('district', ''), 'location': form.data.get('location', ''),
             'is_confirmed': form.data.get('is_confirmed') == 'on'}
            if form.is_bound else {'mapping_mode': mapping.mapping_mode, 'district': mapping.district_id,
                                   'location': mapping.location_id, 'is_confirmed': mapping.is_confirmed}
        )
        data = {
            'id': mapping.pk, 'source_name': str(mapping), 'source_type': mapping.source_type,
            'external_id': mapping.external_id, 'parent_external_id': mapping.parent_external_id,
            'description_en': mapping.description_en, 'description_ru': mapping.description_ru,
            'is_deleted': mapping.is_deleted, 'last_seen_at': date_format(mapping.last_seen_at, 'd.m.Y H:i')
                               if mapping.last_seen_at else '',
            'mode': values['mapping_mode'], 'district': str(getattr(values['district'], 'pk', values['district']) or ''),
            'location': str(getattr(values['location'], 'pk', values['location']) or ''),
            'is_confirmed': values['is_confirmed'], 'can_change': can_change, 'vue_preview': vue_preview,
            'modes': [{'value': value, 'label': label}
                      for value, label in ArealistingLocationMapping.MappingMode.choices],
            'districts': [{'id': str(district.pk), 'name': str(district)}
                          for district in District.objects.order_by('name')],
            'locations': [{'id': str(location.pk), 'name': str(location), 'district': str(location.district)}
                          for location in Location.objects.select_related('district').order_by('district__name', 'name')],
            'errors': {key: [str(error) for error in errors] for key, errors in form.errors.items()},
            'save_url': request.path, 'back_url': back_url,
            'return_fields': return_fields,
        }
        return TemplateResponse(request, 'admin/arealisting/location_mapping_detail_vue.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': 'Сопоставление локации AREALISTING', 'shell_active': 'locations',
            'vue_preview': vue_preview, 'location_mapping_detail_data': data,
        })


@admin.register(ArealistingPaymentPlan)
class ArealistingPaymentPlanAdmin(SourceReadOnlyAdmin):
    change_list_template = 'admin/arealisting/arealistingpaymentplan/change_list.html'
    list_display = ('name', 'project', 'remote_updated_at', 'synced_at', 'is_deleted')
    list_filter = ('is_deleted',)
    search_fields = ('external_id', 'name', 'project__name_en', 'project__name_ru')
    readonly_fields = tuple(field.name for field in ArealistingPaymentPlan._meta.fields)

    def changelist_view(self, request, extra_context=None):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        from .templatetags.arealisting_vite import matching_vue_available
        vue_preview = settings.DEBUG and request.GET.get('vue') == '1'
        vue_available = matching_vue_available()
        use_vue = bool((settings.AREALISTING_VUE_ENABLED or vue_preview) and vue_available)
        if not use_vue:
            context = {**(extra_context or {})}
            if settings.DEBUG and vue_available:
                params = request.GET.copy()
                params['vue'] = '1'
                context['vue_preview_url'] = request.path + '?' + params.urlencode()
            return super().changelist_view(request, context)

        query = request.GET.get('q', '').strip()[:200]
        project = str(request.GET.get('project', ''))
        if not project.isdigit():
            project = ''
        deleted = request.GET.get('is_deleted__exact', '0')
        if deleted not in ('0', '1', 'all'):
            deleted = '0'
        plans = self.get_queryset(request).select_related('project')
        if project:
            plans = plans.filter(project_id=int(project))
        if query:
            plans = plans.filter(
                Q(external_id__icontains=query) | Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(project__name_en__icontains=query) | Q(project__name_ru__icontains=query)
            )
        counts = {'all': plans.count(), 'active': plans.filter(is_deleted=False).count(),
                  'deleted': plans.filter(is_deleted=True).count()}
        if deleted != 'all':
            plans = plans.filter(is_deleted=deleted == '1')
        page = Paginator(plans.order_by('project__name_en', 'name', 'pk'), 30).get_page(request.GET.get('page'))
        list_url = reverse('admin:arealisting_arealistingpaymentplan_changelist')
        def filter_url(*, next_deleted=deleted, number=None):
            params = {'is_deleted__exact': next_deleted, 'project': project, 'q': query}
            if number is not None:
                params['page'] = number
            if vue_preview:
                params['vue'] = '1'
            return list_url + '?' + urlencode(params)
        data = {
            'filter_url': list_url, 'vue_preview': vue_preview,
            'query': query, 'project': project, 'deleted': deleted, 'counts': counts,
            'status_urls': {'all': filter_url(next_deleted='all'),
                            'active': filter_url(next_deleted='0'),
                            'deleted': filter_url(next_deleted='1')},
            'result_count': page.paginator.count,
            'page': {'number': page.number, 'total': page.paginator.num_pages,
                     'previous_url': filter_url(number=page.previous_page_number()) if page.has_previous() else '',
                     'next_url': filter_url(number=page.next_page_number()) if page.has_next() else ''},
            'plans': [{
                'id': plan.pk, 'name': str(plan), 'project': str(plan.project),
                'description': plan.description[:180], 'item_count': len(plan.items or []),
                'is_deleted': plan.is_deleted,
                'remote_updated_at': date_format(plan.remote_updated_at, 'd.m.Y H:i')
                                     if plan.remote_updated_at else '',
                'url': reverse('admin:arealisting_arealistingpaymentplan_change', args=[plan.pk])
                       + '?' + urlencode({'return_project': project, 'return_q': query,
                                          'return_deleted': deleted, 'return_page': page.number,
                                          **({'vue': '1'} if vue_preview else {})}),
            } for plan in page],
        }
        return TemplateResponse(request, 'admin/arealisting/payment_plan_list_vue.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': 'Планы оплаты AREALISTING', 'shell_active': 'payment',
            'vue_preview': vue_preview, 'payment_plan_list_data': data,
        })

    def change_view(self, request, object_id, form_url='', extra_context=None):
        from .templatetags.arealisting_vite import matching_vue_available
        vue_preview = settings.DEBUG and request.GET.get('vue') == '1'
        use_vue = bool((settings.AREALISTING_VUE_ENABLED or vue_preview) and matching_vue_available())
        if not use_vue:
            return super().change_view(request, object_id, form_url, extra_context)
        if request.method != 'GET':
            raise PermissionDenied
        plan = self.get_object(request, object_id)
        if plan is None:
            raise Http404
        if not self.has_view_or_change_permission(request, plan):
            raise PermissionDenied
        return_params = _payment_plan_return_params(request.GET)
        if vue_preview:
            return_params['vue'] = '1'
        field_labels = {'stage': 'Этап', 'type': 'Тип', 'value': 'Сумма или доля',
                        'currency': 'Валюта', 'due': 'Когда оплачивается'}
        items = []
        for index, item in enumerate(plan.items or [], start=1):
            if isinstance(item, dict):
                fields = [{'label': field_labels.get(str(key), str(key)),
                           'value': (json.dumps(value, ensure_ascii=False)
                                     if isinstance(value, (dict, list)) else str(value) if value is not None else '—')}
                          for key, value in item.items()]
                title = str(item.get('stage') or item.get('name') or f'Этап {index}')
            else:
                fields = [{'label': 'Значение', 'value': str(item)}]
                title = f'Этап {index}'
            items.append({'title': title, 'fields': fields})
        data = {
            'id': plan.pk, 'name': str(plan), 'external_id': plan.external_id,
            'project': str(plan.project), 'description': plan.description,
            'items': items, 'is_deleted': plan.is_deleted,
            'remote_updated_at': date_format(plan.remote_updated_at, 'd.m.Y H:i')
                                 if plan.remote_updated_at else '',
            'last_seen_at': date_format(plan.last_seen_at, 'd.m.Y H:i') if plan.last_seen_at else '',
            'synced_at': date_format(plan.synced_at, 'd.m.Y H:i') if plan.synced_at else '',
            'project_url': (reverse('admin:arealisting_arealistingproject_change', args=[plan.project_id])
                            if request.user.has_perm('arealisting.view_arealistingproject') else ''),
            'back_url': reverse('admin:arealisting_arealistingpaymentplan_changelist')
                        + '?' + urlencode(return_params),
        }
        return TemplateResponse(request, 'admin/arealisting/payment_plan_detail_vue.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': 'План оплаты AREALISTING', 'shell_active': 'payment',
            'vue_preview': vue_preview, 'payment_plan_detail_data': data,
        })


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
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        from .templatetags.arealisting_vite import matching_vue_available
        vue_preview = settings.DEBUG and request.GET.get('vue') == '1'
        vue_available = matching_vue_available()
        use_vue = bool((settings.AREALISTING_VUE_ENABLED or vue_preview) and vue_available)
        if not use_vue or request.method != 'GET':
            if settings.DEBUG and vue_available and not use_vue:
                preview_query = request.GET.copy()
                preview_query['vue'] = '1'
                context['vue_preview_url'] = request.path + '?' + preview_query.urlencode()
            return super().changelist_view(request, context)

        state = request.GET.get('download_state', '')
        if state not in ('error', 'downloaded', 'url'):
            state = ''
        asset_type = request.GET.get('asset_type__exact', '')
        if asset_type not in {value for value, _ in ArealistingAsset.AssetType.choices}:
            asset_type = ''
        activity = request.GET.get('is_active__exact', '')
        if activity not in ('0', '1'):
            activity = ''
        project_id = str(request.GET.get('project', ''))
        if not project_id.isdigit():
            project_id = ''
        query = request.GET.get('q', '').strip()[:200]
        assets = self.get_queryset(request)
        if project_id:
            assets = assets.filter(project_id=int(project_id))
        if asset_type:
            assets = assets.filter(asset_type=asset_type)
        if activity:
            assets = assets.filter(is_active=activity == '1')
        if query:
            assets = assets.filter(
                Q(source_url__icontains=query) | Q(source_key__icontains=query)
                | Q(project__name_en__icontains=query) | Q(project__name_ru__icontains=query)
                | Q(unit__unit_number__icontains=query)
            )
        counts = {
            'all': assets.count(),
            'error': assets.exclude(last_error='').count(),
            'downloaded': assets.filter(last_error='', downloaded_at__isnull=False).count(),
            'url': assets.filter(last_error='', downloaded_at__isnull=True).count(),
        }
        if state == 'error':
            assets = assets.exclude(last_error='')
        elif state == 'downloaded':
            assets = assets.filter(last_error='', downloaded_at__isnull=False)
        elif state == 'url':
            assets = assets.filter(last_error='', downloaded_at__isnull=True)
        page = Paginator(assets.order_by('-updated_at', '-pk'), 30).get_page(request.GET.get('page'))
        list_url = reverse('admin:arealisting_arealistingasset_changelist')
        def filter_url(*, next_state=state, number=None):
            params = {'download_state': next_state, 'asset_type__exact': asset_type,
                      'is_active__exact': activity, 'project': project_id, 'q': query}
            if number is not None:
                params['page'] = number
            if vue_preview:
                params['vue'] = '1'
            return list_url + '?' + urlencode(params)
        detail_return = {'return_list': '1', 'return_state': state, 'return_type': asset_type,
                         'return_activity': activity, 'return_project': project_id,
                         'return_q': query, 'return_page': page.number}
        if vue_preview:
            detail_return['vue'] = '1'
        data = {
            'base_url': list_url, 'vue_preview': vue_preview,
            'state': state, 'asset_type': asset_type, 'activity': activity,
            'project': project_id, 'query': query,
            'types': [{'value': value, 'label': label} for value, label in ArealistingAsset.AssetType.choices],
            'counts': counts,
            'state_urls': {key: filter_url(next_state=key) for key in ('', 'error', 'downloaded', 'url')},
            'result_count': page.paginator.count,
            'page': {'number': page.number, 'total': page.paginator.num_pages,
                     'previous_url': filter_url(number=page.previous_page_number()) if page.has_previous() else '',
                     'next_url': filter_url(number=page.next_page_number()) if page.has_next() else ''},
            'can_retry': context['can_retry_assets'],
            'can_view_groups': context['can_view_asset_groups'],
            'groups_url': reverse('admin:arealisting_arealistinglistinggroup_changelist'),
            'assets': [{
                'id': asset.pk, 'title': str(asset), 'type': asset.asset_type,
                'type_label': asset.get_asset_type_display(),
                'project': str(asset.project) if asset.project else '',
                'unit': str(asset.unit) if asset.unit else '',
                'source_url': asset.source_url, 'source_key': asset.source_key,
                'preview_url': asset.file.url if asset.file and asset.downloaded_at else asset.source_url,
                'position': asset.position + 1, 'is_active': asset.is_active,
                'state': 'error' if asset.last_error else 'downloaded' if asset.downloaded_at else 'url',
                'error': asset.last_error,
                'updated_at': date_format(asset.updated_at, 'd.m.Y H:i'),
                'can_retry': bool(context['can_retry_assets'] and self._can_download(asset)),
                'detail_url': reverse('admin:arealisting_arealistingasset_change', args=[asset.pk])
                              + '?' + urlencode(detail_return),
                'retry_url': reverse('admin:arealisting_arealistingasset_retry_download', args=[asset.pk]),
                'linked_cards': [{'title': str(link.listing_group.property),
                                  'url': reverse('admin:properties_property_change',
                                                 args=[link.listing_group.property_id])}
                                 for link in asset.property_links.all()
                                 if link.listing_group.property_id
                                 and (request.user.has_perm('properties.view_property')
                                      or request.user.has_perm('properties.change_property'))][:2]
                                if context['can_view_asset_groups'] else [],
            } for asset in page],
        }
        return TemplateResponse(request, 'admin/arealisting/asset_list_vue.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': 'Материалы AREALISTING', 'shell_active': 'assets',
            'vue_preview': vue_preview, 'asset_list_data': data,
        })

    def change_view(self, request, object_id, form_url='', extra_context=None):
        asset = self.get_object(request, object_id)
        if not self.has_view_or_change_permission(request, asset):
            raise PermissionDenied
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
        from .templatetags.arealisting_vite import matching_vue_available
        vue_preview = settings.DEBUG and request.GET.get('vue') == '1'
        vue_available = matching_vue_available()
        use_vue = bool((settings.AREALISTING_VUE_ENABLED or vue_preview) and vue_available)
        if not use_vue or request.method != 'GET' or not asset:
            if settings.DEBUG and vue_available and not use_vue:
                preview_query = request.GET.copy()
                preview_query['vue'] = '1'
                context['vue_preview_url'] = request.path + '?' + preview_query.urlencode()
            return super().change_view(request, object_id, form_url, context)
        navigation = _asset_list_return_params(request.GET)
        list_params = {
            'download_state': navigation['return_state'],
            'asset_type__exact': navigation['return_type'],
            'is_active__exact': navigation['return_activity'],
            'project': navigation['return_project'],
            'q': navigation['return_q'],
            **({'page': navigation['return_page']} if 'return_page' in navigation else {}),
        } if navigation else {'download_state': 'error'}
        if vue_preview:
            list_params['vue'] = '1'
        can_change_groups = request.user.has_perm('arealisting.change_arealistinglistinggroup')
        context.update({
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': str(asset), 'shell_active': 'assets', 'vue_preview': vue_preview,
            'asset_detail_data': {
                'id': asset.pk, 'title': str(asset), 'type_label': asset.get_asset_type_display(),
                'project': str(asset.project) if asset.project else '',
                'unit': str(asset.unit) if asset.unit else '',
                'source_key': asset.source_key, 'source_url': asset.source_url,
                'local_url': asset.file.url if asset.file else '',
                'is_image': asset.asset_type in {
                    ArealistingAsset.AssetType.PROJECT_GALLERY,
                    ArealistingAsset.AssetType.UNIT_GALLERY,
                    ArealistingAsset.AssetType.FLOOR_PLAN,
                    ArealistingAsset.AssetType.MASTER_PLAN,
                    ArealistingAsset.AssetType.PHOTOS_RENDERS,
                },
                'position': asset.position + 1, 'is_active': asset.is_active,
                'state': 'error' if asset.last_error else 'downloaded' if asset.downloaded_at else 'url',
                'error': asset.last_error,
                'downloaded_at': date_format(asset.downloaded_at, 'd.m.Y H:i') if asset.downloaded_at else '',
                'updated_at': date_format(asset.updated_at, 'd.m.Y H:i'),
                'back_url': reverse('admin:arealisting_arealistingasset_changelist')
                            + '?' + urlencode(list_params),
                'retry_url': reverse('admin:arealisting_arealistingasset_retry_download', args=[asset.pk]),
                'can_retry': context['can_retry_asset'],
                'can_view_groups': context['can_view_asset_groups'],
                'groups_url': (reverse('admin:arealisting_arealistinglistinggroup_changelist')
                               + ('?vue=1' if vue_preview else '')),
                'group_count': context.get('asset_group_count', 0),
                'groups': [{
                    'title': str(group), 'property': str(group.property) if group.property else '',
                    'url': (reverse('admin:arealisting_arealistinglistinggroup_change', args=[group.pk])
                            + ('?vue=1' if vue_preview else '')),
                    'preview_url': (reverse('admin:arealisting_arealistinglistinggroup_preview_media', args=[group.pk])
                                    + ('?vue=1' if vue_preview else ''))
                                   if group.property_id and can_change_groups else '',
                } for group in context.get('asset_groups', [])],
            },
        })
        return TemplateResponse(request, 'admin/arealisting/asset_detail_vue.html', context)

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
        json_response = request.POST.get('format') == 'json'
        result = self._retry_assets(request, [asset], notify=not json_response)
        if json_response:
            return JsonResponse({**result,
                                 'state': 'error' if asset.last_error else 'downloaded' if asset.downloaded_at else 'url',
                                 'error': asset.last_error})
        return HttpResponseRedirect(reverse('admin:arealisting_arealistingasset_change', args=[asset.pk]))

    @admin.action(description='Повторить скачивание выбранных изображений', permissions=['change'])
    def retry_download(self, request, queryset):
        if queryset.count() > 10:
            self.message_user(request, 'За один запуск можно скачать не более 10 изображений.', messages.ERROR)
            return
        self._retry_assets(request, queryset)

    def _retry_assets(self, request, assets, *, notify=True):
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
        result = {'downloaded': downloaded, 'failed': failed, 'skipped': skipped}
        if not notify:
            return result
        if not downloaded and not failed:
            self.message_user(
                request,
                'Скачивать нечего: выбранные материалы уже загружены, неактивны '
                'или относятся к документам.',
                messages.INFO,
            )
            return result
        level = messages.WARNING if failed else messages.SUCCESS
        self.message_user(
            request,
            f'Скачано: {downloaded}; ошибок: {failed}; пропущено: {skipped}. '
            'Чтобы добавить фото в карточку, откройте «Связи с карточками» и выполните '
            '«Импортировать/обновить фотографии и планировки» для нужной группы.',
            level,
        )
        return result

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
    change_list_template = 'admin/arealisting/arealistingpropertyasset/change_list.html'
    list_display = ('listing_group', 'role', 'asset', 'property_image', 'updated_at')
    list_filter = ('role',)
    search_fields = (
        'listing_group__name',
        'listing_group__property__title',
        'asset__source_url',
    )
    readonly_fields = tuple(field.name for field in ArealistingPropertyAsset._meta.fields)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'listing_group__property', 'listing_group__project',
            'asset__project', 'asset__unit', 'property_image',
        )

    def changelist_view(self, request, extra_context=None):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        from .templatetags.arealisting_vite import matching_vue_available
        vue_preview = settings.DEBUG and request.GET.get('vue') == '1'
        vue_available = matching_vue_available()
        if not ((settings.AREALISTING_VUE_ENABLED or vue_preview) and vue_available):
            context = {**(extra_context or {})}
            if settings.DEBUG and vue_available:
                params = request.GET.copy()
                params['vue'] = '1'
                context['vue_preview_url'] = request.path + '?' + params.urlencode()
            return super().changelist_view(request, context)

        role = request.GET.get('role', '')
        if role not in {value for value, _ in ArealistingPropertyAsset.Role.choices}:
            role = ''
        image_state = request.GET.get('image_state', 'all')
        if image_state not in ('all', 'linked', 'missing'):
            image_state = 'all'
        project = str(request.GET.get('project', ''))
        if not project.isdigit():
            project = ''
        query = request.GET.get('q', '').strip()[:200]
        links = self.get_queryset(request)
        if project:
            links = links.filter(listing_group__project_id=int(project))
        if role:
            links = links.filter(role=role)
        if query:
            links = links.filter(
                Q(listing_group__name__icontains=query)
                | Q(listing_group__property__title__icontains=query)
                | Q(listing_group__property__title_ru__icontains=query)
                | Q(listing_group__project__name_en__icontains=query)
                | Q(listing_group__project__name_ru__icontains=query)
                | Q(asset__source_url__icontains=query)
                | Q(asset__source_key__icontains=query)
            )
        counts = {'all': links.count(),
                  'linked': links.filter(property_image__isnull=False).count(),
                  'missing': links.filter(property_image__isnull=True).count()}
        if image_state == 'linked':
            links = links.filter(property_image__isnull=False)
        elif image_state == 'missing':
            links = links.filter(property_image__isnull=True)
        page = Paginator(links.order_by('-updated_at', '-pk'), 30).get_page(request.GET.get('page'))
        list_url = reverse('admin:arealisting_arealistingpropertyasset_changelist')

        def filter_url(*, next_state=image_state, number=None):
            params = {'image_state': next_state, 'role': role, 'project': project, 'q': query}
            if number is not None:
                params['page'] = number
            if vue_preview:
                params['vue'] = '1'
            return list_url + '?' + urlencode(params)

        data = {
            'filter_url': list_url, 'vue_preview': vue_preview,
            'role': role, 'image_state': image_state, 'project': project, 'query': query,
            'roles': [{'value': value, 'label': label} for value, label in ArealistingPropertyAsset.Role.choices],
            'counts': counts,
            'state_urls': {value: filter_url(next_state=value) for value in counts},
            'result_count': page.paginator.count,
            'page': {'number': page.number, 'total': page.paginator.num_pages,
                     'previous_url': filter_url(number=page.previous_page_number()) if page.has_previous() else '',
                     'next_url': filter_url(number=page.next_page_number()) if page.has_next() else ''},
            'links': [{
                'id': link.pk, 'role': link.get_role_display(),
                'group': str(link.listing_group),
                'property': str(link.listing_group.property) if link.listing_group.property else '',
                'project': str(link.listing_group.project),
                'asset_type': link.asset.get_asset_type_display(),
                'source_url': link.asset.source_url,
                'preview_url': (link.property_image.image.url
                                if link.property_image and link.property_image.image
                                else link.asset.file.url if link.asset.file else link.asset.source_url),
                'has_image': bool(link.property_image_id),
                'is_main': bool(link.property_image and link.property_image.is_main),
                'updated_at': date_format(link.updated_at, 'd.m.Y H:i'),
                'url': reverse('admin:arealisting_arealistingpropertyasset_change', args=[link.pk])
                       + '?' + urlencode({'return_state': image_state, 'return_role': role,
                                          'return_project': project, 'return_q': query,
                                          'return_page': page.number,
                                          **({'vue': '1'} if vue_preview else {})}),
            } for link in page],
        }
        return TemplateResponse(request, 'admin/arealisting/property_asset_list_vue.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': 'Фото в карточках AREALISTING', 'shell_active': 'property_assets',
            'vue_preview': vue_preview, 'property_asset_list_data': data,
        })

    def change_view(self, request, object_id, form_url='', extra_context=None):
        from .templatetags.arealisting_vite import matching_vue_available
        vue_preview = settings.DEBUG and request.GET.get('vue') == '1'
        if not ((settings.AREALISTING_VUE_ENABLED or vue_preview) and matching_vue_available()):
            return super().change_view(request, object_id, form_url, extra_context)
        if request.method != 'GET':
            raise PermissionDenied
        link = self.get_object(request, object_id)
        if link is None:
            raise Http404
        if not self.has_view_or_change_permission(request, link):
            raise PermissionDenied
        state = request.GET.get('return_state', 'all')
        if state not in ('all', 'linked', 'missing'):
            state = 'all'
        role = request.GET.get('return_role', '')
        if role not in {value for value, _ in ArealistingPropertyAsset.Role.choices}:
            role = ''
        project = str(request.GET.get('return_project', ''))
        page = str(request.GET.get('return_page', ''))
        params = {'image_state': state, 'role': role,
                  'project': project if project.isdigit() else '',
                  'q': request.GET.get('return_q', '').strip()[:200]}
        if page.isdigit() and int(page) > 0:
            params['page'] = page
        if vue_preview:
            params['vue'] = '1'
        group = link.listing_group
        image = link.property_image
        asset = link.asset
        data = {
            'id': link.pk, 'role': link.get_role_display(),
            'group': str(group), 'property': str(group.property) if group.property else '',
            'project': str(group.project), 'asset_type': asset.get_asset_type_display(),
            'source_key': asset.source_key, 'source_url': asset.source_url,
            'asset_error': asset.last_error, 'is_active': asset.is_active,
            'preview_url': (image.image.url if image and image.image
                            else asset.file.url if asset.file else asset.source_url),
            'card_image_url': image.image.url if image and image.image else '',
            'has_image': bool(image), 'is_main': bool(image and image.is_main),
            'position': asset.position + 1,
            'created_at': date_format(link.created_at, 'd.m.Y H:i'),
            'updated_at': date_format(link.updated_at, 'd.m.Y H:i'),
            'back_url': reverse('admin:arealisting_arealistingpropertyasset_changelist')
                        + '?' + urlencode(params),
            'asset_url': (reverse('admin:arealisting_arealistingasset_change', args=[asset.pk])
                          + ('?vue=1' if vue_preview else '')
                          if request.user.has_perm('arealisting.view_arealistingasset') else ''),
            'group_url': (reverse('admin:arealisting_arealistinglistinggroup_change', args=[group.pk])
                          + ('?vue=1' if vue_preview else '')
                          if request.user.has_perm('arealisting.view_arealistinglistinggroup') else ''),
            'property_url': (reverse('admin:properties_property_change', args=[group.property_id])
                             if group.property_id and (request.user.has_perm('properties.view_property')
                                                       or request.user.has_perm('properties.change_property')) else ''),
        }
        return TemplateResponse(request, 'admin/arealisting/property_asset_detail_vue.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': 'Фото в карточке AREALISTING', 'shell_active': 'property_assets',
            'vue_preview': vue_preview, 'property_asset_detail_data': data,
        })


@admin.register(ArealistingSkippedUnit)
class ArealistingSkippedUnitAdmin(SourceReadOnlyAdmin):
    change_list_template = 'admin/arealisting/arealistingskippedunit/change_list.html'
    list_display = ('unit', 'skipped_by', 'reason', 'created_at')
    search_fields = (
        'unit__external_id',
        'unit__unit_number',
        'unit__project__name_en',
        'unit__project__name_ru',
        'reason',
    )
    readonly_fields = tuple(field.name for field in ArealistingSkippedUnit._meta.fields)

    @staticmethod
    def _can_restore(request, skipped):
        required = (
            'arealisting.view_arealistingproject', 'arealisting.change_arealistingunit',
            'arealisting.add_arealistinglistinggroup', 'arealisting.change_arealistinglistinggroup',
            'properties.change_property',
        )
        return bool(
            request.user.has_perms(required) and not skipped.unit.is_deleted
            and not skipped.unit.project.is_deleted and skipped.unit.listing_group_id is None
        )

    def get_urls(self):
        return [path('<path:object_id>/restore/', self.admin_site.admin_view(self.restore_view),
                     name='arealisting_arealistingskippedunit_restore')] + super().get_urls()

    @method_decorator(require_POST)
    def restore_view(self, request, object_id):
        skipped = get_object_or_404(
            ArealistingSkippedUnit.objects.select_related('unit__project', 'unit__listing_group'),
            pk=object_id,
        )
        if not self.has_view_or_change_permission(request, skipped) or not self._can_restore(request, skipped):
            raise PermissionDenied
        count = restore_units(skipped.unit.project_id, [skipped.unit_id])
        self.admin_site._registry[ArealistingProject].log_change(
            request, skipped.unit.project, f'Возвращено предложений в очередь: {count}',
        )
        self.message_user(request, 'Предложение возвращено в очередь сопоставления.', messages.SUCCESS)
        params = _skipped_unit_return_params(request.POST)
        if settings.DEBUG and request.POST.get('vue') == '1':
            params['vue'] = '1'
        return HttpResponseRedirect(
            reverse('admin:arealisting_arealistingskippedunit_changelist') + '?' + urlencode(params)
        )

    def changelist_view(self, request, extra_context=None):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        from .templatetags.arealisting_vite import matching_vue_available
        vue_preview = settings.DEBUG and request.GET.get('vue') == '1'
        vue_available = matching_vue_available()
        use_vue = bool((settings.AREALISTING_VUE_ENABLED or vue_preview) and vue_available)
        if not use_vue:
            context = {**(extra_context or {})}
            if settings.DEBUG and vue_available:
                params = request.GET.copy()
                params['vue'] = '1'
                context['vue_preview_url'] = request.path + '?' + params.urlencode()
            return super().changelist_view(request, context)

        project = str(request.GET.get('project', ''))
        if not project.isdigit():
            project = ''
        query = request.GET.get('q', '').strip()[:200]
        skipped = self.get_queryset(request).select_related('unit__project', 'unit__listing_group', 'skipped_by')
        if project:
            skipped = skipped.filter(unit__project_id=int(project))
        if query:
            skipped = skipped.filter(
                Q(unit__external_id__icontains=query) | Q(unit__unit_number__icontains=query)
                | Q(unit__project__name_en__icontains=query) | Q(unit__project__name_ru__icontains=query)
                | Q(reason__icontains=query)
            )
        page = Paginator(skipped.order_by('-created_at', '-pk'), 30).get_page(request.GET.get('page'))
        list_url = reverse('admin:arealisting_arealistingskippedunit_changelist')
        def page_url(number):
            return list_url + '?' + urlencode({'project': project, 'q': query, 'page': number,
                                               **({'vue': '1'} if vue_preview else {})})
        can_view_unit = request.user.has_perm('arealisting.view_arealistingunit')
        data = {
            'filter_url': list_url, 'vue_preview': vue_preview, 'project': project, 'query': query,
            'result_count': page.paginator.count,
            'page': {'number': page.number, 'total': page.paginator.num_pages,
                     'previous_url': page_url(page.previous_page_number()) if page.has_previous() else '',
                     'next_url': page_url(page.next_page_number()) if page.has_next() else ''},
            'rows': [{
                'id': item.pk, 'unit_id': item.unit_id,
                'unit': item.unit.unit_number or item.unit.external_id,
                'project': str(item.unit.project), 'project_id': item.unit.project_id,
                'reason': item.reason, 'skipped_by': str(item.skipped_by) if item.skipped_by_id else '',
                'created_at': date_format(item.created_at, 'd.m.Y H:i'),
                'is_deleted': item.unit.is_deleted, 'is_linked': item.unit.listing_group_id is not None,
                'can_restore': self._can_restore(request, item),
                'unit_url': (reverse('admin:arealisting_arealistingunit_change', args=[item.unit_id])
                             + ('?vue=1' if vue_preview else '') if can_view_unit else ''),
                'detail_url': reverse('admin:arealisting_arealistingskippedunit_change', args=[item.pk])
                              + '?' + urlencode({'return_project': project, 'return_q': query,
                                                 'return_page': page.number,
                                                 **({'vue': '1'} if vue_preview else {})}),
                'restore_url': reverse('admin:arealisting_arealistingskippedunit_restore', args=[item.pk]),
                'matching_url': (reverse('admin:arealisting_matching') + '?'
                                 + urlencode({'project': item.unit.project_id,
                                              **({'vue': '1'} if vue_preview else {})})
                                 if self._can_restore(request, item) else ''),
            } for item in page],
        }
        return TemplateResponse(request, 'admin/arealisting/skipped_unit_list_vue.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': 'Пропущенные предложения AREALISTING', 'shell_active': 'skipped',
            'vue_preview': vue_preview, 'skipped_unit_list_data': data,
        })

    def change_view(self, request, object_id, form_url='', extra_context=None):
        from .templatetags.arealisting_vite import matching_vue_available
        vue_preview = settings.DEBUG and request.GET.get('vue') == '1'
        use_vue = bool((settings.AREALISTING_VUE_ENABLED or vue_preview) and matching_vue_available())
        if not use_vue:
            return super().change_view(request, object_id, form_url, extra_context)
        if request.method != 'GET':
            raise PermissionDenied
        item = self.get_object(request, object_id)
        if item is None:
            raise Http404
        if not self.has_view_or_change_permission(request, item):
            raise PermissionDenied
        unit = item.unit
        return_params = _skipped_unit_return_params(request.GET)
        if vue_preview:
            return_params['vue'] = '1'
        data = {
            'id': item.pk, 'unit': unit.unit_number or unit.external_id,
            'external_id': unit.external_id, 'project': str(unit.project),
            'project_id': unit.project_id, 'reason': item.reason,
            'skipped_by': str(item.skipped_by) if item.skipped_by_id else '',
            'created_at': date_format(item.created_at, 'd.m.Y H:i'),
            'is_deleted': unit.is_deleted, 'is_linked': unit.listing_group_id is not None,
            'status': unit.get_availability_status_display() or 'Не указан',
            'can_restore': self._can_restore(request, item),
            'unit_url': (reverse('admin:arealisting_arealistingunit_change', args=[unit.pk])
                         + ('?vue=1' if vue_preview else '')
                         if request.user.has_perm('arealisting.view_arealistingunit') else ''),
            'matching_url': (reverse('admin:arealisting_matching') + '?'
                             + urlencode({'project': unit.project_id,
                                          **({'vue': '1'} if vue_preview else {})})
                             if self._can_restore(request, item) else ''),
            'restore_url': reverse('admin:arealisting_arealistingskippedunit_restore', args=[item.pk]),
            'back_url': reverse('admin:arealisting_arealistingskippedunit_changelist')
                        + '?' + urlencode(return_params),
            'return_fields': {'return_project': return_params['project'],
                              'return_q': return_params['q'],
                              'return_page': return_params.get('page', '')},
            'vue_preview': vue_preview,
        }
        return TemplateResponse(request, 'admin/arealisting/skipped_unit_detail_vue.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': 'Пропущенное предложение AREALISTING', 'shell_active': 'skipped',
            'vue_preview': vue_preview, 'skipped_unit_detail_data': data,
        })


@admin.register(ArealistingSyncRun)
class ArealistingSyncRunAdmin(SourceReadOnlyAdmin):
    change_list_template = 'admin/arealisting/arealistingsyncrun/change_list.html'
    list_display = ('started_at', 'mode', 'status', 'finished_at', 'resource_names')
    list_filter = ('mode', 'status')
    search_fields = ('error',)
    readonly_fields = tuple(field.name for field in ArealistingSyncRun._meta.fields)

    def changelist_view(self, request, extra_context=None):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        from .templatetags.arealisting_vite import matching_vue_available
        vue_preview = settings.DEBUG and request.GET.get('vue') == '1'
        vue_available = matching_vue_available()
        use_vue = bool((settings.AREALISTING_VUE_ENABLED or vue_preview) and vue_available)
        if not use_vue:
            context = {**(extra_context or {})}
            if settings.DEBUG and vue_available:
                params = request.GET.copy()
                params['vue'] = '1'
                context['vue_preview_url'] = request.path + '?' + params.urlencode()
            return super().changelist_view(request, context)

        status = request.GET.get('status', '')
        if status not in {value for value, _ in ArealistingSyncRun.Status.choices}:
            status = ''
        mode = request.GET.get('mode', '')
        if mode not in {value for value, _ in ArealistingSyncRun.Mode.choices}:
            mode = ''
        query = request.GET.get('q', '').strip()[:200]
        runs = self.get_queryset(request)
        if mode:
            runs = runs.filter(mode=mode)
        if query:
            search = Q(error__icontains=query)
            if query.isdigit():
                search |= Q(pk=int(query))
            runs = runs.filter(search)
        counts = {value: runs.filter(status=value).count() for value, _ in ArealistingSyncRun.Status.choices}
        if status:
            runs = runs.filter(status=status)
        page = Paginator(runs.order_by('-started_at', '-pk'), 30).get_page(request.GET.get('page'))
        list_url = reverse('admin:arealisting_arealistingsyncrun_changelist')
        def filter_url(*, next_status=status, number=None):
            params = {'status': next_status, 'mode': mode, 'q': query}
            if number is not None:
                params['page'] = number
            if vue_preview:
                params['vue'] = '1'
            return list_url + '?' + urlencode(params)
        data = {
            'filter_url': list_url, 'vue_preview': vue_preview,
            'status': status, 'mode': mode, 'query': query,
            'statuses': [{'value': value, 'label': label, 'count': counts[value],
                          'url': filter_url(next_status=value)}
                         for value, label in ArealistingSyncRun.Status.choices],
            'all_count': sum(counts.values()), 'all_url': filter_url(next_status=''),
            'modes': [{'value': value, 'label': label} for value, label in ArealistingSyncRun.Mode.choices],
            'result_count': page.paginator.count,
            'page': {'number': page.number, 'total': page.paginator.num_pages,
                     'previous_url': filter_url(number=page.previous_page_number()) if page.has_previous() else '',
                     'next_url': filter_url(number=page.next_page_number()) if page.has_next() else ''},
            'runs': [{
                'id': run.pk, 'mode': run.get_mode_display(), 'status': run.status,
                'status_label': run.get_status_display(),
                'started_at': date_format(run.started_at, 'd.m.Y H:i'),
                'finished_at': date_format(run.finished_at, 'd.m.Y H:i') if run.finished_at else '',
                'resources': [_sync_resource_label(resource) for resource in (run.resources or [])],
                'error': (run.error or '')[:240],
                'url': (reverse('admin:arealisting_arealistingsyncrun_change', args=[run.pk])
                        + '?' + urlencode({'return_status': status, 'return_mode': mode,
                                           'return_q': query, 'return_page': page.number,
                                           **({'vue': '1'} if vue_preview else {})})),
            } for run in page],
        }
        return TemplateResponse(request, 'admin/arealisting/sync_run_list_vue.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': 'История обновлений AREALISTING', 'shell_active': 'history',
            'vue_preview': vue_preview, 'sync_run_list_data': data,
        })

    def change_view(self, request, object_id, form_url='', extra_context=None):
        from .templatetags.arealisting_vite import matching_vue_available
        vue_preview = settings.DEBUG and request.GET.get('vue') == '1'
        use_vue = bool((settings.AREALISTING_VUE_ENABLED or vue_preview) and matching_vue_available())
        if not use_vue:
            return super().change_view(request, object_id, form_url, extra_context)
        if request.method != 'GET':
            raise PermissionDenied
        run = self.get_object(request, object_id)
        if run is None:
            raise Http404
        if not self.has_view_or_change_permission(request, run):
            raise PermissionDenied
        return_status = request.GET.get('return_status', '')
        if return_status not in {value for value, _ in ArealistingSyncRun.Status.choices}:
            return_status = ''
        return_mode = request.GET.get('return_mode', '')
        if return_mode not in {value for value, _ in ArealistingSyncRun.Mode.choices}:
            return_mode = ''
        return_page = str(request.GET.get('return_page', ''))
        return_params = {'status': return_status, 'mode': return_mode,
                         'q': request.GET.get('return_q', '').strip()[:200]}
        if return_page.isdigit() and int(return_page) > 0:
            return_params['page'] = return_page
        if vue_preview:
            return_params['vue'] = '1'
        summary = run.summary if isinstance(run.summary, dict) else {}
        resource_rows = []
        for resource in run.resources or []:
            stats = summary.get(resource)
            if not isinstance(stats, dict):
                stats = {}
            resource_rows.append({
                'name': _sync_resource_label(resource),
                'seen': stats.get('seen') or 0, 'created': stats.get('created') or 0,
                'updated': stats.get('updated') or 0, 'deleted': stats.get('deleted') or 0,
                'skipped': stats.get('skipped') or 0, 'errors': stats.get('errors') or 0,
            })
        data = {
            'id': run.pk, 'mode': run.get_mode_display(), 'status': run.status,
            'status_label': run.get_status_display(),
            'started_at': date_format(run.started_at, 'd.m.Y H:i'),
            'finished_at': date_format(run.finished_at, 'd.m.Y H:i') if run.finished_at else '',
            'since': date_format(run.since, 'd.m.Y H:i') if run.since else '',
            'resources': resource_rows, 'project_ids': run.project_ids or [],
            'property_update_count': len(summary.get('property_updates') or []),
            'price_update_count': len(summary.get('price_updates') or []),
            'error': run.error or '',
            'back_url': reverse('admin:arealisting_arealistingsyncrun_changelist')
                        + '?' + urlencode(return_params),
            'review_url': (reverse('admin:arealisting_review_queue')
                           + ('?vue=1' if vue_preview else '')
                           if request.user.has_perm('arealisting.view_arealistingsyncevent') else ''),
        }
        return TemplateResponse(request, 'admin/arealisting/sync_run_detail_vue.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': f'Обновление AREALISTING #{run.pk}', 'shell_active': 'history',
            'vue_preview': vue_preview, 'sync_run_detail_data': data,
        })

    @admin.display(description='Ресурсы')
    def resource_names(self, obj):
        return ', '.join(obj.resources or [])


@admin.register(ArealistingPriceReview)
class ArealistingPriceReviewAdmin(SourceReadOnlyAdmin):
    change_list_template = 'admin/arealisting/arealistingpricereview/change_list.html'
    list_display = ('created_at', 'property_link', 'project', 'change_percent',
                    'status', 'reviewed_by', 'review_action')
    list_filter = ('status', 'created_at')
    search_fields = ('property__title', 'property__title_ru', 'project__name_en', 'project__name_ru')
    list_select_related = ('property', 'project', 'reviewed_by')
    readonly_fields = tuple(field.name for field in ArealistingPriceReview._meta.fields)

    def changelist_view(self, request, extra_context=None):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        from .templatetags.arealisting_vite import matching_vue_available
        vue_preview = settings.DEBUG and request.GET.get('vue') == '1'
        vue_available = matching_vue_available()
        use_vue = bool((settings.AREALISTING_VUE_ENABLED or vue_preview) and vue_available)
        if not use_vue or request.method != 'GET':
            context = {**(extra_context or {})}
            if settings.DEBUG and vue_available and not use_vue:
                preview_query = request.GET.copy()
                preview_query['vue'] = '1'
                context['vue_preview_url'] = request.path + '?' + preview_query.urlencode()
            return super().changelist_view(request, extra_context=context)

        status = request.GET.get('status__exact', '')
        allowed_statuses = {value for value, _ in ArealistingPriceReview.Status.choices}
        if status not in allowed_statuses:
            status = ''
        period = request.GET.get('period', 'all')
        if period not in ('all', '7d', '30d'):
            period = 'all'
        query = request.GET.get('q', '').strip()[:200]
        order = request.GET.get('order', 'newest')
        if order not in ('newest', 'oldest', 'largest'):
            order = 'newest'
        base = self.get_queryset(request)
        if period != 'all':
            base = base.filter(created_at__gte=timezone.now() - timedelta(days=7 if period == '7d' else 30))
        if query:
            base = base.filter(
                Q(property__title__icontains=query) | Q(property__title_ru__icontains=query)
                | Q(project__name_en__icontains=query) | Q(project__name_ru__icontains=query)
            )
        status_counts = {key: 0 for key in allowed_statuses}
        for entry in base.values('status').annotate(total=Count('pk')):
            status_counts[entry['status']] = entry['total']
        reviews = base.select_related('property', 'project', 'reviewed_by')
        if status:
            reviews = reviews.filter(status=status)
        order_fields = {
            'newest': ('-created_at', '-pk'),
            'oldest': ('created_at', 'pk'),
            'largest': ('-change_percent', '-created_at', '-pk'),
        }
        page = Paginator(reviews.order_by(*order_fields[order]), 30).get_page(request.GET.get('page'))
        list_url = reverse('admin:arealisting_arealistingpricereview_changelist')
        def filter_url(*, next_status=status, number=None):
            params = {'status__exact': next_status, 'period': period, 'q': query, 'order': order}
            if number is not None:
                params['page'] = number
            if vue_preview:
                params['vue'] = '1'
            return list_url + '?' + urlencode(params)
        detail_return = {'return_list': '1', 'return_status': status, 'return_period': period,
                         'return_q': query, 'return_order': order, 'return_page': page.number}
        if vue_preview:
            detail_return['vue'] = '1'
        can_view_property = request.user.has_perm('properties.view_property') or request.user.has_perm('properties.change_property')
        data = {
            'filter_url': list_url, 'vue_preview': vue_preview,
            'status': status, 'period': period, 'query': query, 'order': order,
            'statuses': [{'value': value, 'label': label, 'count': status_counts.get(value, 0),
                          'url': filter_url(next_status=value)}
                         for value, label in ArealistingPriceReview.Status.choices],
            'all_count': sum(status_counts.values()), 'all_url': filter_url(next_status=''),
            'result_count': page.paginator.count,
            'page': {'number': page.number, 'total': page.paginator.num_pages,
                     'previous_url': filter_url(number=page.previous_page_number()) if page.has_previous() else '',
                     'next_url': filter_url(number=page.next_page_number()) if page.has_next() else ''},
            'reviews': [{
                'id': review.pk, 'property': str(review.property),
                'property_url': (reverse('admin:properties_property_change', args=[review.property_id])
                                 if can_view_property else ''),
                'project': str(review.project) if review.project else 'Комплекс не указан',
                'percent': str(review.change_percent), 'status': review.status,
                'status_label': review.get_status_display(),
                'before': str((review.before or {}).get('price_sale_thb') or '—'),
                'after': str((review.after or {}).get('price_sale_thb') or '—'),
                'created_at': date_format(review.created_at, 'd.m.Y H:i'),
                'reviewed_at': date_format(review.reviewed_at, 'd.m.Y H:i') if review.reviewed_at else '',
                'reviewed_by': str(review.reviewed_by) if review.reviewed_by else '',
                'url': reverse('admin:arealisting_arealistingpricereview_review', args=[review.pk])
                       + '?' + urlencode(detail_return),
            } for review in page],
        }
        return TemplateResponse(request, 'admin/arealisting/price_review_list_vue.html', {
            **self.admin_site.each_context(request),
            'opts': self.model._meta, 'title': 'Проверка изменений цен',
            'shell_active': 'price', 'vue_preview': vue_preview,
            'price_review_list_data': data,
        })

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
        navigation = _price_review_list_params(request.POST if request.method == 'POST' else request.GET)
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
            redirect_params = dict(navigation)
            if settings.DEBUG and request.POST.get('vue') == '1':
                redirect_params['vue'] = '1'
            url = reverse('admin:arealisting_arealistingpricereview_review', args=[review.pk])
            return HttpResponseRedirect(url + ('?' + urlencode(redirect_params) if redirect_params else ''))
        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': 'Проверка изменения цены',
            'review': review,
            'can_decide': can_decide and review.status == ArealistingPriceReview.Status.PENDING,
            'property_url': reverse('admin:properties_property_change', args=[review.property_id]),
        }
        from .templatetags.arealisting_vite import matching_vue_available
        vue_preview = settings.DEBUG and request.GET.get('vue') == '1'
        vue_available = matching_vue_available()
        use_vue = bool((settings.AREALISTING_VUE_ENABLED or vue_preview) and vue_available)
        context['vue_preview_url'] = (
            request.path + '?vue=1' if settings.DEBUG and vue_available and not use_vue else ''
        )
        if use_vue:
            context['shell_active'] = 'price'
            context['vue_preview'] = vue_preview
            list_params = {
                'status__exact': navigation['return_status'],
                'period': navigation['return_period'],
                'q': navigation['return_q'],
                'order': navigation['return_order'],
                **({'page': navigation['return_page']} if 'return_page' in navigation else {}),
            } if navigation else {'status__exact': 'PENDING'}
            if vue_preview:
                list_params['vue'] = '1'
            context['price_review_data'] = {
                'id': review.pk, 'property': str(review.property), 'project': str(review.project),
                'property_url': context['property_url'],
                'back_url': reverse('admin:arealisting_arealistingpricereview_changelist')
                            + '?' + urlencode(list_params),
                'decision_url': request.path, 'vue_preview': vue_preview,
                'return_fields': navigation,
                'change_percent': str(review.change_percent),
                'status': review.get_status_display(),
                'created_at': date_format(review.created_at, 'd.m.Y H:i'),
                'reviewed_at': date_format(review.reviewed_at, 'd.m.Y H:i') if review.reviewed_at else '',
                'reviewed_by': str(review.reviewed_by) if review.reviewed_by else '',
                'can_decide': context['can_decide'],
                'prices': [{
                    'currency': currency,
                    'before': str((review.before or {}).get(field) or 'Не указана'),
                    'after': str((review.after or {}).get(field) or 'Не указана'),
                } for field, currency in [('price_sale_thb', 'THB'), ('price_sale_usd', 'USD'),
                                          ('price_sale_rub', 'RUB')]],
                'units': [{
                    'number': str(unit.get('number') or unit.get('external_id') or '—'),
                    'source_price': str(unit.get('source_price') or '—'),
                    'currency': str(unit.get('currency') or ''),
                    'price_thb': str(unit.get('price_thb') or '—'),
                } for unit in (review.units or [])],
            }
        return TemplateResponse(request, 'admin/arealisting/price_review_vue.html'
                                if use_vue else 'admin/arealisting/price_review.html', context)


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
    change_list_template = 'admin/arealisting/arealistingsyncevent/change_list.html'
    list_display = ('created_at', 'kind', 'project', 'unit', 'property_link', 'next_step', 'reviewed_at')
    list_filter = ('kind', SyncEventRunFilter)
    search_fields = ('unit__external_id', 'unit__unit_number',
                     'project__name_ru', 'project__name_en', 'property__title_ru')
    list_select_related = ('run', 'project', 'unit', 'property')
    readonly_fields = ('created_at', 'run', 'kind', 'project', 'unit', 'property',
                       'details_display', 'reviewed_at', 'reviewed_by')
    fields = readonly_fields
    ordering = ('-created_at', '-pk')

    def changelist_view(self, request, extra_context=None):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        from .templatetags.arealisting_vite import matching_vue_available
        vue_preview = settings.DEBUG and request.GET.get('vue') == '1'
        vue_available = matching_vue_available()
        if not ((settings.AREALISTING_VUE_ENABLED or vue_preview) and vue_available):
            context = {**(extra_context or {})}
            if settings.DEBUG and vue_available:
                params = request.GET.copy()
                params['vue'] = '1'
                context['vue_preview_url'] = request.path + '?' + params.urlencode()
            return super().changelist_view(request, context)

        kind = request.GET.get('kind', '')
        if kind not in {value for value, _ in ArealistingSyncEvent.Kind.choices}:
            kind = ''
        state = request.GET.get('state', 'all')
        if state not in ('all', 'open', 'checked'):
            state = 'all'
        run = str(request.GET.get('run', ''))
        if not run.isdigit():
            run = ''
        query = request.GET.get('q', '').strip()[:200]
        events = self.get_queryset(request).select_related('run', 'project', 'unit', 'property')
        if run:
            events = events.filter(run_id=int(run))
        if kind:
            events = events.filter(kind=kind)
        if query:
            events = events.filter(
                Q(unit__external_id__icontains=query) | Q(unit__unit_number__icontains=query)
                | Q(project__name_en__icontains=query) | Q(project__name_ru__icontains=query)
                | Q(property__title__icontains=query) | Q(property__title_ru__icontains=query)
            )
        counts = {'all': events.count(), 'open': events.filter(reviewed_at__isnull=True).count(),
                  'checked': events.filter(reviewed_at__isnull=False).count()}
        if state == 'open':
            events = events.filter(reviewed_at__isnull=True)
        elif state == 'checked':
            events = events.filter(reviewed_at__isnull=False)
        page = Paginator(events.order_by('-created_at', '-pk'), 30).get_page(request.GET.get('page'))
        list_url = reverse('admin:arealisting_arealistingsyncevent_changelist')

        def filter_url(*, next_state=state, number=None):
            params = {'state': next_state, 'kind': kind, 'run': run, 'q': query}
            if number is not None:
                params['page'] = number
            if vue_preview:
                params['vue'] = '1'
            return list_url + '?' + urlencode(params)

        data = {
            'filter_url': list_url, 'vue_preview': vue_preview, 'state': state,
            'kind': kind, 'run': run, 'query': query, 'counts': counts,
            'state_urls': {value: filter_url(next_state=value) for value in counts},
            'kinds': [{'value': value, 'label': label}
                      for value, label in ArealistingSyncEvent.Kind.choices],
            'result_count': page.paginator.count,
            'page': {'number': page.number, 'total': page.paginator.num_pages,
                     'previous_url': filter_url(number=page.previous_page_number()) if page.has_previous() else '',
                     'next_url': filter_url(number=page.next_page_number()) if page.has_next() else ''},
            'events': [{
                'id': event.pk, 'kind': event.get_kind_display(),
                'created_at': date_format(event.created_at, 'd.m.Y H:i'),
                'title': str(event.property or event.project or event.unit or 'AREALISTING'),
                'detail': _sync_event_detail(event), 'next_step': self.next_step(event),
                'run_id': event.run_id, 'reviewed': bool(event.reviewed_at),
                'url': reverse('admin:arealisting_arealistingsyncevent_change', args=[event.pk])
                       + '?' + urlencode({'return_state': state, 'return_kind': kind,
                                          'return_run': run, 'return_q': query,
                                          'return_page': page.number,
                                          **({'vue': '1'} if vue_preview else {})}),
            } for event in page],
        }
        return TemplateResponse(request, 'admin/arealisting/sync_event_list_vue.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': 'События синхронизации AREALISTING', 'shell_active': 'events',
            'vue_preview': vue_preview, 'sync_event_list_data': data,
        })

    def change_view(self, request, object_id, form_url='', extra_context=None):
        from .templatetags.arealisting_vite import matching_vue_available
        vue_preview = settings.DEBUG and request.GET.get('vue') == '1'
        if not ((settings.AREALISTING_VUE_ENABLED or vue_preview) and matching_vue_available()):
            return super().change_view(request, object_id, form_url, extra_context)
        if request.method != 'GET':
            raise PermissionDenied
        event = self.get_object(request, object_id)
        if event is None:
            raise Http404
        if not self.has_view_or_change_permission(request, event):
            raise PermissionDenied
        state = request.GET.get('return_state', 'all')
        if state not in ('all', 'open', 'checked'):
            state = 'all'
        kind = request.GET.get('return_kind', '')
        if kind not in {value for value, _ in ArealistingSyncEvent.Kind.choices}:
            kind = ''
        run = str(request.GET.get('return_run', ''))
        page = str(request.GET.get('return_page', ''))
        return_params = {'state': state, 'kind': kind, 'run': run if run.isdigit() else '',
                         'q': request.GET.get('return_q', '').strip()[:200]}
        if page.isdigit() and int(page) > 0:
            return_params['page'] = page
        if vue_preview:
            return_params['vue'] = '1'
        details = event.details or {}
        data = {
            'id': event.pk, 'kind': event.get_kind_display(),
            'created_at': date_format(event.created_at, 'd.m.Y H:i'),
            'title': str(event.property or event.project or event.unit or 'AREALISTING'),
            'detail': _sync_event_detail(event), 'next_step': self.next_step(event),
            'reviewed_at': date_format(event.reviewed_at, 'd.m.Y H:i') if event.reviewed_at else '',
            'reviewed_by': str(event.reviewed_by) if event.reviewed_by else '',
            'details': json.dumps(details, ensure_ascii=False, indent=2),
            'back_url': reverse('admin:arealisting_arealistingsyncevent_changelist')
                        + '?' + urlencode(return_params),
            'run_url': (reverse('admin:arealisting_arealistingsyncrun_change', args=[event.run_id])
                        + ('?vue=1' if vue_preview else '')
                        if request.user.has_perm('arealisting.view_arealistingsyncrun') else ''),
            'project_url': (reverse('admin:arealisting_arealistingproject_change', args=[event.project_id])
                            if event.project_id and request.user.has_perm('arealisting.view_arealistingproject') else ''),
            'unit_url': (reverse('admin:arealisting_arealistingunit_change', args=[event.unit_id])
                         + ('?vue=1' if vue_preview else '')
                         if event.unit_id and request.user.has_perm('arealisting.view_arealistingunit') else ''),
            'property_url': (reverse('admin:properties_property_change', args=[event.property_id])
                             if event.property_id and request.user.has_perm('properties.view_property') else ''),
            'review_url': (reverse('admin:arealisting_arealistingpricereview_changelist')
                           + '?' + urlencode({'status__exact': 'PENDING',
                                              **({'vue': '1'} if vue_preview else {})})
                           if event.kind == ArealistingSyncEvent.Kind.PRICE_REVIEW
                           and request.user.has_perm('arealisting.view_arealistingpricereview')
                           else reverse('admin:arealisting_review_queue')
                           + '?' + urlencode({'state': 'checked' if event.reviewed_at else 'open',
                                              'kind': event.kind,
                                              **({'vue': '1'} if vue_preview else {})})
                           if event.kind != ArealistingSyncEvent.Kind.PRICE_REVIEW else ''),
        }
        return TemplateResponse(request, 'admin/arealisting/sync_event_detail_vue.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': 'Событие синхронизации AREALISTING', 'shell_active': 'events',
            'vue_preview': vue_preview, 'sync_event_detail_data': data,
        })

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


def _property_change_detail_rows(change):
    details = change.details or {}
    rows = []

    def display(value):
        if value is None or value == '':
            return '—'
        if isinstance(value, bool):
            return 'Да' if value else 'Нет'
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    for item in details.get('changed_fields') or []:
        field = item.get('field', '')
        rows.append({'label': SOURCE_FIELD_LABELS.get(field, field),
                     'before': display(item.get('before')), 'after': display(item.get('after'))})
    activity = details.get('activity_change')
    if activity:
        rows.append({'label': 'Активность', 'before': display(activity.get('before')),
                     'after': display(activity.get('after'))})
    if details.get('units_before') != details.get('units_after'):
        before = details.get('unit_labels_before') or details.get('units_before') or []
        after = details.get('unit_labels_after') or details.get('units_after') or []
        rows.append({'label': 'Предложения',
                     'before': ', '.join(map(str, before)) or 'нет',
                     'after': ', '.join(map(str, after)) or 'нет'})
    for key, label in (('managed_added', 'Передано AREALISTING'),
                       ('managed_removed', 'Возвращено редактору'),
                       ('locked_fields_added', 'Защищено от синхронизации')):
        fields = details.get(key) or []
        if fields:
            rows.append({'label': label, 'before': '—',
                         'after': ', '.join(SOURCE_FIELD_LABELS.get(field, field) for field in fields)})
    if change.kind == ArealistingPropertyChange.Kind.DETACH:
        rows.append({'label': 'Комплекс', 'before': display(details.get('project')),
                     'after': 'Связь удалена'})
    return rows


@admin.register(ArealistingPropertyChange)
class ArealistingPropertyChangeAdmin(SourceReadOnlyAdmin):
    change_list_template = 'admin/arealisting/arealistingpropertychange/change_list.html'
    list_display = ('created_at', 'kind', 'property_link', 'project', 'actor', 'change_summary')
    list_filter = ('kind', 'created_at', PropertyHistoryFilter)
    search_fields = ('property__title', 'property__title_ru', 'project__name_en', 'project__name_ru')
    list_select_related = ('property', 'project', 'actor')
    readonly_fields = ('created_at', 'kind', 'property', 'project', 'actor', 'sync_run', 'details_display')
    fields = readonly_fields
    ordering = ('-created_at', '-pk')

    def changelist_view(self, request, extra_context=None):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        from .templatetags.arealisting_vite import matching_vue_available
        vue_preview = settings.DEBUG and request.GET.get('vue') == '1'
        vue_available = matching_vue_available()
        use_vue = bool((settings.AREALISTING_VUE_ENABLED or vue_preview) and vue_available)
        if not use_vue:
            context = {**(extra_context or {})}
            if settings.DEBUG and vue_available:
                params = request.GET.copy()
                params['vue'] = '1'
                context['vue_preview_url'] = request.path + '?' + params.urlencode()
            return super().changelist_view(request, context)

        kind = request.GET.get('kind', '')
        if kind not in {value for value, _ in ArealistingPropertyChange.Kind.choices}:
            kind = ''
        card = str(request.GET.get('card', ''))
        if not card.isdigit():
            card = ''
        query = request.GET.get('q', '').strip()[:200]
        changes = self.get_queryset(request).select_related('property', 'project', 'actor', 'sync_run')
        if card:
            changes = changes.filter(property_id=int(card))
        if query:
            changes = changes.filter(
                Q(property__title__icontains=query) | Q(property__title_ru__icontains=query)
                | Q(project__name_en__icontains=query) | Q(project__name_ru__icontains=query)
            )
        counts = {value: changes.filter(kind=value).count()
                  for value, _ in ArealistingPropertyChange.Kind.choices}
        if kind:
            changes = changes.filter(kind=kind)
        page = Paginator(changes.order_by('-created_at', '-pk'), 30).get_page(request.GET.get('page'))
        list_url = reverse('admin:arealisting_arealistingpropertychange_changelist')
        def filter_url(*, next_kind=kind, number=None):
            params = {'kind': next_kind, 'card': card, 'q': query}
            if number is not None:
                params['page'] = number
            if vue_preview:
                params['vue'] = '1'
            return list_url + '?' + urlencode(params)
        can_view_property = request.user.has_perm('properties.view_property') or request.user.has_perm('properties.change_property')
        data = {
            'filter_url': list_url, 'vue_preview': vue_preview,
            'kind': kind, 'card': card, 'query': query,
            'kinds': [{'value': value, 'label': label, 'count': counts[value],
                       'url': filter_url(next_kind=value)}
                      for value, label in ArealistingPropertyChange.Kind.choices],
            'all_count': sum(counts.values()), 'all_url': filter_url(next_kind=''),
            'result_count': page.paginator.count,
            'page': {'number': page.number, 'total': page.paginator.num_pages,
                     'previous_url': filter_url(number=page.previous_page_number()) if page.has_previous() else '',
                     'next_url': filter_url(number=page.next_page_number()) if page.has_next() else ''},
            'changes': [{
                'id': change.pk, 'kind': change.get_kind_display(),
                'property': str(change.property), 'project': str(change.project) if change.project_id else '',
                'actor': str(change.actor) if change.actor_id else 'Синхронизация',
                'created_at': date_format(change.created_at, 'd.m.Y H:i'),
                'summary': str(self.change_summary(change)),
                'property_url': (reverse('admin:properties_property_change', args=[change.property_id])
                                 if can_view_property else ''),
                'url': reverse('admin:arealisting_arealistingpropertychange_change', args=[change.pk])
                       + '?' + urlencode({'return_kind': kind, 'return_card': card,
                                          'return_q': query, 'return_page': page.number,
                                          **({'vue': '1'} if vue_preview else {})}),
            } for change in page],
        }
        return TemplateResponse(request, 'admin/arealisting/property_change_list_vue.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': 'Изменения карточек AREALISTING', 'shell_active': 'changes',
            'vue_preview': vue_preview, 'property_change_list_data': data,
        })

    def change_view(self, request, object_id, form_url='', extra_context=None):
        from .templatetags.arealisting_vite import matching_vue_available
        vue_preview = settings.DEBUG and request.GET.get('vue') == '1'
        use_vue = bool((settings.AREALISTING_VUE_ENABLED or vue_preview) and matching_vue_available())
        if not use_vue:
            return super().change_view(request, object_id, form_url, extra_context)
        if request.method != 'GET':
            raise PermissionDenied
        change = self.get_object(request, object_id)
        if change is None:
            raise Http404
        if not self.has_view_or_change_permission(request, change):
            raise PermissionDenied
        kind = request.GET.get('return_kind', '')
        if kind not in {value for value, _ in ArealistingPropertyChange.Kind.choices}:
            kind = ''
        card = str(request.GET.get('return_card', ''))
        if not card.isdigit():
            card = ''
        page = str(request.GET.get('return_page', ''))
        return_params = {'kind': kind, 'card': card, 'q': request.GET.get('return_q', '').strip()[:200]}
        if page.isdigit() and int(page) > 0:
            return_params['page'] = page
        if vue_preview:
            return_params['vue'] = '1'
        can_view_property = request.user.has_perm('properties.view_property') or request.user.has_perm('properties.change_property')
        data = {
            'id': change.pk, 'kind': change.get_kind_display(),
            'property': str(change.property), 'project': str(change.project) if change.project_id else '',
            'actor': str(change.actor) if change.actor_id else 'Синхронизация',
            'created_at': date_format(change.created_at, 'd.m.Y H:i'),
            'summary': str(self.change_summary(change)),
            'rows': _property_change_detail_rows(change),
            'property_url': (reverse('admin:properties_property_change', args=[change.property_id])
                             if can_view_property else ''),
            'sync_run_url': (reverse('admin:arealisting_arealistingsyncrun_change', args=[change.sync_run_id])
                             + ('?vue=1' if vue_preview else '')
                             if change.sync_run_id and request.user.has_perm('arealisting.view_arealistingsyncrun') else ''),
            'back_url': reverse('admin:arealisting_arealistingpropertychange_changelist')
                        + '?' + urlencode(return_params),
        }
        return TemplateResponse(request, 'admin/arealisting/property_change_detail_vue.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': f'Изменение карточки #{change.pk}', 'shell_active': 'changes',
            'vue_preview': vue_preview, 'property_change_detail_data': data,
        })

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
    change_list_template = 'admin/arealisting/arealistingsyncstate/change_list.html'
    list_display = ('key', 'status', 'last_successful_sync_at', 'updated_at')
    list_filter = ('status',)
    readonly_fields = tuple(field.name for field in ArealistingSyncState._meta.fields)

    def _row(self, state, *, vue_preview=False):
        is_lock = state.key == ArealistingSyncService.LOCK_KEY
        resource = state.key.removeprefix('resource:') if state.key.startswith('resource:') else ''
        stale = bool(is_lock and state.status == ArealistingSyncState.Status.RUNNING
                     and (not state.current_started_at
                          or state.current_started_at < timezone.now() - ArealistingSyncService.LOCK_STALE_AFTER))
        return {
            'id': state.pk, 'key': state.key,
            'name': 'Общее состояние' if is_lock else _sync_resource_label(resource) if resource else state.key,
            'is_lock': is_lock, 'stale': stale, 'status': state.status,
            'status_label': 'Возможное зависание' if stale else state.get_status_display(),
            'current_started_at': date_format(state.current_started_at, 'd.m.Y H:i')
                                  if state.current_started_at else '',
            'last_successful_sync_at': date_format(state.last_successful_sync_at, 'd.m.Y H:i')
                                       if state.last_successful_sync_at else '',
            'updated_at': date_format(state.updated_at, 'd.m.Y H:i'),
            'last_error': state.last_error or '',
            'url': reverse('admin:arealisting_arealistingsyncstate_change', args=[state.pk])
                   + ('?vue=1' if vue_preview else ''),
        }

    def changelist_view(self, request, extra_context=None):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        from .templatetags.arealisting_vite import matching_vue_available
        vue_preview = settings.DEBUG and request.GET.get('vue') == '1'
        vue_available = matching_vue_available()
        if not ((settings.AREALISTING_VUE_ENABLED or vue_preview) and vue_available):
            context = {**(extra_context or {})}
            if settings.DEBUG and vue_available:
                params = request.GET.copy()
                params['vue'] = '1'
                context['vue_preview_url'] = request.path + '?' + params.urlencode()
            return super().changelist_view(request, context)

        states = list(self.get_queryset(request).order_by('key'))
        rows = [self._row(state, vue_preview=vue_preview) for state in states]
        lock = next((row for row in rows if row['is_lock']), None)
        resources = [row for row in rows if not row['is_lock']]
        latest_run = ArealistingSyncRun.objects.order_by('-started_at', '-pk').first()
        latest_successful_run = ArealistingSyncRun.objects.filter(
            status=ArealistingSyncRun.Status.SUCCESS,
        ).order_by('-started_at', '-pk').first()
        latest_job = ArealistingSyncJob.objects.order_by('-created_at', '-pk').first()
        data = {
            'lock': lock, 'resources': resources,
            'latest_job': ({'status': latest_job.status,
                            'status_label': latest_job.get_status_display(),
                            'created_at': date_format(latest_job.created_at, 'd.m.Y H:i'),
                            'error': latest_job.error or ''}
                           if latest_job else None),
            'last_successful_at': (date_format(latest_successful_run.finished_at, 'd.m.Y H:i')
                                   if latest_successful_run and latest_successful_run.finished_at else ''),
            'latest_run': ({'id': latest_run.pk, 'status': latest_run.status,
                            'status_label': latest_run.get_status_display(),
                            'started_at': date_format(latest_run.started_at, 'd.m.Y H:i'),
                            'url': reverse('admin:arealisting_arealistingsyncrun_change', args=[latest_run.pk])
                                   + ('?vue=1' if vue_preview else '')}
                           if latest_run and request.user.has_perm('arealisting.view_arealistingsyncrun') else None),
            'history_url': (reverse('admin:arealisting_arealistingsyncrun_changelist')
                            + ('?vue=1' if vue_preview else '')
                            if request.user.has_perm('arealisting.view_arealistingsyncrun') else ''),
        }
        return TemplateResponse(request, 'admin/arealisting/sync_state_list_vue.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': 'Состояние синхронизации AREALISTING', 'shell_active': 'state',
            'vue_preview': vue_preview, 'sync_state_list_data': data,
        })

    def change_view(self, request, object_id, form_url='', extra_context=None):
        from .templatetags.arealisting_vite import matching_vue_available
        vue_preview = settings.DEBUG and request.GET.get('vue') == '1'
        if not ((settings.AREALISTING_VUE_ENABLED or vue_preview) and matching_vue_available()):
            return super().change_view(request, object_id, form_url, extra_context)
        if request.method != 'GET':
            raise PermissionDenied
        state = self.get_object(request, object_id)
        if state is None:
            raise Http404
        if not self.has_view_or_change_permission(request, state):
            raise PermissionDenied
        data = {
            'row': self._row(state, vue_preview=vue_preview),
            'back_url': reverse('admin:arealisting_arealistingsyncstate_changelist')
                        + ('?vue=1' if vue_preview else ''),
            'history_url': (reverse('admin:arealisting_arealistingsyncrun_changelist')
                            + ('?vue=1' if vue_preview else '')
                            if request.user.has_perm('arealisting.view_arealistingsyncrun') else ''),
        }
        return TemplateResponse(request, 'admin/arealisting/sync_state_detail_vue.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': 'Состояние синхронизации AREALISTING', 'shell_active': 'state',
            'vue_preview': vue_preview, 'sync_state_detail_data': data,
        })
