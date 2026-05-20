import os
import shutil
import sys
import tempfile
from pathlib import Path

try:
    import dj_database_url
except ImportError:
    dj_database_url = None

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent


def load_environment():
    # Only load from files if they exist, but do NOT override system environment variables (like Render's DATABASE_URL)
    for env_path in (BASE_DIR / ".env", BASE_DIR / ".env.local"):
        if env_path.exists():
            load_dotenv(env_path, override=False)

    django_env = os.environ.get("DJANGO_ENV", "dev").strip()
    for env_path in (
        BASE_DIR / f".env.{django_env}",
        BASE_DIR / f".env.{django_env}.local",
    ):
        if env_path.exists():
            load_dotenv(env_path, override=True)


load_environment()

DJANGO_ENV = os.environ.get("DJANGO_ENV", "dev")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

# ─── Sentry error tracking ──────────────────────────────────────────────────
# Initialised only when SENTRY_DSN is present in the environment so local dev
# stays a no-op. Send-default-pii=False because we don't want logged-in user
# emails leaking into stack traces.
_SENTRY_DSN = (os.environ.get("SENTRY_DSN") or "").strip()
if _SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration

        sentry_sdk.init(
            dsn=_SENTRY_DSN,
            integrations=[DjangoIntegration()],
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1") or 0.1),
            environment=DJANGO_ENV,
            send_default_pii=False,
        )
    except ImportError:
        # sentry-sdk not installed (e.g. very old image) — silently skip.
        pass
IS_VERCEL = bool(os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"))
IS_RENDER = bool(
    os.environ.get("RENDER")
    or os.environ.get("RENDER_SERVICE_ID")
    or os.environ.get("RENDER_INSTANCE_ID")
)


def csv_env(name, default=""):
    return [
        value.strip()
        for value in os.environ.get(name, default).split(",")
        if value.strip()
    ]


def first_env(*names, default=""):
    normalized_env = {key.upper(): value for key, value in os.environ.items()}
    for name in names:
        value = normalized_env.get(name.upper(), "").strip()
        if value:
            return value
    return default

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "vrt-space-agency-dev-key-change-me",
)
ALLOWED_HOSTS = csv_env("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")
RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
if ".onrender.com" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(".onrender.com")

CSRF_TRUSTED_ORIGINS = csv_env("DJANGO_CSRF_TRUSTED_ORIGINS")

VERCEL_URL = os.environ.get("VERCEL_URL", "").strip()
if VERCEL_URL:
    vercel_host = VERCEL_URL.replace("https://", "").replace("http://", "").strip("/")
    if vercel_host and vercel_host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(vercel_host)
    if ".vercel.app" not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(".vercel.app")

    vercel_origin = f"https://{vercel_host}"
    if vercel_host and vercel_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(vercel_origin)
    if "https://*.vercel.app" not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append("https://*.vercel.app")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "apps.core",
    "apps.seo",
    "apps.aeo",
    "apps.content",
    "apps.leads",
    "apps.case_studies",
    "apps.tools",
    "apps.analytics",
    "apps.affiliates",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
]

# Only include WhiteNoise if it's installed
try:
    import whitenoise
    MIDDLEWARE.append("whitenoise.middleware.WhiteNoiseMiddleware")
except ImportError:
    pass

MIDDLEWARE += [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
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
                "apps.leads.context_processors.workspace_projects",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

if dj_database_url and os.environ.get("DATABASE_URL"):
    # Render / Production Database
    DATABASES = {
        "default": dj_database_url.config(
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
elif os.environ.get("POSTGRES_DB"):
    # Docker / Alternative Postgres setup
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB"),
            "USER": os.environ.get("POSTGRES_USER", "postgres"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }
else:
    # Default to SQLite for local development
    sqlite_path = BASE_DIR / "db.sqlite3"
    if IS_VERCEL:
        runtime_sqlite_path = Path(tempfile.gettempdir()) / "db.sqlite3"
        if not runtime_sqlite_path.exists():
            if sqlite_path.exists():
                shutil.copyfile(sqlite_path, runtime_sqlite_path)
            else:
                runtime_sqlite_path.touch()
        sqlite_path = runtime_sqlite_path

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": sqlite_path,
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "tools:workspace-login"
LOGIN_REDIRECT_URL = "tools:workspace-dashboard"
LOGOUT_REDIRECT_URL = "core:home"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"

USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "public" / "static"]

IS_TEST = "test" in sys.argv

STATICFILES_STORAGE_BACKEND = "django.contrib.staticfiles.storage.StaticFilesStorage"
if not IS_TEST:
    try:
        import whitenoise
        STATICFILES_STORAGE_BACKEND = "whitenoise.storage.CompressedManifestStaticFilesStorage"
    except ImportError:
        pass

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": STATICFILES_STORAGE_BACKEND,
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = os.environ.get("REDIS_URL")
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", REDIS_URL or "")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
AUDIT_USE_CELERY = os.environ.get("AUDIT_USE_CELERY", "1" if CELERY_BROKER_URL else "0") == "1"
APP_BASE_URL = (
    os.environ.get("APP_BASE_URL", "").strip()
    or (f"https://{RENDER_EXTERNAL_HOSTNAME}" if RENDER_EXTERNAL_HOSTNAME else "")
    or ("http://127.0.0.1:8000" if DEBUG else "")
)
DEFAULT_AUDIT_SHARE_EXPIRY_DAYS = int(os.environ.get("DEFAULT_AUDIT_SHARE_EXPIRY_DAYS", "14"))
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "vrt-space-agency",
        }
    }

# ─── Email configuration ────────────────────────────────────────────────────
# Auto-select an SMTP backend when EMAIL_HOST is set in the environment (e.g.
# SendGrid / Resend / Mailgun on Render). Otherwise fall back to the console
# backend so local dev still works without any setup. The DJANGO_EMAIL_BACKEND
# override is always honoured if explicitly set.

EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587") or 587)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") not in ("0", "false", "False", "")
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "0") in ("1", "true", "True")
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "10") or 10)

_default_email_backend = (
    "django.core.mail.backends.smtp.EmailBackend"
    if EMAIL_HOST
    else "django.core.mail.backends.console.EmailBackend"
)
EMAIL_BACKEND = os.environ.get("DJANGO_EMAIL_BACKEND", _default_email_backend)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "hello@vrtspace.agency")
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

GOOGLE_OAUTH_CLIENT_ID = first_env(
    "GOOGLE_OAUTH_CLIENT_ID",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_AUTH_CLIENT_ID",
    "GOOGLE_PUBLISHABLE_KEY",
)
GOOGLE_OAUTH_CLIENT_SECRET = first_env(
    "GOOGLE_OAUTH_CLIENT_SECRET",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_AUTH_CLIENT_SECRET",
    "GOOGLE_SECRET_KEY",
)
GOOGLE_OAUTH_ENABLED = bool(GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET)

STRIPE_PUBLISHABLE_KEY = first_env("STRIPE_PUBLISHABLE_KEY", "PUBLISHABLE_KEY")
STRIPE_SECRET_KEY = first_env("STRIPE_SECRET_KEY", "SECRET_KEY")
STRIPE_WEBHOOK_SECRET = first_env("STRIPE_WEBHOOK_SECRET")
STRIPE_ENABLED = bool(STRIPE_PUBLISHABLE_KEY and STRIPE_SECRET_KEY)
STRIPE_PRICE_IDS = {
    "starter": first_env("STRIPE_PRICE_STARTER"),
    "growth": first_env("STRIPE_PRICE_GROWTH"),
    "authority": first_env("STRIPE_PRICE_AUTHORITY"),
    "enterprise": first_env("STRIPE_PRICE_ENTERPRISE"),
}

STRIPE_TOPUP_PACKS = [
    {
        "slug": "topup-10",
        "name": "10 credits",
        "credits": 10,
        "price_label": "$10",
        "amount_cents": 1000,
        "stripe_price_id": first_env("STRIPE_PRICE_TOPUP_10"),
    },
    {
        "slug": "topup-30",
        "name": "30 credits",
        "credits": 30,
        "price_label": "$25",
        "amount_cents": 2500,
        "stripe_price_id": first_env("STRIPE_PRICE_TOPUP_30"),
    },
    {
        "slug": "topup-70",
        "name": "70 credits",
        "credits": 70,
        "price_label": "$50",
        "amount_cents": 5000,
        "stripe_price_id": first_env("STRIPE_PRICE_TOPUP_70"),
    },
]

try:
    from celery.schedules import crontab as _crontab
except Exception:
    _crontab = None

CELERY_BEAT_SCHEDULE = {}
if _crontab is not None:
    CELERY_BEAT_SCHEDULE["affiliates-process-payouts-weekly"] = {
        "task": "affiliates.process_affiliate_payouts",
        # Mondays at 09:00 UTC — well outside US business-hour Stripe surges.
        "schedule": _crontab(hour=9, minute=0, day_of_week="mon"),
    }
    CELERY_BEAT_SCHEDULE["affiliates-refresh-connect-statuses-daily"] = {
        "task": "affiliates.refresh_connect_statuses",
        "schedule": _crontab(hour=8, minute=30),
    }

AFFILIATE_COOKIE_NAME = "vrt_ref"
AFFILIATE_COOKIE_MAX_AGE_DAYS = int(os.environ.get("AFFILIATE_COOKIE_MAX_AGE_DAYS", "60"))
AFFILIATE_COMMISSION_FIRST_PAYMENT_PCT = int(os.environ.get("AFFILIATE_COMMISSION_FIRST_PAYMENT_PCT", "25"))
AFFILIATE_COMMISSION_RECURRING_PCT = int(os.environ.get("AFFILIATE_COMMISSION_RECURRING_PCT", "15"))
AFFILIATE_PAYOUT_HOLD_DAYS = int(os.environ.get("AFFILIATE_PAYOUT_HOLD_DAYS", "30"))
AFFILIATE_STRIPE_CONNECT_ENABLED = os.environ.get("AFFILIATE_STRIPE_CONNECT_ENABLED", "1") == "1"
AFFILIATE_PROGRAM_FROM_EMAIL = os.environ.get(
    "AFFILIATE_PROGRAM_FROM_EMAIL",
    os.environ.get("DEFAULT_FROM_EMAIL", "partners@vrtspace.agency"),
)

SERP_DISCOVERY_PROVIDER = first_env("SERP_DISCOVERY_PROVIDER", default="serpapi,duckduckgo")
SERPAPI_API_KEY = first_env("SERPAPI_API_KEY", "SERP_API_KEY")
SERP_DISCOVERY_QUERY_LIMIT = int(os.environ.get("SERP_DISCOVERY_QUERY_LIMIT", "4"))
SERP_DISCOVERY_RESULTS_PER_QUERY = int(os.environ.get("SERP_DISCOVERY_RESULTS_PER_QUERY", "8"))
SERP_PROVIDER_TIMEOUT_SECONDS = int(os.environ.get("SERP_PROVIDER_TIMEOUT_SECONDS", "10"))
SERP_DUCKDUCKGO_TIMEOUT_SECONDS = int(os.environ.get("SERP_DUCKDUCKGO_TIMEOUT_SECONDS", "8"))
SERP_PROVIDER_COOLDOWN_SECONDS = int(os.environ.get("SERP_PROVIDER_COOLDOWN_SECONDS", "300"))
SERP_DUCKDUCKGO_COOLDOWN_SECONDS = int(os.environ.get("SERP_DUCKDUCKGO_COOLDOWN_SECONDS", "180"))
SERP_DISCOVERY_ENABLED = bool(
    SERP_DISCOVERY_PROVIDER and (
        "duckduckgo" in SERP_DISCOVERY_PROVIDER.lower()
        or ("serpapi" in SERP_DISCOVERY_PROVIDER.lower() and SERPAPI_API_KEY)
    )
)

CONTENT_REFINEMENT_PROVIDER = first_env("CONTENT_REFINEMENT_PROVIDER", default="deterministic")
CONTENT_REFINEMENT_MODEL = first_env("CONTENT_REFINEMENT_MODEL")
CONTENT_REFINEMENT_TIMEOUT = int(os.environ.get("CONTENT_REFINEMENT_TIMEOUT", "45"))
OLLAMA_BASE_URL = first_env("OLLAMA_BASE_URL", default="http://127.0.0.1:11434")
CONTENT_REFINEMENT_ENABLED = bool(
    CONTENT_REFINEMENT_PROVIDER == "ollama" and CONTENT_REFINEMENT_MODEL
)

SEO_REFRESH_ASYNC = False if (IS_TEST or (DEBUG and not IS_RENDER)) else os.environ.get("SEO_REFRESH_ASYNC", "1") == "1"
SEO_BACKGROUND_WORKERS = max(1, int(os.environ.get("SEO_BACKGROUND_WORKERS", "2")))
SEO_COMPETITOR_LIMIT = max(1, int(os.environ.get("SEO_COMPETITOR_LIMIT", "4")))
SEO_COMPETITOR_PAGE_LIMIT = max(1, int(os.environ.get("SEO_COMPETITOR_PAGE_LIMIT", "4")))
SEO_BACKLINK_ASYNC = os.environ.get("SEO_BACKLINK_ASYNC", "1") == "1"

AUDIT_TIER_ENFORCEMENT = os.environ.get("AUDIT_TIER_ENFORCEMENT", "0") == "1"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

if not DEBUG or DJANGO_ENV in {"staging", "production"}:
    SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "1") == "1"
else:
    SECURE_SSL_REDIRECT = False
