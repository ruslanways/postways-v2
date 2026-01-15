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
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'apps.diary',
]


# ------------------------------------------------------------------------------
# Middleware
# ------------------------------------------------------------------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# ------------------------------------------------------------------------------
# URL routing / templates
# ------------------------------------------------------------------------------
ROOT_URLCONF = 'config.urls'

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


# ------------------------------------------------------------------------------
# WSGI
# ------------------------------------------------------------------------------
WSGI_APPLICATION = 'config.wsgi.application'


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


# ------------------------------------------------------------------------------
# Internationalization
# ------------------------------------------------------------------------------
LANGUAGE_CODE = 'en-gb'

TIME_ZONE = 'Europe/Prague'

USE_I18N = True

USE_TZ = True


# ------------------------------------------------------------------------------
# Static files / media uploads
# ------------------------------------------------------------------------------
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ------------------------------------------------------------------------------
# Defaults
# ------------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
