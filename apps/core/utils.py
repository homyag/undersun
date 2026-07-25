import logging
import re
from ipaddress import ip_address, ip_network
import time
from functools import wraps
from urllib.parse import urlencode

from django.core.cache import cache
from django.conf import settings
from django.http import JsonResponse
from django.utils.html import strip_tags
from django.utils.translation import gettext as _


logger = logging.getLogger(__name__)


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


def _strip_terminal_ellipsis(value):
    return re.sub(r'(?:\s*(?:\.{3,}|\u2026))+$', '', value).strip()


def truncate_meta(value, limit=155, ellipsis=''):
    """Очистить HTML, нормализовать пробелы и обрезать SEO-текст до лимита."""
    if not value:
        return ''

    text = strip_tags(str(value))
    text = re.sub(r'\s+', ' ', text).strip()
    text = _strip_terminal_ellipsis(text)
    if not text or len(text) <= limit:
        return text

    suffix = ellipsis or ''
    content_limit = max(limit - len(suffix), 0) if suffix else limit
    truncated = text[:content_limit]
    last_space = truncated.rfind(' ')
    if last_space > 0:
        truncated = truncated[:last_space]

    truncated = truncated.rstrip(' .,;:-')
    truncated = _strip_terminal_ellipsis(truncated)
    if not truncated:
        truncated = _strip_terminal_ellipsis(text[:content_limit].rstrip())

    return f"{truncated}{suffix}" if suffix else truncated


def get_client_ip(request):
    """Return a client IP without trusting a spoofed forwarding header."""
    remote_addr = (request.META.get('REMOTE_ADDR') or '').strip()
    try:
        remote_ip = ip_address(remote_addr)
    except ValueError:
        return remote_addr or 'unknown'

    trusted_networks = []
    for value in getattr(settings, 'TRUSTED_PROXY_CIDRS', []):
        try:
            trusted_networks.append(ip_network(value))
        except ValueError:
            logger.warning('Ignoring invalid TRUSTED_PROXY_CIDRS value: %s', value)

    if not any(remote_ip in network for network in trusted_networks):
        return remote_addr

    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    candidates = [item.strip() for item in forwarded.split(',') if item.strip()]
    for candidate in reversed(candidates):
        try:
            candidate_ip = ip_address(candidate)
        except ValueError:
            continue
        if not any(candidate_ip in network for network in trusted_networks):
            return candidate
    return remote_addr


def rate_limit(key_prefix, limit=5, timeout=60):
    """Простой декоратор для ограничения числа запросов с одного IP."""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if request.user.is_authenticated and request.user.is_staff:
                return view_func(request, *args, **kwargs)

            client_ip = get_client_ip(request)
            cache_key = f'rate-limit:{key_prefix}:{client_ip}'

            if cache.add(cache_key, 1, timeout):
                count = 1
            else:
                try:
                    count = cache.incr(cache_key)
                except ValueError:
                    # A concurrent expiry is harmless; start a fresh window.
                    cache.set(cache_key, 1, timeout)
                    count = 1

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
