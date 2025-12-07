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
from utils.tonal_balance_utils import (
    get_freq_bands,
    compute_band_energies,
    get_style_tonal_profile,
    compute_tonal_error,
)
try:
    from context import PipelineContext
except ImportError:
    PipelineContext = None # type: ignore


def _analyze_mixbus_memory(context: PipelineContext) -> Dict[str, Any]:
    """
    Analiza context.audio_mixdown
    """
    if context.audio_mixdown is None:
        return {
            "band_current_db": None,
            "sr_mix": None,
            "error": "[S7_MIXBUS_TONAL_BALANCE] No mixdown in memory.",
        }

    y = context.audio_mixdown
    # Check if stereo/mono
    # compute_band_energies expects always_2d?
    # It takes (N, C) or (N,).

    sr = context.sample_rate

    band_current_db = compute_band_energies(y, sr)
    return {
        "band_current_db": band_current_db,
        "sr_mix": sr,
        "error": None,
    }


def process(context: PipelineContext, *args) -> bool:
    """
    IN-MEMORY analysis for S7_MIXBUS_TONAL_BALANCE
    """
    contract_id = context.stage_id

    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    max_tonal_error_db = float(metrics.get("max_tonal_balance_error_db", 3.0))
    max_eq_change_db = float(limits.get("max_eq_change_db_per_band_per_pass", 1.5))

    try:
        cfg = load_session_config_memory(context, contract_id)
    except Exception:
        cfg = {"style_preset": "Unknown"}

    style_preset = cfg.get("style_preset", "Unknown")

    freq_bands = get_freq_bands()
    style_profile = get_style_tonal_profile(style_preset)

    result = _analyze_mixbus_memory(context)

    if result["error"] is not None:
        logger.info(result["error"])
        band_current_db = {b["id"]: float("-inf") for b in freq_bands}
        band_target_db = style_profile
        band_error_db = {}
        error_rms_db = 0.0
        sr_mix = None
    else:
        sr_mix = result["sr_mix"]
        band_current_db = result["band_current_db"]
        band_target_db = style_profile
        band_error_db, error_rms_db = compute_tonal_error(
            band_current_db, band_target_db
        )
        logger.info(
            f"[S7_MIXBUS_TONAL_BALANCE] In-memory mixbus analysis (sr={sr_mix}). "
            f"error_RMS={error_rms_db:.2f} dB."
        )

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "samplerate_hz": sr_mix,
            "max_tonal_balance_error_db": max_tonal_error_db,
            "max_eq_change_db_per_band_per_pass": max_eq_change_db,
            "tonal_bands": {
                "bands": freq_bands,
                "current_band_db": band_current_db,
                "target_band_db": band_target_db,
                "error_by_band_db": band_error_db,
                "error_rms_db": error_rms_db,
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
        logger.error(f"[S7_MIXBUS_TONAL_BALANCE] Failed to save analysis JSON: {e}")
        return False

    return True

def main() -> None:
    pass

if __name__ == "__main__":
    main()
