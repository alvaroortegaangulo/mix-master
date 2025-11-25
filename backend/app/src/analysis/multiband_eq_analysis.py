from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import soundfile as sf
from pedalboard import Pedalboard, HighpassFilter, LowpassFilter


def _safe_dbfs(value: float, floor: float = -120.0) -> float:
    v = float(value)
    if v <= 0.0:
        return floor
    return 20.0 * np.log10(v)


DEFAULT_LOW_MID_CROSSOVER_HZ = 120.0
DEFAULT_MID_HIGH_CROSSOVER_HZ = 5000.0


@dataclass
class MultibandEQResult:
    file_path: Path
    relative_path: str
    sample_rate: int
    num_channels: int
    duration_seconds: float

    is_vocal: bool
    is_bus_fx: bool
    bus_key: Optional[str]

    low_rms_dbfs: float
    mid_rms_dbfs: float
    high_rms_dbfs: float
    full_rms_dbfs: float

    suggested_low_gain_db: float
    suggested_mid_gain_db: float
    suggested_high_gain_db: float


def _classify_stem_for_multiband(
    filename: str,
    vocal_filename: str = "vocal.wav",
) -> Tuple[bool, bool, Optional[str]]:
    name = filename.lower()
    stem_stem = Path(filename).stem.lower()
    vocal_stem = Path(vocal_filename).stem.lower()

    is_vocal = (
        stem_stem == vocal_stem
        or "vocal" in stem_stem
        or "vox" in stem_stem
    )

    is_bus_fx = (
        stem_stem.startswith("bus_")
        or "reverb" in stem_stem
        or "verb" in stem_stem
        or "space" in stem_stem
        or stem_stem.endswith("_fx")
        or stem_stem == "fx"
    )

    bus_key: Optional[str] = None
    for cand in [
        "drums",
        "bass",
        "guitars",
        "keys_synth",
        "lead_vocal",
        "backing_vocals",
        "fx",
        "misc",
    ]:
        if cand in stem_stem:
            bus_key = cand
            break

    return is_vocal, is_bus_fx, bus_key


def _split_into_bands(
    audio_ch_first: np.ndarray,
    sr: int,
    low_mid_crossover_hz: float,
    mid_high_crossover_hz: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    board_low = Pedalboard(
        [LowpassFilter(cutoff_frequency_hz=low_mid_crossover_hz)]
    )
    board_mid = Pedalboard(
        [
            HighpassFilter(cutoff_frequency_hz=low_mid_crossover_hz),
            LowpassFilter(cutoff_frequency_hz=mid_high_crossover_hz),
        ]
    )
    board_high = Pedalboard(
        [HighpassFilter(cutoff_frequency_hz=mid_high_crossover_hz)]
    )

    low = board_low(audio_ch_first, sr)
    mid = board_mid(audio_ch_first, sr)
    high = board_high(audio_ch_first, sr)

    return low, mid, high


def analyze_multiband_eq(
    media_dir: Path,
    low_mid_crossover_hz: float = DEFAULT_LOW_MID_CROSSOVER_HZ,
    mid_high_crossover_hz: float = DEFAULT_MID_HIGH_CROSSOVER_HZ,
    vocal_filename: str = "vocal.wav",
) -> List[MultibandEQResult]:
    if not media_dir.exists() or not media_dir.is_dir():
        raise FileNotFoundError(f"El directorio de medios no existe: {media_dir}")

    results: List[MultibandEQResult] = []

    for wav_path in sorted(media_dir.glob("*.wav")):
        audio, sr = sf.read(str(wav_path), dtype="float32", always_2d=True)
        num_samples, num_channels = audio.shape
        duration_seconds = float(num_samples) / float(sr) if num_samples > 0 else 0.0

        if num_samples == 0:
            low_rms_dbfs = mid_rms_dbfs = high_rms_dbfs = full_rms_dbfs = -120.0
            suggested_low = suggested_mid = suggested_high = 0.0
        else:
            audio_ch_first = audio.T  # (C, N)

            low, mid, high = _split_into_bands(
                audio_ch_first,
                sr,
                low_mid_crossover_hz=low_mid_crossover_hz,
                mid_high_crossover_hz=mid_high_crossover_hz,
            )

            low_rms = float(np.sqrt(np.mean(low * low))) if low.size else 0.0
            mid_rms = float(np.sqrt(np.mean(mid * mid))) if mid.size else 0.0
            high_rms = float(np.sqrt(np.mean(high * high))) if high.size else 0.0
            full_rms = float(np.sqrt(np.mean(audio_ch_first * audio_ch_first))) if audio_ch_first.size else 0.0

            low_rms_dbfs = _safe_dbfs(low_rms)
            mid_rms_dbfs = _safe_dbfs(mid_rms)
            high_rms_dbfs = _safe_dbfs(high_rms)
            full_rms_dbfs = _safe_dbfs(full_rms)

            if full_rms <= 0.0:
                suggested_low = suggested_mid = suggested_high = 0.0
            else:
                ref = mid_rms_dbfs
                suggested_mid = 0.0
                suggested_low = float(np.clip(ref - low_rms_dbfs, -4.0, 4.0))
                suggested_high = float(np.clip(ref - high_rms_dbfs, -4.0, 4.0))

        is_vocal, is_bus_fx, bus_key = _classify_stem_for_multiband(
            wav_path.name,
            vocal_filename=vocal_filename,
        )

        if is_bus_fx:
            suggested_low = float(np.clip(suggested_low, -2.0, 2.0))
            suggested_mid = float(np.clip(suggested_mid, -2.0, 2.0))
            suggested_high = float(np.clip(suggested_high, -2.0, 2.0))

        results.append(
            MultibandEQResult(
                file_path=wav_path,
                relative_path=wav_path.name,
                sample_rate=int(sr),
                num_channels=int(num_channels),
                duration_seconds=duration_seconds,
                is_vocal=is_vocal,
                is_bus_fx=is_bus_fx,
                bus_key=bus_key,
                low_rms_dbfs=low_rms_dbfs,
                mid_rms_dbfs=mid_rms_dbfs,
                high_rms_dbfs=high_rms_dbfs,
                full_rms_dbfs=full_rms_dbfs,
                suggested_low_gain_db=suggested_low,
                suggested_mid_gain_db=suggested_mid,
                suggested_high_gain_db=suggested_high,
            )
        )

    return results


def export_multiband_eq_to_json(
    results: List[MultibandEQResult],
    json_path: Path,
) -> Path:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = []
    for r in results:
        row = asdict(r)
        row["file_path"] = str(r.file_path)
        payload.append(row)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return json_path


__all__ = ["MultibandEQResult", "analyze_multiband_eq", "export_multiband_eq_to_json"]
