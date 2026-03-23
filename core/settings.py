"""
Django settings for starkbank_webhook project.
"""

import sentry_sdk
from pathlib import Path
from decouple import config, Csv

SENTRY_DSN = config('SENTRY_DSN', default='')
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        traces_sample_rate=config('SENTRY_TRACES_SAMPLE_RATE', default=0.1, cast=float),
        profiles_sample_rate=config('SENTRY_PROFILES_SAMPLE_RATE', default=0.1, cast=float),
        send_default_pii=False,
        environment=config('SENTRY_ENVIRONMENT', default='development'),
    )

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY', default='django-insecure-dev-key')

DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'drf_spectacular',
    'django_celery_beat',
    'invoices',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='starkbank_db'),
        'USER': config('DB_USER', default='starkbank_user'),
        'PASSWORD': config('DB_PASSWORD', default='starkbank_pass'),
        'HOST': config('DB_HOST', default='db'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': config('THROTTLE_RATE_ANON', default='100/hour'),
        'user': config('THROTTLE_RATE_USER', default='1000/hour'),
        'webhook': config('THROTTLE_RATE_WEBHOOK', default='60/minute'),
    },
}

# DRF Spectacular
SPECTACULAR_SETTINGS = {
    'TITLE': 'Stark Bank Webhook API',
    'DESCRIPTION': 'API for processing Stark Bank invoice webhooks and transfers',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SECURITY': [{'ApiKeyAuth': []}],
    'COMPONENTS': {
        'securitySchemes': {
            'ApiKeyAuth': {
                'type': 'apiKey',
                'in': 'header',
                'name': 'X-API-Key',
            },
        },
    },
}

CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://redis:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_BROKER_URL', default='redis://redis:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'America/Sao_Paulo'

CELERY_RETRY_BACKOFF = config('CELERY_RETRY_BACKOFF', default=60, cast=int)
CELERY_RETRY_BACKOFF_MAX = config('CELERY_RETRY_BACKOFF_MAX', default=600, cast=int)
CELERY_RETRY_MAX = config('CELERY_RETRY_MAX', default=5, cast=int)

CELERY_BEAT_SCHEDULE = {
    'issue-invoices-every-3-hours': {
        'task': 'invoices.tasks.issue_invoices',
        'schedule': 3 * 60 * 60,  # 3 hours in seconds
    },
}

STARKBANK_ENVIRONMENT = config('STARKBANK_ENVIRONMENT', default='sandbox')
STARKBANK_PROJECT_ID = config('STARKBANK_PROJECT_ID', default='')
STARKBANK_PRIVATE_KEY_PATH = config('STARKBANK_PRIVATE_KEY_PATH', default='')

TRANSFER_BANK_CODE = config('TRANSFER_BANK_CODE', default='20018183')
TRANSFER_BRANCH_CODE = config('TRANSFER_BRANCH_CODE', default='0001')
TRANSFER_ACCOUNT_NUMBER = config('TRANSFER_ACCOUNT_NUMBER', default='6341320293482496')
TRANSFER_ACCOUNT_NAME = config('TRANSFER_ACCOUNT_NAME', default='Stark Bank S.A.')
TRANSFER_TAX_ID = config('TRANSFER_TAX_ID', default='20.018.183/0001-80')
TRANSFER_ACCOUNT_TYPE = config('TRANSFER_ACCOUNT_TYPE', default='payment')

# API Authentication
API_KEY = config('API_KEY', default='')

# Webhook IP Whitelist (comma-separated, empty = disabled)
WEBHOOK_IP_WHITELIST = config('WEBHOOK_IP_WHITELIST', default='', cast=Csv())