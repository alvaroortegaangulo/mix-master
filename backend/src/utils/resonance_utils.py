# C:\mix-master\backend\src\utils\resonance_utils.py

from __future__ import annotations

from typing import List, Dict, Any

import numpy as np
from scipy.signal import lfilter


def compute_magnitude_spectrum(
    y: np.ndarray,
    sr: int,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Calcula el espectro de magnitud (FFT de todo el clip).

    Devuelve:
      - freqs: frecuencias de cada bin (rfft).
      - mag_lin: magnitud lineal por bin.
    """
    if not isinstance(y, np.ndarray):
        y = np.asarray(y, dtype=np.float32)
    else:
        y = y.astype(np.float32)

    if y.ndim > 1:
        y_mono = np.mean(y, axis=1)
    else:
        y_mono = y

    n = y_mono.shape[0]
    if n == 0:
        return np.array([], dtype=np.float32), np.array([], dtype=np.float32)

    Y = np.fft.rfft(y_mono)
    mag_lin = np.abs(Y)
    freqs = np.fft.rfftfreq(n, d=1.0 / float(sr))
    return freqs, mag_lin


def detect_resonances(
    freqs: np.ndarray,
    mag_lin: np.ndarray,
    fmin: float = 200.0,
    fmax: float = 12000.0,
    threshold_db: float = 12.0,
    local_window_hz: float = 200.0,
    max_resonances: int | None = None,
) -> List[Dict[str, float]]:
    """
    Detecta resonancias como bins cuya magnitud está por encima de la media local
    (en un vecindario en frecuencia) más 'threshold_db'.

    Devuelve lista de dicts:
      { "freq_hz": float, "gain_above_local_db": float }
    """
    if freqs.size == 0 or mag_lin.size == 0:
        return []

    freqs = np.asarray(freqs, dtype=np.float32)
    mag_lin = np.asarray(mag_lin, dtype=np.float32)

    # Acotamos rango de interés
    fmin = max(fmin, float(freqs[0]))
    fmax = min(fmax, float(freqs[-1]))

    idx_lo = int(np.searchsorted(freqs, fmin, side="left"))
    idx_hi = int(np.searchsorted(freqs, fmax, side="right") - 1)

    if idx_hi <= idx_lo:
        return []

    # Resolución en frecuencia
    if freqs.size > 1:
        df = float(freqs[1] - freqs[0])
    else:
        df = 1.0

    window_bins = max(3, int(round(local_window_hz / df)))
    half = window_bins // 2

    candidates: list[tuple[int, float, float]] = []

    for i in range(idx_lo, idx_hi + 1):
        start = max(idx_lo, i - half)
        end = min(idx_hi, i + half)
        if end <= start:
            continue

        region = mag_lin[start : end + 1].copy()
        if region.size < 3:
            continue

        j_self = i - start
        # Excluimos el propio bin del cálculo local
        region[j_self] = 0.0

        if np.all(region <= 0.0):
            continue

        local_lin = float(np.sqrt(np.mean(region**2)))
        peak_lin = float(mag_lin[i])

        if peak_lin <= 0.0 or local_lin <= 0.0:
            continue

        peak_db = 20.0 * np.log10(peak_lin)
        local_db = 20.0 * np.log10(local_lin)
        diff_db = peak_db - local_db

        if diff_db >= threshold_db:
            candidates.append((i, float(freqs[i]), float(diff_db)))

    if not candidates:
        return []

    # Agrupar bins contiguos en "picos"
    candidates.sort(key=lambda x: x[0])
    groups: list[list[tuple[int, float, float]]] = []
    current_group = [candidates[0]]
    for c in candidates[1:]:
        if c[0] == current_group[-1][0] + 1:
            current_group.append(c)
        else:
            groups.append(current_group)
            current_group = [c]
    groups.append(current_group)

    resonances: List[Dict[str, float]] = []
    for group in groups:
        # Nos quedamos con el bin más "resonante" del grupo
        best = max(group, key=lambda x: x[2])  # diff_db
        _, f0, diff = best
        resonances.append(
            {"freq_hz": float(f0), "gain_above_local_db": float(diff)}
        )

    # Ordenar por severidad descendente
    resonances.sort(key=lambda r: r["gain_above_local_db"], reverse=True)

    if max_resonances is not None and len(resonances) > max_resonances:
        resonances = resonances[:max_resonances]

    return resonances


def _apply_resonance_cuts_mono(
    y: np.ndarray,
    sr: int,
    notches: List[Dict[str, float]],
) -> np.ndarray:
    """
    Aplica notches en dominio de frecuencia (FFT) sobre señal mono.

    Cada notch:
      - {"freq_hz": f0, "cut_db": cut_db}

    Sólo hace cortes (attenuación <= 1.0), nunca boosts.
    """
    y = np.asarray(y, dtype=np.float32)
    n = y.shape[0]
    if n == 0 or not notches:
        return y

    Y = np.fft.rfft(y)
    freqs = np.fft.rfftfreq(n, d=1.0 / float(sr))
    atten = np.ones_like(freqs, dtype=np.float32)

    nyq = sr / 2.0

    for notch in notches:
        f0 = float(notch.get("freq_hz", 0.0))
        cut_db = float(notch.get("cut_db", 0.0))

        if cut_db <= 0.0 or f0 <= 0.0 or f0 >= nyq:
            continue

        # Q objetivo aproximado
        Q = 10.0
        bandwidth_hz = max(20.0, f0 / Q)
        sigma_hz = bandwidth_hz / 3.0
        if sigma_hz <= 0.0:
            continue

        g = 10.0 ** (-cut_db / 20.0)  # ganancia en el centro (< 1)

        # Gaussiana en frecuencia
        w = np.exp(-0.5 * ((freqs - f0) / sigma_hz) ** 2)
        # En el pico, factor g; fuera, ~1
        atten *= (1.0 - w * (1.0 - g))

    Y_filt = Y * atten
    y_out = np.fft.irfft(Y_filt, n=n).astype(np.float32)
    return y_out


def _design_peaking_eq_biquad(
    f0: float,
    fs: int,
    gain_db: float,
    q: float = 5.0,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Diseña un biquad de tipo peaking EQ centrado en f0 (Hz),
    con ganancia 'gain_db' (negativa para notch) y factor Q.

    Fórmulas basadas en el Audio EQ Cookbook de RBJ.

    Devuelve (b, a) normalizados para usar con scipy.signal.lfilter.
    """
    # Ganancia lineal
    A = 10.0 ** (gain_db / 40.0)
    omega = 2.0 * np.pi * (f0 / float(fs))
    cos_omega = float(np.cos(omega))
    sin_omega = float(np.sin(omega))

    alpha = sin_omega / (2.0 * q)

    b0 = 1.0 + alpha * A
    b1 = -2.0 * cos_omega
    b2 = 1.0 - alpha * A
    a0 = 1.0 + alpha / A
    a1 = -2.0 * cos_omega
    a2 = 1.0 - alpha / A

    # Normalizar por a0
    b = np.array([b0 / a0, b1 / a0, b2 / a0], dtype=np.float64)
    a = np.array([1.0, a1 / a0, a2 / a0], dtype=np.float64)
    return b, a


def _apply_resonance_cuts_mono(
    y: np.ndarray,
    sr: int,
    notches: List[Dict[str, float]],
    q_default: float = 5.0,
) -> np.ndarray:
    """
    Aplica en serie un conjunto de filtros peaking EQ (notches suaves)
    sobre una señal mono.

    - y: señal mono.
    - sr: sample rate.
    - notches: lista de dicts {"freq_hz": float, "cut_db": float}
               donde cut_db es positiva (cantidad de corte).
    - q_default: Q por defecto para todos los notches (bastante estrecho).

    Devuelve señal filtrada (float32).
    """
    x = np.asarray(y, dtype=np.float32)
    if x.ndim != 1:
        x = x.reshape(-1)

    # Trabajamos internamente en float64 por estabilidad numérica
    out = x.astype(np.float64)

    nyquist = 0.5 * float(sr)

    for notch in notches:
        try:
            f0 = float(notch.get("freq_hz", 0.0))
            cut_db = float(notch.get("cut_db", 0.0))
        except (TypeError, ValueError):
            continue

        if f0 <= 0.0 or f0 >= nyquist:
            continue
        if cut_db <= 0.0:
            continue

        # El contrato habla de "cut_db" positiva => convertimos a ganancia negativa
        gain_db = -abs(cut_db)

        b, a = _design_peaking_eq_biquad(
            f0=f0,
            fs=sr,
            gain_db=gain_db,
            q=q_default,
        )

        out = lfilter(b, a, out)

    return out.astype(np.float32)


def apply_resonance_cuts(
    y: np.ndarray,
    sr: int,
    notches: List[Dict[str, float]],
) -> np.ndarray:
    """
    Versión multicanal:

    - y mono: aplica notches a la señal mono.
    - y (N, C): aplica el mismo conjunto de notches a cada canal.
    """
    arr = np.asarray(y, dtype=np.float32)

    if arr.ndim == 1:
        return _apply_resonance_cuts_mono(arr, sr, notches)

    n, c = arr.shape
    out = np.empty_like(arr)
    for ch in range(c):
        out[:, ch] = _apply_resonance_cuts_mono(arr[:, ch], sr, notches)
    return out
