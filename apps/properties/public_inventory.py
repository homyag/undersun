from django.db.models import Q


PUBLIC_RENTAL_SLUG_PATTERN = (
    r'(^|-)(rent(?:al|ed|ing|s)?|lease(?:hold|d|s|ing)?|leashold|arend[^-]*)($|-)'
)


PUBLIC_RENTAL_SLUG_Q = Q(slug__iregex=PUBLIC_RENTAL_SLUG_PATTERN)


def exclude_public_rental_slugs(queryset):
    """Hide legacy records whose public URL still advertises a rental use case."""
    return queryset.exclude(PUBLIC_RENTAL_SLUG_Q)


def public_sale_queryset(queryset):
    """Apply the shared public sale-only inventory policy to a Property queryset."""
    return exclude_public_rental_slugs(queryset.filter(deal_type='sale'))
