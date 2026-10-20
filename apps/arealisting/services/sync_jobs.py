"""Run administrator-triggered synchronizations outside HTTP requests."""

import logging
import subprocess
import sys
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from ..client import ArealistingClient
from ..exceptions import ArealistingSyncInProgressError
from ..models import ArealistingSyncJob, ArealistingSyncState
from .sync import ArealistingSyncService


logger = logging.getLogger(__name__)
ACTIVE_STATUSES = (ArealistingSyncJob.Status.PENDING, ArealistingSyncJob.Status.RUNNING)


def recover_stale_sync_jobs():
    now = timezone.now()
    ArealistingSyncJob.objects.filter(
        status=ArealistingSyncJob.Status.PENDING,
        created_at__lt=now - timedelta(minutes=5),
    ).update(status=ArealistingSyncJob.Status.FAILED, finished_at=now,
             error='Обработчик не запустился. Повторите обновление.')
    ArealistingSyncJob.objects.filter(
        status=ArealistingSyncJob.Status.RUNNING,
        started_at__lt=now - ArealistingSyncService.LOCK_STALE_AFTER,
    ).update(status=ArealistingSyncJob.Status.FAILED, finished_at=now,
             error='Обработчик остановился. Повторите обновление.')


def queue_sync_job(*, resources, project_ids=None, full=True, actor=None):
    recover_stale_sync_jobs()
    active = ArealistingSyncJob.objects.filter(status__in=ACTIVE_STATUSES).first()
    if active:
        return active, False
    lock = ArealistingSyncState.objects.filter(key=ArealistingSyncService.LOCK_KEY).first()
    if (lock and lock.status == ArealistingSyncState.Status.RUNNING
            and lock.current_started_at
            and lock.current_started_at >= timezone.now() - ArealistingSyncService.LOCK_STALE_AFTER):
        raise ArealistingSyncInProgressError('Другое обновление AREALISTING уже выполняется.')
    try:
        with transaction.atomic():
            job = ArealistingSyncJob.objects.create(
                resources=list(resources), project_ids=list(project_ids or []),
                full=full, requested_by=actor,
            )
    except IntegrityError:
        active = ArealistingSyncJob.objects.filter(status__in=ACTIVE_STATUSES).first()
        if not active:
            raise ArealistingSyncInProgressError('Повторите запуск обновления AREALISTING.')
        return active, False
    return job, True


def start_sync_worker(job_id):
    log_path = settings.BASE_DIR / 'logs' / 'arealisting_sync_worker.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, 'a', encoding='utf-8') as log_file:
        subprocess.Popen(
            [sys.executable, str(settings.BASE_DIR / 'manage.py'),
             'process_arealisting_sync_jobs', '--job-id', str(job_id)],
            cwd=settings.BASE_DIR,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            close_fds=True,
            start_new_session=True,
        )


def process_sync_job(job_id):
    now = timezone.now()
    claimed = ArealistingSyncJob.objects.filter(
        pk=job_id, status=ArealistingSyncJob.Status.PENDING,
    ).update(status=ArealistingSyncJob.Status.RUNNING, started_at=now)
    if not claimed:
        return False
    job = ArealistingSyncJob.objects.get(pk=job_id)
    client = None
    try:
        client = ArealistingClient()
        summary = ArealistingSyncService(client=client).sync(
            resources=job.resources, project_ids=job.project_ids, full=job.full,
        )
        job.summary = summary
        job.status = ArealistingSyncJob.Status.SUCCESS
    except Exception as exc:
        logger.exception('AREALISTING sync job %s failed', job_id)
        job.status = ArealistingSyncJob.Status.FAILED
        job.error = str(exc)[:1000] or 'Не удалось обновить данные AREALISTING.'
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                logger.exception('Could not close AREALISTING client for sync job %s', job_id)
        job.finished_at = timezone.now()
        job.save(update_fields=('status', 'summary', 'error', 'finished_at'))
    return True
