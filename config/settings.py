"""
Django settings for this project.

This file is intentionally kept small and explicit. Values are primarily loaded
from environment variables (optionally via a local `.env` file next to this
module) to keep secrets out of source control and enable 12-factor deployment.
"""

from pathlib import Path

import environ


# ------------------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent


# ------------------------------------------------------------------------------
# Environment / runtime flags
# ------------------------------------------------------------------------------
env = environ.Env(
    # Cast and default values for environment variables.
    DEBUG=(bool, False),
    REDIS_HOST=(str, "redis"),  # Default to service name in Docker Compose
    REDIS_PORT=(int, 6379),  # Explicit int cast needed since env vars are strings
)

# Load optional local `.env` file (safe no-op if missing).
env.read_env(Path(__file__).parent / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DEBUG")


# ------------------------------------------------------------------------------
# Security / hosts
# ------------------------------------------------------------------------------
# Host header validation (kept permissive here; tighten in production).
ALLOWED_HOSTS = ["*"]


# ------------------------------------------------------------------------------
# Applications
# ------------------------------------------------------------------------------
INSTALLED_APPS = [
    'daphne',
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.diary",
    "rest_framework",
    "django_filters",
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'channels',
]


# ------------------------------------------------------------------------------
# Middleware
# ------------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'diary.middleware.UserLastRequestMiddleware',
    'diary.middleware.UncaughtExceptionMiddleware',
]


# ------------------------------------------------------------------------------
# URL routing / templates
# ------------------------------------------------------------------------------
ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# ------------------------------------------------------------------------------
# WSGI
# ------------------------------------------------------------------------------
WSGI_APPLICATION = "config.wsgi.application"


# ------------------------------------------------------------------------------
# Database
# ------------------------------------------------------------------------------
DATABASES = {
    # Reads `DATABASE_URL`.
    "default": env.db(),
}


# ------------------------------------------------------------------------------
# Authentication / password validation
# ------------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# ------------------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'other_errors': {
            'format': '{levelname} - {asctime} - {module} - {process: d} - {thread: d} - {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': 'other_errors.log',
            'formatter': 'other_errors',
        },
    },
    'loggers': {
        'diary.middleware': {
            'handlers': ['file'],
            'level': 'WARNING',
            'propagate': True,
        },
    },
}
# ------------------------------------------------------------------------------
# Internationalization
# ------------------------------------------------------------------------------
LANGUAGE_CODE = "en-gb"

TIME_ZONE = "Europe/Prague"

USE_I18N = True

USE_TZ = True


# ------------------------------------------------------------------------------
# Static files / media uploads
# ------------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"


# Email configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env('EMAIL_HOST')
EMAIL_PORT = env('EMAIL_PORT')
EMAIL_HOST_USER = env('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')
EMAIL_USE_TLS = env('EMAIL_USE_TLS')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL')
WEEKLY_RECIPIENTS = env('WEEKLY_RECIPIENTS')

# ------------------------------------------------------------------------------
# Redis configuration (used for both Channels and Celery)
# ------------------------------------------------------------------------------
REDIS_HOST = env("REDIS_HOST")
REDIS_PORT = env("REDIS_PORT")


# ------------------------------------------------------------------------------
# Defaults
# ------------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ------------------------------------------------------------------------------
# REST Framework
# ------------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication'
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
}


# ------------------------------------------------------------------------------
# CHANNELS
# ------------------------------------------------------------------------------
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [(REDIS_HOST, REDIS_PORT)],
        },
    },
}

AUTH_USER_MODEL = 'diary.CustomUser'
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'

# ============================================================================
# CELERY CONFIGURATION
# ============================================================================
# Uses REDIS_HOST and REDIS_PORT loaded from env vars above
CELERY_BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/1"
CELERY_RESULT_BACKEND = f"redis://{REDIS_HOST}:{REDIS_PORT}/1"

# ------------------------------------------------------------------------------
# Simple JWT
# ------------------------------------------------------------------------------
SIMPLE_JWT = {
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('JWT',),
}
