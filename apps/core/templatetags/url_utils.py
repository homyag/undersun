from django import template

register = template.Library()


@register.filter(name='absolute_url')
def absolute_url(path, request):
    """Return an absolute URL using the current request when needed."""
    if not path:
        return ''

    if isinstance(path, str) and path.startswith(('http://', 'https://')):
        return path

    if request is None:
        return path

    try:
        return request.build_absolute_uri(path)
    except Exception:
        return path


SCHEMA_TYPE_MAP = {
    'condo': 'https://schema.org/Apartment',
    'villa': 'https://schema.org/SingleFamilyResidence',
    'townhouse': 'https://schema.org/House',
    'land': 'https://schema.org/Landform',
    'land_plot': 'https://schema.org/Landform',
    'business': 'https://schema.org/Place',
    'investment': 'https://schema.org/Place',
}
DEFAULT_SCHEMA_TYPE = 'https://schema.org/Place'


@register.filter(name='schema_additional_type')
def schema_additional_type(value):
    """Return a schema.org type that best matches property type slug."""
    slug = None

    if hasattr(value, 'name'):
        slug = getattr(value, 'name')
    elif isinstance(value, str):
        slug = value

    if not slug:
        return DEFAULT_SCHEMA_TYPE

    slug = slug.strip().lower()
    if not slug:
        return DEFAULT_SCHEMA_TYPE

    return SCHEMA_TYPE_MAP.get(slug, DEFAULT_SCHEMA_TYPE)
