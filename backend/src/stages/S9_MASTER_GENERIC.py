# C:\mix-master\backend\src\stages\S9_MASTER_GENERIC.py

from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any, Tuple

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from pedalboard import Pedalboard, Gain, Limiter  # noqa: E402

try:  # noqa: E402
    from pedalboard import Compressor  # type: ignore
    _HAVE_COMPRESSOR = True
except Exception:  # pragma: no cover
    Compressor = None  # type: ignore
    _HAVE_COMPRESSOR = False

from utils.analysis_utils import get_temp_dir  # noqa: E402
from utils.loudness_utils import compute_lufs_and_lra  # noqa: E402
from utils.color_utils import compute_true_peak_dbfs  # noqa: E402
from utils.mastering_profiles_utils import get_mastering_profile  # noqa: E402


def load_analysis(contract_id: str) -> Dict[str, Any]:
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"
    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")
    with analysis_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _to_float32(x: np.ndarray) -> np.ndarray:
    arr = np.asarray(x, dtype=np.float32)
    return arr


def _soft_clip(x: np.ndarray, threshold_dbfs: float = -3.0, drive: float = 2.5) -> np.ndarray:
    """
    Soft clip simple y estable (tanh) con zona lineal hasta threshold.
    Reduce picos ANTES del limitador sin contar como GR del limitador.
    """
    arr = _to_float32(x)
    thr = float(10.0 ** (threshold_dbfs / 20.0))
    thr = max(1e-6, min(thr, 0.999))

    a = np.abs(arr)
    y = arr.copy()

    over = a > thr
    if np.any(over):
        t = (a[over] - thr) / max(1e-6, (1.0 - thr))
        # mapeo suave al rango (thr..1)
        sat = np.tanh(t * drive) / np.tanh(drive)
        y_over = thr + (1.0 - thr) * sat
        y[over] = np.sign(arr[over]) * y_over

    return np.clip(y, -1.0, 1.0).astype(np.float32)


def _apply_chain_gain_clip_limiter(
    x: np.ndarray,
    sr: int,
    gain_db: float,
    ceiling_dbtp: float,
    enable_soft_clip: bool,
) -> Tuple[np.ndarray, float, float, float]:
    """
    Aplica: Gain -> (SoftClip opcional) -> Limiter(ceiling)
    Devuelve:
      y_out, limiter_gr_db, pre_peak_seen_by_limiter, post_peak
    """
    arr = _to_float32(x)

    # Gain
    g = float(gain_db)
    if abs(g) > 1e-6:
        arr_g = arr * float(10.0 ** (g / 20.0))
    else:
        arr_g = arr

    # Soft clip (antes del limiter)
    if enable_soft_clip:
        arr_prelim = _soft_clip(arr_g, threshold_dbfs=-3.0, drive=2.5)
    else:
        arr_prelim = np.clip(arr_g, -1.0, 1.0).astype(np.float32)

    pre_peak = compute_true_peak_dbfs(arr_prelim, oversample_factor=4)

    # Limiter
    board = Pedalboard([Limiter(threshold_db=float(ceiling_dbtp))])
    y = board(arr_prelim, sr)
    y = _to_float32(y)

    post_peak = compute_true_peak_dbfs(y, oversample_factor=4)
    limiter_gr = max(0.0, float(pre_peak - post_peak))

    return y, float(limiter_gr), float(pre_peak), float(post_peak)


def _maybe_precompress(x: np.ndarray, sr: int, delta_lufs: float) -> Tuple[np.ndarray, Dict[str, float]]:
    """
    Compresión suave opcional para bajar crest factor cuando el target está muy lejos.
    Si Compressor no está disponible, no-op.
    """
    meta = {"used": 0.0, "threshold_db": 0.0, "ratio": 0.0, "attack_ms": 0.0, "release_ms": 0.0}

    if not _HAVE_COMPRESSOR:
        return _to_float32(x), meta

    # Solo si necesitamos empujar bastante (p.ej. > 4 LU)
    if delta_lufs <= 4.0:
        return _to_float32(x), meta

    # Ajuste conservador: reduce picos sin “aplastar” demasiado
    threshold_db = -18.0
    ratio = 2.0
    attack_ms = 10.0
    release_ms = 120.0

    try:
        board = Pedalboard([
            Compressor(
                threshold_db=float(threshold_db),
                ratio=float(ratio),
                attack_ms=float(attack_ms),
                release_ms=float(release_ms),
            )
        ])
        y = board(_to_float32(x), sr)
        y = _to_float32(y)
        meta.update(
            {
                "used": 1.0,
                "threshold_db": float(threshold_db),
                "ratio": float(ratio),
                "attack_ms": float(attack_ms),
                "release_ms": float(release_ms),
            }
        )
        return y, meta
    except Exception as e:
        logger.logger.info(f"[S9_MASTER_GENERIC] Pre-compressor falló: {e}. Continuando sin compresión.")
        return _to_float32(x), meta


def _apply_ms_width(
    x: np.ndarray,
    width_factor: float,
) -> Tuple[np.ndarray, float, float]:
    arr = _to_float32(x)

    if arr.ndim == 1 or (arr.ndim == 2 and arr.shape[1] == 1):
        mono = arr if arr.ndim == 1 else arr[:, 0]
        return mono.astype(np.float32), 0.0, 0.0

    if arr.ndim != 2 or arr.shape[1] < 2:
        raise ValueError("Se esperaba audio estéreo (N, 2) para M/S width.")

    L = arr[:, 0]
    R = arr[:, 1]
    M = 0.5 * (L + R)
    S = 0.5 * (L - R)

    eps = 1e-9
    rms_M = float(np.sqrt(np.mean(M**2)) + eps)
    rms_S_pre = float(np.sqrt(np.mean(S**2)) + eps)
    ratio_pre = rms_S_pre / rms_M if rms_M > 0 else 0.0

    S2 = S * float(width_factor)

    rms_S_post = float(np.sqrt(np.mean(S2**2)) + eps)
    ratio_post = rms_S_post / rms_M if rms_M > 0 else 0.0

    y = np.stack([M + S2, M - S2], axis=1)
    y = np.clip(y, -1.0, 1.0)

    return y.astype(np.float32), float(ratio_pre), float(ratio_post)


def main() -> None:
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S9_MASTER_GENERIC.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]
    analysis = load_analysis(contract_id)

    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}
    session: Dict[str, Any] = analysis.get("session", {}) or {}

    style_preset = analysis.get("style_preset", "default")
    mastering_targets: Dict[str, Any] = session.get("mastering_targets", {}) or {}
    m_profile = get_mastering_profile(style_preset)

    target_lufs = float(mastering_targets.get("target_lufs_integrated") or m_profile.get("target_lufs_integrated", -11.0))
    target_lra_min = float(mastering_targets.get("target_lra_min") or m_profile.get("target_lra_min", 5.0))
    target_lra_max = float(mastering_targets.get("target_lra_max") or m_profile.get("target_lra_max", 10.0))
    target_ceiling = float(mastering_targets.get("target_ceiling_dbtp") or m_profile.get("target_ceiling_dbtp", -1.0))
    target_width_factor_style = float(mastering_targets.get("target_ms_width_factor") or m_profile.get("target_ms_width_factor", 1.0))

    max_limiter_gr_db = float(limits.get("max_limiter_gain_reduction_db", 4.0))
    max_width_change_pct = float(limits.get("max_stereo_width_change_percent", 10.0))

    temp_dir = get_temp_dir(contract_id, create=False)
    full_song_path = temp_dir / "full_song.wav"
    if not full_song_path.exists():
        logger.logger.info(f"[S9_MASTER_GENERIC] No existe {full_song_path}; no se puede aplicar mastering.")
        return

    # Leer audio
    y, sr = sf.read(full_song_path, always_2d=False)
    y = _to_float32(y)
    sr = int(sr)

    pre_tp = compute_true_peak_dbfs(y, oversample_factor=4)
    pre_lufs, pre_lra = compute_lufs_and_lra(y, sr)

    logger.logger.info(
        f"[S9_MASTER_GENERIC] PRE: TP={pre_tp:.2f} dBTP, LUFS={pre_lufs:.2f}, LRA={pre_lra:.2f}."
    )

    delta_lufs = float(target_lufs - pre_lufs)

    # 1) Pre-compresión opcional si estamos muy lejos del target
    y_work, comp_meta = _maybe_precompress(y, sr, delta_lufs)

    pre2_tp = compute_true_peak_dbfs(y_work, oversample_factor=4)
    pre2_lufs, pre2_lra = compute_lufs_and_lra(y_work, sr)

    logger.logger.info(
        f"[S9_MASTER_GENERIC] PRE2(after pre-comp): TP={pre2_tp:.2f} dBTP, LUFS={pre2_lufs:.2f}, "
        f"used_comp={bool(comp_meta.get('used', 0.0) > 0.5)}."
    )

    # 2) Buscar gain_db máximo (hasta delta_lufs) que respete GR_max del limitador
    #    OJO: delta_lufs puede ser negativo (si ya estamos por encima). En ese caso, atenuamos directo.
    enable_soft_clip = True  # clave para ganar loudness sin disparar GR del limiter

    if delta_lufs <= 0.0:
        # ya estamos por encima del target → bajamos sin necesidad de limitar (pero mantenemos ceiling)
        gain_db_best = float(delta_lufs)
        y_lim, gr_db, pre_seen, post_peak = _apply_chain_gain_clip_limiter(
            y_work, sr, gain_db_best, target_ceiling, enable_soft_clip=False
        )
    else:
        gain_hi = float(max(0.0, delta_lufs))
        gain_lo = 0.0

        best = None

        # 12 iteraciones = precisión sub-0.01 dB aprox
        for _ in range(12):
            g = 0.5 * (gain_lo + gain_hi)
            y_try, gr_try, pre_seen, post_peak = _apply_chain_gain_clip_limiter(
                y_work, sr, g, target_ceiling, enable_soft_clip=enable_soft_clip
            )
            if gr_try <= (max_limiter_gr_db + 0.10):
                gain_lo = g
                best = (y_try, gr_try, pre_seen, post_peak)
            else:
                gain_hi = g

        gain_db_best = float(gain_lo)
        if best is None:
            # extremo: ni siquiera con 0 dB cumple (raro). Usamos 0.
            y_lim, gr_db, pre_seen, post_peak = _apply_chain_gain_clip_limiter(
                y_work, sr, 0.0, target_ceiling, enable_soft_clip=enable_soft_clip
            )
        else:
            y_lim, gr_db, pre_seen, post_peak = best

    # Métricas tras limiter
    post_lim_tp = compute_true_peak_dbfs(y_lim, oversample_factor=4)
    post_lim_lufs, post_lim_lra = compute_lufs_and_lra(y_lim, sr)

    logger.logger.info(
        f"[S9_MASTER_GENERIC] POST-LIMITER: gain={gain_db_best:+.2f} dB, "
        f"limiter_GR≈{gr_db:.2f} dB (max={max_limiter_gr_db:.1f}), "
        f"TP={post_lim_tp:.2f} dBTP, LUFS={post_lim_lufs:.2f}, LRA={post_lim_lra:.2f}."
    )

    # 3) Width M/S limitado por contrato (igual que antes, pero garantizando límites)
    max_width_delta = float(max_width_change_pct) / 100.0
    raw_delta = float(target_width_factor_style - 1.0)
    clamped_delta = max(-max_width_delta, min(max_width_delta, raw_delta))
    width_factor = 1.0 + clamped_delta

    y_ms, width_ratio_pre, width_ratio_post = _apply_ms_width(y_lim, width_factor)

    # 4) Safety trim final si el width ha reventado ceiling (o por overs)
    post_tp = compute_true_peak_dbfs(y_ms, oversample_factor=4)
    post_lufs, post_lra = compute_lufs_and_lra(y_ms, sr)

    CEIL_SAFETY_DB = 0.30
    trim_db = 0.0
    if post_tp > target_ceiling:
        trim_db = (target_ceiling - CEIL_SAFETY_DB) - post_tp
        lin = float(10.0 ** (trim_db / 20.0))
        y_ms = (_to_float32(y_ms) * lin).astype(np.float32)

        post_tp = compute_true_peak_dbfs(y_ms, oversample_factor=4)
        post_lufs, post_lra = compute_lufs_and_lra(y_ms, sr)

        logger.logger.info(
            f"[S9_MASTER_GENERIC] Safety trim {trim_db:+.2f} dB para ceiling {target_ceiling:.2f}."
        )

    logger.logger.info(
        f"[S9_MASTER_GENERIC] POST-FINAL: TP={post_tp:.2f} dBTP, LUFS={post_lufs:.2f}, "
        f"LRA={post_lra:.2f}, width_factor={width_factor:.3f}."
    )

    # Escribir audio final (float)
    sf.write(full_song_path, np.clip(y_ms, -1.0, 1.0).astype(np.float32), sr, subtype="FLOAT")

    # Guardar métricas para QC
    metrics_path = temp_dir / "master_metrics_S9_MASTER_GENERIC.json"
    payload = {
        "contract_id": contract_id,
        "style_preset": style_preset,
        "targets": {
            "target_lufs_integrated": float(target_lufs),
            "target_lra_min": float(target_lra_min),
            "target_lra_max": float(target_lra_max),
            "target_ceiling_dbtp": float(target_ceiling),
            "target_ms_width_factor": float(target_width_factor_style),
            "max_limiter_gain_reduction_db": float(max_limiter_gr_db),
            "max_stereo_width_change_percent": float(max_width_change_pct),
        },
        "pre": {
            "true_peak_dbtp": float(pre_tp),
            "lufs_integrated": float(pre_lufs),
            "lra": float(pre_lra),
        },
        "preconditioning": {
            "used_compressor": bool(comp_meta.get("used", 0.0) > 0.5),
            "compressor_params": comp_meta,
            "pre2_true_peak_dbtp": float(pre2_tp),
            "pre2_lufs_integrated": float(pre2_lufs),
            "pre2_lra": float(pre2_lra),
            "soft_clip_enabled": bool(enable_soft_clip),
        },
        "post_limiter": {
            "pre_gain_db": float(gain_db_best),
            "limiter_gr_db": float(gr_db),
            "pre_peak_seen_by_limiter_dbtp": float(pre_seen),
            "true_peak_dbtp": float(post_lim_tp),
            "lufs_integrated": float(post_lim_lufs),
            "lra": float(post_lim_lra),
        },
        "post_final": {
            "true_peak_dbtp": float(post_tp),
            "lufs_integrated": float(post_lufs),
            "lra": float(post_lra),
            "width_ratio_pre": float(width_ratio_pre),
            "width_ratio_post": float(width_ratio_post),
            "width_factor_applied": float(width_factor),
            "safety_trim_db": float(trim_db),
        },
    }

    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    logger.logger.info(f"[S9_MASTER_GENERIC] Métricas guardadas en: {metrics_path}")


if __name__ == "__main__":
    main()
