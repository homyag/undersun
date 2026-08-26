from decimal import Decimal, InvalidOperation

from django.db.models import Case, DecimalField, ExpressionWrapper, F, Value, When

from apps.currency.services import CurrencyService


CATALOG_PRICE_OUTPUT_FIELD = DecimalField(max_digits=24, decimal_places=6)

CATALOG_PRICE_FIELDS = {
    'sale': {
        'THB': 'price_sale_thb',
        'USD': 'price_sale_usd',
        'RUB': 'price_sale_rub',
    },
    'rent': {
        'THB': 'price_rent_monthly_thb',
        'USD': 'price_rent_monthly',
        'RUB': 'price_rent_monthly_rub',
    },
}


def _normalize_currency_code(currency_code):
    normalized_code = (currency_code or 'USD').upper()
    return normalized_code if normalized_code in CATALOG_PRICE_FIELDS['sale'] else 'USD'


def _parse_price_value(value):
    if value in (None, ''):
        return None

    try:
        parsed_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None

    return parsed_value if parsed_value.is_finite() else None


def build_catalog_price_expression(currency_code, deal_type='sale'):
    """Return the same effective price that Property.get_price_in_currency displays."""
    normalized_currency = _normalize_currency_code(currency_code)
    price_fields = CATALOG_PRICE_FIELDS.get(deal_type, CATALOG_PRICE_FIELDS['sale'])
    thb_field = price_fields['THB']

    if normalized_currency == 'THB':
        return Case(
            When(**{f'{thb_field}__gt': 0}, then=F(thb_field)),
            default=Value(None),
            output_field=CATALOG_PRICE_OUTPUT_FIELD,
        )

    selected_currency_field = price_fields[normalized_currency]
    thb_to_selected_rate = CurrencyService.convert_price(
        Decimal('1'),
        'THB',
        normalized_currency,
    )
    converted_thb_price = Value(None, output_field=CATALOG_PRICE_OUTPUT_FIELD)
    if thb_to_selected_rate is not None:
        converted_thb_price = ExpressionWrapper(
            F(thb_field) * Value(Decimal(str(thb_to_selected_rate))),
            output_field=CATALOG_PRICE_OUTPUT_FIELD,
        )

    return Case(
        When(
            **{
                f'{thb_field}__gt': 0,
                f'{selected_currency_field}__gt': 0,
            },
            then=F(selected_currency_field),
        ),
        When(**{f'{thb_field}__gt': 0}, then=converted_thb_price),
        default=Value(None),
        output_field=CATALOG_PRICE_OUTPUT_FIELD,
    )


def apply_catalog_price_filters(
    queryset,
    *,
    min_price=None,
    max_price=None,
    currency_code='USD',
    deal_type='sale',
):
    parsed_min_price = _parse_price_value(min_price)
    parsed_max_price = _parse_price_value(max_price)

    if parsed_min_price is None and parsed_max_price is None:
        return queryset

    queryset = queryset.alias(
        _catalog_effective_price=build_catalog_price_expression(currency_code, deal_type),
    )
    if parsed_min_price is not None:
        queryset = queryset.filter(_catalog_effective_price__gte=parsed_min_price)
    if parsed_max_price is not None:
        queryset = queryset.filter(_catalog_effective_price__lte=parsed_max_price)

    return queryset
