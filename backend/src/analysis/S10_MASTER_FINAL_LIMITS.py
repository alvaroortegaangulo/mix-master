from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any
import json
import numpy as np

# --- hack para importar utils ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.analysis_utils import (
    load_contract,
    get_temp_dir,
)
from utils.session_utils import load_session_config_memory
from utils.loudness_utils import compute_lufs_and_lra
from utils.color_utils import compute_true_peak_dbfs
from utils.mastering_profiles_utils import get_mastering_profile

try:
    from context import PipelineContext
except ImportError:
    PipelineContext = None # type: ignore


def _compute_channel_lufs_diff(y: np.ndarray, sr: int) -> Dict[str, float]:
    arr = np.asarray(y, dtype=np.float32)
    if arr.ndim == 1:
        lufs_L, _ = compute_lufs_and_lra(arr, sr)
        return {
            "lufs_L": lufs_L,
            "lufs_R": lufs_L,
            "channel_loudness_diff_db": 0.0,
        }

    if arr.ndim == 2 and arr.shape[1] >= 2:
        L = arr[:, 0]
        R = arr[:, 1]
        lufs_L, _ = compute_lufs_and_lra(L, sr)
        lufs_R, _ = compute_lufs_and_lra(R, sr)
        if lufs_L == float("-inf") or lufs_R == float("-inf"):
            diff = 0.0
        else:
            diff = abs(lufs_L - lufs_R)
        return {
            "lufs_L": lufs_L,
            "lufs_R": lufs_R,
            "channel_loudness_diff_db": diff,
        }

    return {
        "lufs_L": float("-inf"),
        "lufs_R": float("-inf"),
        "channel_loudness_diff_db": 0.0,
    }


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


def _analyze_master_final_memory(context: PipelineContext) -> Dict[str, Any]:
    if context.audio_mixdown is None:
        return {
            "sr_mix": None,
            "true_peak_dbtp": float("-inf"),
            "lufs_integrated": float("-inf"),
            "lra": 0.0,
            "channel_lufs_L": float("-inf"),
            "channel_lufs_R": float("-inf"),
            "channel_diff_db": 0.0,
            "correlation": 1.0,
            "error": "[S10_MASTER_FINAL_LIMITS] No mixdown in memory.",
        }

    y = context.audio_mixdown
    sr = context.sample_rate

    true_peak_dbtp = compute_true_peak_dbfs(y, oversample_factor=4)
    lufs_integrated, lra = compute_lufs_and_lra(y, sr)
    ch_info = _compute_channel_lufs_diff(y, sr)
    correlation = _compute_stereo_correlation(y)

    return {
        "sr_mix": sr,
        "true_peak_dbtp": true_peak_dbtp,
        "lufs_integrated": lufs_integrated,
        "lra": lra,
        "channel_lufs_L": ch_info["lufs_L"],
        "channel_lufs_R": ch_info["lufs_R"],
        "channel_diff_db": ch_info["channel_loudness_diff_db"],
        "correlation": correlation,
        "error": None,
    }


def process(context: PipelineContext, *args) -> bool:
    """
    IN-MEMORY analysis for S10_MASTER_FINAL_LIMITS
    """
    contract_id = context.stage_id
    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    true_peak_max_dbtp = float(metrics.get("true_peak_max_dbtp", -1.0))
    max_channel_diff_db = float(metrics.get("max_channel_loudness_diff_db", 0.5))
    correlation_min = float(metrics.get("correlation_min", -0.2))

    max_eq_trim_db_per_band = float(limits.get("max_eq_trim_db_per_band", 0.5))
    max_output_ceiling_adjust_db = float(limits.get("max_output_ceiling_adjust_db", 0.2))

    try:
        cfg = load_session_config_memory(context, contract_id)
    except Exception:
        cfg = {"style_preset": "Unknown"}

    style_preset = cfg.get("style_preset", "Unknown")

    m_profile = get_mastering_profile(style_preset)
    target_lufs = float(m_profile.get("target_lufs_integrated", -11.0))
    style_lufs_tolerance = 0.5

    result = _analyze_master_final_memory(context)

    if result["error"] is not None:
        logger.info(result["error"])
        sr_mix = None
        true_peak_dbtp = float("-inf")
        lufs_integrated = float("-inf")
        lra = 0.0
        channel_lufs_L = float("-inf")
        channel_lufs_R = float("-inf")
        channel_diff_db = 0.0
        correlation = 1.0
    else:
        sr_mix = result["sr_mix"]
        true_peak_dbtp = result["true_peak_dbtp"]
        lufs_integrated = result["lufs_integrated"]
        lra = result["lra"]
        channel_lufs_L = result["channel_lufs_L"]
        channel_lufs_R = result["channel_lufs_R"]
        channel_diff_db = result["channel_diff_db"]
        correlation = result["correlation"]

        logger.info(
            f"[S10_MASTER_FINAL_LIMITS] In-memory analysis (sr={sr_mix}). "
            f"TP={true_peak_dbtp:.2f} dBTP, "
            f"LUFS={lufs_integrated:.2f}, LRA={lra:.2f}, "
            f"diff_LR={channel_diff_db:.2f} dB, corr={correlation:.3f}."
        )

    lufs_within_style = False
    if lufs_integrated != float("-inf"):
        if abs(lufs_integrated - target_lufs) <= style_lufs_tolerance:
            lufs_within_style = True

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "samplerate_hz": sr_mix,
            "true_peak_dbtp": true_peak_dbtp,
            "true_peak_max_dbtp_target": true_peak_max_dbtp,
            "lufs_integrated": lufs_integrated,
            "target_lufs_integrated": target_lufs,
            "style_lufs_tolerance": style_lufs_tolerance,
            "lufs_integrated_within_style_tolerance": lufs_within_style,
            "lra": lra,
            "lra_target_min": float(m_profile.get("target_lra_min", 5.0)),
            "lra_target_max": float(m_profile.get("target_lra_max", 10.0)),
            "channel_lufs_L": channel_lufs_L,
            "channel_lufs_R": channel_lufs_R,
            "channel_loudness_diff_db": channel_diff_db,
            "max_channel_loudness_diff_db_target": max_channel_diff_db,
            "correlation": correlation,
            "correlation_min_target": correlation_min,
            "max_eq_trim_db_per_band": max_eq_trim_db_per_band,
            "max_output_ceiling_adjust_db": max_output_ceiling_adjust_db,
        },
    }

    temp_dir = context.get_stage_dir()
    temp_dir.mkdir(parents=True, exist_ok=True)
    output_path = temp_dir / f"analysis_{contract_id}.json"

    try:
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(session_state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"[S10_MASTER_FINAL_LIMITS] Failed to save analysis JSON: {e}")
        return False

    return True

def main() -> None:
    pass

if __name__ == "__main__":
    main()
