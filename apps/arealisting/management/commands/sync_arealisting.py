import json

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.arealisting.client import ArealistingClient
from apps.arealisting.exceptions import ArealistingError
from apps.arealisting.services.sync import ArealistingSyncService


class Command(BaseCommand):
    help = (
        'Synchronize AREALISTING source records. New Property records are not '
        'published automatically.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--resources',
            nargs='+',
            choices=('projects', 'units', 'payment-plans', 'deletions'),
            default=('projects',),
            help='Resources to synchronize. Defaults to projects only.',
        )
        parser.add_argument(
            '--full',
            action='store_true',
            help='Fetch full selected resources and reconcile missing records.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Validate API responses without writing to the database or storage.',
        )
        parser.add_argument(
            '--since',
            help='ISO 8601 lower boundary for an incremental synchronization.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='API page size from 1 to 500.',
        )
        parser.add_argument(
            '--project-ids',
            help='Comma-separated project external IDs for a targeted synchronization.',
        )
        parser.add_argument(
            '--ids',
            help='Comma-separated IDs; only valid with exactly one resource.',
        )
        parser.add_argument(
            '--skip-assets',
            action='store_true',
            help='Do not synchronize asset URL metadata.',
        )

    @staticmethod
    def _split_ids(value):
        if not value:
            return []
        return [item.strip() for item in value.split(',') if item.strip()]

    @staticmethod
    def _parse_since(value):
        if not value:
            return None
        parsed = parse_datetime(value)
        if parsed is None:
            raise CommandError('--since must be a valid ISO 8601 datetime.')
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed)
        return parsed

    def handle(self, *args, **options):
        resources = [resource.replace('-', '_') for resource in options['resources']]
        project_ids = self._split_ids(options.get('project_ids'))
        ids = self._split_ids(options.get('ids'))
        since = self._parse_since(options.get('since'))

        if not 1 <= options['limit'] <= ArealistingClient.MAX_PAGE_SIZE:
            raise CommandError('--limit must be between 1 and 500.')
        if ids and len(resources) != 1:
            raise CommandError('--ids requires exactly one selected resource.')

        self.stdout.write(
            'AREALISTING sync: '
            f"resources={','.join(resources)} "
            f"mode={'full' if options['full'] else 'incremental'} "
            f"dry_run={options['dry_run']}"
        )

        client = None
        try:
            client = ArealistingClient()
            service = ArealistingSyncService(client=client)
            summary = service.sync(
                resources=resources,
                full=options['full'],
                dry_run=options['dry_run'],
                since=since,
                limit=options['limit'],
                project_ids=project_ids,
                ids=ids,
                skip_assets=options['skip_assets'],
            )
        except (ArealistingError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        finally:
            if client is not None:
                client.close()

        rendered = json.dumps(summary, ensure_ascii=False, indent=2, default=str)
        self.stdout.write(rendered)
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('Dry run completed; no data was written.'))
        else:
            self.stdout.write(self.style.SUCCESS('AREALISTING synchronization completed.'))
