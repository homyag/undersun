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
