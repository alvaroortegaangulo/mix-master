import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict

PROGRESS_REDIS_URL = os.environ.get(
    "PROGRESS_REDIS_URL",
    os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0"),
)
PROGRESS_REDIS_PREFIX = os.environ.get("PROGRESS_REDIS_PREFIX", "job-progress:")

_redis_client = None

logger = logging.getLogger(__name__)


def progress_channel_name(job_id: str) -> str:
    """
    Devuelve el nombre de canal Pub/Sub para progreso en tiempo real.
    """
    clean = (job_id or "").strip()
    return f"{PROGRESS_REDIS_PREFIX}{clean}"


def _get_redis_client():
    """
    Obtiene (y cachea) un cliente Redis sincrono para publicar progreso.
    Silencia errores para no romper el flujo de escritura.
    """
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    redis_url = PROGRESS_REDIS_URL
    if not redis_url:
        return None

    try:
        import redis

        _redis_client = redis.Redis.from_url(redis_url)
        return _redis_client
    except Exception as exc:  # pragma: no cover - fallo no critico
        logger.debug("No se pudo inicializar Redis para progreso: %s", exc)
        _redis_client = None
        return None


def _publish_progress(job_root: Path, status: Dict[str, Any]) -> None:
    """
    Publica el estado en Redis Pub/Sub para que el servidor lo reenvie por WebSocket.
    Best-effort: si Redis no esta disponible, no interfiere con la escritura.
    """
    client = _get_redis_client()
    if not client:
        return

    job_id = str(status.get("jobId") or status.get("job_id") or job_root.name)
    if not job_id:
        return

    channel = progress_channel_name(job_id)
    envelope = {
        "type": "job_status",
        "jobId": job_id,
        "payload": status,
        "ts": time.time(),
    }

    try:
        client.publish(channel, json.dumps(envelope))
    except Exception as exc:  # pragma: no cover - envio best-effort
        logger.debug("No se pudo publicar progreso en Redis (%s): %s", channel, exc)


def write_job_status(job_root: Path, status: Dict[str, Any]) -> None:
    """
    Atomically writes job_status.json to disk using a temporary file and os.replace.
    Ensures file permissions are 666 (rw-rw-rw-) to avoid permission issues between
    server and worker processes.
    """
    write_ok = False
    try:
        if not job_root.exists():
            job_root.mkdir(parents=True, exist_ok=True)

        status_path = job_root / "job_status.json"

        # Create temp file in the same directory to ensure atomic move works
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile("w", dir=job_root, delete=False, encoding="utf-8") as tmp_file:
                json.dump(status, tmp_file, indent=2, ensure_ascii=False)
                tmp_path = Path(tmp_file.name)

            # Set permissions to rw-rw-rw- before moving
            os.chmod(tmp_path, 0o666)

            # Atomic replace
            os.replace(tmp_path, status_path)
        finally:
            # Ensure final file also has correct permissions
            if status_path.exists():
                try:
                    os.chmod(status_path, 0o666)
                except Exception:
                    pass
            # Cleanup tmp if left behind
            try:
                if tmp_path and tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass
        write_ok = True

    except Exception as e:
        logger.error(f"Failed to write job status atomic: {e}; falling back to direct write")
        try:
            status_path.parent.mkdir(parents=True, exist_ok=True)
            status_path.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")
            os.chmod(status_path, 0o666)
            write_ok = True
        except Exception as e2:
            logger.error(f"Fallback write_job_status also failed: {e2}")

    if write_ok:
        _publish_progress(job_root, status)


def update_job_status(job_root: Path, status_update: Dict[str, Any]) -> None:
    """
    Helper to update job_status.json in a race-safe(ish) way.
    Reads existing, updates fields, writes back using atomic write.
    """
    try:
        status_path = job_root / "job_status.json"
        current = {}

        if status_path.exists():
            try:
                with open(status_path, "r", encoding="utf-8") as f:
                    current = json.load(f)
            except Exception as e:
                logger.warning(f"Could not read existing job_status.json, starting fresh: {e}")
                current = {}

        current.update(status_update)
        write_job_status(job_root, current)

    except Exception as e:
        logger.error(f"Failed to update job status: {e}")


def set_share_token(token: str, job_id: str, ttl_seconds: int = 7 * 24 * 3600) -> bool:
    """
    Stores a share token mapping to a job_id in Redis with an expiration.
    """
    client = _get_redis_client()
    if not client:
        return False
    try:
        key = f"share_token:{token}"
        client.setex(key, ttl_seconds, job_id)
        return True
    except Exception as e:
        logger.error(f"Failed to set share token: {e}")
        return False


def get_job_id_from_share_token(token: str) -> str | None:
    """
    Retrieves the job_id associated with a share token.
    """
    client = _get_redis_client()
    if not client:
        return None
    try:
        key = f"share_token:{token}"
        job_id = client.get(key)
        if job_id:
            if isinstance(job_id, bytes):
                return job_id.decode("utf-8")
            return str(job_id)
        return None
    except Exception as e:
        logger.error(f"Failed to get share token: {e}")
        return None
