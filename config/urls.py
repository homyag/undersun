from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('rosetta/', include('rosetta.urls')),  # Интерфейс для переводов
    path('i18n/', include('django.conf.urls.i18n')),  # URLs для смены языка
    path('currency/', include('apps.currency.urls')),  # URLs для валют
    path('tinymce/', include('tinymce.urls')),  # URLs для TinyMCE
    path('data-import/', include('data_import.urls')),  # URLs для импорта данных
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