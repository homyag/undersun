import requests
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apps.arealisting.models import ArealistingListingGroup
from apps.arealisting.services.media import sync_group_media


class Command(BaseCommand):
    help = 'Import AREALISTING photos and image floor plans into linked Property cards.'

    def add_arguments(self, parser):
        parser.add_argument('--group-id', action='append', type=int, default=[])
        parser.add_argument('--property-id', action='append', type=int, default=[])
        parser.add_argument(
            '--all-drafts',
            action='store_true',
            help='Process all cards originally created as AREALISTING drafts.',
        )

    def handle(self, *args, **options):
        if not options['group_id'] and not options['property_id'] and not options['all_drafts']:
            raise CommandError(
                'Specify --group-id, --property-id or --all-drafts.'
            )
        filters = Q(pk__in=options['group_id']) | Q(property_id__in=options['property_id'])
        if options['all_drafts']:
            filters |= Q(
                catalog_origin=ArealistingListingGroup.CatalogOrigin.AREALISTING_DRAFT
            )
        groups = list(
            ArealistingListingGroup.objects.filter(filters, property__isnull=False)
            .order_by('pk')
            .distinct()
        )
        if not groups:
            raise CommandError('No linked publication groups matched the selection.')

        totals = {
            'downloaded': 0,
            'created': 0,
            'updated': 0,
            'deleted': 0,
            'skipped': 0,
            'errors': 0,
        }
        with requests.Session() as session:
            for group in groups:
                report = sync_group_media(group.pk, session=session, enable=True)
                for key in totals:
                    totals[key] += report[key]
                self.stdout.write(f'Group {group.pk}: {report}')
        self.stdout.write(self.style.SUCCESS(f'AREALISTING media: {totals}'))
        if totals['errors']:
            raise CommandError(
                f'{totals["errors"]} media file(s) failed; see ArealistingAsset.last_error.'
            )
