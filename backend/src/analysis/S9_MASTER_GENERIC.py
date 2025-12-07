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


def _analyze_master_memory(context: PipelineContext) -> Dict[str, Any]:
    if context.audio_mixdown is None:
        return {
            "sr_mix": None,
            "pre_true_peak_dbtp": float("-inf"),
            "pre_lufs_integrated": float("-inf"),
            "pre_lra": 0.0,
            "error": "[S9_MASTER_GENERIC] No mixdown in memory.",
        }

    y = context.audio_mixdown
    sr = context.sample_rate

    pre_true_peak_dbtp = compute_true_peak_dbfs(y, oversample_factor=4)
    pre_lufs_integrated, pre_lra = compute_lufs_and_lra(y, sr)

    return {
        "sr_mix": sr,
        "pre_true_peak_dbtp": pre_true_peak_dbtp,
        "pre_lufs_integrated": pre_lufs_integrated,
        "pre_lra": pre_lra,
        "error": None,
    }


def process(context: PipelineContext, *args) -> bool:
    """
    IN-MEMORY analysis for S9_MASTER_GENERIC
    """
    contract_id = context.stage_id
    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    max_limiter_gr_db = float(limits.get("max_limiter_gain_reduction_db", 4.0))
    max_eq_change_db = float(limits.get("max_eq_change_db_per_band_per_pass", 2.0))
    max_width_change_pct = float(limits.get("max_stereo_width_change_percent", 10.0))

    try:
        cfg = load_session_config_memory(context, contract_id)
    except Exception:
        cfg = {"style_preset": "Unknown"}

    style_preset = cfg.get("style_preset", "Unknown")

    m_profile = get_mastering_profile(style_preset)
    target_lufs = float(m_profile.get("target_lufs_integrated", -11.0))
    target_lra_min = float(m_profile.get("target_lra_min", 5.0))
    target_lra_max = float(m_profile.get("target_lra_max", 10.0))
    target_ceiling_dbtp = float(m_profile.get("target_ceiling_dbtp", -1.0))
    target_ms_width_factor = float(m_profile.get("target_ms_width_factor", 1.0))

    result = _analyze_master_memory(context)

    if result["error"] is not None:
        logger.info(result["error"])
        sr_mix = None
        pre_true_peak_dbtp = float("-inf")
        pre_lufs_integrated = float("-inf")
        pre_lra = 0.0
    else:
        sr_mix = result["sr_mix"]
        pre_true_peak_dbtp = result["pre_true_peak_dbtp"]
        pre_lufs_integrated = result["pre_lufs_integrated"]
        pre_lra = result["pre_lra"]

        logger.info(
            f"[S9_MASTER_GENERIC] In-memory analysis (sr={sr_mix}). "
            f"true_peak={pre_true_peak_dbtp:.2f} dBTP, "
            f"LUFS={pre_lufs_integrated:.2f}, LRA={pre_lra:.2f}."
        )

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "samplerate_hz": sr_mix,
            "pre_true_peak_dbtp": pre_true_peak_dbtp,
            "pre_lufs_integrated": pre_lufs_integrated,
            "pre_lra": pre_lra,
            "max_limiter_gain_reduction_db": max_limiter_gr_db,
            "max_eq_change_db_per_band_per_pass": max_eq_change_db,
            "max_stereo_width_change_percent": max_width_change_pct,
            "mastering_targets": {
                "target_lufs_integrated": target_lufs,
                "target_lra_min": target_lra_min,
                "target_lra_max": target_lra_max,
                "target_ceiling_dbtp": target_ceiling_dbtp,
                "target_ms_width_factor": target_ms_width_factor,
            },
        },
    }

    temp_dir = context.get_stage_dir()
    temp_dir.mkdir(parents=True, exist_ok=True)
    output_path = temp_dir / f"analysis_{contract_id}.json"

    try:
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(session_state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"[S9_MASTER_GENERIC] Failed to save analysis JSON: {e}")
        return False

    return True

def main() -> None:
    pass

if __name__ == "__main__":
    main()
