from utils.logger import logger
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import json
import numpy as np

# Añadir .../src al sys.path
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    from context import PipelineContext
except ImportError:
    PipelineContext = None # type: ignore

from utils.analysis_utils import (
    load_contract,
    get_temp_dir,
)

def analyze_stem_memory(name: str, data: np.ndarray, sr: int, file_path_str: str) -> Dict[str, Any]:
    """
    Analiza un stem desde memoria (numpy array).
    data shape: (samples, channels)
    """
    if data.size == 0:
        dc_per_channel = []
        peak_val = 0.0
    else:
        dc_per_channel = np.mean(data, axis=0).tolist()
        peak_val = float(np.max(np.abs(data)))

    if peak_val > 0.0:
        peak_dbfs = float(20.0 * np.log10(peak_val))
    else:
        peak_dbfs = float("-inf")

    if not dc_per_channel:
        max_dc_abs = 0.0
    else:
        max_dc_abs = 0.0
        for val in dc_per_channel:
            if abs(val) > max_dc_abs:
                max_dc_abs = abs(val)

    eps = 1e-12
    if max_dc_abs < eps:
        dc_db = -120.0
    else:
        dc_db = 20.0 * np.log10(max_dc_abs)

    return {
        "file_name": name,
        "file_path": file_path_str, # Keep logical path for frontend
        "samplerate_hz": sr,
        "dc_offset_linear": dc_per_channel,
        "dc_offset_db": dc_db,
        "peak_dbfs": peak_dbfs,
    }


def process(context: PipelineContext, *args) -> bool:
    """
    Analysis execution using in-memory context.
    """
    contract_id = context.stage_id

    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    stems_analysis: List[Dict[str, Any]] = []
    dc_offsets_db: List[float] = []
    peaks_dbfs: List[float] = []

    # Analyze in-memory stems
    # Sorted keys for determinism
    for name in sorted(context.audio_stems.keys()):
        data = context.audio_stems[name]
        # Construct a logical path for the report to reference
        logical_path = context.get_stage_dir() / name

        res = analyze_stem_memory(name, data, context.sample_rate, str(logical_path))

        stems_analysis.append(res)
        dc_offsets_db.append(res["dc_offset_db"])
        peaks_dbfs.append(res["peak_dbfs"])

    if dc_offsets_db:
        max_dc_offset_db = float(max(dc_offsets_db))
    else:
        max_dc_offset_db = float("-inf")

    if peaks_dbfs:
        max_peak_dbfs = float(max(peaks_dbfs))
    else:
        max_peak_dbfs = float("-inf")

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "dc_offset_max_db_target": metrics.get("dc_offset_max_db"),
            "true_peak_max_dbtp_target": metrics.get("true_peak_max_dbtp"),
            "max_dc_offset_db_measured": max_dc_offset_db,
            "max_peak_dbfs_measured": max_peak_dbfs,
        },
        "stems": stems_analysis,
    }

    # Save Analysis JSON to disk (needed for report generation later)
    temp_dir = context.get_stage_dir()
    temp_dir.mkdir(parents=True, exist_ok=True)

    output_path = temp_dir / f"analysis_{contract_id}.json"
    try:
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(session_state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"[S1_STEM_DC_OFFSET] Failed to save analysis JSON: {e}")
        return False

    return True

def main() -> None:
    logger.error("[S1_STEM_DC_OFFSET] Analysis cannot run standalone in in-memory mode.")
    sys.exit(1)

if __name__ == "__main__":
    main()
