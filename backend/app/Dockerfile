# Imagen base: Python 3.10 sobre Debian slim (ligera y suficiente para wheels manylinux)
FROM python:3.10-slim

# Evitamos preguntas en apt
ENV DEBIAN_FRONTEND=noninteractive

# Paquetes del sistema:
# - build-essential: para compilar algún paquete de pip si lo necesita
# - libsndfile1: backend de soundfile
# - ffmpeg: utilidades de audio/vídeo
# - librubberband-dev: librería compartida Rubber Band
# - rubberband-cli: ejecutable 'rubberband' que usa pyrubberband
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libsndfile1 \
        ffmpeg \
        librubberband-dev \
        rubberband-cli \
    && rm -rf /var/lib/apt/lists/*

# Directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiamos únicamente requirements primero (para cachear instalación de deps)
COPY requirements.txt .

# Mejoramos pip y instalamos dependencias Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Ahora copiamos el resto del proyecto
# (main.py, src/, etc.)
COPY . .

RUN chmod +x start.sh
CMD ["./start.sh"]

# Variable para que tu módulo config.paths resuelva rutas correctamente
ENV APP_PROJECT_ROOT=/app

# Comando por defecto: lanzar API FastAPI
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
