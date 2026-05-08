from pathlib import Path
import os
from dotenv import load_dotenv

# -------------------------
# BASE DIRECTORY
# -------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

# -------------------------
# LOAD ENV VARIABLES
# -------------------------

load_dotenv(BASE_DIR / ".env")

# -------------------------
# SECURITY
# -------------------------

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-key"
)

DEBUG = True

ALLOWED_HOSTS = []

# -------------------------
# RAZORPAY CONFIG
# -------------------------
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
# -------------------------
# EMAIL CONFIG
# -------------------------

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

EMAIL_HOST = 'smtp.sendgrid.net'
EMAIL_PORT = 587
EMAIL_USE_TLS = True

EMAIL_HOST_USER = 'apikey'
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")

DEFAULT_FROM_EMAIL = 'adi.juhi5@gmail.com'

# -------------------------
# APPS
# -------------------------

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'booking.apps.BookingConfig',
]

# -------------------------
# MIDDLEWARE
# -------------------------

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# -------------------------
# URLS
# -------------------------

ROOT_URLCONF = 'ShowTime.urls'

# -------------------------
# TEMPLATES
# -------------------------

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

# -------------------------
# WSGI
# -------------------------

WSGI_APPLICATION = 'ShowTime.wsgi.application'

# -------------------------
# DATABASE
# -------------------------

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',

        'NAME': 'ShowTime',

        'USER': 'postgres',

        'PASSWORD': 'Qubixl@123',

        'HOST': 'localhost',

        'PORT': '5432',
    }
}

# -------------------------
# PASSWORD VALIDATORS
# -------------------------

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME':
        'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },

    {
        'NAME':
        'django.contrib.auth.password_validation.MinimumLengthValidator',
    },

    {
        'NAME':
        'django.contrib.auth.password_validation.CommonPasswordValidator',
    },

    {
        'NAME':
        'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# -------------------------
# LANGUAGE & TIME
# -------------------------

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

# -------------------------
# STATIC FILES
# -------------------------

STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / 'booking' / 'static',
]

# -------------------------
# DEFAULT PRIMARY KEY
# -------------------------

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'