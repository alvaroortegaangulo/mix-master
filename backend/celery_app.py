from __future__ import annotations

import os
import logging
from celery import Celery

# ---------------------------------------------------------------------------
# Config básica de broker / backend
# ---------------------------------------------------------------------------

BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", BROKER_URL)

# Configuración básica de logging (si el root logger no tiene handlers).
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

logger = logging.getLogger("mix_master.celery_app")

logger.info(
    "Inicializando Celery. broker=%s backend=%s",
    BROKER_URL,
    RESULT_BACKEND,
)

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

celery_app.autodiscover_tasks(["tasks"])

logger.info("Celery configurado y tasks autodiscover ejecutado.")
