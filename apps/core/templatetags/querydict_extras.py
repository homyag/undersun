from django import template

register = template.Library()


@register.filter(name='get_list')
def get_list(value, key):
    """Return list of values from a QueryDict-like object."""
    if value is None:
        return []

    getlist = getattr(value, 'getlist', None)
    if callable(getlist):
        return getlist(key)

    item = value.get(key)
    if item is None:
        return []

    if isinstance(item, (list, tuple)):
        return list(item)

    return [item]
