from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

# Ensure src is on sys.path when executed standalone
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from context import PipelineContext
from utils.audio_utils import save_audio_stems, load_audio_stems
from utils.logger import logger as pipeline_logger

# Try importing pedalboard for DSP
try:
    from pedalboard import Pedalboard, Compressor, HighShelfFilter, LowShelfFilter, PeakingFilter, Reverb, Gain
    HAS_PEDALBOARD = True
except ImportError:
    HAS_PEDALBOARD = False


def _normalize_stem_name(value: str) -> str:
    if not value:
        return ""
    name = str(value).strip().lower()
    if not name:
        return ""
    stem = Path(name).stem.replace(" ", "_")
    while "__" in stem:
        stem = stem.replace("__", "_")
    return stem


def _detect_sample_rate(*directories: Path) -> int | None:
    """
    Try to infer the sample rate from the first available WAV file in the
    provided directories. Returns None if it cannot be determined.
    """
    for directory in directories:
        if not directory or not directory.exists():
            continue
        for wav_path in directory.glob("*.wav"):
            if wav_path.name.lower() == "full_song.wav":
                continue
            try:
                return int(sf.info(wav_path).samplerate)
            except Exception:
                continue
    return None


def process(context: PipelineContext, *args) -> bool:
    """
    Applies manual corrections (volume, pan, eq, comp, reverb, mute, solo) to stems.
    Uses pedalboard if available for high quality processing.
    """
    stage_id = "S6_MANUAL_CORRECTION"
    pipeline_logger.log_stage_start(stage_id)

    # 1. Setup directories
    current_dir = context.get_stage_dir(stage_id)
    current_dir.mkdir(parents=True, exist_ok=True)
    s5_dir = context.temp_root / "S5_LEADVOX_DYNAMICS" if context.temp_root else None

    # 2. Load corrections
    work_dir = context.temp_root / "work"
    corrections_path = work_dir / "manual_corrections.json"

    corrections = []
    if corrections_path.exists():
        try:
            with open(corrections_path, 'r') as f:
                data = json.load(f)
                corrections = data.get("corrections", [])
        except Exception as e:
            pipeline_logger.info(f"[{stage_id}] Failed to load corrections: {e}")
            return False

    # 3. Load input stems (prefer cached context; fallback to disk when resuming)
    stems_map = getattr(context, "audio_stems", {}) or {}
    if not stems_map:
        stems_map = load_audio_stems(current_dir)
        if not stems_map:
            pipeline_logger.info(f"[{stage_id}] No stems in memory or {current_dir}. Checking S5...")
            if s5_dir and s5_dir.exists():
                stems_map = load_audio_stems(s5_dir)

            if not stems_map:
                pipeline_logger.info(f"[{stage_id}] No input stems found.")
                return False

    # 4. Apply corrections
    corr_map = {}
    for corr in corrections:
        key = _normalize_stem_name(corr.get("name", ""))
        if key:
            corr_map[key] = corr
    any_solo = any(c.get('solo', False) for c in corrections)

    processed_stems = {}
    sr = getattr(context, "sample_rate", None)
    if sr is None:
        sr = _detect_sample_rate(current_dir, s5_dir)
    if sr is None:
        sr = 48000
        pipeline_logger.info(f"[{stage_id}] sample_rate not found; defaulting to {sr} Hz.")
    context.sample_rate = sr

    for name, audio in stems_map.items():
        # Audio is (channels, samples) float32 numpy array

        corr = corr_map.get(_normalize_stem_name(name))
        if not corr:
            processed_stems[name] = audio
            continue

        # Mute / Solo logic
        is_muted = corr.get('mute', False)
        is_solo = corr.get('solo', False)

        if is_muted or (any_solo and not is_solo):
            processed_stems[name] = np.zeros_like(audio)
            continue

        # If we have pedalboard, we build a chain
        if HAS_PEDALBOARD:
            board = Pedalboard()

            # EQ
            # Frontend sends: eq: { low, mid, high, enabled }
            eq_cfg = corr.get('eq')
            if eq_cfg and eq_cfg.get('enabled'):
                # Simple 3-band EQ mapping
                # Low Shelf (100Hz?)
                if eq_cfg.get('low') != 0:
                    board.append(LowShelfFilter(cutoff_frequency_hz=100, gain_db=eq_cfg['low']))

                # Peaking (1kHz?)
                if eq_cfg.get('mid') != 0:
                    board.append(PeakingFilter(cutoff_frequency_hz=1000, gain_db=eq_cfg['mid'], q=1.0))

                # High Shelf (5kHz?)
                if eq_cfg.get('high') != 0:
                    board.append(HighShelfFilter(cutoff_frequency_hz=5000, gain_db=eq_cfg['high']))

            # Compression
            # Frontend sends: compression: { threshold, ratio, enabled }
            comp_cfg = corr.get('compression')
            if comp_cfg and comp_cfg.get('enabled'):
                board.append(Compressor(
                    threshold_db=comp_cfg.get('threshold', -20),
                    ratio=comp_cfg.get('ratio', 2),
                    attack_ms=10,
                    release_ms=100
                ))

            # Reverb
            # Frontend sends: reverb: { amount (0-100), enabled }
            verb_cfg = corr.get('reverb')
            if verb_cfg and verb_cfg.get('enabled'):
                amt = verb_cfg.get('amount', 0) / 100.0
                if amt > 0:
                    board.append(Reverb(room_size=0.5, wet_level=amt, dry_level=1.0-amt*0.5))

            # Volume / Pan
            # Pedalboard doesn't have a simple "Pan" plugin in standard set?
            # Usually we handle pan by modifying gain of channels manually or using Gain(gain_db).
            # Gain plugin applies to all channels.

            # Apply Volume first via Gain plugin?
            vol_db = corr.get('volume_db', 0.0)
            if vol_db != 0:
                board.append(Gain(gain_db=vol_db))

            # Run the chain
            # Pedalboard expects (channels, samples)
            processed = board(audio, sr)

            # Apply Pan manually after processing (simple linear/power pan)
            pan = corr.get('pan', 0.0)
            if pan != 0.0 and processed.shape[0] == 2:
                # Standard equal-power or linear
                # Using linear for simplicity and robustness
                l_gain = 1.0 if pan <= 0 else (1.0 - pan)
                r_gain = 1.0 if pan >= 0 else (1.0 + pan)
                processed[0] *= l_gain
                processed[1] *= r_gain

            processed_stems[name] = processed

        else:
            # Fallback if no pedalboard (Volume/Pan only)
            pipeline_logger.info(f"[{stage_id}] Pedalboard not installed. Applying Volume/Pan only.")
            vol_db = corr.get('volume_db', 0.0)
            pan = corr.get('pan', 0.0)

            processed = audio * (10 ** (vol_db / 20.0))
            if pan != 0.0 and processed.shape[0] == 2:
                l_gain = 1.0 if pan <= 0 else (1.0 - pan)
                r_gain = 1.0 if pan >= 0 else (1.0 + pan)
                processed[0] *= l_gain
                processed[1] *= r_gain

            processed_stems[name] = processed

    # 5. Save results
    context.audio_stems = processed_stems
    save_audio_stems(current_dir, processed_stems, sr)

    pipeline_logger.log_stage_success(stage_id)
    return True
