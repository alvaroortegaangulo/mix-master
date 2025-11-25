# src/analysis/space_depth_analysis.py

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

try:
    import soundfile as sf  # sólo para lectura de audio si no reutilizamos helpers
except ImportError as exc:
    raise ImportError(
        "space_depth_analysis.py requiere la librería 'soundfile'. "
        "Instálala con: pip install soundfile"
    ) from exc


# Reutilizamos la lógica y la configuración ya definida en tu stage:
#   - asignación de perfiles a buses
#   - presets de buses + estilos
#   - helpers de tempo y análisis de audio
from src.stages.stage3_space_depth_buses.space_depth import (
    PROFILE_TO_BUS,
    get_bus_definition_for_style,
    guess_profile_for_stem,
    resolve_bus_for_profile,
    apply_tempo_to_bus_times,
    analyze_bus_audio,
    apply_audio_driven_adjustments,
    _sum_stems_for_bus,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclass de salida (una fila por BUS FX)
# ---------------------------------------------------------------------------

@dataclass
class SpaceDepthBusAnalysisRow:
    """
    Fila de análisis para un bus de Space & Depth.

    Esta estructura está pensada para ser serializada a CSV y consumida
    posteriormente por la fase de corrección (space_depth.py) para construir
    los buses FX sin recalcular heurísticas.
    """

    bus_fx_stem_name: str     # p.ej. "bus_drums_space.wav"
    bus_key: str              # "drums", "guitars", "lead_vocal", ...
    style_key: str            # "flamenco_rumba", "urban_trap", ... o ""

    stem_names: str           # nombres de stems de entrada separados por '|'
    num_input_stems: int

    reverb_archetype: str     # "room", "plate", "hall", "spring" o ""
    send_level_db: float
    pre_delay_ms: float
    delay_ms: float
    delay_feedback: float
    mod_type: str
    mod_rate_hz: float
    mod_depth: float
    hp_hz: float
    lp_hz: float

    tempo_bpm: float
    delay_note: str           # subdivision cuantizada del delay (1/8, 1/8_dotted, ...)
    pre_delay_note: str       # subdivision cuantizada del pre-delay

    crest_factor: float
    spectral_centroid_hz: float
    low_fraction: float
    mid_fraction: float
    high_fraction: float


# ---------------------------------------------------------------------------
# Función principal de análisis
# ---------------------------------------------------------------------------

def analyze_space_depth(
    media_dir: Path,
    stem_profiles: Optional[Dict[str, str]] = None,
    bus_styles: Optional[Dict[str, str]] = None,
    tempo_bpm: Optional[float] = None,
    enable_audio_adaptive: bool = True,
) -> List[SpaceDepthBusAnalysisRow]:
    """
    Analiza los stems de media_dir y calcula, bus por bus, la configuración
    recomendada de Space & Depth (reverb/delay/modulación + filtros).

    No aplica ningún efecto ni genera audio. Sólo devuelve una lista de
    SpaceDepthBusAnalysisRow para una exportación posterior a CSV.

    Parámetros
    ----------
    media_dir:
        Carpeta con los stems (.wav) ya preparados por los stages anteriores
        (típicamente salida de static_mix_dyn).
    stem_profiles:
        Mapa opcional {stem_name|stem_stem|default -> perfil lógico}, p.ej.:
          - "kick.wav" -> "drums"
          - "vocal"    -> "lead_vocal"
          - "default"  -> "misc"
    bus_styles:
        Mapa opcional {bus_key|default -> estilo}, p.ej.:
          - "drums"   -> "flamenco_rumba"
          - "default" -> "urban_trap"
    tempo_bpm:
        BPM real de la canción, calculado en stage tempo_key (ctx.tempo_result.bpm).
        Si es None o <= 0, no se aplica cuantización a tempo.
    enable_audio_adaptive:
        Si True, ajusta send/filtros según el contenido del audio del bus
        (crest factor, espectro, etc.) usando apply_audio_driven_adjustments.
    """
    stem_profiles = stem_profiles or {}
    bus_styles = bus_styles or {}

    wav_files = sorted(Path(media_dir).glob("*.wav"))
    if not wav_files:
        logger.warning(
            "[SPACE_DEPTH_ANALYSIS] No se encontraron stems .wav en %s",
            media_dir,
        )
        return []

    logger.info(
        "[SPACE_DEPTH_ANALYSIS] Analizando %d stems en %s | tempo_bpm=%s",
        len(wav_files),
        media_dir,
        tempo_bpm,
    )

    # ----------------------------------------------------------------------
    # 1) Agrupar stems por bus usando stem_profiles → PROFILE_TO_BUS
    # ----------------------------------------------------------------------
    from collections import defaultdict

    bus_to_stems: Dict[str, List[Path]] = defaultdict(list)

    for stem_path in wav_files:
        stem_name = stem_path.name
        profile = guess_profile_for_stem(stem_name, stem_profiles)
        bus_key = resolve_bus_for_profile(profile)
        bus_to_stems[bus_key].append(stem_path)

    # ----------------------------------------------------------------------
    # 2) Para cada bus, sumar audio, analizarlo y proponer parámetros
    # ----------------------------------------------------------------------
    results: List[SpaceDepthBusAnalysisRow] = []

    for bus_key, stems_for_bus in bus_to_stems.items():
        if not stems_for_bus:
            continue

        logger.info(
            "[SPACE_DEPTH_ANALYSIS] Bus '%s' con %d stems: %s",
            bus_key,
            len(stems_for_bus),
            ", ".join(p.name for p in stems_for_bus),
        )

        # Estilo elegido para este bus (si existe)
        style_key = bus_styles.get(bus_key) or bus_styles.get("default") or ""
        style_key_stripped = style_key.strip()

        # Config base del bus + estilo (reutiliza BUS_DEFINITIONS + STYLE_PRESETS)
        base_bus_cfg = get_bus_definition_for_style(
            bus_key=bus_key,
            style_key=style_key_stripped or None,
        )

        # 2.1) Sumar stems del bus en un solo array (n_channels, n_samples)
        try:
            bus_dry, samplerate = _sum_stems_for_bus(stems_for_bus)
        except Exception as exc:
            logger.exception(
                "[SPACE_DEPTH_ANALYSIS] No se pudo sumar stems para bus '%s': %s",
                bus_key,
                exc,
            )
            continue

        # 2.2) Analizar contenido de audio del bus
        stats = analyze_bus_audio(bus_dry, samplerate)

        # 2.3) Aplicar cuantización a tempo (pre-delay / delay)
        cfg_after_tempo, tempo_notes = apply_tempo_to_bus_times(
            bus_cfg=base_bus_cfg,
            tempo_bpm=tempo_bpm if tempo_bpm and tempo_bpm > 0.0 else None,
        )

        # 2.4) Ajustes audio-driven (crest, espectro, etc.)
        if enable_audio_adaptive:
            final_cfg = apply_audio_driven_adjustments(
                bus_cfg=cfg_after_tempo,
                stats=stats,
                bus_key=bus_key,
                tempo_bpm=tempo_bpm if tempo_bpm and tempo_bpm > 0.0 else None,
                style_key=style_key_stripped or None,
            )
        else:
            final_cfg = cfg_after_tempo

        # Nombre del stem FX que generará space_depth posteriormente
        bus_fx_name = f"bus_{bus_key}_space.wav"

        row = SpaceDepthBusAnalysisRow(
            bus_fx_stem_name=bus_fx_name,
            bus_key=bus_key,
            style_key=style_key_stripped,

            stem_names="|".join(p.name for p in stems_for_bus),
            num_input_stems=len(stems_for_bus),

            reverb_archetype=(final_cfg.reverb_archetype or ""),
            send_level_db=final_cfg.send_level_db,
            pre_delay_ms=final_cfg.pre_delay_ms,
            delay_ms=(final_cfg.delay_ms or 0.0),
            delay_feedback=final_cfg.delay_feedback,
            mod_type=(final_cfg.mod_type or ""),
            mod_rate_hz=final_cfg.mod_rate_hz,
            mod_depth=final_cfg.mod_depth,
            hp_hz=(final_cfg.hp_hz or 0.0),
            lp_hz=(final_cfg.lp_hz or 0.0),

            tempo_bpm=float(tempo_bpm or 0.0),
            delay_note=tempo_notes.get("delay_note", ""),
            pre_delay_note=tempo_notes.get("pre_delay_note", ""),

            crest_factor=stats.crest,
            spectral_centroid_hz=stats.spectral_centroid_hz,
            low_fraction=stats.low_fraction,
            mid_fraction=stats.mid_fraction,
            high_fraction=stats.high_fraction,
        )

        results.append(row)

    logger.info(
        "[SPACE_DEPTH_ANALYSIS] Análisis completado: %d buses analizados",
        len(results),
    )
    return results


# ---------------------------------------------------------------------------
# Exportación a CSV
# ---------------------------------------------------------------------------

def export_space_depth_to_csv(
    rows: List[SpaceDepthBusAnalysisRow],
    csv_path: Path,
) -> None:
    """
    Exporta la lista de SpaceDepthBusAnalysisRow a un CSV.

    Este CSV está pensado para ser consumido por un futuro
    run_space_depth_correction(...) que aplique las colas FX a partir
    de la configuración ya calculada aquí.
    """
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        writer.writerow(
            [
                "bus_fx_stem_name",
                "bus_key",
                "style_key",
                "stem_names",
                "num_input_stems",
                "reverb_archetype",
                "send_level_db",
                "pre_delay_ms",
                "delay_ms",
                "delay_feedback",
                "mod_type",
                "mod_rate_hz",
                "mod_depth",
                "hp_hz",
                "lp_hz",
                "tempo_bpm",
                "delay_note",
                "pre_delay_note",
                "crest_factor",
                "spectral_centroid_hz",
                "low_fraction",
                "mid_fraction",
                "high_fraction",
            ]
        )

        for r in rows:
            writer.writerow(
                [
                    r.bus_fx_stem_name,
                    r.bus_key,
                    r.style_key,
                    r.stem_names,
                    r.num_input_stems,
                    r.reverb_archetype,
                    r.send_level_db,
                    r.pre_delay_ms,
                    r.delay_ms,
                    r.delay_feedback,
                    r.mod_type,
                    r.mod_rate_hz,
                    r.mod_depth,
                    r.hp_hz,
                    r.lp_hz,
                    r.tempo_bpm,
                    r.delay_note,
                    r.pre_delay_note,
                    r.crest_factor,
                    r.spectral_centroid_hz,
                    r.low_fraction,
                    r.mid_fraction,
                    r.high_fraction,
                ]
            )

    logger.info(
        "[SPACE_DEPTH_ANALYSIS] CSV exportado a %s (%d filas)",
        csv_path,
        len(rows),
    )


__all__ = [
    "SpaceDepthBusAnalysisRow",
    "analyze_space_depth",
    "export_space_depth_to_csv",
]
