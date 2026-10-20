from django.core.management.base import BaseCommand

from apps.arealisting.models import ArealistingMediaJob
from apps.arealisting.services.media_jobs import process_media_job, recover_stale_media_jobs


class Command(BaseCommand):
    help = 'Обработать очередь импорта фотографий AREALISTING вне HTTP-запроса.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=10)
        parser.add_argument('--job-id', type=int)

    def handle(self, *args, **options):
        recover_stale_media_jobs()
        queryset = ArealistingMediaJob.objects.filter(status=ArealistingMediaJob.Status.PENDING)
        if options['job_id']:
            queryset = queryset.filter(pk=options['job_id'])
        ids = list(queryset.order_by('created_at', 'pk').values_list('pk', flat=True)[:max(1, options['limit'])])
        for job_id in ids:
            if process_media_job(job_id):
                self.stdout.write(f'Processed AREALISTING media job #{job_id}')
        if not ids:
            self.stdout.write('No pending AREALISTING media jobs.')
