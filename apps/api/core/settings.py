"""
Django settings for ProEnglish Platform.

Clean backend focused on authentication system for English learning platform.
"""

import os
from pathlib import Path
from datetime import timedelta
from decouple import config, Csv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# =============================================================================
# CORE SETTINGS
# =============================================================================

# Security: SECRET_KEY must be provided via environment variable
SECRET_KEY = config('SECRET_KEY', default='django-insecure-development-only-key-change-in-production')
DEBUG = config('DEBUG', default=True, cast=bool)

# Validate SECRET_KEY in production
if not DEBUG and SECRET_KEY == 'django-insecure-development-only-key-change-in-production':
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured(
        "SECRET_KEY deve ser definido via variável de ambiente em produção. "
        "Use: python manage.py generate_secret_key"
    )
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

# =============================================================================
# APPLICATION DEFINITION
# =============================================================================

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    'channels',
]

LOCAL_APPS = [
    'apps.core',
    'apps.users',
    'apps.courses',
    'apps.practice',  # Temporarily enabled for testing - functionality moved to courses/api structure
    'apps.perfil',  # perfil de fala do aluno (níveis, banco de frases, padrões de erro)
    'apps.subscriptions',
    'apps.pagamentos',  # Pagamentos Multicaixa Express (AOA)
    'apps.cms',  # antigo: as rotas /api/v1/cms/ respondem 410
    'apps.site',  # conteúdo do site público (rascunho + publicado)
    'apps.platform_admin',  # Platform admin dashboard and management
    'apps.chatbot',  # Intelligent landing page chatbot
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # static files (admin, API docs) without nginx
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.users.middleware.JWTCookieAuthenticationMiddleware',  # JWT from HttpOnly cookies
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Vistas Django (fora do DRF) com @ratelimit(block=True): 429 em JSON (RATELIMIT_VIEW)
    'django_ratelimit.middleware.RatelimitMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# =============================================================================
# DATABASE
# =============================================================================

# Database configuration: PostgreSQL via DATABASE_URL (own server in production,
# docker-compose.dev.yml locally), SQLite as a last-resort fallback.
DATABASE_URL = config('DATABASE_URL', default='')

if DATABASE_URL:
    import dj_database_url
    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            # Reuse connections between requests instead of reconnecting every time.
            conn_max_age=config('DB_CONN_MAX_AGE', default=60, cast=int),
            conn_health_checks=True,
        )
    }
elif config('USE_POSTGRESQL', default=False, cast=bool):
    # Manual PostgreSQL configuration
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_NAME', default='proenglish_dev'),
            'USER': config('DB_USER', default='postgres'),
            'PASSWORD': config('DB_PASSWORD', default='postgres'),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5432'),
            'OPTIONS': {
                'charset': 'utf8',
            },
            'TEST': {
                'NAME': 'test_proenglish_dev',
            },
        }
    }
else:
    # SQLite for development
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# =============================================================================
# AUTHENTICATION & SECURITY
# =============================================================================

AUTH_USER_MODEL = 'users.User'

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# =============================================================================
# DJANGO REST FRAMEWORK
# =============================================================================

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FileUploadParser',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'apps.core.exceptions.custom_exception_handler',
}

# =============================================================================
# JWT SETTINGS
# =============================================================================

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,

    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,

    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',

    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',

    'JTI_CLAIM': 'jti',
}

# =============================================================================
# CORS SETTINGS
# =============================================================================

# CORS: Always use explicit origins, never allow all
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:3000,http://127.0.0.1:3000',
    cast=Csv()
)

# CSRF Settings - Add trusted origins for frontend requests
CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='http://localhost:3000,http://127.0.0.1:3000',
    cast=Csv()
)

# Additional CORS security settings
CORS_ALLOW_CREDENTIALS = True
CORS_PREFLIGHT_MAX_AGE = 86400  # 24 hours
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# WebSocket CORS settings
# SECURITY: Never enable CORS_ALLOW_ALL_ORIGINS in production
# Use CORS_ALLOWED_ORIGINS from environment variable instead
CORS_ALLOW_ALL_ORIGINS = config('CORS_ALLOW_ALL_ORIGINS', default=False, cast=bool)
CORS_ALLOW_PRIVATE_NETWORK = config('CORS_ALLOW_PRIVATE_NETWORK', default=False, cast=bool)

# =============================================================================
# COOKIE SETTINGS FOR CROSS-DOMAIN AUTHENTICATION
# =============================================================================

# For cross-domain cookies to work (Vercel frontend -> different domain backend):
# - SameSite must be 'None' to allow cross-site cookies
# - Secure must be True when SameSite is 'None' (requires HTTPS)
SESSION_COOKIE_SAMESITE = config('SESSION_COOKIE_SAMESITE', default='Lax')
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=not DEBUG, cast=bool)
CSRF_COOKIE_SAMESITE = config('CSRF_COOKIE_SAMESITE', default='Lax')
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=not DEBUG, cast=bool)

# =============================================================================
# INTERNATIONALIZATION
# =============================================================================

# Português europeu/angolano: as mensagens do Django, do DRF e do simplejwt saem em pt-PT.
# O catálogo do Django para pt-PT tem falhas e palavras do pt-BR; locale/pt_PT corrige-as
# (grafia anterior ao Acordo de 1990, como no site). Não há LocaleMiddleware: é sempre pt-PT.
LANGUAGE_CODE = 'pt-pt'
LANGUAGES = [('pt-pt', 'Português')]
LOCALE_PATHS = [BASE_DIR / 'locale']
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# =============================================================================
# STATIC & MEDIA FILES
# =============================================================================

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').is_dir() else []

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# =============================================================================
# AWS S3 CONFIGURATION
# =============================================================================

# AWS Settings
AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID', default='')
AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY', default='')
AWS_STORAGE_BUCKET_NAME = config('AWS_S3_BUCKET_NAME', default='')
AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='us-east-1')

# CloudFront Distribution (for CDN)
AWS_CLOUDFRONT_DOMAIN = config('AWS_CLOUDFRONT_DOMAIN', default='')

# S3 Settings
AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com'
AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=86400',
}
AWS_DEFAULT_ACL = 'public-read'
AWS_QUERYSTRING_AUTH = False

# Static and Media files configuration
USE_S3 = config('USE_S3', default=False, cast=bool)

if USE_S3:
    # Static files
    STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/static/'
    
    # Media files  
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'

# =============================================================================
# EMAIL SETTINGS
# =============================================================================

EMAIL_BACKEND = config(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.console.EmailBackend'
)

# SMTP Settings
EMAIL_HOST = config('EMAIL_HOST', default='localhost')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=False, cast=bool)

DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@proenglish.com')
CONTACT_EMAIL = config('CONTACT_EMAIL', default='contact@proenglish.com')

# Endereço do site (links nos emails e lista de origens aceites para pedidos com cookie)
FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:3000').rstrip('/')
# Email de apoio mostrado nos emails enviados aos alunos
SUPPORT_EMAIL = config('SUPPORT_EMAIL', default='suporte@proenglish.ao')

# Web Push (avisos do aluno). Sem as chaves, o push fica desligado
# (push.disponivel=false) e os avisos in-app continuam a funcionar.
# Gerar: ./venv/bin/python manage.py gerar_chaves_vapid
VAPID_PUBLIC_KEY = config('VAPID_PUBLIC_KEY', default='')
VAPID_PRIVATE_KEY = config('VAPID_PRIVATE_KEY', default='')
VAPID_CLAIMS_EMAIL = config('VAPID_CLAIMS_EMAIL', default='')
AVISOS_PUSH_SINCRONO = config('AVISOS_PUSH_SINCRONO', default=False, cast=bool)

# =============================================================================
# GOOGLE OAUTH SETTINGS
# =============================================================================

# Google OAuth2 configuration
GOOGLE_OAUTH2_CLIENT_ID = config('GOOGLE_OAUTH2_CLIENT_ID', default='')
GOOGLE_OAUTH2_CLIENT_SECRET = config('GOOGLE_OAUTH2_CLIENT_SECRET', default='')
GOOGLE_OAUTH2_REDIRECT_URI = config('GOOGLE_OAUTH2_REDIRECT_URI', default='http://localhost:3000/auth/google/callback')

# OAuth2 settings
OAUTH2_SETTINGS = {
    'GOOGLE': {
        'CLIENT_ID': GOOGLE_OAUTH2_CLIENT_ID,
        'CLIENT_SECRET': GOOGLE_OAUTH2_CLIENT_SECRET,
        'REDIRECT_URI': GOOGLE_OAUTH2_REDIRECT_URI,
        'SCOPE': [
            'https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/userinfo.profile',
            'openid'
        ],
        'AUTH_URI': 'https://accounts.google.com/o/oauth2/auth',
        'TOKEN_URI': 'https://oauth2.googleapis.com/token',
        'USER_INFO_URI': 'https://www.googleapis.com/oauth2/v2/userinfo',
    }
}

# =============================================================================
# LOGGING
# =============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# =============================================================================
# API DOCUMENTATION
# =============================================================================

SPECTACULAR_SETTINGS = {
    'TITLE': 'ProEnglish Platform API',
    'DESCRIPTION': '''
    API for the ProEnglish Platform - English Learning Management System.
    
    ## Features
    - 🔐 User Authentication & Authorization (JWT)
    - 👥 User Management with Student/Teacher roles
    - 📚 Course Management System
    - 📊 Progress Tracking
    - 💳 Payment Processing
    - 🔗 Google OAuth Integration
    
    ## Authentication
    This API uses JWT (JSON Web Tokens) for authentication.
    Include the token in the Authorization header: `Authorization: Bearer <your-token>`
    ''',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'CONTACT': {
        'name': 'ProEnglish Development Team',
        'email': 'dev@proenglish.com',
    },
    'LICENSE': {
        'name': 'Proprietary',
    },
    'SERVERS': [
        {
            'url': 'http://localhost:8000',
            'description': 'Development server'
        },
    ],
    'SCHEMA_PATH_PREFIX': '/api/v1/',
    'SCHEMA_PATH_PREFIX_TRIM': True,
    'SORT_OPERATIONS': True,
    'SECURITY': [
        {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT',
        }
    ],
}

# =============================================================================
# OPENAI API SETTINGS
# =============================================================================

# OpenAI (Whisper e GPT na análise de pronúncia e de traduções)
OPENAI_API_KEY = config('OPENAI_API_KEY', default='')
OPENAI_ORGANIZATION_ID = config('OPENAI_ORGANIZATION_ID', default='')

# =============================================================================
# DEFAULT FIELD SETTINGS
# =============================================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =============================================================================
# DEVELOPMENT SETTINGS
# =============================================================================

if DEBUG:
    # Allow all hosts in development (but not in production)
    ALLOWED_HOSTS = ['*']
    
    # In development, we still use explicit CORS origins for security practice
    # If you need to add development origins, update CORS_ALLOWED_ORIGINS in .env
    # Example: CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001
    pass  # Removed CORS_ALLOW_ALL_ORIGINS = True for security

# Create logs directory if it doesn't exist
os.makedirs(BASE_DIR / 'logs', exist_ok=True)

# =============================================================================
# CHANNELS & WEBSOCKET CONFIGURATION
# =============================================================================

# ASGI Configuration
ASGI_APPLICATION = 'core.asgi.application'

# Channel Layers Configuration
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [config('REDIS_URL', default='redis://localhost:6379/0')],
        },
    },
}

# =============================================================================
# VAPI INTEGRATION SETTINGS
# =============================================================================

# Vapi API Configuration
VAPI_PRIVATE_KEY = config('VAPI_PRIVATE_KEY', default=None)
VAPI_PUBLIC_KEY = config('VAPI_PUBLIC_KEY', default=None)
VAPI_ORG_ID = config('VAPI_ORG_ID', default=None)
VAPI_BASE_URL = config('VAPI_BASE_URL', default='https://api.vapi.ai')
VAPI_WEBHOOK_SECRET = config('VAPI_WEBHOOK_SECRET', default='default_webhook_secret')

# Vapi Voice Configuration
VAPI_DEFAULT_VOICE = config('VAPI_DEFAULT_VOICE', default='alloy')
VAPI_TTS_PROVIDER = config('VAPI_TTS_PROVIDER', default='openai')
VAPI_STT_PROVIDER = config('VAPI_STT_PROVIDER', default='openai')

# Vapi URLs
VAPI_WEBHOOK_URL = config('VAPI_WEBHOOK_URL', default='http://localhost:8000/api/v1/practice/vapi/webhook/')
BACKEND_BASE_URL = config('BACKEND_BASE_URL', default='http://localhost:8000')

# Default Assistant ID (create one in Vapi dashboard and put ID here)
VAPI_DEFAULT_ASSISTANT_ID = config('VAPI_DEFAULT_ASSISTANT_ID', default=None)
VAPI_ENGLISH_ASSISTANT_ID = config('VAPI_ENGLISH_ASSISTANT_ID', default=None)

# =============================================================================
# CONVERSA COM O TUTOR (api/v1/practice/conversa/)
# =============================================================================

# Modo simulado: sem chamadas Vapi nem OpenAI (tutor com guião fixo e avaliação
# determinística a partir do texto). Liga-se sozinho quando faltam as chaves Vapi.
CONVERSA_SIMULADA = config(
    'CONVERSA_SIMULADA',
    default=not (VAPI_PUBLIC_KEY and (VAPI_ENGLISH_ASSISTANT_ID or VAPI_DEFAULT_ASSISTANT_ID)),
    cast=bool,
)
# Duração máxima de uma conversa (minutos), além do que resta da quota diária.
CONVERSA_MAX_MINUTOS_SESSAO = config('CONVERSA_MAX_MINUTOS_SESSAO', default=15, cast=int)
# Modelo barato (o mesmo do chatbot) para avaliação, respostas escritas e ajustes.
# Claude (Anthropic): ajustes, respostas escritas do tutor e avaliação das conversas.
ANTHROPIC_API_KEY = config('ANTHROPIC_API_KEY', default='')
CONVERSA_CLAUDE_MODELO = config('CONVERSA_CLAUDE_MODELO', default='claude-opus-5-5')  # avaliação e respostas escritas
# Correcção em tempo real (ajuste/): um pedido por frase, por isso um modelo rápido e barato.
CONVERSA_CLAUDE_MODELO_AJUSTE = config('CONVERSA_CLAUDE_MODELO_AJUSTE', default='claude-haiku-5-5')
# Se o modelo recusar um pedido, a Anthropic repete-o noutro modelo no mesmo pedido.
CONVERSA_CLAUDE_FALLBACKS = config('CONVERSA_CLAUDE_FALLBACKS', default=True, cast=bool)
# Modelo que o Vapi usa durante a chamada de voz. Tem de estar na lista do Vapi
# (docs.vapi.ai/providers/model/anthropic); o claude-opus-5-5 ainda não está.
CONVERSA_VAPI_PROVEDOR = config('CONVERSA_VAPI_PROVEDOR', default='anthropic')
CONVERSA_VAPI_MODELO = config('CONVERSA_VAPI_MODELO', default='claude-sonnet-5')
CONVERSA_LIMITE_AJUSTE = config('CONVERSA_LIMITE_AJUSTE', default='30/min')
CONVERSA_LIMITE_RESPONDER = config('CONVERSA_LIMITE_RESPONDER', default='30/min')
CONVERSA_LIMITE_SESSOES = config('CONVERSA_LIMITE_SESSOES', default='10/hour')
# Geração de lições de prática com o Claude (área do professor) e limite diário por professor.
PRATICA_CLAUDE_MODELO = config('PRATICA_CLAUDE_MODELO', default='claude-opus-5-5')
PRATICA_GERAR_LIMITE_DIA = config('PRATICA_GERAR_LIMITE_DIA', default=30, cast=int)
# Revisão de hoje: exercícios curtos para os padrões de erro (gerados uma vez por padrão e reutilizados).
REVISAO_CLAUDE_MODELO = config('REVISAO_CLAUDE_MODELO', default='claude-haiku-5-5')
# Exercício "Responder" (resposta livre em voz alta): um pedido curto por gravação, modelo rápido.
RESPONDER_CLAUDE_MODELO = config('RESPONDER_CLAUDE_MODELO', default='claude-haiku-5-5')
# Conversa curta no fim de uma lição (exercício VAPI_CONVERSATION): duração máxima em segundos.
CONVERSA_LICAO_MAX_SEGUNDOS = config('CONVERSA_LICAO_MAX_SEGUNDOS', default=120, cast=int)
# Conversa de 3 minutos no fim de uma aula em vídeo ("Usar isto numa conversa").
CONVERSA_AULA_MAX_SEGUNDOS = config('CONVERSA_AULA_MAX_SEGUNDOS', default=180, cast=int)
# Fase 6: teste de nível falado (primeira entrada) e exame oral do curso. Fora da quota diária.
CONVERSA_DIAGNOSTICO_MAX_SEGUNDOS = config('CONVERSA_DIAGNOSTICO_MAX_SEGUNDOS', default=240, cast=int)
CONVERSA_EXAME_MAX_SEGUNDOS = config('CONVERSA_EXAME_MAX_SEGUNDOS', default=600, cast=int)
# Aulas em vídeo: transcrição automática (ffmpeg + Whisper) quando o professor carrega o vídeo,
# e frases da aula propostas pelo Claude. TRANSCRICAO_AUTOMATICA=False: só o comando
# transcrever_aulas (cron) ou o botão do professor transcrevem.
TRANSCRICAO_AUTOMATICA = config('TRANSCRICAO_AUTOMATICA', default=True, cast=bool)
TRANSCRICAO_MODELO = config('TRANSCRICAO_MODELO', default='whisper-1')
TRANSCRICAO_MAX_BYTES = config('TRANSCRICAO_MAX_BYTES', default=2200 * 1024 * 1024, cast=int)  # vídeo descarregado
TRANSCRICAO_PEDACO_SEGUNDOS = config('TRANSCRICAO_PEDACO_SEGUNDOS', default=600, cast=int)  # 10 min (~2.4 MB a 32 kb/s)
FFMPEG_BIN = config('FFMPEG_BIN', default='ffmpeg')
FFPROBE_BIN = config('FFPROBE_BIN', default='ffprobe')
FRASES_AULA_CLAUDE_MODELO = config('FRASES_AULA_CLAUDE_MODELO', default='claude-opus-5-5')
# Nota: os limites acima (e os throttles/ratelimits) usam a cache 'default' (ver CACHES).

# =============================================================================
# PAGAMENTOS (Multicaixa Express, AOA)
# =============================================================================

# Provedor usado para novos pagamentos: "simulado" (MulticaixaSimulado) ou
# "emis" (MulticaixaEMIS - ainda não implementado, aguarda acordo com a EMIS).
PAGAMENTOS_PROVEDOR = config('PAGAMENTOS_PROVEDOR', default='simulado')

# Permite o provedor simulado e o endpoint POST pagamentos/<id>/simular/.
# Por omissão só fica ativo com DEBUG=True. NUNCA ativar em produção: com o
# simulador qualquer número de telefone "paga" ao fim de 6 segundos.
PAGAMENTOS_SIMULADOS = config('PAGAMENTOS_SIMULADOS', default=DEBUG, cast=bool)

# Análise de pronúncia simulada: só em desenvolvimento e quando não há chave real da OpenAI.
# Nunca ligar em produção (dava pontos sem ouvir a pessoa).
PRONUNCIA_SIMULADA = config(
    'PRONUNCIA_SIMULADA',
    default=DEBUG and (not OPENAI_API_KEY or OPENAI_API_KEY in ('dummy', 'sk-dummy')),
    cast=bool,
)

# Limite de criação de pagamentos por utilizador (formato DRF, ex.: "10/min").
PAGAMENTOS_LIMITE_CRIACAO = config('PAGAMENTOS_LIMITE_CRIACAO', default='10/min')

# Ganhos dos professores (apps/pagamentos/ganhos.py): esta percentagem da receita de
# subscrições confirmada no mês é dividida pelos professores segundo o tempo que os
# alunos com plano pago passaram nos seus cursos; paga no dia GANHOS_DIA_PAGAMENTO do mês seguinte.
GANHOS_PERCENTAGEM_PROFESSORES = config('GANHOS_PERCENTAGEM_PROFESSORES', default=30, cast=int)
GANHOS_DIA_PAGAMENTO = config('GANHOS_DIA_PAGAMENTO', default=5, cast=int)
# Tempo estimado por resposta num exercício de prática (não há tempo medido por exercício).
GANHOS_SEGUNDOS_POR_EXERCICIO = config('GANHOS_SEGUNDOS_POR_EXERCICIO', default=20, cast=int)
# Cada exercício conta uma vez por aluno e dia; por aluno e dia (somando os professores) conta
# no máximo este tempo de prática e de vídeo. Acima do limite, reparte-se em proporção.
GANHOS_MAX_PRATICA_SEGUNDOS_DIA = config('GANHOS_MAX_PRATICA_SEGUNDOS_DIA', default=3600, cast=int)
GANHOS_MAX_VIDEO_SEGUNDOS_DIA = config('GANHOS_MAX_VIDEO_SEGUNDOS_DIA', default=4 * 3600, cast=int)

# =============================================================================
# CACHE E LIMITES DE PEDIDOS
# =============================================================================

# Os limites de pedidos (django_ratelimit e throttles do DRF) contam na cache 'default'.
# Com REDIS_URL (ex.: redis://redis:6379/1) a contagem é partilhada por todos os workers e
# instâncias; sem ela fica em memória, por processo (serve para desenvolvimento).
REDIS_URL = config('REDIS_URL', default='')
if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
            'KEY_PREFIX': config('CACHE_KEY_PREFIX', default='proenglish'),
            'TIMEOUT': 300,
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'proenglish-default',
        }
    }

# Atrás de um proxy (nginx), REMOTE_ADDR é o IP do proxy. Com TRUSTED_PROXY=True os limites
# usam X-Real-IP (ou a entrada TRUSTED_PROXY_COUNT a contar do fim de X-Forwarded-For).
# Só ligar quando há mesmo um proxy à frente: sem ele, o cliente podia inventar o IP.
TRUSTED_PROXY = config('TRUSTED_PROXY', default=False, cast=bool)
TRUSTED_PROXY_COUNT = config('TRUSTED_PROXY_COUNT', default=1, cast=int)
RATELIMIT_IP_META_KEY = 'apps.core.ip.ip_do_cliente'
# django_ratelimit com block=True devolve 429 (e não 403) através de apps.core.exceptions.
RATELIMIT_VIEW = 'apps.core.exceptions.ratelimit_view'

# Pedidos que alteram dados autenticados pelo cookie access_token só são aceites se vierem
# destas origens (defesa contra CSRF: em produção os cookies são SameSite=None).
# Por omissão: CORS_ALLOWED_ORIGINS + FRONTEND_URL.
COOKIE_AUTH_ALLOWED_ORIGINS = config('COOKIE_AUTH_ALLOWED_ORIGINS', default='', cast=Csv())
