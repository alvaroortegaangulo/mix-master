from __future__ import annotations

import logging
import json
import numpy as np
import soundfile as sf
from pathlib import Path
from typing import Dict, Any, List

from ..context import PipelineContext
from ..utils.logger import PipelineLogger
from ..utils.audio_utils import save_audio_stems, load_audio_stems

# Try importing pedalboard for DSP
try:
    from pedalboard import Pedalboard, Compressor, HighShelfFilter, LowShelfFilter, PeakingFilter, Reverb, Gain
    from pedalboard.io import AudioFile
    HAS_PEDALBOARD = True
except ImportError:
    HAS_PEDALBOARD = False

logger = logging.getLogger(__name__)

def process(context: PipelineContext) -> bool:
    """
    Applies manual corrections (volume, pan, eq, comp, reverb, mute, solo) to stems.
    Uses pedalboard if available for high quality processing.
    """
    stage_id = "S6_MANUAL_CORRECTION"
    # PipelineLogger is a class, not an instance in this scope, but logger.py exports `logger` instance.
    # We should use `logger.log_stage_start(stage_id)`.
    # But `logger` here is `logging.getLogger(__name__)`.
    # Let's import the global logger instance as `pipeline_logger`.
    from ..utils.logger import logger as pipeline_logger

    pipeline_logger.log_stage_start(stage_id)

    # 1. Setup directories
    current_dir = context.get_stage_dir(stage_id)
    current_dir.mkdir(parents=True, exist_ok=True)

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

    # 3. Load input stems
    # Ensure inputs are available. If pipeline was paused, stems should be in S5 output or similar.
    # The pipeline architecture usually copies previous stage output to current stage dir before running.
    # So we check current_dir for inputs.

    # However, since we might be resuming, the `copy_stems` might have run before the pause?
    # Or `run_pipeline_for_job` re-runs copy logic.
    # We will assume stems are in `current_dir` (copied from S5) OR we check context.

    stems_map = context.audio_stems
    if not stems_map:
        stems_map = load_audio_stems(current_dir)
        if not stems_map:
             # Fallback: Check S5 directory if S6 dir is empty (maybe copy didn't happen on resume?)
             # In standard pipeline, `run_stage` calls `_run_script(copy_script)` at the END of previous stage.
             # If we paused, copy might have happened.
             # Let's try loading from S6 dir. If empty, fail/warn.
             pipeline_logger.info(f"[{stage_id}] No stems in memory or {current_dir}. Checking S5...")
             s5_dir = context.temp_root / "S5_LEADVOX_DYNAMICS" # Assuming this is the predecessor
             if s5_dir.exists():
                 stems_map = load_audio_stems(s5_dir)

             if not stems_map:
                  pipeline_logger.info(f"[{stage_id}] No input stems found.")
                  return False

    # 4. Apply corrections
    corr_map = {c['name']: c for c in corrections}
    any_solo = any(c.get('solo', False) for c in corrections)

    processed_stems = {}
    sr = context.sample_rate

    for name, audio in stems_map.items():
        # Audio is (channels, samples) float32 numpy array

        corr = corr_map.get(name)
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
