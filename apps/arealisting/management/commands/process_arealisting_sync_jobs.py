from django.core.management.base import BaseCommand

from apps.arealisting.models import ArealistingSyncJob
from apps.arealisting.services.sync_jobs import process_sync_job, recover_stale_sync_jobs


class Command(BaseCommand):
    help = 'Обработать ожидающие фоновые обновления AREALISTING.'

    def add_arguments(self, parser):
        parser.add_argument('--job-id', type=int)
        parser.add_argument('--limit', type=int, default=10)

    def handle(self, *args, **options):
        recover_stale_sync_jobs()
        jobs = ArealistingSyncJob.objects.filter(status=ArealistingSyncJob.Status.PENDING)
        if options['job_id']:
            jobs = jobs.filter(pk=options['job_id'])
        ids = list(jobs.order_by('created_at', 'pk').values_list('pk', flat=True)[:max(1, options['limit'])])
        for job_id in ids:
            if process_sync_job(job_id):
                self.stdout.write(f'Processed AREALISTING sync job #{job_id}')
        if not ids:
            self.stdout.write('No pending AREALISTING sync jobs.')
