import time
from functools import wraps
from urllib.parse import urlencode

from django.core.cache import cache
from django.http import JsonResponse
from django.utils.translation import gettext as _


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


def rate_limit(key_prefix, limit=5, timeout=60):
    """Простой декоратор для ограничения числа запросов с одного IP."""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if request.user.is_authenticated and request.user.is_staff:
                return view_func(request, *args, **kwargs)

            forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
            client_ip = forwarded_for or request.META.get('REMOTE_ADDR', '') or 'unknown'
            cache_key = f'rate-limit:{key_prefix}:{client_ip}'

            count = cache.get(cache_key, 0) + 1
            cache.set(cache_key, count, timeout)

            if count > limit:
                return JsonResponse(
                    {
                        'success': False,
                        'error': 'rate_limited',
                        'message': 'Слишком много запросов. Попробуйте позже.',
                        'retry_after': timeout,
                    },
                    status=429,
                )

            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def validate_form_security(request, min_delay_seconds=2):
    """Проверяем honeypot и минимальное время до отправки формы."""

    honeypot_value = (request.POST.get('website') or '').strip()
    if honeypot_value:
        return JsonResponse(
            {
                'success': False,
                'error': 'suspected_bot',
                'message': _('Обнаружена подозрительная активность. Попробуйте другой способ связи.'),
            },
            status=400,
        )

    rendered_at = request.POST.get('form_rendered_at')
    if rendered_at:
        try:
            rendered_ts = int(rendered_at)
        except (TypeError, ValueError):
            rendered_ts = None

        if rendered_ts:
            now_ts = int(time.time())
            if now_ts - rendered_ts < min_delay_seconds:
                return JsonResponse(
                    {
                        'success': False,
                        'error': 'too_fast',
                        'message': _('Пожалуйста, подождите пару секунд и попробуйте снова.'),
                        'retry_after': min_delay_seconds,
                    },
                    status=429,
                )

    return None
