# C:\mix-master\backend\src\utils\tonal_balance_utils.py

from __future__ import annotations

from typing import Dict, Any, List, Tuple
import numpy as np

# Definición de bandas de frecuencia para el tonal balance (ejemplo 8 bandas)
_FREQ_BANDS: List[Dict[str, Any]] = [
    {"id": "sub",        "f_min": 20.0,    "f_max": 40.0},
    {"id": "bass",       "f_min": 40.0,    "f_max": 120.0},
    {"id": "low_mid",    "f_min": 120.0,   "f_max": 400.0},
    {"id": "mid",        "f_min": 400.0,   "f_max": 1000.0},
    {"id": "high_mid",   "f_min": 1000.0,  "f_max": 3000.0},
    {"id": "presence",   "f_min": 3000.0,  "f_max": 6000.0},
    {"id": "air",        "f_min": 6000.0,  "f_max": 12000.0},
    {"id": "ultra_air",  "f_min": 12000.0, "f_max": 20000.0},
]


def get_freq_bands() -> List[Dict[str, Any]]:
    """Devuelve una copia de la definición de bandas."""
    return [dict(b) for b in _FREQ_BANDS]


def _to_mono(x: np.ndarray) -> np.ndarray:
    """Convierte array 1D/2D a mono (media de canales)."""
    arr = np.asarray(x, dtype=np.float32)
    if arr.ndim == 1:
        return arr
    return np.mean(arr, axis=1)


def compute_band_energies(y: np.ndarray, sr: int) -> Dict[str, float]:
    """
    Calcula energía media en dB por banda de frecuencia a partir de la FFT
    de un mix mono.

    Devuelve dict band_id -> energy_db (dBFS aprox).
    """
    mono = _to_mono(y)
    n = mono.size
    if n == 0 or sr <= 0:
        return {b["id"]: float("-inf") for b in _FREQ_BANDS}

    # FFT real
    spec = np.fft.rfft(mono)
    freqs = np.fft.rfftfreq(n, 1.0 / float(sr))
    power = (np.abs(spec) ** 2).astype(np.float64)

    band_energies: Dict[str, float] = {}

    for b in _FREQ_BANDS:
        band_id = b["id"]
        f_min = b["f_min"]
        f_max = b["f_max"]

        if f_min >= sr / 2.0:
            band_energies[band_id] = float("-inf")
            continue

        idx = (freqs >= f_min) & (freqs < min(f_max, sr / 2.0))
        if not np.any(idx):
            band_energies[band_id] = float("-inf")
            continue

        # Usamos suma de energía en la banda (no media) para compensar
        # el ancho de banda variable (logarítmico). Así, ruido rosa
        # (energía constante por octava) se verá plano.
        band_power = float(np.sum(power[idx]))
        if band_power <= 0.0:
            band_db = float("-inf")
        else:
            band_db = 10.0 * np.log10(band_power)

        band_energies[band_id] = band_db

    return band_energies


def get_style_tonal_profile(style_preset: str | None) -> Dict[str, float]:
    """
    Devuelve una curva objetivo por estilo: dict band_id -> target_db (relativos).
    No son absolutos, sino offsets relativos entre bandas.

    Se puede afinar más adelante con datos reales; por ahora definimos
    curvas razonables por estilo.
    """
    style = (style_preset or "default").lower()

    # Curva base "semi-flat" con ligera caída hacia agudos (tipo pink-ish)
    base_profile = {
        "sub":       -4.0,
        "bass":      -2.0,
        "low_mid":    0.0,
        "mid":        0.0,
        "high_mid":  -1.0,
        "presence":  -2.0,
        "air":       -3.0,
        "ultra_air": -4.0,
    }

    profile = dict(base_profile)

    # Flamenco / Rumba: menos sub, más medios/presencia
    if "flamenco" in style or "rumba" in style:
        profile.update(
            {
                "sub":       -6.0,
                "bass":      -3.0,
                "low_mid":   +1.0,
                "mid":       +1.0,
                "high_mid":   0.0,
                "presence":   0.0,
                "air":       -2.0,
                "ultra_air": -4.0,
            }
        )

    # Urbano / Trap: más sub/bass y algo de top
    elif "urbano" in style or "trap" in style:
        profile.update(
            {
                "sub":       0.0,
                "bass":      +1.0,
                "low_mid":   -1.0,
                "mid":       -1.0,
                "high_mid":   0.0,
                "presence":  +1.0,
                "air":       +1.0,
                "ultra_air":  0.0,
            }
        )

    # EDM / Club: graves y agudos más presentes, low-mid algo recortados
    elif "edm" in style or "club" in style:
        profile.update(
            {
                "sub":       +1.0,
                "bass":      +1.0,
                "low_mid":   -2.0,
                "mid":       -1.0,
                "high_mid":   0.0,
                "presence":  +1.0,
                "air":       +2.0,
                "ultra_air": +2.0,
            }
        )

    # Acústico / Jazz: más natural/medio, graves controlados, agudos suaves
    elif "acoustic" in style or "jazz" in style or "acústico" in style:
        profile.update(
            {
                "sub":       -6.0,
                "bass":      -2.0,
                "low_mid":   +1.0,
                "mid":       +1.0,
                "high_mid":   0.0,
                "presence":  -1.0,
                "air":       -2.0,
                "ultra_air": -3.0,
            }
        )

    # Otros estilos usan base_profile

    return profile


def compute_tonal_error(
    current_band_db: Dict[str, float],
    target_band_db: Dict[str, float],
) -> Tuple[Dict[str, float], float]:
    """
    Calcula error por banda (current - target) y error RMS (dB).
    Ignora bandas sin valor (inf/None).
    """
    errors: Dict[str, float] = {}
    diffs: List[float] = []

    # Calculate offset to align the average level of current bands to target bands
    valid_cur = []
    valid_tgt = []
    for band_id, cur_val in current_band_db.items():
        tgt_val = target_band_db.get(band_id)
        if tgt_val is not None and cur_val != float("-inf"):
            valid_cur.append(cur_val)
            valid_tgt.append(tgt_val)

    offset = 0.0
    if valid_cur and valid_tgt:
        offset = float(np.mean(valid_tgt)) - float(np.mean(valid_cur))

    for band_id, cur_val in current_band_db.items():
        tgt_val = target_band_db.get(band_id)
        if tgt_val is None:
            continue
        if cur_val == float("-inf"):
            continue

        # Error relative to shape, normalized by offset
        err = (float(cur_val) + offset) - float(tgt_val)
        errors[band_id] = err
        diffs.append(err)

    if not diffs:
        return errors, 0.0

    diffs_arr = np.asarray(diffs, dtype=np.float32)
    rms = float(np.sqrt(np.mean(diffs_arr**2)))
    return errors, rms
