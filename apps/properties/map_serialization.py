from collections import defaultdict
from decimal import Decimal
from math import floor

from apps.core.business_profile import BUSINESS_PROFILE
from apps.currency.models import ExchangeRate
from apps.currency.services import CurrencyService

from .models import PROPERTY_FALLBACK_LABELS


def _get_localized_value(instance, field_name, language_code, fallback=''):
    if not instance:
        return fallback

    value = getattr(instance, f'{field_name}_{language_code}', None)
    return value or getattr(instance, field_name, fallback)


def _get_price_deal_type(property_obj):
    if property_obj.deal_type == 'rent':
        return 'rent'
    if property_obj.deal_type == 'both' and not property_obj.price_sale_thb:
        return 'rent'
    return 'sale'


class MapPriceFormatter:
    def __init__(self, request, language_code):
        self.language_code = language_code
        self.currency_code = CurrencyService.get_selected_currency_code(request)
        self.currency = CurrencyService.get_currency_by_code(self.currency_code)
        self.currency_symbol = self.currency.symbol if self.currency else self.currency_code
        self.decimal_places = self.currency.decimal_places if self.currency else 0
        self.sale_field, self.rent_field = CurrencyService.get_price_field_names(self.currency_code)
        self.conversion_rate = self._get_conversion_rate()

    def _get_conversion_rate(self):
        if self.currency_code == 'THB' or not self.currency:
            return Decimal('1')

        thb_currency = CurrencyService.get_currency_by_code('THB')
        if not thb_currency:
            return None

        return ExchangeRate.get_latest_rate(thb_currency, self.currency)

    def _get_price(self, property_obj, deal_type):
        field_name = self.rent_field if deal_type == 'rent' else self.sale_field
        stored_price = getattr(property_obj, field_name, None)
        if stored_price:
            return stored_price

        base_price = (
            property_obj.price_rent_monthly_thb
            if deal_type == 'rent'
            else property_obj.price_sale_thb
        )
        if not base_price or not self.conversion_rate:
            return None

        return Decimal(base_price) * self.conversion_rate

    def format(self, property_obj):
        deal_type = _get_price_deal_type(property_obj)
        price = self._get_price(property_obj, deal_type)
        if not price:
            return PROPERTY_FALLBACK_LABELS[self.language_code]['price_on_request']

        if self.decimal_places:
            value = f'{price:,.{self.decimal_places}f}'
        else:
            value = f'{price:,.0f}'

        suffix = PROPERTY_FALLBACK_LABELS[self.language_code]['per_month'] if deal_type == 'rent' else ''
        return f'{self.currency_symbol}{value}{suffix}'


def _get_map_image(property_obj):
    images = getattr(property_obj, 'map_images', ())
    return next((image for image in images if image.is_main), images[0] if images else None)


def serialize_map_properties(properties, request, language_code):
    """Serialize prefetched map properties for the legacy MapLibre JSON contract."""
    language_code = language_code if language_code in PROPERTY_FALLBACK_LABELS else 'ru'
    price_formatter = MapPriceFormatter(request, language_code)

    serialized = []
    for property_obj in properties:
        if property_obj.latitude is None or property_obj.longitude is None:
            continue

        main_image = _get_map_image(property_obj)
        agent_phone = property_obj.agent.phone if property_obj.agent and property_obj.agent.phone else ''

        serialized.append({
            'id': property_obj.id,
            'title': _get_localized_value(property_obj, 'title', language_code, property_obj.title),
            'slug': property_obj.slug,
            'lat': float(property_obj.latitude),
            'lng': float(property_obj.longitude),
            'property_type': property_obj.property_type.name if property_obj.property_type else '',
            'property_type_label': _get_localized_value(
                property_obj.property_type,
                'name_display',
                language_code,
                property_obj.property_type.name_display if property_obj.property_type else '',
            ),
            'deal_type': 'sale',
            'price': price_formatter.format(property_obj),
            'location': _get_localized_value(
                property_obj.location,
                'name',
                language_code,
                _get_localized_value(
                    property_obj.district,
                    'name',
                    language_code,
                    property_obj.district.name if property_obj.district else '',
                ),
            ),
            'url': f'/{language_code}/property/{property_obj.slug}/',
            'image_url': main_image.thumbnail_url if main_image else '',
            'bedrooms': property_obj.bedrooms or 0,
            'bathrooms': property_obj.bathrooms or 0,
            'area': float(property_obj.area_total) if property_obj.area_total else 0,
            'agent_phone': agent_phone or BUSINESS_PROFILE['phone_e164'],
        })

    return serialized


def serialize_map_markers(properties):
    """Return the minimum data MapLibre needs to render property pins."""
    return [
        {
            'id': property_obj.id,
            'lat': float(property_obj.latitude),
            'lng': float(property_obj.longitude),
        }
        for property_obj in properties
        if property_obj.latitude is not None and property_obj.longitude is not None
    ]


def serialize_map_aggregates(properties, zoom):
    """Group property coordinates into a stable screen-sized grid for far zooms."""
    tile_size = 512
    grid_size_px = 80
    grid_size_degrees = (360 * grid_size_px) / (tile_size * (2 ** floor(zoom)))
    buckets = defaultdict(lambda: {'count': 0, 'lat_sum': 0.0, 'lng_sum': 0.0})

    for latitude, longitude in properties.values_list('latitude', 'longitude'):
        lat = float(latitude)
        lng = float(longitude)
        bucket_key = (floor(lat / grid_size_degrees), floor(lng / grid_size_degrees))
        bucket = buckets[bucket_key]
        bucket['count'] += 1
        bucket['lat_sum'] += lat
        bucket['lng_sum'] += lng

    return [
        {
            'id': f'grid:{zoom:.2f}:{lat_bucket}:{lng_bucket}',
            'lat': values['lat_sum'] / values['count'],
            'lng': values['lng_sum'] / values['count'],
            'count': values['count'],
        }
        for (lat_bucket, lng_bucket), values in sorted(buckets.items())
    ]
