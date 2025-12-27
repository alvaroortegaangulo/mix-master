# syntax=docker/dockerfile:1.6

FROM python:3.12-slim

# Config generales
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLCONFIGDIR=/tmp/mplconfig \
    XDG_CACHE_HOME=/tmp/.cache \
    APP_PROJECT_ROOT=/app \
    PYTHONPATH=/app:/app/src \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_PYTHON_VERSION_WARNING=1

WORKDIR /app

# Dependencias de sistema (audio + compilación) con caché APT (BuildKit)
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt/lists \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        libsndfile1 \
        ffmpeg \
        build-essential \
        libfftw3-dev \
        libavcodec-dev \
        libavformat-dev \
        libavutil-dev \
        libsamplerate0-dev \
        libtag1-dev \
        libatomic1 \
    && rm -rf /var/lib/apt/lists/*

# Usuario no root
RUN groupadd -r app && useradd -r -g app app

# Dependencias Python
# Esta capa solo se invalida si cambia requirements.txt
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install --prefer-binary -r requirements.txt && \
    pip install --prefer-binary hypercorn

# Código de la aplicación
# Esta capa solo se rehace si cambian los fuentes / config no ignorados por .dockerignore
COPY . .

# Directorios donde la app escribe (montados como volúmenes / tmpfs)
RUN mkdir -p /app/temp /app/media /tmp/mplconfig /tmp/.cache /tmp/matplotlib && \
    chown -R app:app /app /tmp/mplconfig /tmp/.cache /tmp/matplotlib

USER app

EXPOSE 8000

# Evitar que Matplotlib cree caché en sitios raros
ENV MPLCONFIGDIR=/tmp/matplotlib

# Comando por defecto: Hypercorn con 4 workers
CMD ["hypercorn", "server:app", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info"]

