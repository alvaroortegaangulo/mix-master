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

from pedalboard import Distortion

from utils.analysis_utils import get_temp_dir
from utils.color_utils import (
    compute_rms_dbfs,
    compute_true_peak_dbfs,
    estimate_thd_percent,
)

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


def _style_saturation_factor(style_preset: str) -> float:
    s = (style_preset or "").lower()
    if "flamenco" in s or "rumba" in s:
        return 0.7
    if "urbano" in s or "trap" in s or "reggaeton" in s:
        return 1.0
    if "edm" in s or "club" in s or "house" in s:
        return 1.0
    if "acoustic" in s or "acústico" in s or "jazz" in s:
        return 0.5
    return 0.8


def _apply_pedalboard_saturation(y: np.ndarray, sr: int, drive_db: float) -> np.ndarray:
    if not isinstance(y, np.ndarray):
        y = np.asarray(y, dtype=np.float32)
    else:
        y = y.astype(np.float32)

    dist = Distortion()
    dist.drive_db = float(drive_db)
    y_sat = dist(y, sr)
    return y_sat.astype(np.float32)


def _process_mixbus_color_memory(
    audio: np.ndarray,
    sr: int,
    style_preset: str,
    tp_min: float,
    tp_max: float,
    max_thd_percent: float,
    max_sat_per_pass_db: float,
) -> tuple[np.ndarray, Dict[str, float]]:
    y = audio

    pre_true_peak_dbtp = compute_true_peak_dbfs(y, oversample_factor=4)
    pre_rms_dbfs = compute_rms_dbfs(y)

    logger.info(
        f"[S8_MIXBUS_COLOR_GENERIC] PRE: true_peak={pre_true_peak_dbtp:.2f} dBTP, "
        f"RMS={pre_rms_dbfs:.2f} dBFS."
    )

    TP_MARGIN = 0.3
    IDEMP_DRIVE_MAX_DB = 0.5
    IDEMP_TRIM_MAX_DB = 0.5

    pre_in_range = (
        pre_true_peak_dbtp >= tp_min - TP_MARGIN
        and pre_true_peak_dbtp <= tp_max + TP_MARGIN
    )

    style_factor = _style_saturation_factor(style_preset)
    drive_db = max_sat_per_pass_db * style_factor

    if pre_in_range and drive_db > IDEMP_DRIVE_MAX_DB:
        drive_db = IDEMP_DRIVE_MAX_DB

    if drive_db < 0.1:
        y_sat = y.copy()
        thd_pct = 0.0
    else:
        y_sat = _apply_pedalboard_saturation(y, sr, drive_db=drive_db)
        thd_pct = estimate_thd_percent(y, y_sat)

        if thd_pct > max_thd_percent:
            scale = max_thd_percent / max(thd_pct, 1e-6)
            new_drive = float(drive_db * scale)

            if new_drive < 0.1:
                drive_db = 0.0
                y_sat = y.copy()
                thd_pct = 0.0
            else:
                drive_db = new_drive
                y_sat = _apply_pedalboard_saturation(y, sr, drive_db=drive_db)
                thd_pct = estimate_thd_percent(y, y_sat)

    post_true_peak_dbtp_raw = compute_true_peak_dbfs(y_sat, oversample_factor=4)
    target_mid = 0.5 * (tp_min + tp_max)
    needed_trim = target_mid - post_true_peak_dbtp_raw

    if pre_in_range:
        max_trim_up_db = IDEMP_TRIM_MAX_DB
        max_trim_down_db = IDEMP_TRIM_MAX_DB
    else:
        max_trim_up_db = 6.0
        max_trim_down_db = 2.0

    if needed_trim >= 0.0:
        trim_db = min(needed_trim, max_trim_up_db)
    else:
        trim_db = max(needed_trim, -max_trim_down_db)

    if abs(trim_db) > 0.05:
        trim_lin = 10.0 ** (trim_db / 20.0)
        y_out = (y_sat * trim_lin).astype(np.float32)
    else:
        trim_db = 0.0
        y_out = y_sat

    y_out = np.clip(y_out, -1.0, 1.0)

    post_true_peak_dbtp = compute_true_peak_dbfs(y_out, oversample_factor=4)
    post_rms_dbfs = compute_rms_dbfs(y_out)

    return y_out, {
        "pre_true_peak_dbtp": float(pre_true_peak_dbtp),
        "pre_rms_dbfs": float(pre_rms_dbfs),
        "post_true_peak_dbtp": float(post_true_peak_dbtp),
        "post_rms_dbfs": float(post_rms_dbfs),
        "drive_db_used": float(drive_db),
        "trim_db_applied": float(trim_db),
        "thd_percent": float(thd_pct),
    }


def process(context: PipelineContext, *args) -> bool:
    """
    IN-MEMORY processing for S8_MIXBUS_COLOR_GENERIC
    """
    contract_id = context.stage_id
    try:
        analysis = load_analysis_with_context(context)
    except FileNotFoundError:
        logger.error(f"[S8_MIXBUS_COLOR_GENERIC] Analysis not found.")
        return False

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}

    style_preset = analysis.get("style_preset", "default")

    tp_min = float(metrics.get("target_true_peak_range_dbtp_min", -4.0))
    tp_max = float(metrics.get("target_true_peak_range_dbtp_max", -2.0))
    max_thd_percent = float(metrics.get("max_thd_percent", 3.0))
    max_sat_per_pass_db = float(
        limits.get("max_additional_saturation_per_pass", 1.0)
    )

    if context.audio_mixdown is None:
        logger.warning("[S8_MIXBUS_COLOR_GENERIC] No mixdown to process.")
        return True

    y_processed, result = _process_mixbus_color_memory(
        context.audio_mixdown,
        context.sample_rate,
        style_preset,
        tp_min,
        tp_max,
        max_thd_percent,
        max_sat_per_pass_db,
    )

    context.audio_mixdown = y_processed

    # Save metrics
    temp_dir = context.get_stage_dir()
    temp_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = temp_dir / "color_metrics_S8_MIXBUS_COLOR_GENERIC.json"

    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "contract_id": contract_id,
                "style_preset": style_preset,
                "target_true_peak_range_dbtp_min": tp_min,
                "target_true_peak_range_dbtp_max": tp_max,
                "max_thd_percent": max_thd_percent,
                "max_additional_saturation_per_pass_db": max_sat_per_pass_db,
                "pre_true_peak_dbtp": result["pre_true_peak_dbtp"],
                "pre_rms_dbfs": result["pre_rms_dbfs"],
                "post_true_peak_dbtp": result["post_true_peak_dbtp"],
                "post_rms_dbfs": result["post_rms_dbfs"],
                "drive_db_used": result["drive_db_used"],
                "trim_db_applied": result["trim_db_applied"],
                "thd_percent": result["thd_percent"],
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
