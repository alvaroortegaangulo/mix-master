# C:\mix-master\backend\src\utils\session_utils.py

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any

from .analysis_utils import get_temp_dir


def load_session_config(contract_id: str) -> Dict[str, Any]:
    """
    Lee temp[/<MIX_JOB_ID>]/<contract_id>/session_config.json si existe.

    Devuelve:
      - style_preset: str
      - instrument_by_file: dict[file_name -> instrument_profile]

    Comportamiento:
      - Modo CLI (single-job):
          PROJECT_ROOT/temp/<contract_id>/session_config.json
      - Modo multi-job (Celery, con MIX_JOB_ID/MIX_TEMP_ROOT):
          PROJECT_ROOT/temp/<MIX_JOB_ID>/<contract_id>/session_config.json
          o MIX_TEMP_ROOT/<contract_id>/session_config.json
    """
    # No forzamos create=True: si no existe la carpeta, simplemente no hay config.
    temp_dir: Path = get_temp_dir(contract_id, create=False)
    config_path = temp_dir / "session_config.json"

    style_preset = "Unknown"
    instrument_by_file: Dict[str, str] = {}

    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            cfg = json.load(f)

        style_preset = cfg.get("style_preset", "Unknown")

        for stem in cfg.get("stems", []):
            if not isinstance(stem, dict):
                continue
            fname = stem.get("file_name")
            prof = stem.get("instrument_profile", "Other")
            if fname:
                instrument_by_file[str(fname)] = str(prof)

    return {
        "style_preset": style_preset,
        "instrument_by_file": instrument_by_file,
    }


def infer_bus_target(instrument_profile: str) -> str:
    """
    Mapea instrument_profile a bus_target.
    """
    mapping = {
        "Kick": "Bus_Drums",
        "Snare": "Bus_Drums",
        "Percussion": "Bus_Perc",
        "Bass_Electric": "Bus_Bass",
        "Bass_Synth_808": "Bus_Bass",
        "Acoustic_Guitar": "Bus_Guitars",
        "Electric_Guitar_Rhythm": "Bus_Guitars",
        "Electric_Guitar_Lead": "Bus_Guitars",
        "Keys_Piano": "Bus_Keys_Synths",
        "Synth_Pads": "Bus_Keys_Synths",
        "Synth_Lead_Arp": "Bus_Keys_Synths",
        "Lead_Vocal_Melodic": "Bus_LeadVox",
        "Lead_Vocal_Rap": "Bus_LeadVox",
        "Backing_Vocals": "Bus_BGV",
        "Vocal_Adlibs_Shouts": "Bus_BGV",
        "Choir_Group": "Bus_BGV",
        "FX_EarCandy": "Bus_FX",
        "Ambience_Atmos": "Bus_Ambience",
        "Other": "Bus_Other",
    }
    return mapping.get(instrument_profile, "Bus_Other")
