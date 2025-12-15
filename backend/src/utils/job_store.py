
import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

def update_job_status(job_root: Path, status_update: Dict[str, Any]) -> None:
    """
    Helper to update job_status.json in a race-safe(ish) way.
    Reads existing, updates fields, writes back.
    """
    try:
        status_path = job_root / "job_status.json"
        if not status_path.exists():
            return

        with open(status_path, "r", encoding="utf-8") as f:
            current = json.load(f)

        current.update(status_update)

        with open(status_path, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Failed to update job status: {e}")
