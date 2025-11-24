#!/usr/bin/env bash
set -e

celery -A celery_app.celery_app worker --loglevel=info --concurrency=1 --pool=solo &

uvicorn server:app --host 0.0.0.0 --port "$PORT"