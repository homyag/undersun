"""Helpers for generating the Yandex YML feed."""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, Iterable, List, Optional, Tuple

from django.conf import settings
from django.db.models import Count, Prefetch, Q, QuerySet
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.translation import override
from xml.etree.ElementTree import Element, SubElement, tostring

from apps.properties.models import Property, PropertyImage


class YandexYmlFeedGenerator:
    """Builds a YML feed that matches the Yandex real-estate specification."""

    CATEGORY_ID = 1
    MAX_OFFERS = 30000
    MAX_PICTURES_PER_OFFER = 10
    MIN_SET_SIZE = 3

    PRICE_SALE_FILTER = (
        Q(price_sale_rub__gt=0)
        | Q(price_sale_usd__gt=0)
        | Q(price_sale_thb__gt=0)
    )
    PRICE_RENT_FILTER = (
        Q(price_rent_monthly_rub__gt=0)
        | Q(price_rent_monthly__gt=0)
        | Q(price_rent_monthly_thb__gt=0)
    )
    PRICE_ANY_FILTER = PRICE_SALE_FILTER | PRICE_RENT_FILTER

    def __init__(self, base_url: str, language_code: str = 'ru') -> None:
        self.base_url = (base_url or '').rstrip('/')
        self.language_code = language_code or 'ru'
        self.generated_at = timezone.now()
        self.shop_name = getattr(settings, 'SITE_NAME', 'Undersun Estate')
        self.company_name = getattr(settings, 'SITE_COMPANY_NAME', self.shop_name)
        configured_site_url = getattr(settings, 'SITE_URL', '')
        self.site_url = (configured_site_url or '').rstrip('/')
        default_image = static('images/no-image.svg')
        self.default_picture = self._build_absolute_url(default_image)

    # Public API -----------------------------------------------------------------
    def generate(self) -> bytes:
        """Return rendered XML payload."""

        base_queryset = Property.objects.filter(
            is_active=True,
            status='available'
        ).filter(self.PRICE_ANY_FILTER)

        sets = self._build_sets(base_queryset)
        properties = self._prepare_properties_queryset(base_queryset)

        root = Element('yml_catalog', date=self.generated_at.strftime('%Y-%m-%d %H:%M'))
        shop = SubElement(root, 'shop')
        SubElement(shop, 'name').text = self.shop_name
        SubElement(shop, 'company').text = self.company_name
        SubElement(shop, 'url').text = self.site_url or self.base_url

        currencies_element = SubElement(shop, 'currencies')
        categories_element = SubElement(shop, 'categories')
        SubElement(categories_element, 'category', id=str(self.CATEGORY_ID)).text = 'Недвижимость'
        sets_element = SubElement(shop, 'sets')
        offers_element = SubElement(shop, 'offers')

        currencies_used = set()

        for property_obj in properties:
            offer_element, currency_code, set_ids, first_picture = self._build_offer(property_obj, sets)
            if offer_element is None:
                continue

            offers_element.append(offer_element)

            if currency_code:
                currencies_used.add(currency_code)

            if first_picture:
                self._maybe_assign_set_picture(set_ids, first_picture, sets)

        # Populate currencies block only with the currencies actually used.
        for currency_code in sorted(currencies_used):
            SubElement(currencies_element, 'currency', id=currency_code, rate='1')

        # Render sets after offer loop so that we already know preview pictures.
        for set_data in sets.values():
            set_element = SubElement(sets_element, 'set', id=set_data['id'])
            SubElement(set_element, 'name').text = set_data['name']
            SubElement(set_element, 'url').text = set_data['url']
            if set_data.get('description'):
                SubElement(set_element, 'description').text = set_data['description']
            if set_data.get('picture'):
                SubElement(set_element, 'picture').text = set_data['picture']

        return tostring(root, encoding='utf-8', xml_declaration=True)

    # Query helpers --------------------------------------------------------------
    def _prepare_properties_queryset(self, base_queryset: QuerySet) -> Iterable[Property]:
        images_prefetch = Prefetch(
            'images',
            queryset=PropertyImage.objects.order_by('order', 'id')
        )

        queryset = (
            base_queryset
            .select_related('district', 'location', 'developer', 'property_type')
            .prefetch_related(images_prefetch)
            .order_by('-featured_priority', '-is_featured', '-created_at')
        )

        return queryset[:self.MAX_OFFERS]

    def _build_sets(self, queryset: QuerySet) -> Dict[str, Dict[str, str]]:
        """Prepare metadata for property type, deal type and district sets."""

        sets: Dict[str, Dict[str, str]] = {}

        with override(self.language_code):
            sale_url = self._build_absolute_url(reverse('properties:property_sale'))
            rent_url = self._build_absolute_url(reverse('properties:property_rent'))

            sale_count = queryset.filter(self.PRICE_SALE_FILTER).count()
            if sale_count >= self.MIN_SET_SIZE:
                sets['deal-sale'] = {
                    'id': 'deal-sale',
                    'name': 'Недвижимость на продажу',
                    'url': sale_url,
                    'description': f'Каталог объектов на продажу ({sale_count} предложений)',
                    'picture': '',
                }

            rent_count = queryset.filter(self.PRICE_RENT_FILTER).count()
            if rent_count >= self.MIN_SET_SIZE:
                sets['deal-rent'] = {
                    'id': 'deal-rent',
                    'name': 'Недвижимость в аренду',
                    'url': rent_url,
                    'description': f'Недвижимость для аренды ({rent_count} предложений)',
                    'picture': '',
                }

            # Property type sets
            type_counts = (
                queryset.values('property_type__id', 'property_type__name', 'property_type__name_display')
                .annotate(total=Count('id'))
                .order_by('property_type__name_display', 'property_type__name')
            )
            for entry in type_counts:
                if not entry['property_type__name'] or entry['total'] < self.MIN_SET_SIZE:
                    continue

                slug = entry['property_type__name']
                set_id = f'type-{slug}'
                set_name = f"{entry['property_type__name_display'] or 'Недвижимость'} на Пхукете"
                type_url = self._build_absolute_url(
                    reverse('properties:property_by_type', args=[slug])
                )

                sets[set_id] = {
                    'id': set_id,
                    'name': set_name,
                    'url': type_url,
                    'description': f"{set_name} ({entry['total']} предложений)",
                    'picture': '',
                }

            # District sets
            district_counts = (
                queryset.values('district__slug', 'district__name')
                .annotate(total=Count('id'))
                .order_by('district__name', 'district__slug')
            )
            for entry in district_counts:
                if not entry['district__slug'] or entry['total'] < self.MIN_SET_SIZE:
                    continue

                slug = entry['district__slug']
                set_id = f'district-{slug}'
                district_url = self._build_absolute_url(
                    reverse('district_detail', kwargs={'district_slug': slug})
                )
                district_name = entry['district__name'] or 'Пхукет'

                sets[set_id] = {
                    'id': set_id,
                    'name': f'Недвижимость в районе {district_name}',
                    'url': district_url,
                    'description': f"{district_name}: {entry['total']} предложений",
                    'picture': '',
                }

        return sets

    # Offer helpers -------------------------------------------------------------
    def _build_offer(
        self,
        property_obj: Property,
        sets: Dict[str, Dict[str, str]],
    ) -> Tuple[Optional[Element], Optional[str], List[str], Optional[str]]:
        price_value, currency_code, active_deal_type = self._extract_price(property_obj)
        if price_value is None or currency_code is None:
            return None, None, [], None

        url = self._resolve_property_url(property_obj)
        if not url:
            return None, None, [], None

        pictures = self._get_picture_urls(property_obj)
        if not pictures:
            pictures = [self.default_picture]

        offer_element = Element('offer', id=str(property_obj.pk), available='true')
        SubElement(offer_element, 'name').text = property_obj.title or 'Объект недвижимости'
        SubElement(offer_element, 'url').text = url
        SubElement(offer_element, 'price').text = self._format_decimal(price_value)
        SubElement(offer_element, 'currencyId').text = currency_code
        SubElement(offer_element, 'categoryId').text = str(self.CATEGORY_ID)

        set_ids = self._collect_set_ids(property_obj, active_deal_type, sets)
        if set_ids:
            SubElement(offer_element, 'set-ids').text = ','.join(set_ids)

        for picture in pictures[: self.MAX_PICTURES_PER_OFFER]:
            SubElement(offer_element, 'picture').text = picture

        vendor_value = (property_obj.developer.name if property_obj.developer else self.company_name)
        SubElement(offer_element, 'vendor').text = vendor_value

        description_text = self._prepare_description(property_obj)
        if description_text:
            SubElement(offer_element, 'description').text = description_text

        # Mandatory params in the specification
        self._append_param(offer_element, 'Конверсия', str(self._calculate_conversion_score(property_obj)))
        self._append_param(offer_element, 'Тип предложения', 'Продажа' if active_deal_type == 'sale' else 'Аренда')

        # Optional params that we can currently populate
        self._append_param(offer_element, 'Посуточно', self._format_bool(False))
        self._append_param(
            offer_element,
            'С земельным участком',
            self._format_bool(bool(property_obj.area_land and property_obj.area_land > 0)),
        )
        if property_obj.area_land:
            self._append_param(offer_element, 'Площадь участка', self._format_decimal(property_obj.area_land))

        self._append_param(offer_element, 'Адрес', self._compose_address(property_obj))

        if property_obj.latitude is not None:
            self._append_param(offer_element, 'Широта', self._format_decimal(property_obj.latitude))
        if property_obj.longitude is not None:
            self._append_param(offer_element, 'Долгота', self._format_decimal(property_obj.longitude))

        if property_obj.year_built:
            self._append_param(offer_element, 'Год постройки', str(property_obj.year_built))

        if property_obj.floor:
            self._append_param(offer_element, 'Этаж', str(property_obj.floor))
        if property_obj.floors_total:
            self._append_param(offer_element, 'Число этажей', str(property_obj.floors_total))

        if property_obj.bedrooms is not None:
            self._append_param(offer_element, 'Число комнат', str(property_obj.bedrooms))

        if property_obj.area_total:
            self._append_param(offer_element, 'Площадь', self._format_decimal(property_obj.area_total))

        if property_obj.created_at:
            self._append_param(offer_element, 'Дата публикации', property_obj.created_at.isoformat())

        self._append_param(offer_element, 'Размещено агентом', self._format_bool(True))
        self._append_param(offer_element, 'Проверено в ЕГРН', self._format_bool(False))

        if active_deal_type == 'rent':
            self._append_param(offer_element, 'Включая коммунальные услуги', self._format_bool(False))

        if property_obj.developer and property_obj.developer.website:
            self._append_param(offer_element, 'Сайт застройщика', property_obj.developer.website)

        return offer_element, currency_code, set_ids, pictures[0]

    def _collect_set_ids(
        self,
        property_obj: Property,
        active_deal_type: str,
        sets: Dict[str, Dict[str, str]],
    ) -> List[str]:
        set_ids: List[str] = []

        type_slug = property_obj.property_type.name if property_obj.property_type else None
        if type_slug:
            candidate = f'type-{type_slug}'
            if candidate in sets:
                set_ids.append(candidate)

        if property_obj.district and property_obj.district.slug:
            candidate = f'district-{property_obj.district.slug}'
            if candidate in sets:
                set_ids.append(candidate)

        if active_deal_type == 'sale' and 'deal-sale' in sets:
            set_ids.append('deal-sale')
        if active_deal_type == 'rent' and 'deal-rent' in sets:
            set_ids.append('deal-rent')

        return set_ids

    def _extract_price(self, property_obj: Property) -> Tuple[Optional[Decimal], Optional[str], Optional[str]]:
        sale_priorities = [
            ('price_sale_rub', 'RUB'),
            ('price_sale_usd', 'USD'),
            ('price_sale_thb', 'THB'),
        ]
        rent_priorities = [
            ('price_rent_monthly_rub', 'RUB'),
            ('price_rent_monthly', 'USD'),
            ('price_rent_monthly_thb', 'THB'),
        ]

        if property_obj.deal_type in ('sale', 'both'):
            price = self._resolve_price_from_fields(property_obj, sale_priorities)
            if price:
                return price[0], price[1], 'sale'

        if property_obj.deal_type in ('rent', 'both'):
            price = self._resolve_price_from_fields(property_obj, rent_priorities)
            if price:
                return price[0], price[1], 'rent'

        # Fallback: try any available price regardless of declared deal type.
        price = self._resolve_price_from_fields(property_obj, sale_priorities + rent_priorities)
        if price:
            inferred_deal = 'sale' if price[2] == 'sale' else 'rent'
            return price[0], price[1], inferred_deal

        return None, None, None

    @staticmethod
    def _resolve_price_from_fields(
        property_obj: Property,
        fields: List[Tuple[str, str]],
    ) -> Optional[Tuple[Decimal, str, str]]:
        for field_name, currency in fields:
            value = getattr(property_obj, field_name)
            if value:
                deal = 'sale' if 'sale' in field_name else 'rent'
                return Decimal(value), currency, deal
        return None

    def _get_picture_urls(self, property_obj: Property) -> List[str]:
        picture_urls: List[str] = []

        seen = set()

        for image in property_obj.images.all():
            url = self._build_absolute_url(image.original_url)
            if not url or url in seen:
                continue
            picture_urls.append(url)
            seen.add(url)

        extra_images = [
            self._safe_file_url(property_obj.intro_image),
            self._safe_file_url(property_obj.floorplan),
        ]
        for raw in extra_images:
            url = self._build_absolute_url(raw)
            if url and url not in seen:
                picture_urls.append(url)
                seen.add(url)

        return picture_urls

    def _prepare_description(self, property_obj: Property) -> str:
        source = property_obj.short_description or property_obj.description
        if not source:
            return ''
        description = strip_tags(source).strip()
        return description[:4000]

    def _compose_address(self, property_obj: Property) -> str:
        if property_obj.address:
            return property_obj.address

        parts = []
        if property_obj.location:
            parts.append(property_obj.location.name)
        if property_obj.district:
            parts.append(property_obj.district.name)

        return ', '.join(parts) or 'Таиланд, Пхукет'

    def _calculate_conversion_score(self, property_obj: Property) -> int:
        base_score = property_obj.views_count or 0
        priority_bonus = property_obj.featured_priority or 0
        return max(1, base_score + priority_bonus)

    def _resolve_property_url(self, property_obj: Property) -> str:
        with override(self.language_code):
            relative_url = property_obj.get_absolute_url()
        return self._build_absolute_url(relative_url)

    def _build_absolute_url(self, url: Optional[str]) -> str:
        if not url:
            return ''
        if url.startswith('http://') or url.startswith('https://'):
            return url
        base = self.base_url or self.site_url
        if not base:
            return url
        if not url.startswith('/'):
            url = f'/{url}'
        return f'{base}{url}'

    def _append_param(self, offer: Element, name: str, value: Optional[str], unit: Optional[str] = None) -> None:
        if value in (None, ''):
            return
        attributes = {'name': name}
        if unit:
            attributes['unit'] = unit
        SubElement(offer, 'param', attrib=attributes).text = str(value)

    def _format_decimal(self, value: Decimal) -> str:
        if isinstance(value, Decimal):
            text = format(value, 'f')
        else:
            text = str(value)
        if '.' in text:
            text = text.rstrip('0').rstrip('.')
            if not text:
                text = '0'
        return text

    @staticmethod
    def _format_bool(value: bool) -> str:
        return 'true' if value else 'false'

    @staticmethod
    def _safe_file_url(file_field) -> str:
        if not file_field:
            return ''
        try:
            return file_field.url
        except Exception:
            return ''

    def _maybe_assign_set_picture(
        self,
        set_ids: Iterable[str],
        picture_url: Optional[str],
        sets: Dict[str, Dict[str, str]],
    ) -> None:
        if not picture_url:
            return
        for set_id in set_ids:
            set_data = sets.get(set_id)
            if set_data and not set_data.get('picture'):
                set_data['picture'] = picture_url
