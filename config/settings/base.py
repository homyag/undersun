import json
import os
import sys
from pathlib import Path
import environ
from django.urls import reverse_lazy


BASE_DIR = Path(__file__).resolve().parent.parent.parent
IP2ASN_DB_PATH = BASE_DIR / 'tmp' / 'ip2asn.tsv'


sys.path.insert(0, os.path.join(BASE_DIR, 'apps'))


env = environ.Env(
    DEBUG=(bool, False)
)


env_file = BASE_DIR / '.env'
if env_file.exists():
    env.read_env(env_file)


SITE_NAME = env('SITE_NAME', default='Undersun Estate')
SITE_COMPANY_NAME = env('SITE_COMPANY_NAME', default='Undersun Estate Co., Ltd.')
SITE_URL = env('SITE_URL', default='https://undersunestate.com')

# Google reCAPTCHA v3
RECAPTCHA_SITE_KEY = env('RECAPTCHA_SITE_KEY', default='')
RECAPTCHA_SECRET_KEY = env('RECAPTCHA_SECRET_KEY', default='')
RECAPTCHA_VERIFY_URL = 'https://www.google.com/recaptcha/api/siteverify'
RECAPTCHA_MIN_SCORE = env.float('RECAPTCHA_MIN_SCORE', default=0.5)


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


def _load_googlebot_ip_ranges():
    base_path = BASE_DIR / 'seo' / 'googlebot-ip-ranges'
    if not base_path.exists():
        return []

    ranges = set()
    for json_path in base_path.glob('*.json'):
        try:
            data = json.loads(json_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        for prefix in data.get('prefixes', []):
            for key in ('ipv4Prefix', 'ipv6Prefix'):
                value = prefix.get(key)
                if value:
                    ranges.add(value.strip())

    return sorted(ranges)


GOOGLEBOT_IP_RANGES = _load_googlebot_ip_ranges()

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'apps.core.middleware.LanguageRedirectMiddleware',
    'apps.core.middleware.LegacyRealEstateRedirectMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'apps.core.middleware.BadInquiryRequestLoggerMiddleware',
    'apps.core.middleware.ForbiddenPathLoggerMiddleware',
    'apps.core.middleware.BotDetectionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.middleware.PermissionsPolicyMiddleware',  # Fix for admin permissions policy
    'apps.core.middleware.FrameAncestorsMiddleware',
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

# Bot protection (Phase 1 defaults)
BOT_PROTECTION = {
    'ENABLED': env.bool('BOT_PROTECTION_ENABLED', default=True),
    'WHITELIST_IPS': [
        #'91.212.150.176',  # reverse proxy for RU traffic
        '95.161.221.91',   # admin IP
        '5.45.192.0/18',
        '5.255.192.0/18',
        '37.9.64.0/18',
        '37.140.128.0/18',
        '77.88.0.0/18',
        '84.252.160.0/19',
        '87.250.224.0/19',
        '90.156.176.0/20',
        '92.255.112.0/20',
        '93.158.128.0/18',
        '95.108.128.0/17',
        '141.8.128.0/18',
        '178.154.128.0/18',
        '185.32.187.0/24',
        '213.180.192.0/19',
        '2a02:6b8::/29',
    ] + GOOGLEBOT_IP_RANGES,
    'WHITELIST_USER_AGENTS': [
        r'Googlebot',
        r'Chrome-Lighthouse',
        r'Google-InspectionTool',
        r'Google-Structured-Data-Testing-Tool',
        r'Structured-Data-Testing-Tool',
        r'Schema-Markup-Validator',
        r'Google-Read-Aloud',
        r'Bingbot',
        r'BingPreview',
        r'Slurp',
        r'DuckDuckBot',
        r'YandexBot',
        r'YandexMetrika',
        r'Mail\.RU_Bot',
        r'Baiduspider',
        r'Sogou',
        r'PetalBot',
        r'LinkedInBot',
        r'facebookexternalhit',
        r'meta-externalagent',
        r'Twitterbot',
        r'Applebot',
        r'AhrefsBot',
        r'AhrefsSiteAudit',
        r'Screaming Frog',
        r'SemrushBot',
        r'Amazonbot',
        r'Instagram',
        r'OpenAI-SearchBot',
        r'GPTBot',
        r'ClaudeBot',
        r'Claude-User',
        r'Claude-SearchBot',
        r'claude-code',
        r'AnthropicAI',
        r'Bytespider',
        r'CensysInspect',
        r'Palo Alto Networks',
        r'ChatGPT-User',
        r'Slackbot',
        r'TelegramBot',
        r'newsai/1\.0',
        r'MJ12bot',
        r'SERankingBacklinksBot',
        r'PerplexityBot',
        r'TikTokSpider',
        r'BusinessValidator',
    ],
    'BLACKLIST_IPS': [
        '20.205.115.105',
        '20.220.148.239',
        '20.203.201.174',
        '104.208.81.121',
        '4.194.217.214',
        '20.27.221.169',
        '20.151.2.11',
        '20.69.252.116',
        '20.151.224.91',
        '20.123.25.77',
    ],
    'SUSPICIOUS_USER_AGENTS': [
        r'curl',
        r'python-requests',
        r'Go-http-client',
        r'Go-http-client/2\.0',
        r'HeadlessChrome',
        r'zgrab',
    ],
    'HIGH_RISK_USER_AGENT_PATTERNS': [
        r'Chrome/13[0-9]\.0\.0\.0 Safari/537\.36$',
        r'Mozilla/5\.0 \(Windows NT 10\.0; Win64; x64\).*Chrome/139\.0\.0\.0',
    ],
    'FORBIDDEN_PATH_PATTERNS': [
        r'^/administrator(?:/|$)',
        r'^/wp-admin',
        r'^/wp-login\.php$',
        r'^/wp-content',
        r'^/wp-includes',
        r'^/phpmyadmin',
        r'^/pma',
        r'^/adminer',
        r'^/manager/html',
        r'^/vendor/phpunit',
        r'^/wp-json',
        r'^/xmlrpc\.php$',
        r'^/\.env',
        r'^/\.git',
        r'^/vendor(?:/|$)',
        r'^/composer\.json$',
        r'^/package-lock\.json$',
        r'^/aws',
        r'^/cgi-bin',
        r'^/storage',
        r'^/backup',
        r'^/\.well-known/security\.txt',
        r'/wp-content/plugins/hellopress',
        r'/wp-content/plugins',
    ],
    'HEADER_KEYS': [
        'HTTP_ACCEPT_LANGUAGE',
        'HTTP_ACCEPT_ENCODING',
        'HTTP_SEC_CH_UA',
        'HTTP_SEC_CH_UA_PLATFORM',
        'HTTP_SEC_FETCH_DEST',
        'HTTP_SEC_FETCH_SITE',
    ],
    'RATE_LIMIT': {
        'WINDOW_SECONDS': 10,
        'MAX_REQUESTS': 5,
    },
    'ISSUE_SERVER_CHALLENGE_COOKIE': False,
    'RESPECT_MANUAL_IP_BANS': False,
    'JS_CHALLENGE_GRACE_SECONDS': 10,
    'JS_CHALLENGE_MAX_MISSES': 3,
    'ACTION_THRESHOLDS': {
        'monitor': 30,
        'challenge': 60,
        'block': 90,
        'fail2ban': 100,
    },
    'SKIP_PATH_PREFIXES': ['/static/', '/media/'],
    'SKIP_METHODS': ['OPTIONS'],
    'BOUNCE_WINDOW_SECONDS': 5,
    'ASN_DB_PATH': IP2ASN_DB_PATH,
    'ASN_WEIGHTS': {
        'AS16509': 40,  # Amazon AWS
        'AS14618': 40,
        'AS14061': 35,  # DigitalOcean
        'AS16276': 35,  # OVH
        'AS24940': 35,  # Hetzner
        'AS61317': 35,  # DigitalEnergy
        'AS4837': 45,   # China169 Backbone
        'AS9808': 45,   # China Mobile
        'AS4811': 45,   # China Telecom Shanghai
        'AS4134': 45,   # ChinaNet Backbone
        'AS58563': 45,  # China Telecom Hubei
        'AS134763': 40, # CT Dongguan IDC
        'AS134760': 40, # ChinaNet Hebei
    },
    'ASN_ORG_PATTERNS': {
        'google': 15,
        'facebook': 15,
    },
    'RULE_WEIGHTS': {
        'forbidden_path': 120,
        'suspicious_user_agent': 25,
        'high_risk_user_agent': 35,
        'missing_headers': 10,
        'missing_headers_critical': 120,
        'no_referer': 15,
        'no_referer_combo': 25,
        'js_challenge_missing': 40,
        'js_challenge_failed': 120,
        'single_html_hit': 35,
        'asn_datacenter': 40,
        'rate_limit': 20,
        'blacklist_ip': 40,
        'suspicious_payload': 30,
        'head_on_html': 10,
    },
    'CHALLENGE_COOKIE': 'bot_challenge',
    'CHALLENGE_QUERY_PARAM': 'bot_challenge_token',
    'CHALLENGE_COOKIE_MAX_AGE_DAYS': 7,
}

GOOGLE_PLACES_API_KEY = env('GOOGLE_PLACES_API_KEY', default='')
GOOGLE_PLACE_ID = env('GOOGLE_PLACE_ID', default='')
GOOGLE_BUSINESS_PROFILE_ACCOUNT_ID = env('GOOGLE_BUSINESS_PROFILE_ACCOUNT_ID', default='')
GOOGLE_BUSINESS_PROFILE_LOCATION_ID = env('GOOGLE_BUSINESS_PROFILE_LOCATION_ID', default='')
GOOGLE_OAUTH_CLIENT_ID = env('GOOGLE_OAUTH_CLIENT_ID', default='')
GOOGLE_OAUTH_CLIENT_SECRET = env('GOOGLE_OAUTH_CLIENT_SECRET', default='')
GOOGLE_OAUTH_REFRESH_TOKEN = env('GOOGLE_OAUTH_REFRESH_TOKEN', default='')
GOOGLE_BUSINESS_PROFILE_CONFIGURED = bool(
    GOOGLE_BUSINESS_PROFILE_ACCOUNT_ID
    and GOOGLE_BUSINESS_PROFILE_LOCATION_ID
    and GOOGLE_OAUTH_CLIENT_ID
    and GOOGLE_OAUTH_CLIENT_SECRET
    and GOOGLE_OAUTH_REFRESH_TOKEN
)
GOOGLE_REVIEWS = {
    'ENABLED': env.bool(
        'GOOGLE_REVIEWS_ENABLED',
        default=GOOGLE_BUSINESS_PROFILE_CONFIGURED or bool(GOOGLE_PLACES_API_KEY and GOOGLE_PLACE_ID),
    ),
    'SOURCE': env('GOOGLE_REVIEWS_SOURCE', default='business_profile'),
    'API_KEY': GOOGLE_PLACES_API_KEY,
    'PLACE_ID': GOOGLE_PLACE_ID,
    'BUSINESS_PROFILE_ACCOUNT_ID': GOOGLE_BUSINESS_PROFILE_ACCOUNT_ID,
    'BUSINESS_PROFILE_LOCATION_ID': GOOGLE_BUSINESS_PROFILE_LOCATION_ID,
    'OAUTH_CLIENT_ID': GOOGLE_OAUTH_CLIENT_ID,
    'OAUTH_CLIENT_SECRET': GOOGLE_OAUTH_CLIENT_SECRET,
    'OAUTH_REFRESH_TOKEN': GOOGLE_OAUTH_REFRESH_TOKEN,
    'MAPS_URL': env('GOOGLE_REVIEWS_MAPS_URL', default='https://maps.google.com/maps?cid=15686779743811846375'),
    'PAGE_SIZE': env.int('GOOGLE_REVIEWS_PAGE_SIZE', default=10),
    'ORDER_BY': env('GOOGLE_REVIEWS_ORDER_BY', default='updateTime desc'),
    'CACHE_TIMEOUT': env.int('GOOGLE_REVIEWS_CACHE_TIMEOUT', default=43200),
    'REQUEST_TIMEOUT': env.float('GOOGLE_REVIEWS_REQUEST_TIMEOUT', default=4),
}

# Login/Logout URLs
LOGIN_URL = '/users/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# Session settings
SESSION_COOKIE_AGE = 1209600  # 2 weeks

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

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
    'images_file_types': 'jpeg,jpg,jpe,jfi,jif,jfif,png,gif,webp,svg',
    'images_upload_url': reverse_lazy('blog:tinymce_upload'),
}

# Translation API Settings
YANDEX_TRANSLATE_API_KEY = env('YANDEX_TRANSLATE_API_KEY', default='')
YANDEX_TRANSLATE_FOLDER_ID = env('YANDEX_TRANSLATE_FOLDER_ID', default='')
YANDEX_TRANSLATE_ENDPOINT = env(
    'YANDEX_TRANSLATE_ENDPOINT',
    default='https://translate.api.cloud.yandex.net/translate/v2/translate'
)
YANDEX_TRANSLATE_CONNECT_TIMEOUT = env.float(
    'YANDEX_TRANSLATE_CONNECT_TIMEOUT',
    default=5.0,
)
YANDEX_TRANSLATE_READ_TIMEOUT = env.float(
    'YANDEX_TRANSLATE_READ_TIMEOUT',
    default=20.0,
)
YANDEX_TRANSLATE_FAILURE_COOLDOWN_SECONDS = env.float(
    'YANDEX_TRANSLATE_FAILURE_COOLDOWN_SECONDS',
    default=60.0,
)

# Translation settings
TRANSLATION_SETTINGS = {
    'source_language': 'ru',
    'target_languages': ['en', 'th'],
    'chunk_size': 5000,  # Max characters per translation request
    'request_timeout': (
        YANDEX_TRANSLATE_CONNECT_TIMEOUT,
        YANDEX_TRANSLATE_READ_TIMEOUT,
    ),
    'failure_cooldown_seconds': YANDEX_TRANSLATE_FAILURE_COOLDOWN_SECONDS,
}


TAILWIND_USE_CDN = False

ADMINS = [tuple(admin.split(":")) for admin in env.list("ADMINS", default=[])]

# ImageKit cache strategy
IMAGEKIT_DEFAULT_CACHEFILE_STRATEGY = 'imagekit.cachefiles.strategies.JustInTime'

# CSP frame-ancestors directive (override in production when needed)
FRAME_ANCESTORS = None
