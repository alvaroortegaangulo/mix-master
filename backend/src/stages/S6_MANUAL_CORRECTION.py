from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

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
except ImportError:  # pragma: no cover
    HAS_PEDALBOARD = False


STAGE_ID = "S6_MANUAL_CORRECTION"


def _normalize_stem_name(value: str) -> str:
    """
    Normalize names so that:
      - "Vocals.wav" -> "vocals"
      - "lead vox.wav" -> "lead_vox"
    """
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


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _apply_simple_reverb(audio: np.ndarray, sr: int, amount: float) -> np.ndarray:
    """
    Simple, deterministic delay-tap reverb (fallback when Pedalboard is unavailable).

    Expects audio in (channels, samples) float32.
    amount in [0..1].
    """
    amount = _clamp(amount, 0.0, 1.0)
    if amount <= 0:
        return audio

    delays_sec = [0.03, 0.05, 0.08, 0.11]
    gains = [0.5, 0.35, 0.25, 0.2]
    wet = audio.copy()

    for delay_sec, gain in zip(delays_sec, gains):
        delay = int(sr * delay_sec)
        if delay <= 0 or delay >= wet.shape[1]:
            continue
        wet[:, delay:] += audio[:, :-delay] * (gain * amount)

    dry_gain = 1.0 - min(0.5, amount * 0.5)
    wet_gain = amount
    mixed = (audio * dry_gain) + (wet * wet_gain)

    # Prevent clipping before writing PCM WAV
    peak = float(np.max(np.abs(mixed))) if mixed.size else 0.0
    if peak > 1.0:
        mixed = mixed / peak

    return mixed.astype(np.float32, copy=False)


def _detect_sample_rate(*directories: Optional[Path]) -> Optional[int]:
    """
    Infer sample rate from the first available WAV file (excluding full_song.wav).
    """
    for directory in directories:
        if not directory or not directory.exists():
            continue
        for wav_path in sorted(directory.glob("*.wav")):
            if wav_path.name.lower() == "full_song.wav":
                continue
            try:
                return int(sf.info(str(wav_path)).samplerate)
            except Exception:
                continue
    return None


def _load_corrections(context: PipelineContext, current_dir: Path) -> List[Dict[str, Any]]:
    """
    Load corrections saved by the Studio UI via POST /jobs/{job_id}/correction.
    Expected path: <temp_root>/work/manual_corrections.json

    Accepts:
      - {"corrections": [ ... ]}
      - [ ... ] (legacy)
    """
    temp_root = getattr(context, "temp_root", None)
    work_dir = (Path(temp_root) / "work") if temp_root else (current_dir.parent / "work")
    corrections_path = work_dir / "manual_corrections.json"

    if not corrections_path.exists():
        pipeline_logger.info(f"[{STAGE_ID}] No manual_corrections.json found at {corrections_path}.")
        return []

    raw = _read_json(corrections_path)
    if isinstance(raw, dict) and isinstance(raw.get("corrections"), list):
        return [c for c in raw["corrections"] if isinstance(c, dict)]
    if isinstance(raw, list):
        return [c for c in raw if isinstance(c, dict)]

    pipeline_logger.info(f"[{STAGE_ID}] manual_corrections.json has unexpected shape. Ignoring.")
    return []


def _pan_gains_linear(pan: float) -> tuple[float, float]:
    """
    Linear pan gains (matches existing behaviour in this repo):
      pan=-1 -> (1, 0)
      pan= 0 -> (1, 1)
      pan=+1 -> (0, 1)
    """
    pan = _clamp(pan, -1.0, 1.0)
    l_gain = 1.0 if pan <= 0.0 else (1.0 - pan)
    r_gain = 1.0 if pan >= 0.0 else (1.0 + pan)
    return l_gain, r_gain


def process(context: PipelineContext, *args) -> bool:
    """
    Applies manual corrections (volume, pan, eq, comp, reverb, mute, solo) to stems.

    Data flow (current app):
      - Frontend calls POST /jobs/{job_id}/correction with a list of corrections.
      - Backend persists them at <temp_root>/work/manual_corrections.json
      - Pipeline resumes from S6 and this stage consumes that file.

    Stems are expected in (channels, samples) float32 numpy arrays.
    """
    pipeline_logger.log_stage_start(STAGE_ID)

    # 1) Directories
    current_dir = context.get_stage_dir(STAGE_ID)
    current_dir.mkdir(parents=True, exist_ok=True)
    temp_root = getattr(context, "temp_root", None)
    s5_dir = (Path(temp_root) / "S5_LEADVOX_DYNAMICS") if temp_root else None

    # 2) Corrections
    corrections = _load_corrections(context, current_dir)

    corr_map: Dict[str, Dict[str, Any]] = {}
    for corr in corrections:
        key = _normalize_stem_name(corr.get("name", ""))
        if key:
            corr_map[key] = corr

    any_solo = any(_as_bool(c.get("solo", False)) for c in corrections)

    pipeline_logger.info(
        f"[{STAGE_ID}] Loaded {len(corrections)} corrections ({len(corr_map)} mapped). "
        f"Solo active: {any_solo}. Pedalboard: {HAS_PEDALBOARD}."
    )

    # 3) Load input stems (prefer in-memory; fallback to disk)
    stems_map: Dict[str, np.ndarray] = getattr(context, "audio_stems", {}) or {}

    # IMPORTANT:
    # Corrections coming from the UI are *absolute* (volume_db/pan/eq/etc).
    # To keep the stage idempotent (and avoid stacking on re-runs), we prefer
    # loading the pre-correction stems from the previous stage (S5) when present.
    if not stems_map:
        if s5_dir and s5_dir.exists():
            stems_map = load_audio_stems(s5_dir)
            if stems_map:
                pipeline_logger.info(f"[{STAGE_ID}] Using base stems from {s5_dir}.")
        if not stems_map:
            stems_map = load_audio_stems(current_dir)

    if not stems_map:
        pipeline_logger.info(f"[{STAGE_ID}] No input stems found.")
        return False

    # 4) Sample rate
    sr = getattr(context, "sample_rate", None)
    if not isinstance(sr, int) or sr <= 0:
        sr = _detect_sample_rate(current_dir, s5_dir) or 48000
        if sr == 48000:
            pipeline_logger.info(f"[{STAGE_ID}] sample_rate not found; defaulting to {sr} Hz.")
        context.sample_rate = sr

    # 5) Apply corrections
    processed_stems: Dict[str, np.ndarray] = {}
    muted_count = 0

    for filename, audio in stems_map.items():
        key = _normalize_stem_name(filename)
        corr = corr_map.get(key)

        # Ensure float32 and shape (channels, samples)
        if not isinstance(audio, np.ndarray):
            processed_stems[filename] = audio  # type: ignore[assignment]
            continue

        if audio.dtype != np.float32:
            audio = audio.astype(np.float32, copy=False)

        if audio.ndim == 1:
            audio = audio[np.newaxis, :]
        elif audio.ndim == 2:
            pass
        else:
            audio = np.reshape(audio, (audio.shape[0], -1)).astype(np.float32, copy=False)

        if not corr:
            processed_stems[filename] = audio
            continue

        # Mute / Solo logic
        is_muted = _as_bool(corr.get("mute", False))
        is_solo = _as_bool(corr.get("solo", False))

        if is_muted or (any_solo and not is_solo):
            processed_stems[filename] = np.zeros_like(audio)
            muted_count += 1
            continue

        processed = audio

        # --- Pedalboard chain (preferred) ---
        if HAS_PEDALBOARD:
            board = Pedalboard()

            # EQ (3-band)
            eq_cfg = corr.get("eq")
            if isinstance(eq_cfg, dict) and _as_bool(eq_cfg.get("enabled", True), default=True):
                low = _as_float(eq_cfg.get("low", 0.0))
                mid = _as_float(eq_cfg.get("mid", 0.0))
                high = _as_float(eq_cfg.get("high", 0.0))

                if abs(low) > 0.01:
                    board.append(LowShelfFilter(cutoff_frequency_hz=100, gain_db=low))
                if abs(mid) > 0.01:
                    board.append(PeakingFilter(cutoff_frequency_hz=1000, gain_db=mid, q=1.0))
                if abs(high) > 0.01:
                    board.append(HighShelfFilter(cutoff_frequency_hz=5000, gain_db=high))

            # Compression
            comp_cfg = corr.get("compression")
            if isinstance(comp_cfg, dict) and _as_bool(comp_cfg.get("enabled", True), default=True):
                threshold_db = _as_float(comp_cfg.get("threshold", -20.0), default=-20.0)
                ratio = _as_float(comp_cfg.get("ratio", 2.0), default=2.0)
                ratio = max(1.0, ratio)
                board.append(
                    Compressor(
                        threshold_db=threshold_db,
                        ratio=ratio,
                        attack_ms=10,
                        release_ms=100,
                    )
                )

            # Reverb
            verb_cfg = corr.get("reverb")
            if isinstance(verb_cfg, dict) and _as_bool(verb_cfg.get("enabled", True), default=True):
                amt_raw = _as_float(verb_cfg.get("amount", 0.0))
                amt = amt_raw / 100.0 if amt_raw > 1.0 else amt_raw
                amt = _clamp(amt, 0.0, 1.0)
                if amt > 0:
                    board.append(Reverb(room_size=0.5, wet_level=amt, dry_level=1.0 - amt * 0.5))

            # Volume
            vol_db = _as_float(corr.get("volume_db", 0.0), default=0.0)
            vol_db = _clamp(vol_db, -120.0, 24.0)
            if abs(vol_db) > 0.01:
                board.append(Gain(gain_db=vol_db))

            try:
                processed = board(processed, sr)
                if isinstance(processed, np.ndarray) and processed.dtype != np.float32:
                    processed = processed.astype(np.float32, copy=False)
            except Exception as exc:
                pipeline_logger.info(f"[{STAGE_ID}] Pedalboard failed for {filename}: {exc}. Using dry audio.")
                processed = audio

        # --- Fallback DSP (no pedalboard): Volume/Pan/Reverb only ---
        else:
            verb_cfg = corr.get("reverb")
            if isinstance(verb_cfg, dict) and _as_bool(verb_cfg.get("enabled", False)):
                amt_raw = _as_float(verb_cfg.get("amount", 0.0))
                amt = amt_raw / 100.0 if amt_raw > 1.0 else amt_raw
                if amt > 0:
                    processed = _apply_simple_reverb(processed, sr, amt)

            vol_db = _as_float(corr.get("volume_db", 0.0), default=0.0)
            vol_db = _clamp(vol_db, -120.0, 24.0)
            if abs(vol_db) > 0.01:
                processed = processed * (10.0 ** (vol_db / 20.0))

        # Pan (linear, como estaba en tu repo)
        pan = _as_float(corr.get("pan", 0.0), default=0.0)
        pan = _clamp(pan, -1.0, 1.0)
        if abs(pan) > 1e-6 and processed.shape[0] == 2:
            l_gain, r_gain = _pan_gains_linear(pan)
            processed = processed.copy()
            processed[0] *= l_gain
            processed[1] *= r_gain

        # Prevent clipping before writing PCM WAV
        peak = float(np.max(np.abs(processed))) if processed.size else 0.0
        if peak > 1.0:
            processed = (processed / peak).astype(np.float32, copy=False)

        processed_stems[filename] = processed

    # 6) Save results
    context.audio_stems = processed_stems
    save_audio_stems(current_dir, processed_stems, sr)

    pipeline_logger.info(f"[{STAGE_ID}] Processed {len(processed_stems)} stems. Muted: {muted_count}.")
    pipeline_logger.log_stage_success(STAGE_ID)
    return True
