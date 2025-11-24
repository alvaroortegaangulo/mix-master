# src/analysis/mastering_analysis.py
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np
import soundfile as sf


EPS = 1e-12


def _safe_dbfs(value: float, floor: float = -120.0) -> float:
    v = float(value)
    if v <= 0.0:
        return floor
    return 20.0 * np.log10(v)


@dataclass
class MasteringResult:
    file_path: Path
    sample_rate: int
    num_channels: int
    duration_seconds: float

    peak_dbfs: float
    rms_dbfs: float
    is_vocal: bool

    recommended_target_peak_dbfs: float
    recommended_drive_db: float


def analyze_mastering(
    media_dir: Path,
    vocal_tuning_media_dir: Optional[Path] = None,
    vocal_filename: str = "vocal.wav",
) -> List[MasteringResult]:
    """
    Analiza todos los stems de media_dir (static_mix_dyn) y, si existe,
    usa la voz afinada de vocal_tuning_media_dir/vocal_filename para la pista vocal.

    :param media_dir: Carpeta con stems dinámicos (static_mix_dyn).
    :param vocal_tuning_media_dir: Carpeta con la voz afinada (vocal_tuning).
    :param vocal_filename: Nombre del archivo de voz principal.
    """
    if not media_dir.exists() or not media_dir.is_dir():
        raise FileNotFoundError(f"El directorio de medios no existe: {media_dir}")

    results: List[MasteringResult] = []

    for wav_path in sorted(media_dir.glob("*.wav")):
        is_vocal = wav_path.name.lower() == vocal_filename.lower()

        # Para el análisis, si es la voz y existe la versión afinada, la usamos
        analysis_path = wav_path
        if is_vocal and vocal_tuning_media_dir is not None:
            tuned_path = vocal_tuning_media_dir / vocal_filename
            if tuned_path.exists():
                analysis_path = tuned_path

        audio, sr = sf.read(analysis_path, dtype="float32", always_2d=True)
        num_samples, num_channels = audio.shape
        duration_seconds = float(num_samples) / float(sr) if num_samples > 0 else 0.0

        if num_samples > 0:
            peak = float(np.max(np.abs(audio)))
            rms = float(np.sqrt(np.mean(audio**2)))
        else:
            peak = 0.0
            rms = 0.0

        peak_dbfs = _safe_dbfs(peak)
        rms_dbfs = _safe_dbfs(rms)

        # Target de pico recomendado (más conservador en vocal)
        if is_vocal:
            target_peak = -2.0
        else:
            target_peak = -1.0

        # Drive aproximado hacia ese target (se clampeará)
        drive_db = target_peak - peak_dbfs
        drive_db = max(min(drive_db, 12.0), -24.0)

        results.append(
            MasteringResult(
                file_path=wav_path,
                sample_rate=int(sr),
                num_channels=int(num_channels),
                duration_seconds=duration_seconds,
                peak_dbfs=peak_dbfs,
                rms_dbfs=rms_dbfs,
                is_vocal=is_vocal,
                recommended_target_peak_dbfs=target_peak,
                recommended_drive_db=drive_db,
            )
        )

    return results


def export_mastering_to_csv(
    results: List[MasteringResult],
    csv_path: Path,
) -> None:
    """
    Exporta el análisis de mastering a un CSV en analysis/.
    Estructura (por fila de stem):

      filename
      relative_path
      sample_rate
      num_channels
      duration_seconds
      peak_dbfs
      rms_dbfs
      is_vocal
      recommended_target_peak_dbfs
      recommended_drive_db
    """
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "filename",
        "relative_path",
        "sample_rate",
        "num_channels",
        "duration_seconds",
        "peak_dbfs",
        "rms_dbfs",
        "is_vocal",
        "recommended_target_peak_dbfs",
        "recommended_drive_db",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for r in results:
            writer.writerow(
                {
                    "filename": r.file_path.name,
                    "relative_path": r.file_path.name,
                    "sample_rate": r.sample_rate,
                    "num_channels": r.num_channels,
                    "duration_seconds": f"{r.duration_seconds:.6f}",
                    "peak_dbfs": f"{r.peak_dbfs:.2f}",
                    "rms_dbfs": f"{r.rms_dbfs:.2f}",
                    "is_vocal": "1" if r.is_vocal else "0",
                    "recommended_target_peak_dbfs": f"{r.recommended_target_peak_dbfs:.2f}",
                    "recommended_drive_db": f"{r.recommended_drive_db:.2f}",
                }
            )
