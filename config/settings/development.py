from .base import *

DEBUG = True

ALLOWED_HOSTS = ['51.79.173.21','localhost','127.0.0.1']

# Database для разработки (PostgreSQL)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'undersunestate_db',
        'USER': 'undersunestate_user',
        'PASSWORD': 'asertivcn',
        'HOST': 'localhost',
        'PORT': 5432,
    }
}

# Email backend для тестирования
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

TAILWIND_USE_CDN = True