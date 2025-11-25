from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np

try:
    import soundfile as sf
except ImportError as exc:
    raise ImportError(
        "space_depth.py requiere la librería 'soundfile'. "
        "Instálala con: pip install soundfile"
    ) from exc

try:
    from pedalboard import (
        Pedalboard,
        Reverb,
        Delay,
        Chorus,
        Phaser,
        HighpassFilter,
        LowpassFilter,
        Gain,
    )
except ImportError as exc:
    raise ImportError(
        "space_depth.py requiere la librería 'pedalboard'. "
        "Instálala con: pip install pedalboard"
    ) from exc


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Utilidades de conversión
# ---------------------------------------------------------------------------

def db_to_linear(db: float) -> float:
    """
    Convierte dBFS a factor lineal. -inf dB se aproxima a 0.
    """
    return float(10.0 ** (db / 20.0))


def amplitude_to_dbfs(amplitude: float, floor_db: float = -120.0) -> float:
    """
    Convierte una amplitud lineal (0..1) a dBFS, con floor configurable.
    """
    amp = float(amplitude)
    if amp <= 0.0:
        return float(floor_db)
    return 20.0 * float(np.log10(amp))


# ---------------------------------------------------------------------------
# Definición de buses y arquetipos de reverb
# ---------------------------------------------------------------------------

@dataclass
class BusDefinition:
    key: str
    description: str
    reverb_archetype: Optional[str]
    send_level_db: float
    pre_delay_ms: float = 0.0
    delay_ms: Optional[float] = None
    delay_feedback: float = 0.0
    mod_type: Optional[str] = None  # "chorus", "phaser" o None
    mod_rate_hz: float = 0.0
    mod_depth: float = 0.0
    hp_hz: Optional[float] = None
    lp_hz: Optional[float] = None
    output_trim_db: float = 0.0


# Arquetipos de reverb típicos, simulados con pedalboard.Reverb
REVERB_ARCHETYPES: Dict[str, Dict[str, float]] = {
    # Room corta, bastante damping, cola rápida
    "room": {
        "room_size": 0.25,
        "damping": 0.55,
        "width": 1.0,
    },
    # Plate clásico: algo más grande, más bright
    "plate": {
        "room_size": 0.35,
        "damping": 0.75,
        "width": 1.0,
    },
    # Hall grande y envolvente
    "hall": {
        "room_size": 0.75,
        "damping": 0.6,
        "width": 1.0,
    },
    # Spring aproximado: pequeño, con poco damping y algo más estrecho
    "spring": {
        "room_size": 0.20,
        "damping": 0.35,
        "width": 0.9,
    },
}


# Mapa de perfiles (frontend) → buses
PROFILE_TO_BUS: Dict[str, str] = {
    "drums": "drums",
    "percussion": "drums",
    "bass": "bass",
    "acoustic_guitar": "guitars",
    "electric_guitar": "guitars",
    "keys": "keys_synth",
    "synth": "keys_synth",
    "lead_vocal": "lead_vocal",
    "backing_vocals": "backing_vocals",
    "fx": "fx",
    "ambience": "fx",
    "other": "misc",
    "auto": "misc",
}


BUS_DEFINITIONS: Dict[str, BusDefinition] = {
    "drums": BusDefinition(
        key="drums",
        description="Tight stereo room reverb para drum/percussion bus",
        reverb_archetype="room",
        send_level_db=-14.0,
        pre_delay_ms=8.0,
        hp_hz=250.0,
        lp_hz=12000.0,
    ),
    "bass": BusDefinition(
        key="bass",
        description="Room muy corto y sutil para bajo (casi seco)",
        reverb_archetype="room",
        send_level_db=-22.0,
        pre_delay_ms=5.0,
        hp_hz=80.0,
        lp_hz=8000.0,
    ),
    "guitars": BusDefinition(
        key="guitars",
        description="Plate/spring para guitarras, con delay y chorus ligeros",
        reverb_archetype="plate",
        send_level_db=-16.0,
        pre_delay_ms=20.0,
        delay_ms=380.0,
        delay_feedback=0.18,
        mod_type="chorus",
        mod_rate_hz=0.8,
        mod_depth=0.15,
        hp_hz=180.0,
        lp_hz=12000.0,
    ),
    "keys_synth": BusDefinition(
        key="keys_synth",
        description="Hall amplio y largo para pads/keys",
        reverb_archetype="hall",
        send_level_db=-14.0,
        pre_delay_ms=25.0,
        delay_ms=420.0,
        delay_feedback=0.25,
        mod_type="chorus",
        mod_rate_hz=0.6,
        mod_depth=0.20,
        hp_hz=200.0,
        lp_hz=16000.0,
    ),
    "lead_vocal": BusDefinition(
        key="lead_vocal",
        description="Vocal plate con pre-delay y slapback suave",
        reverb_archetype="plate",
        send_level_db=-12.0,
        pre_delay_ms=80.0,
        delay_ms=120.0,
        delay_feedback=0.22,
        mod_type="chorus",
        mod_rate_hz=0.9,
        mod_depth=0.12,
        hp_hz=150.0,
        lp_hz=12000.0,
    ),
    "backing_vocals": BusDefinition(
        key="backing_vocals",
        description="Hall más largo para coros, más húmedos para profundidad",
        reverb_archetype="hall",
        send_level_db=-10.0,
        pre_delay_ms=40.0,
        delay_ms=320.0,
        delay_feedback=0.30,
        mod_type="chorus",
        mod_rate_hz=0.7,
        mod_depth=0.20,
        hp_hz=180.0,
        lp_hz=14000.0,
    ),
    "fx": BusDefinition(
        key="fx",
        description="Hall muy largo, casi cinemático, con phaser suave",
        reverb_archetype="hall",
        send_level_db=-8.0,
        pre_delay_ms=30.0,
        delay_ms=480.0,
        delay_feedback=0.35,
        mod_type="phaser",
        mod_rate_hz=0.5,
        mod_depth=0.30,
        hp_hz=250.0,
        lp_hz=18000.0,
    ),
    "misc": BusDefinition(
        key="misc",
        description="Room/plate neutro para material no clasificado",
        reverb_archetype="room",
        send_level_db=-18.0,
        pre_delay_ms=15.0,
        hp_hz=200.0,
        lp_hz=14000.0,
    ),
}


# ---------------------------------------------------------------------------
# Construcción de la cadena de Pedalboard para un bus
# ---------------------------------------------------------------------------

def build_space_pedalboard(bus_cfg: BusDefinition) -> Pedalboard:
    """
    Crea una cadena de Pedalboard 100% WET (dry=0) para usar como bus FX.
    El dry se mezcla fuera del board con send_level_db.
    """
    plugins = []

    # Filtros previos de la reverb/delay
    if bus_cfg.hp_hz and bus_cfg.hp_hz > 0.0:
        plugins.append(HighpassFilter(cutoff_frequency_hz=bus_cfg.hp_hz))

    if bus_cfg.lp_hz and bus_cfg.lp_hz > 0.0:
        plugins.append(LowpassFilter(cutoff_frequency_hz=bus_cfg.lp_hz))

    # Pre-delay antes de la reverb
    if bus_cfg.pre_delay_ms > 0.0:
        plugins.append(
            Delay(
                delay_seconds=bus_cfg.pre_delay_ms / 1000.0,
                feedback=0.0,
                mix=1.0,  # 100% wet, es sólo pre-delay
            )
        )

    # Reverb principal (room/plate/hall/spring)
    if bus_cfg.reverb_archetype:
        params = REVERB_ARCHETYPES.get(bus_cfg.reverb_archetype)
        if not params:
            raise ValueError(f"Arquetipo de reverb desconocido: {bus_cfg.reverb_archetype}")

        plugins.append(
            Reverb(
                room_size=params["room_size"],
                damping=params["damping"],
                width=params["width"],
                wet_level=1.0,   # 100% wet
                dry_level=0.0,   # 0% dry
                freeze_mode=0.0,
            )
        )

    # Delay creativo (eco/slapback) después de la reverb
    if bus_cfg.delay_ms and bus_cfg.delay_ms > 0.0:
        plugins.append(
            Delay(
                delay_seconds=bus_cfg.delay_ms / 1000.0,
                feedback=bus_cfg.delay_feedback,
                mix=1.0,  # 100% wet, se mezcla fuera
            )
        )

    # Modulación (chorus/phaser) sobre la cola
    if bus_cfg.mod_type == "chorus":
        plugins.append(
            Chorus(
                rate_hz=bus_cfg.mod_rate_hz,
                depth=bus_cfg.mod_depth,
                mix=1.0,  # 100% wet
            )
        )
    elif bus_cfg.mod_type == "phaser":
        plugins.append(
            Phaser(
                rate_hz=bus_cfg.mod_rate_hz,
                depth=bus_cfg.mod_depth,
                mix=1.0,  # 100% wet
            )
        )

    # Trim final de seguridad (por si el bus es muy caliente)
    if bus_cfg.output_trim_db != 0.0:
        plugins.append(Gain(gain_db=bus_cfg.output_trim_db))

    return Pedalboard(plugins)


# ---------------------------------------------------------------------------
# Asignación de perfiles a buses
# ---------------------------------------------------------------------------

def guess_profile_for_stem(stem_name: str, stem_profiles: Dict[str, str]) -> str:
    """
    Intenta recuperar el perfil de un stem:
      - Primero usando el nombre completo.
      - Luego usando sólo el stem (sin extensión).
      - Si no encuentra nada, devuelve 'auto'.
    """
    if stem_name in stem_profiles:
        return stem_profiles[stem_name]

    stem_stem = Path(stem_name).stem
    if stem_stem in stem_profiles:
        return stem_profiles[stem_stem]

    return stem_profiles.get("default", "auto")


def resolve_bus_for_profile(profile: str) -> Tuple[str, BusDefinition]:
    """
    Devuelve (bus_key, BusDefinition) a partir de un perfil de stem.
    """
    profile_key = (profile or "auto").strip()
    bus_key = PROFILE_TO_BUS.get(profile_key, "misc")
    bus_cfg = BUS_DEFINITIONS[bus_key]
    return bus_key, bus_cfg


# ---------------------------------------------------------------------------
# Procesado de un stem
# ---------------------------------------------------------------------------

def _process_stem_with_bus(
    stem_path: Path,
    output_path: Path,
    bus_cfg: BusDefinition,
) -> Tuple[float, float]:
    """
    Aplica la cadena de espacio/profundidad del bus a un stem concreto.

    - Lee el stem de stem_path.
    - Calcula wet = board(dry).
    - Mezcla out = dry + wet * send_gain (send_gain en lineal a partir de send_level_db).
    - Normaliza si es necesario para evitar clipping.
    - Escribe el stem procesado en output_path.
    - Devuelve (peak_dbfs, rms_dbfs).
    """
    data, samplerate = sf.read(str(stem_path), always_2d=True)
    # data.shape = (n_samples, n_channels)
    if data.ndim != 2:
        raise ValueError(f"Formato de audio inesperado para {stem_path}: {data.shape}")

    # Transponer a (n_channels, n_samples) para pedalboard
    audio = data.T.astype(np.float32)

    dry = audio
    board = build_space_pedalboard(bus_cfg)

    # Cadena 100% wet
    wet = board(dry, samplerate)

    # Envío a bus FX en dB
    send_gain = db_to_linear(bus_cfg.send_level_db)

    # Mezcla tipo envío: dry + (wet * send_gain)
    wet_scaled = wet * send_gain
    processed = dry + wet_scaled

    # Control anti-clipping
    peak = float(np.max(np.abs(processed)))
    if peak > 0.98:
        norm_gain = 0.98 / peak
        processed *= norm_gain
        peak = 0.98

    # Cálculo de RMS global (todas las canales)
    rms = float(np.sqrt(np.mean(processed ** 2.0)))

    # Volver a (n_samples, n_channels)
    processed_out = processed.T
    sf.write(str(output_path), processed_out, samplerate)

    peak_dbfs = amplitude_to_dbfs(peak)
    rms_dbfs = amplitude_to_dbfs(rms)

    logger.info(
        "[SPACE_DEPTH] %s | bus=%s | peak=%.2f dBFS | rms=%.2f dBFS",
        stem_path.name,
        bus_cfg.key,
        peak_dbfs,
        rms_dbfs,
    )

    return peak_dbfs, rms_dbfs


# ---------------------------------------------------------------------------
# Entry point de stage: run_space_depth
# ---------------------------------------------------------------------------

def run_space_depth(
    input_media_dir: Path,
    output_media_dir: Path,
    analysis_csv_path: Path,
    stem_profiles: Optional[Dict[str, str]] = None,
) -> None:
    """
    Stage de Space & Depth.

    - input_media_dir: directorio con los stems de entrada (ya con EQ/dinámica).
    - output_media_dir: directorio donde se escribirán los stems procesados.
    - analysis_csv_path: CSV con el mapeo stem→bus y métricas.
    - stem_profiles: dict opcional {stem_name (o base) -> perfil}.
    """
    stem_profiles = stem_profiles or {}
    output_media_dir.mkdir(parents=True, exist_ok=True)

    wav_files = sorted(input_media_dir.glob("*.wav"))
    if not wav_files:
        logger.warning(
            "[SPACE_DEPTH] No se encontraron stems .wav en %s", input_media_dir
        )
        return

    logger.info(
        "[SPACE_DEPTH] Procesando %d stems desde %s -> %s",
        len(wav_files),
        input_media_dir,
        output_media_dir,
    )

    # CSV de análisis / documentación
    with analysis_csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            [
                "stem_name",
                "profile",
                "bus_key",
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
                "output_peak_dbfs",
                "output_rms_dbfs",
            ]
        )

        for stem_path in wav_files:
            stem_name = stem_path.name
            profile = guess_profile_for_stem(stem_name, stem_profiles)
            bus_key, bus_cfg = resolve_bus_for_profile(profile)

            output_path = output_media_dir / stem_name

            try:
                peak_dbfs, rms_dbfs = _process_stem_with_bus(
                    stem_path=stem_path,
                    output_path=output_path,
                    bus_cfg=bus_cfg,
                )
            except Exception as exc:
                logger.exception(
                    "[SPACE_DEPTH] Error procesando stem %s: %s",
                    stem_name,
                    exc,
                )
                continue

            writer.writerow(
                [
                    stem_name,
                    profile,
                    bus_key,
                    bus_cfg.reverb_archetype or "",
                    bus_cfg.send_level_db,
                    bus_cfg.pre_delay_ms,
                    bus_cfg.delay_ms or 0.0,
                    bus_cfg.delay_feedback,
                    bus_cfg.mod_type or "",
                    bus_cfg.mod_rate_hz,
                    bus_cfg.mod_depth,
                    bus_cfg.hp_hz or 0.0,
                    bus_cfg.lp_hz or 0.0,
                    peak_dbfs,
                    rms_dbfs,
                ]
            )

    logger.info(
        "[SPACE_DEPTH] Completado. Stems con espacio/profundidad en %s, "
        "CSV de análisis en %s",
        output_media_dir,
        analysis_csv_path,
    )


__all__ = [
    "run_space_depth",
    "BusDefinition",
    "BUS_DEFINITIONS",
    "PROFILE_TO_BUS",
]
