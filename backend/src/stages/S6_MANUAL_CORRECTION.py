from __future__ import annotations

import json
import math
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
from utils.color_utils import apply_soft_saturation
from utils.logger import logger as pipeline_logger

# Try importing pedalboard for DSP
try:
    from pedalboard import Pedalboard, Reverb, Gain
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


def _apply_speed(audio: np.ndarray, speed: float) -> np.ndarray:
    """
    Resample audio to simulate playback speed changes.

    Expects audio in (channels, samples) float32.
    speed > 1.0 = faster (shorter), speed < 1.0 = slower (longer).
    """
    speed = float(speed)
    if speed <= 0 or abs(speed - 1.0) < 1e-3:
        return audio

    channels, samples = audio.shape
    if samples < 2:
        return audio

    new_length = max(1, int(round(samples / speed)))
    if new_length == samples:
        return audio
    if new_length < 2:
        return audio[:, :new_length]

    x_old = np.linspace(0.0, 1.0, num=samples, endpoint=True)
    x_new = np.linspace(0.0, 1.0, num=new_length, endpoint=True)
    resampled = np.empty((channels, new_length), dtype=np.float32)
    for ch in range(channels):
        resampled[ch] = np.interp(x_new, x_old, audio[ch]).astype(np.float32, copy=False)
    return resampled


def _read_effect_amount(value: Any, default: float, lo: float, hi: float) -> float:
    """
    Read amount from either a plain number or {amount, enabled}.
    Returns default if disabled or missing.
    """
    if value is None:
        return default
    enabled = True
    amount = value
    if isinstance(value, dict):
        enabled = _as_bool(value.get("enabled", True), default=True)
        amount = value.get("amount", value.get("value", default))
    if not enabled:
        return default
    return _clamp(_as_float(amount, default), lo, hi)


def _parse_stereo_width(value: Any, default: float = 1.0) -> float:
    """
    Accepts:
      - factor (0..2)
      - percent (0..200)
      - {amount, enabled}
    """
    if value is None:
        return default
    enabled = True
    amount = value
    if isinstance(value, dict):
        enabled = _as_bool(value.get("enabled", True), default=True)
        amount = value.get("amount", value.get("value", default))
    if not enabled:
        return default
    raw = _as_float(amount, default)
    if raw > 2.0:
        raw = raw / 100.0
    return _clamp(raw, 0.0, 2.0)


def _apply_stereo_width(audio: np.ndarray, width: float) -> np.ndarray:
    if audio.ndim != 2 or audio.shape[0] != 2:
        return audio
    width = _clamp(width, 0.0, 2.0)
    if abs(width - 1.0) < 1e-3:
        return audio

    left = audio[0]
    right = audio[1]
    mid = 0.5 * (left + right)
    side = 0.5 * (left - right)
    side = side * width
    out = np.vstack([mid + side, mid - side])
    return out.astype(np.float32, copy=False)


def _apply_simple_ambience(audio: np.ndarray, sr: int, amount: float) -> np.ndarray:
    """
    Short ambience send (early reflections) to push elements back.
    Expects audio in (channels, samples) float32.
    """
    amount = _clamp(amount, 0.0, 1.0)
    if amount <= 0:
        return audio

    delays_sec = [0.01, 0.02, 0.035]
    gains = [0.45, 0.3, 0.2]
    wet = audio.copy()

    for delay_sec, gain in zip(delays_sec, gains):
        delay = int(sr * delay_sec)
        if delay <= 0 or delay >= wet.shape[1]:
            continue
        wet[:, delay:] += audio[:, :-delay] * (gain * amount)

    dry_gain = 1.0 - min(0.3, amount * 0.3)
    wet_gain = amount * 0.7
    mixed = (audio * dry_gain) + (wet * wet_gain)

    peak = float(np.max(np.abs(mixed))) if mixed.size else 0.0
    if peak > 1.0:
        mixed = mixed / peak

    return mixed.astype(np.float32, copy=False)


def _apply_transient_shaper(audio: np.ndarray, sr: int, punch: float) -> np.ndarray:
    """
    Simple transient shaper using fast/slow envelope difference.
    punch in [-1..1], positive boosts attack, negative softens.
    """
    punch = _clamp(punch, -1.0, 1.0)
    if abs(punch) < 1e-3:
        return audio
    if audio.ndim != 2 or audio.shape[1] < 2:
        return audio

    mono = np.mean(audio, axis=0)
    rect = np.abs(mono)
    if rect.size < 2:
        return audio

    stride = max(1, int(sr * 0.0025))
    idx = np.arange(0, rect.size, stride)
    rect_ds = rect[idx]

    dt = stride / float(sr)
    fast_attack = math.exp(-dt / 0.001) if dt > 0 else 0.0
    fast_release = math.exp(-dt / 0.05) if dt > 0 else 0.0
    slow_attack = math.exp(-dt / 0.01) if dt > 0 else 0.0
    slow_release = math.exp(-dt / 0.2) if dt > 0 else 0.0

    fast_env = 0.0
    slow_env = 0.0
    fast_vals = np.empty_like(rect_ds, dtype=np.float32)
    slow_vals = np.empty_like(rect_ds, dtype=np.float32)

    for i, x in enumerate(rect_ds):
        if x > fast_env:
            fast_env = fast_attack * fast_env + (1.0 - fast_attack) * x
        else:
            fast_env = fast_release * fast_env + (1.0 - fast_release) * x
        if x > slow_env:
            slow_env = slow_attack * slow_env + (1.0 - slow_attack) * x
        else:
            slow_env = slow_release * slow_env + (1.0 - slow_release) * x
        fast_vals[i] = fast_env
        slow_vals[i] = slow_env

    transient = np.maximum(fast_vals - slow_vals, 0.0)
    ratio = transient / (fast_vals + 1e-6)
    gain_ds = 1.0 + punch * ratio
    gain_ds = np.clip(gain_ds, 0.0, 2.0)
    gain = np.interp(np.arange(rect.size), idx, gain_ds).astype(np.float32, copy=False)

    return (audio * gain).astype(np.float32, copy=False)


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
    Applies manual corrections (volume, pan, stereo width, saturation, transient, depth,
    reverb, speed, mute, solo) to stems.

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
    # Corrections coming from the UI are *absolute* (volume_db/pan/reverb/speed/etc).
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

        speed = _as_float(corr.get("speed", 1.0), default=1.0)
        speed = _clamp(speed, 0.5, 1.5)
        if abs(speed - 1.0) > 1e-3:
            processed = _apply_speed(processed, speed)

        width = _parse_stereo_width(corr.get("stereo_width", None))
        sat_amount = _read_effect_amount(corr.get("saturation", None), 0.0, 0.0, 100.0)
        transient_amount = _read_effect_amount(corr.get("transient", None), 0.0, -100.0, 100.0)
        depth_amount = _read_effect_amount(corr.get("depth", None), 0.0, 0.0, 100.0) / 100.0

        if sat_amount > 0.01:
            drive_db = sat_amount * 0.12
            processed = apply_soft_saturation(processed, drive_db=drive_db)

        if abs(transient_amount) > 0.01:
            processed = _apply_transient_shaper(processed, sr, transient_amount / 100.0)

        if abs(width - 1.0) > 1e-3:
            processed = _apply_stereo_width(processed, width)

        # --- Pedalboard chain (preferred) ---
        if HAS_PEDALBOARD:
            board = Pedalboard()

            # Depth (ambience)
            if depth_amount > 0:
                board.append(
                    Reverb(
                        room_size=0.25,
                        wet_level=_clamp(depth_amount * 0.7, 0.0, 1.0),
                        dry_level=_clamp(1.0 - depth_amount * 0.3, 0.0, 1.0),
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

            processed_input = processed
            try:
                processed = board(processed_input, sr)
                if isinstance(processed, np.ndarray) and processed.dtype != np.float32:
                    processed = processed.astype(np.float32, copy=False)
            except Exception as exc:
                pipeline_logger.info(f"[{STAGE_ID}] Pedalboard failed for {filename}: {exc}. Using unprocessed audio.")
                processed = processed_input

        # --- Fallback DSP (no pedalboard): Volume/Pan/Reverb only ---
        else:
            if depth_amount > 0:
                processed = _apply_simple_ambience(processed, sr, depth_amount)

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
