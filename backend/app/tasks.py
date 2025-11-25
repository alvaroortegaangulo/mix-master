# /app/tasks.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from celery import states

from celery_app import celery_app
from src.pipeline import run_full_pipeline


# Raíz del proyecto dentro del contenedor
PROJECT_ROOT = Path(__file__).resolve().parent


@celery_app.task(bind=True)
def run_full_pipeline_task(
    self,
    job_id: str,
    media_dir: str,
    temp_root: str,
    enabled_stage_keys: list[str] | None = None,
    stem_profiles: dict[str, str] | None = None,
    bus_styles: dict[str, str] | None = None,
) -> Dict[str, Any]:
    """
    Tarea Celery que ejecuta el pipeline completo (o un subconjunto de stages).

    Parámetros
    ----------
    job_id:
        Identificador del job; se usa también como task_id desde server.py.
    media_dir:
        Carpeta de stems de entrada (…/temp/<job_id>/media).
    temp_root:
        Carpeta de trabajo interna (…/temp/<job_id>/work).
    enabled_stage_keys:
        Lista opcional de claves de etapa (stage["key"]) a ejecutar.
        Si es None o lista vacía, se ejecutan todas las etapas definidas en STAGES.
    """
    media_dir_path = Path(media_dir)
    temp_root_path = Path(temp_root)

    # job_root es /app/temp/<job_id>, padre de "work" y "media"
    job_root_path = temp_root_path.parent

    # ---------------------------
    # Callback de progreso Celery
    # ---------------------------
    def progress_cb(stage_index: int, total_stages: int, stage_key: str, message: str):
        """
        Publica progreso en el backend de Celery.
        """
        progress = float(stage_index) / float(total_stages) * 100.0
        self.update_state(
            state="PROGRESS",
            meta={
                "jobId": job_id,
                "stage_index": stage_index,
                "total_stages": total_stages,
                "stage_key": stage_key,
                "message": message,
                "progress": progress,
            },
        )

    # ---------------------------
    # Ejecución del pipeline
    # ---------------------------
    try:
        pipeline_result = run_full_pipeline(
            project_root=PROJECT_ROOT,
            media_dir=media_dir_path,
            temp_root=temp_root_path,
            progress_callback=progress_cb,
            enabled_stage_keys=enabled_stage_keys,
            stem_profiles=stem_profiles,
            bus_styles=bus_styles,
        )    
    except Exception as exc:
        # Marcamos fallo en Celery con información básica
        self.update_state(
            state=states.FAILURE,
            meta={
                "jobId": job_id,
                "exc_type": type(exc).__name__,
                "exc_message": str(exc),
                "exc_module": exc.__class__.__module__,
            },
        )
        raise

    # ---------------------------
    # Serialización a JSON
    # ---------------------------

    # Helper para construir URLs públicas bajo /files
    # En server.py has montado:
    # app.mount("/files", StaticFiles(directory=str(JOBS_ROOT)), name="files")
    #
    # JOBS_ROOT = /app/temp
    # job_root_path = /app/temp/<job_id>
    # Así que la URL será /files/<job_id>/rutas_relativas...
    def make_files_url(path: Path) -> str:
        rel = path.relative_to(job_root_path)  # p.ej. "media/full_song.wav"
        return f"/files/{job_id}/{rel.as_posix()}"

    # Métricas estructuradas (para que Celery las pueda guardar en JSON)
    metrics = pipeline_result.metrics
    metrics_dict: Dict[str, Any] = {
        "final_peak_dbfs": metrics.final_peak_dbfs,
        "final_rms_dbfs": metrics.final_rms_dbfs,
        "tempo_bpm": metrics.tempo_bpm,
        "tempo_confidence": metrics.tempo_confidence,
        "key": metrics.key,
        "scale": metrics.scale,
        "key_strength": metrics.key_strength,
        "vocal_shift_min": metrics.vocal_shift_min,
        "vocal_shift_max": metrics.vocal_shift_max,
        "vocal_shift_mean": metrics.vocal_shift_mean,
        "bus_styles": bus_styles,
    }

    # Rutas útiles para el frontend/API
    original_path = pipeline_result.original_full_song_path
    full_path = pipeline_result.full_song_path

    return {
        # Info interna de carpetas (por si la quieres usar en logs o debug)
        "job_root": str(job_root_path),                 # /app/temp/<job_id>
        "input_media_dir": str(pipeline_result.input_media_dir),
        "temp_root": str(pipeline_result.temp_root),

        # Rutas absolutas en filesystem
        "original_full_song_path": str(original_path),
        "full_song_path": str(full_path),

        # URLs públicas para que el frontend pueda hacer GET
        # sobre /files/...
        "original_full_song_url": make_files_url(original_path),
        "full_song_url": make_files_url(full_path),

        # Rutas de directorios intermedios (por si quieres exponerlos en /jobs/{id}/tree)
        "dc_offset_media_dir": str(pipeline_result.dc_offset_media_dir),
        "loudness_media_dir": str(pipeline_result.loudness_media_dir),
        "spectral_media_dir": str(pipeline_result.spectral_media_dir),
        "dynamics_media_dir": str(pipeline_result.dynamics_media_dir),
        "vocal_tuning_media_dir": str(pipeline_result.vocal_tuning_media_dir),

        # Métricas finales
        "metrics": metrics_dict,
        "bus_styles": bus_styles or {},
    }
