from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.core.models import SEOContentBlock
from apps.locations.models import District, Location
from apps.properties.models import PropertyType
from apps.properties.seo_landings import (
    WHITELIST_DISTRICTS,
    WHITELIST_LOCATIONS,
    WHITELIST_PROPERTY_TYPES,
    build_landing_block_payload,
    build_landing_heading,
    build_primary_slug,
    get_deal_label,
    get_property_type_label,
    resolve_landing_signature,
)


class Command(BaseCommand):
    help = 'Generate whitelist SEO landing blocks for valuable property catalogue combinations.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Update existing SEOContentBlock records instead of skipping them.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview the generated blocks without saving to the database.',
        )

    def handle(self, *args, **options):
        update_existing = options['update_existing']
        dry_run = options['dry_run']

        created = 0
        updated = 0
        skipped = 0

        property_types = list(PropertyType.objects.filter(name__in=WHITELIST_PROPERTY_TYPES).order_by('name'))
        districts = list(District.objects.filter(slug__in=WHITELIST_DISTRICTS).order_by('slug'))
        locations = list(
            Location.objects.select_related('district')
            .filter(slug__in=WHITELIST_LOCATIONS, district__slug__in=WHITELIST_DISTRICTS)
            .order_by('slug')
        )

        combos = []

        combos.append({'deal_type': '', 'property_type': '', 'district': None, 'location': None})

        for deal_type in ('sale', 'rent'):
            combos.append({'deal_type': deal_type, 'property_type': '', 'district': None, 'location': None})

        for property_type in property_types:
            combos.append({'deal_type': '', 'property_type': property_type.name, 'district': None, 'location': None})
            for deal_type in ('sale', 'rent'):
                combos.append({'deal_type': deal_type, 'property_type': property_type.name, 'district': None, 'location': None})

        for district in districts:
            combos.append({'deal_type': '', 'property_type': '', 'district': district, 'location': None})
            for deal_type in ('sale', 'rent'):
                combos.append({'deal_type': deal_type, 'property_type': '', 'district': district, 'location': None})

        for location in locations:
            combos.append({'deal_type': '', 'property_type': '', 'district': location.district, 'location': location})
            for deal_type in ('sale', 'rent'):
                combos.append({'deal_type': deal_type, 'property_type': '', 'district': location.district, 'location': location})

        for property_type in property_types:
            for district in districts:
                combos.append({'deal_type': '', 'property_type': property_type.name, 'district': district, 'location': None})
                for deal_type in ('sale', 'rent'):
                    combos.append({'deal_type': deal_type, 'property_type': property_type.name, 'district': district, 'location': None})

            for location in locations:
                combos.append({'deal_type': '', 'property_type': property_type.name, 'district': location.district, 'location': location})
                for deal_type in ('sale', 'rent'):
                    combos.append({'deal_type': deal_type, 'property_type': property_type.name, 'district': location.district, 'location': location})

        seen_slugs = set()

        for combo in combos:
            district = combo['district']
            location = combo['location']
            signature = resolve_landing_signature(
                deal_type=combo['deal_type'],
                property_type=combo['property_type'],
                district=district.slug if district else '',
                location=location.slug if location else '',
            )
            if not signature:
                continue

            slug = build_primary_slug(signature)
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)

            payload = {
                'slug': slug,
                'title': '',
                'content_ru': '',
                'content_en': '',
                'content_th': '',
                'is_active': True,
            }

            for language_code in ('ru', 'en', 'th'):
                heading = build_landing_heading(
                    language_code=language_code,
                    property_type_label=get_property_type_label(combo['property_type'], language_code) if combo['property_type'] else '',
                    deal_label=get_deal_label(combo['deal_type'], language_code) if combo['deal_type'] else '',
                    district_label=self._get_translated_name(district, language_code) if district else '',
                    location_label=self._get_translated_name(location, language_code) if location else '',
                )
                property_type_label = get_property_type_label(combo['property_type'], language_code) if combo['property_type'] else ''
                district_label = self._get_translated_name(district, language_code) if district else ''
                location_label = self._get_translated_name(location, language_code) if location else ''
                block_payload = build_landing_block_payload(
                    language_code=language_code,
                    heading=heading,
                    signature=signature,
                    property_type_label=property_type_label,
                    district_label=district_label,
                    location_label=location_label,
                )
                if language_code == 'ru':
                    payload['title'] = block_payload['title']
                payload[f'content_{language_code}'] = block_payload['content']

            existing = SEOContentBlock.objects.filter(slug=slug).first()
            if existing and not update_existing:
                skipped += 1
                continue

            if dry_run:
                action = 'UPDATE' if existing else 'CREATE'
                self.stdout.write(f'{action} {slug}')
                if existing:
                    updated += 1
                else:
                    created += 1
                continue

            if existing:
                existing.title = payload['title']
                existing.content_ru = payload['content_ru']
                existing.content_en = payload['content_en']
                existing.content_th = payload['content_th']
                existing.is_active = True
                existing.save(update_fields=['title', 'content_ru', 'content_en', 'content_th', 'is_active', 'updated_at'])
                updated += 1
            else:
                SEOContentBlock.objects.create(**payload)
                created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Whitelist landings processed. Created: {created}, updated: {updated}, skipped: {skipped}.'
            )
        )

    @staticmethod
    def _get_translated_name(instance, language_code: str) -> str:
        if instance is None:
            return ''
        field_name = 'name' if language_code == 'ru' else f'name_{language_code}'
        value = getattr(instance, field_name, None) or getattr(instance, 'name', '')
        return ' '.join(str(value).split())
