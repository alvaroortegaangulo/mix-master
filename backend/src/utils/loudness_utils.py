# C:\mix-master\backend\src\utils\loudness_utils.py

from __future__ import annotations

from typing import Union, Tuple, Optional

import numpy as np
import scipy.signal

ArrayLike = Union[np.ndarray, list]


def _to_mono_float32(y: ArrayLike) -> np.ndarray:
    """
    Convierte cualquier array (mono o estéreo/multicanal) a mono float32.
    """
    arr = np.asarray(y, dtype=np.float32)
    if arr.ndim > 1:
        arr = np.mean(arr, axis=1)
    return arr


def _normalize_channels(y: ArrayLike) -> np.ndarray:
    """
    Devuelve array float32 en forma (n_samples, n_channels>=1).
    """
    arr = np.asarray(y, dtype=np.float32)
    if arr.ndim == 1:
        return arr.reshape(-1, 1)
    if arr.ndim == 2:
        return arr
    return arr.reshape(arr.shape[0], -1)


def _bs1770_loudness(audio: np.ndarray, sr: int) -> Tuple[Optional[float], Optional[float]]:
    """
    Loudness integrado y LRA según ITU-R BS.1770 con gating EBU R128.

    Usa Essentia (LoudnessEBUR128) si está disponible; si no, pyloudnorm.
    Si ninguna dependencia está presente, devuelve (None, None).
    """
    if audio.size == 0 or sr <= 0:
        return None, None

    # Essentia prefiere estéreo explícito
    try:
        import essentia.standard as es

        if audio.ndim == 1:
            audio_for_es = np.column_stack((audio, np.zeros_like(audio)))
        elif audio.shape[1] == 1:
            audio_for_es = np.column_stack((audio[:, 0], np.zeros_like(audio[:, 0])))
        else:
            audio_for_es = audio[:, :2]

        audio_for_es = np.ascontiguousarray(audio_for_es, dtype=np.float32)
        loudness_algo = es.LoudnessEBUR128(sampleRate=sr)
        _, _, integrated, lra = loudness_algo(audio_for_es)
        return float(integrated), float(lra)
    except Exception:
        pass

    try:
        import pyloudnorm as pyln

        meter = pyln.Meter(sr, block_size=0.400, filter_class="K-weighting")
        integrated = meter.integrated_loudness(audio)
        lra = meter.loudness_range(audio)
        return float(integrated), float(lra)
    except Exception:
        pass

    return None, None


def _oversample_channel(x: np.ndarray, factor: int) -> np.ndarray:
    """
    Oversampling seguro para una sola señal (1D).
    Usa resample_poly y hace fallback a interpolación lineal.
    """
    if factor <= 1 or x.size == 0:
        return x.astype(np.float32, copy=False)

    try:
        return scipy.signal.resample_poly(x, up=factor, down=1).astype(np.float32, copy=False)
    except Exception:
        t_in = np.arange(x.size, dtype=np.float32)
        t_out = np.linspace(0.0, float(x.size - 1), int(x.size * factor), dtype=np.float32)
        return np.interp(t_out, t_in, x).astype(np.float32, copy=False)


def measure_sample_peak_dbfs(y: ArrayLike) -> float:
    """
    Sample-peak en dBFS (sin oversampling).
    """
    arr = _normalize_channels(y)
    if arr.size == 0:
        return float("-inf")

    peak = float(np.max(np.abs(arr)))
    if peak <= 0.0:
        return float("-inf")
    return float(20.0 * np.log10(peak))


def measure_true_peak_dbtp(y: ArrayLike, sr: int | None = None, oversample: int = 4) -> float:
    """
    True Peak (dBTP) con oversampling >=4×.

    - Máximo entre todos los canales.
    - Oversampling por factor entero (resample_poly); fallback a interpolación lineal.
    - oversample se fuerza a 4 como mínimo.
    """
    arr = _normalize_channels(y)
    if arr.size == 0:
        return float("-inf")

    factor = max(int(oversample), 4)
    peak_lin = 0.0

    for ch in range(arr.shape[1]):
        ch_data = arr[:, ch]
        up = _oversample_channel(ch_data, factor)
        pk = float(np.max(np.abs(up))) if up.size else 0.0
        if pk > peak_lin:
            peak_lin = pk

    if peak_lin <= 0.0:
        return float("-inf")
    return float(20.0 * np.log10(peak_lin))


def measure_true_peak_dbfs(y: ArrayLike, sr: int | None = None, oversample: int = 4) -> float:
    """
    Alias de measure_true_peak_dbtp por compatibilidad previa.
    Mantiene el nombre histórico pero devuelve dBTP.
    """
    return measure_true_peak_dbtp(y, sr=sr, oversample=oversample)


def measure_integrated_lufs(y: ArrayLike, sr: int) -> float:
    """
    Loudness integrado en LUFS según ITU-R BS.1770 (K-weighting + gating EBU R128).
    Devuelve -inf si la señal es silencio.
    """
    audio = _normalize_channels(y)
    if audio.size == 0:
        return float("-inf")

    integrated, _ = _bs1770_loudness(audio, sr)
    if integrated is not None:
        return integrated

    # Fallback aproximado (sin gating completo) para entornos sin dependencias.
    mono = np.mean(audio, axis=1)
    rms = float(np.sqrt(np.mean(mono**2)))
    if rms <= 0.0:
        return float("-inf")
    return float(20.0 * np.log10(rms) - 0.691)


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
    LUFS integrado + LRA según ITU-R BS.1770 (K-weighting) y gating EBU R128.
    Si las dependencias no están disponibles, cae a un cálculo RMS aproximado.
    """
    audio = _normalize_channels(x)
    if audio.size == 0 or sr <= 0:
        return float("-inf"), 0.0

    integrated, lra = _bs1770_loudness(audio, sr)
    if integrated is not None and lra is not None:
        return float(integrated), float(lra)

    # Fallback aproximado (sin gating completo)
    mono = _to_mono(audio)
    n = mono.size
    if n == 0:
        return float("-inf"), 0.0

    frame_len = int(frame_len_s * sr)
    hop_len = int(hop_s * sr)
    if frame_len <= 0 or hop_len <= 0:
        return float("-inf"), 0.0

    levels_db = []
    for start in range(0, n, hop_len):
        end = start + frame_len
        frame = mono[start:end]
        if frame.size == 0:
            continue

        rms = float(np.sqrt(np.mean(frame**2)))
        level_db = float("-inf") if rms <= 0.0 else 20.0 * np.log10(rms)
        if np.isfinite(level_db):
            levels_db.append(level_db)

    if not levels_db:
        return float("-inf"), 0.0

    levels = np.asarray(levels_db, dtype=np.float32)
    lufs_integrated = float(np.mean(levels))

    p10 = float(np.percentile(levels, 10.0))
    p95 = float(np.percentile(levels, 95.0))
    lra = max(0.0, p95 - p10)

    return lufs_integrated, lra
