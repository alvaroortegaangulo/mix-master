# C:\mix-master\backend\celery_app.py

from __future__ import annotations

import os
from celery import Celery

BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", BROKER_URL)

celery_app = Celery(
    "mix_master",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=["tasks"],  # registra tasks.py
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Madrid",
    enable_utc=True,
    task_track_started=True,
)
