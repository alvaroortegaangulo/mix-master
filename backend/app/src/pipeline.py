from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import logging
import os
import psutil
import shutil
import time
from typing import Callable, Optional, Any, Dict, List
import json

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




def render_mixdown_for_stage(
    stage_label: str,
    stems_dir: Path,
    full_song_name: str = "full_song.wav",
) -> FullSongRenderResult:
    """
    Renderiza un full mix en la carpeta de stems indicada.

    - stage_label: nombre lógico de la etapa (para logs).
    - stems_dir: carpeta donde están los stems de esa etapa.
    - full_song_name: nombre del bounce dentro de esa carpeta.
    """
    logger.info("[MIXDOWN] %s -> %s (%s)", stage_label, stems_dir, full_song_name)
    log_mem(f"before_mixdown_{stage_label}")

    result = mix_corrected_stems_to_full_song(
        output_media_dir=stems_dir,
        full_song_name=full_song_name,
    )

    log_mem(f"after_mixdown_{stage_label}")
    logger.info(
        "[MIXDOWN] %s completado. Output=%s | peak=%.2f dBFS | rms=%.2f dBFS",
        stage_label,
        result.output_path,
        result.peak_dbfs,
        result.rms_dbfs,
    )
    return result


ProgressCallback = Callable[[int, int, str, str], None]
# args: stage_index, total_stages, stage_key, message


# --------------------------------------------------------------------
# API pública para exponer la definición del pipeline al frontend
# --------------------------------------------------------------------

def get_pipeline_stages_definition() -> List[Dict[str, Any]]:
    """
    Devuelve una representación serializable de STAGES para el frontend.

    Cada elemento incluye:
      - key: identificador interno del stage (p.ej. "dc_offset").
      - label: etiqueta legible.
      - description: descripción corta.
      - index: orden 1-based dentro del pipeline.
      - mediaSubdir: subdirectorio dentro de temp_root/media para los stems.
      - updatesCurrentDir: si encadena el current_media_dir.
      - previewMixRelPath: ruta relativa (desde /files/{jobId}) al bounce de mezcla
        representativo de esta etapa, si existe (si no, None).
    """
    result: List[Dict[str, Any]] = []

    for idx, s in enumerate(STAGES, start=1):
        key = s.get("key")
        media_subdir = s.get("media_subdir")
        updates_current_dir = bool(s.get("updates_current_dir", False))

        # Si la etapa tiene carpeta de media, asumimos que allí habrá un full_song.wav
        preview_relpath: str | None = None
        if media_subdir:
            preview_relpath = f"/work/media/{media_subdir}/full_song.wav"

        result.append(
            {
                "key": key,
                "label": s.get("label", key),
                "description": s.get("description", ""),
                "index": idx,
                "mediaSubdir": media_subdir,
                "updatesCurrentDir": updates_current_dir,
                "previewMixRelPath": preview_relpath,
            }
        )

    return result



# --------------------------------------------------------------------
# Definición de STAGES (orden, rutas y parámetros)
# --------------------------------------------------------------------

STAGES: List[Dict[str, Any]] = [
    {
        "key": "dc_offset",
        "label": "DC Offset",
        "description": "Analyzing and correcting DC offset",
        "media_subdir": "dc_offset",
        "updates_current_dir": True,
        "analysis_csv": "dc_offset_analysis.csv",
    },
    {
        "key": "loudness",
        "label": "Loudness",
        "description": "Analyzing and normalizing loudness per stem",
        "media_subdir": "loudness",
        "updates_current_dir": True,
        "analysis_csv": "loudness_analysis.csv",
        "target_rms_dbfs": -18.0,
    },
    {
        "key": "static_mix_eq",
        "label": "Static Mix EQ",
        "description": "Applying spectral cleanup and subtractive EQ",
        "media_subdir": "static_mix_eq",
        "updates_current_dir": True,
        "analysis_csv": "spectral_cleanup_analysis.csv",
        "max_notches": 4,
    },
    {
        "key": "static_mix_dyn",
        "label": "Static Mix Dynamics",
        "description": "Applying per-track compression and limiting",
        "media_subdir": "static_mix_dyn",
        "updates_current_dir": True,
        "analysis_csv": "dynamics_analysis.csv",
    },
    {
        "key": "tempo_key",
        "label": "Tempo & Key",
        "description": "Analyzing tempo and musical key",
        "media_subdir": None,          # no crea nuevo directorio de stems
        "updates_current_dir": False,  # no cambia el current_media_dir
        "analysis_csv": "key_analysis.csv",
    },
    {
        "key": "vocal_tuning",
        "label": "Vocal Tuning",
        "description": "Applying vocal tuning to lead vocal",
        "media_subdir": "vocal_tuning",
        "updates_current_dir": False,  # generamos solo la voz afinada, no cambia el dir base de stems
        "log_csv": "vocal_autotune_log.csv",
        "vocal_filename": "vocal.wav",
    },
    {
        "key": "space_depth",
        "label": "Space & Depth",
        "description": "Creating buses and applying room/plate/hall/spring FX",
        "media_subdir": "space_depth",
        "updates_current_dir": True,
        "analysis_csv": "space_depth_analysis.csv",
    },
    {
        "key": "multiband_eq",
        "label": "Multiband EQ & Dynamics",
        "description": "Three-band compression/EQ per stem (low/mid/high)",
        "media_subdir": "multiband_eq",
        "updates_current_dir": True,
        "analysis_csv": "multiband_eq_analysis.csv",
        "low_mid_crossover_hz": 120.0,
        "mid_high_crossover_hz": 5000.0,
    },
    {
        "key": "mastering",
        "label": "Mixdown & Mastering",
        "description": "Rendering final full mix and mastering from stems",
        "media_subdir": "mastering",
        "updates_current_dir": False,  # pipeline termina aquí
        "analysis_csv": "mastering_analysis.csv",
        "vocal_stage_key": "vocal_tuning",
        "vocal_filename": "vocal.wav",
        "original_mix_name": "original_full_song.wav",
        "premaster_name": "full_song.wav",
        "mastered_name": "full_song.wav",  # se usa este nombre en render_mixdown_for_stage

        # --- NUEVO: configuración de mix-bus color ---
        "mix_bus_color_enable": True,
        "mix_bus_color_analysis_csv": "mix_bus_color_analysis.csv",
        "mix_bus_color_log_csv": "mix_bus_color_log.csv",

        # Rutas relativas al project_root; pon aquí tus IRs reales o déjalas a None
        "mix_bus_tape_ir": None,     # ej: "irs/mixbus/tape_a.wav"
        "mix_bus_console_ir": None,  # ej: "irs/mixbus/console_a.wav"

        # Lista de VST3 opcionales (rutas relativas o absolutas)
        "mix_bus_vst3_plugins": [
            # "vst3/DeEsser.vst3",
            # "vst3/TapeSaturator.vst3",
        ],
    },

]


# --------------------------------------------------------------------
# Imports de módulos de análisis / corrección
# --------------------------------------------------------------------

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
from src.analysis.mastering_analysis import analyze_mastering, export_mastering_to_csv
from src.stages.stage10_mastering.mastering_correction import run_mastering_correction
from src.utils.mixdown import mix_corrected_stems_to_full_song, FullSongRenderResult
from src.stages.stage3_space_depth_buses.space_depth import run_space_depth
from src.analysis.multiband_eq_analysis import (
    analyze_multiband_eq,
    export_multiband_eq_to_csv,
)
from src.stages.stage4_multiband_eq.multiband_eq_correction import (
    run_multiband_eq_correction,
)
from src.analysis.mix_bus_color_analysis import (
    analyze_mix_bus_color,
    export_mix_bus_color_to_csv,
)
from src.stages.stage11_mix_bus_color.mix_bus_color_correction import (
    run_mix_bus_color_correction,
)



# --------------------------------------------------------------------
# Dataclasses de salida
# --------------------------------------------------------------------


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

    original_full_song_path: Path
    full_song_path: Path

    temp_root: Path
    input_media_dir: Path

    dc_offset_media_dir: Path
    loudness_media_dir: Path
    spectral_media_dir: Path
    dynamics_media_dir: Path
    vocal_tuning_media_dir: Path

    metrics: FullPipelineMetrics


@dataclass
class PipelineContext:
    """
    Contexto mutable compartido por todos los stages.
    - stage_media_dirs: mapea stage_key -> ruta de media de ese stage (si aplica).
    - current_media_dir: dir con stems "actuales" (se va encadenando).
    """

    project_root: Path
    media_dir: Path
    temp_root: Path
    analysis_dir: Path

    stage_media_dirs: Dict[str, Path]
    current_media_dir: Path

    stem_profiles: Dict[str, str]
    bus_styles: Dict[str, str]  # p.ej. {"drums": "flamenco_rumba", "lead_vocal": "urban_trap"}

    tempo_result: Any | None = None
    key_result: Any | None = None
    vocal_tuning_result: Any | None = None

    original_full_song_render: FullSongRenderResult | None = None
    mastered_full_song_render: FullSongRenderResult | None = None
    static_mix_dyn_render: FullSongRenderResult | None = None 

# --------------------------------------------------------------------
# Implementación de cada stage con firma genérica:
#   stage_X(ctx, stage_conf, input_dir, output_dir)
# --------------------------------------------------------------------


def stage_dc_offset(
    ctx: PipelineContext,
    stage_conf: Dict[str, Any],
    input_dir: Path,
    output_dir: Path,
) -> None:
    analysis_csv = ctx.analysis_dir / stage_conf.get("analysis_csv", "dc_offset_analysis.csv")

    logger.info("Iniciando análisis de DC offset en %s", input_dir)
    log_mem("before_dc_offset_analysis")

    dc_offset_results = detect_dc_offset(input_dir)

    log_mem("after_dc_offset_analysis")
    logger.info(
        "Análisis de DC offset completado (%s resultados)",
        getattr(dc_offset_results, "__len__", lambda: "n/a")(),
    )

    export_dc_offset_to_csv(dc_offset_results, analysis_csv)
    logger.info("CSV de DC offset exportado a %s", analysis_csv)

    log_mem("before_dc_offset_correction")
    run_dc_offset_correction(
        analysis_csv,
        input_dir,
        output_dir,
    )
    log_mem("after_dc_offset_correction")
    logger.info(
        "Corrección de DC offset aplicada. Stems corregidos en %s", output_dir
    )

    # Mixdown post-DC offset → media/dc_offset/full_song.wav
    dc_offset_mix = render_mixdown_for_stage(
        stage_label="dc_offset",
        stems_dir=output_dir,
    )




def stage_loudness(
    ctx: PipelineContext,
    stage_conf: Dict[str, Any],
    input_dir: Path,
    output_dir: Path,
) -> None:
    analysis_csv = ctx.analysis_dir / stage_conf.get("analysis_csv", "loudness_analysis.csv")
    target_rms_dbfs = float(stage_conf.get("target_rms_dbfs", -18.0))

    logger.info("Iniciando análisis de loudness por stem (target %.2f dBFS)", target_rms_dbfs)

    log_mem("before_loudness_analysis")
    loudness_results = analyze_loudness(
        media_dir=input_dir,
        target_rms_dbfs=target_rms_dbfs,
    )
    log_mem("after_loudness_analysis")

    logger.info(
        "Análisis de loudness completado (%s resultados)",
        getattr(loudness_results, "__len__", lambda: "n/a")(),
    )

    export_loudness_to_csv(loudness_results, analysis_csv)
    logger.info("CSV de loudness exportado a %s", analysis_csv)

    log_mem("before_loudness_correction")
    run_loudness_correction(
        analysis_csv,
        input_dir,
        output_dir,
        mode="rms",
    )
    log_mem("after_loudness_correction")
    logger.info(
        "Corrección de loudness aplicada. Stems normalizados en %s", output_dir
    )

    # Mixdown post-Loudness → media/loudness/full_song.wav
    loudness_mix = render_mixdown_for_stage(
        stage_label="loudness",
        stems_dir=output_dir,
    )




def stage_static_mix_eq(
    ctx: PipelineContext,
    stage_conf: Dict[str, Any],
    input_dir: Path,
    output_dir: Path,
) -> None:
    analysis_csv = ctx.analysis_dir / stage_conf.get(
        "analysis_csv", "spectral_cleanup_analysis.csv"
    )
    max_notches = int(stage_conf.get("max_notches", 4))

    logger.info("Iniciando análisis de limpieza espectral (static mix EQ) en %s", input_dir)

    log_mem("before_spectral_analysis")
    spectral_cleanup_results = analyze_spectral_cleanup(input_dir)
    log_mem("after_spectral_analysis")

    logger.info(
        "Análisis espectral completado (%s resultados)",
        getattr(spectral_cleanup_results, "__len__", lambda: "n/a")(),
    )

    export_spectral_cleanup_to_csv(spectral_cleanup_results, analysis_csv)
    logger.info(
        "CSV de limpieza espectral exportado a %s", analysis_csv
    )

    log_mem("before_spectral_correction")
    run_spectral_cleanup_correction(
        analysis_csv,
        input_dir,
        output_dir,
        max_notches=max_notches,
    )
    log_mem("after_spectral_correction")
    logger.info(
        "Corrección espectral aplicada. Stems EQ en %s", output_dir
    )

    # Mixdown post-Static Mix EQ → media/static_mix_eq/full_song.wav
    static_mix_eq_mix = render_mixdown_for_stage(
        stage_label="static_mix_eq",
        stems_dir=output_dir,
    )





def stage_static_mix_dyn(
    ctx: PipelineContext,
    stage_conf: Dict[str, Any],
    input_dir: Path,
    output_dir: Path,
) -> None:
    analysis_csv = ctx.analysis_dir / stage_conf.get(
        "analysis_csv", "dynamics_analysis.csv"
    )

    logger.info("Iniciando análisis de dinámica por pista (static mix dyn) en %s", input_dir)

    log_mem("before_dynamics_analysis")
    dynamics_results = analyze_dynamics(input_dir)
    log_mem("after_dynamics_analysis")

    logger.info(
        "Análisis de dinámica completado (%s resultados)",
        getattr(dynamics_results, "__len__", lambda: "n/a")(),
    )

    export_dynamics_to_csv(dynamics_results, analysis_csv)
    logger.info("CSV de dinámica exportado a %s", analysis_csv)

    log_mem("before_dynamics_correction")
    run_dynamics_correction(
        analysis_csv,
        input_dir,
        output_dir,
    )
    log_mem("after_dynamics_correction")

    logger.info(
        "Corrección de dinámica aplicada. Stems dinámicos en %s", output_dir
    )

    # Mixdown post-Static Mix Dynamics (pre-master) → media/static_mix_dyn/full_song.wav
    static_mix_dyn_mix = render_mixdown_for_stage(
        stage_label="static_mix_dyn",
        stems_dir=output_dir,
    )

    # Guardamos el pre-master (mix dinámico) en el contexto
    ctx.static_mix_dyn_render = static_mix_dyn_mix


def stage_tempo_key(
    ctx: PipelineContext,
    stage_conf: Dict[str, Any],
    input_dir: Path,
    output_dir: Path,
) -> None:
    """
    Stage de análisis puro. No altera stems (output_dir == input_dir).
    """
    analysis_csv = ctx.analysis_dir / stage_conf.get("analysis_csv", "key_analysis.csv")

    logger.info("Iniciando análisis de tempo y tonalidad usando %s", input_dir)

    log_mem("before_tempo_key")
    tempo_result = analyze_tempo(input_dir)
    key_result = analyze_key(input_dir)
    log_mem("after_tempo_key")

    ctx.tempo_result = tempo_result
    ctx.key_result = key_result

    logger.info(
        "Tempo detectado: %.2f BPM (conf=%.3f)",
        tempo_result.bpm,
        tempo_result.bpm_confidence,
    )
    logger.info(
        "Tonalidad detectada: %s %s (strength=%.3f)",
        key_result.key,
        key_result.scale,
        key_result.strength,
    )

    export_key_to_csv(key_result, analysis_csv)
    logger.info("CSV de tonalidad exportado a %s", analysis_csv)





def stage_vocal_tuning(
    ctx: PipelineContext,
    stage_conf: Dict[str, Any],
    input_dir: Path,
    output_dir: Path,
) -> None:
    """
    Stage de afinación vocal.
    - Lee stems desde input_dir (el current_media_dir en ese momento).
    - Escribe la voz afinada en output_dir (media/vocal_tuning).
    - No modifica current_media_dir (sólo añade un "sidecar" con la voz afinada).
    """
    log_csv_name = stage_conf.get("log_csv", "vocal_autotune_log.csv")
    vocal_filename = stage_conf.get("vocal_filename", "vocal.wav")
    key_csv_path = ctx.analysis_dir / "key_analysis.csv"
    vocal_autotune_log_path = ctx.analysis_dir / log_csv_name

    logger.info(
        "Iniciando Auto-Tune de la voz (input=%s, output=%s)", input_dir, output_dir
    )

    log_mem("before_vocal_tuning")
    vocal_tuning_result = run_vocal_tuning_autotune(
        input_media_dir=input_dir,
        output_media_dir=output_dir,
        key_csv_path=key_csv_path,
        vocal_filename=vocal_filename,
    )
    log_mem("after_vocal_tuning")

    ctx.vocal_tuning_result = vocal_tuning_result

    logger.info(
        "Auto-Tune completado. Shift min=%.2f, max=%.2f, mean=%.2f semitonos",
        vocal_tuning_result.shift_semitones_min,
        vocal_tuning_result.shift_semitones_max,
        vocal_tuning_result.shift_semitones_mean,
    )

    export_vocal_autotune_log(vocal_tuning_result, vocal_autotune_log_path)
    logger.info("Log de Auto-Tune exportado a %s", vocal_autotune_log_path)

    # ------------------------------------------------------------------
    # Mixdown específico con la voz afinada → media/vocal_tuning/full_song.wav
    # ------------------------------------------------------------------
    logger.info(
        "[6/7] Preparando mixdown con voz afinada en %s (stems desde %s)",
        output_dir,
        input_dir,
    )

    # Ya tenemos vocal_filename de stage_conf
    # Copiamos todos los stems dinámicos salvo la voz al directorio de vocal_tuning
    for stem_path in input_dir.glob("*.wav"):
        if stem_path.name.lower() == vocal_filename.lower():
            continue
        dest = output_dir / stem_path.name
        try:
            shutil.copy2(stem_path, dest)
        except Exception as exc:
            logger.warning(
                "No se pudo copiar stem %s a %s: %s",
                stem_path,
                dest,
                exc,
            )

    # En output_dir deben quedar todos los stems + vocal afinada
    vocal_tuning_mix = render_mixdown_for_stage(
        stage_label="vocal_tuning",
        stems_dir=output_dir,
    )



def stage_space_depth(
    ctx: PipelineContext,
    stage_conf: Dict[str, Any],
    input_dir: Path,
    output_dir: Path,
) -> None:
    """
    Stage de creación de buses de espacio (reverb/delay/modulación).
    - Lee los stems desde input_dir (salida de static_mix_dyn).
    - Usa ctx.stem_profiles para mapear cada stem a un bus.
    - Usa ctx.bus_styles para aplicar presets de estilo por bus.
    - Usa ctx.tempo_result (si existe) para alinear pre-delay/delay al BPM.
    - Escribe stems con profundidad espacial en output_dir.
    """
    analysis_csv = ctx.analysis_dir / stage_conf.get(
        "analysis_csv", "space_depth_analysis.csv"
    )

    # BPM detectado en el stage tempo_key (si se ha ejecutado)
    tempo_bpm: Optional[float] = None
    if ctx.tempo_result is not None:
        try:
            tempo_bpm = float(ctx.tempo_result.bpm)
        except Exception as exc:
            logger.warning(
                "No se pudo leer BPM desde ctx.tempo_result: %s", exc
            )

    logger.info(
        "Iniciando Space & Depth (buses de reverb/delay/mod) en %s -> %s | bus_styles=%s | tempo_bpm=%s",
        input_dir,
        output_dir,
        ctx.bus_styles,
        tempo_bpm,
    )

    log_mem("before_space_depth")

    run_space_depth(
        input_media_dir=input_dir,
        output_media_dir=output_dir,
        analysis_csv_path=analysis_csv,
        stem_profiles=ctx.stem_profiles,
        bus_styles=ctx.bus_styles,
        tempo_bpm=tempo_bpm,           # <<< NUEVO: BPM real de la canción
        enable_audio_adaptive=True,    # <<< NUEVO: activar heurísticas audio-driven
    )

    log_mem("after_space_depth")

    logger.info(
        "Space & Depth completado. Stems procesados en %s, CSV en %s",
        output_dir,
        analysis_csv,
    )

    render_mixdown_for_stage(
        stage_label="space_depth",
        stems_dir=output_dir,
    )



def stage_multiband_eq(
    ctx: PipelineContext,
    stage_conf: Dict[str, Any],
    input_dir: Path,
    output_dir: Path,
) -> None:
    """
    Stage de multiband EQ / comp por stem (low/mid/high).
    - Lee los stems desde input_dir (salida de space_depth, con buses).
    - Escribe stems procesados en output_dir (media/multiband_eq).
    """
    analysis_csv = ctx.analysis_dir / stage_conf.get(
        "analysis_csv", "multiband_eq_analysis.csv"
    )

    low_mid_crossover_hz = float(
        stage_conf.get("low_mid_crossover_hz", 120.0)
    )
    mid_high_crossover_hz = float(
        stage_conf.get("mid_high_crossover_hz", 5000.0)
    )

    logger.info(
        "Iniciando análisis multibanda en %s (low_mid=%.1f Hz, mid_high=%.1f Hz)",
        input_dir,
        low_mid_crossover_hz,
        mid_high_crossover_hz,
    )

    log_mem("before_multiband_eq_analysis")
    multiband_results = analyze_multiband_eq(
        media_dir=input_dir,
        low_mid_crossover_hz=low_mid_crossover_hz,
        mid_high_crossover_hz=mid_high_crossover_hz,
    )
    log_mem("after_multiband_eq_analysis")

    logger.info(
        "Análisis multibanda completado (%s resultados)",
        getattr(multiband_results, "__len__", lambda: "n/a")(),
    )

    export_multiband_eq_to_csv(multiband_results, analysis_csv)
    logger.info("CSV de multiband EQ exportado a %s", analysis_csv)

    logger.info(
        "Aplicando corrección multibanda en %s -> %s",
        input_dir,
        output_dir,
    )
    log_mem("before_multiband_eq_correction")
    run_multiband_eq_correction(
        analysis_csv_path=analysis_csv,
        input_media_dir=input_dir,
        output_media_dir=output_dir,
        low_mid_crossover_hz=low_mid_crossover_hz,
        mid_high_crossover_hz=mid_high_crossover_hz,
    )
    log_mem("after_multiband_eq_correction")

    # Si quieres, puedes generar un bounce de preview:
    # render_mixdown_for_stage(
    #     stage_label="multiband_eq",
    #     stems_dir=output_dir,
    # )




def stage_mastering(
    ctx: PipelineContext,
    stage_conf: Dict[str, Any],
    input_dir: Path,
    output_dir: Path,
) -> None:
    """
    Stage final: mixdown (original + pre-master) + análisis y mastering por stems,
    + mixdown masterizado.
    - input_dir: current_media_dir (último stage "transform"), p.ej. static_mix_dyn.
    - output_dir: media/mastering.
    - también usa el directorio del stage 'vocal_tuning' si existe.
    """
    original_mix_name = stage_conf.get("original_mix_name", "original_full_song.wav")
    premaster_name = stage_conf.get("premaster_name", "full_song.wav")
    mastered_name = stage_conf.get("mastered_name", "full_song_mastered.wav")
    analysis_csv = ctx.analysis_dir / stage_conf.get("analysis_csv", "mastering_analysis.csv")
    vocal_stage_key = stage_conf.get("vocal_stage_key", "vocal_tuning")
    vocal_filename = stage_conf.get("vocal_filename", "vocal.wav")

    logger.info(
        "Iniciando mixdown final y mastering (input=%s, output=%s)",
        input_dir,
        output_dir,
    )

    # Mixdown original (stems de entrada sin procesar)
    original_full_song_render: FullSongRenderResult = render_mixdown_for_stage(
        stage_label="original",
        stems_dir=ctx.media_dir,
        full_song_name=original_mix_name,
    )

    log_mem("after_original_mixdown")
    ctx.original_full_song_render = original_full_song_render

    # Mixdown estático (pre-master) ya se ha renderizado en la etapa 4, si todo va bien
    if ctx.static_mix_dyn_render is not None:
        full_song_render: FullSongRenderResult = ctx.static_mix_dyn_render
        logger.info(
            "[7/7] Mixdown estático (pre-master) reutilizado. Output=%s | peak=%.2f dBFS | rms=%.2f dBFS",
            full_song_render.output_path,
            full_song_render.peak_dbfs,
            full_song_render.rms_dbfs,
        )
    else:
        # Fallback: lo generamos aquí a partir de input_dir
        full_song_render = render_mixdown_for_stage(
            stage_label="static_mix_dyn",
            stems_dir=input_dir,
            full_song_name=premaster_name,
        )
        logger.info(
            "[7/7] Mixdown estático (pre-master) generado en mastering. Output=%s | peak=%.2f dBFS | rms=%.2f dBFS",
            full_song_render.output_path,
            full_song_render.peak_dbfs,
            full_song_render.rms_dbfs,
        )


    # Directorio de voz afinada (si existe)
    vocal_tuning_media_dir = ctx.stage_media_dirs.get(vocal_stage_key, input_dir)

    # Análisis de mastering
    logger.info(
        "Iniciando análisis de mastering sobre stems dinámicos (%s) + voz afinada (%s)",
        input_dir,
        vocal_tuning_media_dir,
    )
    log_mem("before_mastering_analysis")
    mastering_results = analyze_mastering(
        media_dir=input_dir,
        vocal_tuning_media_dir=vocal_tuning_media_dir,
        vocal_filename=vocal_filename,
    )
    log_mem("after_mastering_analysis")

    logger.info(
        "Análisis de mastering completado (%s resultados)",
        getattr(mastering_results, "__len__", lambda: "n/a")(),
    )

    export_mastering_to_csv(mastering_results, analysis_csv)
    logger.info("CSV de mastering exportado a %s", analysis_csv)

    # Corrección de mastering (por stems)
    logger.info("Aplicando mastering por stems en %s", output_dir)
    log_mem("before_mastering_correction")
    run_mastering_correction(
        analysis_csv_path=analysis_csv,
        input_media_dir=input_dir,
        vocal_tuning_media_dir=vocal_tuning_media_dir,
        output_media_dir=output_dir,
        vocal_filename=vocal_filename,
    )
    log_mem("after_mastering_correction")

    # Mixdown final masterizado → media/mastering/full_song.wav
    mastered_full_song_render: FullSongRenderResult = render_mixdown_for_stage(
        stage_label="mastering",
        stems_dir=output_dir,
        full_song_name="full_song.wav",
    )

    log_mem("after_mastered_mixdown")

    # ------------------------------------------------------------------
    # Mix-bus color: saturación + IRs + VST3 sobre el full mix final
    # ------------------------------------------------------------------
    if stage_conf.get("mix_bus_color_enable", True):
        logger.info(
            "Iniciando mix-bus color sobre full mix: %s",
            mastered_full_song_render.output_path,
        )

        mix_bus_analysis_csv = ctx.analysis_dir / stage_conf.get(
            "mix_bus_color_analysis_csv",
            "mix_bus_color_analysis.csv",
        )
        mix_bus_log_csv = ctx.analysis_dir / stage_conf.get(
            "mix_bus_color_log_csv",
            "mix_bus_color_log.csv",
        )

        # 1) Análisis del full mix para decidir HPF/drive/mix de IRs
        log_mem("before_mix_bus_color_analysis")
        mix_bus_result = analyze_mix_bus_color(mastered_full_song_render.output_path)
        export_mix_bus_color_to_csv(mix_bus_result, mix_bus_analysis_csv)
        log_mem("after_mix_bus_color_analysis")
        logger.info(
            "Mix-bus color analysis completo. peak=%.2f dBFS | rms=%.2f dBFS | crest=%.2f dB | drive=%.2f dB",
            mix_bus_result.peak_dbfs,
            mix_bus_result.rms_dbfs,
            mix_bus_result.crest_factor_db,
            mix_bus_result.recommended_saturation_drive_db,
        )

        # 2) Resolución de rutas de IRs / VST3
        tape_ir_rel = stage_conf.get("mix_bus_tape_ir")
        console_ir_rel = stage_conf.get("mix_bus_console_ir")
        vst3_conf = stage_conf.get("mix_bus_vst3_plugins") or []

        tape_ir_path = (
            (ctx.project_root / tape_ir_rel).resolve()
            if tape_ir_rel
            else None
        )
        console_ir_path = (
            (ctx.project_root / console_ir_rel).resolve()
            if console_ir_rel
            else None
        )

        vst3_paths: List[Path] = []
        for p in vst3_conf:
            p_path = Path(p)
            if not p_path.is_absolute():
                p_path = (ctx.project_root / p).resolve()
            vst3_paths.append(p_path)

        # 3) Corrección: HPF + IRs + saturación + VST3 + limiter
        log_mem("before_mix_bus_color_correction")
        mix_bus_corr_result = run_mix_bus_color_correction(
            analysis_csv_path=mix_bus_analysis_csv,
            log_csv_path=mix_bus_log_csv,
            tape_ir_path=tape_ir_path,
            console_ir_path=console_ir_path,
            vst3_plugin_paths=vst3_paths,
            overwrite=True,
            output_path=mastered_full_song_render.output_path,  # procesamos in-place
        )
        log_mem("after_mix_bus_color_correction")

        logger.info(
            "Mix-bus color aplicado. peak: %.2f -> %.2f dBFS | rms: %.2f -> %.2f dBFS",
            mix_bus_corr_result.original_peak_dbfs,
            mix_bus_corr_result.resulting_peak_dbfs,
            mix_bus_corr_result.original_rms_dbfs,
            mix_bus_corr_result.resulting_rms_dbfs,
        )

        # Actualizamos métricas del render final para que run_full_pipeline
        # use los valores ya coloreados.
        mastered_full_song_render.peak_dbfs = mix_bus_corr_result.resulting_peak_dbfs
        mastered_full_song_render.rms_dbfs = mix_bus_corr_result.resulting_rms_dbfs


    ctx.mastered_full_song_render = mastered_full_song_render

    logger.info(
        "Mastering mixdown completado. Output=%s | peak=%.2f dBFS | rms=%.2f dBFS",
        mastered_full_song_render.output_path,
        mastered_full_song_render.peak_dbfs,
        mastered_full_song_render.rms_dbfs,
    )


# Mapa clave → función para dispatch dinámico, todas con firma genérica
STAGE_RUNNERS: Dict[str, Callable[[PipelineContext, Dict[str, Any], Path, Path], None]] = {
    "dc_offset": stage_dc_offset,
    "loudness": stage_loudness,
    "static_mix_eq": stage_static_mix_eq,
    "static_mix_dyn": stage_static_mix_dyn,
    "tempo_key": stage_tempo_key,
    "vocal_tuning": stage_vocal_tuning,
    "space_depth": stage_space_depth,
    "multiband_eq": stage_multiband_eq,
    "mastering": stage_mastering,
}


# --------------------------------------------------------------------
# Función genérica reutilizable para todos los stages
# --------------------------------------------------------------------


def execute_stage(
    index: int,
    total_stages: int,
    stage_conf: Dict[str, Any],
    ctx: PipelineContext,
    progress_callback: Optional[ProgressCallback] = None,
) -> None:
    """
    Ejecuta un stage de forma genérica:
      - Determina input_dir = ctx.current_media_dir.
      - Determina output_dir según 'media_subdir' (o reutiliza input_dir).
      - Lanza el runner correspondiente vía STAGE_RUNNERS.
      - Actualiza stage_media_dirs y current_media_dir según 'updates_current_dir'.
    """
    key = stage_conf["key"]
    label = stage_conf.get("label", key)
    description = stage_conf.get("description", "")

    logger.info("[%d/%d] %s - %s", index, total_stages, key, label)

    if progress_callback:
        progress_callback(index, total_stages, key, description)

    input_dir = ctx.current_media_dir
    media_subdir = stage_conf.get("media_subdir")
    updates_current_dir = bool(stage_conf.get("updates_current_dir", False))

    if media_subdir:
        output_dir = ctx.temp_root / "media" / media_subdir
        output_dir.mkdir(parents=True, exist_ok=True)
    else:
        output_dir = input_dir  # stage solo de análisis

    runner = STAGE_RUNNERS.get(key)
    if runner is None:
        logger.warning("No hay runner configurado para stage key=%s, se omite", key)
        return

    log_mem(f"{key}_start")
    t0 = time.perf_counter()
    runner(ctx, stage_conf, input_dir, output_dir)
    t1 = time.perf_counter()
    logger.info("[TIMER] %s: %.2f s", key, t1 - t0)
    log_mem(f"{key}_end")

    if media_subdir:
        ctx.stage_media_dirs[key] = output_dir

    if updates_current_dir:
        ctx.current_media_dir = output_dir



# --------------------------------------------------------------------
# Entry point principal
# --------------------------------------------------------------------


def run_full_pipeline(
    project_root: Path,
    media_dir: Path,
    temp_root: Path,
    progress_callback: Optional[ProgressCallback] = None,
    enabled_stage_keys: Optional[List[str]] = None,
    stem_profiles: Optional[Dict[str, str]] = None,
    bus_styles: Optional[Dict[str, str]] = None,
) -> FullPipelineResult:
    """
    Ejecuta TODO el pipeline de mezcla sobre los stems de media_dir,
    utilizando STAGES para ordenar y describir cada fase.

    Si enabled_stage_keys no es None ni vacío, solo se ejecutan los
    stages cuya 'key' esté en esa lista (respetando el orden de STAGES).
    """

    logger.info("=== Iniciando run_full_pipeline ===")
    logger.info("project_root=%s", project_root)
    logger.info("media_dir=%s", media_dir)
    logger.info("temp_root=%s", temp_root)

    # Directorio de análisis (compartido por todos los stages)
    analysis_dir = temp_root / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    logger.info("analysis_dir = %s", analysis_dir)
    log_mem("start_pipeline")


    # Contexto inicial
    ctx = PipelineContext(
        project_root=project_root,
        media_dir=media_dir,
        temp_root=temp_root,
        analysis_dir=analysis_dir,
        stage_media_dirs={},
        current_media_dir=media_dir,
        stem_profiles=stem_profiles or {},
        bus_styles=bus_styles or {},
    )

    # Filtrado de stages según enabled_stage_keys
    if enabled_stage_keys:
        enabled_set = set(enabled_stage_keys)
        stages_to_run = [s for s in STAGES if s["key"] in enabled_set]
    else:
        stages_to_run = STAGES

    total_stages = len(stages_to_run)
    if total_stages == 0:
        raise RuntimeError("No hay stages seleccionados para ejecutar el pipeline.")

    if progress_callback:
        progress_callback(0, total_stages, "start", "Starting pipeline")

    # Ejecución secuencial vía execute_stage
    for idx, stage_conf in enumerate(stages_to_run, start=1):
        execute_stage(idx, total_stages, stage_conf, ctx, progress_callback)

    # Validación mínima de resultados imprescindibles
    if (
        ctx.tempo_result is None
        or ctx.key_result is None
        or ctx.vocal_tuning_result is None
        or ctx.mastered_full_song_render is None
        or ctx.original_full_song_render is None
    ):
        raise RuntimeError(
            "Pipeline incompleto: faltan resultados de alguna etapa crítica "
            "(tempo/key, vocal_tuning o mastering)."
        )

    tempo_result = ctx.tempo_result
    key_result = ctx.key_result
    vocal_tuning_result = ctx.vocal_tuning_result
    mastered_full_song_render = ctx.mastered_full_song_render
    original_full_song_render = ctx.original_full_song_render

    # Reconstruimos rutas tipo "*_media_dir" a partir de stage_media_dirs
    dc_offset_media_dir = ctx.stage_media_dirs.get("dc_offset", media_dir)
    loudness_media_dir = ctx.stage_media_dirs.get("loudness", dc_offset_media_dir)
    spectral_media_dir = ctx.stage_media_dirs.get(
        "static_mix_eq", loudness_media_dir
    )
    dynamics_media_dir = ctx.stage_media_dirs.get(
        "static_mix_dyn", spectral_media_dir
    )
    vocal_tuning_media_dir = ctx.stage_media_dirs.get(
        "vocal_tuning", loudness_media_dir
    )

    metrics = FullPipelineMetrics(
        final_peak_dbfs=mastered_full_song_render.peak_dbfs,
        final_rms_dbfs=mastered_full_song_render.rms_dbfs,
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
        original_full_song_path=original_full_song_render.output_path,
        full_song_path=mastered_full_song_render.output_path,
        temp_root=temp_root,
        input_media_dir=media_dir,
        dc_offset_media_dir=dc_offset_media_dir,
        loudness_media_dir=loudness_media_dir,
        spectral_media_dir=spectral_media_dir,
        dynamics_media_dir=dynamics_media_dir,
        vocal_tuning_media_dir=vocal_tuning_media_dir,
        metrics=metrics,
    )
