# C:\mix\src\analysis\dc_offset_detection.py

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List

import numpy as np
import soundfile as sf

@dataclass
class DcOffsetResult:
    """Resultado de análisis de DC offset para un archivo de audio."""
    file_path: Path
    is_full_song: bool
    sample_rate: int
    num_channels: int
    duration_seconds: float
    dc_offsets: List[float]          # offset por canal (en -1..1)
    max_abs_dc_offset: float         # máximo |offset| entre canales


def _analyze_single_file(path: Path) -> DcOffsetResult:
    """
    Analiza el DC offset de un único fichero WAV.

    Calcula la media de las muestras por canal (DC offset) y algunos metadatos básicos.
    """
    # always_2d=True -> shape: (n_muestras, n_canales)
    audio, sr = sf.read(path, always_2d=True)
    num_channels = audio.shape[1]
    num_samples = audio.shape[0]

    # Media por canal (float32 / float64 en el rango -1..1 en la mayoría de casos)
    dc_offsets = audio.mean(axis=0).astype(float)
    max_abs_dc_offset = float(np.max(np.abs(dc_offsets)))
    duration_seconds = float(num_samples / sr)

    return DcOffsetResult(
        file_path=path,
        is_full_song=(path.name.lower() == "full_song.wav"),
        sample_rate=int(sr),
        num_channels=int(num_channels),
        duration_seconds=duration_seconds,
        dc_offsets=dc_offsets.tolist(),
        max_abs_dc_offset=max_abs_dc_offset,
    )


def detect_dc_offset(media_dir: Path) -> List[DcOffsetResult]:
    """
    Detecta el DC offset en todos los .wav dentro de media_dir.

    :param media_dir: Carpeta donde están los stems y full_song.wav.
    :return: Lista de resultados por archivo.
    """
    if not media_dir.exists() or not media_dir.is_dir():
        raise FileNotFoundError(f"El directorio de medios no existe: {media_dir}")

    results: List[DcOffsetResult] = []

    for wav_path in sorted(media_dir.glob("*.wav")):
        result = _analyze_single_file(wav_path)
        results.append(result)

    return results


def export_dc_offset_to_csv(results: List[DcOffsetResult], csv_path: Path) -> None:
    """
    Exporta los resultados de DC offset a un CSV.

    Estructura del CSV:
        filename              -> nombre del archivo (solo nombre, sin ruta)
        relative_path         -> ruta relativa a la carpeta media (si la conoces en el main)
        is_full_song          -> True/False
        sample_rate           -> Hz
        num_channels
        duration_seconds
        dc_offsets            -> lista JSON de offsets por canal (ej: [0.0001, -0.0002])
        max_abs_dc_offset     -> máximo |offset| entre canales
    """
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "filename",
        "relative_path",
        "is_full_song",
        "sample_rate",
        "num_channels",
        "duration_seconds",
        "dc_offsets",
        "max_abs_dc_offset",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for r in results:
            # relative_path queda a rellenar en el main si quieres algo concreto;
            # aquí asumimos que guardas solo el nombre y dejas "" o igual al filename.
            writer.writerow({
                "filename": r.file_path.name,
                "relative_path": r.file_path.name,  # o algo relativo a media_dir si lo pasas
                "is_full_song": int(r.is_full_song),  # 1/0 para facilitar lectura posterior
                "sample_rate": r.sample_rate,
                "num_channels": r.num_channels,
                "duration_seconds": f"{r.duration_seconds:.6f}",
                "dc_offsets": json.dumps(r.dc_offsets),
                "max_abs_dc_offset": f"{r.max_abs_dc_offset:.8f}",
            })
