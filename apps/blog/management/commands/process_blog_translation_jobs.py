import time

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.blog.models import BlogTranslationJob
from apps.blog.services import process_blog_translation_job


class Command(BaseCommand):
    help = 'Обрабатывает очередь переводов статей блога.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=5,
            help='Максимум заданий за один проход.',
        )
        parser.add_argument(
            '--job-id',
            type=int,
            help='Обработать конкретное задание.',
        )
        parser.add_argument(
            '--poll',
            action='store_true',
            help='Работать постоянно и опрашивать очередь.',
        )
        parser.add_argument(
            '--sleep',
            type=float,
            default=10.0,
            help='Пауза между проходами в режиме --poll.',
        )

    def handle(self, *args, **options):
        limit = max(options['limit'], 1)
        job_id = options.get('job_id')

        while True:
            processed = self._process_batch(limit=limit, job_id=job_id)

            if not options['poll'] or job_id:
                break

            if processed == 0:
                time.sleep(max(options['sleep'], 1.0))

    def _process_batch(self, *, limit, job_id=None):
        processed = 0

        for job in self._claim_jobs(limit=limit, job_id=job_id):
            self.stdout.write(f'Processing blog translation job #{job.pk}: {job.post}')
            process_blog_translation_job(job)
            job.refresh_from_db()
            processed += 1

            if job.status == BlogTranslationJob.STATUS_SUCCEEDED:
                self.stdout.write(self.style.SUCCESS(f'Job #{job.pk} completed.'))
            elif job.status == BlogTranslationJob.STATUS_FAILED:
                self.stdout.write(self.style.ERROR(f'Job #{job.pk} failed: {job.error_message}'))
            else:
                self.stdout.write(f'Job #{job.pk} finished with status {job.status}.')

        if processed == 0:
            self.stdout.write('No pending blog translation jobs found.')

        return processed

    def _claim_jobs(self, *, limit, job_id=None):
        queryset = BlogTranslationJob.objects.filter(status=BlogTranslationJob.STATUS_PENDING)

        if job_id:
            queryset = queryset.filter(pk=job_id)

        job_ids = list(queryset.order_by('created_at').values_list('pk', flat=True)[:limit])

        for claimed_job_id in job_ids:
            claimed_job = None

            with transaction.atomic():
                updated = BlogTranslationJob.objects.filter(
                    pk=claimed_job_id,
                    status=BlogTranslationJob.STATUS_PENDING,
                ).update(
                    status=BlogTranslationJob.STATUS_RUNNING,
                    started_at=timezone.now(),
                    updated_at=timezone.now(),
                )

                if not updated:
                    continue

                claimed_job = BlogTranslationJob.objects.select_related('post').get(pk=claimed_job_id)

            if claimed_job:
                yield claimed_job
