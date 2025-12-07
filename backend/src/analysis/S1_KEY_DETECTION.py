from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any, List
import numpy as np
import essentia.standard as es

# --- hack para poder importar utils cuando se ejecuta como script suelto ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# PipelineContext import (handled by stage.py or local import if needed)
try:
    from context import PipelineContext
except ImportError:
    pass # Assume it's available in runtime namespace or imported

from utils.analysis_utils import load_contract

_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

def _detect_key_from_mix(y: np.ndarray, sr: int) -> Dict[str, Any]:
    if y.size == 0:
        return {"key_root_pc": None, "key_mode": None, "key_name": None, "confidence": None}

    audio = np.asarray(y, dtype=np.float32).flatten()
    target_sr = 44100
    if sr != target_sr:
        resample = es.Resample(inputSampleRate=float(sr), outputSampleRate=float(target_sr))
        audio = resample(audio)
        sr = target_sr

    key_extractor = es.KeyExtractor()
    key_str, scale_str, strength = key_extractor(audio)

    key_str = str(key_str or "").strip()
    scale_str = str(scale_str or "").strip().lower()

    key_root_pc = None
    if key_str in _NOTE_NAMES:
        key_root_pc = int(_NOTE_NAMES.index(key_str))

    key_mode = scale_str if scale_str in ("major", "minor") else None
    key_name = f"{_NOTE_NAMES[key_root_pc]} {key_mode}" if key_root_pc is not None and key_mode is not None else None
    confidence = float(strength) if strength is not None else 0.0
    confidence = max(0.0, min(1.0, confidence))

    return {
        "key_root_pc": key_root_pc,
        "key_mode": key_mode,
        "key_name": key_name,
        "confidence": confidence,
    }

def _build_scale_degrees_midi(key_root_pc: int, key_mode: str) -> List[int]:
    pattern = [0, 2, 3, 5, 7, 8, 10] if key_mode == "minor" else [0, 2, 4, 5, 7, 9, 11]
    return [int((key_root_pc + step) % 12) for step in pattern]

def process(context: PipelineContext, contract_id: str) -> bool:
    logger.logger.info(f"[{contract_id}] Starting analysis in-memory...")

    # 1. Load Contract/Config (from memory/context if needed, or static file)
    # contracts are static.
    contract = load_contract(contract_id)
    metrics = contract.get("metrics", {})
    limits = contract.get("limits", {})
    stage_id = contract.get("stage_id")

    session_config = context.metadata.get("session_config", {})
    style_preset = session_config.get("style_preset", "Unknown")

    # Build instrument map
    instrument_by_file = {}
    for item in session_config.get("stems", []):
        instrument_by_file[item["file_name"]] = item["instrument_profile"]

    # 2. Mix Stems to Mono
    mix = np.zeros(1, dtype=np.float32)
    sr = context.sample_rate
    first = True

    # We iterate over context.audio_stems
    # Exclude full_song if present in stems (usually not, it's in audio_mixdown)

    for name, stem in context.audio_stems.items():
        if name.lower() == "full_song.wav": continue

        # Convert to mono
        if stem.ndim > 1:
             mono = np.mean(stem, axis=1)
        else:
             mono = stem

        if first:
            mix = np.zeros_like(mono)
            first = False

        # Simple addition (assuming aligned)
        if len(mono) == len(mix):
            mix += mono
        elif len(mono) < len(mix):
            mix[:len(mono)] += mono
        else:
            # Resize mix?
            new_mix = np.zeros_like(mono)
            new_mix[:len(mix)] = mix
            mix = new_mix
            mix += mono

    # Normalize
    peak = float(np.max(np.abs(mix))) if mix.size > 0 else 0.0
    if peak > 0.0: mix /= peak

    # 3. Detect Key
    key_info = _detect_key_from_mix(mix, sr)

    key_root_pc = key_info["key_root_pc"]
    key_mode = key_info["key_mode"]
    scale_pcs = _build_scale_degrees_midi(key_root_pc, key_mode) if key_root_pc is not None and key_mode is not None else None

    # 4. Build Result
    stems_info = []
    for name in sorted(context.audio_stems.keys()):
        inst_profile = instrument_by_file.get(name, "Other")
        stems_info.append({
            "file_name": name,
            "file_path": "memory",
            "instrument_profile": inst_profile,
        })

    session_state = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "key_root_pc": key_root_pc,
            "key_mode": key_mode,
            "key_name": key_info["key_name"],
            "key_detection_confidence": key_info["confidence"],
            "scale_pitch_classes": scale_pcs,
        },
        "stems": stems_info,
    }

    context.analysis_results[contract_id] = session_state

    logger.logger.info(f"[{contract_id}] Analysis complete. Key: {key_info['key_name']}")
    return True
