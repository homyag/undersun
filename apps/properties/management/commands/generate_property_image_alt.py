from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from io import BytesIO

import requests
from PIL import Image as PILImage
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.properties.models import PROPERTY_IMAGE_FRAME_TYPES, PropertyImage


VALID_FRAME_TYPES = {choice[0] for choice in PROPERTY_IMAGE_FRAME_TYPES}
FRAME_TYPE_ALIASES = {
    'facade': 'facade',
    'front': 'facade',
    'exterior': 'exterior',
    'outside': 'exterior',
    'external': 'exterior',
    'living_room': 'living_room',
    'living room': 'living_room',
    'livingroom': 'living_room',
    'lounge': 'living_room',
    'salon': 'living_room',
    'bedroom': 'bedroom',
    'master bedroom': 'bedroom',
    'sleeping room': 'bedroom',
    'bathroom': 'bathroom',
    'bath room': 'bathroom',
    'kitchen': 'kitchen',
    'pool': 'pool',
    'terrace': 'terrace',
    'balcony': 'terrace',
    'patio': 'terrace',
    'deck': 'terrace',
    'view': 'view',
    'sea view': 'view',
    'ocean view': 'view',
    'garden': 'garden',
    'yard': 'garden',
    'floorplan': 'floorplan',
    'floor plan': 'floorplan',
    'layout': 'floorplan',
    'plan': 'floorplan',
    'masterplan': 'floorplan',
    'neighborhood': 'neighborhood',
    'location': 'neighborhood',
    'area': 'neighborhood',
    'interior': 'interior',
    'inside': 'interior',
    'other': 'other',
}


@dataclass
class VisionResult:
    frame_type: str
    confidence: Decimal | None


class Command(BaseCommand):
    help = 'Generate frame types and localized alt text for property images.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--mode',
            choices=('auto', 'heuristic', 'vision'),
            default='auto',
            help='Heuristic only, heuristic with vision fallback, or vision first.',
        )
        parser.add_argument(
            '--vision-endpoint',
            default=os.environ.get('IMAGE_FRAME_VISION_ENDPOINT', ''),
            help='Optional HTTP endpoint that returns JSON with frame_type/confidence.',
        )
        parser.add_argument(
            '--min-confidence',
            type=float,
            default=0.75,
            help='Use vision only when heuristic confidence is below this threshold.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Process only the first N images.',
        )
        parser.add_argument(
            '--property-id',
            type=int,
            default=0,
            help='Process images for a single property id.',
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite existing localized alt text even if it is already filled.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would change without saving anything.',
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=30,
            help='Timeout in seconds for the optional vision endpoint.',
        )

    def handle(self, *args, **options):
        mode = options['mode']
        vision_endpoint = (options['vision_endpoint'] or '').strip()
        min_confidence = float(options['min_confidence'])
        limit = options['limit'] or 0
        property_id = options['property_id'] or 0
        overwrite = options['overwrite']
        dry_run = options['dry_run']
        timeout = options['timeout']

        if mode == 'vision' and not vision_endpoint:
            raise CommandError('VISION endpoint is required when --mode vision is used.')

        queryset = (
            PropertyImage.objects.select_related(
                'property',
                'property__property_type',
                'property__district',
                'property__location',
            )
            .order_by('property_id', 'order', 'id')
        )
        if property_id:
            queryset = queryset.filter(property_id=property_id)
        if limit:
            queryset = queryset[:limit]

        processed = 0
        updated = 0
        heuristic_count = 0
        vision_count = 0
        skipped = 0

        for image in queryset.iterator():
            processed += 1

            if not self._image_exists(image):
                skipped += 1
                self.stdout.write(self.style.WARNING(f'SKIP image_id={image.pk}: source file is missing.'))
                continue

            heuristic_frame_type, heuristic_confidence = image.infer_frame_type()
            chosen_frame_type = heuristic_frame_type
            chosen_confidence = self._as_decimal(heuristic_confidence)
            source = 'heuristic'

            if mode in ('auto', 'vision') and vision_endpoint:
                should_call_vision = (
                    mode == 'vision'
                    or heuristic_frame_type == 'other'
                    or (heuristic_confidence is not None and heuristic_confidence < Decimal(str(min_confidence)))
                )
                if should_call_vision:
                    vision_result = self._classify_with_vision(image, vision_endpoint, timeout)
                    if vision_result and self._should_use_vision(
                        vision_result=vision_result,
                        heuristic_frame_type=heuristic_frame_type,
                        heuristic_confidence=chosen_confidence,
                        min_confidence=min_confidence,
                    ):
                        chosen_frame_type = vision_result.frame_type
                        chosen_confidence = vision_result.confidence
                        source = 'vision'

            frame_type_changed = image.frame_type != chosen_frame_type
            alt_changed = self._populate_localized_alt_texts(
                image=image,
                frame_type=chosen_frame_type,
                overwrite=overwrite,
            )

            should_update_meta = frame_type_changed or alt_changed
            if should_update_meta:
                image.frame_type = chosen_frame_type
                image.alt_generated_by = source
                image.alt_confidence = chosen_confidence
                image.alt_generated_at = timezone.now()

            if dry_run:
                if should_update_meta:
                    self.stdout.write(
                        f'UPDATE image_id={image.pk} frame={chosen_frame_type} source={source} '
                        f'confidence={chosen_confidence} alt_changed={alt_changed}'
                    )
                continue

            if should_update_meta:
                image.save()
                updated += 1

            if source == 'vision':
                vision_count += 1
            else:
                heuristic_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                'Property image alt generation completed. '
                f'Processed: {processed}, updated: {updated}, '
                f'heuristic: {heuristic_count}, vision: {vision_count}, skipped: {skipped}.'
            )
        )

    def _populate_localized_alt_texts(self, image: PropertyImage, frame_type: str, overwrite: bool) -> bool:
        changed = False
        for language_code in ('ru', 'en', 'th'):
            field_name = 'alt_text' if language_code == 'ru' else f'alt_text_{language_code}'
            current_value = image._normalize_alt_source(getattr(image, field_name, ''))
            previous_generated_value = image._normalize_alt_source(
                image.get_auto_alt_text(language_code, frame_type=image.frame_type)
            )
            is_previous_generated_alt = (
                bool(image.alt_generated_by)
                and current_value
                and current_value == previous_generated_value
            )
            if (
                current_value
                and not overwrite
                and not image._looks_generic_alt(current_value)
                and not is_previous_generated_alt
            ):
                continue

            new_value = image.get_auto_alt_text(language_code, frame_type=frame_type)
            if new_value and new_value != current_value:
                setattr(image, field_name, new_value)
                changed = True
        return changed

    def _classify_with_vision(self, image: PropertyImage, endpoint: str, timeout: int) -> VisionResult | None:
        try:
            payload = self._build_vision_payload(image)
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f'Vision payload failed for image_id={image.pk}: {exc}'))
            return None

        try:
            response = requests.post(endpoint, json=payload, timeout=timeout)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f'Vision request failed for image_id={image.pk}: {exc}'))
            return None

        frame_type = self._normalize_frame_type(data.get('frame_type'))
        if frame_type not in VALID_FRAME_TYPES:
            return None

        confidence = self._parse_confidence(data.get('confidence'))
        return VisionResult(frame_type=frame_type, confidence=confidence)

    def _build_vision_payload(self, image: PropertyImage) -> dict:
        raw_bytes, content_type = self._prepare_image_bytes(image)
        encoded_image = base64.b64encode(raw_bytes).decode('ascii')

        property_obj = image.property
        property_type = property_obj.property_type.name if property_obj and property_obj.property_type else ''
        district = property_obj.district.name if property_obj and property_obj.district else ''
        location = property_obj.location.name if property_obj and property_obj.location else ''

        return {
            'filename': os.path.basename(image.image.name or ''),
            'content_type': content_type,
            'image_base64': encoded_image,
            'allowed_frame_types': [choice[0] for choice in PROPERTY_IMAGE_FRAME_TYPES],
            'property_context': {
                'title': property_obj.title if property_obj else '',
                'property_type': property_type,
                'district': district,
                'location': location,
                'image_type': image.image_type,
            },
        }

    def _prepare_image_bytes(self, image: PropertyImage) -> tuple[bytes, str]:
        with image.image.open('rb') as source:
            raw_bytes = source.read()

        try:
            with PILImage.open(BytesIO(raw_bytes)) as pil_image:
                pil_image.load()
                if pil_image.mode not in ('RGB', 'L'):
                    pil_image = pil_image.convert('RGB')
                pil_image.thumbnail((1280, 1280))

                output = BytesIO()
                pil_image.save(output, format='JPEG', quality=85, optimize=True)
                return output.getvalue(), 'image/jpeg'
        except Exception:
            pass

        content_type = 'image/jpeg'
        lower_name = (image.image.name or '').lower()
        if lower_name.endswith('.png'):
            content_type = 'image/png'
        elif lower_name.endswith('.webp'):
            content_type = 'image/webp'
        elif lower_name.endswith('.gif'):
            content_type = 'image/gif'
        return raw_bytes, content_type

    def _normalize_frame_type(self, value) -> str:
        if not isinstance(value, str):
            return 'other'
        normalized = ' '.join(value.replace('-', ' ').replace('_', ' ').split()).lower()
        if normalized in VALID_FRAME_TYPES:
            return normalized
        return FRAME_TYPE_ALIASES.get(normalized, 'other')

    @staticmethod
    def _parse_confidence(value) -> Decimal | None:
        if value in (None, ''):
            return None
        try:
            confidence = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None
        if confidence < 0:
            return Decimal('0')
        if confidence > 1:
            return Decimal('1')
        return confidence

    @staticmethod
    def _as_decimal(value) -> Decimal | None:
        if value in (None, ''):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None

    def _should_use_vision(
        self,
        *,
        vision_result: VisionResult,
        heuristic_frame_type: str,
        heuristic_confidence: Decimal | None,
        min_confidence: float,
    ) -> bool:
        if vision_result.frame_type == 'other':
            return False

        if heuristic_frame_type == 'other':
            return True

        if vision_result.confidence is None:
            return True

        if heuristic_confidence is None:
            return vision_result.confidence >= Decimal(str(min_confidence))

        return vision_result.confidence >= heuristic_confidence or vision_result.confidence >= Decimal(str(min_confidence))

    @staticmethod
    def _image_exists(image: PropertyImage) -> bool:
        try:
            storage = image.image.storage
            name = image.image.name
            return bool(storage and name and storage.exists(name))
        except Exception:
            return False
