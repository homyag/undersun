"""Durable AREALISTING photo imports, executed outside admin HTTP requests."""

import logging
import subprocess
import sys
from datetime import timedelta

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from ..models import ArealistingListingGroup, ArealistingMediaJob
from .media import preview_group_media, sync_group_media


logger = logging.getLogger(__name__)
ACTIVE_STATUSES = (ArealistingMediaJob.Status.PENDING, ArealistingMediaJob.Status.RUNNING)


@transaction.atomic
def queue_media_job(group_id, *, selected_asset_ids, actor=None, prune_missing=True, preferred_main_asset_id=None):
    group = ArealistingListingGroup.objects.select_for_update().get(pk=group_id)
    active = group.media_jobs.filter(status__in=ACTIVE_STATUSES).order_by('-pk').first()
    if active:
        return active, False
    selected = sorted({int(value) for value in selected_asset_ids})
    preview = preview_group_media(group.pk, enable=True, selected_asset_ids=selected,
                                  preferred_main_asset_id=preferred_main_asset_id)
    job = ArealistingMediaJob.objects.create(
        group=group,
        requested_by=actor,
        selected_asset_ids=selected,
        preferred_main_asset_id=preview['preferred_main_asset_id'],
        preview_fingerprint=preview['fingerprint'],
        prune_missing=prune_missing,
    )
    return job, True


def start_media_worker(*, limit=10):
    """Launch a short-lived management command, following the blog job pattern."""
    log_path = settings.BASE_DIR / 'logs' / 'arealisting_media_worker.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, 'a', encoding='utf-8') as log_file:
        subprocess.Popen(
            [sys.executable, str(settings.BASE_DIR / 'manage.py'),
             'process_arealisting_media_jobs', '--limit', str(max(1, min(limit, 10)))],
            cwd=settings.BASE_DIR,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            close_fds=True,
            start_new_session=True,
        )
    return log_path


def recover_stale_media_jobs(*, minutes=20):
    cutoff = timezone.now() - timedelta(minutes=minutes)
    return ArealistingMediaJob.objects.filter(
        status=ArealistingMediaJob.Status.RUNNING, updated_at__lt=cutoff,
    ).update(
        status=ArealistingMediaJob.Status.FAILED,
        error='Обработчик остановился. Повторите импорт из группы.',
        finished_at=timezone.now(),
    )


def process_media_job(job_id, *, session=None):
    now = timezone.now()
    claimed = ArealistingMediaJob.objects.filter(
        pk=job_id, status=ArealistingMediaJob.Status.PENDING,
    ).update(status=ArealistingMediaJob.Status.RUNNING, started_at=now, updated_at=now)
    if not claimed:
        return False
    job = ArealistingMediaJob.objects.select_related('group').get(pk=job_id)

    def progress(kind, *, total=None, asset=None, role=None, error='', image_id=None):
        if kind == 'plan':
            job.total = total
            job.save(update_fields=('total', 'updated_at'))
            return
        row = {
            'asset_id': asset.pk,
            'title': str(asset),
            'source_url': asset.source_url,
            'role': role,
            'status': kind,
            'error': str(error or '')[:1000],
            'image_id': image_id,
        }
        job.results = [*job.results, row]
        job.processed += 1
        job.save(update_fields=('results', 'processed', 'updated_at'))

    try:
        preview = preview_group_media(
            job.group_id, enable=True, selected_asset_ids=job.selected_asset_ids,
            preferred_main_asset_id=job.preferred_main_asset_id,
        )
        if preview['fingerprint'] != job.preview_fingerprint:
            raise ValueError('Состав фото изменился после постановки в очередь. Проверьте фото и запустите импорт заново.')
        if session is None:
            with requests.Session() as http:
                totals = sync_group_media(
                    job.group_id, session=http, enable=True,
                    selected_asset_ids=job.selected_asset_ids,
                    preferred_main_asset_id=job.preferred_main_asset_id,
                    prune_missing=job.prune_missing,
                    progress_callback=progress,
                )
        else:
            totals = sync_group_media(
                job.group_id, session=session, enable=True,
                selected_asset_ids=job.selected_asset_ids,
                preferred_main_asset_id=job.preferred_main_asset_id,
                prune_missing=job.prune_missing,
                progress_callback=progress,
            )
        job.totals = totals
        job.status = (ArealistingMediaJob.Status.PARTIAL
                      if totals['errors'] or totals['skipped'] else ArealistingMediaJob.Status.SUCCESS)
        job.finished_at = timezone.now()
        job.save(update_fields=('totals', 'status', 'finished_at', 'updated_at'))
    except (ValidationError, ValueError) as exc:
        job.status = ArealistingMediaJob.Status.FAILED
        job.error = (' '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc))[:1000]
        job.finished_at = timezone.now()
        job.save(update_fields=('status', 'error', 'finished_at', 'updated_at'))
    except Exception as exc:
        logger.exception('AREALISTING media job %s failed', job.pk)
        job.status = ArealistingMediaJob.Status.FAILED
        job.error = str(exc)[:1000] or 'Не удалось выполнить импорт.'
        job.finished_at = timezone.now()
        job.save(update_fields=('status', 'error', 'finished_at', 'updated_at'))
    return True
