import os
from decimal import Decimal
from pathlib import Path

import environ

env = environ.Env()

BASE_DIR = Path(__file__).resolve().parent.parent

environ.Env.read_env(BASE_DIR / "config" / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)

# Si ALLOWED_HOSTS está en .env pero vacío, env.list puede dejar la lista vacía y Django
# responde 400 DisallowedHost para cualquier host (incl. 127.0.0.1).
_default_hosts = ["localhost", "127.0.0.1", "localhost:5173", "127.0.0.1:5173"]
_raw_hosts = os.environ.get("ALLOWED_HOSTS")
if _raw_hosts is not None and not str(_raw_hosts).strip():
    ALLOWED_HOSTS = list(_default_hosts)
else:
    ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=_default_hosts)
    if not ALLOWED_HOSTS or ALLOWED_HOSTS == [""]:
        ALLOWED_HOSTS = list(_default_hosts)

# Login POST del admin con Django 4+ comprueba orígenes de confianza.
_default_csrf_origins = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]
_raw_csrf = os.environ.get("CSRF_TRUSTED_ORIGINS")
if _raw_csrf is not None and not str(_raw_csrf).strip():
    CSRF_TRUSTED_ORIGINS = list(_default_csrf_origins)
else:
    CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=_default_csrf_origins)
    if not CSRF_TRUSTED_ORIGINS or CSRF_TRUSTED_ORIGINS == [""]:
        CSRF_TRUSTED_ORIGINS = list(_default_csrf_origins)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "apps.users",
    "apps.products",
    "apps.inventory",
    "apps.purchases",
    "apps.dashboard",
    "apps.analytics",
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
    "config.middleware.ApiExceptionMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://segupak:segupak_secret@localhost:5432/segupak_db",
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Buenos_Aires"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "users.User"

CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:5173", "http://127.0.0.1:5173"],
)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
}

from datetime import timedelta

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "UPDATE_LAST_LOGIN": False,
}

# Legado / reservado; el flujo de solicitudes en `purchases.rules` no usa costo ni este umbral para Gerencia.
GERENCIA_COSTO_UMBRAL = Decimal(str(env("GERENCIA_COSTO_UMBRAL", default="10000.00")))

# Celery: broker y result backend en Redis por defecto (misma URL que REDIS_URL).
CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=CELERY_BROKER_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

from celery.schedules import crontab

# Hora local de Django (TIME_ZONE): por defecto 22:00. Sobrescribir con CELERY_ETL_CRON_HOUR / MINUTE.
_etl_hour = env.int("CELERY_ETL_CRON_HOUR", default=22)
_etl_minute = env.int("CELERY_ETL_CRON_MINUTE", default=0)
CELERY_BEAT_SCHEDULE = {
    "etl-analitico-d1-diario": {
        "task": "apps.analytics.tasks.run_etl_analitico_d1",
        "schedule": crontab(hour=_etl_hour, minute=_etl_minute),
        "kwargs": {"metodo": "SCHEDULED"},
    },
}

# Email (notificaciones Release 1: estado de solicitud)
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Segupak <noreply@segupak.local>")
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
