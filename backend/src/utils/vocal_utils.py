# C:\mix-master\backend\src\utils\vocal_utils.py

from __future__ import annotations

from typing import Set

# Perfiles que consideramos voces
VOCAL_PROFILES: Set[str] = {
    "Lead_Vocal_Melodic",
    "Lead_Vocal_Rap",
    "Backing_Vocals",
    "Vocal_Adlibs_Shouts",
    "Choir_Group",
}


def is_vocal_profile(instrument_profile: str | None) -> bool:
    """
    Devuelve True si el instrument_profile corresponde a una voz.

    La condición de afinación depende EXCLUSIVAMENTE del instrument_profile,
    no del análisis de pitch (aunque luego lo uses).
    """
    if not instrument_profile:
        return False

    if instrument_profile in VOCAL_PROFILES:
        return True

    # Por si en el futuro añades variantes tipo Lead_Vocal_Algo
    if instrument_profile.startswith("Lead_Vocal_"):
        return True

    return False
