"""
Django settings for this project.

This file is intentionally kept small and explicit. Values are primarily loaded
from environment variables (optionally via a local `.env` file next to this
module) to keep secrets out of source control and enable 12-factor deployment.

Environment modes (controlled by DJANGO_ENV):
- development (default): DEBUG=True, local filesystem storage, permissive settings
- production: DEBUG=False, S3 media, ManifestStaticFilesStorage, security hardening
"""

from pathlib import Path

import environ

# ==============================================================================
# CORE SETTINGS
# ==============================================================================

# ------------------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent


# ------------------------------------------------------------------------------
# Environment
# ------------------------------------------------------------------------------
env = environ.Env(
    DJANGO_ENV=(str, "development"),
    REDIS_HOST=(str, "redis"),
    REDIS_PORT=(int, 6379),
)

env.read_env(Path(__file__).parent / ".env")

DJANGO_ENV = env("DJANGO_ENV")
SECRET_KEY = env("DJANGO_SECRET_KEY")

IS_PRODUCTION = DJANGO_ENV == "production"
DEBUG = not IS_PRODUCTION


# ------------------------------------------------------------------------------
# Security / Hosts
# ------------------------------------------------------------------------------
if IS_PRODUCTION:
    ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
    CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS")

    # Security settings for production (CloudFlare handles SSL termination)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"

    # HSTS is handled by CloudFlare, so we don't set it here
    # SECURE_HSTS_SECONDS = 31536000
    # SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # SECURE_HSTS_PRELOAD = True
else:
    ALLOWED_HOSTS = ["*"]


# ==============================================================================
# APPLICATION DEFINITION
# ==============================================================================

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Local apps
    "apps.diary",
    # Third-party apps
    "corsheaders",
    "rest_framework",
    "django_filters",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "channels",
    "storages",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.diary.middleware.UserLastActivityMiddleware",
    "apps.diary.middleware.UncaughtExceptionMiddleware",
]

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

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# ==============================================================================
# DATABASE
# ==============================================================================

DATABASES = {
    "default": env.db(),
}


# ==============================================================================
# AUTHENTICATION
# ==============================================================================

AUTH_USER_MODEL = "diary.CustomUser"

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

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"


# ==============================================================================
# INTERNATIONALIZATION
# ==============================================================================

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Europe/Prague"
USE_I18N = True
USE_TZ = True


# ==============================================================================
# STATIC & MEDIA FILES
# ==============================================================================

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

if IS_PRODUCTION:
    # ------------------------------------------------------------------------------
    # Production: ManifestStaticFilesStorage + S3 for media
    # ------------------------------------------------------------------------------
    # AWS S3 configuration for media files
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="eu-central-1")

    # S3 settings
    AWS_S3_FILE_OVERWRITE = False  # Don't overwrite files with same name
    AWS_DEFAULT_ACL = None  # Use bucket's default ACL
    AWS_S3_OBJECT_PARAMETERS = {
        "CacheControl": "max-age=86400",  # 1 day cache for media
    }
    AWS_QUERYSTRING_AUTH = False  # Public URLs without query string auth

    # Custom domain for S3 (optional: use CloudFront or direct S3)
    # AWS_S3_CUSTOM_DOMAIN = f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"
    # Or with CloudFront:
    # AWS_S3_CUSTOM_DOMAIN = "media.postways.com"

    STORAGES = {
        "default": {
            # S3 storage for media (user uploads)
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        },
        "staticfiles": {
            # ManifestStaticFilesStorage for hashed static file names
            # Enables aggressive browser caching with cache-busting on changes
            "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
        },
    }

    # Media URL points to S3 bucket (or CloudFront if configured)
    MEDIA_URL = (
        f"https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com/"
    )

else:
    # ------------------------------------------------------------------------------
    # Development: Local filesystem storage
    # ------------------------------------------------------------------------------
    MEDIA_URL = "media/"
    MEDIA_ROOT = BASE_DIR / "media"

    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }


# ==============================================================================
# EMAIL
# ==============================================================================

# Use console backend in DEBUG mode if EMAIL_HOST is not set (for local development)
if DEBUG and not env("EMAIL_HOST", default=None):
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = env("EMAIL_HOST")
    EMAIL_PORT = env.int("EMAIL_PORT", default=587)
    EMAIL_HOST_USER = env("EMAIL_HOST_USER")
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
    EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
    EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
    EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=30)
    DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default=EMAIL_HOST_USER)
WEEKLY_RECIPIENTS = env.list("WEEKLY_RECIPIENTS", default=[])


# ==============================================================================
# LOGGING
# ==============================================================================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} - {asctime} - {module} - {process:d} - {thread:d} - {message}",
            "style": "{",
        },
    },
    "handlers": {
        "middleware_file": {
            "level": "WARNING",
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs" / "middleware.log",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "apps.diary.middleware": {
            "handlers": ["middleware_file"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}


# ==============================================================================
# DEFAULT SETTINGS
# ==============================================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ==============================================================================
# THIRD-PARTY SETTINGS
# ==============================================================================

# ------------------------------------------------------------------------------
# Redis (shared by Channels and Celery)
# ------------------------------------------------------------------------------
REDIS_HOST = env("REDIS_HOST")
REDIS_PORT = env("REDIS_PORT")


# ------------------------------------------------------------------------------
# Django REST Framework
# ------------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",  # Fallback for browser-based API access
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
}


# ------------------------------------------------------------------------------
# Simple JWT
# ------------------------------------------------------------------------------
SIMPLE_JWT = {
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    # AUTH_HEADER_TYPES defaults to ("Bearer",) - using default
}


# ------------------------------------------------------------------------------
# Django Channels
# ------------------------------------------------------------------------------
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [f"redis://{REDIS_HOST}:{REDIS_PORT}/0"],
        },
    },
}


# ------------------------------------------------------------------------------
# Django Cache
# ------------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:{REDIS_PORT}/2",
    },
}


# ------------------------------------------------------------------------------
# Celery
# ------------------------------------------------------------------------------
CELERY_BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/1"
CELERY_RESULT_BACKEND = f"redis://{REDIS_HOST}:{REDIS_PORT}/1"


# ------------------------------------------------------------------------------
# Django CORS Headers
# ------------------------------------------------------------------------------
# In development, allow all origins. In production, set CORS_ALLOWED_ORIGINS env var.
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
