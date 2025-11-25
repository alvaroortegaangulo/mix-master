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
# Definición de buses y arquetipos de reverb
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
# Los ajustes están pensados para ser "mezclables" y no para demos
# extremas: tiempos y send realistas, HP agresivos y plates/halls
# típicos de esos géneros.


STYLE_PRESETS_BY_STYLE_AND_BUS: Dict[str, Dict[str, StyleOverride]] = {
    # ------------------------------------------------------------------
    # FLAMENCO / RUMBA: natural, íntimo. Guitarras y voces 1-2 dB más
    # húmedas; drums algo más secos. FX algo más largos pero filtrados.
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # URBAN / TRAP / HIP-HOP: drums/bass muy secos; keys/FX más largos.
    # Lead con pre-delay largo y hall/plate moderno.
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # ROCK / POP-ROCK: rooms algo mayores en drums, guitarras con plate,
    # voces con plate corto, FX moderados.
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # LATIN POP / REGGAETON: entre flamenco y urban. Algo más húmedo en
    # voces, pero drums/bass bastante contenidos.
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # EDM / CLUB: drums y bass muy secos; keys y FX con halls algo más
    # largos; voces en hall moderno pero sin exagerar.
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # BALLAD / AMBIENT: todo 2-3 dB más húmedo que base, pero con HH
    # fuertes y halls moderados.
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # ACÚSTICO / SINGER-SONGWRITER: todo bastante seco, rooms cortos,
    # plate moderado en voz y algo de hall en coros.
    # ------------------------------------------------------------------
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
) -> Tuple[float, float]:
    """
    Renderiza un stem de BUS FX 100 % wet:

      - Suma todos los stems del bus (dry) en un solo array.
      - Aplica la cadena de Pedalboard 100 % wet.
      - Aplica el send_level_db del bus como ganancia.
      - Controla clipping y calcula métricas.
      - Escribe un archivo .wav sólo FX en output_path.
    """
    if not stem_paths:
        raise ValueError(f"No hay stems para el bus {bus_key}")

    bus_dry, samplerate = _sum_stems_for_bus(stem_paths)

    board = build_space_pedalboard(bus_cfg)

    # FX 100 % wet sobre la suma de dry
    wet = board(bus_dry, samplerate)

    # Envío a bus FX en dB
    send_gain = db_to_linear(bus_cfg.send_level_db)
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

    return peak_dbfs, rms_dbfs


# ---------------------------------------------------------------------------
# Entry point de stage: run_space_depth (nuevo diseño: genera buses FX)
# ---------------------------------------------------------------------------


def run_space_depth(
    input_media_dir: Path,
    output_media_dir: Path,
    analysis_csv_path: Path,
    stem_profiles: Optional[Dict[str, str]] = None,
    bus_styles: Optional[Dict[str, str]] = None,
) -> None:
    """
    Stage de Space & Depth (versión bus-FX).

    Nuevo diseño:
      - Copia todos los stems secos de input_media_dir a output_media_dir.
      - Agrupa stems por bus (drums, guitars, lead_vocal...).
      - Para cada bus:
          * Suma los stems del bus en un solo array.
          * Aplica la cadena de reverb/delay/mod 100 % wet.
          * Aplica el send_level_db del bus.
          * Escribe un stem de bus FX 100 % wet: bus_<bus_key>_space.wav

    El mixdown posterior sumará:
      - los stems secos (copiados)
      - + los stems bus_XXX_space.wav (sólo FX).

    Parámetros:
      - stem_profiles: dict opcional {stem_name (o base) -> perfil}.
      - bus_styles: dict opcional {bus_key -> style_key} o {"default": style_key}.
        Los style_key deben coincidir con los usados en STYLE_PRESETS_BY_STYLE_AND_BUS:
          flamenco_rumba, urban_trap, rock, latin_pop, edm, ballad_ambient, acoustic.
    """
    stem_profiles = stem_profiles or {}
    bus_styles = bus_styles or {}

    output_media_dir.mkdir(parents=True, exist_ok=True)

    wav_files = sorted(input_media_dir.glob("*.wav"))
    if not wav_files:
        logger.warning(
            "[SPACE_DEPTH] No se encontraron stems .wav en %s",
            input_media_dir,
        )
        return

    logger.info(
        "[SPACE_DEPTH] Procesando %d stems desde %s -> %s (bus-FX)",
        len(wav_files),
        input_media_dir,
        output_media_dir,
    )

    # ------------------------------------------------------------------
    # 1) Copiar stems secos tal cual a output_media_dir
    # ------------------------------------------------------------------
    for stem_path in wav_files:
        dest = output_media_dir / stem_path.name
        if dest.resolve() == stem_path.resolve():
            # Caso raro: input_dir == output_dir
            continue
        try:
            shutil.copy2(stem_path, dest)
        except Exception as exc:
            logger.warning(
                "[SPACE_DEPTH] No se pudo copiar stem seco %s -> %s: %s",
                stem_path,
                dest,
                exc,
            )

    # ------------------------------------------------------------------
    # 2) Agrupar stems por bus usando stem_profiles → PROFILE_TO_BUS
    # ------------------------------------------------------------------
    bus_to_stems: Dict[str, List[Path]] = defaultdict(list)

    for stem_path in wav_files:
        stem_name = stem_path.name
        profile = guess_profile_for_stem(stem_name, stem_profiles)
        bus_key = resolve_bus_for_profile(profile)
        bus_to_stems[bus_key].append(stem_path)

    # ------------------------------------------------------------------
    # 3) CSV de análisis: una fila por BUS FX stem
    # ------------------------------------------------------------------
    with analysis_csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            [
                "stem_name",         # nombre del BUS FX stem (bus_<bus_key>_space.wav)
                "bus_key",           # drums, guitars, lead_vocal, ...
                "style_key",         # flamenco_rumba, urban_trap, ...
                "reverb_archetype",  # room/plate/hall/spring
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
                "num_input_stems",   # cuántos stems secos alimentan este bus
            ]
        )

        # ------------------------------------------------------------------
        # 4) Para cada bus, generar bus FX stem 100 % wet
        # ------------------------------------------------------------------
        for bus_key, stems_for_bus in bus_to_stems.items():
            if not stems_for_bus:
                continue

            # Estilo seleccionado para este bus (si lo hay)
            style_key = bus_styles.get(bus_key) or bus_styles.get("default")

            bus_cfg = get_bus_definition_for_style(bus_key, style_key)

            bus_fx_name = f"bus_{bus_key}_space.wav"
            output_path = output_media_dir / bus_fx_name

            try:
                peak_dbfs, rms_dbfs = _render_bus_fx_stem(
                    bus_key=bus_key,
                    bus_cfg=bus_cfg,
                    stem_paths=stems_for_bus,
                    output_path=output_path,
                )
            except Exception as exc:
                logger.exception(
                    "[SPACE_DEPTH] Error renderizando bus FX %s: %s",
                    bus_key,
                    exc,
                )
                continue

            writer.writerow(
                [
                    bus_fx_name,
                    bus_key,
                    style_key or "",
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
                    len(stems_for_bus),
                ]
            )

    logger.info(
        "[SPACE_DEPTH] Completado. Stems secos + buses FX en %s, CSV en %s",
        output_media_dir,
        analysis_csv_path,
    )


__all__ = [
    "run_space_depth",
    "BusDefinition",
    "BUS_DEFINITIONS",
    "PROFILE_TO_BUS",
    "STYLE_PRESETS_BY_STYLE_AND_BUS",
]
