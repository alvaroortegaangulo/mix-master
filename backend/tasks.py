# C:\mix-master\backend\tasks.py

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



STAGE_UI_INFO: Dict[str, Dict[str, str]] = {
    "S0_SESSION_FORMAT": {
        "label": "SESSION FORMAT",
        "description_en": (
            "Session format normalization (sample rate, bit depth, working headroom "
            "and bus routing)."
        ),
    },
    "S1_STEM_DC_OFFSET": {
        "label": "STEM DC OFFSET",
        "description_en": (
            "DC offset detection and correction per stem to recentre the waveform "
            "and recover headroom."
        ),
    },
    "S1_STEM_WORKING_LOUDNESS": {
        "label": "STEM WORKING LOUDNESS",
        "description_en": (
            "Working loudness normalization per stem based on its instrument profile, "
            "so all tracks sit in a comfortable level range."
        ),
    },
    "S1_KEY_DETECTION": {
        "label": "GLOBAL KEY DETECTION",
        "description_en": (
            "Global key and scale detection for the session, used later for vocal tuning "
            "and harmonic decisions."
        ),
    },
    "S1_VOX_TUNING": {
        "label": "VOCAL TUNING",
        "description_en": (
            "Lead vocal pitch correction using the detected key, with controlled pitch "
            "range and tuning strength."
        ),
    },
    "S2_GROUP_PHASE_DRUMS": {
        "label": "DRUM GROUP PHASE",
        "description_en": (
            "Phase and polarity alignment within the drums/percussion group to preserve "
            "low-end punch and avoid cancellations."
        ),
    },
    "S3_MIXBUS_HEADROOM": {
        "label": "MIXBUS HEADROOM",
        "description_en": (
            "Global headroom adjustment for the mix bus, targeting a safe peak level "
            "and working LUFS for downstream processing."
        ),
    },
    "S3_LEADVOX_AUDIBILITY": {
        "label": "LEAD VOCAL AUDIBILITY",
        "description_en": (
            "Static level balancing of the lead vocal against the rest of the mix so it "
            "sits clearly on top without sounding detached."
        ),
    },
    "S4_STEM_HPF_LPF": {
        "label": "STEM HPF/LPF FILTERS",
        "description_en": (
            "Per-stem high-pass and low-pass filtering based on instrument profile to "
            "remove unnecessary sub-lows and ultra-highs."
        ),
    },
    "S4_STEM_RESONANCE_CONTROL": {
        "label": "STEM RESONANCE CONTROL",
        "description_en": (
            "Per-stem resonance control using limited narrow cuts to tame harsh or "
            "ringing frequencies without over-EQing."
        ),
    },
    "S5_STEM_DYNAMICS_GENERIC": {
        "label": "STEM DYNAMICS",
        "description_en": (
            "Generic per-stem dynamics (compression and/or gating) to keep the dynamic "
            "range under control while preserving natural transients."
        ),
    },
    "S5_LEADVOX_DYNAMICS": {
        "label": "LEAD VOCAL DYNAMICS",
        "description_en": (
            "Lead vocal-focused dynamics processing (main compression and gentle "
            "automation) to stabilize level and presence."
        ),
    },
    "S5_BUS_DYNAMICS_DRUMS": {
        "label": "DRUM BUS DYNAMICS",
        "description_en": (
            "Bus compression for the drums group to add punch, cohesion and musical glue "
            "to the kit."
        ),
    },
    "S6_BUS_REVERB_STYLE": {
        "label": "BUS REVERB & SPACE",
        "description_en": (
            "Style-based assignment of reverbs and spatial treatment per bus family, "
            "building a coherent sense of depth and room."
        ),
    },
    "S7_MIXBUS_TONAL_BALANCE": {
        "label": "MIXBUS TONAL BALANCE",
        "description_en": (
            "Broadband mix bus EQ by frequency bands to match the overall tonal balance "
            "to the chosen reference style."
        ),
    },
    "S8_MIXBUS_COLOR_GENERIC": {
        "label": "MIXBUS COLOR",
        "description_en": (
            "Mix bus colour and glue via gentle saturation and harmonic enhancement, "
            "kept within defined distortion limits."
        ),
    },
    "S9_MASTER_GENERIC": {
        "label": "STEM MASTERING",
        "description_en": (
            "Mastering stage: final loudness and true-peak target, plus moderate M/S "
            "width shaping according to style profile."
        ),
    },
    "S10_MASTER_FINAL_LIMITS": {
        "label": "FINAL MASTER QC",
        "description_en": (
            "Final master quality control (true peak, LUFS, L/R balance and correlation) "
            "with micro-adjustments only."
        ),
    },
}

# -------------------------------------------------------------------
# Helpers de métricas finales
# -------------------------------------------------------------------

def _format_stage_message(
    stage_index: int,
    total_stages: int,
    stage_key: str,
    progress_val: float,
) -> str:
    """
    Construye el mensaje para el frontend, p.ej.:

      [42%] Step 8/19 – Running stage MIXBUS HEADROOM…
      Global headroom adjustment for the mix bus (peak and working LUFS).
    """
    percent_int = int(round(progress_val))
    info = STAGE_UI_INFO.get(stage_key, {})
    label = info.get("label", stage_key)
    desc = info.get("description_en", "")

    header = f"[{percent_int}%] Step {stage_index}/{total_stages} – Running stage {label}…"
    if desc:
        return f"{header}\n{desc}"
    return header


def _safe_compute_final_metrics(job_id: str) -> Dict[str, Any]:
    """
    Calcula un bloque mínimo de métricas finales para el frontend.

    - Lee el full_song de S10_MASTER_FINAL_LIMITS (si existe).
    - Lee análisis de S1_KEY_DETECTION (si existe).
    - El resto de campos se devuelven con valores neutros.

    Devuelve un dict con la forma de MixMetrics.
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
                "[tasks] No se ha encontrado máster final en %s", master_path
            )
    except Exception as exc:
        logger.warning(
            "[tasks] Error calculando métricas de máster final: %s", exc
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
                "[tasks] No se ha encontrado analysis_%s.json para key detection",
                contract_id,
            )
    except Exception as exc:
        logger.warning(
            "[tasks] Error leyendo análisis de key detection: %s", exc
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
        rel = path.relative_to(job_root)  # p.ej. "S10_MASTER_FINAL_LIMITS/full_song.wav"
    except ValueError:
        # No cuelga de job_root
        return ""

    # Asumimos que en server.py montas StaticFiles en /files apuntando a PROJECT_ROOT/temp
    # de forma que: /files/<job_id>/... -> temp/<job_id>/...
    return f"/files/{job_id}/{rel.as_posix()}"


def _locate_original_and_master_paths(job_id: str) -> tuple[Path | None, Path | None]:
    """
    Intenta localizar:
      - original_mix_path: full_song de S0_MIX_ORIGINAL
      - master_path: full_song de S10_MASTER_FINAL_LIMITS

    Devolvemos (original_path or None, master_path or None).
    """
    original_path: Path | None = None
    master_path: Path | None = None

    try:
        # S0_MIX_ORIGINAL
        s0_dir = get_temp_dir("S0_MIX_ORIGINAL", create=False)
        cand = s0_dir / "full_song.wav"
        if cand.exists():
            original_path = cand
        else:
            logger.info(
                "[tasks] No se encuentra original full_song.wav en %s", cand
            )
    except Exception as exc:
        logger.warning(
            "[tasks] Error localizando original full_song.wav: %s", exc
        )

    try:
        # S10_MASTER_FINAL_LIMITS
        s10_dir = get_temp_dir("S10_MASTER_FINAL_LIMITS", create=False)
        cand = s10_dir / "full_song.wav"
        if cand.exists():
            master_path = cand
        else:
            logger.info(
                "[tasks] No se encuentra máster full_song.wav en %s", cand
            )
    except Exception as exc:
        logger.warning(
            "[tasks] Error localizando máster full_song.wav: %s", exc
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
    except Exception as exc:
        logger.warning("[tasks] No se pudo escribir job_status.json: %s", exc)


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

    - job_id: identificador del job.
    - media_dir: carpeta donde se han guardado los stems originales.
    - temp_root: carpeta raíz temporal del job (p.ej. /app/temp/<job_id>).
    - enabled_stage_keys: lista opcional de contract_ids a ejecutar.
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

    # En este diseño, temp_root = /app/temp/<job_id>
    job_root_path = temp_root_path

    # Estado de progreso que iremos actualizando en la callback
    progress_state: Dict[str, Any] = {
        "stage_index": 0,
        "total_stages": 0,
        "stage_key": "initializing",
        "message": "Inicializando pipeline...",
    }

    # Estado inicial mínimo (por si el frontend pregunta antes de que arranque el pipeline)
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

    # ----------------------------------------------------
    # Callback de progreso: llamado desde run_pipeline_for_job
    # ----------------------------------------------------
    def progress_cb(
        stage_index: int,
        total_stages: int,
        stage_key: str,
        message: str,   # lo seguimos aceptando pero ya no lo usamos para el UI
    ) -> None:
        # Actualizar estado interno
        progress_state["stage_index"] = stage_index
        progress_state["total_stages"] = total_stages
        progress_state["stage_key"] = stage_key
        progress_state["message"] = message  # opcional para logs internos

        if total_stages <= 0:
            progress_val = 0.0
        else:
            progress_val = float(stage_index) / float(total_stages) * 100.0

        # Nuevo mensaje “bonito” para el frontend
        ui_message = _format_stage_message(
            stage_index=stage_index,
            total_stages=total_stages,
            stage_key=stage_key,
            progress_val=progress_val,
        )

        meta = {
            "jobId": job_id,
            "stage_index": stage_index,
            "total_stages": total_stages,
            "stage_key": stage_key,
            "message": ui_message,
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
            "message": ui_message,   # aquí es lo que le llegará al frontend
            "progress": progress_val,
        }
        _write_job_status(job_root_path, status)


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
        # Marcamos fallo en Celery con info básica
        logger.exception("Error en run_pipeline_for_job(job_id=%s)", job_id)
        self.update_state(
            state=states.FAILURE,
            meta={
                "jobId": job_id,
                "exc_type": type(exc).__name__,
                "exc_message": str(exc),
                "exc_module": exc.__class__.__module__,
            },
        )

        # Y escribimos job_status.json con estado de error
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

    logger.info("Celery: pipeline finalizado correctamente job_id=%s", job_id)

    # ---------------------------
    # 2) Calcular métricas y URLs finales
    # ---------------------------
    metrics = _safe_compute_final_metrics(job_id)
    original_path, master_path = _locate_original_and_master_paths(job_id)

    original_url = _make_files_url(job_root_path, job_id, original_path)
    master_url = _make_files_url(job_root_path, job_id, master_path)

    # ---------------------------
    # 3) Resultado estructurado
    # ---------------------------
    total_stages = int(progress_state.get("total_stages", 0))
    stage_index = int(progress_state.get("stage_index", total_stages))

    final_status = {
        # Identificación básica
        "jobId": job_id,
        "job_id": job_id,
        "status": "success",
        "message": "Mix pipeline finished successfully.",

        # Progreso
        "stage_index": stage_index,
        "total_stages": total_stages,
        "stage_key": "finished",
        "progress": 100.0,

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

    # Guardar estado final en job_status.json
    _write_job_status(job_root_path, final_status)

    # Devolvemos también el resultado a Celery (por si quieres inspeccionarlo vía backend)
    return final_status
