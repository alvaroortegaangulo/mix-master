from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

try:
    import soundfile as sf  # s取りlo para lectura de audio si no reutilizamos helpers
except ImportError as exc:
    raise ImportError(
        "space_depth_analysis.py requiere la librerクリa 'soundfile'. "
        "Instロla con: pip install soundfile"
    ) from exc


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


@dataclass
class SpaceDepthBusAnalysisRow:
    """Fila de análisis para un bus de Space & Depth."""

    bus_fx_stem_name: str
    bus_key: str
    style_key: str

    stem_names: str
    num_input_stems: int

    reverb_archetype: str
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
    delay_note: str
    pre_delay_note: str

    crest_factor: float
    spectral_centroid_hz: float
    low_fraction: float
    mid_fraction: float
    high_fraction: float


def analyze_space_depth(
    media_dir: Path,
    stem_profiles: Optional[Dict[str, str]] = None,
    bus_styles: Optional[Dict[str, str]] = None,
    tempo_bpm: Optional[float] = None,
    enable_audio_adaptive: bool = True,
) -> List[SpaceDepthBusAnalysisRow]:
    """
    Analiza los stems de media_dir y calcula, bus por bus, la configuracion
    recomendada de Space & Depth (reverb/delay/modulacion + filtros).
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

    from collections import defaultdict

    bus_to_stems: Dict[str, List[Path]] = defaultdict(list)

    for stem_path in wav_files:
        stem_name = stem_path.name
        profile = guess_profile_for_stem(stem_name, stem_profiles)
        bus_key = resolve_bus_for_profile(profile)
        bus_to_stems[bus_key].append(stem_path)

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

        style_key = bus_styles.get(bus_key) or bus_styles.get("default") or ""
        style_key_stripped = style_key.strip()

        base_bus_cfg = get_bus_definition_for_style(
            bus_key=bus_key,
            style_key=style_key_stripped or None,
        )

        try:
            bus_dry, samplerate = _sum_stems_for_bus(stems_for_bus)
        except Exception as exc:
            logger.exception(
                "[SPACE_DEPTH_ANALYSIS] No se pudo sumar stems para bus '%s': %s",
                bus_key,
                exc,
            )
            continue

        stats = analyze_bus_audio(bus_dry, samplerate)

        cfg_after_tempo, tempo_notes = apply_tempo_to_bus_times(
            bus_cfg=base_bus_cfg,
            tempo_bpm=tempo_bpm if tempo_bpm and tempo_bpm > 0.0 else None,
        )

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
        "[SPACE_DEPTH_ANALYSIS] Analisis completado: %d buses analizados",
        len(results),
    )
    return results


def export_space_depth_to_json(
    rows: List[SpaceDepthBusAnalysisRow],
    json_path: Path,
) -> Path:
    """Exporta la lista de SpaceDepthBusAnalysisRow a JSON."""
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = []
    for r in rows:
        row = asdict(r)
        payload.append(row)

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        "[SPACE_DEPTH_ANALYSIS] JSON exportado a %s (%d filas)",
        json_path,
        len(rows),
    )
    return json_path


__all__ = [
    "SpaceDepthBusAnalysisRow",
    "analyze_space_depth",
    "export_space_depth_to_json",
]
