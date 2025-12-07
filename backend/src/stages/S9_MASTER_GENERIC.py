from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any
import json
import numpy as np

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pedalboard import Pedalboard, Gain, Limiter

from utils.analysis_utils import get_temp_dir
from utils.loudness_utils import compute_lufs_and_lra
from utils.color_utils import compute_true_peak_dbfs
from utils.mastering_profiles_utils import get_mastering_profile

try:
    from context import PipelineContext
except ImportError:
    PipelineContext = None # type: ignore

# Sample rate global para el limitador de Pedalboard
_MASTER_SAMPLE_RATE: float | None = None


def load_analysis_with_context(context: PipelineContext) -> Dict[str, Any]:
    stage_id = context.stage_id
    if context.temp_root:
        temp_dir = context.temp_root / stage_id
    else:
        temp_dir = get_temp_dir(stage_id, create=False)

    analysis_path = temp_dir / f"analysis_{stage_id}.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def _apply_limiter(
    x: np.ndarray,
    pre_gain_db: float,
    ceiling_dbtp: float,
) -> tuple[np.ndarray, float]:
    global _MASTER_SAMPLE_RATE
    if _MASTER_SAMPLE_RATE is None:
        raise RuntimeError(
            "Sample rate no definido en _MASTER_SAMPLE_RATE antes de llamar a _apply_limiter."
        )

    sr = _MASTER_SAMPLE_RATE
    arr = np.asarray(x, dtype=np.float32)

    pre_gain_lin = 10.0 ** (pre_gain_db / 20.0)
    y_pre = arr * pre_gain_lin
    pre_peak = compute_true_peak_dbfs(y_pre, oversample_factor=4)

    board = Pedalboard(
        [
            Gain(gain_db=float(pre_gain_db)),
            Limiter(threshold_db=float(ceiling_dbtp)),
        ]
    )

    y_lim = board(arr, sr)
    y_lim = np.asarray(y_lim, dtype=np.float32)
    post_peak = compute_true_peak_dbfs(y_lim, oversample_factor=4)

    gr_db = max(0.0, (pre_peak - post_peak))

    if x.ndim == 1 and y_lim.ndim == 2 and y_lim.shape[1] == 1:
        y_lim = y_lim[:, 0]

    return y_lim.astype(np.float32), gr_db


def _apply_ms_width(
    x: np.ndarray,
    width_factor: float,
) -> tuple[np.ndarray, float, float]:
    arr = np.asarray(x, dtype=np.float32)
    if arr.ndim == 1 or (arr.ndim == 2 and arr.shape[1] == 1):
        mono = arr if arr.ndim == 1 else arr[:, 0]
        return mono.astype(np.float32), 0.0, 0.0

    if arr.ndim != 2 or arr.shape[1] < 2:
        # Assuming last dim is channels
        pass

    L = arr[:, 0]
    R = arr[:, 1]

    M = 0.5 * (L + R)
    S = 0.5 * (L - R)

    eps = 1e-9
    rms_M_pre = float(np.sqrt(np.mean(M**2)) + eps)
    rms_S_pre = float(np.sqrt(np.mean(S**2)) + eps)
    ratio_pre = rms_S_pre / rms_M_pre if rms_M_pre > 0 else 0.0

    S_proc = S * float(width_factor)

    rms_S_post = float(np.sqrt(np.mean(S_proc**2)) + eps)
    ratio_post = rms_S_post / rms_M_pre if rms_M_pre > 0 else 0.0

    L_out = M + S_proc
    R_out = M - S_proc

    y = np.stack([L_out, R_out], axis=1)
    y = np.clip(y, -1.0, 1.0)

    return y.astype(np.float32), ratio_pre, ratio_post


def _process_master_memory(
    audio: np.ndarray,
    sr: int,
    max_limiter_gr_db: float,
    max_width_change_pct: float,
    target_lufs: float,
    target_lra_min: float,
    target_lra_max: float,
    target_ceiling: float,
    target_width_factor_style: float,
) -> tuple[np.ndarray, Dict[str, float]]:
    global _MASTER_SAMPLE_RATE
    _MASTER_SAMPLE_RATE = float(sr)
    y = audio

    pre_true_peak = compute_true_peak_dbfs(y, oversample_factor=4)
    pre_lufs, pre_lra = compute_lufs_and_lra(y, sr)

    logger.info(
        f"[S9_MASTER_GENERIC] PRE: true_peak={pre_true_peak:.2f} dBTP, "
        f"LUFS={pre_lufs:.2f}, LRA={pre_lra:.2f}."
    )

    delta_lufs = target_lufs - pre_lufs

    pre_gain_db = 0.0
    if delta_lufs > 0.0:
        allowed_gain_by_gr = max_limiter_gr_db + target_ceiling - pre_true_peak
        pre_gain_db = min(delta_lufs, allowed_gain_by_gr)
        pre_gain_db = max(pre_gain_db, 0.0)
    else:
        pre_gain_db = delta_lufs

    y_limited, limiter_gr_db = _apply_limiter(y, pre_gain_db, target_ceiling)

    post_true_peak_lim = compute_true_peak_dbfs(y_limited, oversample_factor=4)
    post_lufs_lim, post_lra_lim = compute_lufs_and_lra(y_limited, sr)

    max_width_delta = max_width_change_pct / 100.0
    raw_delta = target_width_factor_style - 1.0
    clamped_delta = max(-max_width_delta, min(max_width_delta, raw_delta))
    width_factor = 1.0 + clamped_delta

    y_ms, width_ratio_pre, width_ratio_post = _apply_ms_width(y_limited, width_factor)

    post_true_peak = compute_true_peak_dbfs(y_ms, oversample_factor=4)
    post_lufs, post_lra = compute_lufs_and_lra(y_ms, sr)

    CEIL_SAFETY_DB = 0.3
    trim_peak_db = 0.0
    if post_true_peak > target_ceiling:
        trim_peak_db = (target_ceiling - CEIL_SAFETY_DB) - post_true_peak
        trim_lin = 10.0 ** (trim_peak_db / 20.0)
        y_ms = (y_ms * trim_lin).astype(np.float32)

        post_true_peak = compute_true_peak_dbfs(y_ms, oversample_factor=4)
        post_lufs, post_lra = compute_lufs_and_lra(y_ms, sr)

    y_ms = np.clip(y_ms, -1.0, 1.0).astype(np.float32)

    return y_ms, {
        "pre_true_peak_dbtp": float(pre_true_peak),
        "pre_lufs_integrated": float(pre_lufs),
        "pre_lra": float(pre_lra),
        "pre_gain_db": float(pre_gain_db),
        "post_true_peak_lim_dbtp": float(post_true_peak_lim),
        "post_lufs_lim": float(post_lufs_lim),
        "post_lra_lim": float(post_lra_lim),
        "limiter_gr_db": float(limiter_gr_db),
        "post_true_peak_final_dbtp": float(post_true_peak),
        "post_lufs_final": float(post_lufs),
        "post_lra_final": float(post_lra),
        "width_ratio_pre": float(width_ratio_pre),
        "width_ratio_post": float(width_ratio_post),
        "width_factor_applied": float(width_factor),
    }


def process(context: PipelineContext, *args) -> bool:
    """
    IN-MEMORY processing for S9_MASTER_GENERIC
    """
    contract_id = context.stage_id
    try:
        analysis = load_analysis_with_context(context)
    except FileNotFoundError:
        logger.error(f"[S9_MASTER_GENERIC] Analysis not found.")
        return False

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}
    session: Dict[str, Any] = analysis.get("session", {}) or {}

    style_preset = analysis.get("style_preset", "default")

    max_limiter_gr_db = float(limits.get("max_limiter_gain_reduction_db", 4.0))
    max_width_change_pct = float(limits.get("max_stereo_width_change_percent", 10.0))

    mastering_targets: Dict[str, Any] = session.get("mastering_targets", {}) or {}
    m_profile = get_mastering_profile(style_preset)

    target_lufs = float(mastering_targets.get("target_lufs_integrated") or m_profile.get("target_lufs_integrated", -11.0))
    target_lra_min = float(mastering_targets.get("target_lra_min") or m_profile.get("target_lra_min", 5.0))
    target_lra_max = float(mastering_targets.get("target_lra_max") or m_profile.get("target_lra_max", 10.0))
    target_ceiling = float(mastering_targets.get("target_ceiling_dbtp") or m_profile.get("target_ceiling_dbtp", -1.0))
    target_width_factor_style = float(mastering_targets.get("target_ms_width_factor") or m_profile.get("target_ms_width_factor", 1.0))

    if context.audio_mixdown is None:
        logger.warning("[S9_MASTER_GENERIC] No mixdown to master.")
        return True

    y_processed, result = _process_master_memory(
        context.audio_mixdown,
        context.sample_rate,
        max_limiter_gr_db,
        max_width_change_pct,
        target_lufs,
        target_lra_min,
        target_lra_max,
        target_ceiling,
        target_width_factor_style,
    )

    context.audio_mixdown = y_processed

    # Save metrics
    temp_dir = context.get_stage_dir()
    temp_dir.mkdir(parents=True, exist_ok=True)
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
                },
                "pre": {
                    "true_peak_dbtp": result["pre_true_peak_dbtp"],
                    "lufs_integrated": result["pre_lufs_integrated"],
                    "lra": result["pre_lra"],
                },
                "post_limiter": {
                    "true_peak_dbtp": result["post_true_peak_lim_dbtp"],
                    "lufs_integrated": result["post_lufs_lim"],
                    "lra": result["post_lra_lim"],
                    "limiter_gr_db": result["limiter_gr_db"],
                    "pre_gain_db": result["pre_gain_db"],
                },
                "post_final": {
                    "true_peak_dbtp": result["post_true_peak_final_dbtp"],
                    "lufs_integrated": result["post_lufs_final"],
                    "lra": result["post_lra_final"],
                    "width_ratio_pre": result["width_ratio_pre"],
                    "width_ratio_post": result["width_ratio_post"],
                    "width_factor_applied": result["width_factor_applied"],
                },
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    return True

def main() -> None:
    pass

if __name__ == "__main__":
    main()
