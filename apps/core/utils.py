from urllib.parse import urlencode


def build_query_string(querydict, allowed_keys):
    """Return a sanitized query string containing only allowed keys."""
    if not querydict or not allowed_keys:
        return ''

    get_values = getattr(querydict, 'getlist', None)
    if not callable(get_values):
        def get_values(key):
            value = querydict.get(key)
            if value is None:
                return []
            if isinstance(value, (list, tuple)):
                return list(value)
            return [value]

    params = []

    for key in allowed_keys:
        values = get_values(key)
        for value in values:
            if value in (None, ''):
                continue
            params.append((key, value))

    if not params:
        return ''

    return urlencode(params, doseq=True)
