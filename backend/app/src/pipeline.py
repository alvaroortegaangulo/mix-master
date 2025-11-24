from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import logging
import os
import psutil
import time
from typing import Callable, Optional

# Configuración básica de logging si nadie la ha configurado aún
logger = logging.getLogger(__name__)
if not logging.getLogger().hasHandlers():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

_process = psutil.Process(os.getpid())

def timed(label: str):
    def decorator(fn):
        def wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            result = fn(*args, **kwargs)
            t1 = time.perf_counter()
            logger.info("[TIMER] %s: %.2f s", label, t1 - t0)
            return result
        return wrapper
    return decorator


def log_mem(label: str) -> None:
    """Log sencillo de memoria residente, en MB."""
    try:
        mem_mb = _process.memory_info().rss / (1024 * 1024)
        logger.info("[MEM] %s: %.1f MB", label, mem_mb)
    except Exception as exc:
        logger.warning("No se pudo leer memoria en %s: %s", label, exc)


ProgressCallback = Callable[[int, int, str, str], None]
# args: stage_index, total_stages, stage_key, message


# Imports de tus módulos actuales (ajusta rutas reales)
from src.analysis.dc_offset_detection import detect_dc_offset, export_dc_offset_to_csv
from src.stages.stage0_technical_preparation.dc_offset_correction import run_dc_offset_correction
from src.analysis.loudness_analysis import analyze_loudness, export_loudness_to_csv
from src.stages.stage0_technical_preparation.loudness_correction import run_loudness_correction
from src.analysis.spectral_cleanup_analysis import analyze_spectral_cleanup, export_spectral_cleanup_to_csv
from src.stages.stage1_static_mix.spectral_cleanup_correction import run_spectral_cleanup_correction
from src.analysis.dynamics_analysis import analyze_dynamics, export_dynamics_to_csv
from src.stages.stage2_dynamics.dynamics_correction import run_dynamics_correction
from src.analysis.tempo_analysis import analyze_tempo
from src.analysis.key_analysis import analyze_key, export_key_to_csv
from src.stages.stage0_technical_preparation.vocal_tuning import (
    run_vocal_tuning_autotune,
    export_vocal_autotune_log,
)
from src.utils.mixdown import mix_corrected_stems_to_full_song, FullSongRenderResult


@dataclass
class FullPipelineMetrics:
    final_peak_dbfs: float
    final_rms_dbfs: float

    tempo_bpm: float
    tempo_confidence: float

    key: str
    scale: str
    key_strength: float

    vocal_shift_min: float
    vocal_shift_max: float
    vocal_shift_mean: float


@dataclass
class FullPipelineResult:
    """
    Resultado de alto nivel del pipeline completo de mezcla.
    Este objeto es lo que usará la API para construir la respuesta JSON.
    """
    full_song_path: Path

    temp_root: Path
    input_media_dir: Path

    dc_offset_media_dir: Path
    loudness_media_dir: Path
    spectral_media_dir: Path
    dynamics_media_dir: Path
    vocal_tuning_media_dir: Path

    metrics: FullPipelineMetrics


def run_full_pipeline(
    project_root: Path,
    media_dir: Path,
    temp_root: Path,
    progress_callback: Optional[ProgressCallback] = None,
) -> FullPipelineResult:
    """
    Ejecuta TODO el pipeline de mezcla sobre los stems de media_dir.

    Pasos:
      1) DC offset (análisis + corrección).
      2) Loudness por stem + normalización.
      3) Limpieza espectral (HPF + notches).
      4) Control de dinámica por pista.
      5) Análisis de tempo y tonalidad.
      6) Auto-Tune de la voz hacia la escala del tema.
      7) Mixdown de stems finales a full_song.wav.
    """

    TOTAL_STAGES = 7  # DC offset, Loudness, Spectral, Dynamics, Tempo/Key, Vocal, Mixdown

    def _report(stage_index: int, stage_key: str, message: str) -> None:
        if progress_callback:
            progress_callback(stage_index, TOTAL_STAGES, stage_key, message)

    logger.info("=== Iniciando run_full_pipeline ===")
    _report(0, "start", "Starting pipeline")
    logger.info("project_root=%s", project_root)
    logger.info("media_dir=%s", media_dir)
    logger.info("temp_root=%s", temp_root)

    # Directorios internos
    analysis_dir = temp_root / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)

    dc_offset_media_dir = temp_root / "media" / "dc_offset"
    loudness_media_dir = temp_root / "media" / "loudness"
    spectral_media_dir = temp_root / "media" / "static_mix_eq"
    dynamics_media_dir = temp_root / "media" / "static_mix_dyn"
    vocal_tuning_media_dir = temp_root / "media" / "vocal_tuning"

    for d in [
        dc_offset_media_dir,
        loudness_media_dir,
        spectral_media_dir,
        dynamics_media_dir,
        vocal_tuning_media_dir,
    ]:
        d.mkdir(parents=True, exist_ok=True)

    logger.info("Directorios creados:")
    logger.info("  analysis_dir           = %s", analysis_dir)
    logger.info("  dc_offset_media_dir    = %s", dc_offset_media_dir)
    logger.info("  loudness_media_dir     = %s", loudness_media_dir)
    logger.info("  spectral_media_dir     = %s", spectral_media_dir)
    logger.info("  dynamics_media_dir     = %s", dynamics_media_dir)
    logger.info("  vocal_tuning_media_dir = %s", vocal_tuning_media_dir)

    log_mem("start_pipeline")

    # ------------------------------------------------------------------
    # 1. DC offset
    # ------------------------------------------------------------------
    t0 = time.perf_counter()
    logger.info("[1/7] Iniciando análisis de DC offset en %s", media_dir)
    _report(1, "dc_offset", "Analyzing and correcting DC offset")
    log_mem("before_dc_offset_analysis")
    dc_offset_results = detect_dc_offset(media_dir)
    log_mem("after_dc_offset_analysis")
    logger.info("[1/7] Análisis de DC offset completado (%s resultados)", 
                getattr(dc_offset_results, "__len__", lambda: "n/a")())

    dc_offset_csv_path = analysis_dir / "dc_offset_analysis.csv"
    export_dc_offset_to_csv(dc_offset_results, dc_offset_csv_path)
    logger.info("[1/7] CSV de DC offset exportado a %s", dc_offset_csv_path)

    log_mem("before_dc_offset_correction")
    run_dc_offset_correction(
        dc_offset_csv_path,
        media_dir,
        dc_offset_media_dir,
    )
    log_mem("after_dc_offset_correction")
    logger.info("[1/7] Corrección de DC offset aplicada. Stems corregidos en %s", dc_offset_media_dir)
    logger.info("[TIMER] DC offset: %.2f s", time.perf_counter() - t0)

    # ------------------------------------------------------------------
    # 2. Loudness por stem
    # ------------------------------------------------------------------
    t0 = time.perf_counter()
    logger.info("[2/7] Iniciando análisis de loudness por stem")
    _report(2, "loudness", "Analyzing and normalizing loudness per stem")
    loudness_csv_path = analysis_dir / "loudness_analysis.csv"
    target_rms_dbfs = -18.0
    logger.info("[2/7] Objetivo de RMS: %.2f dBFS", target_rms_dbfs)

    log_mem("before_loudness_analysis")
    loudness_results = analyze_loudness(
        media_dir=dc_offset_media_dir,
        target_rms_dbfs=target_rms_dbfs,
    )
    log_mem("after_loudness_analysis")
    logger.info("[2/7] Análisis de loudness completado (%s resultados)", 
                getattr(loudness_results, "__len__", lambda: "n/a")())

    export_loudness_to_csv(loudness_results, loudness_csv_path)
    logger.info("[2/7] CSV de loudness exportado a %s", loudness_csv_path)

    log_mem("before_loudness_correction")
    run_loudness_correction(
        loudness_csv_path,
        dc_offset_media_dir,
        loudness_media_dir,
        mode="rms",
    )
    log_mem("after_loudness_correction")
    logger.info("[2/7] Corrección de loudness aplicada. Stems normalizados en %s", loudness_media_dir)
    logger.info("[TIMER] Loudness: %.2f s", time.perf_counter() - t0)

    # ------------------------------------------------------------------
    # 3. Limpieza espectral (HPF + EQ sustractiva)
    # ------------------------------------------------------------------
    t0 = time.perf_counter()
    logger.info("[3/7] Iniciando análisis de limpieza espectral")
    _report(3, "spectral", "Applying spectral cleanup and EQ")
    spectral_cleanup_csv_path = analysis_dir / "spectral_cleanup_analysis.csv"

    log_mem("before_spectral_analysis")
    spectral_cleanup_results = analyze_spectral_cleanup(loudness_media_dir)
    log_mem("after_spectral_analysis")
    logger.info("[3/7] Análisis espectral completado (%s resultados)", 
                getattr(spectral_cleanup_results, "__len__", lambda: "n/a")())

    export_spectral_cleanup_to_csv(spectral_cleanup_results, spectral_cleanup_csv_path)
    logger.info("[3/7] CSV de limpieza espectral exportado a %s", spectral_cleanup_csv_path)

    log_mem("before_spectral_correction")
    run_spectral_cleanup_correction(
        spectral_cleanup_csv_path,
        loudness_media_dir,
        spectral_media_dir,
        max_notches=4,
    )
    log_mem("after_spectral_correction")
    logger.info("[3/7] Corrección espectral aplicada. Stems EQ en %s", spectral_media_dir)
    logger.info("[TIMER] Espectral: %.2f s", time.perf_counter() - t0)

    # ------------------------------------------------------------------
    # 4. Dinámica por pista (comp + limiter)
    # ------------------------------------------------------------------
    t0 = time.perf_counter()
    logger.info("[4/7] Iniciando análisis de dinámica por pista")
    _report(4, "dynamics", "Applying dynamics processing (compression/limiting)")
    dynamics_csv_path = analysis_dir / "dynamics_analysis.csv"

    log_mem("before_dynamics_analysis")
    dynamics_results = analyze_dynamics(spectral_media_dir)
    log_mem("after_dynamics_analysis")

    logger.info("[4/7] Análisis de dinámica completado (%s resultados)", 
                getattr(dynamics_results, "__len__", lambda: "n/a")())

    export_dynamics_to_csv(dynamics_results, dynamics_csv_path)
    logger.info("[4/7] CSV de dinámica exportado a %s", dynamics_csv_path)

    log_mem("before_dynamics_correction")
    run_dynamics_correction(
        dynamics_csv_path,
        spectral_media_dir,
        dynamics_media_dir,
    )
    log_mem("after_dynamics_correction")

    logger.info("[4/7] Corrección de dinámica aplicada. Stems dinámicos en %s", dynamics_media_dir)
    logger.info("[TIMER] Dinámica: %.2f s", time.perf_counter() - t0)

    # ------------------------------------------------------------------
    # 5. Tempo & Key
    # ------------------------------------------------------------------
    t0 = time.perf_counter()
    logger.info("[5/7] Iniciando análisis de tempo y tonalidad usando %s", loudness_media_dir)
    _report(5, "tempo_key", "Analyzing tempo and musical key")

    log_mem("before_tempo_key")
    tempo_result = analyze_tempo(loudness_media_dir)
    key_result = analyze_key(loudness_media_dir)
    log_mem("after_tempo_key")

    logger.info(
        "[5/7] Tempo detectado: %.2f BPM (conf=%.3f)",
        tempo_result.bpm,
        tempo_result.bpm_confidence,
    )
    logger.info(
        "[5/7] Tonalidad detectada: %s %s (strength=%.3f)",
        key_result.key,
        key_result.scale,
        key_result.strength,
    )

    key_csv_path = analysis_dir / "key_analysis.csv"
    export_key_to_csv(key_result, key_csv_path)
    logger.info("[5/7] CSV de tonalidad exportado a %s", key_csv_path)
    logger.info("[TIMER] Tempo & key: %.2f s", time.perf_counter() - t0)

    # ------------------------------------------------------------------
    # 6. Auto-Tune de la voz
    # ------------------------------------------------------------------
    t0 = time.perf_counter()
    logger.info("[6/7] Iniciando Auto-Tune de la voz")
    _report(6, "vocal_tuning", "Applying vocal tuning to lead vocal")
    vocal_autotune_log_path = analysis_dir / "vocal_autotune_log.csv"

    log_mem("before_vocal_tuning")
    vocal_tuning_result = run_vocal_tuning_autotune(
        input_media_dir=loudness_media_dir,
        output_media_dir=vocal_tuning_media_dir,
        key_csv_path=key_csv_path,
        vocal_filename="vocal.wav",
    )
    log_mem("after_vocal_tuning")

    logger.info(
        "[6/7] Auto-Tune completado. Shift min=%.2f, max=%.2f, mean=%.2f semitonos",
        vocal_tuning_result.shift_semitones_min,
        vocal_tuning_result.shift_semitones_max,
        vocal_tuning_result.shift_semitones_mean,
    )

    export_vocal_autotune_log(vocal_tuning_result, vocal_autotune_log_path)
    logger.info("[6/7] Log de Auto-Tune exportado a %s", vocal_autotune_log_path)
    logger.info("[TIMER] AutoTune: %.2f s", time.perf_counter() - t0)

    # ------------------------------------------------------------------
    # 7. Mixdown a full_song.wav
    # ------------------------------------------------------------------
    logger.info("[7/7] Iniciando mixdown final desde %s", dynamics_media_dir)
    _report(7, "mixdown", "Rendering final full mix")

    log_mem("before_mixdown")
    full_song_render: FullSongRenderResult = mix_corrected_stems_to_full_song(
        output_media_dir=dynamics_media_dir,
        full_song_name="full_song.wav",
    )
    log_mem("after_mixdown")


    logger.info(
        "[7/7] Mixdown completado. Output=%s | peak=%.2f dBFS | rms=%.2f dBFS",
        full_song_render.output_path,
        full_song_render.peak_dbfs,
        full_song_render.rms_dbfs,
    )

    metrics = FullPipelineMetrics(
        final_peak_dbfs=full_song_render.peak_dbfs,
        final_rms_dbfs=full_song_render.rms_dbfs,
        tempo_bpm=tempo_result.bpm,
        tempo_confidence=tempo_result.bpm_confidence,
        key=key_result.key,
        scale=key_result.scale,
        key_strength=key_result.strength,
        vocal_shift_min=vocal_tuning_result.shift_semitones_min,
        vocal_shift_max=vocal_tuning_result.shift_semitones_max,
        vocal_shift_mean=vocal_tuning_result.shift_semitones_mean,
    )

    logger.info("=== run_full_pipeline finalizado correctamente ===")

    return FullPipelineResult(
        full_song_path=full_song_render.output_path,
        temp_root=temp_root,
        input_media_dir=media_dir,
        dc_offset_media_dir=dc_offset_media_dir,
        loudness_media_dir=loudness_media_dir,
        spectral_media_dir=spectral_media_dir,
        dynamics_media_dir=dynamics_media_dir,
        vocal_tuning_media_dir=vocal_tuning_media_dir,
        metrics=metrics,
    )
