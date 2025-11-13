from django.conf import settings
from django.http import HttpResponsePermanentRedirect
from django.utils import translation
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
