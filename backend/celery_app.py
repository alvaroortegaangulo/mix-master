# C:\mix-master\backend\celery_app.py

from __future__ import annotations

import os
from celery import Celery

# ---------------------------------------------------------------------------
# Config básica de broker / backend
# ---------------------------------------------------------------------------

BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", BROKER_URL)

celery_app = Celery(
    "mix_master",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
)

# ---------------------------------------------------------------------------
# Configuración de Celery
# ---------------------------------------------------------------------------

celery_app.conf.update(
    # Serialización
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Zona horaria
    timezone="Europe/Madrid",
    enable_utc=True,

    # Tracking de estados
    task_track_started=True,

    # No quedarnos 30+ minutos reintentando si el broker no está listo.
    # Si no puede conectar al arrancar, peta rápido y Docker lo reinicia.
    broker_connection_retry_on_startup=False,

    # Heartbeat to detect lost connections (importante en entornos con desconexiones)
    broker_heartbeat=10,

    # Ajustar reintentos de transporte (cuando pierde el broker en caliente)
    broker_transport_options={
        "max_retries": 5,
        "interval_start": 0,
        "interval_step": 2,
        "interval_max": 10,
        # Timeouts para evitar hangs si la red/DNS fallan
        "socket_timeout": 30,
        "socket_connect_timeout": 30,
    },

    # Para que no acapare demasiadas tareas por proceso
    worker_prefetch_multiplier=1,

    # Si una tarea peta, que el mensaje no se pierda
    task_acks_late=True,
)

# ---------------------------------------------------------------------------
# Registro de tasks
# ---------------------------------------------------------------------------
# Tus tareas están en tasks.py en la raíz del backend.
# Esto equivale a include=["tasks"], pero es un poco más explícito y extensible.
celery_app.autodiscover_tasks(["tasks"])
