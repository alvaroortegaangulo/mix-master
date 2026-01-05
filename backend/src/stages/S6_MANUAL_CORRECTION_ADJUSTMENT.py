from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import soundfile as sf

# Pedalboard imports for effects
try:
    from pedalboard import (
        Pedalboard,
        Compressor,
        HighShelfFilter,
        LowShelfFilter,
        PeakingFilter,
        Reverb,
        Gain,
    )
    HAS_PEDALBOARD = True
except ImportError:  # pragma: no cover
    HAS_PEDALBOARD = False

# --- hack sys.path ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.logger import logger

try:
    from context import PipelineContext
except ImportError:  # pragma: no cover
    PipelineContext = None  # type: ignore


STAGE_ID = "S6_MANUAL_CORRECTION_ADJUSTMENT"


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


def _clamp(x: float, lo: float, hi: float) -> float:
    return float(min(hi, max(lo, x)))


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"1", "true", "yes", "y", "on"}:
            return True
        if v in {"0", "false", "no", "n", "off"}:
            return False
    return default


def _apply_simple_reverb(audio: np.ndarray, sr: int, amount: float) -> np.ndarray:
    """
    Simple delay-tap reverb for fallback path (no pedalboard).

    Expects audio in (samples, channels).
    amount in [0..1].
    """
    amount = _clamp(amount, 0.0, 1.0)
    if amount <= 0:
        return audio

    delays_sec = [0.03, 0.05, 0.08, 0.11]
    gains = [0.5, 0.35, 0.25, 0.2]
    wet = audio.copy()

    n_samples = wet.shape[0]
    for delay_sec, gain in zip(delays_sec, gains):
        delay = int(sr * delay_sec)
        if delay <= 0 or delay >= n_samples:
            continue
        wet[delay:, :] += audio[:-delay, :] * (gain * amount)

    dry_gain = 1.0 - min(0.5, amount * 0.5)
    wet_gain = amount
    mixed = (audio * dry_gain) + (wet * wet_gain)

    peak = float(np.max(np.abs(mixed))) if mixed.size else 0.0
    if peak > 1.0:
        mixed = mixed / peak

    return mixed.astype(np.float32, copy=False)


def _load_corrections(stage_dir: Path) -> List[Dict[str, Any]]:
    """
    Reads <stage_dir>/changes.json

    Accepts:
      - [ { ... }, ... ]
      - { "corrections": [ ... ] }
    """
    json_path = stage_dir / "changes.json"
    if not json_path.exists():
        logger.logger.warning(f"[{STAGE_ID}] No changes.json found in {stage_dir}")
        return []

    try:
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return [c for c in data if isinstance(c, dict)]
            if isinstance(data, dict) and isinstance(data.get("corrections"), list):
                return [c for c in data["corrections"] if isinstance(c, dict)]
            return []
    except Exception as e:
        logger.logger.error(f"[{STAGE_ID}] Error reading changes.json: {e}")
        return []


def process(context: "PipelineContext", *args) -> bool:
    """
    S6_MANUAL_CORRECTION_ADJUSTMENT:
      1) Reads changes.json in this stage folder.
      2) Finds the best available stems source (prioritize S6_MANUAL_CORRECTION -> S11 -> S10 -> S0).
      3) Applies EQ/Comp/Reverb/Gain/Pan/Mute/Solo.
      4) Writes processed stems into this stage folder.

    This stage is not part of the default contracts sequence, but the API may
    serve stems from it if the folder exists.
    """
    stage_dir = context.get_stage_dir(STAGE_ID)
    stage_dir.mkdir(parents=True, exist_ok=True)

    temp_root = getattr(context, "temp_root", None)
    if not temp_root:
        logger.logger.error(f"[{STAGE_ID}] temp_root missing in PipelineContext")
        return False

    # 1) Corrections
    corrections = _load_corrections(stage_dir)
    if not corrections:
        logger.logger.info(f"[{STAGE_ID}] No corrections defined. No-op.")
        return True

    if not HAS_PEDALBOARD:
        logger.logger.info(f"[{STAGE_ID}] Pedalboard not installed. Using fallback processing.")

    # 2) Source stems
    candidate_sources = [
        Path(temp_root) / "S6_MANUAL_CORRECTION",
        Path(temp_root) / "S11_REPORT_GENERATION",
        Path(temp_root) / "S10_MASTER_FINAL_LIMITS",
        Path(temp_root) / "S0_SESSION_FORMAT",
        Path(temp_root) / "S0_MIX_ORIGINAL",
    ]

    source_dir: Optional[Path] = None
    for cand in candidate_sources:
        if cand.exists():
            stems_here = [p for p in cand.glob("*.wav") if p.name.lower() != "full_song.wav"]
            if stems_here:
                source_dir = cand
                break

    if source_dir is None:
        logger.logger.error(f"[{STAGE_ID}] No source stems found in {temp_root}")
        return False

    # Map corrections by normalized stem name
    corr_map: Dict[str, Dict[str, Any]] = {}
    for corr in corrections:
        key = _normalize_stem_name(corr.get("name", ""))
        if key:
            corr_map[key] = corr

    solo_active = any(_as_bool(c.get("solo", False)) for c in corrections)

    logger.logger.info(
        f"[{STAGE_ID}] Source={source_dir.name}. "
        f"Corrections={len(corrections)} mapped={len(corr_map)} solo_active={solo_active} pedalboard={HAS_PEDALBOARD}"
    )

    processed_count = 0

    for stem_path in sorted(source_dir.glob("*.wav")):
        if stem_path.name.lower() == "full_song.wav":
            continue

        stem_name = stem_path.stem
        corr = corr_map.get(_normalize_stem_name(stem_name), {})

        is_muted = _as_bool(corr.get("mute", False))
        is_solo = _as_bool(corr.get("solo", False))

        if solo_active:
            should_play = is_solo
        else:
            should_play = not is_muted

        try:
            audio, sr = sf.read(str(stem_path), dtype="float32")
        except Exception as e:
            logger.logger.warning(f"[{STAGE_ID}] Error reading stem {stem_name}: {e}")
            continue

        # Ensure (samples, channels=2)
        if audio.ndim == 1:
            audio = np.stack([audio, audio], axis=1)
        elif audio.ndim == 2 and audio.shape[1] == 1:
            audio = np.repeat(audio, 2, axis=1)
        elif audio.ndim == 2 and audio.shape[1] > 2:
            audio = audio[:, :2]

        if not should_play:
            audio = np.zeros_like(audio)
        else:
            if HAS_PEDALBOARD:
                board = Pedalboard()

                comp_cfg = corr.get("compression")
                if isinstance(comp_cfg, dict) and _as_bool(comp_cfg.get("enabled", True), default=True):
                    thresh = _as_float(comp_cfg.get("threshold", 0.0))
                    ratio = max(1.0, _as_float(comp_cfg.get("ratio", 1.0)))
                    if thresh < 0.0 and ratio > 1.0:
                        board.append(Compressor(threshold_db=thresh, ratio=ratio))

                eq_cfg = corr.get("eq")
                if isinstance(eq_cfg, dict) and _as_bool(eq_cfg.get("enabled", True), default=True):
                    low_gain = _as_float(eq_cfg.get("low", 0.0))
                    mid_gain = _as_float(eq_cfg.get("mid", 0.0))
                    high_gain = _as_float(eq_cfg.get("high", 0.0))

                    if abs(low_gain) > 0.01:
                        board.append(LowShelfFilter(cutoff_frequency_hz=320, gain_db=low_gain))
                    if abs(mid_gain) > 0.01:
                        board.append(PeakingFilter(cutoff_frequency_hz=1000, gain_db=mid_gain, q=1.0))
                    if abs(high_gain) > 0.01:
                        board.append(HighShelfFilter(cutoff_frequency_hz=3200, gain_db=high_gain))

                verb_cfg = corr.get("reverb")
                if isinstance(verb_cfg, dict) and _as_bool(verb_cfg.get("enabled", True), default=True):
                    amt_raw = _as_float(verb_cfg.get("amount", 0.0))
                    amt = amt_raw / 100.0 if amt_raw > 1.0 else amt_raw
                    amt = _clamp(amt, 0.0, 1.0)
                    if amt > 0:
                        board.append(Reverb(room_size=0.5, wet_level=amt, dry_level=1.0 - amt * 0.5))

                vol_db = _clamp(_as_float(corr.get("volume_db", 0.0)), -120.0, 24.0)
                if abs(vol_db) > 0.01:
                    board.append(Gain(gain_db=vol_db))

                try:
                    out = board(audio.T, sr)
                    audio = out.T
                except Exception as e:
                    logger.logger.error(f"[{STAGE_ID}] Error applying effects to {stem_name}: {e}")
            else:
                verb_cfg = corr.get("reverb")
                if isinstance(verb_cfg, dict) and _as_bool(verb_cfg.get("enabled", False)):
                    amt_raw = _as_float(verb_cfg.get("amount", 0.0))
                    amt = amt_raw / 100.0 if amt_raw > 1.0 else amt_raw
                    if amt > 0:
                        audio = _apply_simple_reverb(audio, sr, amt)

                vol_db = _clamp(_as_float(corr.get("volume_db", 0.0)), -120.0, 24.0)
                if abs(vol_db) > 0.01:
                    audio = audio * (10.0 ** (vol_db / 20.0))

            # Pan (constant power)
            pan = _clamp(_as_float(corr.get("pan", 0.0)), -1.0, 1.0)
            if abs(pan) > 0.01 and audio.shape[1] == 2:
                theta = (pan + 1.0) * (math.pi / 4.0)
                gain_L = math.cos(theta)
                gain_R = math.sin(theta)
                audio = audio.copy()
                audio[:, 0] *= gain_L
                audio[:, 1] *= gain_R

        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        if peak > 1.0:
            audio = audio / peak

        out_path = stage_dir / f"{stem_name}.wav"
        sf.write(str(out_path), audio, sr)
        processed_count += 1

    logger.logger.info(f"[{STAGE_ID}] Processed {processed_count} stems.")
    return True
