import os
from pathlib import Path
from datetime import timedelta
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")

DEBUG = os.environ.get("DEBUG", "false").lower() in ("1", "true", "yes")

ALLOWED_HOSTS = ["*"]

# UPDATED FOR PRODUCTION: Added your new Render URL to trusted origins
CSRF_TRUSTED_ORIGINS = [
    "https://yeab-game-zone-o5c7.onrender.com",
    "https://baba-bingo.onrender.com",
    "https://baba-bingo-1.onrender.com"
]

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    "channels",
    "bingo",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "vlad_bingo.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": ["django.template.context_processors.debug",
                                           "django.template.context_processors.request",
                                           "django.contrib.auth.context_processors.auth",
                                           "django.contrib.messages.context_processors.messages"]},
    }
]

WSGI_APPLICATION = "vlad_bingo.wsgi.application"
ASGI_APPLICATION = "vlad_bingo.asgi.application"

# Database
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("RENDER_DATABASE_URL")
if DATABASE_URL:
    DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=600)}
else:
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }}

# Channels
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Custom user
AUTH_USER_MODEL = "bingo.User"

# Rest framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

CORS_ALLOW_ALL_ORIGINS = True

# Business rules
MIN_COMMISSION_PERCENTAGE = 20
MAX_COMMISSION_PERCENTAGE = 35