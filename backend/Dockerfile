FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Dependencias del sistema (las que ya tenías)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libfftw3-dev \
        libavcodec-dev \
        libavformat-dev \
        libavutil-dev \
        libsamplerate0-dev \
        libtag1-dev \
        libsndfile1 \
        libatomic1 \
    && rm -rf /var/lib/apt/lists/*

# Directorio de trabajo
WORKDIR /app

# Usuario no root
RUN groupadd -r app && useradd -r -g app app

# Dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Código
COPY . .

ENV APP_PROJECT_ROOT=/app \
    PYTHONPATH=/app/src

# Directorios que la app necesita escribir (logs, temp, etc.)
RUN mkdir -p /app/temp && chown -R app:app /app

# A partir de aquí, todo se ejecuta como usuario 'app'
USER app

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]

