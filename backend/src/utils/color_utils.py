# C:\mix-master\backend\src\utils\color_utils.py

from __future__ import annotations

from typing import Tuple
import numpy as np

from utils.loudness_utils import measure_true_peak_dbtp, measure_sample_peak_dbfs


def _to_mono(x: np.ndarray) -> np.ndarray:
    """Convierte audio 1D/2D a mono (media de canales)."""
    arr = np.asarray(x, dtype=np.float32)
    if arr.ndim == 1:
        return arr
    return np.mean(arr, axis=1)


def compute_rms_dbfs(x: np.ndarray) -> float:
    """RMS global en dBFS aproximado."""
    mono = _to_mono(x)
    if mono.size == 0:
        return float("-inf")
    rms = float(np.sqrt(np.mean(mono**2)))
    if rms <= 0.0:
        return float("-inf")
    return 20.0 * np.log10(rms)


def compute_true_peak_dbtp(x: np.ndarray, oversample_factor: int = 4) -> float:
    """
    True Peak (dBTP) usando oversampling >=4× (coherente con el resto del pipeline).
    """
    return measure_true_peak_dbtp(x, sr=None, oversample=oversample_factor)


def compute_true_peak_dbfs(x: np.ndarray, oversample_factor: int = 4) -> float:
    """
    Alias histórico: devuelve dBTP aunque el nombre diga dBFS.
    """
    return compute_true_peak_dbtp(x, oversample_factor=oversample_factor)


def compute_sample_peak_dbfs(x: np.ndarray) -> float:
    """Sample-peak en dBFS (sin oversampling)."""
    return measure_sample_peak_dbfs(x)


def apply_soft_saturation(
    x: np.ndarray,
    drive_db: float,
    curve_strength: float = 1.5,
) -> np.ndarray:
    """
    Saturación suave tipo 'tanh' con pre-gain en dB.

    - drive_db: ganancia previa (dB) que empuja a la saturación.
    - curve_strength: controla la dureza de la curva (1–3 aprox).

    Devuelve audio procesado con misma forma que x.
    """
    if drive_db <= 0.0:
        return np.asarray(x, dtype=np.float32)

    arr = np.asarray(x, dtype=np.float32)
    drive_lin = 10.0 ** (drive_db / 20.0)

    x_drive = arr * drive_lin
    k = float(max(curve_strength, 0.1))

    # Saturación tanh normalizada a [-1, 1]
    y = np.tanh(k * x_drive) / np.tanh(k)

    # Clamp suave para evitar valores extremos
    y = np.clip(y, -1.0, 1.0)
    return y.astype(np.float32)


def estimate_thd_percent(
    clean: np.ndarray,
    processed: np.ndarray,
) -> float:
    """
    Estimación simple de THD (%):

      THD ≈ 100 * RMS(processed - clean) / RMS(clean)

    Es una medida pragmática de cuánto hemos "ensuciado" el mix.
    """
    c = _to_mono(clean)
    p = _to_mono(processed)

    n = min(c.size, p.size)
    if n == 0:
        return 0.0

    c = c[:n]
    p = p[:n]
    diff = p - c

    rms_clean = float(np.sqrt(np.mean(c**2)))
    rms_diff = float(np.sqrt(np.mean(diff**2)))

    if rms_clean <= 1e-8:
        return 0.0

    thd = 100.0 * (rms_diff / rms_clean)
    return float(thd)
