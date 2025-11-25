# src/analysis/multiband_eq_analysis.py
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import soundfile as sf

from pedalboard import Pedalboard, HighpassFilter, LowpassFilter


EPS = 1e-12


def _safe_dbfs(value: float, floor: float = -120.0) -> float:
    v = float(value)
    if v <= 0.0:
        return floor
    return 20.0 * np.log10(v)


# Crossovers por defecto (muy estándar / seguros)
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


# ----------------------------------------------------------------------
# Clasificación muy simple por nombre de archivo
# ----------------------------------------------------------------------


def _classify_stem_for_multiband(
    filename: str,
    vocal_filename: str = "vocal.wav",
) -> Tuple[bool, bool, Optional[str]]:
    """
    Heurística muy sencilla:
      - is_vocal si el nombre coincide con vocal_filename o contiene vocal/vox.
      - is_bus_fx si parece un bus de FX/reverb/space.
      - bus_key aproximado por keywords en el nombre.
    """
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


# ----------------------------------------------------------------------
# Split en 3 bandas usando filtros de Pedalboard
# ----------------------------------------------------------------------


def _split_into_bands(
    audio_ch_first: np.ndarray,
    sr: int,
    low_mid_crossover_hz: float,
    mid_high_crossover_hz: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Divide audio (channels, samples) en tres bandas usando HP/LP de Pedalboard.
    Devuelve (low, mid, high) con la misma forma que audio_ch_first.
    """
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


# ----------------------------------------------------------------------
# Análisis
# ----------------------------------------------------------------------


def analyze_multiband_eq(
    media_dir: Path,
    low_mid_crossover_hz: float = DEFAULT_LOW_MID_CROSSOVER_HZ,
    mid_high_crossover_hz: float = DEFAULT_MID_HIGH_CROSSOVER_HZ,
    vocal_filename: str = "vocal.wav",
) -> List[MultibandEQResult]:
    """
    Analiza todos los .wav de media_dir, calculando RMS de low/mid/high/full
    y una sugerencia de ganancia por banda muy moderada.

    - low_mid_crossover_hz: punto de crossover low/mid.
    - mid_high_crossover_hz: punto de crossover mid/high.
    """
    if not media_dir.exists() or not media_dir.is_dir():
        raise FileNotFoundError(f"El directorio de medios no existe: {media_dir}")

    results: List[MultibandEQResult] = []

    for wav_path in sorted(media_dir.glob("*.wav")):
        audio, sr = sf.read(str(wav_path), dtype="float32", always_2d=True)
        num_samples, num_channels = audio.shape
        duration_seconds = float(num_samples) / float(sr) if num_samples > 0 else 0.0

        if num_samples == 0:
            # Archivo vacío → todo a -inf (~floor)
            low_rms_dbfs = mid_rms_dbfs = high_rms_dbfs = full_rms_dbfs = -120.0
            suggested_low = suggested_mid = suggested_high = 0.0
        else:
            # Pedalboard trabaja como (channels, samples)
            audio_ch_first = audio.T  # (C, N)

            low, mid, high = _split_into_bands(
                audio_ch_first,
                sr,
                low_mid_crossover_hz=low_mid_crossover_hz,
                mid_high_crossover_hz=mid_high_crossover_hz,
            )

            # RMS por banda (global, todas las canales)
            low_rms = float(np.sqrt(np.mean(low**2))) if low.size else 0.0
            mid_rms = float(np.sqrt(np.mean(mid**2))) if mid.size else 0.0
            high_rms = float(np.sqrt(np.mean(high**2))) if high.size else 0.0
            full_rms = float(np.sqrt(np.mean(audio_ch_first**2))) if audio_ch_first.size else 0.0

            low_rms_dbfs = _safe_dbfs(low_rms)
            mid_rms_dbfs = _safe_dbfs(mid_rms)
            high_rms_dbfs = _safe_dbfs(high_rms)
            full_rms_dbfs = _safe_dbfs(full_rms)

            # Sugerencia de ganancia muy suave:
            # tomamos mid como referencia y compensamos ±4 dB máx.
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

        # Para buses de FX, forzamos sugerencias casi neutras (solo logging)
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


def export_multiband_eq_to_csv(
    results: List[MultibandEQResult],
    csv_path: Path,
) -> None:
    """
    Exporta el análisis multibanda a CSV.
    """
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "filename",
        "relative_path",
        "sample_rate",
        "num_channels",
        "duration_seconds",
        "is_vocal",
        "is_bus_fx",
        "bus_key",
        "low_rms_dbfs",
        "mid_rms_dbfs",
        "high_rms_dbfs",
        "full_rms_dbfs",
        "suggested_low_gain_db",
        "suggested_mid_gain_db",
        "suggested_high_gain_db",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for r in results:
            writer.writerow(
                {
                    "filename": r.file_path.name,
                    "relative_path": r.relative_path,
                    "sample_rate": r.sample_rate,
                    "num_channels": r.num_channels,
                    "duration_seconds": f"{r.duration_seconds:.6f}",
                    "is_vocal": "1" if r.is_vocal else "0",
                    "is_bus_fx": "1" if r.is_bus_fx else "0",
                    "bus_key": r.bus_key or "",
                    "low_rms_dbfs": f"{r.low_rms_dbfs:.2f}",
                    "mid_rms_dbfs": f"{r.mid_rms_dbfs:.2f}",
                    "high_rms_dbfs": f"{r.high_rms_dbfs:.2f}",
                    "full_rms_dbfs": f"{r.full_rms_dbfs:.2f}",
                    "suggested_low_gain_db": f"{r.suggested_low_gain_db:.2f}",
                    "suggested_mid_gain_db": f"{r.suggested_mid_gain_db:.2f}",
                    "suggested_high_gain_db": f"{r.suggested_high_gain_db:.2f}",
                }
            )
