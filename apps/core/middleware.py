import logging
import re
import secrets

from django.conf import settings
from django.http import HttpResponse, HttpResponsePermanentRedirect, JsonResponse
from django.shortcuts import render
from django.conf.urls.i18n import is_language_prefix_patterns_used
from django.utils.deprecation import MiddlewareMixin
from urllib.parse import urlsplit, urlencode, parse_qsl, urlunsplit

from apps.core.bot_detection import BotDetectionService, bot_detection_service
from apps.core.models import ManualIPBan, RequestLog


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
    """Append CSP directives (frame-ancestors, connect-src, default-src) when configured."""

    def process_response(self, request, response):
        csp_directives = {}

        frame_ancestors = getattr(settings, 'FRAME_ANCESTORS', None)
        if frame_ancestors:
            csp_directives['frame-ancestors'] = frame_ancestors

        connect_sources = getattr(settings, 'CONNECT_SRC', None)
        if connect_sources:
            csp_directives['connect-src'] = connect_sources

        default_sources = getattr(settings, 'DEFAULT_SRC', None)
        if default_sources:
            csp_directives['default-src'] = default_sources

        extra_directives = getattr(settings, 'CSP_EXTRA_DIRECTIVES', {})
        if isinstance(extra_directives, dict):
            csp_directives.update(extra_directives)

        if not csp_directives:
            return response

        existing_csp = response.get('Content-Security-Policy', '')
        directive_map = {}

        if existing_csp:
            for part in existing_csp.split(';'):
                part = part.strip()
                if not part:
                    continue
                bits = part.split(' ', 1)
                directive = bits[0]
                value = bits[1] if len(bits) > 1 else ''
                directive_map[directive] = value

        for directive_name, directive_value in csp_directives.items():
            if directive_name in directive_map:
                continue
            directive_map[directive_name] = directive_value

        if directive_map:
            response['Content-Security-Policy'] = '; '.join(
                f"{name} {value}".strip()
                for name, value in directive_map.items()
                if value
            )

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


class LegacyRealEstateRedirectMiddleware(MiddlewareMixin):
    """301-редиректы со старых URL /{lang}/real-estate/... на актуальный каталог."""

    legacy_pattern = re.compile(r'^/(ru|en|th)/real-estate(?:/.*)?$')

    def process_request(self, request):
        match = self.legacy_pattern.match(request.path)
        if not match:
            return None

        language = match.group(1)
        target = f'/{language}/property/'

        query_string = request.META.get('QUERY_STRING')
        if query_string:
            target = f'{target}?{query_string}'

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


class BotDetectionMiddleware(MiddlewareMixin):
    """Score incoming requests and block/monitor bots."""

    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.service: BotDetectionService = bot_detection_service
        self.logger = logging.getLogger('bad_requests')
        self.challenge_query_param = settings.BOT_PROTECTION.get('CHALLENGE_QUERY_PARAM')
        self.challenge_cookie_max_age = int(
            settings.BOT_PROTECTION.get('CHALLENGE_COOKIE_MAX_AGE_DAYS', 7) * 86400
        )

    def process_request(self, request):
        if not self.service.enabled:
            return None

        cleaned = self._remove_challenge_param(request)
        if cleaned:
            return cleaned

        client_ip, proxy_ip = self._extract_ips(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')

        if not client_ip:
            return None

        if self._is_manually_banned(client_ip):
            return HttpResponse('Forbidden', status=403)

        if self.service.is_ip_whitelisted(client_ip) or self.service.is_user_agent_whitelisted(user_agent):
            return None

        result = self.service.evaluate(request, client_ip, proxy_ip)
        if result.action == RequestLog.Action.ALLOW:
            self._schedule_challenge_cookie(request)
            if result.score <= 0:
                return None

        if result.action == RequestLog.Action.CHALLENGE and not request.COOKIES.get(self.service.challenge_cookie):
            if self._is_basic_first_visit(result.matched_rules):
                result.action = RequestLog.Action.MONITOR
            else:
                return self._challenge_response(request)

        matched_rules = [
            {
                'key': match.key,
                'weight': match.weight,
                'detail': match.detail,
            }
            for match in result.matched_rules
        ]

        log_entry = RequestLog.objects.create(
            client_ip=client_ip,
            proxy_ip=proxy_ip,
            method=request.method,
            path=request.path[:2048],
            referer=(request.META.get('HTTP_REFERER') or '')[:2048],
            user_agent=user_agent[:512],
            headers=result.headers,
            bot_score=result.score,
            matched_rules=matched_rules,
            action=result.action,
            source=RequestLog.Source.MIDDLEWARE,
            asn=result.asn or '',
            asn_organization=result.asn_organization or '',
        )
        request._bot_request_log = log_entry

        if result.action == RequestLog.Action.MONITOR:
            self._schedule_challenge_cookie(request)

        if result.action in {RequestLog.Action.MONITOR, RequestLog.Action.BLOCK, RequestLog.Action.CHALLENGE}:
            self.logger.warning(
                'bot-detected score=%s action=%s ip=%s path=%s ua="%s" rules=%s',
                result.score,
                result.action,
                client_ip,
                request.path,
                user_agent,
                ','.join(match['key'] for match in matched_rules) or '-',
            )

        if result.action == RequestLog.Action.BLOCK:
            self.logger.error(
                'bot-fastban ip=%s score=%s path=%s rules=%s',
                client_ip,
                result.score,
                request.path,
                ','.join(match['key'] for match in matched_rules) or '-',
            )
            response = HttpResponse('Forbidden', status=403)
            log_entry.status_code = response.status_code
            log_entry.save(update_fields=['status_code'])
            return response

        if result.notify_fail2ban:
            self.logger.warning(
                'bot-fail2ban-trigger score=%s ip=%s path=%s',
                result.score,
                client_ip,
                request.path,
            )

        return None

    def process_response(self, request, response):
        response = self._apply_challenge_cookie(request, response)
        self._finalize_log(request, getattr(response, 'status_code', None))
        return response

    def process_exception(self, request, exception):
        self._finalize_log(request, 500)
        return None

    def _finalize_log(self, request, status_code):
        log_entry = getattr(request, '_bot_request_log', None)
        if not log_entry or status_code is None or log_entry.status_code:
            return
        log_entry.status_code = status_code
        log_entry.save(update_fields=['status_code'])

    @staticmethod
    def _extract_ips(request):
        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
        client_ip = forwarded_for.split(',')[0].strip() if forwarded_for else request.META.get('REMOTE_ADDR', '')
        proxy_ip = request.META.get('REMOTE_ADDR', '')
        return client_ip, proxy_ip

    @staticmethod
    def _is_manually_banned(client_ip: str) -> bool:
        if not client_ip:
            return False
        try:
            ban = ManualIPBan.objects.filter(ip_address=client_ip, active=True).first()
            if not ban:
                return False
            if not ban.is_active():
                ban.active = False
                ban.save(update_fields=['active'])
                return False
            return True
        except Exception:
            logger.exception('Failed to check ManualIPBan for %s', client_ip)
            return False

    def _challenge_response(self, request):
        from django.shortcuts import render
        target_url = request.build_absolute_uri()
        response = render(request, 'challenge_challenge.html', {
            'target_url': target_url,
        })
        response.status_code = 302
        response['Refresh'] = '0;url=%s' % target_url
        return response

    @staticmethod
    def _is_basic_first_visit(matched_rules):
        basic_rules = {'js_challenge_missing', 'no_referer', 'single_html_hit'}
        return all(getattr(match, 'key', None) in basic_rules for match in matched_rules)

    def _remove_challenge_param(self, request):
        if request.method != 'GET':
            return None
        token_param = self.challenge_query_param
        if not token_param or token_param not in request.GET:
            return None
        parsed = urlsplit(request.get_full_path())
        params = parse_qsl(parsed.query, keep_blank_values=True)
        filtered = [(k, v) for k, v in params if k != token_param]
        if len(filtered) == len(params):
            return None
        new_query = urlencode(filtered, doseq=True)
        new_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment))
        if not new_url:
            new_path = parsed.path or '/'
            if new_query:
                new_path = f"{new_path}?{new_query}"
            if parsed.fragment:
                new_path = f"{new_path}#{parsed.fragment}"
            new_url = new_path
        return HttpResponsePermanentRedirect(new_url)

    def _schedule_challenge_cookie(self, request):
        if not self._should_issue_cookie(request):
            return
        if getattr(request, '_bot_challenge_cookie_value', None):
            return
        request._bot_challenge_cookie_value = self._generate_challenge_token()

    def _should_issue_cookie(self, request):
        if not request:
            return False
        if request.COOKIES.get(self.service.challenge_cookie):
            return False
        if request.method not in {'GET', 'HEAD'}:
            return False
        return True

    @staticmethod
    def _generate_challenge_token():
        return secrets.token_urlsafe(32)

    def _apply_challenge_cookie(self, request, response):
        token = getattr(request, '_bot_challenge_cookie_value', None)
        if not token or not response:
            return response
        secure_flag = False
        if request is not None:
            try:
                secure_flag = request.is_secure()
            except Exception:
                secure_flag = False
        response.set_cookie(
            self.service.challenge_cookie,
            token,
            max_age=self.challenge_cookie_max_age,
            secure=secure_flag,
            path='/',
            httponly=False,
            samesite='Lax',
        )
        return response
