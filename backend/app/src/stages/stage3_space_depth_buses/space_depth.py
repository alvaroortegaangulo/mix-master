from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, replace
from pathlib import Path
import shutil
from collections import defaultdict
from typing import Dict, Optional, Tuple, List
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
# Helpers de tempo: BPM → milisegundos y cuantización musical
# ---------------------------------------------------------------------------

NOTE_BEAT_FACTORS: Dict[str, float] = {
    "1/1": 4.0,
    "1/2": 2.0,
    "1/2_dotted": 3.0,
    "1/4": 1.0,
    "1/4_dotted": 1.5,
    "1/4_triplet": 2.0 / 3.0,
    "1/8": 0.5,
    "1/8_dotted": 0.75,
    "1/8_triplet": 1.0 / 3.0,
    "1/16": 0.25,
    "1/16_dotted": 0.375,
    "1/16_triplet": 1.0 / 6.0,
}


def tempo_ms_for_note(bpm: float, note: str) -> float:
    """
    Devuelve la duración en ms de una subdivisión musical a un BPM dado.
    Ejemplo: note="1/8" → corchea, note="1/8_dotted" → corchea con puntillo.
    """
    if bpm <= 0.0:
        raise ValueError(f"BPM inválido para tempo_ms_for_note: {bpm}")

    factor = NOTE_BEAT_FACTORS.get(note)
    if factor is None:
        raise ValueError(f"Subdivisión musical desconocida: {note}")

    beat_ms = 60000.0 / bpm  # negra
    return beat_ms * factor


def quantize_ms_to_tempo_subdivision(
    raw_ms: float,
    bpm: float,
    candidate_notes: Optional[List[str]] = None,
) -> Tuple[float, str]:
    """
    Dado un tiempo aproximado en ms (de tus presets) y el BPM real,
    encuentra la subdivisión musical más cercana y devuelve (ms_cuantizado, nombre_nota).

    Si bpm <= 0 o raw_ms <= 0, devuelve el valor original sin cuantizar.
    """
    if bpm <= 0.0 or raw_ms <= 0.0:
        return raw_ms, ""

    if candidate_notes is None:
        candidate_notes = [
            "1/16_triplet",
            "1/16",
            "1/8_triplet",
            "1/8",
            "1/8_dotted",
            "1/4_triplet",
            "1/4",
            "1/4_dotted",
            "1/2",
        ]

    best_note = ""
    best_ms = raw_ms
    best_err = float("inf")

    for note in candidate_notes:
        try:
            ideal_ms = tempo_ms_for_note(bpm, note)
        except ValueError:
            continue

        err = abs(ideal_ms - raw_ms)
        if err < best_err:
            best_err = err
            best_note = note
            best_ms = ideal_ms

    return best_ms, best_note


# ---------------------------------------------------------------------------
# Definición de buses, arquetipos de reverb y stats de audio
# ---------------------------------------------------------------------------


@dataclass
class BusDefinition:
    """
    Ajustes base de espacio/profundidad de un bus.

    Estos valores representan un punto de partida "auto" conservador,
    pensado para no embarrar la mezcla. Los presets de estilo aplican
    overrides sobre estos valores.
    """

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


@dataclass
class StyleOverride:
    """
    Overrides opcionales de un BusDefinition para un estilo concreto.

    Cualquier campo en None significa "no cambiar el valor base".
    """

    reverb_archetype: Optional[str] = None
    send_level_db: Optional[float] = None
    pre_delay_ms: Optional[float] = None
    delay_ms: Optional[float] = None
    delay_feedback: Optional[float] = None
    mod_type: Optional[str] = None
    mod_rate_hz: Optional[float] = None
    mod_depth: Optional[float] = None
    hp_hz: Optional[float] = None
    lp_hz: Optional[float] = None
    output_trim_db: Optional[float] = None


@dataclass
class BusAudioStats:
    """
    Métricas básicas del audio sumado de un bus, para adaptar send/filtros.
    """

    peak: float
    rms: float
    crest: float
    spectral_centroid_hz: float
    low_fraction: float
    mid_fraction: float
    high_fraction: float


def apply_style_override(
    base: BusDefinition, override: Optional[StyleOverride]
) -> BusDefinition:
    """
    Devuelve una copia de base con los overrides aplicados.
    """
    if override is None:
        return base

    cfg = replace(base)  # copia superficial

    if override.reverb_archetype is not None:
        cfg.reverb_archetype = override.reverb_archetype
    if override.send_level_db is not None:
        cfg.send_level_db = override.send_level_db
    if override.pre_delay_ms is not None:
        cfg.pre_delay_ms = override.pre_delay_ms
    if override.delay_ms is not None:
        cfg.delay_ms = override.delay_ms
    if override.delay_feedback is not None:
        cfg.delay_feedback = override.delay_feedback
    if override.mod_type is not None:
        cfg.mod_type = override.mod_type
    if override.mod_rate_hz is not None:
        cfg.mod_rate_hz = override.mod_rate_hz
    if override.mod_depth is not None:
        cfg.mod_depth = override.mod_depth
    if override.hp_hz is not None:
        cfg.hp_hz = override.hp_hz
    if override.lp_hz is not None:
        cfg.lp_hz = override.lp_hz
    if override.output_trim_db is not None:
        cfg.output_trim_db = override.output_trim_db

    return cfg


# Arquetipos de reverb típicos, simulados con pedalboard.Reverb
# room_size ~= tiempo de cola
# damping ~= damping de agudos
REVERB_ARCHETYPES: Dict[str, Dict[str, float]] = {
    # Room muy corto, cola rápida y bastante damping.
    # Útil para sensación de sala sin “bola”.
    "room": {
        "room_size": 0.18,
        "damping": 0.78,
        "width": 1.0,
    },
    # Plate vocal/instrumental estándar: algo más largo y brillante
    # pero con damping suficiente para no volverse chillón.
    "plate": {
        "room_size": 0.32,
        "damping": 0.72,
        "width": 1.0,
    },
    # Hall moderado, no “catedral”: largo pero bien amortiguado.
    "hall": {
        "room_size": 0.56,
        "damping": 0.82,
        "width": 1.0,
    },
    # Spring aproximado: mid-rangey, algo estrecho.
    "spring": {
        "room_size": 0.24,
        "damping": 0.65,
        "width": 0.95,
    },
}


# Mapa de perfiles (frontend) → buses internos
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


# Configuración base muy conservadora (modo AUTO)
# Si no hay estilo seleccionado, se usa esto.
BUS_DEFINITIONS: Dict[str, BusDefinition] = {
    "drums": BusDefinition(
        key="drums",
        description="Room compacto y controlado para batería/percu (glue sutil).",
        reverb_archetype="room",
        send_level_db=-22.0,   # ~8% de nivel relativo
        pre_delay_ms=8.0,
        hp_hz=300.0,
        lp_hz=10000.0,
    ),
    "bass": BusDefinition(
        key="bass",
        description="Ambiencia mínima en bajo; prácticamente seco.",
        reverb_archetype="room",
        send_level_db=-30.0,   # ~3% de nivel; apenas se nota
        pre_delay_ms=5.0,
        hp_hz=90.0,
        lp_hz=6500.0,
    ),
    "guitars": BusDefinition(
        key="guitars",
        description="Plate corto y filtrado para guitarras; cola clara pero discreta.",
        reverb_archetype="plate",
        send_level_db=-21.0,
        pre_delay_ms=18.0,
        delay_ms=220.0,
        delay_feedback=0.16,
        mod_type="chorus",
        mod_rate_hz=0.7,
        mod_depth=0.10,
        hp_hz=220.0,
        lp_hz=12000.0,
    ),
    "keys_synth": BusDefinition(
        key="keys_synth",
        description="Hall moderado para pads/keys; da profundidad sin inundar.",
        reverb_archetype="hall",
        send_level_db=-21.0,
        pre_delay_ms=24.0,
        delay_ms=260.0,
        delay_feedback=0.20,
        mod_type="chorus",
        mod_rate_hz=0.6,
        mod_depth=0.16,
        hp_hz=230.0,
        lp_hz=14500.0,
    ),
    "lead_vocal": BusDefinition(
        key="lead_vocal",
        description="Plate corto de vocal con predelay para inteligibilidad.",
        reverb_archetype="plate",
        send_level_db=-20.0,
        pre_delay_ms=80.0,
        delay_ms=140.0,
        delay_feedback=0.22,
        mod_type="chorus",
        mod_rate_hz=0.9,
        mod_depth=0.10,
        hp_hz=160.0,
        lp_hz=12000.0,
    ),
    "backing_vocals": BusDefinition(
        key="backing_vocals",
        description="Hall moderado para coros, algo más húmedos que la lead.",
        reverb_archetype="hall",
        send_level_db=-19.0,
        pre_delay_ms=45.0,
        delay_ms=230.0,
        delay_feedback=0.24,
        mod_type="chorus",
        mod_rate_hz=0.75,
        mod_depth=0.16,
        hp_hz=180.0,
        lp_hz=13500.0,
    ),
    "fx": BusDefinition(
        key="fx",
        description="Hall algo más largo para FX, pero filtrado en graves y muy agudos.",
        reverb_archetype="hall",
        send_level_db=-18.0,
        pre_delay_ms=28.0,
        delay_ms=340.0,
        delay_feedback=0.30,
        mod_type="phaser",
        mod_rate_hz=0.5,
        mod_depth=0.26,
        hp_hz=260.0,
        lp_hz=18000.0,
    ),
    "misc": BusDefinition(
        key="misc",
        description="Room neutro para material no clasificado.",
        reverb_archetype="room",
        send_level_db=-23.0,
        pre_delay_ms=18.0,
        hp_hz=230.0,
        lp_hz=13000.0,
    ),
}


# ---------------------------------------------------------------------------
# Presets por estilo/bus
# ---------------------------------------------------------------------------

# Valores de estilo que vienen del frontend:
#   - "flamenco_rumba"
#   - "urban_trap"
#   - "rock"
#   - "latin_pop"
#   - "edm"
#   - "ballad_ambient"
#   - "acoustic"
#
# Diseño:
#   STYLE_PRESETS_BY_STYLE_AND_BUS[style_key][bus_key] -> StyleOverride
#
# (Se mantiene igual que en tu versión original)
STYLE_PRESETS_BY_STYLE_AND_BUS: Dict[str, Dict[str, StyleOverride]] = {
    # ... TODO: aquí va exactamente el mismo bloque de estilos
    # que ya tenías en tu script original, lo copio íntegro:
    "flamenco_rumba": {
        "drums": StyleOverride(
            send_level_db=-23.0,
            pre_delay_ms=9.0,
            hp_hz=320.0,
            lp_hz=10000.0,
        ),
        "bass": StyleOverride(
            reverb_archetype=None,   # prácticamente seco
            send_level_db=-60.0,
            hp_hz=80.0,
            lp_hz=6500.0,
        ),
        "guitars": StyleOverride(
            reverb_archetype="plate",
            send_level_db=-20.0,     # 1 dB más húmedo que base
            pre_delay_ms=26.0,
            delay_ms=190.0,
            delay_feedback=0.16,
            mod_type="chorus",
            mod_rate_hz=0.8,
            mod_depth=0.12,
            hp_hz=230.0,
            lp_hz=12000.0,
        ),
        "keys_synth": StyleOverride(
            reverb_archetype="hall",
            send_level_db=-22.0,
            pre_delay_ms=24.0,
            delay_ms=260.0,
            delay_feedback=0.18,
            hp_hz=240.0,
            lp_hz=14500.0,
        ),
        "lead_vocal": StyleOverride(
            reverb_archetype="plate",
            send_level_db=-19.0,
            pre_delay_ms=95.0,
            delay_ms=150.0,
            delay_feedback=0.24,
            mod_type="chorus",
            mod_rate_hz=0.9,
            mod_depth=0.12,
            hp_hz=170.0,
            lp_hz=12000.0,
        ),
        "backing_vocals": StyleOverride(
            reverb_archetype="hall",
            send_level_db=-18.0,
            pre_delay_ms=60.0,
            delay_ms=260.0,
            delay_feedback=0.26,
            hp_hz=190.0,
            lp_hz=13500.0,
        ),
        "fx": StyleOverride(
            reverb_archetype="hall",
            send_level_db=-17.0,
            pre_delay_ms=38.0,
            delay_ms=360.0,
            delay_feedback=0.30,
            mod_type="phaser",
            mod_rate_hz=0.5,
            mod_depth=0.26,
            hp_hz=260.0,
            lp_hz=17500.0,
        ),
        "misc": StyleOverride(
            send_level_db=-23.0,
            pre_delay_ms=18.0,
        ),
    },
    "urban_trap": {
        "drums": StyleOverride(
            send_level_db=-24.0,
            pre_delay_ms=6.0,
            hp_hz=360.0,
            lp_hz=9500.0,
        ),
        "bass": StyleOverride(
            reverb_archetype=None,
            send_level_db=-80.0,
            hp_hz=70.0,
            lp_hz=5500.0,
        ),
        "guitars": StyleOverride(
            send_level_db=-22.0,
            pre_delay_ms=22.0,
            delay_ms=260.0,
            delay_feedback=0.20,
            mod_type="chorus",
            mod_rate_hz=0.7,
            mod_depth=0.10,
            hp_hz=230.0,
            lp_hz=11500.0,
        ),
        "keys_synth": StyleOverride(
            reverb_archetype="hall",
            send_level_db=-19.0,
            pre_delay_ms=30.0,
            delay_ms=300.0,
            delay_feedback=0.26,
            mod_type="chorus",
            mod_rate_hz=0.55,
            mod_depth=0.18,
            hp_hz=260.0,
            lp_hz=16500.0,
        ),
        "lead_vocal": StyleOverride(
            reverb_archetype="hall",
            send_level_db=-19.0,
            pre_delay_ms=110.0,
            delay_ms=260.0,
            delay_feedback=0.28,
            mod_type="chorus",
            mod_rate_hz=1.0,
            mod_depth=0.12,
            hp_hz=180.0,
            lp_hz=12500.0,
        ),
        "backing_vocals": StyleOverride(
            reverb_archetype="hall",
            send_level_db=-18.0,
            pre_delay_ms=70.0,
            delay_ms=300.0,
            delay_feedback=0.30,
            hp_hz=200.0,
            lp_hz=13500.0,
        ),
        "fx": StyleOverride(
            reverb_archetype="hall",
            send_level_db=-17.0,
            pre_delay_ms=42.0,
            delay_ms=380.0,
            delay_feedback=0.36,
            mod_type="phaser",
            mod_rate_hz=0.45,
            mod_depth=0.30,
            hp_hz=280.0,
            lp_hz=18500.0,
        ),
    },
    "rock": {
        "drums": StyleOverride(
            send_level_db=-21.0,
            pre_delay_ms=12.0,
            hp_hz=300.0,
            lp_hz=10500.0,
        ),
        "bass": StyleOverride(
            reverb_archetype=None,
            send_level_db=-60.0,
        ),
        "guitars": StyleOverride(
            send_level_db=-20.0,
            pre_delay_ms=22.0,
            delay_ms=260.0,
            delay_feedback=0.20,
            mod_type="chorus",
            mod_rate_hz=0.7,
            mod_depth=0.12,
        ),
        "keys_synth": StyleOverride(
            reverb_archetype="hall",
            send_level_db=-21.0,
            pre_delay_ms=24.0,
            delay_ms=280.0,
            delay_feedback=0.22,
        ),
        "lead_vocal": StyleOverride(
            reverb_archetype="plate",
            send_level_db=-20.0,
            pre_delay_ms=75.0,
            delay_ms=170.0,
            delay_feedback=0.24,
        ),
        "backing_vocals": StyleOverride(
            reverb_archetype="hall",
            send_level_db=-19.0,
            pre_delay_ms=52.0,
            delay_ms=240.0,
            delay_feedback=0.26,
        ),
        "fx": StyleOverride(
            reverb_archetype="hall",
            send_level_db=-18.0,
            pre_delay_ms=30.0,
            delay_ms=340.0,
            delay_feedback=0.32,
            mod_type="phaser",
            mod_rate_hz=0.5,
            mod_depth=0.28,
        ),
    },
    "latin_pop": {
        "drums": StyleOverride(
            send_level_db=-22.0,
            pre_delay_ms=9.0,
            hp_hz=320.0,
            lp_hz=10000.0,
        ),
        "bass": StyleOverride(
            reverb_archetype=None,
            send_level_db=-60.0,
        ),
        "guitars": StyleOverride(
            send_level_db=-20.0,
            pre_delay_ms=22.0,
            delay_ms=230.0,
            delay_feedback=0.20,
            mod_type="chorus",
            mod_rate_hz=0.7,
            mod_depth=0.12,
        ),
        "keys_synth": StyleOverride(
            reverb_archetype="hall",
            send_level_db=-20.0,
            pre_delay_ms=28.0,
            delay_ms=300.0,
            delay_feedback=0.24,
        ),
        "lead_vocal": StyleOverride(
            reverb_archetype="plate",
            send_level_db=-19.0,
            pre_delay_ms=90.0,
            delay_ms=230.0,
            delay_feedback=0.26,
            mod_type="chorus",
            mod_rate_hz=0.9,
            mod_depth=0.12,
        ),
        "backing_vocals": StyleOverride(
            reverb_archetype="hall",
            send_level_db=-18.0,
            pre_delay_ms=60.0,
            delay_ms=270.0,
            delay_feedback=0.28,
        ),
        "fx": StyleOverride(
            reverb_archetype="hall",
            send_level_db=-17.0,
            pre_delay_ms=40.0,
            delay_ms=360.0,
            delay_feedback=0.34,
            mod_type="phaser",
            mod_rate_hz=0.45,
            mod_depth=0.28,
        ),
    },
    "edm": {
        "drums": StyleOverride(
            send_level_db=-25.0,
            pre_delay_ms=6.0,
            hp_hz=380.0,
            lp_hz=9500.0,
        ),
        "bass": StyleOverride(
            reverb_archetype=None,
            send_level_db=-80.0,
        ),
        "guitars": StyleOverride(
            send_level_db=-22.0,
            pre_delay_ms=20.0,
            delay_ms=240.0,
            delay_feedback=0.22,
        ),
        "keys_synth": StyleOverride(
            reverb_archetype="hall",
            send_level_db=-18.0,
            pre_delay_ms=35.0,
            delay_ms=340.0,
            delay_feedback=0.30,
            mod_type="chorus",
            mod_rate_hz=0.65,
            mod_depth=0.22,
            hp_hz=260.0,
            lp_hz=17000.0,
        ),
        "lead_vocal": StyleOverride(
            reverb_archetype="hall",
            send_level_db=-19.0,
            pre_delay_ms=100.0,
            delay_ms=280.0,
            delay_feedback=0.30,
        ),
        "backing_vocals": StyleOverride(
            reverb_archetype="hall",
            send_level_db=-18.0,
            pre_delay_ms=65.0,
            delay_ms=300.0,
            delay_feedback=0.32,
        ),
        "fx": StyleOverride(
            reverb_archetype="hall",
            send_level_db=-16.0,
            pre_delay_ms=40.0,
            delay_ms=400.0,
            delay_feedback=0.38,
            mod_type="phaser",
            mod_rate_hz=0.5,
            mod_depth=0.32,
        ),
    },
    "ballad_ambient": {
        "drums": StyleOverride(
            send_level_db=-21.0,
            pre_delay_ms=14.0,
            hp_hz=320.0,
            lp_hz=10000.0,
        ),
        "bass": StyleOverride(
            reverb_archetype=None,
            send_level_db=-55.0,
        ),
        "guitars": StyleOverride(
            reverb_archetype="hall",
            send_level_db=-19.0,
            pre_delay_ms=30.0,
            delay_ms=260.0,
            delay_feedback=0.26,
        ),
        "keys_synth": StyleOverride(
            reverb_archetype="hall",
            send_level_db=-18.0,
            pre_delay_ms=35.0,
            delay_ms=320.0,
            delay_feedback=0.32,
        ),
        "lead_vocal": StyleOverride(
            reverb_archetype="hall",
            send_level_db=-18.0,
            pre_delay_ms=95.0,
            delay_ms=260.0,
            delay_feedback=0.28,
        ),
        "backing_vocals": StyleOverride(
            reverb_archetype="hall",
            send_level_db=-17.0,
            pre_delay_ms=70.0,
            delay_ms=300.0,
            delay_feedback=0.32,
        ),
        "fx": StyleOverride(
            reverb_archetype="hall",
            send_level_db=-16.0,
            pre_delay_ms=45.0,
            delay_ms=380.0,
            delay_feedback=0.38,
        ),
    },
    "acoustic": {
        "drums": StyleOverride(
            send_level_db=-23.0,
            pre_delay_ms=9.0,
            hp_hz=320.0,
            lp_hz=10000.0,
        ),
        "bass": StyleOverride(
            reverb_archetype=None,
            send_level_db=-60.0,
        ),
        "guitars": StyleOverride(
            reverb_archetype="room",
            send_level_db=-21.0,
            pre_delay_ms=18.0,
            delay_ms=200.0,
            delay_feedback=0.16,
        ),
        "keys_synth": StyleOverride(
            reverb_archetype="room",
            send_level_db=-21.0,
            pre_delay_ms=20.0,
            delay_ms=230.0,
            delay_feedback=0.18,
        ),
        "lead_vocal": StyleOverride(
            reverb_archetype="plate",
            send_level_db=-20.0,
            pre_delay_ms=75.0,
            delay_ms=150.0,
            delay_feedback=0.22,
        ),
        "backing_vocals": StyleOverride(
            reverb_archetype="hall",
            send_level_db=-19.0,
            pre_delay_ms=55.0,
            delay_ms=250.0,
            delay_feedback=0.24,
        ),
        "fx": StyleOverride(
            reverb_archetype="hall",
            send_level_db=-18.0,
            pre_delay_ms=35.0,
            delay_ms=320.0,
            delay_feedback=0.30,
        ),
        "misc": StyleOverride(
            send_level_db=-23.0,
            pre_delay_ms=16.0,
        ),
    },
}




# ---------------------------------------------------------------------------
# Límites seguros por bus (para mantener Space & Depth sutil y musical)
# ---------------------------------------------------------------------------

# Rango de send_level_db por bus (valores negativos: más bajo = más seco)
SEND_LIMITS_BY_BUS: Dict[str, tuple[float, float]] = {
    #    min_dB,  max_dB
    "drums":         (-30.0, -20.0),
    "bass":          (-40.0, -24.0),
    "guitars":       (-28.0, -18.0),
    "keys_synth":    (-28.0, -18.0),
    "lead_vocal":    (-26.0, -18.0),
    "backing_vocals":(-26.0, -17.0),
    "fx":            (-24.0, -15.0),
    "misc":          (-30.0, -20.0),
}

# Rango de HPF y LPF por bus (Hz) para las colas de FX
HP_LIMITS_BY_BUS: Dict[str, tuple[float, float]] = {
    "drums":         (220.0, 480.0),
    "bass":          (60.0,  160.0),
    "guitars":       (140.0, 360.0),
    "keys_synth":    (160.0, 420.0),
    "lead_vocal":    (120.0, 260.0),
    "backing_vocals":(140.0, 280.0),
    "fx":            (200.0, 500.0),
    "misc":          (140.0, 400.0),
}

LP_LIMITS_BY_BUS: Dict[str, tuple[float, float]] = {
    "drums":         (8000.0, 12000.0),
    "bass":          (5000.0, 9000.0),
    "guitars":       (10000.0, 16000.0),
    "keys_synth":    (12000.0, 18000.0),
    "lead_vocal":    (10000.0, 16000.0),
    "backing_vocals":(11000.0, 17000.0),
    "fx":            (14000.0, 20000.0),
    "misc":          (10000.0, 16000.0),
}

# Límites globales de feedback de delay
DELAY_FEEDBACK_LIMITS: tuple[float, float] = (0.05, 0.35)

# Límites de modulación
MOD_DEPTH_LIMITS: Dict[str, tuple[float, float]] = {
    "chorus": (0.05, 0.22),
    "phaser": (0.06, 0.28),
}
MOD_RATE_LIMITS: tuple[float, float] = (0.3, 1.2)




def get_bus_definition_for_style(
    bus_key: str,
    style_key: Optional[str],
) -> BusDefinition:
    """
    Devuelve un BusDefinition para un bus dado y, opcionalmente, un estilo.

    - Si style_key es None o no existe en STYLE_PRESETS_BY_STYLE_AND_BUS:
      devuelve la definición base (BUS_DEFINITIONS[bus_key]).
    - Si existe, aplica los overrides definidos para ese bus.
    """
    base_cfg = BUS_DEFINITIONS[bus_key]

    if not style_key:
        return base_cfg

    style_key_norm = style_key.strip().lower()
    style_map = STYLE_PRESETS_BY_STYLE_AND_BUS.get(style_key_norm)
    if not style_map:
        logger.warning(
            "[SPACE_DEPTH] Estilo '%s' no reconocido para bus '%s'; usando AUTO.",
            style_key,
            bus_key,
        )
        return base_cfg

    override = style_map.get(bus_key) or style_map.get("misc")
    if override is None:
        # No hay override específico; AUTO
        return base_cfg

    return apply_style_override(base_cfg, override)


# ---------------------------------------------------------------------------
# Ajustes dinámicos: tempo y contenido de audio
# ---------------------------------------------------------------------------


def apply_tempo_to_bus_times(
    bus_cfg: BusDefinition,
    tempo_bpm: Optional[float],
) -> Tuple[BusDefinition, Dict[str, str]]:
    """
    Aplica cuantización a tempo sobre pre_delay_ms y delay_ms de un BusDefinition.

    - Si tempo_bpm es None o <= 0, devuelve bus_cfg sin cambios.
    - Si hay valores > 0 en pre_delay_ms / delay_ms, se cuantizan a la
      subdivisión musical más cercana (1/16, 1/8, 1/8 puntillo, 1/4, etc.).
    """
    if not tempo_bpm or tempo_bpm <= 0.0:
        return bus_cfg, {}

    cfg = replace(bus_cfg)
    used_notes: Dict[str, str] = {}

    if cfg.pre_delay_ms > 0.0:
        new_ms, note = quantize_ms_to_tempo_subdivision(cfg.pre_delay_ms, tempo_bpm)
        cfg.pre_delay_ms = new_ms
        used_notes["pre_delay_note"] = note

    if cfg.delay_ms and cfg.delay_ms > 0.0:
        new_ms, note = quantize_ms_to_tempo_subdivision(cfg.delay_ms, tempo_bpm)
        cfg.delay_ms = new_ms
        used_notes["delay_note"] = note

    return cfg, used_notes


def analyze_bus_audio(bus_dry: np.ndarray, samplerate: int) -> BusAudioStats:
    """
    Calcula métricas simples del audio del bus (suma de stems):

      - peak, rms, crest factor
      - centroide espectral
      - fracción de energía en graves / medios / agudos
    """
    if bus_dry.ndim != 2:
        raise ValueError(f"bus_dry con forma inesperada: {bus_dry.shape}")

    if bus_dry.shape[0] > 1:
        mono = bus_dry.mean(axis=0)
    else:
        mono = bus_dry[0]

    mono = mono.astype(np.float32)
    mono = np.nan_to_num(mono, nan=0.0)

    peak = float(np.max(np.abs(mono)))
    eps = 1e-12
    rms = float(np.sqrt(np.mean(mono ** 2) + eps))
    crest = peak / rms if rms > 0.0 else 0.0

    # Espectro en magnitud
    fft = np.fft.rfft(mono)
    mag = np.abs(fft) + eps
    freqs = np.fft.rfftfreq(mono.size, 1.0 / samplerate)

    spectral_centroid_hz = float(np.sum(freqs * mag) / np.sum(mag))

    # Bandas simples: <200 Hz, 200–4k, >4k
    low_mask = freqs < 200.0
    mid_mask = (freqs >= 200.0) & (freqs < 4000.0)
    high_mask = freqs >= 4000.0

    low_energy = float(np.sum(mag[low_mask]))
    mid_energy = float(np.sum(mag[mid_mask]))
    high_energy = float(np.sum(mag[high_mask]))

    total_energy = low_energy + mid_energy + high_energy + eps

    return BusAudioStats(
        peak=peak,
        rms=rms,
        crest=crest,
        spectral_centroid_hz=spectral_centroid_hz,
        low_fraction=low_energy / total_energy,
        mid_fraction=mid_energy / total_energy,
        high_fraction=high_energy / total_energy,
    )


def apply_audio_driven_adjustments(
    bus_cfg: BusDefinition,
    stats: BusAudioStats,
    bus_key: str,
    tempo_bpm: Optional[float] = None,
    style_key: Optional[str] = None,
) -> BusDefinition:
    """
    Ajusta send/filtros/delay/modulación del bus según:
      - contenido del audio (crest, espectro, low/mid/high),
      - tempo de la canción,
      - estilo (flamenco_rumba, edm, ballad_ambient, ...),
      - tipo de bus (drums, lead_vocal, fx, ...).

    Siempre respeta límites seguros por bus definidos en:
      - SEND_LIMITS_BY_BUS
      - HP_LIMITS_BY_BUS
      - LP_LIMITS_BY_BUS
      - DELAY_FEEDBACK_LIMITS
      - MOD_DEPTH_LIMITS / MOD_RATE_LIMITS
    """
    cfg = replace(bus_cfg)

    crest = stats.crest
    low = stats.low_fraction
    high = stats.high_fraction
    centroid = stats.spectral_centroid_hz

    # --------------------------------------------------------------
    # 1) Ajuste de send_level_db (cantidad de reverb/delay)
    # --------------------------------------------------------------
    # Base: crest factor → más sostenido => algo más de reverb, muy transitorio => menos
    # Rango base ± ~2 dB alrededor del preset.
    if crest <= 4.0:
        # pads / material súper sostenido
        crest_offset = +1.0
    elif crest >= 9.0:
        # muy transitorio (drums perc agresiva)
        crest_offset = -2.0
    else:
        # interpolación lineal entre +1.0 (crest=4) y -2.0 (crest=9)
        t = (crest - 4.0) / (9.0 - 4.0)
        crest_offset = 1.0 + (-2.0 - 1.0) * t

    # Tempo: canciones lentas admiten algo más de FX, rápidas algo menos
    tempo_offset = 0.0
    if tempo_bpm and tempo_bpm > 0.0:
        if tempo_bpm < 80.0:
            tempo_offset = +0.75
        elif tempo_bpm > 130.0:
            tempo_offset = -1.0

    # Estilo: ballad_ambient/edm algo más de FX, acústico/flamenco algo menos
    style_offset = 0.0
    style_norm = (style_key or "").strip().lower()
    if style_norm in ("ballad_ambient", "edm"):
        style_offset = +0.75
    elif style_norm in ("acoustic", "flamenco_rumba"):
        style_offset = -0.5

    wet_offset_db = crest_offset + tempo_offset + style_offset

    # Buses que deben ser más secos por naturaleza
    if bus_key in ("drums", "bass"):
        wet_offset_db *= 0.5

    cfg.send_level_db += wet_offset_db

    # Clamp por bus (no queremos nunca más de ~10–15 % de nivel wet relativo)
    min_send, max_send = SEND_LIMITS_BY_BUS.get(
        bus_key,
        (-30.0, -17.0),
    )
    cfg.send_level_db = max(min_send, min(cfg.send_level_db, max_send))

    # --------------------------------------------------------------
    # 2) HPF dinámico sobre la cola de FX
    # --------------------------------------------------------------
    if cfg.hp_hz:
        # Más graves en la fuente → subimos HPF
        if low > 0.55:
            cfg.hp_hz *= 1.25
        # Fuente muy ligera en graves → podemos relajar HPF
        elif low < 0.20:
            cfg.hp_hz *= 0.9

        hp_min, hp_max = HP_LIMITS_BY_BUS.get(
            bus_key,
            (80.0, 450.0),
        )
        cfg.hp_hz = float(max(hp_min, min(cfg.hp_hz, hp_max)))

    # --------------------------------------------------------------
    # 3) LPF dinámico sobre la cola de FX
    # --------------------------------------------------------------
    if cfg.lp_hz:
        # Fuente muy brillante → recortamos algo de top end
        if centroid > 4000.0 or high > 0.45:
            cfg.lp_hz *= 0.9
        # Fuente oscura → podemos dejar un poco más de aire
        elif centroid < 1500.0 and high < 0.25:
            cfg.lp_hz *= 1.08

        lp_min, lp_max = LP_LIMITS_BY_BUS.get(
            bus_key,
            (8000.0, 18000.0),
        )
        cfg.lp_hz = float(max(lp_min, min(cfg.lp_hz, lp_max)))

    # --------------------------------------------------------------
    # 4) Delay feedback dinámico
    # --------------------------------------------------------------
    if cfg.delay_ms and cfg.delay_ms > 0.0:
        fb = cfg.delay_feedback

        # Tempo: temas rápidos → menos feedback; lentos → algo más
        if tempo_bpm and tempo_bpm > 0.0:
            if tempo_bpm > 130.0:
                fb *= 0.7
            elif tempo_bpm < 80.0:
                fb *= 1.1

        # Material muy transitorio → reducir feedback para que no embarre
        if crest > 10.0:
            fb *= 0.8

        # Buses que deben ser discretos en eco
        if bus_key in ("drums", "bass"):
            fb *= 0.7

        # Estilos muy ambients pueden permitir algo más
        if style_norm == "ballad_ambient":
            fb *= 1.1

        fb_min, fb_max = DELAY_FEEDBACK_LIMITS
        cfg.delay_feedback = float(max(fb_min, min(fb, fb_max)))

    # --------------------------------------------------------------
    # 5) Modulación (chorus/phaser) sutil
    # --------------------------------------------------------------
    if cfg.mod_type:
        depth = cfg.mod_depth
        rate = cfg.mod_rate_hz

        # Si la fuente ya es muy brillante, reducimos un poco la profundidad
        if high > 0.45:
            depth *= 0.8
        elif high < 0.20:
            depth *= 1.05  # algo más de movimiento en cosas oscuras

        # Voces: mantener chorus muy sutil
        if cfg.mod_type == "chorus" and bus_key in ("lead_vocal", "backing_vocals"):
            depth *= 0.8

        # clamp por tipo
        depth_min, depth_max = MOD_DEPTH_LIMITS.get(
            cfg.mod_type,
            (0.05, 0.25),
        )
        depth = float(max(depth_min, min(depth, depth_max)))

        # Rate sutil, ligeramente modulado por tempo
        if tempo_bpm and tempo_bpm > 0.0:
            if tempo_bpm > 130.0:
                rate *= 1.1
            elif tempo_bpm < 80.0:
                rate *= 0.9

        rate_min, rate_max = MOD_RATE_LIMITS
        rate = float(max(rate_min, min(rate, rate_max)))

        cfg.mod_depth = depth
        cfg.mod_rate_hz = rate

    return cfg


# ---------------------------------------------------------------------------
# Construcción de la cadena de Pedalboard para un bus
# ---------------------------------------------------------------------------


def build_space_pedalboard(bus_cfg: BusDefinition) -> Pedalboard:
    """
    Crea una cadena de Pedalboard 100% WET (dry=0) para usar como bus FX.
    El dry se mezcla fuera del board con send_level_db.

    Filosofía "pro":
      - HP fuerte antes de la reverb para evitar bola de graves.
      - LP razonable para que la cola no compita con los elementos brillantes.
      - Reverbs cortas/medias, salvo en FX y estilos muy ambients.
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
            raise ValueError(
                f"Arquetipo de reverb desconocido: {bus_cfg.reverb_archetype}"
            )

        plugins.append(
            Reverb(
                room_size=params["room_size"],
                damping=params["damping"],
                width=params["width"],
                wet_level=1.0,  # 100% wet
                dry_level=0.0,  # 0% dry
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


def guess_profile_for_stem(
    stem_name: str, stem_profiles: Dict[str, str]
) -> str:
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


def resolve_bus_for_profile(profile: str) -> str:
    """
    Devuelve el bus_key a partir de un perfil de stem.
    """
    profile_key = (profile or "auto").strip()
    bus_key = PROFILE_TO_BUS.get(profile_key, "misc")
    return bus_key


# ---------------------------------------------------------------------------
# Helpers para sumar stems por bus y renderizar buses FX 100 % wet
# ---------------------------------------------------------------------------


def _load_stem_as_nc(path: Path) -> Tuple[np.ndarray, int]:
    """
    Carga un stem como array (n_channels, n_samples) float32 y devuelve (audio, samplerate).
    """
    data, samplerate = sf.read(str(path), always_2d=True)
    if data.ndim != 2:
        raise ValueError(f"Formato de audio inesperado para {path}: {data.shape}")

    audio = data.T.astype(np.float32)  # (n_channels, n_samples)
    return audio, samplerate


def _sum_stems_for_bus(stem_paths: List[Path]) -> Tuple[np.ndarray, int]:
    """
    Suma todos los stems de un bus en un solo array (n_channels, n_samples).

    - Alinea samplerate y número de canales:
      - Si hay mezcla mono/estéreo, se hace upmix/downmix sencillo.
      - Si hay stems de distintas longitudes, se zero-padean al máximo.
    """
    if not stem_paths:
        raise ValueError("No hay stems para este bus")

    audio_list: List[np.ndarray] = []
    samplerate: Optional[int] = None
    n_channels: Optional[int] = None
    max_len = 0

    for stem_path in stem_paths:
        try:
            audio, sr = _load_stem_as_nc(stem_path)
        except Exception as exc:
            logger.warning("[SPACE_DEPTH] No se pudo leer stem %s: %s", stem_path, exc)
            continue

        if samplerate is None:
            samplerate = sr
        elif sr != samplerate:
            logger.warning(
                "[SPACE_DEPTH] Samplerate inconsistente en %s (sr=%s, esperado=%s); se omite",
                stem_path,
                sr,
                samplerate,
            )
            continue

        if n_channels is None:
            n_channels = audio.shape[0]
        else:
            if audio.shape[0] != n_channels:
                # Resolución simple de mono/estéreo
                if n_channels == 2 and audio.shape[0] == 1:
                    audio = np.vstack([audio, audio])  # mono -> estéreo
                elif n_channels == 1 and audio.shape[0] == 2:
                    audio = audio.mean(axis=0, keepdims=True)  # estéreo -> mono
                else:
                    logger.warning(
                        "[SPACE_DEPTH] Nº de canales incompatible en %s (got=%d, esperado=%d); se omite",
                        stem_path,
                        audio.shape[0],
                        n_channels,
                    )
                    continue

        max_len = max(max_len, audio.shape[1])
        audio_list.append(audio)

    if samplerate is None or n_channels is None or not audio_list:
        raise RuntimeError("No se pudo construir la suma de stems para el bus")

    bus_sum = np.zeros((n_channels, max_len), dtype=np.float32)

    for audio in audio_list:
        length = audio.shape[1]
        bus_sum[:, :length] += audio

    return bus_sum, samplerate


def _render_bus_fx_stem(
    bus_key: str,
    bus_cfg: BusDefinition,
    stem_paths: List[Path],
    output_path: Path,
    tempo_bpm: Optional[float] = None,
    enable_audio_adaptive: bool = True,
) -> Tuple[float, float, BusDefinition, Optional[BusAudioStats], Dict[str, str]]:
    """
    Renderiza un stem de BUS FX 100 % wet:

      - Suma todos los stems del bus (dry) en un solo array.
      - Opcionalmente ajusta pre-delay/delay en función del tempo (tempo_bpm).
      - Opcionalmente ajusta send y filtros según el contenido del audio.
      - Aplica la cadena de Pedalboard 100 % wet.
      - Aplica el send_level_db del bus.
      - Controla clipping y calcula métricas.
      - Escribe un archivo .wav sólo FX en output_path.
    """
    if not stem_paths:
        raise ValueError(f"No hay stems para el bus {bus_key}")

    bus_dry, samplerate = _sum_stems_for_bus(stem_paths)

    # --- 1) Aplicar tempo (pre-delay / delay) ---
    tempo_notes: Dict[str, str] = {}
    cfg_for_tempo, tempo_notes = apply_tempo_to_bus_times(bus_cfg, tempo_bpm)

    # --- 2) Analizar contenido del audio y ajustar ---
    stats: Optional[BusAudioStats] = None
    final_cfg = cfg_for_tempo

    if enable_audio_adaptive:
        stats = analyze_bus_audio(bus_dry, samplerate)
        final_cfg = apply_audio_driven_adjustments(cfg_for_tempo, stats, bus_key)

    # --- 3) Construir pedalboard con la config final ---
    board = build_space_pedalboard(final_cfg)

    # FX 100 % wet sobre la suma de dry
    wet = board(bus_dry, samplerate)

    # Envío a bus FX en dB
    send_gain = db_to_linear(final_cfg.send_level_db)
    wet_scaled = wet * send_gain

    # Control anti-clipping
    peak = float(np.max(np.abs(wet_scaled)))
    if peak > 0.98:
        norm_gain = 0.98 / peak
        wet_scaled *= norm_gain
        peak = 0.98

    # RMS global
    rms = float(np.sqrt(np.mean(wet_scaled ** 2.0)))

    # Guardar como (n_samples, n_channels)
    processed_out = wet_scaled.T
    sf.write(str(output_path), processed_out, samplerate)

    peak_dbfs = amplitude_to_dbfs(peak)
    rms_dbfs = amplitude_to_dbfs(rms)

    logger.info(
        "[SPACE_DEPTH] Bus FX %s (%d stems) -> %s | peak=%.2f dBFS | rms=%.2f dBFS",
        bus_key,
        len(stem_paths),
        output_path.name,
        peak_dbfs,
        rms_dbfs,
    )

    return peak_dbfs, rms_dbfs, final_cfg, stats, tempo_notes


# ---------------------------------------------------------------------------
# Helper: renderizar un bus FX a partir de una configuración ya fijada
# ---------------------------------------------------------------------------

def _render_bus_fx_stem_from_cfg(
    bus_key: str,
    bus_cfg: BusDefinition,
    stem_paths: List[Path],
    output_path: Path,
) -> tuple[float, float]:
    """
    Renderiza un stem de BUS FX 100 % wet usando una configuración YA calculada
    (por el análisis previo). No hace análisis, no ajusta nada a tempo, etc.

    Pasos:
      - Suma todos los stems del bus en un solo array.
      - Aplica la cadena de Pedalboard 100 % wet según bus_cfg.
      - Aplica el send_level_db del bus.
      - Controla clipping y calcula peak/rms en dBFS.
      - Escribe un archivo .wav sólo FX en output_path.
    """
    if not stem_paths:
        raise ValueError(f"No hay stems para el bus {bus_key}")

    # Suma de stems en un solo array (n_channels, n_samples)
    bus_dry, samplerate = _sum_stems_for_bus(stem_paths)

    # Cadena 100 % wet (HP/LP + pre-delay + reverb + delay + mod + trim final)
    board = build_space_pedalboard(bus_cfg)

    # Procesado FX 100 % wet sobre la suma dry
    wet = board(bus_dry, samplerate)

    # Aplicar nivel de envío en dB
    send_gain = db_to_linear(bus_cfg.send_level_db)
    wet_scaled = wet * send_gain

    # Control anti-clipping suave
    peak = float(np.max(np.abs(wet_scaled)))
    if peak > 0.98:
        norm_gain = 0.98 / peak
        wet_scaled *= norm_gain
        peak = 0.98

    # RMS global
    rms = float(np.sqrt(np.mean(wet_scaled ** 2.0)))

    # Guardar como (n_samples, n_channels)
    processed_out = wet_scaled.T
    sf.write(str(output_path), processed_out, samplerate)

    peak_dbfs = amplitude_to_dbfs(peak)
    rms_dbfs = amplitude_to_dbfs(rms)

    logger.info(
        "[SPACE_DEPTH] Bus FX %s -> %s | peak=%.2f dBFS | rms=%.2f dBFS",
        bus_key,
        output_path.name,
        peak_dbfs,
        rms_dbfs,
    )

    return peak_dbfs, rms_dbfs


# ---------------------------------------------------------------------------
# Entry point de stage: run_space_depth (corrección desde el CSV de análisis)
# ---------------------------------------------------------------------------

def run_space_depth(
    input_media_dir: Path,
    output_media_dir: Path,
    analysis_csv_path: Path,
) -> None:
    """
    Stage de Space & Depth (versión CORRECCIÓN).

    Supone que:
      - El análisis previo ya ha generado un CSV en analysis_csv_path
        (p.ej. con analyze_space_depth/export_space_depth_to_csv).
      - El CSV contiene una fila por bus FX con todos los parámetros ya
        calculados (reverb_archetype, send_level_db, pre_delay_ms, ...).

    Este stage:
      1) Copia todos los stems secos de input_media_dir a output_media_dir.
      2) Lee el CSV de análisis.
      3) Para cada fila/bus:
           - Localiza los stems de ese bus (columna 'stem_names').
           - Reconstruye un BusDefinition a partir de la fila.
           - Genera un stem FX 100 % wet: bus_<bus_key>_space.wav

    NO recalcula análisis, ni tempo, ni ajustes audio-driven: únicamente aplica
    lo que haya decidido el stage de análisis.
    """
    output_media_dir.mkdir(parents=True, exist_ok=True)

    # ----------------------------------------------------------------------
    # 1) Copiar todos los stems secos
    # ----------------------------------------------------------------------
    wav_files = sorted(input_media_dir.glob("*.wav"))
    if not wav_files:
        logger.warning(
            "[SPACE_DEPTH] No se encontraron stems .wav en %s",
            input_media_dir,
        )
        return

    logger.info(
        "[SPACE_DEPTH] Copiando %d stems secos %s -> %s",
        len(wav_files),
        input_media_dir,
        output_media_dir,
    )

    for stem_path in wav_files:
        dest = output_media_dir / stem_path.name
        try:
            if dest.resolve() == stem_path.resolve():
                # Caso raro: input_dir == output_dir
                continue
        except Exception:
            # Si resolve() falla (p.ej. por permisos), asumimos que podemos copiar
            pass

        try:
            shutil.copy2(stem_path, dest)
        except Exception as exc:
            logger.warning(
                "[SPACE_DEPTH] No se pudo copiar stem seco %s -> %s: %s",
                stem_path,
                dest,
                exc,
            )

    # ----------------------------------------------------------------------
    # 2) Leer CSV de análisis
    # ----------------------------------------------------------------------
    if not analysis_csv_path.exists():
        logger.error(
            "[SPACE_DEPTH] CSV de análisis no encontrado: %s. "
            "Asegúrate de ejecutar antes el stage de análisis.",
            analysis_csv_path,
        )
        return

    logger.info("[SPACE_DEPTH] Leyendo análisis desde %s", analysis_csv_path)

    def _parse_float(value: str, default: float = 0.0) -> float:
        value = (value or "").strip()
        if not value:
            return default
        try:
            return float(value)
        except ValueError:
            return default

    buses_procesados = 0

    with analysis_csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        # Comprobamos mínimamente que está el campo clave
        if "bus_fx_stem_name" not in reader.fieldnames and "stem_name" not in reader.fieldnames:
            raise RuntimeError(
                "[SPACE_DEPTH] El CSV de análisis no contiene "
                "'bus_fx_stem_name' ni 'stem_name'. Revisa el script de análisis."
            )

        for row in reader:
            # Nombre del stem FX resultante
            bus_fx_stem_name = (
                (row.get("bus_fx_stem_name") or row.get("stem_name") or "").strip()
            )
            if not bus_fx_stem_name:
                logger.warning(
                    "[SPACE_DEPTH] Fila sin nombre de bus FX stem, se omite: %s",
                    row,
                )
                continue

            bus_key = (row.get("bus_key") or "misc").strip()

            # Lista de stems de entrada para este bus (columna 'stem_names')
            stem_names_field = (row.get("stem_names") or "").strip()
            if not stem_names_field:
                logger.warning(
                    "[SPACE_DEPTH] Fila sin 'stem_names' para bus '%s'; "
                    "no se puede reconstruir la suma del bus. Se omite.",
                    bus_key,
                )
                continue

            stem_names = [s.strip() for s in stem_names_field.split("|") if s.strip()]
            stems_for_bus: List[Path] = []

            for stem_name in stem_names:
                stem_path = input_media_dir / stem_name
                if not stem_path.exists():
                    logger.warning(
                        "[SPACE_DEPTH] Stem '%s' (bus '%s') no existe en %s; se omite.",
                        stem_name,
                        bus_key,
                        input_media_dir,
                    )
                    continue
                stems_for_bus.append(stem_path)

            if not stems_for_bus:
                logger.warning(
                    "[SPACE_DEPTH] Ningún stem válido encontrado para bus '%s'; se omite.",
                    bus_key,
                )
                continue

            # ------------------------------------------------------------------
            # Reconstruir BusDefinition a partir de la fila del CSV
            # ------------------------------------------------------------------
            reverb_arch = (row.get("reverb_archetype") or "").strip() or None
            send_level_db = _parse_float(row.get("send_level_db"), default=-24.0)
            pre_delay_ms = _parse_float(row.get("pre_delay_ms"), default=0.0)

            delay_ms_val = _parse_float(row.get("delay_ms"), default=0.0)
            delay_ms = delay_ms_val if delay_ms_val > 0.0 else None

            delay_feedback = _parse_float(row.get("delay_feedback"), default=0.0)

            mod_type = (row.get("mod_type") or "").strip() or None
            mod_rate_hz = _parse_float(row.get("mod_rate_hz"), default=0.0)
            mod_depth = _parse_float(row.get("mod_depth"), default=0.0)

            hp_hz_val = _parse_float(row.get("hp_hz"), default=0.0)
            hp_hz = hp_hz_val if hp_hz_val > 0.0 else None

            lp_hz_val = _parse_float(row.get("lp_hz"), default=0.0)
            lp_hz = lp_hz_val if lp_hz_val > 0.0 else None

            bus_cfg = BusDefinition(
                key=bus_key,
                description=f"Config desde análisis (style={row.get('style_key', '').strip()})",
                reverb_archetype=reverb_arch,
                send_level_db=send_level_db,
                pre_delay_ms=pre_delay_ms,
                delay_ms=delay_ms,
                delay_feedback=delay_feedback,
                mod_type=mod_type,
                mod_rate_hz=mod_rate_hz,
                mod_depth=mod_depth,
                hp_hz=hp_hz,
                lp_hz=lp_hz,
                output_trim_db=0.0,  # opcional: podrías añadirlo al CSV si lo necesitas
            )

            output_path = output_media_dir / bus_fx_stem_name

            try:
                peak_dbfs, rms_dbfs = _render_bus_fx_stem_from_cfg(
                    bus_key=bus_key,
                    bus_cfg=bus_cfg,
                    stem_paths=stems_for_bus,
                    output_path=output_path,
                )
                buses_procesados += 1
            except Exception as exc:
                logger.exception(
                    "[SPACE_DEPTH] Error renderizando bus FX '%s': %s",
                    bus_key,
                    exc,
                )
                continue

            logger.info(
                "[SPACE_DEPTH] Bus '%s' procesado -> %s (peak=%.2f dBFS, rms=%.2f dBFS)",
                bus_key,
                output_path.name,
                peak_dbfs,
                rms_dbfs,
            )

    logger.info(
        "[SPACE_DEPTH] Corrección completada: %d buses FX generados en %s "
        "(stems secos + buses FX listos para el mixdown).",
        buses_procesados,
        output_media_dir,
    )



__all__ = [
    "run_space_depth",
    "BusDefinition",
    "BUS_DEFINITIONS",
    "PROFILE_TO_BUS",
    "STYLE_PRESETS_BY_STYLE_AND_BUS",
]