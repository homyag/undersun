from .base import *

DEBUG = True

ALLOWED_HOSTS = ['51.79.173.21','localhost','127.0.0.1', '72.60.194.3']

# Database для разработки (PostgreSQL)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'undersunestate_db',
        # 'NAME': 'testbase',
        'USER': 'undersunestate_user',
        # 'USER': 'postgres',
        'PASSWORD': 'Idmv7p8daXca!',
        # 'PASSWORD': '!QAZxsw2',
        'HOST': 'localhost',
        'PORT': 5432,
    }
}

# Email backend для тестирования
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Email настройки Prod
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
# EMAIL_PORT = env('EMAIL_PORT', default=587)
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = env('EMAIL_HOST_USER')
# EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')
# DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL')

TAILWIND_USE_CDN = False