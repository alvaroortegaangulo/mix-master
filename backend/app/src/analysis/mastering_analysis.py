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



def _classify_stem_for_mastering(
    filename: str,
    vocal_filename: str,
) -> tuple[bool, bool, Optional[str]]:
    """
    Devuelve (is_vocal, is_bus_fx, bus_key) en función del nombre de archivo.

    - is_vocal: sólo la pista vocal principal (vocal_filename).
    - is_bus_fx: nombre tipo bus_<bus_key>_space.wav.
    - bus_key: por ejemplo 'drums', 'guitars', 'lead_vocal', 'fx', etc.
    """
    lower = filename.lower()
    is_vocal = lower == vocal_filename.lower()
    is_bus_fx = False
    bus_key: Optional[str] = None

    # Detectar bus FX: bus_<bus_key>_space.wav
    if lower.startswith("bus_") and "_space" in lower:
        is_bus_fx = True
        # quitar extensión
        stem = Path(filename).stem.lower()  # p.ej. "bus_drums_space"
        core = stem
        if core.startswith("bus_"):
            core = core[4:]  # quita "bus_"
        if core.endswith("_space"):
            core = core[:-6]  # quita "_space"
        bus_key = core or None
        # Un bus de voces NO es "voz principal" a efectos de mastering
        is_vocal = False

    return is_vocal, is_bus_fx, bus_key



@dataclass
class MasteringResult:
    file_path: Path
    sample_rate: int
    num_channels: int
    duration_seconds: float

    peak_dbfs: float
    rms_dbfs: float
    is_vocal: bool
    is_bus_fx: bool
    bus_key: Optional[str]

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
        is_vocal, is_bus_fx, bus_key = _classify_stem_for_mastering(
            wav_path.name, vocal_filename
        )

        # Para el análisis, si es la voz principal y existe la versión afinada, la usamos
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


        # Target de pico recomendado:
        # - buses FX algo más bajos para dejar headroom y no dominar la mezcla
        # - voz principal algo más conservadora
        if is_bus_fx:
            if bus_key == "fx":
                target_peak = -5.0
            else:
                target_peak = -4.0
        elif is_vocal:
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
                is_bus_fx=is_bus_fx,
                bus_key=bus_key,
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
        "is_bus_fx",
        "bus_key",
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
                    "is_bus_fx": "1" if r.is_bus_fx else "0",
                    "bus_key": r.bus_key or "",
                    "recommended_target_peak_dbfs": f"{r.recommended_target_peak_dbfs:.2f}",
                    "recommended_drive_db": f"{r.recommended_drive_db:.2f}",
                }
            )
