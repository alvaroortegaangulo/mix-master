
import json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

def write_job_status(job_root: Path, status: Dict[str, Any]) -> None:
    """
    Atomically writes job_status.json to disk using a temporary file and os.replace.
    Ensures file permissions are 666 (rw-rw-rw-) to avoid permission issues between
    server and worker processes.
    """
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

    except Exception as e:
        logger.error(f"Failed to write job status atomic: {e}; falling back to direct write")
        try:
            status_path.parent.mkdir(parents=True, exist_ok=True)
            status_path.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")
            os.chmod(status_path, 0o666)
        except Exception as e2:
            logger.error(f"Fallback write_job_status also failed: {e2}")

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
