from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import logging
import os
import psutil
import shutil
import time
from typing import Callable, Optional, Any, Dict, List

# Configuración básica de logging si nadie la ha configurado aún
logger = logging.getLogger(__name__)
if not logging.getLogger().hasHandlers():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

_process = psutil.Process(os.getpid())


def log_mem(label: str) -> None:
    """Log sencillo de memoria residente, en MB."""
    try:
        mem_mb = _process.memory_info().rss / (1024 * 1024)
        logger.info("[MEM] %s: %.1f MB", label, mem_mb)
    except Exception as exc:
        logger.warning("No se pudo leer memoria en %s: %s", label, exc)


def log_stage_banner(
    stage_key: str,
    stage_label: str,
    description: str,
    index: int,
    total: int,
    input_dir: Path,
    output_dir: Path,
) -> None:
    """Cabecera consistente por stage para que los logs sean faciles de seguir."""
    desc_suffix = f" - {description}" if description else ""
    logger.info("[STAGE %d/%d] %s%s", index, total, stage_label, desc_suffix)
    logger.info("[STAGE %s] in=%s | out=%s", stage_key, input_dir, output_dir)


def log_stage_event(stage_key: str, step: str, message: str, *args) -> None:
    """Prefijo consistente [stage][paso] para cada sub-tarea."""
    logger.info("[%s][%s] " + message, stage_key, step, *args)


def log_stage_memory(stage_key: str, label: str) -> None:
    """Atajo para loguear memoria con el prefijo del stage."""
    log_mem(f"{stage_key}_{label}")




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
        "analysis_json": "dc_offset_analysis.json",
    },
    {
        "key": "loudness",
        "label": "Loudness",
        "description": "Analyzing and normalizing loudness per stem",
        "media_subdir": "loudness",
        "updates_current_dir": True,
        "analysis_json": "loudness_analysis.json",
        "target_rms_dbfs": -18.0,
    },
    {
        "key": "static_mix_eq",
        "label": "Static Mix EQ",
        "description": "Applying spectral cleanup and subtractive EQ",
        "media_subdir": "static_mix_eq",
        "updates_current_dir": True,
        "analysis_json": "spectral_cleanup_analysis.json",
        "max_notches": 4,
    },
    {
        "key": "static_mix_dyn",
        "label": "Static Mix Dynamics",
        "description": "Applying per-track compression and limiting",
        "media_subdir": "static_mix_dyn",
        "updates_current_dir": True,
        "analysis_json": "dynamics_analysis.json",
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
        "analysis_json": "space_depth_analysis.json",
    },
    {
        "key": "multiband_eq",
        "label": "Multiband EQ & Dynamics",
        "description": "Three-band compression/EQ per stem (low/mid/high)",
        "media_subdir": "multiband_eq",
        "updates_current_dir": True,
        "analysis_json": "multiband_eq_analysis.json",
        "low_mid_crossover_hz": 120.0,
        "mid_high_crossover_hz": 5000.0,
    },
    {
        "key": "mastering",
        "label": "Mixdown & Mastering",
        "description": "Rendering final full mix and mastering from stems",
        "media_subdir": "mastering",
        "updates_current_dir": False,  # pipeline termina aquí
        "analysis_json": "mastering_analysis.json",
        "vocal_stage_key": "vocal_tuning",
        "vocal_filename": "vocal.wav",
        "original_mix_name": "original_full_song.wav",
        "premaster_name": "full_song.wav",
        "mastered_name": "full_song.wav",  # se usa este nombre en render_mixdown_for_stage

        # --- NUEVO: Master Stereo (M/S) ---
        "master_stereo_enable": True,
        "master_stereo_analysis_json": "master_stereo_analysis.json",
        "master_stereo_log_json": "master_stereo_log.json",
        # IR opcional para el campo Side (room/cab, etc.) relativa a project_root
        "master_stereo_side_ir": None,  # ej: "irs/stereo/side_room.wav"
        # Si None → usa el mix recomendado por el análisis
        "master_stereo_side_ir_mix_override": None,

        # --- NUEVO: configuración de mix-bus color ---
        "mix_bus_color_enable": True,
        "mix_bus_color_analysis_json": "mix_bus_color_analysis.json",
        "mix_bus_color_log_json": "mix_bus_color_log.json",

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

from src.analysis.dc_offset_detection import detect_dc_offset, export_dc_offset_to_json
from src.stages.stage0_technical_preparation.dc_offset_correction import run_dc_offset_correction
from src.analysis.loudness_analysis import analyze_loudness, export_loudness_to_json
from src.stages.stage0_technical_preparation.loudness_correction import run_loudness_correction
from src.analysis.spectral_cleanup_analysis import analyze_spectral_cleanup, export_spectral_cleanup_to_json
from src.stages.stage1_static_mix.spectral_cleanup_correction import run_spectral_cleanup_correction
from src.analysis.dynamics_analysis import analyze_dynamics, export_dynamics_to_json
from src.stages.stage2_dynamics.dynamics_correction import run_dynamics_correction
from src.analysis.tempo_analysis import analyze_tempo
from src.analysis.key_analysis import analyze_key, export_key_to_csv
from src.stages.stage0_technical_preparation.vocal_tuning import (
    run_vocal_tuning_autotune,
    export_vocal_autotune_log,
)
from src.analysis.mastering_analysis import analyze_mastering, export_mastering_to_json
from src.stages.stage10_mastering.mastering_correction import run_mastering_correction
from src.utils.mixdown import mix_corrected_stems_to_full_song, FullSongRenderResult
from src.analysis.space_depth_analysis import (
    analyze_space_depth,
    export_space_depth_to_json,
)
from src.stages.stage3_space_depth_buses.space_depth import run_space_depth
from src.analysis.multiband_eq_analysis import (
    analyze_multiband_eq,
    export_multiband_eq_to_json,
)
from src.stages.stage4_multiband_eq.multiband_eq_correction import (
    run_multiband_eq_correction,
)
from src.analysis.mix_bus_color_analysis import (
    analyze_mix_bus_color,
    export_mix_bus_color_to_json,
)
from src.stages.stage12_mix_bus_color.mix_bus_color_correction import (
    run_mix_bus_color_correction,
)
from src.analysis.master_stereo_analysis import (
    analyze_master_stereo,
    export_master_stereo_to_json,
)
from src.stages.stage11_master_stereo.master_stereo_correction import (
    run_master_stereo_correction,
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
    """Detecta y corrige DC offset, guardando analisis y bounce."""
    stage_key = 'dc_offset'
    analysis_path = ctx.analysis_dir / stage_conf.get('analysis_json', 'dc_offset_analysis.json')

    log_stage_event(stage_key, 'analysis', 'Detectando DC offset en %s', input_dir)
    log_stage_memory(stage_key, 'analysis_start')
    dc_offset_results = detect_dc_offset(input_dir)
    log_stage_memory(stage_key, 'analysis_end')

    results_len = getattr(dc_offset_results, '__len__', lambda: 'n/a')()
    log_stage_event(stage_key, 'analysis', 'Resultados: %s filas', results_len)
    export_dc_offset_to_json(dc_offset_results, analysis_path)
    log_stage_event(stage_key, 'analysis', 'JSON guardado en %s', analysis_path)

    log_stage_event(stage_key, 'correction', 'Aplicando correccion -> %s', output_dir)
    log_stage_memory(stage_key, 'correction_start')
    run_dc_offset_correction(analysis_path, input_dir, output_dir)
    log_stage_memory(stage_key, 'correction_end')

    log_stage_event(stage_key, 'mixdown', 'Renderizando referencia post stage')
    render_mixdown_for_stage(stage_label=stage_key, stems_dir=output_dir)


def stage_loudness(
    ctx: PipelineContext,
    stage_conf: Dict[str, Any],
    input_dir: Path,
    output_dir: Path,
) -> None:
    """Normaliza loudness por stem y deja bounce de control."""
    stage_key = 'loudness'
    analysis_path = ctx.analysis_dir / stage_conf.get('analysis_json', 'loudness_analysis.json')
    target_rms_dbfs = float(stage_conf.get('target_rms_dbfs', -18.0))

    log_stage_event(stage_key, 'analysis', 'Analizando loudness target %.2f dBFS en %s', target_rms_dbfs, input_dir)
    log_stage_memory(stage_key, 'analysis_start')
    loudness_results = analyze_loudness(media_dir=input_dir, target_rms_dbfs=target_rms_dbfs)
    log_stage_memory(stage_key, 'analysis_end')

    results_len = getattr(loudness_results, '__len__', lambda: 'n/a')()
    log_stage_event(stage_key, 'analysis', 'Resultados: %s filas', results_len)
    export_loudness_to_json(loudness_results, analysis_path)
    log_stage_event(stage_key, 'analysis', 'JSON guardado en %s', analysis_path)

    log_stage_event(stage_key, 'correction', 'Aplicando normalizado RMS -> %s', output_dir)
    log_stage_memory(stage_key, 'correction_start')
    run_loudness_correction(analysis_path, input_dir, output_dir, mode='rms')
    log_stage_memory(stage_key, 'correction_end')

    log_stage_event(stage_key, 'mixdown', 'Renderizando bounce post-loudness')
    render_mixdown_for_stage(stage_label=stage_key, stems_dir=output_dir)



def stage_static_mix_eq(
    ctx: PipelineContext,
    stage_conf: Dict[str, Any],
    input_dir: Path,
    output_dir: Path,
) -> None:
    """Limpieza espectral y EQ sustractiva por stem."""
    stage_key = 'static_mix_eq'
    analysis_path = ctx.analysis_dir / stage_conf.get('analysis_json', 'spectral_cleanup_analysis.json')
    max_notches = int(stage_conf.get('max_notches', 4))

    log_stage_event(stage_key, 'analysis', 'Analizando limpieza espectral en %s', input_dir)
    log_stage_memory(stage_key, 'analysis_start')
    spectral_cleanup_results = analyze_spectral_cleanup(input_dir)
    log_stage_memory(stage_key, 'analysis_end')

    results_len = getattr(spectral_cleanup_results, '__len__', lambda: 'n/a')()
    log_stage_event(stage_key, 'analysis', 'Resultados: %s filas', results_len)
    export_spectral_cleanup_to_json(spectral_cleanup_results, analysis_path)
    log_stage_event(stage_key, 'analysis', 'JSON guardado en %s', analysis_path)

    log_stage_event(stage_key, 'correction', 'Aplicando EQ correctiva (max %d notches)', max_notches)
    log_stage_memory(stage_key, 'correction_start')
    run_spectral_cleanup_correction(analysis_path, input_dir, output_dir, max_notches=max_notches)
    log_stage_memory(stage_key, 'correction_end')

    log_stage_event(stage_key, 'mixdown', 'Renderizando bounce post-EQ')
    render_mixdown_for_stage(stage_label=stage_key, stems_dir=output_dir)



def stage_static_mix_dyn(
    ctx: PipelineContext,
    stage_conf: Dict[str, Any],
    input_dir: Path,
    output_dir: Path,
) -> None:
    """Analiza y aplica compresion/limitacion por pista."""
    stage_key = 'static_mix_dyn'
    analysis_path = ctx.analysis_dir / stage_conf.get('analysis_json', 'dynamics_analysis.json')

    log_stage_event(stage_key, 'analysis', 'Analizando dinamica en %s', input_dir)
    log_stage_memory(stage_key, 'analysis_start')
    dynamics_results = analyze_dynamics(media_dir=input_dir, stem_profiles=ctx.stem_profiles)
    log_stage_memory(stage_key, 'analysis_end')

    results_len = getattr(dynamics_results, '__len__', lambda: 'n/a')()
    log_stage_event(stage_key, 'analysis', 'Resultados: %s filas', results_len)
    export_dynamics_to_json(dynamics_results, analysis_path)
    log_stage_event(stage_key, 'analysis', 'JSON guardado en %s', analysis_path)

    log_stage_event(stage_key, 'correction', 'Aplicando correccion dinamica -> %s', output_dir)
    log_stage_memory(stage_key, 'correction_start')
    run_dynamics_correction(analysis_path, input_dir, output_dir)
    log_stage_memory(stage_key, 'correction_end')

    log_stage_event(stage_key, 'mixdown', 'Renderizando pre-master dinamico')
    ctx.static_mix_dyn_render = render_mixdown_for_stage(stage_label=stage_key, stems_dir=output_dir)



def stage_tempo_key(
    ctx: PipelineContext,
    stage_conf: Dict[str, Any],
    input_dir: Path,
    output_dir: Path,
) -> None:
    """Solo analisis de tempo y tonalidad (no modifica stems)."""
    stage_key = 'tempo_key'
    analysis_csv = ctx.analysis_dir / stage_conf.get('analysis_csv', 'key_analysis.csv')

    log_stage_event(stage_key, 'analysis', 'Analizando tempo y tonalidad en %s', input_dir)
    log_stage_memory(stage_key, 'analysis_start')
    tempo_result = analyze_tempo(input_dir)
    key_result = analyze_key(input_dir)
    log_stage_memory(stage_key, 'analysis_end')

    ctx.tempo_result = tempo_result
    ctx.key_result = key_result

    log_stage_event(stage_key, 'analysis', 'Tempo: %.2f BPM (conf=%.3f)', tempo_result.bpm, tempo_result.bpm_confidence)
    log_stage_event(stage_key, 'analysis', 'Key: %s %s (strength=%.3f)', key_result.key, key_result.scale, key_result.strength)

    export_key_to_csv(key_result, analysis_csv)
    log_stage_event(stage_key, 'analysis', 'CSV guardado en %s', analysis_csv)



def stage_vocal_tuning(
    ctx: PipelineContext,
    stage_conf: Dict[str, Any],
    input_dir: Path,
    output_dir: Path,
) -> None:
    """Afina la voz principal y deja mix con voz procesada."""
    stage_key = 'vocal_tuning'
    log_csv_name = stage_conf.get('log_csv', 'vocal_autotune_log.csv')
    vocal_filename = stage_conf.get('vocal_filename', 'vocal.wav')
    key_csv_path = ctx.analysis_dir / 'key_analysis.csv'
    vocal_autotune_log_path = ctx.analysis_dir / log_csv_name

    log_stage_event(stage_key, 'analysis', 'Auto-Tune de voz (in=%s, out=%s)', input_dir, output_dir)
    log_stage_memory(stage_key, 'analysis_start')
    vocal_tuning_result = run_vocal_tuning_autotune(
        input_media_dir=input_dir,
        output_media_dir=output_dir,
        key_csv_path=key_csv_path,
        vocal_filename=vocal_filename,
    )
    log_stage_memory(stage_key, 'analysis_end')

    ctx.vocal_tuning_result = vocal_tuning_result
    log_stage_event(stage_key, 'analysis', 'Shift min=%.2f max=%.2f mean=%.2f',
                    vocal_tuning_result.shift_semitones_min,
                    vocal_tuning_result.shift_semitones_max,
                    vocal_tuning_result.shift_semitones_mean)
    export_vocal_autotune_log(vocal_tuning_result, vocal_autotune_log_path)
    log_stage_event(stage_key, 'analysis', 'Log guardado en %s', vocal_autotune_log_path)

    # Copiamos stems dinamicos salvo la voz al directorio de vocal_tuning para generar el mix con voz afinada.
    for stem_path in input_dir.glob('*.wav'):
        if stem_path.name.lower() == vocal_filename.lower():
            continue
        dest = output_dir / stem_path.name
        try:
            shutil.copy2(stem_path, dest)
        except Exception as exc:
            logger.warning('No se pudo copiar stem %s a %s: %s', stem_path, dest, exc)

    log_stage_event(stage_key, 'mixdown', 'Renderizando mix con voz afinada')
    render_mixdown_for_stage(stage_label=stage_key, stems_dir=output_dir)



def stage_space_depth(
    ctx: PipelineContext,
    stage_conf: Dict[str, Any],
    input_dir: Path,
    output_dir: Path,
) -> None:
    """Genera buses y FX de espacio/profundidad segun analisis."""
    stage_key = 'space_depth'
    analysis_json = ctx.analysis_dir / stage_conf.get('analysis_json', 'space_depth_analysis.json')

    tempo_bpm = None
    if ctx.tempo_result is not None:
        try:
            tempo_bpm = float(ctx.tempo_result.bpm)
        except Exception as exc:
            logger.warning('No se pudo leer BPM desde ctx.tempo_result: %s', exc)

    log_stage_event(stage_key, 'analysis', 'Analizando espacio (tempo=%s, bus_styles=%s)', tempo_bpm, ctx.bus_styles)
    rows = analyze_space_depth(
        media_dir=input_dir,
        stem_profiles=ctx.stem_profiles,
        bus_styles=ctx.bus_styles,
        tempo_bpm=tempo_bpm,
        enable_audio_adaptive=True,
    )
    export_space_depth_to_json(rows, analysis_json)
    log_stage_event(stage_key, 'analysis', 'JSON guardado en %s', analysis_json)

    log_stage_event(stage_key, 'correction', 'Aplicando FX de espacio -> %s', output_dir)
    run_space_depth(input_media_dir=input_dir, output_media_dir=output_dir, analysis_json_path=analysis_json)

    log_stage_event(stage_key, 'mixdown', 'Renderizando bounce con buses')
    render_mixdown_for_stage(stage_label=stage_key, stems_dir=output_dir)



def stage_multiband_eq(
    ctx: PipelineContext,
    stage_conf: Dict[str, Any],
    input_dir: Path,
    output_dir: Path,
) -> None:
    """EQ y compresion multibanda por stem (low/mid/high)."""
    stage_key = 'multiband_eq'
    analysis_json = ctx.analysis_dir / stage_conf.get('analysis_json', 'multiband_eq_analysis.json')
    low_mid_crossover_hz = float(stage_conf.get('low_mid_crossover_hz', 120.0))
    mid_high_crossover_hz = float(stage_conf.get('mid_high_crossover_hz', 5000.0))

    log_stage_event(stage_key, 'analysis', 'Analizando multibanda en %s (%.1f/%.1f Hz)', input_dir, low_mid_crossover_hz, mid_high_crossover_hz)
    log_stage_memory(stage_key, 'analysis_start')
    multiband_results = analyze_multiband_eq(
        media_dir=input_dir,
        low_mid_crossover_hz=low_mid_crossover_hz,
        mid_high_crossover_hz=mid_high_crossover_hz,
    )
    log_stage_memory(stage_key, 'analysis_end')

    results_len = getattr(multiband_results, '__len__', lambda: 'n/a')()
    log_stage_event(stage_key, 'analysis', 'Resultados: %s filas', results_len)
    export_multiband_eq_to_json(multiband_results, analysis_json)
    log_stage_event(stage_key, 'analysis', 'JSON guardado en %s', analysis_json)

    log_stage_event(stage_key, 'correction', 'Aplicando correccion multibanda -> %s', output_dir)
    log_stage_memory(stage_key, 'correction_start')
    run_multiband_eq_correction(
        analysis_json_path=analysis_json,
        input_media_dir=input_dir,
        output_media_dir=output_dir,
        low_mid_crossover_hz=low_mid_crossover_hz,
        mid_high_crossover_hz=mid_high_crossover_hz,
    )
    log_stage_memory(stage_key, 'correction_end')

    # Mixdown opcional para preview
    # render_mixdown_for_stage(stage_label=stage_key, stems_dir=output_dir)



def stage_mastering(
    ctx: PipelineContext,
    stage_conf: Dict[str, Any],
    input_dir: Path,
    output_dir: Path,
) -> None:
    """Mixdown final, mastering por stems y color de mix-bus."""
    stage_key = 'mastering'
    original_mix_name = stage_conf.get('original_mix_name', 'original_full_song.wav')
    premaster_name = stage_conf.get('premaster_name', 'full_song.wav')
    mastered_name = stage_conf.get('mastered_name', 'full_song_mastered.wav')
    analysis_json = ctx.analysis_dir / stage_conf.get('analysis_json', 'mastering_analysis.json')
    vocal_stage_key = stage_conf.get('vocal_stage_key', 'vocal_tuning')
    vocal_filename = stage_conf.get('vocal_filename', 'vocal.wav')

    log_stage_event(stage_key, 'mixdown', 'Preparando original y pre-master')
    original_full_song_render = render_mixdown_for_stage(
        stage_label='original',
        stems_dir=ctx.media_dir,
        full_song_name=original_mix_name,
    )
    log_stage_memory(stage_key, 'after_original_mixdown')
    ctx.original_full_song_render = original_full_song_render

    if ctx.static_mix_dyn_render is not None:
        full_song_render: FullSongRenderResult = ctx.static_mix_dyn_render
        log_stage_event(stage_key, 'mixdown', 'Usando pre-master existente %s', full_song_render.output_path)
    else:
        full_song_render = render_mixdown_for_stage(
            stage_label='static_mix_dyn',
            stems_dir=input_dir,
            full_song_name=premaster_name,
        )
        log_stage_event(stage_key, 'mixdown', 'Pre-master generado en mastering')

    vocal_tuning_media_dir = ctx.stage_media_dirs.get(vocal_stage_key, input_dir)

    log_stage_event(stage_key, 'analysis', 'Analizando mastering (stems %s + voz %s)', input_dir, vocal_tuning_media_dir)
    log_stage_memory(stage_key, 'analysis_start')
    mastering_results = analyze_mastering(
        media_dir=input_dir,
        vocal_tuning_media_dir=vocal_tuning_media_dir,
        vocal_filename=vocal_filename,
    )
    log_stage_memory(stage_key, 'analysis_end')

    results_len = getattr(mastering_results, '__len__', lambda: 'n/a')()
    log_stage_event(stage_key, 'analysis', 'Resultados: %s filas', results_len)
    export_mastering_to_json(mastering_results, analysis_json)
    log_stage_event(stage_key, 'analysis', 'JSON guardado en %s', analysis_json)

    log_stage_event(stage_key, 'correction', 'Aplicando mastering por stems en %s', output_dir)
    log_stage_memory(stage_key, 'correction_start')
    run_mastering_correction(
        analysis_json_path=analysis_json,
        input_media_dir=input_dir,
        vocal_tuning_media_dir=vocal_tuning_media_dir,
        output_media_dir=output_dir,
        vocal_filename=vocal_filename,
    )
    log_stage_memory(stage_key, 'correction_end')

    mastered_full_song_render = render_mixdown_for_stage(
        stage_label='mastering',
        stems_dir=output_dir,
        full_song_name=mastered_name,
    )
    log_stage_memory(stage_key, 'after_mastered_mixdown')

    if stage_conf.get('master_stereo_enable', True):
        log_stage_event(stage_key, 'stereo', 'Analizando y aplicando Mid/Side')
        master_stereo_analysis_json = ctx.analysis_dir / stage_conf.get('master_stereo_analysis_json', 'master_stereo_analysis.json')
        master_stereo_log_json = ctx.analysis_dir / stage_conf.get('master_stereo_log_json', 'master_stereo_log.json')

        log_stage_memory(stage_key, 'master_stereo_analysis_start')
        ms_result = analyze_master_stereo(mastered_full_song_render.output_path)
        export_master_stereo_to_json(ms_result, master_stereo_analysis_json)
        log_stage_memory(stage_key, 'master_stereo_analysis_end')

        side_ir_rel = stage_conf.get('master_stereo_side_ir')
        side_ir_path = (ctx.project_root / side_ir_rel).resolve() if side_ir_rel else None
        side_ir_mix_override = stage_conf.get('master_stereo_side_ir_mix_override', None)

        log_stage_memory(stage_key, 'master_stereo_correction_start')
        ms_corr = run_master_stereo_correction(
            analysis_json_path=master_stereo_analysis_json,
            log_json_path=master_stereo_log_json,
            side_ir_path=side_ir_path,
            side_ir_mix_override=side_ir_mix_override,
            overwrite=True,
            output_path=mastered_full_song_render.output_path,
        )
        log_stage_memory(stage_key, 'master_stereo_correction_end')

        mastered_full_song_render.peak_dbfs = ms_corr.resulting_peak_dbfs
        mastered_full_song_render.rms_dbfs = ms_corr.resulting_rms_dbfs
        log_stage_event(stage_key, 'stereo', 'Mid/Side aplicado: peak %.2f, rms %.2f', ms_corr.resulting_peak_dbfs, ms_corr.resulting_rms_dbfs)

    if stage_conf.get('mix_bus_color_enable', True):
        log_stage_event(stage_key, 'mix_bus', 'Aplicando color de mix-bus')
        mix_bus_analysis_json = ctx.analysis_dir / stage_conf.get('mix_bus_color_analysis_json', 'mix_bus_color_analysis.json')
        mix_bus_log_json = ctx.analysis_dir / stage_conf.get('mix_bus_color_log_json', 'mix_bus_color_log.json')

        log_stage_memory(stage_key, 'mix_bus_analysis_start')
        mix_bus_result = analyze_mix_bus_color(mastered_full_song_render.output_path)
        export_mix_bus_color_to_json(mix_bus_result, mix_bus_analysis_json)
        log_stage_memory(stage_key, 'mix_bus_analysis_end')

        tape_ir_rel = stage_conf.get('mix_bus_tape_ir')
        console_ir_rel = stage_conf.get('mix_bus_console_ir')
        vst3_conf = stage_conf.get('mix_bus_vst3_plugins') or []

        tape_ir_path = (ctx.project_root / tape_ir_rel).resolve() if tape_ir_rel else None
        console_ir_path = (ctx.project_root / console_ir_rel).resolve() if console_ir_rel else None
        vst3_paths = []
        for p in vst3_conf:
            p_path = Path(p)
            if not p_path.is_absolute():
                p_path = (ctx.project_root / p).resolve()
            vst3_paths.append(p_path)

        log_stage_memory(stage_key, 'mix_bus_correction_start')
        mix_bus_corr_result = run_mix_bus_color_correction(
            analysis_json_path=mix_bus_analysis_json,
            log_json_path=mix_bus_log_json,
            tape_ir_path=tape_ir_path,
            console_ir_path=console_ir_path,
            vst3_plugin_paths=vst3_paths,
            overwrite=True,
            output_path=mastered_full_song_render.output_path,
        )
        log_stage_memory(stage_key, 'mix_bus_correction_end')

        mastered_full_song_render.peak_dbfs = mix_bus_corr_result.resulting_peak_dbfs
        mastered_full_song_render.rms_dbfs = mix_bus_corr_result.resulting_rms_dbfs
        log_stage_event(stage_key, 'mix_bus', 'Mix-bus aplicado: peak %.2f, rms %.2f', mix_bus_corr_result.resulting_peak_dbfs, mix_bus_corr_result.resulting_rms_dbfs)

    ctx.mastered_full_song_render = mastered_full_song_render
    logger.info(
        'Mastering mixdown completado. Output=%s | peak=%.2f dBFS | rms=%.2f dBFS',
        mastered_full_song_render.output_path,
        mastered_full_song_render.peak_dbfs,
        mastered_full_song_render.rms_dbfs,
    )

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
    Ejecuta un stage de forma generica:
      - Determina input_dir = ctx.current_media_dir.
      - Determina output_dir segun 'media_subdir' (o reutiliza input_dir).
      - Lanza el runner correspondiente via STAGE_RUNNERS.
      - Actualiza stage_media_dirs y current_media_dir segun 'updates_current_dir'.
    """
    key = stage_conf["key"]
    label = stage_conf.get("label", key)
    description = stage_conf.get("description", "")

    input_dir = ctx.current_media_dir
    media_subdir = stage_conf.get("media_subdir")
    updates_current_dir = bool(stage_conf.get("updates_current_dir", False))

    if media_subdir:
        output_dir = ctx.temp_root / "media" / media_subdir
        output_dir.mkdir(parents=True, exist_ok=True)
    else:
        output_dir = input_dir  # stage solo de analisis

    log_stage_banner(
        stage_key=key,
        stage_label=label,
        description=description,
        index=index,
        total=total_stages,
        input_dir=input_dir,
        output_dir=output_dir,
    )

    if progress_callback:
        progress_callback(index, total_stages, key, description)

    runner = STAGE_RUNNERS.get(key)
    if runner is None:
        logger.warning("No hay runner configurado para stage key=%s, se omite", key)
        return

    log_stage_memory(key, "start")
    t0 = time.perf_counter()
    runner(ctx, stage_conf, input_dir, output_dir)
    duration = time.perf_counter() - t0
    logger.info("[TIMER] %s: %.2f s", key, duration)
    log_stage_memory(key, "end")

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
