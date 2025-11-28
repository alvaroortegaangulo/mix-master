# C:\mix-master\backend\src\utils\profiles_utils.py

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any

from .analysis_utils import BASE_DIR

PROFILES_PATH = BASE_DIR / "struct" / "profiles.json"
_PROFILES_CACHE: Dict[str, Any] | None = None


def _load_profiles() -> Dict[str, Any]:
    global _PROFILES_CACHE
    if _PROFILES_CACHE is None:
        if not PROFILES_PATH.exists():
            raise FileNotFoundError(f"No se ha encontrado profiles.json en {PROFILES_PATH}")
        with PROFILES_PATH.open("r", encoding="utf-8") as f:
            _PROFILES_CACHE = json.load(f)
    return _PROFILES_CACHE


def get_instrument_profile(instrument_id: str) -> Dict[str, Any]:
    """
    Devuelve el perfil de instrumento desde profiles.json.
    Si no existe el id, devuelve el perfil 'Other' (si existe) o un dict vacío.
    """
    profiles = _load_profiles()
    insts = profiles.get("instrument_profiles", {})
    profile = insts.get(instrument_id)
    if profile is None:
        profile = insts.get("Other", {})
    return profile


def get_instrument_family(instrument_profile_id: str) -> str:
    """
    Agrupa instrument_profiles en familias lógicas:
      - 'Drums', 'Bass', 'Guitars', 'KeysSynths', 'LeadVox', 'BGV', 'FX', 'Ambience', 'Other'.

    Se basa solo en el nombre del perfil (heurística).
    """
    if not instrument_profile_id:
        return "Other"

    name = instrument_profile_id

    # Drums / Percusión
    if (
        name.startswith("Kick")
        or name.startswith("Snare")
        or name.startswith("HiHat")
        or name.startswith("Tom")
        or "Percussion" in name
        or "Bongo" in name
        or "Conga" in name
        or "Drums" in name
    ):
        return "Drums"

    # Bass
    if "Bass" in name:
        return "Bass"

    # Guitars
    if "Guitar" in name:
        return "Guitars"

    # Voces lead
    if name.startswith("Lead_Vocal"):
        return "LeadVox"

    # Coros / BGV
    if "Backing_Vocals" in name or "Choir" in name:
        return "BGV"

    # Keys / Synths
    if "Keys" in name or "Piano" in name or "Synth" in name:
        return "KeysSynths"

    # FX
    if "FX" in name or "EarCandy" in name:
        return "FX"

    # Ambience / Atmos
    if "Ambience" in name or "Atmos" in name:
        return "Ambience"

    return "Other"


def get_hpf_lpf_targets(instrument_profile_id: str) -> tuple[float | None, float | None]:
    """
    Devuelve (hpf_hz, lpf_hz) recomendados para un instrument_profile.

    Prioridad:
      1) Si instrument_profiles.json define campos 'hpf_hz' / 'lpf_hz' para ese perfil, se usan esos.
      2) Si no, se aplica un mapping por nombre (Kick, Bass, Lead_Vocal, etc.).
      3) Fallback genérico: HPF 20 Hz, LPF 20000 Hz.

    Devolvemos None si queremos 'sin filtro' por ese lado.
    """
    global _PROFILES_CACHE

    profiles = _load_profiles()
    prof = profiles.get(instrument_profile_id, {})

    hpf = prof.get("hpf_hz")
    lpf = prof.get("lpf_hz")

    if hpf is not None or lpf is not None:
        hpf_val = float(hpf) if hpf is not None else None
        lpf_val = float(lpf) if lpf is not None else None
        return hpf_val, lpf_val

    name = instrument_profile_id or ""

    # Heurísticas simples por nombre de perfil
    if name.startswith("Kick"):
        hpf, lpf = 30.0, 16000.0
    elif name.startswith("Snare"):
        hpf, lpf = 80.0, 18000.0
    elif "Percussion" in name or "Bongo" in name or "Conga" in name:
        hpf, lpf = 100.0, 18000.0
    elif "Bass" in name:
        hpf, lpf = 30.0, 12000.0
    elif name.startswith("Acoustic_Guitar"):
        hpf, lpf = 80.0, 18000.0
    elif name.startswith("Electric_Guitar"):
        hpf, lpf = 80.0, 15000.0
    elif "Keys" in name or "Piano" in name:
        hpf, lpf = 60.0, 18000.0
    elif "Lead_Vocal" in name:
        hpf, lpf = 70.0, 18000.0
    elif "Backing_Vocals" in name or "Choir" in name:
        hpf, lpf = 100.0, 16000.0
    elif "FX" in name or "Ambience" in name or "Atmos" in name:
        hpf, lpf = 120.0, 18000.0
    else:
        # Genérico: casi full-band, solo limpiar sub-bajos extremos
        hpf, lpf = 20.0, 20000.0

    return float(hpf), float(lpf)
