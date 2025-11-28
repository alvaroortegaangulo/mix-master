from __future__ import annotations

import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any

from celery import states
from celery_app import celery_app

from src.pipeline import run_pipeline_for_job
from src.utils.analysis_utils import (
    get_temp_dir,
    load_audio_mono,
    compute_peak_dbfs,
    compute_integrated_loudness_lufs,
)

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# Helpers para métricas y localización de ficheros finales
# -------------------------------------------------------------------------

def _safe_compute_final_metrics(job_id: str) -> Dict[str, Any]:
    """
    Calcula un bloque mínimo de métricas finales para el frontend.

    - Busca primero el full_song del contrato S11_REPORT_GENERATION.
    - Si no existe, intenta con S10_MASTER_FINAL_LIMITS.
    - Lee análisis de S1_KEY_DETECTION (si existe).
    - El resto de campos se devuelven con valores neutros.

    Devuelve un dict con la forma de MixMetrics:
      {
        "final_peak_dbfs": float,
        "final_rms_dbfs": float,
        "tempo_bpm": float,
        "tempo_confidence": float,
        "key": str,
        "scale": str,
        "key_strength": float,
        "vocal_shift_min": float,
        "vocal_shift_max": float,
        "vocal_shift_mean": float,
      }
    """
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
    # 1) Métricas a partir del máster final (S11 -> S10)
    # -----------------------------
    master_audio_path: Optional[Path] = None
    try:
        # Preferimos el full_song de S11_REPORT_GENERATION
        for contract_id in ("S11_REPORT_GENERATION", "S10_MASTER_FINAL_LIMITS"):
            master_dir = get_temp_dir(contract_id, create=False)
            cand = master_dir / "full_song.wav"
            if cand.exists():
                master_audio_path = cand
                break

        if master_audio_path is not None:
            mono, sr = load_audio_mono(master_audio_path)
            final_peak_dbfs = compute_peak_dbfs(mono)
            final_rms_dbfs = compute_integrated_loudness_lufs(mono, sr)
        else:
            logger.warning(
                "[tasks] No se ha encontrado máster final (S11 ni S10) para job_id=%s",
                job_id,
            )
    except Exception as exc:
        logger.warning(
            "[tasks] Error calculando métricas de máster final para job_id=%s: %s",
            job_id,
            exc,
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
            key_strength = float(
                session.get("key_detection_confidence", 0.0) or 0.0
            )
        else:
            logger.info(
                "[tasks] No se ha encontrado analysis_%s.json para key detection (job_id=%s)",
                contract_id,
                job_id,
            )
    except Exception as exc:
        logger.warning(
            "[tasks] Error leyendo análisis de key detection para job_id=%s: %s",
            job_id,
            exc,
        )

    # (3) Tempo y shifts vocales: de momento neutros hasta que los midamos en el nuevo pipeline.

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
        # p.ej. "S10_MASTER_FINAL_LIMITS/full_song.wav"
        rel = path.relative_to(job_root)
    except ValueError:
        # No cuelga de job_root
        return ""

    # El server monta StaticFiles en /files apuntando a PROJECT_ROOT/temp:
    #   /files/<job_id>/S10_MASTER_FINAL_LIMITS/full_song.wav -> temp/<job_id>/...
    return f"/files/{job_id}/{rel.as_posix()}"


def _locate_original_and_master_paths(job_id: str) -> tuple[Path | None, Path | None]:
    """
    Intenta localizar:
      - original_mix_path: full_song de S0_MIX_ORIGINAL
      - master_path: full_song de S11_REPORT_GENERATION (si existe) o S10_MASTER_FINAL_LIMITS

    Devolvemos (original_path or None, master_path or None).
    """
    original_path: Path | None = None
    master_path: Path | None = None

    # Original (S0_MIX_ORIGINAL)
    try:
        s0_dir = get_temp_dir("S0_MIX_ORIGINAL", create=False)
        cand = s0_dir / "full_song.wav"
        if cand.exists():
            original_path = cand
        else:
            logger.info(
                "[tasks] No se encuentra original full_song.wav en %s (job_id=%s)",
                cand,
                job_id,
            )
    except Exception as exc:
        logger.warning(
            "[tasks] Error localizando original full_song.wav para job_id=%s: %s",
            job_id,
            exc,
        )

    # Máster final (S11 -> S10)
    try:
        for contract_id in ("S11_REPORT_GENERATION", "S10_MASTER_FINAL_LIMITS"):
            cdir = get_temp_dir(contract_id, create=False)
            cand = cdir / "full_song.wav"
            if cand.exists():
                master_path = cand
                break

        if master_path is None:
            logger.info(
                "[tasks] No se encuentra máster full_song.wav en S11 ni S10 (job_id=%s)",
                job_id,
            )
    except Exception as exc:
        logger.warning(
            "[tasks] Error localizando máster full_song.wav para job_id=%s: %s",
            job_id,
            exc,
        )

    return original_path, master_path


# -------------------------------------------------------------------------
# Tarea Celery principal
# -------------------------------------------------------------------------

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

    - job_id: identificador del job.
    - media_dir: carpeta donde se han guardado los stems originales.
    - temp_root: carpeta raíz temporal del job (p.ej. /app/temp/<job_id>).
    - enabled_stage_keys: lista opcional de contract_ids a ejecutar
                          (S0_SESSION_FORMAT, S1_STEM_DC_OFFSET, ...).
    - profiles_by_name: mapping opcional nombre_de_archivo -> perfil_de_stem.
    """

    logger.info(
        "Celery: iniciando run_full_pipeline_task job_id=%s media_dir=%s temp_root=%s",
        job_id,
        media_dir,
        temp_root,
    )

    # Exportar info mínima a variables de entorno para los scripts de análisis/stages
    os.environ["MIX_JOB_ID"] = job_id
    os.environ["MIX_MEDIA_DIR"] = media_dir
    os.environ["MIX_TEMP_ROOT"] = temp_root

    media_dir_path = Path(media_dir)
    temp_root_path = Path(temp_root)
    job_root_path = temp_root_path  # en este diseño: /app/temp/<job_id>

    # ----------------------------------------------------
    # Callback de progreso: llamado desde run_pipeline_for_job
    # ----------------------------------------------------
    def progress_cb(
        stage_index: int,
        total_stages: int,
        stage_key: str,
        message: str,
    ) -> None:
        if total_stages <= 0:
            progress = 0.0
        else:
            progress = float(stage_index) / float(total_stages) * 100.0

        meta = {
            "jobId": job_id,
            "stage_index": stage_index,
            "total_stages": total_stages,
            "stage_key": stage_key,
            "message": message,
            "progress": progress,
        }
        # Estado custom "PROGRESS" que el endpoint /jobs/{jobId} mapea a "running"
        self.update_state(state="PROGRESS", meta=meta)

    # ---------------------------
    # 1) Ejecutar pipeline
    # ---------------------------
    try:
        run_pipeline_for_job(
            job_id=job_id,
            media_dir=media_dir_path,
            temp_root=temp_root_path,
            enabled_stage_keys=enabled_stage_keys,
            profiles_by_name=profiles_by_name,
            progress_cb=progress_cb,
        )
    except Exception as exc:
        logger.exception("Error en run_pipeline_for_job(job_id=%s)", job_id)

        # Marcamos fallo en Celery (el estado final será FAILURE y /jobs lo verá)
        self.update_state(
            state=states.FAILURE,
            meta={
                "jobId": job_id,
                "exc_type": type(exc).__name__,
                "exc_message": str(exc),
                "exc_module": exc.__class__.__module__,
            },
        )
        # Re-lanzamos para que Celery marque el task como FAILURE
        raise

    logger.info("Celery: pipeline finalizado correctamente job_id=%s", job_id)

    # ---------------------------
    # 2) Calcular métricas y URLs finales
    # ---------------------------
    metrics = _safe_compute_final_metrics(job_id)
    original_path, master_path = _locate_original_and_master_paths(job_id)

    original_url = _make_files_url(job_root_path, job_id, original_path)
    master_url = _make_files_url(job_root_path, job_id, master_path)

    # ---------------------------
    # 3) Resultado estructurado para /jobs/{jobId}
    # ---------------------------
    return {
        # Identificación básica
        "jobId": job_id,
        "status": "success",
        "message": "Mix pipeline finished successfully.",

        # Info de rutas internas (útil para debug / filesystem)
        "job_root": str(job_root_path),          # /app/temp/<job_id>
        "input_media_dir": str(media_dir_path),  # /app/media/<job_id>
        "temp_root": str(temp_root_path),        # igual que job_root en este diseño

        # URLs relativas que el frontend convertirá en absolutas con getBackendBaseUrl
        "original_full_song_url": original_url,
        "full_song_url": master_url,

        # Métricas finales con la forma de MixMetrics
        "metrics": metrics,

        # Placeholder por si más adelante quieres propagar estilos de buses, etc.
        "bus_styles": {},
    }
