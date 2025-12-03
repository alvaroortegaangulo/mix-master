# C:\mix-master\backend\src\utils\filter_utils.py

from __future__ import annotations
from stages.pipeline_context import PipelineContext

from typing import Optional

import numpy as np


def _apply_hpf_lpf_mono(
    y: np.ndarray,
    sr: int,
    hpf_hz: Optional[float],
    lpf_hz: Optional[float],
) -> np.ndarray:
    """
    Aplica un HPF/LPF muy simple en dominio de frecuencia (brickwall).

    - y: señal MONO float32.
    - sr: samplerate.
    - hpf_hz: frecuencia de corte HPF (None => no HPF).
    - lpf_hz: frecuencia de corte LPF (None => no LPF).

    Es lineal en fase e idempotente (aplicar dos veces no cambia más la magnitud),
    ideal para este contrato minimalista.
    """
    y = np.asarray(y, dtype=np.float32)
    n = y.shape[0]
    if n == 0:
        return y

    nyq = sr / 2.0

    hpf = float(hpf_hz) if hpf_hz is not None else None
    lpf = float(lpf_hz) if lpf_hz is not None else None

    # Clamp básico
    if hpf is not None:
        if hpf < 0.0:
            hpf = 0.0
        if hpf > nyq:
            hpf = nyq
    if lpf is not None:
        if lpf < 0.0:
            lpf = 0.0
        if lpf > nyq:
            lpf = nyq

    # Caso degenerado: HPF >= LPF => dejamos silencio
    if hpf is not None and lpf is not None and hpf >= lpf:
        return np.zeros_like(y)

    Y = np.fft.rfft(y)
    freqs = np.fft.rfftfreq(n, d=1.0 / float(sr))

    mask = np.ones_like(freqs, dtype=bool)
    if hpf is not None:
        mask &= freqs >= hpf
    if lpf is not None:
        mask &= freqs <= lpf

    Y_filt = np.zeros_like(Y)
    Y_filt[mask] = Y[mask]

    y_filt = np.fft.irfft(Y_filt, n=n)
    return y_filt.astype(np.float32)


def apply_hpf_lpf(
    y: np.ndarray,
    sr: int,
    hpf_hz: Optional[float],
    lpf_hz: Optional[float],
) -> np.ndarray:
    """
    Versión multicanal:

    - Si y es 1D: aplica _apply_hpf_lpf_mono directamente.
    - Si y es 2D (N, C): filtra cada canal por separado.
    """
    arr = np.asarray(y, dtype=np.float32)
    if arr.ndim == 1:
        return _apply_hpf_lpf_mono(arr, sr, hpf_hz, lpf_hz)

    # (N, C)
    n, c = arr.shape
    out = np.zeros_like(arr)
    for ch in range(c):
        out[:, ch] = _apply_hpf_lpf_mono(arr[:, ch], sr, hpf_hz, lpf_hz)
    return out
