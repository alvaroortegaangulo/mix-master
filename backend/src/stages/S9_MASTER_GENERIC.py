from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from pedalboard import Pedalboard, Gain, Limiter  # noqa: E402

from utils.analysis_utils import get_temp_dir  # noqa: E402
from utils.loudness_utils import compute_lufs_and_lra  # noqa: E402
from utils.mastering_profiles_utils import get_mastering_profile  # noqa: E402


# ------------------------------------------------------------
# Medición de pico / true-peak
# ------------------------------------------------------------

def _peak_dbfs_sample(x: np.ndarray) -> float:
    """
    Pico sample-peak (no true-peak). Devuelve dBFS pudiendo ser > 0 si hay overs en float.
    """
    arr = np.asarray(x, dtype=np.float32)
    if arr.size == 0:
        return float("-inf")
    peak = float(np.max(np.abs(arr)))
    if peak <= 0.0:
        return float("-inf")
    return float(20.0 * np.log10(peak))


def _true_peak_dbfs(x: np.ndarray, sr: int, oversample_factor: int = 4) -> float:
    """
    True-peak aproximado por oversampling.
    - Si SciPy está disponible, usa resample_poly (mejor).
    - Si no, cae a sample-peak.
    """
    arr = np.asarray(x, dtype=np.float32)
    if arr.size == 0 or sr <= 0:
        return float("-inf")

    try:
        from scipy.signal import resample_poly  # type: ignore
    except Exception:
        return _peak_dbfs_sample(arr)

    if arr.ndim == 1:
        chans = [arr]
    elif arr.ndim == 2:
        chans = [arr[:, ch] for ch in range(arr.shape[1])]
    else:
        return _peak_dbfs_sample(arr)

    peaks: List[float] = []
    for y in chans:
        y_os = resample_poly(y, oversample_factor, 1)
        peaks.append(float(np.max(np.abs(y_os))) if y_os.size else 0.0)

    peak = float(max(peaks)) if peaks else 0.0
    if peak <= 0.0:
        return float("-inf")
    return float(20.0 * np.log10(peak))


def _measure_tp_dbfs(x: np.ndarray, sr: int) -> float:
    try:
        return _true_peak_dbfs(x, sr, oversample_factor=4)
    except Exception:
        return _peak_dbfs_sample(x)


# ------------------------------------------------------------
# Clipper (soft/hard) antes del limiter
# ------------------------------------------------------------

def _db_to_lin(db: float) -> float:
    return float(10.0 ** (db / 20.0))


def _apply_clipper(x: np.ndarray, threshold_dbfs: float, mode: str = "soft") -> np.ndarray:
    """
    Aplica clipping simétrico en float.
    - hard: np.clip a +/- threshold_lin
    - soft: y = t * tanh(x/t)  (satura a +/- t, más musical)
    """
    arr = np.asarray(x, dtype=np.float32)
    t = _db_to_lin(float(threshold_dbfs))
    if not np.isfinite(t) or t <= 0.0:
        return arr

    if mode.lower().startswith("hard"):
        return np.clip(arr, -t, t).astype(np.float32)

    # soft
    return (t * np.tanh(arr / t)).astype(np.float32)


def _clipper_to_target_shave(
    x: np.ndarray,
    target_shave_db: float,
    mode: str = "soft",
    max_iters: int = 6,
    tol_db: float = 0.15,
) -> Tuple[np.ndarray, Dict[str, float]]:
    """
    Ajusta el umbral del clipper para conseguir aproximadamente un "peak shave"
    (reducción de sample-peak) de target_shave_db.

    Devuelve (y, metrics):
      metrics incluye:
        - peak_pre_dbfs, peak_post_dbfs
        - threshold_dbfs_used
        - target_shave_db, actual_shave_db
        - clipped_pct
    """
    arr = np.asarray(x, dtype=np.float32)
    peak_pre = _peak_dbfs_sample(arr)
    if peak_pre == float("-inf") or target_shave_db <= 0.05:
        return arr, {
            "peak_pre_dbfs": float(peak_pre),
            "peak_post_dbfs": float(peak_pre),
            "threshold_dbfs_used": float("nan"),
            "target_shave_db": float(target_shave_db),
            "actual_shave_db": 0.0,
            "clipped_pct": 0.0,
        }

    # Rango de búsqueda (en dBFS):
    #   high = sin clip (umbral en el propio pico)
    #   low  = clip fuerte (12 dB por debajo del pico; suficiente para 1-2 dB de shave sin volverse loco)
    high = float(peak_pre)
    low = float(peak_pre - 12.0)

    # Inicial
    thr = float(peak_pre - float(target_shave_db))
    thr = max(low, min(high, thr))

    best_y = arr
    best_thr = thr
    best_shave = 0.0
    best_peak_post = peak_pre

    for _ in range(max_iters):
        y = _apply_clipper(arr, thr, mode=mode)
        peak_post = _peak_dbfs_sample(y)
        shave = float(peak_pre - peak_post)

        # Guardar mejor aproximación
        if abs(shave - target_shave_db) < abs(best_shave - target_shave_db):
            best_y = y
            best_thr = thr
            best_shave = shave
            best_peak_post = peak_post

        if shave < target_shave_db - tol_db:
            # falta shave -> más clipping -> bajar umbral
            high = thr
            thr = 0.5 * (low + high)
        elif shave > target_shave_db + tol_db:
            # sobra shave -> menos clipping -> subir umbral
            low = thr
            thr = 0.5 * (low + high)
        else:
            # suficientemente cerca
            best_y = y
            best_thr = thr
            best_shave = shave
            best_peak_post = peak_post
            break

    # porcentaje aproximado de muestras afectadas
    t_lin = _db_to_lin(best_thr)
    if np.isfinite(t_lin) and t_lin > 0.0:
        clipped_pct = float(100.0 * np.mean(np.abs(arr) > t_lin))
    else:
        clipped_pct = 0.0

    return best_y.astype(np.float32), {
        "peak_pre_dbfs": float(peak_pre),
        "peak_post_dbfs": float(best_peak_post),
        "threshold_dbfs_used": float(best_thr),
        "target_shave_db": float(target_shave_db),
        "actual_shave_db": float(best_shave),
        "clipped_pct": float(clipped_pct),
    }


# ------------------------------------------------------------
# Procesos
# ------------------------------------------------------------

def load_analysis(contract_id: str) -> Dict[str, Any]:
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"
    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")
    with analysis_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _apply_gain_only(x: np.ndarray, sr: int, gain_db: float) -> np.ndarray:
    board = Pedalboard([Gain(gain_db=float(gain_db))])
    y = board(np.asarray(x, dtype=np.float32), sr)
    return np.asarray(y, dtype=np.float32)


def _apply_limiter_only(x: np.ndarray, sr: int, ceiling_db: float) -> np.ndarray:
    board = Pedalboard([Limiter(threshold_db=float(ceiling_db))])
    y = board(np.asarray(x, dtype=np.float32), sr)
    return np.asarray(y, dtype=np.float32)


def _apply_ms_width(
    x: np.ndarray,
    width_factor: float,
) -> Tuple[np.ndarray, float, float]:
    """
    Cambia anchura estéreo en M/S SIN hacer clip.
    Devuelve:
      y, ratio_pre, ratio_post   (RMS(S)/RMS(M))
    """
    arr = np.asarray(x, dtype=np.float32)

    if arr.ndim == 1 or (arr.ndim == 2 and arr.shape[1] == 1):
        mono = arr if arr.ndim == 1 else arr[:, 0]
        return mono.astype(np.float32), 0.0, 0.0

    if arr.ndim != 2 or arr.shape[1] < 2:
        raise ValueError("Se esperaba audio estéreo (N, 2+) para M/S width.")

    L = arr[:, 0]
    R = arr[:, 1]

    M = 0.5 * (L + R)
    S = 0.5 * (L - R)

    eps = 1e-12
    rms_M = float(np.sqrt(np.mean(M**2)) + eps)
    rms_S_pre = float(np.sqrt(np.mean(S**2)) + eps)
    ratio_pre = rms_S_pre / rms_M if rms_M > 0 else 0.0

    S_proc = S * float(width_factor)

    rms_S_post = float(np.sqrt(np.mean(S_proc**2)) + eps)
    ratio_post = rms_S_post / rms_M if rms_M > 0 else 0.0

    L_out = M + S_proc
    R_out = M - S_proc

    y = np.stack([L_out, R_out], axis=1).astype(np.float32)
    return y, ratio_pre, ratio_post


def _enforce_ceiling_with_trim(
    x: np.ndarray,
    sr: int,
    ceiling_db: float,
    safety_db: float = 0.3,
) -> Tuple[np.ndarray, float, float]:
    """
    Asegura ceiling por trim global (NO clip).
    Devuelve:
      y_trim, trim_db, post_tp_db
    """
    tp = _measure_tp_dbfs(x, sr)
    target_tp = float(ceiling_db) - float(safety_db)

    if tp == float("-inf"):
        return x.astype(np.float32), 0.0, tp

    if tp <= target_tp:
        return x.astype(np.float32), 0.0, tp

    trim_db = target_tp - tp
    lin = 10.0 ** (trim_db / 20.0)
    y = (np.asarray(x, dtype=np.float32) * lin).astype(np.float32)
    tp2 = _measure_tp_dbfs(y, sr)
    return y, float(trim_db), float(tp2)


def _choose_clipper_shave_db(
    desired_gain_db: float,
    headroom_db: float,
    max_limiter_gr_db: float,
    max_clipper_shave_db: float,
    reco_from_analysis: float,
    target_lufs: float,
) -> float:
    """
    Política musical:
      - Si no vamos a empujar hacia arriba, no clip.
      - Si vamos a exceder headroom y/o pedir mucho limiting, usar 1–2 dB (cap).
      - Si analysis trae recomendación, se usa como base.
    """
    if desired_gain_db <= 0.2:
        return 0.0

    limiting_needed = max(0.0, desired_gain_db - headroom_db)

    # Base: recomendación del análisis (si existe)
    shave = float(max(0.0, reco_from_analysis))

    # Si no hay recomendación pero limiting será relevante -> aplicar mínimo musical
    if shave < 0.5:
        if limiting_needed >= 3.0 or target_lufs <= -10.0:
            shave = 1.5
        elif limiting_needed >= 2.0:
            shave = 1.0

    # Si excede GR máxima, clipper cubre el exceso
    excess_over_gr = limiting_needed - max_limiter_gr_db
    if excess_over_gr > shave:
        shave = float(excess_over_gr)

    shave = float(min(max(shave, 0.0), max_clipper_shave_db))
    return shave


def _find_optimal_gain_for_lra(
    y: np.ndarray,
    sr: int,
    initial_gain_db: float,
    target_lufs: float,
    target_lra_min: float,
    target_ceiling: float,
    clipper_shave_db: float,
    clipper_mode: str,
    max_iterations: int = 5,
    gain_step_db: float = 1.0,
) -> Tuple[float, Dict[str, float]]:
    """
    Busca iterativamente el gain máximo que no destruya el LRA.

    Algoritmo:
    1. test_gain = initial_gain_db
    2. Loop hasta max_iterations:
       a. Aplicar gain al audio
       b. Aplicar clipper si clipper_shave_db >= 0.5
       c. Aplicar limiter con target_ceiling
       d. Medir LUFS y LRA
       e. Si LRA >= target_lra_min: encontrado, break
       f. Si no: test_gain -= gain_step_db
       g. Si test_gain <= 0: usar 0, break
    3. Return (test_gain, metrics)

    Nota: No modifica el audio original, solo simula para encontrar el gain óptimo.
    """
    test_gain = float(initial_gain_db)
    best_gain = test_gain
    best_lra = 0.0
    best_lufs = float("-inf")
    iterations = 0

    for i in range(max_iterations):
        iterations = i + 1

        # Simular cadena de procesamiento
        y_test = _apply_gain_only(y, sr, test_gain)

        if clipper_shave_db >= 0.5:
            y_test, _ = _clipper_to_target_shave(
                y_test,
                target_shave_db=clipper_shave_db,
                mode=clipper_mode,
            )

        y_test = _apply_limiter_only(y_test, sr, target_ceiling)

        test_lufs, test_lra = compute_lufs_and_lra(y_test, sr)

        # Guardar mejor resultado
        if test_lra >= target_lra_min:
            best_gain = test_gain
            best_lra = test_lra
            best_lufs = test_lufs
            break

        # Guardar incluso si no cumple (por si ninguno cumple)
        if test_lra > best_lra:
            best_gain = test_gain
            best_lra = test_lra
            best_lufs = test_lufs

        # Reducir gain para próxima iteración
        test_gain -= gain_step_db
        if test_gain <= 0:
            test_gain = 0.0
            # Una última prueba con gain 0
            y_test = _apply_limiter_only(y, sr, target_ceiling)
            test_lufs, test_lra = compute_lufs_and_lra(y_test, sr)
            if test_lra > best_lra:
                best_gain = 0.0
                best_lra = test_lra
                best_lufs = test_lufs
            break

    return best_gain, {
        "lufs_achieved": float(best_lufs),
        "lra_achieved": float(best_lra),
        "iterations_used": int(iterations),
        "lra_protected": bool(best_gain < initial_gain_db),
        "gain_reduction_db": float(initial_gain_db - best_gain),
    }


def _process_master(
    full_song_path: Path,
    max_limiter_gr_db: float,
    max_width_change_pct: float,
    target_lufs: float,
    target_lra_min: float,
    target_lra_max: float,
    target_ceiling: float,
    target_width_factor_style: float,
    max_clipper_shave_db: float,
    clipper_mode: str,
    clipper_reco_shave_db: float,
) -> Dict[str, float]:
    """
    Master robusto con clipper pre-limiter:
      - Pre métricas
      - Decide clipper_shave_db (1–2 dB típicos)
      - Calcula pre_gain hacia LUFS target, considerando headroom + shave del clipper + GR máx del limiter
      - Gain -> Clipper -> Limiter
      - M/S width (limitado)
      - Ceiling enforcement con trim (sin clip)
      - Write FLOAT
    """
    y, sr = sf.read(full_song_path, always_2d=False)
    y = np.asarray(y, dtype=np.float32)

    pre_tp = _measure_tp_dbfs(y, sr)
    pre_sample_peak = _peak_dbfs_sample(y)
    pre_lufs, pre_lra = compute_lufs_and_lra(y, sr)

    logger.logger.info(
        f"[S9_MASTER_GENERIC] PRE: TP={pre_tp:.2f} dBTP, sample_peak={pre_sample_peak:.2f} dBFS, "
        f"LUFS={pre_lufs:.2f}, LRA={pre_lra:.2f}."
    )

    desired_gain_db = float(target_lufs - pre_lufs)
    headroom_db = float(target_ceiling - pre_tp)  # headroom hasta ceiling (aprox, TP)

    # Decide clipper shave (objetivo) y ajusta "headroom efectivo"
    clipper_target_shave_db = _choose_clipper_shave_db(
        desired_gain_db=desired_gain_db,
        headroom_db=headroom_db,
        max_limiter_gr_db=max_limiter_gr_db,
        max_clipper_shave_db=max_clipper_shave_db,
        reco_from_analysis=clipper_reco_shave_db,
        target_lufs=target_lufs,
    )
    headroom_eff_db = float(headroom_db + clipper_target_shave_db)

    # ------------------------------------------------------------
    # 1) Calcular pre_gain_db hacia target LUFS, respetando GR máx.
    #    Ahora usando headroom_eff_db (incluye el “shave” del clipper).
    # ------------------------------------------------------------
    if desired_gain_db > 0.0:
        limiting_needed_db = max(0.0, desired_gain_db - headroom_eff_db)
        if limiting_needed_db > max_limiter_gr_db:
            pre_gain_db = headroom_eff_db + max_limiter_gr_db
        else:
            pre_gain_db = desired_gain_db
        pre_gain_db = max(0.0, float(pre_gain_db))
    else:
        pre_gain_db = float(desired_gain_db)

    if abs(pre_gain_db) < 0.05:
        pre_gain_db = 0.0

    HARD_PREGAIN_CAP = 12.0
    if pre_gain_db > HARD_PREGAIN_CAP:
        logger.logger.info(
            f"[S9_MASTER_GENERIC] Aviso: pre_gain_db={pre_gain_db:.2f} dB demasiado alto; "
            f"cap a {HARD_PREGAIN_CAP:.2f} dB por seguridad."
        )
        pre_gain_db = HARD_PREGAIN_CAP

    logger.logger.info(
        f"[S9_MASTER_GENERIC] desired_gain={desired_gain_db:+.2f} dB, "
        f"headroom_to_ceiling={headroom_db:+.2f} dB, "
        f"clipper_target_shave={clipper_target_shave_db:.2f} dB ({clipper_mode}), "
        f"headroom_eff≈{headroom_eff_db:+.2f} dB, "
        f"pre_gain_aplicado={pre_gain_db:+.2f} dB (GRmax={max_limiter_gr_db:.2f} dB)."
    )

    # ------------------------------------------------------------
    # 1.5) LRA Protection
    # ------------------------------------------------------------
    # Si el pre_gain es agresivo, verificar que no destruya el LRA
    lra_was_protected = False
    lra_protection_gain_reduction_db = 0.0
    initial_pre_gain_db = float(pre_gain_db)

    if pre_gain_db > 2.0 and target_lra_min > 0:
        optimal_gain, lra_metrics = _find_optimal_gain_for_lra(
            y=y,
            sr=sr,
            initial_gain_db=pre_gain_db,
            target_lufs=target_lufs,
            target_lra_min=target_lra_min,
            target_ceiling=target_ceiling,
            clipper_shave_db=clipper_target_shave_db,
            clipper_mode=clipper_mode,
            max_iterations=5,
            gain_step_db=1.0,
        )

        if optimal_gain < pre_gain_db:
            logger.logger.info(
                f"[S9_MASTER_GENERIC] LRA protection: gain reducido de {pre_gain_db:+.2f} a {optimal_gain:+.2f} dB "
                f"para mantener LRA >= {target_lra_min:.1f} LU (LRA logrado: {lra_metrics['lra_achieved']:.2f} LU)"
            )
            lra_protection_gain_reduction_db = float(pre_gain_db - optimal_gain)
            pre_gain_db = optimal_gain
            lra_was_protected = True

    # ------------------------------------------------------------
    # 2) Gain -> (Clipper) -> Limiter
    # ------------------------------------------------------------
    y_gain = _apply_gain_only(y, sr, pre_gain_db)

    tp_pre_clip = _measure_tp_dbfs(y_gain, sr)
    sp_pre_clip = _peak_dbfs_sample(y_gain)

    clip_metrics = {
        "peak_pre_dbfs": float(sp_pre_clip),
        "peak_post_dbfs": float(sp_pre_clip),
        "threshold_dbfs_used": float("nan"),
        "target_shave_db": float(0.0),
        "actual_shave_db": float(0.0),
        "clipped_pct": float(0.0),
    }

    if clipper_target_shave_db >= 0.5:
        y_clip, clip_metrics = _clipper_to_target_shave(
            y_gain,
            target_shave_db=float(clipper_target_shave_db),
            mode=str(clipper_mode),
            max_iters=6,
            tol_db=0.15,
        )
        logger.logger.info(
            f"[S9_MASTER_GENERIC] CLIPPER ({clipper_mode}): target_shave={clip_metrics['target_shave_db']:.2f} dB, "
            f"actual_shave={clip_metrics['actual_shave_db']:.2f} dB, "
            f"thr={clip_metrics['threshold_dbfs_used']:.2f} dBFS, "
            f"peak_pre={clip_metrics['peak_pre_dbfs']:.2f} dBFS, peak_post={clip_metrics['peak_post_dbfs']:.2f} dBFS, "
            f"clipped_pct≈{clip_metrics['clipped_pct']:.3f}%."
        )
    else:
        y_clip = y_gain

    tp_post_clip = _measure_tp_dbfs(y_clip, sr)
    sp_post_clip = _peak_dbfs_sample(y_clip)

    y_lim = _apply_limiter_only(y_clip, sr, target_ceiling)

    tp_post_limiter = _measure_tp_dbfs(y_lim, sr)
    sample_peak_post_limiter = _peak_dbfs_sample(y_lim)
    post_lim_lufs, post_lim_lra = compute_lufs_and_lra(y_lim, sr)

    # Estimación de GR del limiter a partir de TP (después del clipper)
    limiter_gr_est = max(0.0, float(tp_post_clip - tp_post_limiter))

    logger.logger.info(
        f"[S9_MASTER_GENERIC] POST-LIMITER: TP={tp_post_limiter:.2f} dBTP, "
        f"sample_peak={sample_peak_post_limiter:.2f} dBFS, "
        f"LUFS={post_lim_lufs:.2f}, LRA={post_lim_lra:.2f}, "
        f"GR_est≈{limiter_gr_est:.2f} dB."
    )

    # ------------------------------------------------------------
    # 3) M/S width (limitado)
    # ------------------------------------------------------------
    max_width_delta = float(max_width_change_pct) / 100.0
    raw_delta = float(target_width_factor_style) - 1.0
    clamped_delta = max(-max_width_delta, min(max_width_delta, raw_delta))
    width_factor = 1.0 + clamped_delta

    logger.logger.info(
        f"[S9_MASTER_GENERIC] width_target_style={target_width_factor_style:.2f}, "
        f"width_factor_aplicado={width_factor:.3f} (maxΔ={max_width_delta*100:.1f}%)."
    )

    y_ms, width_ratio_pre, width_ratio_post = _apply_ms_width(y_lim, width_factor)

    post_tp_pretrim = _measure_tp_dbfs(y_ms, sr)
    post_lufs_pretrim, post_lra_pretrim = compute_lufs_and_lra(y_ms, sr)

    # ------------------------------------------------------------
    # 4) Ceiling enforcement (trim) SIN clip
    # ------------------------------------------------------------
    y_final, trim_db, post_tp = _enforce_ceiling_with_trim(
        y_ms, sr, target_ceiling, safety_db=0.3
    )
    post_lufs, post_lra = compute_lufs_and_lra(y_final, sr)
    post_sample_peak = _peak_dbfs_sample(y_final)

    if trim_db != 0.0:
        logger.logger.info(
            f"[S9_MASTER_GENERIC] Trim final aplicado {trim_db:+.2f} dB "
            f"(TP antes={post_tp_pretrim:.2f} dB, después={post_tp:.2f} dB)."
        )

    logger.logger.info(
        f"[S9_MASTER_GENERIC] POST-FINAL: TP={post_tp:.2f} dBTP, sample_peak={post_sample_peak:.2f} dBFS, "
        f"LUFS={post_lufs:.2f}, LRA={post_lra:.2f}, "
        f"width_ratio_pre={width_ratio_pre:.3f}, width_ratio_post={width_ratio_post:.3f}."
    )

    # Verificar si LRA final cumple con el target
    if target_lra_min > 0 and post_lra < target_lra_min:
        logger.logger.warning(
            f"[S9_MASTER_GENERIC] LRA final ({post_lra:.2f} LU) está por debajo del target mínimo "
            f"({target_lra_min:.1f} LU). El material original puede estar muy comprimido."
        )

    # ------------------------------------------------------------
    # 5) Escritura FLOAT para evitar clip por PCM
    # ------------------------------------------------------------
    sf.write(full_song_path, y_final, sr, subtype="FLOAT")
    logger.logger.info(f"[S9_MASTER_GENERIC] Master reescrito (FLOAT) en {full_song_path}.")

    return {
        "pre_true_peak_dbtp": float(pre_tp),
        "pre_sample_peak_dbfs": float(pre_sample_peak),
        "pre_lufs_integrated": float(pre_lufs),
        "pre_lra": float(pre_lra),
        "pre_gain_db": float(pre_gain_db),

        "lra_protection_applied": float(1.0 if lra_was_protected else 0.0),
        "lra_protection_gain_reduction_db": float(lra_protection_gain_reduction_db),

        "clipper_enabled": float(1.0 if clipper_target_shave_db >= 0.5 else 0.0),
        "clipper_target_shave_db": float(clipper_target_shave_db),
        "clipper_actual_shave_db": float(clip_metrics["actual_shave_db"]),
        "clipper_threshold_dbfs": float(clip_metrics["threshold_dbfs_used"]),
        "clipper_peak_pre_dbfs": float(clip_metrics["peak_pre_dbfs"]),
        "clipper_peak_post_dbfs": float(clip_metrics["peak_post_dbfs"]),
        "clipper_clipped_pct": float(clip_metrics["clipped_pct"]),
        "tp_pre_clip_dbtp": float(tp_pre_clip),
        "tp_post_clip_dbtp": float(tp_post_clip),
        "sp_pre_clip_dbfs": float(sp_pre_clip),
        "sp_post_clip_dbfs": float(sp_post_clip),

        "post_true_peak_lim_dbtp": float(tp_post_limiter),
        "post_sample_peak_lim_dbfs": float(sample_peak_post_limiter),
        "post_lufs_lim": float(post_lim_lufs),
        "post_lra_lim": float(post_lim_lra),
        "limiter_gr_db": float(limiter_gr_est),

        "post_true_peak_final_dbtp": float(post_tp),
        "post_sample_peak_final_dbfs": float(post_sample_peak),
        "post_lufs_final": float(post_lufs),
        "post_lra_final": float(post_lra),

        "width_ratio_pre": float(width_ratio_pre),
        "width_ratio_post": float(width_ratio_post),
        "width_factor_applied": float(width_factor),

        "trim_db": float(trim_db),
        "post_tp_pretrim": float(post_tp_pretrim),
        "post_lufs_pretrim": float(post_lufs_pretrim),
        "post_lra_pretrim": float(post_lra_pretrim),
    }


def main() -> None:
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S9_MASTER_GENERIC.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]
    analysis = load_analysis(contract_id)

    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}
    session: Dict[str, Any] = analysis.get("session", {}) or {}
    style_preset = analysis.get("style_preset", "default")

    max_limiter_gr_db = float(limits.get("max_limiter_gain_reduction_db", 4.0))
    max_width_change_pct = float(limits.get("max_stereo_width_change_percent", 10.0))

    # Nuevo (opcional) límite para clipping
    max_clipper_shave_db = float(limits.get("max_clipper_peak_shave_db", session.get("max_clipper_peak_shave_db", 2.0)))

    mastering_targets: Dict[str, Any] = session.get("mastering_targets", {}) or {}
    m_profile = get_mastering_profile(style_preset)

    target_lufs = float(
        mastering_targets.get("target_lufs_integrated")
        or m_profile.get("target_lufs_integrated", -11.0)
    )
    target_lra_min = float(
        mastering_targets.get("target_lra_min")
        or m_profile.get("target_lra_min", 5.0)
    )
    target_lra_max = float(
        mastering_targets.get("target_lra_max")
        or m_profile.get("target_lra_max", 10.0)
    )
    target_ceiling = float(
        mastering_targets.get("target_ceiling_dbtp")
        or m_profile.get("target_ceiling_dbtp", -1.0)
    )
    target_width_factor_style = float(
        mastering_targets.get("target_ms_width_factor")
        or m_profile.get("target_ms_width_factor", 1.0)
    )

    # Recomendación del análisis (si existe)
    clipper_reco = float(session.get("clipper_recommended_peak_shave_db", 0.0))

    # Modo del clipper: por defecto soft (más “musical”)
    # Puedes hacerlo estilo-dependent si quieres en mastering_profile (p.ej. m_profile["clipper_mode"]).
    clipper_mode = str(m_profile.get("clipper_mode", "soft"))

    temp_dir = get_temp_dir(contract_id, create=False)
    full_song_path = temp_dir / "full_song.wav"
    if not full_song_path.exists():
        logger.logger.info(f"[S9_MASTER_GENERIC] No existe {full_song_path}; no se puede aplicar mastering.")
        return

    result = _process_master(
        full_song_path=full_song_path,
        max_limiter_gr_db=max_limiter_gr_db,
        max_width_change_pct=max_width_change_pct,
        target_lufs=target_lufs,
        target_lra_min=target_lra_min,
        target_lra_max=target_lra_max,
        target_ceiling=target_ceiling,
        target_width_factor_style=target_width_factor_style,
        max_clipper_shave_db=max_clipper_shave_db,
        clipper_mode=clipper_mode,
        clipper_reco_shave_db=clipper_reco,
    )

    metrics_path = temp_dir / "master_metrics_S9_MASTER_GENERIC.json"
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "contract_id": contract_id,
                "style_preset": style_preset,
                "targets": {
                    "target_lufs_integrated": target_lufs,
                    "target_lra_min": target_lra_min,
                    "target_lra_max": target_lra_max,
                    "target_ceiling_dbtp": target_ceiling,
                    "target_ms_width_factor": target_width_factor_style,
                    "max_limiter_gain_reduction_db": max_limiter_gr_db,
                    "max_stereo_width_change_percent": max_width_change_pct,
                    "max_clipper_peak_shave_db": max_clipper_shave_db,
                    "clipper_mode": clipper_mode,
                },
                "pre": {
                    "true_peak_dbtp": result["pre_true_peak_dbtp"],
                    "sample_peak_dbfs": result["pre_sample_peak_dbfs"],
                    "lufs_integrated": result["pre_lufs_integrated"],
                    "lra": result["pre_lra"],
                },
                "clipper": {
                    "enabled": bool(result["clipper_enabled"] >= 0.5),
                    "target_shave_db": result["clipper_target_shave_db"],
                    "actual_shave_db": result["clipper_actual_shave_db"],
                    "threshold_dbfs": result["clipper_threshold_dbfs"],
                    "peak_pre_dbfs": result["clipper_peak_pre_dbfs"],
                    "peak_post_dbfs": result["clipper_peak_post_dbfs"],
                    "clipped_pct": result["clipper_clipped_pct"],
                    "tp_pre_clip_dbtp": result["tp_pre_clip_dbtp"],
                    "tp_post_clip_dbtp": result["tp_post_clip_dbtp"],
                    "sp_pre_clip_dbfs": result["sp_pre_clip_dbfs"],
                    "sp_post_clip_dbfs": result["sp_post_clip_dbfs"],
                },
                "post_limiter": {
                    "true_peak_dbtp": result["post_true_peak_lim_dbtp"],
                    "sample_peak_dbfs": result["post_sample_peak_lim_dbfs"],
                    "lufs_integrated": result["post_lufs_lim"],
                    "lra": result["post_lra_lim"],
                    "limiter_gr_db": result["limiter_gr_db"],
                    "pre_gain_db": result["pre_gain_db"],
                },
                "post_final": {
                    "true_peak_dbtp": result["post_true_peak_final_dbtp"],
                    "sample_peak_dbfs": result["post_sample_peak_final_dbfs"],
                    "lufs_integrated": result["post_lufs_final"],
                    "lra": result["post_lra_final"],
                    "width_ratio_pre": result["width_ratio_pre"],
                    "width_ratio_post": result["width_ratio_post"],
                    "width_factor_applied": result["width_factor_applied"],
                    "trim_db": result["trim_db"],
                    "post_tp_pretrim": result["post_tp_pretrim"],
                    "post_lufs_pretrim": result["post_lufs_pretrim"],
                    "post_lra_pretrim": result["post_lra_pretrim"],
                },
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    logger.logger.info(f"[S9_MASTER_GENERIC] Métricas guardadas en: {metrics_path}")


if __name__ == "__main__":
    main()
