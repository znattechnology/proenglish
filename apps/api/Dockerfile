# =============================================================================
# Dockerfile Otimizado para Tuwi Backend
# =============================================================================
FROM python:3.12-slim

# Metadata
LABEL maintainer="Tuwi Team"
LABEL version="1.0"
LABEL description="Tuwi Backend - English Learning Platform for Angola"

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=core.settings

WORKDIR /app

# Install system dependencies (ffmpeg: transcrição automática dos vídeos das aulas)
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create app user (non-root for security)
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app

# Create necessary directories and set permissions
# /home/appuser: o gunicorn (>= 25) cria lá o seu canal de controlo; sem ela regista um erro.
RUN mkdir -p /app/staticfiles /app/media /app/logs /home/appuser \
    && chown -R appuser:appuser /app /home/appuser

# Collect static files
RUN python manage.py collectstatic --noinput --clear

# Switch to non-root user
USER appuser

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/api/health/ || exit 1

# Expose port
EXPOSE 8000

# Production command with optimized Gunicorn settings
CMD ["gunicorn", \
     "core.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--worker-class", "gthread", \
     "--threads", "2", \
     "--timeout", "120", \
     "--keep-alive", "2", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "100", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info"]
