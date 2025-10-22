from .base import *

DEBUG = True

ALLOWED_HOSTS = ['51.79.173.21','localhost','127.0.0.1']

# Database для разработки (PostgreSQL)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('DB_NAME', default='undersunestate_db'),
        'USER': env('DB_USER', default=''),
        'PASSWORD': env('DB_PASSWORD', default=''),
        'HOST': env('DB_HOST', default='localhost'),
        'PORT': env('DB_PORT', default='5432'),
    }
}

# Для использования SQLite в разработке раскомментируйте:
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'complete_real_estate.db',
# }

# Email backend для тестирования
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

TAILWIND_USE_CDN = True