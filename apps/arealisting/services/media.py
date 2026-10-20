"""Controlled, idempotent import of AREALISTING images into PropertyImage."""

import hashlib
import json
import os
import tempfile
from urllib.parse import unquote, urlsplit

import requests
from PIL import Image, UnidentifiedImageError
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.properties.models import PropertyImage

from ..models import (
    ArealistingAsset,
    ArealistingListingGroup,
    ArealistingPropertyAsset,
)
from .field_ownership import ordered_source_fields


IMAGE_CONTENT_TYPES = {
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/webp': '.webp',
}
MEDIA_FIELDS = ('images', 'floorplans')
MAX_SELECTED_MEDIA_ASSETS = 24
FLOOR_PLAN_HINTS = (
    'floorplan', 'floor-plan', 'floor_plan', 'floor plan',
    'unit-plan', 'unit_plan', 'unit plan', 'layout', 'masterplan', 'master-plan',
)
NON_IMAGE_DOCUMENT_SUFFIXES = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt'}


def _allowed_media_url(url):
    parsed = urlsplit(str(url or ''))
    allowed_hosts = {str(host).strip().lower() for host in settings.AREALISTING_MEDIA_HOSTS}
    return parsed.scheme == 'https' and (parsed.hostname or '').lower() in allowed_hosts


def _asset_filename(asset, extension):
    source_name = os.path.basename(unquote(urlsplit(asset.source_url).path))
    base = os.path.splitext(source_name)[0]
    base = ''.join(char if char.isalnum() or char in '-_' else '-' for char in base)
    base = base.strip('-_')[:70] or asset.source_key[:24]
    return f'{base}-{asset.source_key[:12]}{extension}'


def _record_asset_error(asset, message):
    asset.last_error = str(message)[:1000]
    asset.save(update_fields=('last_error', 'updated_at'))


def download_asset(asset, *, session=None):
    """Download and validate one image asset once; failures stay retryable."""
    if asset.file and asset.downloaded_at:
        try:
            if asset.file.storage.exists(asset.file.name):
                return True
        except OSError:
            pass
    if not _allowed_media_url(asset.source_url):
        _record_asset_error(asset, 'Недопустимый домен или протокол изображения.')
        return False

    http = session or requests.Session()
    response = None
    temporary = tempfile.SpooledTemporaryFile(max_size=2 * 1024 * 1024)
    try:
        response = http.get(
            asset.source_url,
            stream=True,
            timeout=settings.AREALISTING_MEDIA_TIMEOUT,
            allow_redirects=True,
        )
        response.raise_for_status()
        if not _allowed_media_url(response.url):
            raise ValueError('Перенаправление изображения на недопустимый домен.')
        content_type = response.headers.get('Content-Type', '').split(';', 1)[0].lower()
        extension = IMAGE_CONTENT_TYPES.get(content_type)
        if extension is None:
            raise ValueError(f'Неподдерживаемый Content-Type: {content_type or "не указан"}.')
        content_length = response.headers.get('Content-Length')
        if content_length and int(content_length) > settings.AREALISTING_MEDIA_MAX_BYTES:
            raise ValueError('Изображение превышает допустимый размер.')

        checksum = hashlib.sha256()
        size = 0
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            size += len(chunk)
            if size > settings.AREALISTING_MEDIA_MAX_BYTES:
                raise ValueError('Изображение превышает допустимый размер.')
            checksum.update(chunk)
            temporary.write(chunk)
        if not size:
            raise ValueError('Получен пустой файл изображения.')

        temporary.seek(0)
        with Image.open(temporary) as image:
            image.verify()
        temporary.seek(0)
        asset.file.save(_asset_filename(asset, extension), File(temporary), save=False)
        asset.checksum = checksum.hexdigest()
        asset.downloaded_at = timezone.now()
        asset.last_error = ''
        asset.save(update_fields=('file', 'checksum', 'downloaded_at', 'last_error', 'updated_at'))
        return True
    except (OSError, ValueError, requests.RequestException, UnidentifiedImageError) as exc:
        _record_asset_error(asset, exc)
        return False
    finally:
        temporary.close()
        if response is not None:
            response.close()
        if session is None:
            http.close()


def _looks_like_floor_plan(asset):
    if asset.asset_type in {
        ArealistingAsset.AssetType.FLOOR_PLAN,
        ArealistingAsset.AssetType.MASTER_PLAN,
    }:
        return True
    filename = unquote(urlsplit(asset.source_url).path).lower()
    return any(hint in filename for hint in FLOOR_PLAN_HINTS)


def candidate_media_assets(project, units):
    """Return ordered, de-duplicated images eligible for one draft/group."""
    unit_ids = [unit.pk for unit in units]
    queryset = ArealistingAsset.objects.filter(is_active=True).filter(
        Q(project=project, unit__isnull=True, asset_type__in=(
            ArealistingAsset.AssetType.PROJECT_GALLERY,
            ArealistingAsset.AssetType.FLOOR_PLAN,
            ArealistingAsset.AssetType.MASTER_PLAN,
            ArealistingAsset.AssetType.PHOTOS_RENDERS,
        ))
        | Q(unit_id__in=unit_ids, asset_type=ArealistingAsset.AssetType.UNIT_GALLERY)
    ).select_related('unit')
    assets = sorted(
        queryset,
        key=lambda asset: (
            0 if asset.asset_type == ArealistingAsset.AssetType.PROJECT_GALLERY else 1,
            asset.position,
            asset.pk,
        ),
    )
    result = []
    seen_urls = set()
    for asset in assets:
        suffix = os.path.splitext(urlsplit(asset.source_url).path)[1].lower()
        if (
            asset.asset_type not in {
                ArealistingAsset.AssetType.PROJECT_GALLERY,
                ArealistingAsset.AssetType.UNIT_GALLERY,
            }
            and suffix in NON_IMAGE_DOCUMENT_SUFFIXES
        ):
            continue
        if asset.source_url in seen_urls:
            continue
        seen_urls.add(asset.source_url)
        result.append((
            asset,
            ArealistingPropertyAsset.Role.FLOOR_PLAN
            if _looks_like_floor_plan(asset)
            else ArealistingPropertyAsset.Role.GALLERY,
        ))
    return result


def validate_selected_media_assets(project, units, asset_ids, *, max_count=MAX_SELECTED_MEDIA_ASSETS):
    if not isinstance(asset_ids, list) or (max_count is not None and len(asset_ids) > max_count):
        raise ValidationError(
            f'Можно выбрать не более {max_count} изображений.'
        )
    try:
        normalized = {int(value) for value in asset_ids}
    except (TypeError, ValueError) as exc:
        raise ValidationError('Некорректный список изображений AREALISTING.') from exc
    eligible = {asset.pk for asset, _role in candidate_media_assets(project, units)}
    if not normalized <= eligible:
        raise ValidationError(
            'Одно из выбранных изображений больше не относится к этим предложениям. '
            'Обновите экран.'
        )
    return normalized


def _candidate_assets(group):
    return candidate_media_assets(group.project, list(group.units.all()))


def enable_group_media(group):
    fields = set(group.source_owned_fields or [])
    fields.update(MEDIA_FIELDS)
    group.source_owned_fields = ordered_source_fields(fields)
    group.save(update_fields=('source_owned_fields', 'updated_at'))


def _allowed_roles(group, *, enable=False):
    owned = set(group.source_owned_fields or [])
    if enable:
        owned.update(MEDIA_FIELDS)
    locked = set(group.locked_fields or [])
    roles = set()
    if 'images' in owned and 'images' not in locked:
        roles.add(ArealistingPropertyAsset.Role.GALLERY)
    if 'floorplans' in owned and 'floorplans' not in locked:
        roles.add(ArealistingPropertyAsset.Role.FLOOR_PLAN)
    return roles


def _selected_candidates(group, allowed_roles, selected_asset_ids=None):
    candidates = [item for item in _candidate_assets(group) if item[1] in allowed_roles]
    if selected_asset_ids is None:
        excluded = set(group.excluded_media_source_keys or [])
        candidates = [item for item in candidates if item[0].source_key not in excluded]
    else:
        selected = validate_selected_media_assets(
            group.project, list(group.units.all()), list(selected_asset_ids), max_count=None,
        )
        candidates = [item for item in candidates if item[0].pk in selected]
    return candidates


def preview_group_media(group_id, *, enable=False, selected_asset_ids=None, preferred_main_asset_id=None):
    """Read-only account of what sync_group_media will attempt."""
    group = ArealistingListingGroup.objects.select_related('project', 'property').get(pk=group_id)
    roles = _allowed_roles(group, enable=enable)
    available = [item for item in _candidate_assets(group) if item[1] in roles] if group.property_id else []
    candidates = _selected_candidates(group, roles, selected_asset_ids) if group.property_id else []
    links = list(group.property_assets.select_related('asset', 'property_image'))
    by_asset = {link.asset_id: link for link in links}
    selected_ids = {asset.pk for asset, _role in candidates}
    if preferred_main_asset_id not in (None, ''):
        try:
            preferred_main_asset_id = int(preferred_main_asset_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError('Выберите главное фото из отмеченных фото галереи.') from exc
        if not any(asset.pk == preferred_main_asset_id and role == ArealistingPropertyAsset.Role.GALLERY
                   for asset, role in candidates):
            raise ValidationError('Главным может быть только отмеченное фото галереи.')
    else:
        preferred_main_asset_id = None
    additions, updates, removals = [], [], []
    for asset, role in candidates:
        link = by_asset.get(asset.pk)
        item = {'asset': asset, 'role': role, 'image': link.property_image if link else None}
        (updates if link and link.property_image_id else additions).append(item)
    for link in links:
        if link.role in roles and link.asset_id not in selected_ids:
            removals.append({'asset': link.asset, 'role': link.role, 'image': link.property_image})
    available_ids = {asset.pk for asset, _role in available}
    missing_removals = [item for item in removals if item['asset'].pk not in available_ids]
    removed_image_ids = {item['image'].pk for item in removals if item['image']}
    images = list(group.property.images.order_by('order', 'pk')) if group.property_id else []
    current_main = next((image for image in images if image.is_main), None)
    current_main_asset_id = next((link.asset_id for link in links
                                  if current_main and link.property_image_id == current_main.pk), None)
    manual_ids = {image.pk for image in images} - {link.property_image_id for link in links}
    main_unchanged = bool(current_main and current_main.pk not in removed_image_ids)
    if preferred_main_asset_id:
        main_asset = next(asset for asset, role in candidates if asset.pk == preferred_main_asset_id)
        main_image = by_asset.get(preferred_main_asset_id).property_image if preferred_main_asset_id in by_asset else None
    elif main_unchanged:
        main_image = current_main
        main_asset = None
    else:
        # PropertyImage.save makes the first successfully created image main.
        main_asset = additions[0]['asset'] if additions else None
        manual_gallery = [image for image in images if image.pk in manual_ids
                          and image.image_type == 'main']
        kept_gallery = [item['image'] for item in updates
                        if item['role'] == ArealistingPropertyAsset.Role.GALLERY]
        main_image = (manual_gallery + kept_gallery)[0] if not main_asset and (manual_gallery or kept_gallery) else None
    snapshot = {
        'group': group.pk,
        'property': group.property_id,
        'owned': sorted(group.source_owned_fields or []),
        'locked': sorted(group.locked_fields or []),
        'excluded': sorted(group.excluded_media_source_keys or []),
        'units': sorted(group.units.values_list('pk', flat=True)),
        'available': [(asset.pk, role, asset.source_url, asset.position, asset.last_error)
                      for asset, role in available],
        'selected': sorted(selected_ids),
        'preferred_main_asset_id': preferred_main_asset_id,
        'links': [(link.pk, link.asset_id, link.role, link.property_image_id)
                  for link in links],
        'images': [(image.pk, image.order, image.is_main, image.image_type) for image in images],
    }
    fingerprint = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    return {
        'group': group, 'additions': additions, 'updates': updates, 'removals': removals,
        'missing_removals': missing_removals,
        'available': [{'asset': asset, 'role': role, 'selected': asset.pk in selected_ids,
                       'image': by_asset[asset.pk].property_image if asset.pk in by_asset else None}
                      for asset, role in available],
        'selected_ids': [asset.pk for asset, _role in candidates],
        'preferred_main_asset_id': preferred_main_asset_id,
        'current_main_asset_id': current_main_asset_id,
        'main_image': main_image, 'main_asset': main_asset,
        'main_changes': bool(preferred_main_asset_id and preferred_main_asset_id != current_main_asset_id) or not main_unchanged,
        'manual_count': len(manual_ids),
        'fingerprint': fingerprint, 'can_import': bool(group.property_id and roles and (candidates or removals)),
    }


def _create_property_image(group, asset, role, order):
    asset.file.open('rb')
    try:
        source_name = os.path.basename(unquote(urlsplit(asset.source_url).path))[:100]
        image = PropertyImage(
            property=group.property,
            title=source_name,
            order=order,
            image_type='floorplan' if role == ArealistingPropertyAsset.Role.FLOOR_PLAN else 'main',
            frame_type='floorplan' if role == ArealistingPropertyAsset.Role.FLOOR_PLAN else 'other',
        )
        image.image.save(
            _asset_filename(asset, os.path.splitext(asset.file.name)[1]),
            File(asset.file),
            save=True,
        )
        return image
    finally:
        asset.file.close()


def sync_group_media(
    group_id,
    *,
    session=None,
    enable=False,
    selected_asset_ids=None,
    preferred_main_asset_id=None,
    prune_missing=True,
    progress_callback=None,
):
    """Import/update one group's images without touching manually managed files."""
    group = ArealistingListingGroup.objects.select_related('project', 'property').get(pk=group_id)
    if enable:
        enable_group_media(group)
    allowed_roles = _allowed_roles(group)
    report = {'downloaded': 0, 'created': 0, 'updated': 0, 'deleted': 0, 'skipped': 0, 'errors': 0}
    if not group.property_id or not allowed_roles:
        report['skipped'] += 1
        if progress_callback:
            progress_callback('plan', total=0)
        return report

    candidates = _selected_candidates(group, allowed_roles, selected_asset_ids)
    if preferred_main_asset_id is not None:
        preferred_main_asset_id = preview_group_media(
            group.pk, selected_asset_ids=selected_asset_ids,
            preferred_main_asset_id=preferred_main_asset_id,
        )['preferred_main_asset_id']
    selected_ids = {asset.pk for asset, role in candidates}
    links = {
        link.asset_id: link
        for link in group.property_assets.select_related('property_image', 'asset')
    }
    to_delete = [link for link in links.values()
                 if prune_missing and link.role in allowed_roles and link.asset_id not in selected_ids]
    current_main = group.property.images.filter(is_main=True).first()
    available_asset_ids = {asset.pk for asset, _role in _candidate_assets(group)}
    excluded_source_keys = set(group.excluded_media_source_keys or [])
    deferred_main_link = next((link for link in links.values()
                               if preferred_main_asset_id and current_main
                               and link.property_image_id == current_main.pk
                               and link.asset_id not in selected_ids
                               and link.role in allowed_roles
                               and (prune_missing or link.asset.source_key in excluded_source_keys
                                    or link.asset_id not in available_asset_ids)), None)
    if deferred_main_link in to_delete:
        to_delete.remove(deferred_main_link)
    if progress_callback:
        progress_callback('plan', total=len(candidates) + len(to_delete) + bool(deferred_main_link))
    for link in to_delete:
        if link.property_image_id:
            link.property_image.delete()
        link.delete()
        report['deleted'] += 1
        if progress_callback:
            progress_callback('deleted', asset=link.asset, role=link.role)

    manual_orders = group.property.images.exclude(
        arealisting_property_asset__isnull=False
    ).values_list('order', flat=True)
    next_order = (max(manual_orders, default=-1) + 1)
    gallery_index = 0
    floorplan_index = 0
    preferred_main_loaded = False
    for asset, role in candidates:
        link, _ = ArealistingPropertyAsset.objects.get_or_create(
            listing_group=group,
            asset=asset,
            defaults={'role': role},
        )
        order = next_order + (
            gallery_index if role == ArealistingPropertyAsset.Role.GALLERY
            else len(candidates) + floorplan_index
        )
        if role == ArealistingPropertyAsset.Role.GALLERY:
            gallery_index += 1
        else:
            floorplan_index += 1
        if not download_asset(asset, session=session):
            report['errors'] += 1
            if progress_callback:
                progress_callback('error', asset=asset, role=role, error=asset.last_error)
            continue
        report['downloaded'] += 1
        if link.property_image_id:
            PropertyImage.objects.filter(pk=link.property_image_id).update(
                order=order,
                image_type='floorplan' if role == ArealistingPropertyAsset.Role.FLOOR_PLAN else 'main',
                frame_type='floorplan' if role == ArealistingPropertyAsset.Role.FLOOR_PLAN else 'other',
            )
            if link.role != role:
                link.role = role
                link.save(update_fields=('role', 'updated_at'))
            report['updated'] += 1
            if asset.pk == preferred_main_asset_id:
                preferred_main_loaded = True
            if progress_callback:
                progress_callback('updated', asset=asset, role=role, image_id=link.property_image_id)
            continue
        try:
            with transaction.atomic():
                image = _create_property_image(group, asset, role, order)
                link.property_image = image
                link.role = role
                link.save(update_fields=('property_image', 'role', 'updated_at'))
            report['created'] += 1
            if asset.pk == preferred_main_asset_id:
                preferred_main_loaded = True
            if progress_callback:
                progress_callback('created', asset=asset, role=role, image_id=image.pk)
        except (OSError, ValueError) as exc:
            _record_asset_error(asset, f'Ошибка сохранения PropertyImage: {exc}')
            report['errors'] += 1
            if progress_callback:
                progress_callback('error', asset=asset, role=role, error=asset.last_error)

    if preferred_main_loaded:
        preferred_image = group.property_assets.get(asset_id=preferred_main_asset_id).property_image
        PropertyImage.objects.filter(property=group.property, is_main=True).exclude(pk=preferred_image.pk).update(is_main=False)
        PropertyImage.objects.filter(pk=preferred_image.pk).update(is_main=True)
        if deferred_main_link:
            deferred_main_link.property_image.delete()
            deferred_main_link.delete()
            report['deleted'] += 1
            if progress_callback:
                progress_callback('deleted', asset=deferred_main_link.asset, role=deferred_main_link.role)
    if not group.property.images.filter(is_main=True).exists():
        first_gallery = group.property.images.filter(image_type='main').order_by('order', 'pk').first()
        if first_gallery:
            PropertyImage.objects.filter(pk=first_gallery.pk).update(is_main=True)
    return report
