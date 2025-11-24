# C:\mix\src\analysis\loudness_analysis.py

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np
import soundfile as sf

try:
    import essentia
    import essentia.standard as es
except ImportError as e:
    raise ImportError(
        "Essentia no está instalado. Instálalo con 'pip install essentia' "
        "y asegúrate de tener las dependencias del sistema."
    ) from e


@dataclass
class LoudnessResult:
    """Resultado de análisis de loudness para un stem o full_song."""
    file_path: Path
    is_full_song: bool
    sample_rate: int
    num_channels: int
    duration_seconds: float

    # Métricas básicas
    peak_dbfs: float
    rms_dbfs: float

    # Métricas Essentia
    loudness_stevens: Optional[float]  # salida de es.Loudness (no es dB)
    replaygain_gain_db: Optional[float]  # dB de ganancia según ReplayGain

    # Nivelado por RMS hacia un target
    target_rms_dbfs: float
    gain_db_to_target_rms: float  # dB a aplicar para llegar al target


def _safe_dbfs(value: float, floor: float = -120.0) -> float:
    """Convierte magnitud lineal a dBFS, evitando log(0)."""
    value = float(value)
    if value <= 0.0:
        return floor
    return 20.0 * np.log10(value)


def _analyze_single_file(
    path: Path,
    target_rms_dbfs: float,
) -> LoudnessResult:
    """
    Analiza loudness de un único fichero de audio:
    - Lee audio (multi-canal) con soundfile.
    - Downmix a mono para análisis de loudness.
    - Calcula peak, RMS, Loudness (Stevens) y ReplayGain con Essentia.
    """
    # always_2d -> audio.shape = (n_samples, n_channels)
    audio, sr = sf.read(path, dtype="float32", always_2d=True)

    num_samples, num_channels = audio.shape
    duration_seconds = float(num_samples) / float(sr)

    # Downmix simple a mono (media de canales)
    audio_mono = audio.mean(axis=1).astype(np.float32)

    # Evitar problemas con archivos vacíos o casi silenciosos
    if num_samples == 0 or np.allclose(audio_mono, 0.0):
        peak = 0.0
        rms = 0.0
        loudness_stevens = None
        replaygain_gain_db = None
    else:
        # Peak y RMS
        peak = float(np.max(np.abs(audio_mono)))
        rms = float(np.sqrt(np.mean(audio_mono ** 2)))

        # Loudness según Stevens (Essentia.Loudness)
        # Devuelve un escalar proporcional a loudness percibida. 
        loudness_stevens = float(es.Loudness()(audio_mono))

        # ReplayGain -> dB de ganancia para llevar el track a un nivel de referencia. 
        # El valor devuelto se interpreta como “ganancia ideal a aplicar” (puede ser negativo).
        replaygain_gain_db = float(es.ReplayGain()(audio_mono))

    peak_dbfs = _safe_dbfs(peak)
    rms_dbfs = _safe_dbfs(rms)

    # Ganancia recomendada para llevar el stem a un target RMS de mezcla
    # gain_db = target - rms actual
    gain_db_to_target_rms = target_rms_dbfs - rms_dbfs

    return LoudnessResult(
        file_path=path,
        is_full_song=(path.name.lower() == "full_song.wav"),
        sample_rate=int(sr),
        num_channels=int(num_channels),
        duration_seconds=duration_seconds,
        peak_dbfs=peak_dbfs,
        rms_dbfs=rms_dbfs,
        loudness_stevens=loudness_stevens,
        replaygain_gain_db=replaygain_gain_db,
        target_rms_dbfs=target_rms_dbfs,
        gain_db_to_target_rms=gain_db_to_target_rms,
    )


def analyze_loudness(
    media_dir: Path,
    target_rms_dbfs: float = -18.0,
) -> List[LoudnessResult]:
    """
    Analiza loudness de todos los .wav en media_dir.

    :param media_dir: Carpeta con los stems (y opcionalmente full_song.wav).
                      Puede ser C:\\mix\\media o, por ejemplo, una carpeta de
                      stems ya corregidos de DC offset.
    :param target_rms_dbfs: Objetivo de RMS en dBFS para el nivelado base
                            (ej. -18 dBFS típico de mezcla).
    :return: Lista de resultados por archivo.
    """
    if not media_dir.exists() or not media_dir.is_dir():
        raise FileNotFoundError(f"El directorio de medios no existe: {media_dir}")

    results: List[LoudnessResult] = []

    for wav_path in sorted(media_dir.glob("*.wav")):
        result = _analyze_single_file(
            path=wav_path,
            target_rms_dbfs=target_rms_dbfs,
        )
        results.append(result)

    return results


def export_loudness_to_csv(results: List[LoudnessResult], csv_path: Path) -> None:
    """
    Exporta los resultados de loudness a un CSV.

    Estructura del CSV:
        filename
        relative_path
        is_full_song
        sample_rate
        num_channels
        duration_seconds
        peak_dbfs
        rms_dbfs
        loudness_stevens
        replaygain_gain_db
        target_rms_dbfs
        gain_db_to_target_rms
    """
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "filename",
        "relative_path",
        "is_full_song",
        "sample_rate",
        "num_channels",
        "duration_seconds",
        "peak_dbfs",
        "rms_dbfs",
        "loudness_stevens",
        "replaygain_gain_db",
        "target_rms_dbfs",
        "gain_db_to_target_rms",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for r in results:
            writer.writerow({
                "filename": r.file_path.name,
                # Igual que en el módulo de DC offset: usamos solo el nombre.
                "relative_path": r.file_path.name,
                "is_full_song": int(r.is_full_song),
                "sample_rate": r.sample_rate,
                "num_channels": r.num_channels,
                "duration_seconds": f"{r.duration_seconds:.6f}",
                "peak_dbfs": f"{r.peak_dbfs:.2f}",
                "rms_dbfs": f"{r.rms_dbfs:.2f}",
                "loudness_stevens": (
                    "" if r.loudness_stevens is None else f"{r.loudness_stevens:.6f}"
                ),
                "replaygain_gain_db": (
                    "" if r.replaygain_gain_db is None else f"{r.replaygain_gain_db:.2f}"
                ),
                "target_rms_dbfs": f"{r.target_rms_dbfs:.2f}",
                "gain_db_to_target_rms": f"{r.gain_db_to_target_rms:.2f}",
            })
