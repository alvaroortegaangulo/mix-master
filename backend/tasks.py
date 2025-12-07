from __future__ import annotations

import os
import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any

from celery import states
from celery_app import celery_app


logger = logging.getLogger("mix_master.tasks")


# -------------------------------------------------------------------
# Helpers de imports perezosos (por si son pesados)
# -------------------------------------------------------------------


def _import_pipeline():
    """
    Import diferido para evitar cargar el pipeline en el arranque del worker,
    por si el import es pesado.
    """
    from src.pipeline import run_pipeline_for_job
    return run_pipeline_for_job


def _import_analysis_utils():
    """
    Import diferido de funciones de análisis (matrices, audio, etc.).
    """
    from src.utils.analysis_utils import (
        get_temp_dir,
        load_audio_mono,
        compute_peak_dbfs,
        compute_integrated_loudness_lufs,
    )
    return get_temp_dir, load_audio_mono, compute_peak_dbfs, compute_integrated_loudness_lufs


# -------------------------------------------------------------------
# Helpers de métricas finales
# -------------------------------------------------------------------


def _safe_compute_final_metrics(job_id: str) -> Dict[str, Any]:
    """
    Calcula un bloque mínimo de métricas finales para el frontend.

    - Lee el full_song de S10_MASTER_FINAL_LIMITS (si existe).
    - Lee análisis de S1_KEY_DETECTION (si existe).
    - El resto de campos se devuelven con valores neutros.

    Devuelve un dict con la forma de MixMetrics.
    """
    get_temp_dir, load_audio_mono, compute_peak_dbfs, compute_integrated_loudness_lufs = _import_analysis_utils()

    # Defaults neutros
    final_peak_dbfs = 0.0
    final_rms_dbfs = 0.0

    tempo_bpm = 0.0
    tempo_confidence = 0.0

    key_name = ""
    key_mode = ""
    key_strength = 0.0

    vocal_shift_min = 0.0
    vocal_shift_max = 0.0
    vocal_shift_mean = 0.0

    # -----------------------------
    # 1) Métricas a partir del máster final (S10_MASTER_FINAL_LIMITS)
    # -----------------------------
    try:
        contract_id = "S10_MASTER_FINAL_LIMITS"
        master_dir = get_temp_dir(contract_id, create=False)
        master_path = master_dir / "full_song.wav"
        if master_path.exists():
            mono, sr = load_audio_mono(master_path)
            final_peak_dbfs = compute_peak_dbfs(mono)
            final_rms_dbfs = compute_integrated_loudness_lufs(mono, sr)
        else:
            logger.warning(
                "[%s] No se ha encontrado máster final en %s",
                job_id,
                master_path,
            )
    except Exception:
        logger.exception(
            "[%s] Error calculando métricas de máster final",
            job_id,
        )

    # -----------------------------
    # 2) Key detection (S1_KEY_DETECTION)
    # -----------------------------
    try:
        contract_id = "S1_KEY_DETECTION"
        key_dir = get_temp_dir(contract_id, create=False)
        key_json = key_dir / f"analysis_{contract_id}.json"
        if key_json.exists():
            with key_json.open("r", encoding="utf-8") as f:
                data = json.load(f)
            session = data.get("session", {}) or {}
            key_name = str(session.get("key_name") or "")
            key_mode = str(session.get("key_mode") or "")
            key_strength = float(session.get("key_detection_confidence", 0.0) or 0.0)
        else:
            logger.warning(
                "[%s] No se ha encontrado analysis_%s.json",
                job_id,
                contract_id,
            )
    except Exception:
        logger.exception(
        "[%s] Error leyendo análisis de key detection",
            job_id,
        )

    # (3) Tempo y shifts vocales: de momento neutros.

    logger.info(
        "[%s] Métricas finales: peak_dbfs=%.2f rms_dbfs=%.2f tempo_bpm=%.2f key=%s mode=%s key_strength=%.3f",
        job_id,
        final_peak_dbfs,
        final_rms_dbfs,
        tempo_bpm,
        key_name,
        key_mode,
        key_strength,
    )

    return {
        "final_peak_dbfs": final_peak_dbfs,
        "final_rms_dbfs": final_rms_dbfs,
        "tempo_bpm": tempo_bpm,
        "tempo_confidence": tempo_confidence,
        "key": key_name,
        "scale": key_mode,
        "key_strength": key_strength,
        "vocal_shift_min": vocal_shift_min,
        "vocal_shift_max": vocal_shift_max,
        "vocal_shift_mean": vocal_shift_mean,
    }


def _make_files_url(job_root: Path, job_id: str, path: Path | None) -> str:
    """
    Convierte una ruta absoluta dentro de job_root en una URL relativa
    para el endpoint /files.

    Si path es None o no cuelga de job_root, devuelve "".
    """
    if path is None:
        return ""

    try:
        rel = path.relative_to(job_root)
    except ValueError:
        logger.warning(
            "[%s] _make_files_url: path %s no cuelga de job_root %s",
            job_id,
            path,
            job_root,
        )
        return ""

    return f"/files/{job_id}/{rel.as_posix()}"


def _locate_original_and_master_paths(job_id: str) -> tuple[Path | None, Path | None]:
    """
    Intenta localizar:
      - original_mix_path: full_song de S0_MIX_ORIGINAL
      - master_path: full_song de S10_MASTER_FINAL_LIMITS
    """
    get_temp_dir, *_ = _import_analysis_utils()

    original_path: Path | None = None
    master_path: Path | None = None

    try:
        s0_dir = get_temp_dir("S0_MIX_ORIGINAL", create=False)
        cand = s0_dir / "full_song.wav"
        if cand.exists():
            original_path = cand
            logger.info(
                "[%s] Original mix localizado en %s",
                job_id,
                cand,
            )
        else:
            logger.warning(
                "[%s] No se encuentra original full_song.wav en %s",
                job_id,
                cand,
            )
    except Exception:
        logger.exception(
            "[%s] Error localizando original full_song.wav",
            job_id,
        )

    try:
        s10_dir = get_temp_dir("S10_MASTER_FINAL_LIMITS", create=False)
        cand = s10_dir / "full_song.wav"
        if cand.exists():
            master_path = cand
            logger.info(
                "[%s] Máster localizado en %s",
                job_id,
                cand,
            )
        else:
            logger.warning(
                "[%s] No se encuentra máster full_song.wav en %s",
                job_id,
                cand,
            )
    except Exception:
        logger.exception(
            "[%s] Error localizando máster full_song.wav",
            job_id,
        )

    return original_path, master_path


def _write_job_status(job_root: Path, status: Dict[str, Any]) -> None:
    """
    Escribe temp/<job_id>/job_status.json con el estado actual del job.
    """
    try:
        status_path = job_root / "job_status.json"
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text(
            json.dumps(status, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        job_id = status.get("jobId") or status.get("job_id")
        logger.info(
            "[%s] job_status.json actualizado: %s",
            job_id,
            status_path,
        )
    except Exception:
        job_id = status.get("jobId") or status.get("job_id")
        logger.exception(
            "[%s] No se pudo escribir job_status.json",
            job_id,
        )


# -------------------------------------------------------------------
# Tarea Celery
# -------------------------------------------------------------------


@celery_app.task(bind=True, name="run_full_pipeline_task")
def run_full_pipeline_task(
    self,
    job_id: str,
    media_dir: str,
    temp_root: str,
    enabled_stage_keys: Optional[List[str]] = None,
    profiles_by_name: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Tarea Celery que ejecuta el pipeline completo para un job concreto.
    """
    start_ts = time.time()
    logger.info(
        ">>> run_full_pipeline_task recibido en worker. job_id=%s celery_id=%s media_dir=%s temp_root=%s",
        job_id,
        getattr(self.request, "id", None),
        media_dir,
        temp_root,
    )

    # Import diferido del pipeline (por si el import es costoso)
    run_pipeline_for_job = _import_pipeline()

    # Exportar info mínima a variables de entorno para los scripts
    os.environ["MIX_JOB_ID"] = job_id
    os.environ["MIX_MEDIA_DIR"] = media_dir
    os.environ["MIX_TEMP_ROOT"] = temp_root

    media_dir_path = Path(media_dir)
    temp_root_path = Path(temp_root)

    job_root_path = temp_root_path

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
    _write_job_status(job_root_path, initial_status)

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
        _write_job_status(job_root_path, status)

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
            "[%s] Llamando a run_pipeline_for_job (enabled_stage_keys=%s)",
            job_id,
            enabled_stage_keys,
        )
        t0 = time.time()

        run_pipeline_for_job(
            job_id=job_id,
            media_dir=media_dir_path,
            temp_root=temp_root_path,
            enabled_stage_keys=enabled_stage_keys,
            profiles_by_name=profiles_by_name,
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
            "stage_index": progress_state.get("stage_index", 0),
            "total_stages": progress_state.get("total_stages", 0),
            "stage_key": "error",
            "message": f"Error en pipeline: {exc}",
            "progress": float(
                100.0
                if progress_state.get("stage_index", 0)
                >= progress_state.get("total_stages", 0) > 0
                else 0.0
            ),
            "error": str(exc),
        }
        _write_job_status(job_root_path, error_status)
        raise

    logger.info(
        "[%s] Pipeline finalizado correctamente.",
        job_id,
    )

    # ---------------------------
    # 2) Calcular métricas y URLs finales
    # ---------------------------
    metrics = _safe_compute_final_metrics(job_id)
    original_path, master_path = _locate_original_and_master_paths(job_id)

    original_url = _make_files_url(job_root_path, job_id, original_path)
    master_url = _make_files_url(job_root_path, job_id, master_path)

    total_stages = int(progress_state.get("total_stages", 0))
    stage_index = int(progress_state.get("stage_index", total_stages))

    final_status = {
        "jobId": job_id,
        "job_id": job_id,
        "status": "success",
        "message": "Mix pipeline finished successfully.",
        "stage_index": stage_index,
        "total_stages": total_stages,
        "stage_key": "finished",
        "progress": 100.0,
        "job_root": str(job_root_path),
        "input_media_dir": str(media_dir_path),
        "temp_root": str(temp_root_path),
        "original_full_song_url": original_url,
        "full_song_url": master_url,
        "metrics": metrics,
        "bus_styles": {},
    }

    _write_job_status(job_root_path, final_status)

    total_time = time.time() - start_ts
    logger.info(
        "[%s] <<< run_full_pipeline_task COMPLETADO en %.1fs (job_root=%s)",
        job_id,
        total_time,
        job_root_path,
    )

    return final_status
