# C:\mix-master\backend\src\utils\loudness_utils.py

from __future__ import annotations

from typing import Union, Tuple

import numpy as np
import librosa

ArrayLike = Union[np.ndarray, list]


def _to_mono_float32(y: ArrayLike) -> np.ndarray:
    """
    Convierte cualquier array (mono o estéreo/multicanal) a mono float32.

    - Si es 2D: media de canales.
    - Si es 1D: se devuelve tal cual en float32.
    """
    arr = np.asarray(y, dtype=np.float32)
    if arr.ndim > 1:
        arr = np.mean(arr, axis=1)
    return arr


def measure_integrated_lufs(y: ArrayLike, sr: int) -> float:
    """
    Medición aproximada de loudness integrado en LUFS.

    No implementa EBU R128 completa, pero sirve muy bien como métrica relativa:
      LUFS ≈ -0.691 + 20 * log10(RMS)

    - y: señal mono o estéreo/multicanal (float o int).
    - sr: samplerate.

    Devuelve:
      - float('-inf') si la señal es silencio.
    """
    y_mono = _to_mono_float32(y)

    if y_mono.size == 0:
        return float("-inf")

    # RMS
    rms = float(np.sqrt(np.mean(y_mono**2)))
    if rms <= 0.0:
        return float("-inf")

    # Aproximación tipo K-weighting (sin filtro explícito)
    lufs = -0.691 + 20.0 * np.log10(rms + 1e-12)
    return float(lufs)


def measure_true_peak_dbfs(y: ArrayLike, sr: int, oversample: int = 4) -> float:
    """
    Medición aproximada de true peak en dBFS mediante oversampling.

    - Convierte a mono.
    - Oversampling (x4 por defecto) con librosa.resample.
    - Busca el pico máximo absoluto y lo pasa a dBFS.

    Devuelve:
      - float('-inf') si la señal es silencio.
    """
    y_mono = _to_mono_float32(y)

    if y_mono.size == 0:
        return float("-inf")

    if oversample > 1:
        target_sr = int(sr * oversample)
        y_os = librosa.resample(y_mono, orig_sr=sr, target_sr=target_sr)
    else:
        y_os = y_mono

    peak = float(np.max(np.abs(y_os))) if y_os.size > 0 else 0.0
    if peak <= 0.0:
        return float("-inf")

    peak_dbfs = 20.0 * np.log10(peak)
    return float(peak_dbfs)


def _to_mono(x: np.ndarray) -> np.ndarray:
    """Convierte audio 1D/2D a mono (media de canales)."""
    arr = np.asarray(x, dtype=np.float32)
    if arr.ndim == 1:
        return arr
    return np.mean(arr, axis=1)


def compute_lufs_and_lra(
    x: np.ndarray,
    sr: int,
    frame_len_s: float = 0.4,
    hop_s: float = 0.2,
) -> Tuple[float, float]:
    """
    Aproximación simple a LUFS integrados y LRA.

    - LUFS_integrated ≈ media de niveles por frame (en dB).
    - LRA ≈ percentil_95 - percentil_10 de los niveles por frame.

    No es EBU R128 exacto, pero es suficiente para controlar dinámicas de forma
    consistente en el pipeline.
    """
    mono = _to_mono(x)
    n = mono.size
    if n == 0 or sr <= 0:
        return float("-inf"), 0.0

    frame_len = int(frame_len_s * sr)
    hop_len = int(hop_s * sr)
    if frame_len <= 0 or hop_len <= 0:
        return float("-inf"), 0.0

    levels_db = []

    for start in range(0, n, hop_len):
        end = start + frame_len
        if end > n:
            frame = mono[start:n]
        else:
            frame = mono[start:end]

        if frame.size == 0:
            continue

        rms = float(np.sqrt(np.mean(frame**2)))
        if rms <= 0.0:
            level_db = float("-inf")
        else:
            level_db = 20.0 * np.log10(rms)
        levels_db.append(level_db)

    if not levels_db:
        return float("-inf"), 0.0

    levels = np.asarray(levels_db, dtype=np.float32)

    # Excluir frames de silencio extremo de la media
    valid = levels[np.isfinite(levels)]
    if valid.size == 0:
        return float("-inf"), 0.0

    lufs_integrated = float(np.mean(valid))

    # LRA como diferencia entre percentil 95 y 10
    p10 = float(np.percentile(valid, 10.0))
    p95 = float(np.percentile(valid, 95.0))
    lra = max(0.0, p95 - p10)

    return lufs_integrated, lra