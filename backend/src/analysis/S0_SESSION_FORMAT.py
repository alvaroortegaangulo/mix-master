from utils.logger import logger
import sys
from pathlib import Path
from typing import Dict, Any, List
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
    compute_peak_dbfs,
)
from utils.session_utils import (
    load_session_config_memory,
    infer_bus_target,
)


def analyze_stem_memory(name: str, data: np.ndarray, sr: int, logical_path: str) -> Dict[str, Any]:
    """
    Analiza un stem en memoria.
    """
    if data.ndim > 1:
        mono = np.mean(data, axis=1)
    else:
        mono = data

    duration_sec = len(mono) / float(sr) if len(mono) > 0 else 0.0

    peak_dbfs = compute_peak_dbfs(mono)
    peak_linear = float(np.max(np.abs(mono))) if mono.size > 0 else 0.0

    silence_threshold = 10 ** (-60.0 / 20.0)
    non_silent_indices = np.where(np.abs(mono) > silence_threshold)[0]
    if non_silent_indices.size > 0:
        start_idx = int(non_silent_indices[0])
        end_idx = int(non_silent_indices[-1])
        start_time_sec = start_idx / float(sr)
        end_time_sec = end_idx / float(sr)
        silence_head_sec = start_time_sec
        silence_tail_sec = duration_sec - end_time_sec
    else:
        start_time_sec = 0.0
        end_time_sec = 0.0
        silence_head_sec = duration_sec
        silence_tail_sec = 0.0

    channels = data.shape[1] if data.ndim > 1 else 1

    # Internal bit depth is always float32 (32-bit float)
    bit_depth_file = 32

    return {
        "file_name": name,
        "file_path": logical_path,
        "samplerate_hz": sr,
        "channels": channels,
        "bit_depth_file": bit_depth_file,
        "duration_sec": duration_sec,
        "peak_linear": peak_linear,
        "peak_dbfs": peak_dbfs,
        "start_time_sec": start_time_sec,
        "end_time_sec": end_time_sec,
        "silence_head_sec": silence_head_sec,
        "silence_tail_sec": silence_tail_sec,
    }


def process(context: PipelineContext, *args) -> bool:
    """
    IN-MEMORY analysis for S0_SESSION_FORMAT
    """
    contract_id = context.stage_id
    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    # Load session config from memory (metadata in context)
    # We added context.metadata["session_config"] in pipeline.py
    cfg = context.metadata.get("session_config")

    if not cfg:
        # Fallback to loading from file if not in metadata (e.g. legacy or not propagated)
        try:
             cfg = load_session_config_memory(context, contract_id)
        except Exception as e:
            logger.warning(f"Could not load session config: {e}. Using defaults.")
            cfg = {"style_preset": "Unknown", "instrument_by_file": {}}

    style_preset = cfg.get("style_preset", "Unknown")

    # instrument_by_file logic
    # The config structure in metadata is:
    # { "stems": [ {"file_name": "...", "instrument_profile": "..."}, ... ] }
    # We need to build the map.
    instrument_by_file = {}
    if "stems" in cfg and isinstance(cfg["stems"], list):
        for s in cfg["stems"]:
             instrument_by_file[s.get("file_name")] = s.get("instrument_profile")
    elif "instrument_by_file" in cfg: # Legacy direct map
        instrument_by_file = cfg["instrument_by_file"]


    stems_analysis: List[Dict[str, Any]] = []
    session_max_peak_dbfs = float("-inf")
    samplerates_present = set()

    # Analyze memory
    for name in sorted(context.audio_stems.keys()):
        data = context.audio_stems[name]
        logical_path = str(context.get_stage_dir() / name)

        stem_info = analyze_stem_memory(name, data, context.sample_rate, logical_path)

        requested_profile = instrument_by_file.get(name, "Other")
        if str(requested_profile).lower() == "auto":
            resolved_profile = "Other"
        else:
            resolved_profile = requested_profile

        bus_target = infer_bus_target(resolved_profile)

        stem_info["instrument_profile_requested"] = requested_profile
        stem_info["instrument_profile_resolved"] = resolved_profile
        stem_info["bus_target"] = bus_target

        stems_analysis.append(stem_info)

        samplerates_present.add(stem_info["samplerate_hz"])
        peak_dbfs = stem_info["peak_dbfs"]
        if peak_dbfs > session_max_peak_dbfs:
            session_max_peak_dbfs = peak_dbfs

    # Build Session State
    buses: Dict[str, Dict[str, Any]] = {}
    for stem in stems_analysis:
        bus = stem["bus_target"]
        if bus not in buses:
            buses[bus] = {
                "bus_id": bus,
                "stems": []
            }
        buses[bus]["stems"].append(stem["file_name"])

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "samplerate_hz_target": metrics.get("samplerate_hz"),
            "bit_depth_internal_target": metrics.get("bit_depth_internal"),
            "max_peak_dbfs_target": metrics.get("max_peak_dbfs"),
            "samplerates_present": sorted(list(samplerates_present)),
            "session_max_peak_dbfs": session_max_peak_dbfs,
        },
        "stems": stems_analysis,
        "buses": list(buses.values()),
    }

    # Save Analysis JSON
    temp_dir = context.get_stage_dir()
    temp_dir.mkdir(parents=True, exist_ok=True)
    output_path = temp_dir / f"analysis_{contract_id}.json"

    try:
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(session_state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"[S0_SESSION_FORMAT] Failed to save analysis JSON: {e}")
        return False

    return True

def main() -> None:
    pass

if __name__ == "__main__":
    main()
