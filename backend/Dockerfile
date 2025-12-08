FROM python:3.10-slim

# Config generales
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLCONFIGDIR=/tmp/mplconfig \
    XDG_CACHE_HOME=/tmp/.cache \
    APP_PROJECT_ROOT=/app \
    PYTHONPATH=/app:/app/src

WORKDIR /app

# Dependencias de sistema (audio + compilación)
RUN apt-get update && \
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
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install hypercorn

# Código de la aplicación
COPY . .

# Directorios donde la app escribe (montados como volúmenes / tmpfs)
RUN mkdir -p /app/temp /app/media /tmp/mplconfig /tmp/.cache /tmp/matplotlib && \
    chown -R app:app /app /tmp/mplconfig /tmp/.cache /tmp/matplotlib

USER app

EXPOSE 8000

# Evitar que Matplotlib cree caché en sitios raros
ENV MPLCONFIGDIR=/tmp/matplotlib

# Comando por defecto: Hypercorn con 2 workers (puedes subirlo si tu VPS lo aguanta)
CMD ["hypercorn", "server:app", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info"]
