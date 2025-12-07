from __future__ import annotations

import os
import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any

from celery import states
from celery_app import celery_app
from src.utils.job_store import JobStore

logger = logging.getLogger("mix_master.tasks")

# -------------------------------------------------------------------
# Helpers de imports perezosos
# -------------------------------------------------------------------

def _import_pipeline():
    from src.pipeline import run_pipeline_for_job
    return run_pipeline_for_job

# -------------------------------------------------------------------
# Tarea Celery
# -------------------------------------------------------------------

@celery_app.task(bind=True, name="run_full_pipeline_task")
def run_full_pipeline_task(
    self,
    job_id: str,
    media_dir: str,
    enabled_stage_keys: Optional[List[str]] = None,
    profiles_by_name: Optional[Dict[str, str]] = None,
    upload_mode: Optional[Dict[str, Any]] = None,
    space_depth_bus_styles: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Tarea Celery que ejecuta el pipeline completo para un job concreto.
    """
    start_ts = time.time()
    job_store = JobStore()

    logger.info(
        ">>> run_full_pipeline_task recibido en worker. job_id=%s celery_id=%s media_dir=%s",
        job_id,
        getattr(self.request, "id", None),
        media_dir,
    )

    run_pipeline_for_job = _import_pipeline()

    # We remove temp_root usage from environment to force in-memory
    os.environ["MIX_JOB_ID"] = job_id
    os.environ["MIX_MEDIA_DIR"] = media_dir
    if "MIX_TEMP_ROOT" in os.environ:
        del os.environ["MIX_TEMP_ROOT"]

    media_dir_path = Path(media_dir)

    progress_state: Dict[str, Any] = {
        "stage_index": 0,
        "total_stages": 0,
        "stage_key": "initializing",
        "message": "Inicializando pipeline...",
    }

    initial_status = {
        "jobId": job_id,
        "job_id": job_id,
        "status": "running",
        "stage_index": 0,
        "total_stages": 0,
        "stage_key": "initializing",
        "message": "Inicializando pipeline de mezcla...",
        "progress": 0.0,
    }
    job_store.set_status(job_id, initial_status)

    def progress_cb(
        stage_index: int,
        total_stages: int,
        stage_key: str,
        message: str,
    ) -> None:
        progress_state["stage_index"] = stage_index
        progress_state["total_stages"] = total_stages
        progress_state["stage_key"] = stage_key
        progress_state["message"] = message

        if total_stages <= 0:
            progress_val = 0.0
        else:
            progress_val = float(stage_index) / float(total_stages) * 100.0

        meta = {
            "jobId": job_id,
            "stage_index": stage_index,
            "total_stages": total_stages,
            "stage_key": stage_key,
            "message": message,
            "progress": progress_val,
        }

        self.update_state(state="PROGRESS", meta=meta)

        status = {
            "jobId": job_id,
            "job_id": job_id,
            "status": "running",
            "stage_index": stage_index,
            "total_stages": total_stages,
            "stage_key": stage_key,
            "message": message,
            "progress": progress_val,
        }
        job_store.set_status(job_id, status)

        logger.info(
            "[%s] Progreso: %d/%d (%.1f%%) stage_key=%s",
            job_id,
            stage_index,
            total_stages,
            progress_val,
            stage_key,
        )

    # ---------------------------
    # 1) Ejecutar pipeline
    # ---------------------------
    try:
        logger.info(
            "[%s] Llamando a run_pipeline_for_job",
            job_id,
        )
        t0 = time.time()

        # We pass metadata
        metadata = {
            "upload_mode": upload_mode or {},
            "space_depth_bus_styles": space_depth_bus_styles or {},
            "profiles_by_name": profiles_by_name or {}
        }

        context = run_pipeline_for_job(
            job_id=job_id,
            media_dir=media_dir_path,
            enabled_stage_keys=enabled_stage_keys,
            metadata=metadata,
            progress_cb=progress_cb,
        )

        t1 = time.time()
        logger.info(
            "[%s] run_pipeline_for_job terminado en %.1fs",
            job_id,
            t1 - t0,
        )
    except Exception as exc:
        logger.exception(
            "[%s] ERROR en run_pipeline_for_job",
            job_id,
        )
        self.update_state(
            state=states.FAILURE,
            meta={
                "jobId": job_id,
                "exc_type": type(exc).__name__,
                "exc_message": str(exc),
                "exc_module": exc.__class__.__module__,
            },
        )

        error_status = {
            "jobId": job_id,
            "job_id": job_id,
            "status": "failure",
            "message": f"Error en pipeline: {exc}",
            "error": str(exc),
        }
        job_store.set_status(job_id, error_status)
        raise

    logger.info(
        "[%s] Pipeline finalizado correctamente.",
        job_id,
    )

    # ---------------------------
    # 2) Guardar artefactos y métricas
    # ---------------------------
    if context.report:
        job_store.save_artifact(job_id, "report.json", json.dumps(context.report).encode('utf-8'))

    for filename, data in context.generated_artifacts.items():
        job_store.save_artifact(job_id, filename, data)

    metrics = {}
    if context.report and "metrics" in context.report:
        metrics = context.report["metrics"]

    # Construct final status
    total_stages = int(progress_state.get("total_stages", 0))
    stage_index = int(progress_state.get("stage_index", total_stages))

    # We no longer provide file URLs pointing to temp/files.
    # The frontend should fetch report/images via API.
    # If frontend uses legacy fields, we might need to fake them or update frontend (out of scope, but we should provide dynamic urls if possible).
    # Since we use dynamic endpoints, we can provide URLs like /jobs/{jobId}/artifacts/full_song.wav (if we served audio).
    # But for now we only handle report artifacts.

    final_status = {
        "jobId": job_id,
        "job_id": job_id,
        "status": "success",
        "message": "Mix pipeline finished successfully.",
        "stage_index": stage_index,
        "total_stages": total_stages,
        "stage_key": "finished",
        "progress": 100.0,
        "metrics": metrics,
        "bus_styles": space_depth_bus_styles or {},
    }

    job_store.set_status(job_id, final_status)

    return final_status
