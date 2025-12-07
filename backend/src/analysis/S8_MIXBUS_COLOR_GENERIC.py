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
from utils.color_utils import (
    compute_rms_dbfs,
    compute_true_peak_dbfs,
)

try:
    from context import PipelineContext
except ImportError:
    PipelineContext = None # type: ignore


def _estimate_noise_floor_dbfs(y: np.ndarray) -> float:
    arr = np.asarray(y, dtype=np.float32)
    if arr.ndim > 1:
        arr = np.mean(arr, axis=1)

    if arr.size == 0:
        return float("-inf")

    eps = 1e-9
    inst_db = 20.0 * np.log10(np.abs(arr) + eps)
    p10 = float(np.percentile(inst_db, 10.0))
    return p10


def _analyze_mixbus_color_memory(context: PipelineContext) -> Dict[str, Any]:
    if context.audio_mixdown is None:
        return {
            "sr_mix": None,
            "pre_true_peak_dbtp": float("-inf"),
            "pre_rms_dbfs": float("-inf"),
            "noise_floor_dbfs": float("-inf"),
            "error": "[S8_MIXBUS_COLOR_GENERIC] No mixdown in memory.",
        }

    y = context.audio_mixdown
    sr = context.sample_rate

    pre_true_peak_dbtp = compute_true_peak_dbfs(y, oversample_factor=4)
    pre_rms_dbfs = compute_rms_dbfs(y)
    noise_floor_dbfs = _estimate_noise_floor_dbfs(y)

    return {
        "sr_mix": sr,
        "pre_true_peak_dbtp": pre_true_peak_dbtp,
        "pre_rms_dbfs": pre_rms_dbfs,
        "noise_floor_dbfs": noise_floor_dbfs,
        "error": None,
    }


def process(context: PipelineContext, *args) -> bool:
    """
    IN-MEMORY analysis for S8_MIXBUS_COLOR_GENERIC
    """
    contract_id = context.stage_id
    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    tp_min = float(metrics.get("target_true_peak_range_dbtp_min", -4.0))
    tp_max = float(metrics.get("target_true_peak_range_dbtp_max", -2.0))
    max_thd_percent = float(metrics.get("max_thd_percent", 3.0))
    max_sat_per_pass_db = float(limits.get("max_additional_saturation_per_pass", 1.0))

    try:
        cfg = load_session_config_memory(context, contract_id)
    except Exception:
        cfg = {"style_preset": "Unknown"}

    style_preset = cfg.get("style_preset", "Unknown")

    result = _analyze_mixbus_color_memory(context)

    if result['error'] is not None:
        logger.info(result['error'])
        sr_mix = None
        pre_true_peak_dbtp = float("-inf")
        pre_rms_dbfs = float("-inf")
        noise_floor_dbfs = float("-inf")
    else:
        sr_mix = result['sr_mix']
        pre_true_peak_dbtp = result['pre_true_peak_dbtp']
        pre_rms_dbfs = result['pre_rms_dbfs']
        noise_floor_dbfs = result['noise_floor_dbfs']

        logger.info(
            f"[S8_MIXBUS_COLOR_GENERIC] In-memory analysis (sr={sr_mix}). "
            f"true_peak={pre_true_peak_dbtp:.2f} dBTP, RMS={pre_rms_dbfs:.2f} dBFS, "
            f"noise_floor={noise_floor_dbfs:.2f} dBFS."
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
            "pre_rms_dbfs": pre_rms_dbfs,
            "noise_floor_dbfs": noise_floor_dbfs,
            "target_true_peak_range_dbtp_min": tp_min,
            "target_true_peak_range_dbtp_max": tp_max,
            "max_thd_percent": max_thd_percent,
            "max_additional_saturation_per_pass_db": max_sat_per_pass_db,
        },
    }

    temp_dir = context.get_stage_dir()
    temp_dir.mkdir(parents=True, exist_ok=True)
    output_path = temp_dir / f"analysis_{contract_id}.json"

    try:
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(session_state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"[S8_MIXBUS_COLOR_GENERIC] Failed to save analysis JSON: {e}")
        return False

    return True

def main() -> None:
    pass

if __name__ == "__main__":
    main()
