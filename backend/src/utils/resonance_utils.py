from __future__ import annotations

from typing import List, Dict

import numpy as np
from scipy.signal import lfilter


# ---------------------------------------------------------------------
# Espectro de magnitud optimizado
# ---------------------------------------------------------------------


def compute_magnitude_spectrum(
    y: np.ndarray,
    sr: int,
    max_duration_s: float = 60.0,
    target_max_sr: float = 24000.0,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Calcula el espectro de magnitud (FFT de todo el clip), con optimizaciones:

    - Convierte a mono.
    - Recorta a como máximo `max_duration_s` segundos.
    - Opcionalmente decima la señal si sr > target_max_sr para reducir NFFT.

    Devuelve:
      - freqs: frecuencias de cada bin (rfft).
      - mag_lin: magnitud lineal por bin.
    """
    arr = np.asarray(y, dtype=np.float32)

    # Mono
    if arr.ndim > 1:
        y_mono = np.mean(arr, axis=1)
    else:
        y_mono = arr

    if y_mono.size == 0:
        return np.array([], dtype=np.float32), np.array([], dtype=np.float32)

    # 1) Recorte en tiempo
    if max_duration_s is not None and max_duration_s > 0.0:
        max_samples = int(max_duration_s * sr)
        if y_mono.size > max_samples:
            y_mono = y_mono[:max_samples]

    # 2) Decimación simple para limitar samplerate efectivo
    sr_eff = float(sr)
    if target_max_sr is not None and target_max_sr > 0.0 and sr_eff > target_max_sr:
        # factor mínimo para dejar sr_eff <= target_max_sr
        decim_factor = int(sr_eff // target_max_sr)
        if decim_factor > 1:
            y_mono = y_mono[::decim_factor]
            sr_eff = sr_eff / decim_factor

    n = y_mono.shape[0]
    if n == 0:
        return np.array([], dtype=np.float32), np.array([], dtype=np.float32)

    Y = np.fft.rfft(y_mono)
    mag_lin = np.abs(Y).astype(np.float32)
    freqs = np.fft.rfftfreq(n, d=1.0 / sr_eff).astype(np.float32)

    return freqs, mag_lin


# ---------------------------------------------------------------------
# Detección de resonancias optimizada (vectorizada)
# ---------------------------------------------------------------------


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
    (en dB) más 'threshold_db'.

    Implementación optimizada:
      - Trabaja sobre un slice [fmin, fmax].
      - Calcula una media móvil en dB mediante convolución NumPy (vectorizado).
      - Agrupa bins contiguos en “picos” y se queda con el más severo.

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
    if fmax <= fmin:
        return []

    idx_lo = int(np.searchsorted(freqs, fmin, side="left"))
    idx_hi = int(np.searchsorted(freqs, fmax, side="right") - 1)
    if idx_hi <= idx_lo:
        return []

    freqs_slice = freqs[idx_lo : idx_hi + 1]
    mag_slice = mag_lin[idx_lo : idx_hi + 1]

    if freqs_slice.size < 3:
        return []

    # Magnitud en dB
    eps = 1e-12
    mag_db = (20.0 * np.log10(mag_slice + eps)).astype(np.float32)

    # Resolución en frecuencia y tamaño de ventana local
    if freqs_slice.size > 1:
        df = float(freqs_slice[1] - freqs_slice[0])
    else:
        df = 1.0

    window_bins = max(3, int(round(local_window_hz / df)))
    n_bins = mag_db.size

    if window_bins >= n_bins:
        window_bins = max(3, n_bins // 2)

    if window_bins < 3 or n_bins < 3:
        return []

    # Media móvil en dB (vectorizada)
    kernel = np.ones(window_bins, dtype=np.float32) / float(window_bins)
    local_mean_db = np.convolve(mag_db, kernel, mode="same")

    diff_db = mag_db - local_mean_db

    # Candidatos donde estamos por encima del umbral
    mask = diff_db >= float(threshold_db)
    idx_candidates = np.nonzero(mask)[0]
    if idx_candidates.size == 0:
        return []

    # Agrupar índices contiguos en grupos
    groups: list[list[int]] = []
    current_group = [int(idx_candidates[0])]
    for idx in idx_candidates[1:]:
        idx = int(idx)
        if idx == current_group[-1] + 1:
            current_group.append(idx)
        else:
            groups.append(current_group)
            current_group = [idx]
    groups.append(current_group)

    # Para cada grupo, nos quedamos con el bin con mayor diff_db
    resonances: List[Dict[str, float]] = []
    for g in groups:
        g_arr = np.array(g, dtype=int)
        best_local_pos = int(np.argmax(diff_db[g_arr]))
        best_idx = g_arr[best_local_pos]

        f0 = float(freqs_slice[best_idx])
        diff = float(diff_db[best_idx])

        resonances.append(
            {
                "freq_hz": f0,
                "gain_above_local_db": diff,
            }
        )

    # Ordenar por severidad descendente y limitar nº de resonancias
    resonances.sort(key=lambda r: r["gain_above_local_db"], reverse=True)
    if max_resonances is not None and len(resonances) > max_resonances:
        resonances = resonances[:max_resonances]

    return resonances


# ---------------------------------------------------------------------
# Aplicación de notches (peaking EQ en dominio temporal)
# ---------------------------------------------------------------------


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

    if x.size == 0 or not notches:
        return x

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
