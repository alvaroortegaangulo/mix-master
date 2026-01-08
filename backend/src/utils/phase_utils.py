# C:\mix-master\backend\src\utils\phase_utils.py

from __future__ import annotations

from typing import Dict, Any, Optional, Tuple

import numpy as np

# FFT backend (SciPy si está disponible -> suele ser más rápido y más eficiente en float32)
try:
    from scipy.fft import rfft as _rfft, irfft as _irfft, next_fast_len as _next_fast_len  # type: ignore
except Exception:  # pragma: no cover
    from numpy.fft import rfft as _rfft, irfft as _irfft  # type: ignore

    def _next_fast_len(n: int) -> int:  # fallback simple
        # próximo power-of-two (suficiente y estable)
        if n <= 1:
            return 1
        return 1 << (n - 1).bit_length()


def bandlimit_signal(
    y: np.ndarray,
    sr: int,
    fmin: Optional[float] = None,
    fmax: Optional[float] = None,
) -> np.ndarray:
    """
    Filtro pasa-banda simple en dominio de frecuencia usando FFT real:
      - Si no se dan fmin/fmax, devuelve y tal cual.
      - Si y está vacío, devuelve y.

    Optimización:
      - Evita construir freqs/mask: calcula directamente bins [kmin, kmax].
    """
    if y.size == 0 or (fmin is None and fmax is None):
        return np.asarray(y, dtype=np.float32)

    y = np.asarray(y, dtype=np.float32)
    n = int(y.shape[0])
    if n <= 1 or sr <= 0:
        return y

    # rfft tamaño n => bins 0..(n//2)
    Y = _rfft(y)
    nb = int(Y.shape[0])  # = n//2 + 1

    # Convertir frecuencia a bin: k ≈ f * n / sr
    # Clamp a [0, nb-1]
    if fmin is None:
        kmin = 0
    else:
        kmin = int(np.ceil(float(fmin) * n / float(sr)))
        kmin = max(0, min(nb - 1, kmin))

    if fmax is None:
        kmax = nb - 1
    else:
        kmax = int(np.floor(float(fmax) * n / float(sr)))
        kmax = max(0, min(nb - 1, kmax))

    # Si el rango cubre todo, evita trabajo extra
    if kmin <= 0 and kmax >= nb - 1:
        return y

    Y_filt = np.zeros_like(Y)
    if kmin <= kmax:
        Y_filt[kmin : kmax + 1] = Y[kmin : kmax + 1]

    y_filt = _irfft(Y_filt, n=n)
    return np.asarray(y_filt, dtype=np.float32)


def _xcorr_centered_lags_fft(
    ref: np.ndarray,
    cand: np.ndarray,
    max_shift: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Devuelve (lags, numeradores) para lags en [-max_shift, +max_shift]
    usando cross-correlation por FFT (no circular; cero-padding suficiente).

    Definición de numerador que replica tu implementación:
      num(lag) = sum_{i} ref[i] * cand[i + lag] con solapamiento válido.

    Mapeo de índice tras ifft:
      - lag >= 0 -> idx = lag
      - lag < 0  -> idx = L + lag
    """
    ref = np.asarray(ref, dtype=np.float32)
    cand = np.asarray(cand, dtype=np.float32)

    n = int(min(ref.shape[0], cand.shape[0]))
    if n <= 0:
        return np.array([0], dtype=np.int32), np.array([0.0], dtype=np.float64)

    ref = ref[:n]
    cand = cand[:n]

    # Longitud para correlación lineal
    L = int(_next_fast_len(2 * n - 1))
    # FFT real
    R = _rfft(ref, n=L)
    C = _rfft(cand, n=L)
    # Cross-correlation circular en longitud L; con zero-pad se comporta lineal en rango útil
    cc = _irfft(R * np.conj(C), n=L)  # real

    lags = np.arange(-max_shift, max_shift + 1, dtype=np.int32)
    idx = np.where(lags >= 0, lags, L + lags).astype(np.int64)
    nums = np.asarray(cc[idx], dtype=np.float64)
    return lags, nums


def _segment_energy_prefix(x: np.ndarray) -> np.ndarray:
    """
    Prefijo de energía: E[k] = sum_{i<=k} x[i]^2   (float64 para estabilidad).
    """
    x = np.asarray(x, dtype=np.float32)
    if x.size == 0:
        return np.zeros((0,), dtype=np.float64)
    return np.cumsum(x.astype(np.float64) * x.astype(np.float64), dtype=np.float64)


def _energy_range(prefix: np.ndarray, start: np.ndarray, length: np.ndarray) -> np.ndarray:
    """
    Energía por rangos para múltiples segmentos:
      sum_{i=start}^{start+length-1} x[i]^2

    start, length: arrays int64
    """
    # end = start+length-1
    end = start + length - 1
    # prefix[end] - prefix[start-1] (si start>0)
    base = prefix[end]
    sub = np.where(start > 0, prefix[start - 1], 0.0)
    return base - sub


def estimate_best_lag_and_corr(
    ref: np.ndarray,
    cand: np.ndarray,
    sr: int,
    max_time_shift_ms: float,
    fmin: Optional[float] = None,
    fmax: Optional[float] = None,
) -> Dict[str, float]:
    """
    Estima el mejor desplazamiento temporal (lag, en samples) maximizando correlación normalizada.

    Nota importante (coherente con tu pipeline actual):
      - Esta función devuelve el *lag medido* (cand vs ref) que maximiza corr en el sentido:
            num(lag) = sum ref[i] * cand[i + lag]
        Por tanto:
          lag > 0  suele indicar que CANDIDATE está retrasado respecto a REF (para corregir: shift = -lag).
          lag < 0  suele indicar que CANDIDATE está adelantado (para corregir: shift = -lag).

    Devuelve:
      {"lag_samples": float, "lag_ms": float, "correlation": float}
    """
    ref = np.asarray(ref, dtype=np.float32)
    cand = np.asarray(cand, dtype=np.float32)

    if ref.size == 0 or cand.size == 0 or sr <= 0:
        return {"lag_samples": 0.0, "lag_ms": 0.0, "correlation": 0.0}

    # Bandlimit (si aplica)
    if fmin is not None or fmax is not None:
        ref = bandlimit_signal(ref, sr, fmin=fmin, fmax=fmax)
        cand = bandlimit_signal(cand, sr, fmin=fmin, fmax=fmax)

    n = int(min(ref.shape[0], cand.shape[0]))
    if n <= 1:
        return {"lag_samples": 0.0, "lag_ms": 0.0, "correlation": 0.0}

    ref = ref[:n]
    cand = cand[:n]

    max_shift = int(round(float(max_time_shift_ms) * 1e-3 * float(sr)))
    if max_shift >= n:
        max_shift = n - 1
    if max_shift < 0:
        max_shift = 0

    # Caso trivial
    if max_shift == 0:
        num = float(np.dot(ref, cand))
        den = float(np.linalg.norm(ref) * np.linalg.norm(cand))
        corr = (num / den) if den > 0.0 else 0.0
        return {"lag_samples": 0.0, "lag_ms": 0.0, "correlation": float(corr)}

    # ----------------------------
    # Numeradores para lags [-M..M] con FFT
    # ----------------------------
    lags, nums = _xcorr_centered_lags_fft(ref, cand, max_shift=max_shift)

    # ----------------------------
    # Denominadores por energía de solape (prefijos), vectorizado
    # Replica exactamente las longitudes de solape de tu bucle original.
    # ----------------------------
    pref_r = _segment_energy_prefix(ref)
    pref_c = _segment_energy_prefix(cand)

    l = lags.astype(np.int64)

    pos = l >= 0
    neg = ~pos

    # Para lag >= 0:
    #   len = n - lag
    #   ref: start=0
    #   cand: start=lag
    len_pos = (n - l[pos]).astype(np.int64)
    # evitar longitudes no válidas (aunque con clamp de max_shift no debería)
    len_pos = np.maximum(len_pos, 0)

    ref_e_pos = np.where(len_pos > 0, pref_r[len_pos - 1], 0.0)
    cand_start_pos = l[pos]
    cand_e_pos = np.where(
        len_pos > 0,
        _energy_range(pref_c, cand_start_pos, len_pos),
        0.0,
    )

    # Para lag < 0:
    #   k = -lag
    #   len = n - k
    #   ref: start=k
    #   cand: start=0
    k = (-l[neg]).astype(np.int64)
    len_neg = (n - k).astype(np.int64)
    len_neg = np.maximum(len_neg, 0)

    cand_e_neg = np.where(len_neg > 0, pref_c[len_neg - 1], 0.0)
    ref_start_neg = k
    ref_e_neg = np.where(
        len_neg > 0,
        _energy_range(pref_r, ref_start_neg, len_neg),
        0.0,
    )

    # Combinar energías en el orden original de lags
    ref_e = np.zeros_like(nums, dtype=np.float64)
    cand_e = np.zeros_like(nums, dtype=np.float64)
    ref_e[pos] = ref_e_pos
    cand_e[pos] = cand_e_pos
    ref_e[neg] = ref_e_neg
    cand_e[neg] = cand_e_neg

    den = np.sqrt(ref_e * cand_e)
    # correlación normalizada
    corr = np.zeros_like(nums, dtype=np.float64)
    valid = den > 0.0
    corr[valid] = nums[valid] / den[valid]

    # Buscar mejor
    best_idx = int(np.argmax(corr))
    best_lag = int(lags[best_idx])
    best_corr = float(corr[best_idx])

    lag_ms = float(best_lag) * 1000.0 / float(sr)
    return {
        "lag_samples": float(best_lag),
        "lag_ms": float(lag_ms),
        "correlation": float(best_corr),
    }


def apply_time_shift_samples(y: np.ndarray, lag_samples: int) -> np.ndarray:
    """
    Aplica un shift temporal a y:

      new_y[n] = y[n - lag_samples], con padding de ceros.

      - lag_samples > 0 => new_y empieza más tarde (se desplaza hacia adelante).
      - lag_samples < 0 => new_y empieza antes (contenido adelantado).

    Mantiene la longitud original de y.
    Funciona con (N,) y (N,C).
    """
    y = np.asarray(y, dtype=np.float32)
    n = int(y.shape[0])
    if n == 0 or lag_samples == 0:
        return y

    out = np.zeros_like(y, dtype=np.float32)

    if lag_samples > 0:
        if lag_samples >= n:
            return out
        out[lag_samples:] = y[: n - lag_samples]
    else:
        lag = -lag_samples
        if lag >= n:
            return out
        out[: n - lag] = y[lag:]

    return out
