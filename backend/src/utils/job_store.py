import json
import redis
import os
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")

class JobStore:
    def __init__(self, redis_url: str = REDIS_URL):
        try:
            self.r = redis.from_url(redis_url)
        except Exception as e:
            logger.error(f"Failed to connect to Redis at {redis_url}: {e}")
            self.r = None

    def set_status(self, job_id: str, status: Dict[str, Any]) -> None:
        if not self.r: return
        try:
            self.r.set(f"job:{job_id}:status", json.dumps(status))
            # Set expiry to 24h to avoid clutter
            self.r.expire(f"job:{job_id}:status", 86400)
        except Exception as e:
            logger.error(f"Redis set_status error: {e}")

    def get_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        if not self.r: return None
        try:
            data = self.r.get(f"job:{job_id}:status")
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Redis get_status error: {e}")
        return None

    def save_artifact(self, job_id: str, filename: str, data: bytes) -> None:
        if not self.r: return
        try:
            self.r.hset(f"job:{job_id}:artifacts", filename, data)
            self.r.expire(f"job:{job_id}:artifacts", 86400)
        except Exception as e:
            logger.error(f"Redis save_artifact error: {e}")

    def get_artifact(self, job_id: str, filename: str) -> Optional[bytes]:
        if not self.r: return None
        try:
            return self.r.hget(f"job:{job_id}:artifacts", filename)
        except Exception as e:
            logger.error(f"Redis get_artifact error: {e}")
            return None

    def save_config(self, job_id: str, config: Dict[str, Any]) -> None:
        if not self.r: return
        try:
            self.r.set(f"job:{job_id}:config", json.dumps(config))
            self.r.expire(f"job:{job_id}:config", 86400)
        except Exception as e:
            logger.error(f"Redis save_config error: {e}")

    def get_config(self, job_id: str) -> Dict[str, Any]:
        if not self.r: return {}
        try:
            data = self.r.get(f"job:{job_id}:config")
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Redis get_config error: {e}")
        return {}
