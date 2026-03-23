from .settings import *

# Use SQLite in-memory for tests
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Disable Celery during tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Test API Key
API_KEY = 'test-api-key'

# Disable IP whitelist for tests
WEBHOOK_IP_WHITELIST = []