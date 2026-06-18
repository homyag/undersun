from .base import *

DEBUG = False

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['undersunestate.com', 'www.undersunestate.com'])

CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=['http://localhost:8080'])

# Database для продакшена (PostgreSQL)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('DB_NAME'),
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST', default='localhost'),
        'PORT': env('DB_PORT', default='5432'),
    }
}

# Security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_HSTS_SECONDS = 31536000
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = 'ALLOWALL'

# Allow embedding for Yandex Metrica/Webvisor only via CSP frame-ancestors
FRAME_ANCESTORS = "'self' https://metrika.yandex.ru https://*.metrika.yandex.ru https://webvisor.com https://*.webvisor.com"

# CSP directives (consumed by FrameAncestorsMiddleware)
DEFAULT_SRC = "'self'"
CONNECT_SRC = "'self' https://mc.yandex.ru https://mc.yandex.com wss://mc.yandex.ru wss://mc.yandex.com https://www.googletagmanager.com https://www.google-analytics.com https://region1.google-analytics.com https://www.google.com https://www.gstatic.com https://stats.g.doubleclick.net https://analytics.ahrefs.com https://cdn.jsdelivr.net https://cdn.tailwindcss.com https://unpkg.com https://cdnjs.cloudflare.com https://code.jquery.com https://maps.googleapis.com https://maps.gstatic.com https://tile.openstreetmap.org https://*.tile.openstreetmap.org https://cdn.ampproject.org https://www.googleadservices.com"
CSP_EXTRA_DIRECTIVES = {
    'script-src': "'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://code.jquery.com https://unpkg.com https://www.googletagmanager.com https://www.google-analytics.com https://region1.google-analytics.com https://www.google.com https://www.gstatic.com https://analytics.ahrefs.com https://mc.yandex.ru https://mc.yandex.com https://cdn.ampproject.org",
    'worker-src': "'self' blob:",
    'style-src': "'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://unpkg.com https://fonts.googleapis.com",
    'font-src': "'self' data: https://cdnjs.cloudflare.com https://fonts.gstatic.com",
    'img-src': "'self' data: blob: https://mc.yandex.ru https://mc.yandex.com https://www.googletagmanager.com https://www.google-analytics.com https://analytics.ahrefs.com https://www.google.com https://www.gstatic.com https://lh3.googleusercontent.com https://*.googleusercontent.com https://flagcdn.com https://*.tile.openstreetmap.org https://tile.openstreetmap.org https://maps.gstatic.com https://maps.googleapis.com https://cdn.ampproject.org https://ytimg.com https://i.ytimg.com https://www.youtube.com https://www.youtube-nocookie.com https://www.facebook.com https://www.instagram.com https://www.linkedin.com https://t.me https://wa.me https://unpkg.com",
    'frame-src': "'self' https://mc.yandex.ru https://mc.yandex.com https://www.google.com https://www.youtube.com https://www.youtube-nocookie.com https://maps.google.com",
}

SECURE_SSL_REDIRECT = True # раскомментировать после получения доступа по 443
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") # раскомментировать после получения доступа по 443
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin" # раскомментировать после получения доступа по 443


# Static files для продакшена
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Email настройки
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env('EMAIL_PORT', default=587)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@undersunestate.com')


# Tailwind
TAILWIND_USE_CDN = False
