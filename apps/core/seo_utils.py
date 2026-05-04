"""Utility helpers for canonical URLs and SEO metadata generation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, List, Mapping, Sequence, Tuple
from urllib.parse import urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.http import HttpRequest
from django.utils.translation import gettext, ngettext

from apps.core.utils import truncate_meta
from apps.currency.services import CurrencyService
from apps.properties.models import Property

PROPERTY_ALLOWED_PARAMS: Tuple[str, ...] = (
    'deal_type',
    'property_type',
    'district',
    'location',
    'min_price',
    'max_price',
    'bedrooms',
    'build_status',
    'page',
)

BUILD_STATUS_VALUES = {choice[0] for choice in Property.BUILD_STATUS_CHOICES}

SEARCH_ALLOWED_PARAMS: Tuple[str, ...] = (
    'q',
    'page',
)

BLOG_ALLOWED_PARAMS: Tuple[str, ...] = ('page',)

CANONICAL_PARAM_MAP: Mapping[str, Sequence[str]] = {
    'properties:property_list': PROPERTY_ALLOWED_PARAMS,
    'properties:property_sale': PROPERTY_ALLOWED_PARAMS,
    'properties:property_rent': PROPERTY_ALLOWED_PARAMS,
    'properties:property_by_type': PROPERTY_ALLOWED_PARAMS,
    'core:search': SEARCH_ALLOWED_PARAMS,
    'blog:list': BLOG_ALLOWED_PARAMS,
    'blog:category': BLOG_ALLOWED_PARAMS,
    'blog:tag': BLOG_ALLOWED_PARAMS,
    'location_list': BLOG_ALLOWED_PARAMS,
    'district_detail': BLOG_ALLOWED_PARAMS,
    'location_detail': BLOG_ALLOWED_PARAMS,
}

PROPERTY_META_STRINGS: Mapping[str, Mapping[str, str]] = {
    'ru': {
        'heading_fallback': 'Каталог недвижимости на Пхукете',
        'budget_range': 'от %(min)s до %(max)s',
        'budget_from': 'от %(price)s',
        'budget_to': 'до %(price)s',
        'budget_approx': '~%(price)s',
        'budget_label': 'Бюджет: %(price)s',
        'bedrooms_label': 'Спальни: %(bedrooms)s',
        'bedroom_single': '%(count)s спальня',
        'bedroom_plural': '%(count)s спальни',
        'bedroom_plus': '%(count)s+ спальни',
        'stage_label': 'Стадия: %(status)s',
        'listings_single': '%(count)s актуальное предложение доступно сейчас.',
        'listings_plural': '%(count)s актуальных предложений доступны сейчас.',
        'cta': 'Актуальные предложения от агентства Undersun Estate. Свяжитесь с нами для консультации и подбора объектов.',
        'geo_prefix': '%(type)s в %(area)s',
        'location_label': 'Локация: %(location)s',
        'district_label': 'Район: %(district)s',
    },
    'en': {
        'heading_fallback': 'Phuket property catalogue',
        'budget_range': 'from %(min)s to %(max)s',
        'budget_from': 'from %(price)s',
        'budget_to': 'up to %(price)s',
        'budget_approx': '~%(price)s',
        'budget_label': 'Budget: %(price)s',
        'bedrooms_label': 'Bedrooms: %(bedrooms)s',
        'bedroom_single': '%(count)s bedroom',
        'bedroom_plural': '%(count)s bedrooms',
        'bedroom_plus': '%(count)s+ bedrooms',
        'stage_label': 'Stage: %(status)s',
        'listings_single': '%(count)s listing available now.',
        'listings_plural': '%(count)s listings available now.',
        'cta': 'Fresh listings from Undersun Estate. Contact us for expert guidance.',
        'geo_prefix': '%(type)s in %(area)s',
        'location_label': 'Location: %(location)s',
        'district_label': 'District: %(district)s',
    },
    'th': {
        'heading_fallback': 'แค็ตตาล็อกอสังหาฯ ในภูเก็ต',
        'budget_range': 'ตั้งแต่ %(min)s ถึง %(max)s',
        'budget_from': 'ตั้งแต่ %(price)s',
        'budget_to': 'ไม่เกิน %(price)s',
        'budget_approx': '~%(price)s',
        'budget_label': 'งบประมาณ: %(price)s',
        'bedrooms_label': 'ห้องนอน: %(bedrooms)s',
        'bedroom_single': '%(count)s ห้องนอน',
        'bedroom_plural': '%(count)s ห้องนอน',
        'bedroom_plus': '%(count)s+ ห้องนอน',
        'stage_label': 'สถานะ: %(status)s',
        'listings_single': 'ข้อเสนอ %(count)s รายการพร้อมแล้วตอนนี้.',
        'listings_plural': 'ข้อเสนอ %(count)s รายการพร้อมแล้วตอนนี้.',
        'cta': 'รายการใหม่จาก Undersun Estate ติดต่อเราเพื่อขอคำแนะนำ.',
        'geo_prefix': '%(type)s ใน %(area)s',
        'location_label': 'ทำเล: %(location)s',
        'district_label': 'เขต: %(district)s',
    },
}


def build_canonical_url(request: HttpRequest) -> str:
    """Return canonical URL with only the whitelisted query parameters."""

    absolute_url = request.build_absolute_uri()
    split = urlsplit(absolute_url)
    view_name = getattr(getattr(request, 'resolver_match', None), 'view_name', '')
    allowed_params = CANONICAL_PARAM_MAP.get(view_name, ())
    normalized = _normalize_query_params(request, allowed_params)
    query_string = urlencode(normalized, doseq=True)
    return urlunsplit((split.scheme, split.netloc, split.path, query_string, ''))


def _normalize_query_params(request: HttpRequest, allowed_params: Sequence[str]) -> List[Tuple[str, str]]:
    normalized: List[Tuple[str, str]] = []
    if not allowed_params:
        return normalized

    getlist = request.GET.getlist

    for param in allowed_params:
        if param == 'page':
            page_value = _normalize_page(request.GET.get('page'))
            if page_value:
                normalized.append(('page', page_value))
            continue

        values = [value.strip() for value in getlist(param) if value and value.strip()]
        if not values:
            continue

        if param == 'deal_type':
            value = values[0]
            if value in {'sale', 'rent'}:
                normalized.append((param, value))
        elif param == 'property_type':
            for value in _unique(values):
                normalized.append((param, value))
        elif param == 'bedrooms':
            for value in _unique(values):
                normalized.append((param, value))
        elif param == 'build_status':
            if values[0] in BUILD_STATUS_VALUES:
                normalized.append((param, values[0]))
        else:
            normalized.append((param, values[0]))

    return normalized


def _normalize_page(value: str | None) -> str | None:
    if not value:
        return None
    try:
        page_number = int(value)
    except (TypeError, ValueError):
        return None
    if page_number <= 1:
        return None
    return str(page_number)


def _unique(values: Iterable[str]) -> List[str]:
    seen = set()
    unique_values: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values


@dataclass
class MetaData:
    title: str
    description: str


def build_property_meta(
    *,
    heading: str,
    results_count: int | None,
    property_type_name: str = '',
    district_name: str = '',
    location_name: str = '',
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    currency_code: str = 'USD',
    bedrooms: Sequence[str] | None = None,
    build_status_label: str = '',
    language_code: str = 'ru',
) -> MetaData:
    """Construct SEO meta for property listing, prioritising type, geography and price."""

    lang_key = (language_code or 'ru')[:2]
    phrases = PROPERTY_META_STRINGS.get(lang_key, PROPERTY_META_STRINGS['en'])
    site_name = getattr(settings, 'SITE_NAME', 'Undersun Estate')
    base_heading = heading or phrases['heading_fallback']
    price_text = _format_price_text(min_price, max_price, currency_code, phrases)

    bedrooms_text = _format_bedrooms_text(bedrooms, phrases)

    title_parts = [base_heading]
    if bedrooms_text:
        title_parts.append(bedrooms_text)
    if price_text:
        title_parts.append(price_text)
    title_parts.append(site_name)
    title = ' | '.join(part for part in title_parts if part)

    description_parts: List[str] = []

    if property_type_name and (district_name or location_name):
        area = location_name or district_name
        description_parts.append(
            phrases['geo_prefix'] % {'type': property_type_name, 'area': area}
        )
    else:
        description_parts.append(base_heading)

    if location_name:
        description_parts.append(phrases['location_label'] % {'location': location_name})
    elif district_name:
        description_parts.append(phrases['district_label'] % {'district': district_name})

    if price_text:
        description_parts.append(phrases['budget_label'] % {'price': price_text})

    if bedrooms_text:
        description_parts.append(phrases['bedrooms_label'] % {'bedrooms': bedrooms_text})

    if build_status_label:
        description_parts.append(phrases['stage_label'] % {'status': build_status_label})

    if results_count is not None and results_count > 0:
        key = 'listings_single' if results_count == 1 else 'listings_plural'
        description_parts.append(phrases[key] % {'count': results_count})

    description_parts.append(phrases['cta'])

    description = ' '.join(filter(None, description_parts))
    return MetaData(title=title, description=truncate_meta(description))


def _format_price_text(
    min_price: Decimal | None,
    max_price: Decimal | None,
    currency_code: str,
    phrases: Mapping[str, str],
) -> str:
    if not min_price and not max_price:
        return ''

    formatted_min = CurrencyService.format_price(min_price, currency_code) if min_price else None
    formatted_max = CurrencyService.format_price(max_price, currency_code) if max_price else None

    if formatted_min and formatted_max:
        if min_price == max_price:
            return phrases['budget_approx'] % {'price': formatted_min}
        return phrases['budget_range'] % {
            'min': formatted_min,
            'max': formatted_max,
        }
    if formatted_min:
        return phrases['budget_from'] % {'price': formatted_min}
    if formatted_max:
        return phrases['budget_to'] % {'price': formatted_max}
    return ''


def _format_bedrooms_text(
    values: Sequence[str] | None,
    phrases: Mapping[str, str],
) -> str:
    if not values:
        return ''

    unique_values = _unique(value.strip() for value in values if value)
    labels: List[str] = []
    for value in unique_values:
        if value.endswith('+'):
            count = value.rstrip('+') or value
            labels.append(phrases['bedroom_plus'] % {'count': count})
            continue
        try:
            number = int(value)
        except (TypeError, ValueError):
            labels.append(value)
            continue
        key = 'bedroom_single' if number == 1 else 'bedroom_plural'
        labels.append(phrases[key] % {'count': number})

    return ', '.join(labels)
