import os
import sys
from pathlib import Path
import environ
from django.urls import reverse_lazy

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Добавляем apps в Python path
sys.path.insert(0, os.path.join(BASE_DIR, 'apps'))

# Environment variables
env = environ.Env(
    DEBUG=(bool, False)
)

# Читаем .env файл если он существует
env_file = BASE_DIR / '.env'
if env_file.exists():
    env.read_env(env_file)

# Basic site metadata (used by structured feeds, OpenGraph, etc.)
SITE_NAME = env('SITE_NAME', default='Undersun Estate')
SITE_COMPANY_NAME = env('SITE_COMPANY_NAME', default='Undersun Estate Co., Ltd.')
SITE_URL = env('SITE_URL', default='https://undersunestate.com')

# Google reCAPTCHA v3
RECAPTCHA_SITE_KEY = env('RECAPTCHA_SITE_KEY', default='')
RECAPTCHA_SECRET_KEY = env('RECAPTCHA_SECRET_KEY', default='')
RECAPTCHA_VERIFY_URL = 'https://www.google.com/recaptcha/api/siteverify'
RECAPTCHA_MIN_SCORE = env.float('RECAPTCHA_MIN_SCORE', default=0.5)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY', default='django-insecure-change-me-in-production')

# Application definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
]

THIRD_PARTY_APPS = [
    'rosetta',
    'imagekit',
    'django_filters',
    'crispy_forms',
    'crispy_tailwind',
    'tailwind',
    'tinymce',
    # 'leaflet',  # Закомментировано до установки GDAL
]

LOCAL_APPS = [
    'apps.core.apps.CoreConfig',
    'apps.properties.apps.PropertiesConfig',
    'apps.locations.apps.LocationsConfig',
    'apps.users.apps.UsersConfig',
    'apps.currency.apps.CurrencyConfig',
    'apps.blog.apps.BlogConfig',
    'modeltranslation',  # Перемещаем после наших приложений
]

if (BASE_DIR / 'theme').exists():
    LOCAL_APPS.append('theme')

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'apps.core.middleware.LanguageRedirectMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'apps.core.middleware.BadInquiryRequestLoggerMiddleware',
    'apps.core.middleware.ForbiddenPathLoggerMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.middleware.PermissionsPolicyMiddleware',  # Fix for admin permissions policy
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.currency.context_processors.currency_context',
                'django.template.context_processors.i18n',
                'apps.core.context_processors.site_context',
                'apps.core.context_processors.seo_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'ru'
TIME_ZONE = 'Asia/Bangkok'
USE_I18N = True
USE_L10N = True
USE_TZ = True

LANGUAGES = [
    ('ru', 'Русский'),
    ('en', 'English'),
    ('th', 'ไทย'),
]

LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

# Language cookie settings
LANGUAGE_COOKIE_NAME = 'language'
LANGUAGE_COOKIE_AGE = 60 * 60 * 24 * 365  # 1 year
LANGUAGE_COOKIE_SAMESITE = 'Lax'
LANGUAGE_COOKIE_SECURE = env.bool('LANGUAGE_COOKIE_SECURE', default=False)

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"
CRISPY_TEMPLATE_PACK = "tailwind"

# Tailwind via django-tailwind
TAILWIND_APP_NAME = 'theme'

# Leaflet Map
LEAFLET_CONFIG = {
    'DEFAULT_CENTER': (7.8804, 98.3923),  # Phuket coordinates
    'DEFAULT_ZOOM': 11,
    'MIN_ZOOM': 8,
    'MAX_ZOOM': 18,
    'TILES': [
        ('OpenStreetMap', 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            'attribution': '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }),
    ],
    'PLUGINS': {
        'marker-cluster': {
            'css': 'https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.css',
            'js': 'https://unpkg.com/leaflet.markercluster@1.4.1/dist/leaflet.markercluster.js',
        }
    }
}

# Pagination
PAGINATE_BY = 12

# Login/Logout URLs
LOGIN_URL = '/users/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# Session settings
SESSION_COOKIE_AGE = 1209600  # 2 weeks

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB

# Cache (для продакшена настроить Redis)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'django.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'bad_requests_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'bad_requests.log',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.users.notifications': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'bad_requests': {
            'handlers': ['bad_requests_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# TinyMCE Configuration
TINYMCE_DEFAULT_CONFIG = {
    'height': 400,
    'width': 'auto',
    'cleanup_on_startup': True,
    'custom_undo_redo_levels': 20,
    'selector': '.tinymce-content',  # Используем класс вместо всех textarea
    'theme': 'silver',
    'plugins': '''
        save link image media preview codesample
        table code lists fullscreen insertdatetime nonbreaking
        directionality searchreplace wordcount visualblocks
        visualchars code fullscreen autolink lists charmap
        anchor pagebreak
    ''',
    'toolbar1': '''
        fullscreen preview bold italic underline | fontselect,
        fontsizeselect | forecolor backcolor | alignleft aligncenter
        alignright alignjustify | indent outdent | bullist numlist
    ''',
    'toolbar2': '''
        visualblocks visualchars |
        charmap pagebreak nonbreaking anchor | code |
        link unlink | image media | table | codesample |
        searchreplace | undo redo
    ''',
    'menubar': True,
    'statusbar': True,
    'content_css': [
        '//fonts.googleapis.com/css?family=Lato:300,300i,400,400i',
        '//www.tinymce.com/css/codepen.min.css'
    ],
    'language': 'ru',
    'directionality': 'ltr',
    'paste_data_images': True,
    'image_advtab': True,
    'image_title': True,
    'automatic_uploads': True,
    'file_picker_types': 'image',
    'images_upload_url': reverse_lazy('blog:tinymce_upload'),
}

# Translation API Settings
YANDEX_TRANSLATE_API_KEY = env('YANDEX_TRANSLATE_API_KEY', default='')
YANDEX_TRANSLATE_FOLDER_ID = env('YANDEX_TRANSLATE_FOLDER_ID', default='')
YANDEX_TRANSLATE_ENDPOINT = env(
    'YANDEX_TRANSLATE_ENDPOINT',
    default='https://translate.api.cloud.yandex.net/translate/v2/translate'
)

# Translation settings
TRANSLATION_SETTINGS = {
    'source_language': 'ru',
    'target_languages': ['en', 'th'],
    'chunk_size': 5000,  # Max characters per translation request
}


TAILWIND_USE_CDN = False

ADMINS = [tuple(admin.split(":")) for admin in env.list("ADMINS", default=[])]

# ImageKit cache strategy
IMAGEKIT_DEFAULT_CACHEFILE_STRATEGY = 'imagekit.cachefiles.strategies.JustInTime'
