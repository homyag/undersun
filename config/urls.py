from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from django.views.generic import RedirectView
from django.views.generic import TemplateView
from apps.core.views import SitemapView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('rosetta/', include('rosetta.urls')),  # Интерфейс для переводов
    path('i18n/', include('django.conf.urls.i18n')),  # URLs для смены языка
    path('currency/', include('apps.currency.urls')),  # URLs для валют
    path('tinymce/', include('tinymce.urls')),  # URLs для TinyMCE
    path('admin-ajax/', include('apps.properties.admin_urls')),  # Admin AJAX endpoints без i18n
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),  # Robots
    path('sitemap.xml', SitemapView.as_view(), name='sitemap'),
    path('', RedirectView.as_view(url='/ru/', permanent=True)),  # Редирект на русскую версию
]

# Многоязычные URL
urlpatterns += i18n_patterns(
    path('', include('apps.core.urls')),
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
