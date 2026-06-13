from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apps.core.services import translation_service
from apps.properties.models import Property
from apps.properties.services import _trim_field_value


TRANSLATABLE_FIELDS = (
    'title',
    'description',
    'short_description',
    'address',
    'special_offer',
    'complex_name',
    'urgency_note',
    'architectural_style',
    'material_type',
    'investment_potential',
    'suitable_for',
)

HTML_FIELDS = {'description', 'investment_potential'}


class Command(BaseCommand):
    help = 'Translate missing Property modeltranslation fields in controlled batches.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            default='ru',
            help='Source language code (default: ru)',
        )
        parser.add_argument(
            '--lang',
            default='en',
            help='Target language code (default: en)',
        )
        parser.add_argument(
            '--fields',
            nargs='+',
            default=['title'],
            choices=TRANSLATABLE_FIELDS,
            help='Property fields to translate (default: title)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='Maximum number of matching properties to process (default: 50)',
        )
        parser.add_argument(
            '--ids',
            nargs='+',
            type=int,
            default=None,
            help='Process only selected property IDs',
        )
        parser.add_argument(
            '--include-inactive',
            action='store_true',
            help='Include inactive properties',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Overwrite existing target translations',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be translated without calling the API or saving',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Print each translated field',
        )

    def handle(self, *args, **options):
        source = options['source']
        target = options['lang']
        fields = options['fields']
        limit = max(options['limit'] or 0, 0)
        dry_run = options['dry_run']
        force = options['force']
        verbose = options['verbose']

        self._validate_fields(source, target, fields)

        if not dry_run and not translation_service.is_configured():
            raise CommandError(
                'Translation service is not configured. '
                'Set YANDEX_TRANSLATE_API_KEY and YANDEX_TRANSLATE_FOLDER_ID, '
                'or run with --dry-run.'
            )

        queryset = Property.objects.order_by('id')
        if not options['include_inactive']:
            queryset = queryset.filter(is_active=True)
        if options['ids']:
            queryset = queryset.filter(id__in=options['ids'])

        queryset = queryset.filter(self._build_candidate_query(source, target, fields, force))
        if limit:
            queryset = queryset[:limit]

        properties_seen = 0
        field_candidates = 0
        fields_translated = 0
        fields_failed = 0

        for property_obj in queryset:
            properties_seen += 1
            update_fields = []

            for field_name in fields:
                source_field = f'{field_name}_{source}'
                target_field = f'{field_name}_{target}'
                source_value = getattr(property_obj, source_field, '') or ''
                target_value = getattr(property_obj, target_field, '') or ''

                if not str(source_value).strip():
                    continue
                if target_value and not force:
                    continue

                field_candidates += 1

                if dry_run:
                    if verbose:
                        self.stdout.write(
                            f'Would translate Property #{property_obj.pk}: '
                            f'{source_field} -> {target_field}'
                        )
                    continue

                preserve_html = field_name in HTML_FIELDS and '<' in source_value
                translated = translation_service.translate_text(
                    source_value,
                    target,
                    preserve_html=preserve_html,
                )

                if not translated:
                    fields_failed += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'Failed Property #{property_obj.pk}: {source_field} -> {target_field}'
                        )
                    )
                    continue

                translated = _trim_field_value(
                    property_obj,
                    target_field,
                    translated.strip(),
                )
                setattr(property_obj, target_field, translated)
                update_fields.append(target_field)
                fields_translated += 1

                if verbose:
                    self.stdout.write(
                        f'Translated Property #{property_obj.pk}: '
                        f'{source_field} -> {target_field}'
                    )

            if update_fields:
                property_obj.save(update_fields=update_fields)

        if dry_run:
            self.stdout.write(
                self.style.NOTICE(
                    f'Dry run: {field_candidates} field candidates across '
                    f'{properties_seen} properties.'
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f'Translated {fields_translated} fields across '
                f'{properties_seen} properties; failed: {fields_failed}.'
            )
        )

    def _validate_fields(self, source, target, fields):
        for field_name in fields:
            for language_code in (source, target):
                translated_field = f'{field_name}_{language_code}'
                try:
                    Property._meta.get_field(translated_field)
                except Exception as exc:
                    raise CommandError(f'Unknown field: {translated_field}') from exc

    def _build_candidate_query(self, source, target, fields, force):
        query = Q()
        for field_name in fields:
            source_field = f'{field_name}_{source}'
            target_field = f'{field_name}_{target}'
            field_query = (
                ~Q(**{f'{source_field}__isnull': True})
                & ~Q(**{source_field: ''})
            )
            if not force:
                field_query &= (
                    Q(**{f'{target_field}__isnull': True})
                    | Q(**{target_field: ''})
                )
            query |= field_query
        return query
