# C:\mix-master\backend\src\utils\phase_utils.py

from __future__ import annotations

from typing import Dict, Any, Optional

import numpy as np


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

    Se usa para aislar 100–500 Hz en análisis de fase.
    """
    if y.size == 0 or (fmin is None and fmax is None):
        return y

    y = np.asarray(y, dtype=np.float32)
    n = y.shape[0]

    Y = np.fft.rfft(y)
    freqs = np.fft.rfftfreq(n, d=1.0 / float(sr))

    mask = np.ones_like(freqs, dtype=bool)
    if fmin is not None:
        mask &= freqs >= float(fmin)
    if fmax is not None:
        mask &= freqs <= float(fmax)

    Y_filt = np.zeros_like(Y)
    Y_filt[mask] = Y[mask]

    y_filt = np.fft.irfft(Y_filt, n=n)
    return y_filt.astype(np.float32)


def estimate_best_lag_and_corr(
    ref: np.ndarray,
    cand: np.ndarray,
    sr: int,
    max_time_shift_ms: float,
    fmin: Optional[float] = None,
    fmax: Optional[float] = None,
) -> Dict[str, float]:
    """
    Estima el mejor desplazamiento temporal (lag, en samples) para alinear cand con ref
    maximizando la correlación normalizada.

    Convención:
      - 'lag_samples' es el shift a aplicar a CANDIDATE:
          new_cand[n] = cand[n - lag_samples], con padding de ceros.
      - lag > 0  => cand se desplaza hacia ADELANTE (empieza más tarde).
      - lag < 0  => cand se desplaza hacia ATRÁS (empieza antes).

    Se puede band-limitar a [fmin, fmax] (por ejemplo 100–500 Hz).

    Devuelve:
      {
        "lag_samples": int,
        "lag_ms": float,
        "correlation": float  # en [-1, 1]
      }
    """
    ref = np.asarray(ref, dtype=np.float32)
    cand = np.asarray(cand, dtype=np.float32)

    if ref.size == 0 or cand.size == 0:
        return {"lag_samples": 0, "lag_ms": 0.0, "correlation": 0.0}

    if fmin is not None or fmax is not None:
        ref = bandlimit_signal(ref, sr, fmin=fmin, fmax=fmax)
        cand = bandlimit_signal(cand, sr, fmin=fmin, fmax=fmax)

    n_ref = ref.shape[0]
    n_cand = cand.shape[0]
    n = min(n_ref, n_cand)

    if n <= 1:
        return {"lag_samples": 0, "lag_ms": 0.0, "correlation": 0.0}

    max_shift = int(round(max_time_shift_ms * 1e-3 * sr))
    if max_shift >= n:
        max_shift = n - 1
    if max_shift <= 0:
        max_shift = 0

    best_lag = 0
    best_corr = -1.0  # queremos maximizar (>= -1)

    # Para todos los shifts posibles
    for lag in range(-max_shift, max_shift + 1):
        if lag > 0:
            # cand desplazado hacia adelante: new_cand[lag:] = cand[:-lag]
            len_seg = n - lag
            if len_seg <= 0:
                continue
            ref_seg = ref[:len_seg]
            cand_seg = cand[lag:lag + len_seg]
        elif lag < 0:
            # cand desplazado hacia atrás: new_cand[:-lag] = cand[-lag:]
            len_seg = n + lag  # lag es negativo
            if len_seg <= 0:
                continue
            ref_seg = ref[-lag:-lag + len_seg]
            cand_seg = cand[:len_seg]
        else:
            # lag == 0
            len_seg = n
            ref_seg = ref[:len_seg]
            cand_seg = cand[:len_seg]

        num = float(np.dot(ref_seg, cand_seg))
        den = float(np.linalg.norm(ref_seg) * np.linalg.norm(cand_seg))
        if den <= 0.0:
            corr = 0.0
        else:
            corr = num / den

        if corr > best_corr:
            best_corr = corr
            best_lag = lag

    lag_ms = best_lag * 1000.0 / float(sr)
    return {
        "lag_samples": float(best_lag),
        "lag_ms": float(lag_ms),
        "correlation": float(best_corr),
    }


def apply_time_shift_samples(y: np.ndarray, lag_samples: int) -> np.ndarray:
    """
    Aplica un shift temporal a y usando la misma convención que estimate_best_lag_and_corr:

      new_y[n] = y[n - lag_samples], con padding de ceros.

      - lag_samples > 0 => new_y empieza más tarde (se desplaza hacia adelante).
      - lag_samples < 0 => new_y empieza antes (contenido adelantado).

    Mantiene la longitud original de y.
    """
    y = np.asarray(y, dtype=np.float32)
    n = y.shape[0]
    if n == 0 or lag_samples == 0:
        return y

    out = np.zeros_like(y)

    if lag_samples > 0:
        # desplazar hacia adelante
        if lag_samples >= n:
            return out
        out[lag_samples:] = y[: n - lag_samples]
    else:
        # lag_samples < 0 => desplazar hacia atrás
        lag = -lag_samples
        if lag >= n:
            return out
        out[: n - lag] = y[lag:]

    return out
