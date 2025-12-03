# C:\mix-master\backend\src\utils\dynamics_utils.py

from __future__ import annotations
from stages.pipeline_context import PipelineContext

from typing import Tuple

import numpy as np


def _to_mono_float32(y: np.ndarray) -> np.ndarray:
    arr = np.asarray(y, dtype=np.float32)
    if arr.ndim > 1:
        arr = np.mean(arr, axis=1)
    return arr


def compute_crest_factor_db(y: np.ndarray) -> Tuple[float, float, float]:
    """
    Devuelve (rms_db, peak_db, crest_db) en dBFS relativos (escala interna).

    Si la señal es silencio, devuelve (-inf, -inf, 0.0).
    """
    y_mono = _to_mono_float32(y)
    if y_mono.size == 0:
        return float("-inf"), float("-inf"), 0.0

    peak = float(np.max(np.abs(y_mono)))
    if peak <= 0.0:
        return float("-inf"), float("-inf"), 0.0

    rms = float(np.sqrt(np.mean(y_mono**2)))
    if rms <= 0.0:
        rms_db = float("-inf")
    else:
        rms_db = 20.0 * np.log10(rms)

    peak_db = 20.0 * np.log10(peak)
    crest_db = peak_db - rms_db if rms_db != float("-inf") else 0.0

    return rms_db, peak_db, crest_db


def compress_peak_detector(
    y: np.ndarray,
    sr: int,
    threshold_db: float,
    ratio: float,
    attack_ms: float,
    release_ms: float,
    makeup_gain_db: float = 0.0,
) -> Tuple[np.ndarray, float, float]:
    """
    Compresor offline sencillo (peak-based, feed-forward).

    - y: array mono o estéreo/multicanal.
    - sr: samplerate.
    - threshold_db: umbral en dBFS (relativo).
    - ratio: relación de compresión (p.ej. 2.0, 4.0).
    - attack_ms, release_ms: tiempos de ataque y relajación en ms.
    - makeup_gain_db: ganancia de compensación (normalmente 0 en esta fase).

    Devuelve:
      - y_out: señal comprimida, misma forma que y.
      - avg_gr_db: ganancia de reducción media (solo donde hay compresión, en dB).
      - max_gr_db: ganancia de reducción máxima (dB).
    """
    arr = np.asarray(y, dtype=np.float32)
    if arr.size == 0:
        return arr, 0.0, 0.0

    if arr.ndim == 1:
        data = arr.reshape(-1, 1)
    else:
        data = arr

    n, c = data.shape

    # Detector: máximo absoluto entre canales
    detector = np.max(np.abs(data), axis=1)

    # Coeficientes de ataque y release
    attack_ms = max(attack_ms, 0.1)
    release_ms = max(release_ms, 0.1)

    attack_coeff = float(np.exp(-1.0 / (attack_ms * 0.001 * sr)))
    release_coeff = float(np.exp(-1.0 / (release_ms * 0.001 * sr)))

    eps = 1e-12
    env = 0.0

    gr_db_arr = np.zeros(n, dtype=np.float32)
    gain_db_arr = np.zeros(n, dtype=np.float32)

    inv_ratio = 1.0 / float(max(ratio, 1.0))
    k = 1.0 - inv_ratio  # factor para GR: over_db * k

    for i in range(n):
        x = detector[i]
        if x > env:
            env = attack_coeff * env + (1.0 - attack_coeff) * x
        else:
            env = release_coeff * env + (1.0 - release_coeff) * x

        env_db = 20.0 * np.log10(env + eps)
        over_db = env_db - threshold_db

        if over_db > 0.0:
            gr_db = over_db * k
        else:
            gr_db = 0.0

        gr_db_arr[i] = gr_db
        gain_db_arr[i] = -gr_db + makeup_gain_db

    gain_lin = 10.0 ** (gain_db_arr / 20.0)
    gain_lin = gain_lin.reshape(-1, 1)

    data_out = data * gain_lin

    if arr.ndim == 1:
        y_out = data_out[:, 0]
    else:
        y_out = data_out

    # Métricas de GR
    mask = gr_db_arr > 0.0
    if np.any(mask):
        avg_gr_db = float(np.mean(gr_db_arr[mask]))
        max_gr_db = float(np.max(gr_db_arr[mask]))
    else:
        avg_gr_db = 0.0
        max_gr_db = 0.0

    return y_out.astype(np.float32), avg_gr_db, max_gr_db
