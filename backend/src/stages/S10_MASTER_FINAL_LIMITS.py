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

from utils.analysis_utils import get_temp_dir
from utils.loudness_utils import compute_lufs_and_lra
from utils.color_utils import compute_true_peak_dbfs
from utils.mastering_profiles_utils import get_mastering_profile

try:
    from context import PipelineContext
except ImportError:
    PipelineContext = None # type: ignore


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


def _compute_channel_lufs_diff(y: np.ndarray, sr: int) -> Dict[str, float]:
    arr = np.asarray(y, dtype=np.float32)
    if arr.ndim == 1:
        lufs_L, _ = compute_lufs_and_lra(arr, sr)
        return {"lufs_L": lufs_L, "lufs_R": lufs_L, "channel_loudness_diff_db": 0.0}

    if arr.ndim == 2 and arr.shape[1] >= 2:
        L = arr[:, 0]
        R = arr[:, 1]
        lufs_L, _ = compute_lufs_and_lra(L, sr)
        lufs_R, _ = compute_lufs_and_lra(R, sr)
        if lufs_L == float("-inf") or lufs_R == float("-inf"):
            diff = 0.0
        else:
            diff = abs(lufs_L - lufs_R)
        return {"lufs_L": lufs_L, "lufs_R": lufs_R, "channel_loudness_diff_db": diff}

    return {"lufs_L": float("-inf"), "lufs_R": float("-inf"), "channel_loudness_diff_db": 0.0}


def _compute_stereo_correlation(y: np.ndarray) -> float:
    arr = np.asarray(y, dtype=np.float32)
    if arr.ndim == 1:
        return 1.0
    if arr.ndim == 2 and arr.shape[1] >= 2:
        L = arr[:, 0].astype(np.float32)
        R = arr[:, 1].astype(np.float32)
    else:
        return 0.0

    Lm = L - np.mean(L)
    Rm = R - np.mean(R)
    denom = float(np.sqrt(np.sum(Lm**2) * np.sum(Rm**2)) + 1e-12)
    if denom <= 0.0:
        return 0.0
    corr = float(np.sum(Lm * Rm) / denom)
    return max(-1.0, min(1.0, corr))


def _process_final_limits_memory(
    audio: np.ndarray,
    sr: int,
    true_peak_max_dbtp: float,
    max_output_ceiling_adjust_db: float,
    target_lufs: float,
    style_lufs_tolerance: float,
) -> tuple[np.ndarray, Dict[str, Any]]:
    y = audio

    pre_true_peak = compute_true_peak_dbfs(y, oversample_factor=4)
    pre_lufs, pre_lra = compute_lufs_and_lra(y, sr)
    ch_info_pre = _compute_channel_lufs_diff(y, sr)
    pre_lufs_L = ch_info_pre["lufs_L"]
    pre_lufs_R = ch_info_pre["lufs_R"]
    pre_channel_diff = ch_info_pre["channel_loudness_diff_db"]
    pre_corr = _compute_stereo_correlation(y)

    pre_lufs_within_style = (
        pre_lufs != float("-inf")
        and abs(pre_lufs - target_lufs) <= style_lufs_tolerance
    )

    trim_db = 0.0
    if pre_true_peak > true_peak_max_dbtp:
        needed_reduction = pre_true_peak - true_peak_max_dbtp
        trim_db = min(needed_reduction, max_output_ceiling_adjust_db)
        if trim_db < 0.01:
            trim_db = 0.0

    if trim_db > 0.0:
        gain_lin = 10.0 ** (-trim_db / 20.0)
        y_post = (y * gain_lin).astype(np.float32)
    else:
        y_post = y

    y_post = np.clip(y_post, -1.0, 1.0).astype(np.float32)

    post_true_peak = compute_true_peak_dbfs(y_post, oversample_factor=4)
    post_lufs, post_lra = compute_lufs_and_lra(y_post, sr)
    ch_info_post = _compute_channel_lufs_diff(y_post, sr)
    post_lufs_L = ch_info_post["lufs_L"]
    post_lufs_R = ch_info_post["lufs_R"]
    post_channel_diff = ch_info_post["channel_loudness_diff_db"]
    post_corr = _compute_stereo_correlation(y_post)

    post_lufs_within_style = (
        post_lufs != float("-inf")
        and abs(post_lufs - target_lufs) <= style_lufs_tolerance
    )

    return y_post, {
        "pre_true_peak_dbtp": float(pre_true_peak),
        "pre_lufs_integrated": float(pre_lufs),
        "pre_lra": float(pre_lra),
        "pre_lufs_L": float(pre_lufs_L),
        "pre_lufs_R": float(pre_lufs_R),
        "pre_channel_diff_db": float(pre_channel_diff),
        "pre_corr": float(pre_corr),
        "pre_lufs_within_style": bool(pre_lufs_within_style),
        "post_true_peak_dbtp": float(post_true_peak),
        "post_lufs_integrated": float(post_lufs),
        "post_lra": float(post_lra),
        "post_lufs_L": float(post_lufs_L),
        "post_lufs_R": float(post_lufs_R),
        "post_channel_diff_db": float(post_channel_diff),
        "post_corr": float(post_corr),
        "post_lufs_within_style": bool(post_lufs_within_style),
        "trim_db_applied": float(trim_db),
    }


def process(context: PipelineContext, *args) -> bool:
    """
    IN-MEMORY processing for S10_MASTER_FINAL_LIMITS
    """
    contract_id = context.stage_id
    try:
        analysis = load_analysis_with_context(context)
    except FileNotFoundError:
        logger.error(f"[S10_MASTER_FINAL_LIMITS] Analysis not found.")
        return False

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}
    session: Dict[str, Any] = analysis.get("session", {}) or {}

    style_preset = analysis.get("style_preset", "default")

    true_peak_max_dbtp = float(session.get("true_peak_max_dbtp_target", -1.0))
    max_channel_diff_db = float(session.get("max_channel_loudness_diff_db_target", 0.5))
    correlation_min_target = float(session.get("correlation_min_target", -0.2))

    max_eq_trim_db_per_band = float(session.get("max_eq_trim_db_per_band", 0.5))
    max_output_ceiling_adjust_db = float(
        session.get("max_output_ceiling_adjust_db")
        or limits.get("max_output_ceiling_adjust_db", 0.2)
    )

    target_lufs = float(
        session.get("target_lufs_integrated")
        or get_mastering_profile(style_preset).get("target_lufs_integrated", -11.0)
    )
    style_lufs_tolerance = float(session.get("style_lufs_tolerance", 0.5))

    if context.audio_mixdown is None:
        logger.warning("[S10_MASTER_FINAL_LIMITS] No mixdown to process.")
        return True

    y_processed, result = _process_final_limits_memory(
        context.audio_mixdown,
        context.sample_rate,
        true_peak_max_dbtp,
        max_output_ceiling_adjust_db,
        target_lufs,
        style_lufs_tolerance,
    )

    context.audio_mixdown = y_processed

    # Save metrics
    temp_dir = context.get_stage_dir()
    temp_dir.mkdir(parents=True, exist_ok=True)
    qc_path = temp_dir / "qc_metrics_S10_MASTER_FINAL_LIMITS.json"

    with qc_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "contract_id": contract_id,
                "style_preset": style_preset,
                "targets": {
                    "true_peak_max_dbtp": true_peak_max_dbtp,
                    "target_lufs_integrated": target_lufs,
                    "style_lufs_tolerance": style_lufs_tolerance,
                    "max_channel_loudness_diff_db": max_channel_diff_db,
                    "correlation_min": correlation_min_target,
                    "max_eq_trim_db_per_band": max_eq_trim_db_per_band,
                    "max_output_ceiling_adjust_db": max_output_ceiling_adjust_db,
                },
                "pre": {
                    "true_peak_dbtp": result["pre_true_peak_dbtp"],
                    "lufs_integrated": result["pre_lufs_integrated"],
                    "lra": result["pre_lra"],
                    "lufs_L": result["pre_lufs_L"],
                    "lufs_R": result["pre_lufs_R"],
                    "channel_loudness_diff_db": result["pre_channel_diff_db"],
                    "correlation": result["pre_corr"],
                    "lufs_integrated_within_style_tolerance": result[
                        "pre_lufs_within_style"
                    ],
                },
                "post": {
                    "true_peak_dbtp": result["post_true_peak_dbtp"],
                    "lufs_integrated": result["post_lufs_integrated"],
                    "lra": result["post_lra"],
                    "lufs_L": result["post_lufs_L"],
                    "lufs_R": result["post_lufs_R"],
                    "channel_loudness_diff_db": result["post_channel_diff_db"],
                    "correlation": result["post_corr"],
                    "lufs_integrated_within_style_tolerance": result[
                        "post_lufs_within_style"
                    ],
                    "trim_db_applied": result["trim_db_applied"],
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
