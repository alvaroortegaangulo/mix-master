from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any, List
import json
import numpy as np

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    from context import PipelineContext
except ImportError:
    PipelineContext = None # type: ignore

from utils.analysis_utils import get_temp_dir
from utils.profiles_utils import get_instrument_profile


def load_analysis(context: PipelineContext, contract_id: str) -> Dict[str, Any]:
    if context.temp_root:
        temp_dir = context.temp_root / contract_id
    else:
        temp_dir = get_temp_dir(contract_id, create=False)

    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def compute_gain_db_for_stem(
    stem_info: Dict[str, Any],
    true_peak_target_dbtp: float | None,
    max_gain_change_db_per_pass: float | None,
) -> float:
    inst_profile_id = stem_info.get("instrument_profile_resolved", "Other")
    profile = get_instrument_profile(inst_profile_id)
    lufs_range = profile.get("work_loudness_lufs_range")

    integrated_lufs = stem_info.get("integrated_lufs")
    measured_peak_dbfs = stem_info.get("true_peak_dbfs")

    if integrated_lufs is None or integrated_lufs == float("-inf"):
        return 0.0
    if measured_peak_dbfs is None or measured_peak_dbfs == float("-inf"):
        measured_peak_dbfs = -120.0

    if not isinstance(lufs_range, list) or len(lufs_range) != 2:
        return 0.0

    target_min, target_max = float(lufs_range[0]), float(lufs_range[1])
    target_lufs = 0.5 * (target_min + target_max)

    gain_db = target_lufs - float(integrated_lufs)

    if max_gain_change_db_per_pass is not None:
        max_gain = float(max_gain_change_db_per_pass)
        if gain_db > max_gain:
            gain_db = max_gain
        elif gain_db < -max_gain:
            gain_db = -max_gain

    if abs(gain_db) < 0.1:
        return 0.0

    return gain_db


def process(context: PipelineContext, *args) -> bool:
    """
    IN-MEMORY processing for S1_STEM_WORKING_LOUDNESS
    """
    contract_id = context.stage_id
    try:
        analysis = load_analysis(context, contract_id)
    except FileNotFoundError:
        logger.error(f"[S1_STEM_WORKING_LOUDNESS] Analysis not found for {contract_id}")
        return False

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {})
    session_metrics: Dict[str, Any] = analysis.get("session", {})
    stems_info: List[Dict[str, Any]] = analysis.get("stems", [])

    true_peak_target_dbtp = session_metrics.get("true_peak_per_stem_target_max_dbtp", -3.0)
    max_gain_change_db_per_pass = metrics.get("max_gain_change_db_per_pass", None)

    processed_count = 0
    for stem_info in stems_info:
        file_name = Path(stem_info["file_path"]).name
        if file_name not in context.audio_stems:
            continue

        gain_db = compute_gain_db_for_stem(
            stem_info,
            true_peak_target_dbtp=true_peak_target_dbtp,
            max_gain_change_db_per_pass=max_gain_change_db_per_pass,
        )

        if gain_db != 0.0:
            data = context.audio_stems[file_name]
            scale = 10.0 ** (gain_db / 20.0)
            data *= scale
            processed_count += 1
            # context.audio_stems is updated in-place due to numpy reference or we reassign?
            # numpy operations like *= are in-place.

    logger.info(f"[S1_STEM_WORKING_LOUDNESS] Applied loudness gain to {processed_count} stems.")
    return True

def main() -> None:
    pass

if __name__ == "__main__":
    main()
