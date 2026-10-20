import hashlib
from datetime import timedelta, timezone as datetime_timezone
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Count, Max, Min
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.arealisting.client import ArealistingClient
from apps.arealisting.exceptions import (
    ArealistingConfigurationError,
    ArealistingSyncInProgressError,
)
from apps.arealisting.models import (
    ArealistingAsset,
    ArealistingListingGroup,
    ArealistingLocationMapping,
    ArealistingPaymentPlan,
    ArealistingProject,
    ArealistingSyncEvent,
    ArealistingSyncRun,
    ArealistingSyncState,
    ArealistingUnit,
)


RESOURCE_PROJECTS = 'projects'
RESOURCE_UNITS = 'units'
RESOURCE_PAYMENT_PLANS = 'payment_plans'
RESOURCE_DELETIONS = 'deletions'
SUPPORTED_RESOURCES = (
    RESOURCE_PROJECTS,
    RESOURCE_UNITS,
    RESOURCE_PAYMENT_PLANS,
    RESOURCE_DELETIONS,
)
UNIT_REVIEW_FIELDS = ('bedrooms', 'bathrooms', 'floor', 'internal_area_sqm',
                      'plot_size_sqm', 'sea_view', 'property_type', 'furnishing')


def _empty_stats():
    return {
        'seen': 0,
        'created': 0,
        'updated': 0,
        'deleted': 0,
        'skipped': 0,
        'errors': 0,
        'available_created': 0,
        'price_changed': 0,
        'became_sold': 0,
    }


def _decimal_or_none(value):
    if value in (None, ''):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f'Invalid decimal value: {value!r}') from exc


def _integer_or_none(value):
    if value in (None, ''):
        return None
    if isinstance(value, bool):
        raise ValueError(f'Invalid integer value: {value!r}')
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'Invalid integer value: {value!r}') from exc


def _datetime_or_none(value):
    if value in (None, ''):
        return None
    if isinstance(value, timezone.datetime):
        parsed = value
    else:
        parsed = parse_datetime(str(value))
    if parsed is None:
        raise ValueError(f'Invalid datetime value: {value!r}')
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, datetime_timezone.utc)
    return parsed


def _dict_or_empty(value):
    return value if isinstance(value, dict) else {}


def _list_or_empty(value):
    return value if isinstance(value, list) else []


def _required_external_id(payload):
    value = payload.get('external_id') if isinstance(payload, dict) else None
    if not isinstance(value, str) or not value.strip():
        raise ValueError('A source record is missing external_id.')
    return value.strip()


class ArealistingSyncService:
    """Persist the partner feed without publishing Property records automatically."""

    LOCK_KEY = 'global-lock'
    LOCK_STALE_AFTER = timedelta(hours=2)

    def __init__(self, *, client=None):
        self.client = client or ArealistingClient()

    @staticmethod
    def _state_key(resource):
        return f'resource:{resource}'

    @staticmethod
    def _run_mode(*, full, project_ids, ids):
        if project_ids or ids:
            return ArealistingSyncRun.Mode.TARGETED
        if full:
            return ArealistingSyncRun.Mode.FULL
        return ArealistingSyncRun.Mode.INCREMENTAL

    @staticmethod
    def _normalize_resources(resources):
        requested = set()
        for resource in resources or (RESOURCE_PROJECTS,):
            value = str(resource).strip().replace('-', '_')
            if value not in SUPPORTED_RESOURCES:
                raise ArealistingConfigurationError(
                    f'Unsupported AREALISTING resource: {resource}'
                )
            requested.add(value)
        return tuple(resource for resource in SUPPORTED_RESOURCES if resource in requested)

    @classmethod
    def _acquire_lock(cls, started_at):
        with transaction.atomic():
            ArealistingSyncState.objects.get_or_create(key=cls.LOCK_KEY)
            lock = ArealistingSyncState.objects.select_for_update().get(key=cls.LOCK_KEY)
            if (
                lock.status == ArealistingSyncState.Status.RUNNING
                and lock.current_started_at
                and lock.current_started_at >= started_at - cls.LOCK_STALE_AFTER
            ):
                raise ArealistingSyncInProgressError(
                    'Another AREALISTING synchronization is already running.'
                )
            lock.status = ArealistingSyncState.Status.RUNNING
            lock.current_started_at = started_at
            lock.last_error = ''
            lock.save(update_fields=('status', 'current_started_at', 'last_error', 'updated_at'))

    @classmethod
    def _release_lock(cls, *, status, error=''):
        ArealistingSyncState.objects.filter(key=cls.LOCK_KEY).update(
            status=status,
            current_started_at=None,
            last_error=error,
            updated_at=timezone.now(),
        )

    @classmethod
    def _get_resource_since(cls, resource, explicit_since):
        if explicit_since is not None:
            return explicit_since
        return (
            ArealistingSyncState.objects.filter(key=cls._state_key(resource))
            .values_list('last_successful_sync_at', flat=True)
            .first()
        )

    @classmethod
    def _mark_resource_success(cls, resource, completed_through):
        ArealistingSyncState.objects.update_or_create(
            key=cls._state_key(resource),
            defaults={
                'status': ArealistingSyncState.Status.SUCCESS,
                'last_successful_sync_at': completed_through,
                'current_started_at': None,
                'last_error': '',
            },
        )

    @classmethod
    def _mark_resource_failure(cls, resource, error):
        ArealistingSyncState.objects.update_or_create(
            key=cls._state_key(resource),
            defaults={
                'status': ArealistingSyncState.Status.FAILED,
                'current_started_at': None,
                'last_error': error,
            },
        )

    def sync(
        self,
        *,
        resources=None,
        full=False,
        dry_run=False,
        since=None,
        limit=100,
        project_ids=None,
        ids=None,
        skip_assets=False,
    ):
        resources = self._normalize_resources(resources)
        project_ids = list(project_ids or [])
        ids = list(ids or [])
        if ids and len(resources) != 1:
            raise ArealistingConfigurationError(
                'ids can only be used when exactly one resource is selected.'
            )

        started_at = timezone.now()
        mode = self._run_mode(full=full, project_ids=project_ids, ids=ids)
        summary = {resource: _empty_stats() for resource in resources}
        run = None

        if not dry_run:
            self._acquire_lock(started_at)
            run = ArealistingSyncRun.objects.create(
                mode=mode,
                status=ArealistingSyncRun.Status.RUNNING,
                since=since,
                resources=list(resources),
                project_ids=project_ids,
            )

        current_resource = None
        try:
            for resource in resources:
                current_resource = resource
                resource_since = None if full else self._get_resource_since(resource, since)
                if not full and resource_since is None:
                    raise ArealistingConfigurationError(
                        f'No synchronization watermark for {resource}. '
                        'Run a full synchronization or pass --since.'
                    )

                if resource == RESOURCE_PROJECTS:
                    self._sync_projects(
                        stats=summary[resource],
                        seen_at=started_at,
                        full=full,
                        dry_run=dry_run,
                        updated_since=resource_since,
                        ids=ids or project_ids,
                        limit=limit,
                        skip_assets=skip_assets,
                    )
                elif resource == RESOURCE_UNITS:
                    self._sync_units(
                        stats=summary[resource],
                        run=run,
                        seen_at=started_at,
                        full=full,
                        dry_run=dry_run,
                        updated_since=resource_since,
                        project_ids=project_ids,
                        ids=ids,
                        limit=limit,
                        skip_assets=skip_assets,
                    )
                elif resource == RESOURCE_PAYMENT_PLANS:
                    self._sync_payment_plans(
                        stats=summary[resource],
                        seen_at=started_at,
                        full=full,
                        dry_run=dry_run,
                        updated_since=resource_since,
                        project_ids=project_ids,
                        ids=ids,
                        limit=limit,
                    )
                elif resource == RESOURCE_DELETIONS:
                    deletion_since = resource_since or started_at
                    self._sync_deletions(
                        stats=summary[resource],
                        dry_run=dry_run,
                        since=deletion_since,
                        limit=limit,
                    )

                is_global_scope = not project_ids and not ids
                if not dry_run and is_global_scope:
                    self._mark_resource_success(resource, started_at)

            if not dry_run and set(resources) & {RESOURCE_UNITS, RESOURCE_DELETIONS, RESOURCE_PROJECTS}:
                from .drafts import refresh_group_property
                from .pricing import update_group_price
                summary['property_updates'] = []
                summary['price_updates'] = []
                groups = ArealistingListingGroup.objects.filter(property__isnull=False)
                if project_ids:
                    groups = groups.filter(project__external_id__in=project_ids)
                if ids:
                    if RESOURCE_UNITS in resources:
                        groups = groups.filter(units__external_id__in=ids)
                    elif RESOURCE_PROJECTS in resources:
                        groups = groups.filter(project__external_id__in=ids)
                    else:
                        groups = groups.none()
                for group_id in groups.values_list('pk', flat=True).distinct():
                    refresh_group_property(group_id, reports=summary['property_updates'], sync_run=run)
                    update_group_price(group_id, reports=summary['price_updates'], sync_run=run)
                for report in summary['price_updates']:
                    if report['status'] in ('unchanged', 'rejected'):
                        continue
                    active_without_units = False
                    if (report['status'] == 'skipped'
                            and report.get('reason') == 'нет доступных выбранных предложений'):
                        from apps.properties.models import Property
                        active_without_units = Property.objects.filter(
                            pk=report['property_id'], is_active=True,
                        ).exists()
                    ArealistingSyncEvent.objects.create(
                        run=run,
                        kind=(ArealistingSyncEvent.Kind.PRICE_REVIEW
                              if report['status'] == 'review' else
                              ArealistingSyncEvent.Kind.ACTIVE_WITHOUT_UNITS
                              if active_without_units else
                              ArealistingSyncEvent.Kind.CARD_PRICE
                              if report['status'] == 'updated' else
                              ArealistingSyncEvent.Kind.PRICE_SKIPPED),
                        project_id=report['project_id'],
                        property_id=report['property_id'],
                        details={
                            'before': report['before'],
                            'after': report.get('proposed', report['after']),
                            'review_id': report.get('review_id'),
                            'reason': report.get('reason', ''),
                        },
                    )

            if run:
                run.status = ArealistingSyncRun.Status.SUCCESS
                run.finished_at = timezone.now()
                run.summary = summary
                run.save(update_fields=('status', 'finished_at', 'summary'))
                self._release_lock(status=ArealistingSyncState.Status.SUCCESS)
            return summary
        except Exception as exc:
            safe_error = str(exc)[:2000]
            if not dry_run:
                if current_resource:
                    self._mark_resource_failure(current_resource, safe_error)
                if run:
                    run.status = ArealistingSyncRun.Status.FAILED
                    run.finished_at = timezone.now()
                    run.summary = summary
                    run.error = safe_error
                    run.save(
                        update_fields=('status', 'finished_at', 'summary', 'error')
                    )
                self._release_lock(
                    status=ArealistingSyncState.Status.FAILED,
                    error=safe_error,
                )
            raise

    def _sync_projects(
        self,
        *,
        stats,
        seen_at,
        full,
        dry_run,
        updated_since,
        ids,
        limit,
        skip_assets,
    ):
        seen_ids = set()
        for payload in self.client.iter_projects(
            updated_since=updated_since,
            ids=ids,
            limit=limit,
        ):
            stats['seen'] += 1
            try:
                external_id = _required_external_id(payload)
                seen_ids.add(external_id)
                defaults = self._project_defaults(payload, seen_at)
                if dry_run:
                    continue
                with transaction.atomic():
                    project, created = ArealistingProject.objects.update_or_create(
                        external_id=external_id,
                        defaults=defaults,
                    )
                    self._sync_embedded_locations(project, payload, seen_at)
                    if not skip_assets:
                        self._sync_project_assets(project, payload)
                stats['created' if created else 'updated'] += 1
            except (TypeError, ValueError):
                stats['errors'] += 1
                raise

        if full and not dry_run and not ids:
            existing_count = ArealistingProject.objects.filter(is_deleted=False).count()
            if existing_count and not seen_ids:
                raise ArealistingConfigurationError(
                    'Full projects feed was empty; reconciliation was aborted.'
                )
            stale = ArealistingProject.objects.filter(last_seen_at__lt=seen_at, is_deleted=False)
            stats['deleted'] += stale.count()
            for project in stale.iterator():
                self._deactivate_project(project)

    @staticmethod
    def _project_defaults(payload, seen_at):
        ownership = _dict_or_empty(payload.get('ownership'))
        coordinates = _dict_or_empty(payload.get('coordinates'))
        developer = payload.get('developer')
        if isinstance(developer, dict):
            developer = developer.get('name')
        return {
            'name_en': str(payload.get('name_en') or ''),
            'name_ru': str(payload.get('name_ru') or ''),
            'description_en': str(payload.get('description_en') or ''),
            'description_ru': str(payload.get('description_ru') or ''),
            'developer_name': str(developer or ''),
            'project_type': str(payload.get('project_type') or ''),
            'construction_status': str(payload.get('construction_status') or ''),
            'completion_date': _datetime_or_none(payload.get('completion_date')),
            'freehold_available': bool(ownership.get('freehold_available', False)),
            'leasehold_available': bool(ownership.get('leasehold_available', False)),
            'maintenance_fee': _decimal_or_none(payload.get('maintenance_fee')),
            'maintenance_fee_mode': str(payload.get('maintenance_fee_mode') or ''),
            'sinking_fund': _decimal_or_none(payload.get('sinking_fund')),
            'sinking_fund_mode': str(payload.get('sinking_fund_mode') or ''),
            'latitude': _decimal_or_none(coordinates.get('lat')),
            'longitude': _decimal_or_none(coordinates.get('lng')),
            'districts': _list_or_empty(payload.get('districts')),
            'amenities': _list_or_empty(payload.get('amenities')),
            'gallery': _list_or_empty(payload.get('gallery')),
            'documents': _list_or_empty(payload.get('documents')),
            'raw_payload': payload,
            'remote_updated_at': _datetime_or_none(payload.get('updated_at')),
            'last_seen_at': seen_at,
            'is_deleted': False,
        }

    @staticmethod
    def _sync_embedded_locations(project, payload, seen_at):
        for source_location in _list_or_empty(payload.get('districts')):
            if not isinstance(source_location, dict):
                continue
            external_id = source_location.get('external_id')
            if not isinstance(external_id, str) or not external_id.strip():
                continue
            ArealistingLocationMapping.objects.update_or_create(
                external_id=external_id.strip(),
                defaults={
                    'source_name': str(source_location.get('name') or ''),
                    'description_en': str(source_location.get('description_en') or ''),
                    'description_ru': str(source_location.get('description_ru') or ''),
                    'gallery': _list_or_empty(source_location.get('gallery')),
                    'raw_payload': source_location,
                    'remote_updated_at': project.remote_updated_at,
                    'last_seen_at': seen_at,
                    'is_deleted': False,
                },
            )

    def _sync_units(
        self,
        *,
        stats,
        run,
        seen_at,
        full,
        dry_run,
        updated_since,
        project_ids,
        ids,
        limit,
        skip_assets,
    ):
        seen_ids = set()
        for payload in self.client.iter_units(
            project_ids=project_ids,
            updated_since=updated_since,
            ids=ids,
            limit=limit,
        ):
            stats['seen'] += 1
            external_id = _required_external_id(payload)
            project_external_id = payload.get('project_id')
            if not isinstance(project_external_id, str) or not project_external_id:
                stats['errors'] += 1
                raise ValueError(f'Unit {external_id} is missing project_id.')
            seen_ids.add(external_id)
            defaults = self._unit_defaults(payload, seen_at)
            if dry_run:
                continue
            project = ArealistingProject.objects.filter(
                external_id=project_external_id,
                is_deleted=False,
            ).first()
            if project is None:
                stats['errors'] += 1
                raise ValueError(
                    f'Unit {external_id} references unknown project {project_external_id}.'
                )
            with transaction.atomic():
                previous = (
                    ArealistingUnit.objects.filter(external_id=external_id)
                    .values('availability_status', 'price', 'currency', *UNIT_REVIEW_FIELDS)
                    .first()
                )
                unit, created = ArealistingUnit.objects.update_or_create(
                    external_id=external_id,
                    defaults={'project': project, **defaults},
                )
                if not skip_assets:
                    self._sync_unit_assets(unit, payload)
                if unit.listing_group_id:
                    self.recalculate_listing_group(unit.listing_group)
                event_details = []
                if created and unit.availability_status == ArealistingUnit.AvailabilityStatus.AVAILABLE:
                    event_details.append((ArealistingSyncEvent.Kind.NEW_UNIT, {}))
                elif previous:
                    if (previous['availability_status'] != ArealistingUnit.AvailabilityStatus.SOLD
                            and unit.availability_status == ArealistingUnit.AvailabilityStatus.SOLD):
                        event_details.append((ArealistingSyncEvent.Kind.SOLD, {
                            'before': previous['availability_status'], 'after': unit.availability_status,
                        }))
                    if previous['price'] != unit.price or previous['currency'] != unit.currency:
                        event_details.append((ArealistingSyncEvent.Kind.UNIT_PRICE, {
                            'before': {'price': str(previous['price']) if previous['price'] is not None else None,
                                       'currency': previous['currency']},
                            'after': {'price': str(unit.price) if unit.price is not None else None,
                                      'currency': unit.currency},
                        }))
                    if unit.listing_group_id and unit.listing_group.property_id:
                        changed_fields = [
                            {'field': field,
                             'before': str(previous[field]) if previous[field] is not None else None,
                             'after': str(getattr(unit, field)) if getattr(unit, field) is not None else None}
                            for field in UNIT_REVIEW_FIELDS
                            if previous[field] != getattr(unit, field)
                        ]
                        if changed_fields:
                            event_details.append((ArealistingSyncEvent.Kind.UNIT_FIELDS,
                                                  {'changed_fields': changed_fields}))
                for kind, details in event_details:
                    ArealistingSyncEvent.objects.create(
                        run=run, kind=kind, project=project, unit=unit,
                        property_id=unit.listing_group.property_id if unit.listing_group_id else None,
                        details={**details, 'unit_number': unit.unit_number,
                                 'unit_external_id': unit.external_id},
                    )
            stats['created' if created else 'updated'] += 1
            if created:
                if unit.availability_status == ArealistingUnit.AvailabilityStatus.AVAILABLE:
                    stats['available_created'] += 1
            elif previous:
                if (
                    previous['availability_status']
                    != ArealistingUnit.AvailabilityStatus.SOLD
                    and unit.availability_status == ArealistingUnit.AvailabilityStatus.SOLD
                ):
                    stats['became_sold'] += 1
                if (
                    previous['price'] != unit.price
                    or previous['currency'] != unit.currency
                ):
                    stats['price_changed'] += 1

        if full and not dry_run and not ids:
            stale = ArealistingUnit.objects.filter(is_deleted=False)
            if project_ids:
                stale = stale.filter(project__external_id__in=project_ids)
            existing_count = stale.count()
            if existing_count and not seen_ids:
                raise ArealistingConfigurationError(
                    'Full units feed was empty; reconciliation was aborted.'
                )
            stale = stale.filter(last_seen_at__lt=seen_at)
            stats['deleted'] += stale.count()
            for unit in stale.select_related('listing_group').iterator():
                self._deactivate_unit(unit)

    @staticmethod
    def _unit_defaults(payload, seen_at):
        return {
            'unit_number': str(payload.get('unit_number') or ''),
            'bedrooms': _integer_or_none(payload.get('bedrooms')),
            'bathrooms': _decimal_or_none(payload.get('bathrooms')),
            'floor': _integer_or_none(payload.get('floor')),
            'internal_area_sqm': _decimal_or_none(payload.get('internal_area_sqm')),
            'plot_size_sqm': _decimal_or_none(payload.get('plot_size_sqm')),
            'sea_view': payload.get('sea_view') if isinstance(payload.get('sea_view'), bool) else None,
            'availability_status': str(payload.get('availability_status') or ''),
            'property_type': str(payload.get('property_type') or ''),
            'price': _decimal_or_none(payload.get('price')),
            'currency': str(payload.get('currency') or ''),
            'price_per_sqm': _decimal_or_none(payload.get('price_per_sqm')),
            'maintenance_fee': _decimal_or_none(payload.get('maintenance_fee')),
            'maintenance_fee_mode': str(payload.get('maintenance_fee_mode') or ''),
            'sinking_fund': _decimal_or_none(payload.get('sinking_fund')),
            'sinking_fund_mode': str(payload.get('sinking_fund_mode') or ''),
            'furnishing': _list_or_empty(payload.get('furnishing')),
            'gallery': _list_or_empty(payload.get('gallery')),
            'raw_payload': payload,
            'remote_updated_at': _datetime_or_none(payload.get('updated_at')),
            'last_seen_at': seen_at,
            'is_deleted': False,
        }

    def _sync_payment_plans(
        self,
        *,
        stats,
        seen_at,
        full,
        dry_run,
        updated_since,
        project_ids,
        ids,
        limit,
    ):
        seen_ids = set()
        for payload in self.client.iter_payment_plans(
            project_ids=project_ids,
            updated_since=updated_since,
            ids=ids,
            limit=limit,
        ):
            stats['seen'] += 1
            external_id = _required_external_id(payload)
            project_external_id = payload.get('project_id')
            if not isinstance(project_external_id, str) or not project_external_id:
                stats['errors'] += 1
                raise ValueError(f'Payment plan {external_id} is missing project_id.')
            seen_ids.add(external_id)
            defaults = {
                'name': str(payload.get('name') or ''),
                'description': str(payload.get('description') or ''),
                'items': _list_or_empty(payload.get('items')),
                'raw_payload': payload,
                'remote_updated_at': _datetime_or_none(payload.get('updated_at')),
                'last_seen_at': seen_at,
                'is_deleted': False,
            }
            if dry_run:
                continue
            project = ArealistingProject.objects.filter(
                external_id=project_external_id,
                is_deleted=False,
            ).first()
            if project is None:
                stats['errors'] += 1
                raise ValueError(
                    f'Payment plan {external_id} references unknown project '
                    f'{project_external_id}.'
                )
            _, created = ArealistingPaymentPlan.objects.update_or_create(
                external_id=external_id,
                defaults={'project': project, **defaults},
            )
            stats['created' if created else 'updated'] += 1

        if full and not dry_run and not ids:
            stale = ArealistingPaymentPlan.objects.filter(is_deleted=False)
            if project_ids:
                stale = stale.filter(project__external_id__in=project_ids)
            existing_count = stale.count()
            if existing_count and not seen_ids:
                raise ArealistingConfigurationError(
                    'Full payment plans feed was empty; reconciliation was aborted.'
                )
            stale = stale.filter(last_seen_at__lt=seen_at)
            stats['deleted'] += stale.update(is_deleted=True)

    def _sync_deletions(self, *, stats, dry_run, since, limit):
        for payload in self.client.iter_deletions(since=since, limit=limit):
            stats['seen'] += 1
            external_id = _required_external_id(payload)
            entity_type = payload.get('entity_type')
            if dry_run:
                continue
            if entity_type == 'project':
                project = ArealistingProject.objects.filter(external_id=external_id).first()
                if project:
                    self._deactivate_project(project)
                    stats['deleted'] += 1
                else:
                    stats['skipped'] += 1
            elif entity_type == 'unit':
                unit = ArealistingUnit.objects.filter(external_id=external_id).first()
                if unit:
                    self._deactivate_unit(unit)
                    stats['deleted'] += 1
                else:
                    stats['skipped'] += 1
            elif entity_type == 'payment_plan':
                updated = ArealistingPaymentPlan.objects.filter(
                    external_id=external_id,
                    is_deleted=False,
                ).update(is_deleted=True)
                stats['deleted' if updated else 'skipped'] += 1
            else:
                stats['errors'] += 1
                raise ValueError(
                    f'Deletion {external_id} has unknown entity_type {entity_type!r}.'
                )

    @staticmethod
    def _asset_key(owner_type, owner_id, asset_type, source_url):
        identity = '\x1f'.join((owner_type, owner_id, asset_type, source_url))
        return hashlib.sha256(identity.encode('utf-8')).hexdigest()

    def _sync_project_assets(self, project, payload):
        active_keys = set()
        for position, source_url in enumerate(_list_or_empty(payload.get('gallery'))):
            if not isinstance(source_url, str) or not source_url:
                continue
            asset_type = ArealistingAsset.AssetType.PROJECT_GALLERY
            key = self._asset_key('project', project.external_id, asset_type, source_url)
            active_keys.add(key)
            ArealistingAsset.objects.update_or_create(
                source_key=key,
                defaults={
                    'project': project,
                    'unit': None,
                    'source_url': source_url,
                    'asset_type': asset_type,
                    'position': position,
                    'is_active': True,
                    'last_error': '',
                },
            )

        for position, document in enumerate(_list_or_empty(payload.get('documents'))):
            if not isinstance(document, dict):
                continue
            source_url = document.get('url')
            if not isinstance(source_url, str) or not source_url:
                continue
            remote_type = str(document.get('type') or '').upper()
            asset_type = {
                'FLOOR_PLAN': ArealistingAsset.AssetType.FLOOR_PLAN,
                'MASTER_PLAN': ArealistingAsset.AssetType.MASTER_PLAN,
                'PHOTOS_RENDERS': ArealistingAsset.AssetType.PHOTOS_RENDERS,
                'PRESENTATION': ArealistingAsset.AssetType.PRESENTATION,
                'DOCUMENT': ArealistingAsset.AssetType.DOCUMENT,
                'PRICE_LIST': ArealistingAsset.AssetType.PRICE_LIST,
            }.get(remote_type, ArealistingAsset.AssetType.OTHER)
            key = self._asset_key('project', project.external_id, asset_type, source_url)
            active_keys.add(key)
            ArealistingAsset.objects.update_or_create(
                source_key=key,
                defaults={
                    'project': project,
                    'unit': None,
                    'source_url': source_url,
                    'asset_type': asset_type,
                    'position': position,
                    'is_active': True,
                    'last_error': '',
                },
            )

        project.assets.exclude(source_key__in=active_keys).filter(unit__isnull=True).update(
            is_active=False
        )

    def _sync_unit_assets(self, unit, payload):
        active_keys = set()
        asset_type = ArealistingAsset.AssetType.UNIT_GALLERY
        for position, source_url in enumerate(_list_or_empty(payload.get('gallery'))):
            if not isinstance(source_url, str) or not source_url:
                continue
            key = self._asset_key('unit', unit.external_id, asset_type, source_url)
            active_keys.add(key)
            ArealistingAsset.objects.update_or_create(
                source_key=key,
                defaults={
                    'project': unit.project,
                    'unit': unit,
                    'source_url': source_url,
                    'asset_type': asset_type,
                    'position': position,
                    'is_active': True,
                    'last_error': '',
                },
            )
        unit.assets.exclude(source_key__in=active_keys).update(is_active=False)

    def _deactivate_project(self, project):
        project.is_deleted = True
        project.save(update_fields=('is_deleted', 'synced_at'))
        project.units.filter(is_deleted=False).update(is_deleted=True)
        project.payment_plans.filter(is_deleted=False).update(is_deleted=True)
        project.assets.filter(is_active=True).update(is_active=False)
        groups = project.listing_groups.select_related('property').filter(is_active=True)
        for group in groups:
            group.is_active = False
            group.available_units_count = 0
            group.save(update_fields=('is_active', 'available_units_count', 'updated_at'))

    def _deactivate_unit(self, unit):
        if unit.is_deleted:
            return
        unit.is_deleted = True
        unit.save(update_fields=('is_deleted', 'synced_at'))
        unit.assets.filter(is_active=True).update(is_active=False)
        if unit.listing_group_id:
            self.recalculate_listing_group(unit.listing_group)

    @staticmethod
    def recalculate_listing_group(group):
        available = group.units.filter(
            is_deleted=False,
            availability_status=ArealistingUnit.AvailabilityStatus.AVAILABLE,
        )
        aggregates = available.aggregate(
            available_units_count=Count('id'),
            min_price=Min('price'),
            max_price=Max('price'),
            min_area_sqm=Min('internal_area_sqm'),
            max_area_sqm=Max('internal_area_sqm'),
        )
        currencies = list(
            available.exclude(currency='')
            .values_list('currency', flat=True)
            .distinct()[:2]
        )
        validation_errors = list(group.validation_errors or [])
        validation_errors = [
            error for error in validation_errors if error != 'mixed_unit_currencies'
        ]
        currency = currencies[0] if len(currencies) == 1 else ''
        if len(currencies) > 1:
            validation_errors.append('mixed_unit_currencies')

        count = aggregates.pop('available_units_count') or 0
        group.available_units_count = count
        group.currency = currency
        group.min_price = aggregates['min_price']
        group.max_price = aggregates['max_price']
        group.min_area_sqm = aggregates['min_area_sqm']
        group.max_area_sqm = aggregates['max_area_sqm']
        group.validation_errors = validation_errors
        if count == 0:
            group.is_active = False
            group.is_ready_for_publication = False
        group.save(
            update_fields=(
                'available_units_count',
                'currency',
                'min_price',
                'max_price',
                'min_area_sqm',
                'max_area_sqm',
                'validation_errors',
                'is_active',
                'is_ready_for_publication',
                'updated_at',
            )
        )
