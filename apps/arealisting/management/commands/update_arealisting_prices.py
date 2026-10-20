"""Scheduled refresh of inventory and prices for linked projects only."""
from django.core.management.base import BaseCommand, CommandError

from apps.arealisting.client import ArealistingClient
from apps.arealisting.exceptions import ArealistingError, ArealistingSyncInProgressError
from apps.arealisting.models import ArealistingProject
from apps.arealisting.services.sync import ArealistingSyncService


class Command(BaseCommand):
    help = 'Refresh AREALISTING inventory and sale prices for linked Undersun cards.'

    def handle(self, *args, **options):
        project_ids = list(ArealistingProject.objects.filter(
            is_deleted=False, listing_groups__property__isnull=False,
        ).order_by('external_id').values_list('external_id', flat=True).distinct())
        if not project_ids:
            self.stdout.write('No linked projects; nothing to update.')
            return
        failures = []
        try:
            with ArealistingClient() as client:
                service = ArealistingSyncService(client=client)
                for project_id in project_ids:
                    try:
                        # Full inventory detects sold/missing units as well as price
                        # changes. Only explicitly linked units determine card prices.
                        summary = service.sync(
                            resources=('units',), project_ids=[project_id],
                            full=True, skip_assets=True,
                        )
                    except ArealistingSyncInProgressError as exc:
                        raise CommandError(str(exc)) from exc
                    except (ArealistingError, ValueError) as exc:
                        failures.append(project_id)
                        self.stderr.write(f'{project_id}: {exc}')
                        continue
                    reports = summary.get('price_updates', [])
                    counts = {status: sum(row['status'] == status for row in reports)
                              for status in ('updated', 'unchanged', 'skipped')}
                    self.stdout.write(f'{project_id}: {counts}')
        except ArealistingError as exc:
            raise CommandError(str(exc)) from exc
        if failures:
            raise CommandError(f'Failed to refresh {len(failures)} project(s); see sync history.')
        self.stdout.write(self.style.SUCCESS('Linked AREALISTING prices refreshed.'))
