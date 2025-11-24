from __future__ import annotations

from typing import Union

import numpy as np

NumberOrArray = Union[float, np.ndarray]

DBFS_FLOOR = -120.0
EPS = 1e-12


def safe_dbfs(value: NumberOrArray, floor: float = DBFS_FLOOR) -> NumberOrArray:
    """
    Convierte magnitud lineal a dBFS evitando log(0).

    - Si `value` es escalar, devuelve un float.
    - Si `value` es array, devuelve un np.ndarray con la misma forma.
    """
    arr = np.asarray(value, dtype=np.float64)

    # Evitar log10(0)
    min_linear = 10.0 ** (floor / 20.0)
    arr = np.where(arr <= 0.0, min_linear, arr)

    db = 20.0 * np.log10(arr)

    if np.isscalar(value):
        # type: ignore[return-value]
        return float(db)
    return db


def rms_dbfs_from_signal(signal: np.ndarray, floor: float = DBFS_FLOOR) -> float:
    """
    Calcula RMS en dBFS de un array de audio (cualquier número de canales).

    El audio puede venir con shape:
        - (N,)  -> mono
        - (N, C) o (C, N) -> multi-canal
    """
    sig = np.asarray(signal, dtype=np.float64)

    if sig.ndim == 2:
        # Aplanamos todos los canales
        sig = sig.reshape(-1)

    # RMS lineal
    rms = float(np.sqrt(np.mean(sig ** 2) + EPS))
    return float(safe_dbfs(rms, floor=floor))


def peak_dbfs_from_signal(signal: np.ndarray, floor: float = DBFS_FLOOR) -> float:
    """
    Calcula el pico máximo en dBFS de un array de audio.
    """
    sig = np.asarray(signal, dtype=np.float64)
    peak_lin = float(np.max(np.abs(sig)))
    if peak_lin <= 0.0:
        return floor
    return float(20.0 * np.log10(peak_lin))


def linear_from_dbfs(db: float) -> float:
    """
    Convierte dBFS (o dB en general) a magnitud lineal.
    """
    return float(10.0 ** (db / 20.0))
