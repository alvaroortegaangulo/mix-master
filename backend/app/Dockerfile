# Imagen base: Python 3.10 sobre Debian slim
FROM python:3.10-slim

# Evitar prompts interactivos en apt
ENV DEBIAN_FRONTEND=noninteractive

# Paquetes del sistema necesarios para audio y librerías
# - build-essential: compilar wheels si hace falta
# - libsndfile1: backend de soundfile
# - ffmpeg: utilidades de audio/vídeo
# - librubberband-dev / rubberband-cli: para pyrubberband
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

# Dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiamos el código de la app
COPY . .

# Variable por si tu código la utiliza para resolver rutas
ENV APP_PROJECT_ROOT=/app

# Puerto de FastAPI/Uvicorn
EXPOSE 8000

# Comando por defecto:
# - docker run -p 8000:8000 mix-backend
# En docker-compose se sobreescribe con "command:" para web/worker.
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
