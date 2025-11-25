# src/analysis/mix_bus_color_analysis.py
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf


def _safe_dbfs(value: float, floor: float = -120.0) -> float:
    v = float(value)
    if v <= 0.0:
        return floor
    return 20.0 * float(np.log10(v))


@dataclass
class MixBusColorResult:
    mix_path: Path
    sample_rate: int
    num_channels: int
    duration_seconds: float

    peak_dbfs: float
    rms_dbfs: float
    crest_factor_db: float

    recommended_hpf_hz: float
    recommended_saturation_drive_db: float
    recommended_tape_mix: float
    recommended_console_mix: float


def analyze_mix_bus_color(mix_path: Path) -> MixBusColorResult:
    """
    Analiza el full mix para decidir un color de bus sutil pero con carácter.
    Se asume que mix_path apunta al full mix ya masterizado por stems
    (p.ej. media/mastering/full_song.wav).
    """
    mix_path = mix_path.resolve()
    if not mix_path.exists():
        raise FileNotFoundError(f"No se encontró el full mix: {mix_path}")

    audio, sr = sf.read(str(mix_path), dtype="float32", always_2d=True)
    num_samples, num_channels = audio.shape
    duration_seconds = float(num_samples) / float(sr) if num_samples > 0 else 0.0

    if num_samples > 0:
        peak_lin = float(np.max(np.abs(audio)))
        rms_lin = float(np.sqrt(np.mean(audio**2)))
    else:
        peak_lin = 0.0
        rms_lin = 0.0

    peak_dbfs = _safe_dbfs(peak_lin)
    rms_dbfs = _safe_dbfs(rms_lin)
    crest_factor_db = peak_dbfs - rms_dbfs

    # ------------------------------
    # Heurística de drive de color:
    # ------------------------------
    # Mezclas muy dinámicas -> más drive permitido.
    # Mezclas muy densas -> drive mínimo para no destrozar el master.
    if rms_dbfs <= -20.0:
        sat_drive_db = 4.0
    elif rms_dbfs <= -16.0:
        sat_drive_db = 3.0
    elif rms_dbfs <= -14.0:
        sat_drive_db = 2.0
    elif rms_dbfs <= -12.0:
        sat_drive_db = 1.5
    elif rms_dbfs <= -10.0:
        sat_drive_db = 1.0
    else:
        sat_drive_db = 0.5

    # HPF del bus: entre 20 y 30 Hz, casi siempre.
    # Si el crest factor es muy bajo (mezcla muy aplastada),
    # subimos un poco la frecuencia de corte.
    if crest_factor_db < 8.0:
        hpf_hz = 30.0
    elif crest_factor_db < 10.0:
        hpf_hz = 27.0
    else:
        hpf_hz = 24.0

    # Mezcla de IRs:
    # - Tape: más en mezclas muy dinámicas.
    # - Console: siempre algo más discreta.
    if crest_factor_db >= 13.0:
        tape_mix = 0.35
        console_mix = 0.22
    elif crest_factor_db >= 10.0:
        tape_mix = 0.28
        console_mix = 0.20
    elif crest_factor_db >= 8.0:
        tape_mix = 0.22
        console_mix = 0.18
    else:
        tape_mix = 0.18
        console_mix = 0.15

    return MixBusColorResult(
        mix_path=mix_path,
        sample_rate=int(sr),
        num_channels=int(num_channels),
        duration_seconds=duration_seconds,
        peak_dbfs=peak_dbfs,
        rms_dbfs=rms_dbfs,
        crest_factor_db=crest_factor_db,
        recommended_hpf_hz=hpf_hz,
        recommended_saturation_drive_db=sat_drive_db,
        recommended_tape_mix=tape_mix,
        recommended_console_mix=console_mix,
    )


def export_mix_bus_color_to_csv(
    result: MixBusColorResult,
    csv_path: Path,
) -> None:
    """
    Exporta el análisis de mix-bus a CSV (una sola fila).
    """
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "mix_path",
        "sample_rate",
        "num_channels",
        "duration_seconds",
        "peak_dbfs",
        "rms_dbfs",
        "crest_factor_db",
        "recommended_hpf_hz",
        "recommended_saturation_drive_db",
        "recommended_tape_mix",
        "recommended_console_mix",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(
            {
                "mix_path": str(result.mix_path),
                "sample_rate": result.sample_rate,
                "num_channels": result.num_channels,
                "duration_seconds": f"{result.duration_seconds:.6f}",
                "peak_dbfs": f"{result.peak_dbfs:.2f}",
                "rms_dbfs": f"{result.rms_dbfs:.2f}",
                "crest_factor_db": f"{result.crest_factor_db:.2f}",
                "recommended_hpf_hz": f"{result.recommended_hpf_hz:.1f}",
                "recommended_saturation_drive_db": f"{result.recommended_saturation_drive_db:.2f}",
                "recommended_tape_mix": f"{result.recommended_tape_mix:.3f}",
                "recommended_console_mix": f"{result.recommended_console_mix:.3f}",
            }
        )


__all__ = ["MixBusColorResult", "analyze_mix_bus_color", "export_mix_bus_color_to_csv"]
