# """
# Django settings for anchor project.
# """
# import os
# from dotenv import load_dotenv
# from pathlib import Path

# # ── Base / env ────────────────────────────────────────────────────────────────
# BASE_DIR = Path(__file__).resolve().parent.parent
# load_dotenv()  # loads .env from project root

# # Polaris / SEP config you already had
# POLARIS_INTEGRATIONS = {
#     "LOCAL_MODE": False,
#     "NETWORK_PASSPHRASE": "Public Global Stellar Network ; September 2015",
# }
# ACTIVE_SEPS = os.getenv("ACTIVE_SEPS", "sep-10,sep-6, sep-12").split(",")
# FERNET_KEY = os.getenv("FERNET_KEY")
# STELLAR_SECRET_KEY = os.getenv("STELLAR_SECRET_KEY")

# # Service-to-service token for Nest → Django (used by ServiceTokenAuth)
# PYTHON_SERVICE_TOKEN = os.getenv("PYTHON_SERVICE_TOKEN", "supersecrettoken")

# print("📢 LOCAL_MODE:", os.environ.get("LOCAL_MODE"))
# print("🌐 NETWORK_PASSPHRASE:", os.environ.get("NETWORK_PASSPHRASE"))

# # ── Core settings ─────────────────────────────────────────────────────────────
# SECRET_KEY = 'django-insecure-5%7vl%1mzw1vhu@ik6*o$md-3e+4az%^25dtfsm#a1jx#1rk6m'
# DEBUG = True

# ALLOWED_HOSTS = ['*']  # tighten for prod

# # ── CORS / CSRF for local dev (tweak for prod) ────────────────────────────────
# CORS_ALLOWED_ORIGINS = [
#     "http://localhost:3000",
#     "http://127.0.0.1:3000",
# ]
# # If your Nest server or other frontends call Django from a browser:
# CSRF_TRUSTED_ORIGINS = [
#     "http://localhost:3000",
#     "http://127.0.0.1:3000",
# ]
# CORS_ALLOW_CREDENTIALS = True

# # Allow custom headers used by the Nest backend
# CORS_ALLOW_HEADERS = list(set((
#     "accept",
#     "accept-encoding",
#     "authorization",
#     "content-type",
#     "origin",
#     "user-agent",
#     "x-csrftoken",
#     "x-requested-with",
#     # custom integration headers
#     "idempotency-key",
#     "x-actor-id",
# )))

# # ── Installed apps / middleware ───────────────────────────────────────────────
# INSTALLED_APPS = [
#     'django.contrib.admin',
#     'django.contrib.auth',
#     'django.contrib.contenttypes',
#     'django.contrib.sessions',
#     'django.contrib.messages',
#     'django.contrib.staticfiles',
#     "corsheaders",
#     "rest_framework",
#     "marimushaanchorapp.anchor",
#     "polaris",
# ]

# MIDDLEWARE = [
#     'corsheaders.middleware.CorsMiddleware',   # keep CORS first
#     'django.middleware.security.SecurityMiddleware',
#     'django.contrib.sessions.middleware.SessionMiddleware',
#     'django.middleware.common.CommonMiddleware',
#     'django.middleware.csrf.CsrfViewMiddleware',  # OK: S2S auth bypasses CSRF
#     'django.contrib.auth.middleware.AuthenticationMiddleware',
#     'django.contrib.messages.middleware.MessageMiddleware',
#     'django.middleware.clickjacking.XFrameOptionsMiddleware',
# ]

# ROOT_URLCONF = 'marimushaanchorapp.anchor.urls'

# TEMPLATES = [
#     {
#         'BACKEND': 'django.template.backends.django.DjangoTemplates',
#         'DIRS': [],
#         'APP_DIRS': True,
#         'OPTIONS': {
#             'context_processors': [
#                 'django.template.context_processors.request',
#                 'django.contrib.auth.context_processors.auth',
#                 'django.contrib.messages.context_processors.messages',
#             ],
#         },
#     },
# ]

# WSGI_APPLICATION = 'marimushaanchorapp.anchor.wsgi.application'

# # ── Database ──────────────────────────────────────────────────────────────────
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': os.getenv('DB_NAME', 'marimushaanchor'),
#         'USER': os.getenv('DB_USER', 'marimushauser'),
#         'PASSWORD': os.getenv('DB_PASSWORD', 'Letmein99x!'),
#         'HOST': os.getenv('DB_HOST', '161.97.76.198'),
#         'PORT': os.getenv('DB_PORT', '5432'),
#     }
# }

# # ── DRF defaults (safe) ───────────────────────────────────────────────────────
# # We still set authentication per-view (ServiceTokenAuth first). These defaults
# # keep browsable API useful in DEBUG without breaking S2S.
# REST_FRAMEWORK = {
#     "DEFAULT_AUTHENTICATION_CLASSES": (
#         "rest_framework.authentication.SessionAuthentication",
#         "rest_framework.authentication.BasicAuthentication",
#         # NOTE: ServiceTokenAuth is applied explicitly in views to avoid affecting admin/etc.
#         # If you prefer global, add: "marimushaanchorapp.anchor.agents.auth.ServiceTokenAuth",
#     ),
#     "DEFAULT_PERMISSION_CLASSES": (
#         "rest_framework.permissions.IsAuthenticated",
#     ),
# }

# # ── Caching (for idempotency memoization) ─────────────────────────────────────
# CACHES = {
#     "default": {
#         "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
#         "LOCATION": "anchor-cache",
#         "TIMEOUT": 60 * 60,  # 1 hour default
#     }
# }

# # ── i18n / tz ─────────────────────────────────────────────────────────────────
# LANGUAGE_CODE = 'en-us'
# TIME_ZONE = 'UTC'
# USE_I18N = True
# USE_TZ = True

# # ── Static files ──────────────────────────────────────────────────────────────
# STATIC_URL = '/static/'
# STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
"""
Django settings for anchor project - TESTNET CONFIG
"""
import os
from dotenv import load_dotenv
from pathlib import Path

# ── Base / env ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv()  # loads .env from project root

# Polaris / SEP config for TESTNET
POLARIS_INTEGRATIONS = {
    "LOCAL_MODE": True,  # Set to True for testnet
    "NETWORK_PASSPHRASE": "Test SDF Network ; September 2015",  # TESTNET
    "HORIZON_URL": "https://horizon-testnet.stellar.org",  # Testnet Horizon
    "SERVER_JWT_KEY": os.getenv("STELLAR_SECRET_KEY"),  # Your testnet secret
    "RAILS": "anchor.rails.AnchorRails",
}
ACTIVE_SEPS = os.getenv(
    "ACTIVE_SEPS",
    "sep-1,sep-6,sep-10,sep-12,sep-24,sep-31"
).split(",")
FERNET_KEY = os.getenv("FERNET_KEY")
STELLAR_SECRET_KEY = os.getenv("STELLAR_SECRET_KEY")

# Service-to-service token for Nest → Django (used by ServiceTokenAuth)
PYTHON_SERVICE_TOKEN = os.getenv("PYTHON_SERVICE_TOKEN", "supersecrettoken")

POLARIS_TRANSACTION_MODEL = "anchor.AnchorTransaction"  # adjust app label if needed


print("🔧 TESTNET MODE ACTIVE")
print("📢 LOCAL_MODE:", POLARIS_INTEGRATIONS["LOCAL_MODE"])
print("🌐 NETWORK_PASSPHRASE:", POLARIS_INTEGRATIONS["NETWORK_PASSPHRASE"])
print("🚀 HORIZON_URL:", POLARIS_INTEGRATIONS["HORIZON_URL"])

# ── Bank / payout integration (NEW) ───────────────────────────────────────────
# URL of your Nest internal transfer endpoint
BANKING_TRANSFER_URL = os.getenv(
    "BANKING_TRANSFER_URL",
    "http://192.168.100.32:7013/transfers",  # default for local dev
)

WALLET_BACKEND_URL=os.getenv("WALLET_BACKEND_URL", "http://192.168.100.32:7003")

# Internal ledger account number that represents the anchor's fiat float
ANCHOR_BANK_ACCOUNT_NUMBER = os.getenv(
    "ANCHOR_BANK_ACCOUNT_NUMBER",
    "036176797405",  # <-- change to your real anchor account number in prod
)

# ── Core settings ─────────────────────────────────────────────────────────────
SECRET_KEY = 'django-insecure-5%7vl%1mzw1vhu@ik6*o$md-3e+4az%^25dtfsm#a1jx#1rk6m'
DEBUG = True  # Keep True for testnet development

ALLOWED_HOSTS = ['*']  # For local testnet development

# ── CORS / CSRF for testnet dev ────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://127.0.0.1:3002",
    "https://testnet.stellar.org",  # Stellar Laboratory
    "http://localhost:7013",
    "http://192.168.100.32:8001",
    "https://ee6693ae56c8.ngrok-free.app"
   
]
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8001",
    "https://testnet.stellar.org",
    "http://localhost:7013",
    "http://192.168.100.32:8001",
    "https://ee6693ae56c8.ngrok-free.app"
]
CORS_ALLOW_CREDENTIALS = True

# Allow custom headers used by the Nest backend
CORS_ALLOW_HEADERS = list(set((
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    # custom integration headers
    "idempotency-key",
    "x-actor-id",
)))

# ── Installed apps / middleware ───────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    "corsheaders",
    "rest_framework",
    'marimushaanchorapp.anchor.apps.AnchorConfig',
    "polaris",
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',   # keep CORS first
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'marimushaanchorapp.anchor.urls'

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

WSGI_APPLICATION = 'marimushaanchorapp.anchor.wsgi.application'

# ── Database ──────────────────────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME':'australiaanchor',
        'USER':'anchoraustralia_user',
        'PASSWORD':'Letmein99x!',
        'HOST':'localhost',
        'PORT':'5432',
    }
}

# Email configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.webregisteronline.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'info@webregisteronline.com'
EMAIL_HOST_PASSWORD = '12345678#'
DEFAULT_FROM_EMAIL = '"No Reply" <info@webregisteronline.com>'

# Webhook security
KYC_WEBHOOK_SECRET = os.environ.get(
    'KYC_WEBHOOK_SECRET',
    'e88756f8a55a5cd6f8e51d327c3ddd4b388b1d5005e6336e62b173d2cd42d75e'
)

# ── DRF defaults - FIXED FOR SEP ENDPOINTS ────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",  # Allow SEP endpoints without login
    ],
}

# ── Caching ─────────────────────────────────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "anchor-testnet-cache",
        "TIMEOUT": 60 * 60,  # 1 hour default
    }
}

# ── Polaris Specific Testnet Settings ─────────────────────────────────────────
POLARIS_ACTIVE_SEPS = ["sep-1", "sep-6", "sep-10", "sep-12", "sep-24", "sep-31"]
POLARIS_HOST_URL = "http://localhost:8001"  # Your testnet anchor URL
POLARIS_STELLAR_NETWORK_PASSPHRASE = "Test SDF Network ; September 2015"

# ── CRITICAL: Disable authentication for SEP endpoints ────────────────────────
POLARIS_AUTH_REQUIRED = False  # This allows SEP-10 without Django auth
POLARIS_SEP10_AUTH_REQUIRED = False

# ── i18n / tz ─────────────────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ── Static files ──────────────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
