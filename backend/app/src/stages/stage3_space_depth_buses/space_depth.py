from __future__ import annotations
import logging
import json
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
def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(x, hi))
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
# Rango de send_level_db por bus (todas cifras NEGATIVAS)
SEND_LIMITS_BY_BUS: Dict[str, Tuple[float, float]] = {
    #   min_dB,   max_dB
    "drums":        (-32.0, -22.0),
    "bass":         (-40.0, -26.0),
    "guitars":      (-30.0, -20.0),
    "keys_synth":   (-30.0, -20.0),
    "lead_vocal":   (-28.0, -19.0),
    "backing_vocals": (-28.0, -18.0),
    "fx":           (-26.0, -17.0),
    "misc":         (-32.0, -22.0),
}
# HPF y LPF para colas de FX
HP_LIMITS_BY_BUS: Dict[str, Tuple[float, float]] = {
    "drums":        (260.0, 480.0),
    "bass":         (70.0,  160.0),
    "guitars":      (160.0, 360.0),
    "keys_synth":   (180.0, 420.0),
    "lead_vocal":   (130.0, 260.0),
    "backing_vocals": (150.0, 280.0),
    "fx":           (230.0, 520.0),
    "misc":         (160.0, 400.0),
}
LP_LIMITS_BY_BUS: Dict[str, Tuple[float, float]] = {
    "drums":        (8000.0, 12000.0),
    "bass":         (5000.0, 9000.0),
    "guitars":      (10000.0, 16000.0),
    "keys_synth":   (12000.0, 18000.0),
    "lead_vocal":   (10000.0, 16000.0),
    "backing_vocals": (11000.0, 17000.0),
    "fx":           (14000.0, 20000.0),
    "misc":         (10000.0, 16000.0),
}
# Feedback global (lineal 0..1) – muy conservador
DELAY_FEEDBACK_LIMITS: Tuple[float, float] = (0.05, 0.25)
# Profundidad y rate de modulación
MOD_DEPTH_LIMITS: Dict[str, Tuple[float, float]] = {
    "chorus": (0.02, 0.10),
    "phaser": (0.04, 0.18),
}
MOD_RATE_LIMITS: Tuple[float, float] = (0.25, 1.2)
def sanitize_bus_cfg_for_mixing(
    bus_cfg: BusDefinition,
    bus_key: str,
) -> BusDefinition:
    """
    Aplica límites duros a la configuración del bus para evitar
    reverb/delay/mod excesivos o "rotos".
    - Drums / bass: sin delay ni modulación.
    - Voces: slapback suave y chorus muy sutil.
    - Guitarras / keys / synth: delay moderado, chorus suave.
    - FX: es el único que puede ir un poco más lejos.
    """
    cfg = replace(bus_cfg)
    key = bus_key
    # -------------------- 1) Send level seguro --------------------
    send_min, send_max = SEND_LIMITS_BY_BUS.get(
        key,
        (-32.0, -20.0),
    )
    cfg.send_level_db = _clamp(cfg.send_level_db, send_min, send_max)
    # -------------------- 2) Pre-delay --------------------
    if cfg.pre_delay_ms < 0.0:
        cfg.pre_delay_ms = 0.0
    if key in ("lead_vocal", "backing_vocals"):
        cfg.pre_delay_ms = min(cfg.pre_delay_ms, 120.0)
    else:
        cfg.pre_delay_ms = min(cfg.pre_delay_ms, 60.0)
    # -------------------- 3) Filtros HP/LP --------------------
    if cfg.hp_hz:
        hp_min, hp_max = HP_LIMITS_BY_BUS.get(key, (120.0, 450.0))
        cfg.hp_hz = float(_clamp(cfg.hp_hz, hp_min, hp_max))
    if cfg.lp_hz:
        lp_min, lp_max = LP_LIMITS_BY_BUS.get(key, (8000.0, 18000.0))
        cfg.lp_hz = float(_clamp(cfg.lp_hz, lp_min, lp_max))
    # -------------------- 4) Delay por tipo de bus --------------------
    if cfg.delay_ms is not None and cfg.delay_ms <= 0.0:
        cfg.delay_ms = None
    if key in ("drums", "bass", "misc"):
        # Nada de delays creativos aquí
        cfg.delay_ms = None
        cfg.delay_feedback = 0.0
    elif key in ("lead_vocal", "backing_vocals"):
        if cfg.delay_ms:
            cfg.delay_ms = _clamp(cfg.delay_ms, 90.0, 260.0)
            fb = _clamp(cfg.delay_feedback, *DELAY_FEEDBACK_LIMITS)
            # voces: feedback más discreto todavía
            cfg.delay_feedback = min(fb, 0.18)
    elif key in ("guitars", "keys_synth"):
        if cfg.delay_ms:
            cfg.delay_ms = _clamp(cfg.delay_ms, 120.0, 300.0)
            cfg.delay_feedback = _clamp(cfg.delay_feedback, *DELAY_FEEDBACK_LIMITS)
    elif key == "fx":
        if cfg.delay_ms:
            cfg.delay_ms = _clamp(cfg.delay_ms, 180.0, 420.0)
            fb_min, fb_max = DELAY_FEEDBACK_LIMITS
            cfg.delay_feedback = _clamp(cfg.delay_feedback, fb_min, fb_max + 0.05)
    # -------------------- 5) Modulación --------------------
    if cfg.mod_type not in ("chorus", "phaser"):
        cfg.mod_type = None
        cfg.mod_rate_hz = 0.0
        cfg.mod_depth = 0.0
        return cfg
    # Drums / bass / misc: sin mod
    if key in ("drums", "bass", "misc"):
        cfg.mod_type = None
        cfg.mod_rate_hz = 0.0
        cfg.mod_depth = 0.0
        return cfg
    # Voces / guitarras / teclas → chorus muy sutil
    if cfg.mod_type == "chorus":
        if key not in ("lead_vocal", "backing_vocals", "guitars", "keys_synth"):
            cfg.mod_type = None
            cfg.mod_rate_hz = 0.0
            cfg.mod_depth = 0.0
            return cfg
        depth_min, depth_max = MOD_DEPTH_LIMITS["chorus"]
        cfg.mod_depth = _clamp(cfg.mod_depth or 0.05, depth_min, depth_max)
        rate_min, rate_max = MOD_RATE_LIMITS
        cfg.mod_rate_hz = _clamp(cfg.mod_rate_hz or 0.8, rate_min, rate_max)
    # FX → phaser algo más evidente pero todavía controlado
    elif cfg.mod_type == "phaser":
        if key != "fx":
            cfg.mod_type = None
            cfg.mod_rate_hz = 0.0
            cfg.mod_depth = 0.0
            return cfg
        depth_min, depth_max = MOD_DEPTH_LIMITS["phaser"]
        cfg.mod_depth = _clamp(cfg.mod_depth or 0.12, depth_min, depth_max)
        rate_min, rate_max = MOD_RATE_LIMITS
        cfg.mod_rate_hz = _clamp(cfg.mod_rate_hz or 0.5, rate_min, rate_max)
    return cfg
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
    Ajuste muy sutil del bus según el contenido:
      - Pequeños cambios de send según crest.
      - Ajuste suave de HP/LP según graves/agudos presentes.
      - Tempo/estilo afectan sólo un poco.
    Al final siempre pasa por sanitize_bus_cfg_for_mixing, que impone
    los límites duros por bus para evitar delays/chorus descontrolados.
    """
    cfg = replace(bus_cfg)
    crest = stats.crest
    low = stats.low_fraction
    high = stats.high_fraction
    centroid = stats.spectral_centroid_hz
    style_norm = (style_key or "").strip().lower()
    # ---------------- 1) Send: +/- ~1.5 dB máximo ----------------
    wet_offset = 0.0
    # Más dinámica (= crest alto) → menos reverb
    if crest < 4.0:
        wet_offset += 0.8
    elif crest > 10.0:
        wet_offset -= 1.2
    else:
        # Interpolación suave entre +0.8 (crest=4) y -1.2 (crest=10)
        t = (crest - 4.0) / (10.0 - 4.0)
        wet_offset += 0.8 + (-1.2 - 0.8) * t
    # Temas muy lentos → algo más de cola; muy rápidos → un pelín menos
    if tempo_bpm and tempo_bpm > 0.0:
        if tempo_bpm < 80.0:
            wet_offset += 0.5
        elif tempo_bpm > 130.0:
            wet_offset -= 0.5
    # Estilos “ambient / edm” aceptan un pelo más
    if style_norm in ("ballad_ambient", "edm"):
        wet_offset += 0.4
    elif style_norm in ("acoustic", "flamenco_rumba"):
        wet_offset -= 0.4
    # Drums / bass siempre más secos
    if bus_key in ("drums", "bass"):
        wet_offset *= 0.5
    cfg.send_level_db += wet_offset
    # ---------------- 2) HP/LP dinámicos suaves ------------------
    if cfg.hp_hz:
        if low > 0.55:
            cfg.hp_hz *= 1.15
        elif low < 0.20:
            cfg.hp_hz *= 0.92
    if cfg.lp_hz:
        if centroid > 4000.0 or high > 0.45:
            cfg.lp_hz *= 0.9
        elif centroid < 1500.0 and high < 0.25:
            cfg.lp_hz *= 1.08
    # Finalmente imponemos TODOS los límites duros por bus
    cfg = sanitize_bus_cfg_for_mixing(cfg, bus_key)
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
    data, samplerate = sf.read(str(path), always_2d=True, dtype="float32")
    if data.ndim != 2:
        raise ValueError(f"Formato de audio inesperado para {path}: {data.shape}")
    audio = data.T  # (n_channels, n_samples) ya float32 por dtype
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
      - Opcionalmente ajusta pre-delay/delay en funcion del tempo (tempo_bpm).
      - Opcionalmente ajusta send y filtros segun el contenido del audio.
      - Aplica la cadena de Pedalboard 100 % wet.
      - Aplica el send_level_db del bus.
      - Controla clipping y calcula metricas.
      - Escribe un archivo .wav solo FX en output_path.
    """
    if not stem_paths:
        raise ValueError(f"No hay stems para el bus {bus_key}")
    bus_dry, samplerate = _sum_stems_for_bus(stem_paths)
    tempo_notes: Dict[str, str] = {}
    cfg_for_tempo, tempo_notes = apply_tempo_to_bus_times(bus_cfg, tempo_bpm)
    stats: Optional[BusAudioStats] = None
    final_cfg = cfg_for_tempo
    if enable_audio_adaptive:
        stats = analyze_bus_audio(bus_dry, samplerate)
        final_cfg = apply_audio_driven_adjustments(cfg_for_tempo, stats, bus_key)
    board = build_space_pedalboard(final_cfg)
    wet = board(bus_dry, samplerate)
    send_gain = db_to_linear(final_cfg.send_level_db)
    wet *= send_gain
    peak = float(np.max(np.abs(wet)))
    if peak > 0.98:
        norm_gain = 0.98 / peak
        wet *= norm_gain
        peak = 0.98
    rms = float(np.sqrt(np.mean(wet ** 2.0)))
    processed_out = wet.T
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
def _render_bus_fx_stem_from_cfg(
    bus_key: str,
    bus_cfg: BusDefinition,
    stem_paths: List[Path],
    output_path: Path,
) -> tuple[float, float]:
    """
    Renderiza un stem de BUS FX 100 % wet usando una configuracion YA calculada
    (por el analisis previo). No hace analisis, no ajusta nada a tempo, etc.
    Pasos:
      - Suma todos los stems del bus en un solo array.
      - Aplica la cadena de Pedalboard 100 % wet segun bus_cfg.
      - Aplica el send_level_db del bus.
      - Controla clipping y calcula peak/rms en dBFS.
      - Escribe un archivo .wav solo FX en output_path.
    """
    if not stem_paths:
        raise ValueError(f"No hay stems para el bus {bus_key}")
    bus_dry, samplerate = _sum_stems_for_bus(stem_paths)
    board = build_space_pedalboard(bus_cfg)
    wet = board(bus_dry, samplerate)
    send_gain = db_to_linear(bus_cfg.send_level_db)
    wet *= send_gain
    peak = float(np.max(np.abs(wet)))
    if peak > 0.98:
        norm_gain = 0.98 / peak
        wet *= norm_gain
        peak = 0.98
    rms = float(np.sqrt(np.mean(wet ** 2.0)))
    processed_out = wet.T
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
def run_space_depth(
    input_media_dir: Path,
    output_media_dir: Path,
    analysis_json_path: Path,
) -> None:
    """
    Stage de Space & Depth (versión CORRECCIÓN).
    Supone que:
      - El análisis previo ya ha generado un JSON en analysis_json_path
        (p.ej. con analyze_space_depth/export_space_depth_to_json).
      - El JSON contiene una fila por bus FX con todos los parámetros ya
        calculados (reverb_archetype, send_level_db, pre_delay_ms, ...).
    Este stage:
      1) Copia todos los stems secos de input_media_dir a output_media_dir.
      2) Lee el JSON de análisis.
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
                continue
        except Exception:
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
    # 2) Leer JSON de análisis
    # ----------------------------------------------------------------------
    if not analysis_json_path.exists():
        logger.error(
            "[SPACE_DEPTH] JSON de análisis no encontrado: %s. "
            "Asegúrate de ejecutar antes el stage de análisis.",
            analysis_json_path,
        )
        return
    logger.info("[SPACE_DEPTH] Leyendo análisis desde %s", analysis_json_path)
    def _parse_float(value: str, default: float = 0.0) -> float:
        value = (value or "").strip() if isinstance(value, str) else value
        if value is None or value == "":
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    buses_procesados = 0
    log_rows: list[dict[str, object]] = []
    payload = json.loads(analysis_json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise RuntimeError("[SPACE_DEPTH] El JSON de análisis no contiene una lista.")
    for row in payload:
        if not isinstance(row, dict):
            continue
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
            output_trim_db=0.0,
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
        log_rows.append(
            {
                "bus_key": bus_key,
                "bus_fx_stem_name": bus_fx_stem_name,
                "stem_names": stem_names,
                "output_path": str(output_path),
                "peak_dbfs": peak_dbfs,
                "rms_dbfs": rms_dbfs,
                "send_level_db": send_level_db,
                "reverb_archetype": reverb_arch,
            }
        )
        logger.info(
            "[SPACE_DEPTH] Bus '%s' procesado -> %s (peak=%.2f dBFS, rms=%.2f dBFS)",
            bus_key,
            output_path.name,
            peak_dbfs,
            rms_dbfs,
        )
    log_json_path = output_media_dir / "space_depth_log.json"
    log_json_path.write_text(
        json.dumps(log_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("[SPACE_DEPTH] Log JSON escrito en %s", log_json_path)
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
