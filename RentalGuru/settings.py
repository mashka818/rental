import os.path
from datetime import timedelta
from os import getenv
from pathlib import Path

import redis
from dotenv import load_dotenv

load_dotenv()
# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = getenv('SECRET_KEY')
SMS_AERO_API_URL = 'https://sms.aero/api/v1/messages/send'
SMS_AERO_API_KEY = getenv('SMS_AERO_API_KEY')
TELEGRAM_BOT_TOKEN = getenv('TELEGRAM_BOT_TOKEN')


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = getenv('DEBUG')
ALLOWED_HOSTS = [getenv('ALLOWED_HOSTS')]
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

# CORS settings
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

CORS_ALLOW_ALL_ORIGINS = True

# Application definition
INSTALLED_APPS = [
    'jet',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'rest_framework.authtoken',
    'rest_framework_simplejwt',
    'django_filters',
    'channels',
    'app',
    'vehicle',
    'chat',
    'notification',
    'franchise',
    'influencer',
    'feedback',
    'journal',
    'payment',
    'complaint',
    'manager',
    'report',
    'drf_spectacular',
    'polymorphic',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'app.middleware.TranslationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'RentalGuru.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'RentalGuru.wsgi.application'
ASGI_APPLICATION = 'RentalGuru.asgi.application'

# Redis settings
REDIS_HOST = getenv('REDIS_HOST', 'redis')
REDIS_PORT = getenv('REDIS_PORT', '6379')
REDIS_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}'
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [REDIS_URL],
        },
    },
}

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'redis://{REDIS_HOST}:{REDIS_PORT}/2',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

redis_1 = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=1)

# Celery settings 
CELERY_BROKER_URL = REDIS_URL + '/0'
CELERY_RESULT_BACKEND = REDIS_URL + '/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'


# Database settings
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': getenv('DB_NAME'),
        'USER': getenv('DB_USER'),
        'PASSWORD': getenv('DB_PASSWORD'),
        'HOST': getenv('DB_HOST'),
        'PORT': '5432'
    }
}

AUTH_USER_MODEL = 'app.User'

REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework_simplejwt.authentication.JWTAuthentication',
                                       'rest_framework.authentication.SessionAuthentication'],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}


# Spectacular settings
SPECTACULAR_SETTINGS = {
    'TITLE': 'Rental-Guru',
    'DESCRIPTION': 'rental vehicles',
    'VERSION': '1.0.0',
}

# CSRF settings
CSRF_TRUSTED_ORIGINS = [
    'https://rental-guru.netlify.app'
]
CSRF_COOKIE_NAME = 'csrftoken'
CSRF_HEADER_NAME = 'HTTP_X_CSRFTOKEN'

# Настройки перевода
TRANSLATION_ENABLED = True
TRANSLATION_DEFAULT_LANGUAGE = 'ru'
TRANSLATION_CACHE_TIMEOUT = 86400  # 24 часа
TRANSLATION_MAX_LENGTH = 5000  # Максимальная длина
TRANSLATION_MIN_LENGTH = 3  # Минимальная длина для перевода
TRANSLATION_MAX_WORKERS = 4  # Количество параллельных потоков
TRANSLATION_EXCLUDED_KEYWORDS = [
    'url', 'slug', 'id', 'price', 'year', 'latitude', 'code', 'language',
    'longitude', 'rating', 'email', 'phone', 'http://', 'https://'
]

# Logging into 'info.log'
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {name} {message}',
            'style': '{',
        },
        'with_path': {
            'format': '{levelname} {asctime} {name} {message} path={pathname}:{lineno}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'info.log'),
            'formatter': 'verbose',
            'level': 'INFO',
        },
        'requests': {
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'requests.log'),
            'formatter': 'verbose',
            'level': 'INFO',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['console', 'requests'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.server': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'chat': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'payment': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

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
# https://docs.djangoproject.com/en/5.0/topics/i18n/
LANGUAGE_CODE = 'ru'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=180),
}

# Admin jet-reboot settings
JET_THEMES = [
    {
        'theme': 'default',
        'color': '#47bac1',
        'title': 'Default'
    },
    {
        'theme': 'green',
        'color': '#44b78b',
        'title': 'Green'
    },
    {
        'theme': 'light-green',
        'color': '#83C3AA',
        'title': 'Light Green'
    },
    {
        'theme': 'light-violet',
        'color': '#C1A7CE',
        'title': 'Light Violet'
    },
    {
        'theme': 'light-blue',
        'color': '#5EADDE',
        'title': 'Light Blue'
    },
    {
        'theme': 'light-gray',
        'color': '#222',
        'title': 'Light Gray'
    }
]

JET_DEFAULT_THEME = 'green'

# JET_SIDE_MENU_ITEMS = [  # Список приложений или пользовательских элементов dict
#     {'label': _('General'), 'app_label': 'core', 'items': [
#         {'name': 'help.question'},
#         {'name': 'pages.page', 'label': _('Static page')},
#         {'name': 'city'},
#         {'name': 'validationcode'},
#         {'label': _('Analytics'), 'url': 'http://example.com', 'url_blank': True},
#     ]},
#     {'label': _('Users'), 'items': [
#         {'name': 'core.user'},
#         {'name': 'auth.group'},
#         {'name': 'core.userprofile', 'permissions': ['core.user']},
#     ]},
#     {'app_label': 'banners', 'items': [
#         {'name': 'banner'},
#         {'name': 'bannertype'},
#     ]},
# ]

# Email settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.yandex.ru'
EMAIL_PORT = 465
EMAIL_USE_SSL = True
EMAIL_HOST_USER = getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = getenv('EMAIL_HOST_USER')

# Host name
HOST_URL = 'https://rentalguru.ru'
FRONT_URL = 'https://rental-guru.netlify.app'

# File upload settings
DATA_UPLOAD_MAX_MEMORY_SIZE = 20971520  # 20MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 20971520  # 20MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000

# Payments
TINYPAY_TERMINAL_KEY = getenv('TINYPAY_TERMINAL_KEY')
TINYPAY_PASSWORD = getenv('TINYPAY_PASSWORD')
TINYPAY_API_URL = 'https://securepay.tinkoff.ru/v2/'
TINYPAY_SUCCESS_URL = 'https://rental-guru.netlify.app/'
TINYPAY_FAIL_URL = 'https://rental-guru.netlify.app/'

# OAuth 2.0
AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
)

SOCIAL_AUTH_VK_OAUTH2_KEY = getenv('SOCIAL_AUTH_VK_OAUTH2_KEY')
SOCIAL_AUTH_VK_OAUTH2_SECRET = getenv('SOCIAL_AUTH_VK_OAUTH2_SECRET')
SOCIAL_AUTH_VK_OAUTH2_SCOPE = ['email']
SOCIAL_AUTH_VK_EXTRA_DATA = [('email', 'email')]
VK_REDIRECT_URI = 'https://rental-guru.netlify.app/ru/'

SOCIAL_AUTH_MAILRU_OAUTH2_KEY = getenv('SOCIAL_AUTH_MAILRU_OAUTH2_KEY')
SOCIAL_AUTH_MAILRU_OAUTH2_SECRET = getenv('SOCIAL_AUTH_MAILRU_OAUTH2_SECRET')
SOCIAL_AUTH_MAILRU_OAUTH2_SCOPE = ['email']
MAILRU_REDIRECT_URI = 'https://rental-guru.netlify.app/ru/'

SOCIAL_AUTH_YANDEX_OAUTH2_KEY = getenv('SOCIAL_AUTH_YANDEX_OAUTH2_KEY')
SOCIAL_AUTH_YANDEX_OAUTH2_SECRET = getenv('SOCIAL_AUTH_YANDEX_OAUTH2_SECRET')
SOCIAL_AUTH_YANDEX_OAUTH2_SCOPE = ['login:email']
YANDEX_REDIRECT_URI = 'https://rental-guru.netlify.app/ru/'

# Проценты по оплате
RENT_COMMISSION_PERCENTAGE = 4
FRANCHISE_COMMISSION_PERCENTAGE = 20
INFLUENCER_COMMISSION_PERCENTAGE = 40

# Время на подтверждение заявки
RENT_REQUEST_EXPIRATION_HOURS = 24

# Время на отмену поездки с возвратом средств
CANCELLATION_REFUND_LIMIT_HOURS = 48
