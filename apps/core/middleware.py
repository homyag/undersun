import logging
import re

from django.conf import settings
from django.http import HttpResponsePermanentRedirect, JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf.urls.i18n import is_language_prefix_patterns_used


class PermissionsPolicyMiddleware(MiddlewareMixin):
    """
    Middleware to set Permissions Policy headers to allow unload events in admin
    This fixes the permissions policy violation in Django admin RelatedObjectLookups.js
    """
    
    def process_response(self, request, response):
        # Only apply to admin pages
        if request.path.startswith('/admin/'):
            # Allow unload event for admin pages to prevent violations
            # This is needed for Django's RelatedObjectLookups functionality
            response['Permissions-Policy'] = 'unload=*'
        
        return response


class FrameAncestorsMiddleware(MiddlewareMixin):
    """Append a CSP frame-ancestors directive when configured."""

    def process_response(self, request, response):
        directives = getattr(settings, 'FRAME_ANCESTORS', None)
        if not directives:
            return response

        frame_directive = f"frame-ancestors {directives}"
        existing_csp = response.get('Content-Security-Policy')

        if existing_csp:
            if 'frame-ancestors' in existing_csp:
                return response
            response['Content-Security-Policy'] = f"{existing_csp}; {frame_directive}"
        else:
            response['Content-Security-Policy'] = frame_directive

        return response


class LanguageRedirectMiddleware(MiddlewareMixin):
    """Redirect root path to language-aware URL based on Accept-Language."""

    def process_request(self, request):
        if request.method != 'GET' or request.path not in {'', '/'}:
            return None

        if not is_language_prefix_patterns_used(settings.ROOT_URLCONF):
            return None

        accept_language_header = (request.META.get('HTTP_ACCEPT_LANGUAGE') or '').strip()
        supported = {code for code, _ in settings.LANGUAGES}
        fallback_language = 'en' if 'en' in supported else settings.LANGUAGE_CODE

        preferred_language = None
        if accept_language_header:
            first_chunk = accept_language_header.split(',', 1)[0]
            lang_part = first_chunk.split(';', 1)[0].strip()
            if lang_part:
                preferred_language = lang_part.split('-')[0].lower()

        language = preferred_language if preferred_language in supported else None

        if not language:
            language = fallback_language

        target = f'/{language}/'
        if request.get_full_path() == target:
            return None

        return HttpResponsePermanentRedirect(target)


class BadInquiryRequestLoggerMiddleware(MiddlewareMixin):
    """Log подозрительные GET-запросы к AJAX-эндпоинту заявок по объектам."""

    inquiry_pattern = re.compile(r'^/(?:[a-z]{2})?/property/ajax/inquiry/\d+/?$')

    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.logger = logging.getLogger('bad_requests')

    def process_request(self, request):
        if not self.inquiry_pattern.match(request.path):
            return None

        if request.method == 'POST':
            return None

        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        client_ip = forwarded_for or request.META.get('REMOTE_ADDR', 'unknown')
        user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')
        query_string = request.META.get('QUERY_STRING', '') or '-'

        self.logger.warning(
            'bad-inquiry-invalid-method method=%s path=%s ip=%s ua="%s" query=%s',
            request.method,
            request.get_full_path(),
            client_ip,
            user_agent,
            query_string,
        )

        # AJAX-инквайры работают только по POST. Возвращаем 405, но не блокируем Googlebot.
        return JsonResponse(
            {
                'success': False,
                'error': 'method_not_allowed',
            },
            status=405,
        )


class ForbiddenPathLoggerMiddleware(MiddlewareMixin):
    """Фиксируем обращения к типичным бот-пуям (/administrator, /wp-login.php и т.д.)."""

    forbidden_patterns = [
        re.compile(r'^/administrator(?:/|$)'),
        re.compile(r'^/wp-admin(?:/|$)'),
        re.compile(r'^/wp-login\.php$'),
        re.compile(r'^/wp-content(?:/|$)'),
        re.compile(r'^/wp-includes(?:/|$)'),
        re.compile(r'^/phpmyadmin(?:/|$)'),
        re.compile(r'^/pma(?:/|$)'),
        re.compile(r'^/adminer(?:/|$)'),
        re.compile(r'^/manager/html(?:/|$)'),
        re.compile(r'^/vendor/phpunit(?:/|$)'),
        re.compile(r'^/wp-json(?:/|$)'),
        re.compile(r'^/xmlrpc\.php$'),
        re.compile(r'^/\.env'),
        re.compile(r'^/\.git'),
        re.compile(r'^/vendor(?:/|$)'),
        re.compile(r'^/composer\.json$'),
        re.compile(r'^/package-lock\.json$'),
        re.compile(r'^/aws'),
        re.compile(r'^/cgi-bin'),
        re.compile(r'^/storage'),
        re.compile(r'^/backup'),
        re.compile(r'^/\.well-known/security\.txt'),
    ]

    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.logger = logging.getLogger('bad_requests')

    def process_request(self, request):
        path = request.path.lower()
        if not any(pattern.match(path) for pattern in self.forbidden_patterns):
            return None

        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        client_ip = forwarded_for or request.META.get('REMOTE_ADDR', 'unknown')
        user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')
        query_string = request.META.get('QUERY_STRING', '') or '-'

        self.logger.warning(
            'forbidden-path method=%s path=%s ip=%s ua="%s" query=%s',
            request.method,
            request.get_full_path(),
            client_ip,
            user_agent,
            query_string,
        )

        return None
