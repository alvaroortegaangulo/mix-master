FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLCONFIGDIR=/tmp/mplconfig \
    XDG_CACHE_HOME=/tmp/.cache \
    APP_PROJECT_ROOT=/app \
    PYTHONPATH=/app:/app/src

# Directorio de trabajo
WORKDIR /app

# Dependencias del sistema (las que ya tenías)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libsndfile1 ffmpeg \
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

# Dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Código de la aplicación
COPY . .

# Directorios que la app necesita escribir (logs, temp, media, caches, etc.)
RUN mkdir -p /app/temp /app/media /tmp/mplconfig /tmp/.cache && \
    chown -R app:app /app /tmp/mplconfig /tmp/.cache

# A partir de aquí, todo se ejecuta como usuario 'app'
USER app

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
