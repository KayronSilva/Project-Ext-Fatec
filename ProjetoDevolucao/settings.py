"""
Django settings for ProjetoDevolucao project.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / '.env')
except ImportError:
    pass

SECRET_KEY = os.getenv(
    'SECRET_KEY',
    'django-insecure-desenvolvimento-apenas-mudar-em-producao'
)

DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')


# ─── APPS ────────────────────────────────────────────────────
# FIX PERF: whitenoise.runserver_nostatic ANTES de staticfiles
# impede o Django de servir estáticos em dev (WhiteNoise assume o controle)
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',   # ← NOVO (antes de staticfiles)
    'django.contrib.staticfiles',
    'devolucao',
]

# ─── MIDDLEWARE ───────────────────────────────────────────────
# FIX PERF: WhiteNoiseMiddleware logo após SecurityMiddleware
# serve estáticos com gzip/brotli + cache longo (hash no nome)
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',               # ← NOVO
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ProjetoDevolucao.urls'

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

WSGI_APPLICATION = 'ProjetoDevolucao.wsgi.application'


# ─── BANCO DE DADOS ───────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'devolucao',
        'USER': 'root',
        'PASSWORD': '0193485266',
        'HOST': 'localhost',
        'PORT': '3306',
    }
}


# ─── VALIDAÇÃO DE SENHA ───────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ─── INTERNACIONALIZAÇÃO ──────────────────────────────────────
LANGUAGE_CODE = 'pt-br'
TIME_ZONE     = 'America/Cuiaba'
USE_I18N      = True
USE_TZ        = True


# ─── ARQUIVOS ESTÁTICOS ───────────────────────────────────────
STATIC_URL  = 'static/'

# FIX PERF: STATIC_ROOT é obrigatório para collectstatic + WhiteNoise
STATIC_ROOT = BASE_DIR / 'staticfiles'

# FIX PERF: CompressedManifestStaticFilesStorage faz duas coisas:
#   1. Adiciona hash ao nome do arquivo (ex: style.abc123.css)
#      → o browser pode cachear por 1 ano sem medo de cache stale
#   2. Comprime com gzip/brotli automaticamente
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# ─── ARQUIVOS DE MÍDIA ────────────────────────────────────────
MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'uploads'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ─── AUTENTICAÇÃO ─────────────────────────────────────────────
AUTH_USER_MODEL    = 'devolucao.Usuario'
LOGIN_URL          = '/login/'
LOGIN_REDIRECT_URL = '/'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]


# ─── LOGGING ──────────────────────────────────────────────────
import logging.handlers

os.makedirs(BASE_DIR / 'logs', exist_ok=True)

try:
    import structlog
    STRUCTLOG_AVAILABLE = True
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.render_to_log_kwargs,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
except ImportError:
    STRUCTLOG_AVAILABLE = False

if STRUCTLOG_AVAILABLE:
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'json': {
                '()': structlog.stdlib.ProcessorFormatter,
                'processor': structlog.processors.JSONRenderer(),
            },
            'standard': {'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'},
        },
        'handlers': {
            'console':    {'class': 'logging.StreamHandler',              'formatter': 'standard', 'level': 'INFO'},
            'file':       {'level': 'INFO',  'class': 'logging.handlers.RotatingFileHandler', 'filename': BASE_DIR / 'logs' / 'app.log',    'maxBytes': 10485760, 'backupCount': 5,  'formatter': 'json'},
            'error_file': {'level': 'ERROR', 'class': 'logging.handlers.RotatingFileHandler', 'filename': BASE_DIR / 'logs' / 'errors.log', 'maxBytes': 10485760, 'backupCount': 10, 'formatter': 'json'},
        },
        'loggers': {
            'devolucao': {'handlers': ['console', 'file', 'error_file'], 'level': 'INFO', 'propagate': False},
        },
        'root': {'handlers': ['console', 'file'], 'level': 'WARNING'},
    }
else:
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'},
        },
        'handlers': {
            'console': {'class': 'logging.StreamHandler', 'formatter': 'standard', 'level': 'INFO'},
            'file':    {'level': 'INFO', 'class': 'logging.handlers.RotatingFileHandler', 'filename': BASE_DIR / 'logs' / 'app.log', 'maxBytes': 10485760, 'backupCount': 5, 'formatter': 'standard'},
        },
        'loggers': {
            'devolucao': {'handlers': ['console', 'file'], 'level': 'INFO', 'propagate': False},
        },
        'root': {'handlers': ['console'], 'level': 'WARNING'},
    }