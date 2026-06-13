import csv
import re
from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from apps.properties.models import Property, PropertyType


TYPE_PATTERNS = {
    'villa': re.compile(r'\b(villa|villas|вилла|виллы|виллу)\b', re.IGNORECASE),
    'condo': re.compile(
        r'\b(condo|condominium|apartment|apartments|апартамент|апартаменты|'
        r'квартира|квартиры|пентхаус|студия)\b',
        re.IGNORECASE,
    ),
    'townhouse': re.compile(r'\b(townhouse|town house|таунхаус)\b', re.IGNORECASE),
    'land': re.compile(r'\b(land|plot|участок|земля)\b', re.IGNORECASE),
    # There is no dedicated "house" type in the current taxonomy. House hits
    # are reported for manual review, but they are never auto-applied.
    'house_review': re.compile(r'\b(house|home|дом|дома)\b', re.IGNORECASE),
}

AUTO_APPLY_TYPES = {'villa', 'condo', 'townhouse', 'land'}


class Command(BaseCommand):
    help = 'Audit property_type values that conflict with property titles.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv',
            default=None,
            metavar='PATH',
            help='Write the full conflict list to CSV.',
        )
        parser.add_argument(
            '--include-inactive',
            action='store_true',
            help='Include inactive properties.',
        )
        parser.add_argument(
            '--ids',
            nargs='+',
            type=int,
            default=None,
            help='Limit audit/apply to selected property IDs.',
        )
        parser.add_argument(
            '--expected',
            choices=sorted(AUTO_APPLY_TYPES),
            default=None,
            help='Only show/apply conflicts with this expected type.',
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Apply unambiguous conflicts. Requires --expected and --ids.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Limit number of printed examples per conflict group.',
        )

    def handle(self, *args, **options):
        include_inactive = options['include_inactive']
        selected_ids = options['ids']
        expected_filter = options['expected']
        apply_changes = options['apply']
        print_limit = max(options['limit'] or 0, 0)

        if apply_changes and not (expected_filter and selected_ids):
            raise CommandError('--apply requires both --expected and --ids.')

        type_by_slug = {
            property_type.name: property_type
            for property_type in PropertyType.objects.all()
        }
        if apply_changes and expected_filter not in type_by_slug:
            raise CommandError(f'PropertyType "{expected_filter}" does not exist.')

        queryset = Property.objects.select_related('property_type').order_by('id')
        if not include_inactive:
            queryset = queryset.filter(is_active=True)
        if selected_ids:
            queryset = queryset.filter(id__in=selected_ids)

        conflicts = []
        for property_obj in queryset:
            conflict = self._build_conflict_row(property_obj)
            if not conflict:
                continue
            if expected_filter and conflict['expected_type'] != expected_filter:
                continue
            conflicts.append(conflict)

        if options['csv']:
            self._write_csv(options['csv'], conflicts)

        counts = Counter(
            f"{row['expected_type']}_title_vs_{row['current_type'] or 'empty'}"
            for row in conflicts
        )

        self.stdout.write(f'Conflicts found: {len(conflicts)}')
        for key, count in counts.most_common():
            self.stdout.write(f'  {key}: {count}')

        examples_printed = Counter()
        for row in conflicts:
            key = f"{row['expected_type']}_title_vs_{row['current_type'] or 'empty'}"
            if print_limit and examples_printed[key] >= print_limit:
                continue
            examples_printed[key] += 1
            self.stdout.write(
                f"  #{row['id']} {row['current_type'] or 'empty'} -> "
                f"{row['expected_type']}: {row['title'][:140]}"
            )

        if not apply_changes:
            return

        target_type = type_by_slug[expected_filter]
        applied = 0
        skipped = 0
        for row in conflicts:
            if row['is_ambiguous'] or row['expected_type'] == 'house_review':
                skipped += 1
                continue
            updated = Property.objects.filter(id=row['id']).update(property_type=target_type)
            applied += updated

        self.stdout.write(
            self.style.SUCCESS(
                f'Applied property_type={expected_filter} to {applied} properties; '
                f'skipped ambiguous/manual-review rows: {skipped}.'
            )
        )

    def _build_conflict_row(self, property_obj):
        current_type = (
            property_obj.property_type.name.lower()
            if property_obj.property_type_id and property_obj.property_type
            else ''
        )
        title = self._combined_title(property_obj)
        matched_types = [
            expected_type
            for expected_type, pattern in TYPE_PATTERNS.items()
            if pattern.search(title)
        ]
        if not matched_types:
            return None

        expected_type = self._pick_expected_type(matched_types)
        if not expected_type:
            return None
        if expected_type == current_type:
            return None
        if expected_type == 'house_review' and current_type in {'villa', 'townhouse'}:
            return None

        return {
            'id': property_obj.id,
            'slug': property_obj.slug,
            'is_active': property_obj.is_active,
            'current_type': current_type,
            'expected_type': expected_type,
            'matched_types': ','.join(matched_types),
            'is_ambiguous': len(set(matched_types) - {'house_review'}) > 1,
            'title': title,
        }

    @staticmethod
    def _combined_title(property_obj):
        values = [
            property_obj.title_en,
            property_obj.title_ru,
            property_obj.title,
            property_obj.slug,
        ]
        return ' | '.join(str(value).strip() for value in values if value)

    @staticmethod
    def _pick_expected_type(matched_types):
        if 'townhouse' in matched_types:
            return 'townhouse'
        if 'villa' in matched_types:
            return 'villa'
        if 'condo' in matched_types:
            return 'condo'
        if 'land' in matched_types and 'house_review' in matched_types:
            return 'house_review'
        if 'land' in matched_types:
            return 'land'
        if 'house_review' in matched_types:
            return 'house_review'
        return ''

    @staticmethod
    def _write_csv(path, conflicts):
        with open(path, 'w', encoding='utf-8', newline='') as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=[
                    'id',
                    'slug',
                    'is_active',
                    'current_type',
                    'expected_type',
                    'matched_types',
                    'is_ambiguous',
                    'title',
                ],
            )
            writer.writeheader()
            writer.writerows(conflicts)
