from typing import Dict, Any
from pathlib import Path
import json
from context import PipelineContext

def load_session_config(stage_id: str) -> Dict[str, Any]:
    """
    Legacy file-based loader
    """
    from utils.analysis_utils import get_temp_dir
    temp_dir = get_temp_dir(stage_id, create=False)
    config_path = temp_dir / "session_config.json"
    if not config_path.exists():
        # Fallback or empty
        return {"style_preset": "Unknown", "instrument_by_file": {}}

    with config_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # Flatten stems to instrument_by_file map
    stems = data.get("stems", [])
    instrument_by_file = {}
    for s in stems:
        instrument_by_file[s.get("file_name")] = s.get("instrument_profile")

    data["instrument_by_file"] = instrument_by_file
    return data

def load_session_config_memory(context: PipelineContext, stage_id: str) -> Dict[str, Any]:
    """
    Tries to load session config from context metadata or falls back to disk.
    """
    if "session_config" in context.metadata:
        data = context.metadata["session_config"]
        # Flatten logic needed here too?
        # Yes, analysis scripts expect 'instrument_by_file'
        stems = data.get("stems", [])
        instrument_by_file = {}
        for s in stems:
             instrument_by_file[s.get("file_name")] = s.get("instrument_profile")
        data["instrument_by_file"] = instrument_by_file
        return data

    return load_session_config(stage_id)

def infer_bus_target(instrument_profile: str) -> str:
    """
    Simula la lógica de ruteo: Drums, Bass, Vocals, Instruments, Keys, FX...
    """
    prof = instrument_profile.lower()
    if "kick" in prof or "snare" in prof or "hat" in prof or "tom" in prof or "cymbal" in prof or "drum" in prof or "overhead" in prof or "room" in prof:
        return "Drums"
    if "bass" in prof or "808" in prof:
        return "Bass"
    if "vocal" in prof or "vox" in prof or "lead" in prof or "bgv" in prof:
        return "Vocals"
    if "synth" in prof or "key" in prof or "piano" in prof or "pad" in prof:
        return "Keys"
    if "guitar" in prof or "gtr" in prof:
        return "Guitars"
    if "fx" in prof or "sweeps" in prof or "noise" in prof:
        return "FX"

    return "Instruments"
