from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from django.views.generic import RedirectView
from django.views.generic import TemplateView
from django.views.i18n import JavaScriptCatalog
from django.views.decorators.cache import cache_page
from apps.core.views import SitemapView, legacy_real_estate_redirect
from apps.properties.views import YandexYmlFeedView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('templates/yootheme/', RedirectView.as_view(url='/', permanent=True)),
    path('rosetta/', include('rosetta.urls')),  # Интерфейс для переводов
    path('i18n/', include('django.conf.urls.i18n')),  # URLs для смены языка
    path('currency/', include('apps.currency.urls')),  # URLs для валют
    path('tinymce/', include('tinymce.urls')),  # URLs для TinyMCE
    path('admin-ajax/', include('apps.properties.admin_urls')),  # Admin AJAX endpoints без i18n
    path('jsi18n/', cache_page(60 * 60 * 24)(JavaScriptCatalog.as_view()), name='javascript-catalog'),
    path('real-estate/', legacy_real_estate_redirect),
    path('real-estate/<path:legacy_path>/', legacy_real_estate_redirect),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),  # Robots
    path('sitemap.xml', SitemapView.as_view(), name='sitemap'),
    path('feeds/yandex-real-estate.xml', YandexYmlFeedView.as_view(), name='yandex_yml_feed'),
    path('7cf6s6qd8qa7ba52pdgkstaekjtk28a2.txt', TemplateView.as_view(template_name='indexnow_key.txt', content_type='text/plain')),
    # Root handled by LanguageRedirectMiddleware
]

LEGACY_ROOT_REDIRECTS = (
    (r'^faqb2bquestions/?$', '/en/contact/'),
    (r'^faqb2b/?$', '/en/contact/'),
    (r'^faqb2bpromo/?$', '/en/contact/'),
    (r'^faqconf/?$', '/en/contact/'),
    (r'^faqconf2/?$', '/en/contact/'),
    (r'^privacyen/?$', '/en/privacy/'),
    (r'^gr/?$', '/en/'),
)

for pattern, target in LEGACY_ROOT_REDIRECTS:
    urlpatterns.append(
        re_path(pattern, RedirectView.as_view(url=target, permanent=True))
    )

# Многоязычные URL
urlpatterns += i18n_patterns(
    path('', include('apps.core.urls')),
    path('real-estate/', legacy_real_estate_redirect),
    path('real-estate/<path:legacy_path>/', legacy_real_estate_redirect),
    path('property/', include('apps.properties.urls')),
    path('locations/', include('apps.locations.urls')),
    path('users/', include('apps.users.urls')),
    path('blog/', include('apps.blog.urls')),
    prefix_default_language=True
)

# Статические и медиа файлы
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

handler404 = 'apps.core.views.custom_404'
