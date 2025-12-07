from utils.logger import logger
import sys
from pathlib import Path
from typing import Dict, Any, List
import json
import numpy as np

# --- hack para poder importar utils cuando se ejecuta como script ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    from context import PipelineContext
except ImportError:
    PipelineContext = None # type: ignore

from utils.analysis_utils import (
    load_contract,
    get_temp_dir,
    compute_peak_dbfs,
    compute_integrated_loudness_lufs,
)
from utils.session_utils import (
    load_session_config_memory,
    infer_bus_target,
)


def analyze_stem_memory(name: str, data: np.ndarray, sr: int, logical_path: str) -> Dict[str, Any]:
    if data.ndim > 1:
        mono = np.mean(data, axis=1)
    else:
        mono = data

    integrated_lufs = compute_integrated_loudness_lufs(mono, sr)
    true_peak_dbfs = compute_peak_dbfs(mono)

    return {
        "file_name": name,
        "file_path": logical_path,
        "samplerate_hz": sr,
        "integrated_lufs": integrated_lufs,
        "true_peak_dbfs": true_peak_dbfs,
    }


def compute_mixbus_peak_memory(context: PipelineContext) -> float:
    # Use pre-calculated mixdown if available and valid?
    # No, we want peak of sum of CURRENT stems.
    # context.audio_mixdown might be stale if we modified stems?
    # Actually, mixdown_stems.py runs before analysis in stage.py...
    # Wait, stage.py runs mixdown -> pre-analysis -> stage -> post-analysis -> mixdown.
    # So context.audio_mixdown SHOULD be up to date.

    if context.audio_mixdown is None:
        return float("-inf")

    peak = float(np.max(np.abs(context.audio_mixdown)))
    if peak <= 0.0:
        return float("-inf")
    return float(20.0 * np.log10(peak))


def process(context: PipelineContext, *args) -> bool:
    """
    IN-MEMORY analysis for S1_STEM_WORKING_LOUDNESS
    """
    contract_id = context.stage_id
    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    # Load config
    try:
        cfg = load_session_config_memory(context, contract_id)
    except Exception:
        cfg = {"style_preset": "Unknown", "instrument_by_file": {}}

    style_preset = cfg.get("style_preset", "Unknown")

    instrument_by_file = {}
    if "stems" in cfg and isinstance(cfg["stems"], list):
        for s in cfg["stems"]:
             instrument_by_file[s.get("file_name")] = s.get("instrument_profile")
    elif "instrument_by_file" in cfg:
        instrument_by_file = cfg["instrument_by_file"]

    stems_analysis: List[Dict[str, Any]] = []
    lufs_values: List[float] = []
    true_peaks_values: List[float] = []

    for name in sorted(context.audio_stems.keys()):
        data = context.audio_stems[name]
        logical_path = str(context.get_stage_dir() / name)

        stem_info = analyze_stem_memory(name, data, context.sample_rate, logical_path)

        requested_profile = instrument_by_file.get(name, "Other")
        if str(requested_profile).lower() == "auto":
             resolved_profile = "Other"
        else:
             resolved_profile = requested_profile

        stem_info["instrument_profile_requested"] = requested_profile
        stem_info["instrument_profile_resolved"] = resolved_profile
        stem_info["bus_target"] = infer_bus_target(resolved_profile)

        stems_analysis.append(stem_info)
        lufs_values.append(stem_info["integrated_lufs"])
        true_peaks_values.append(stem_info["true_peak_dbfs"])

    mixbus_peak_dbfs_measured = compute_mixbus_peak_memory(context)

    if true_peaks_values:
        max_true_peak_dbfs = float(max(true_peaks_values))
    else:
        max_true_peak_dbfs = float("-inf")

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "true_peak_per_stem_target_max_dbtp": -3.0,
            "mixbus_peak_target_max_dbfs": -6.0,
            "max_true_peak_dbfs_measured": max_true_peak_dbfs,
            "mixbus_peak_dbfs_measured": mixbus_peak_dbfs_measured,
        },
        "stems": stems_analysis,
    }

    # Save Analysis JSON
    temp_dir = context.get_stage_dir()
    temp_dir.mkdir(parents=True, exist_ok=True)
    output_path = temp_dir / f"analysis_{contract_id}.json"

    try:
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(session_state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"[S1_STEM_WORKING_LOUDNESS] Failed to save analysis JSON: {e}")
        return False

    return True

def main() -> None:
    pass

if __name__ == "__main__":
    main()
