FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLCONFIGDIR=/tmp/mplconfig \
    XDG_CACHE_HOME=/tmp/.cache \
    APP_PROJECT_ROOT=/app \
    PYTHONPATH=/app:/app/src

WORKDIR /app

# Dependencias de sistema (audio + compilación de libs Python)
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

# Requisitos Python de tu proyecto
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    # Hypercorn ASGI server (HTTP/1 + HTTP/2, opcionalmente HTTP/3)
    pip install --no-cache-dir hypercorn

# Código de la aplicación
COPY . .

# Directorios donde la app escribe (volúmenes / tmpfs)
RUN mkdir -p /app/temp /app/media /tmp/mplconfig /tmp/.cache /tmp/matplotlib && \
    chown -R app:app /app /tmp/mplconfig /tmp/.cache /tmp/matplotlib

USER app

EXPOSE 8000

# Evitar que Matplotlib cree caché en sitios raros
ENV MPLCONFIGDIR=/tmp/matplotlib

# Hypercorn en vez de uvicorn
# - 2 workers (ajústalo a tus cores si quieres)
CMD ["hypercorn", "server:app", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info"]
