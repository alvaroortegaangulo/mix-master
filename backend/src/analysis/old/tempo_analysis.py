from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import essentia
import essentia.standard as es


@dataclass
class TempoAnalysisResult:
    source_filename: str
    source_path: Path
    sample_rate: int
    duration_seconds: float

    bpm: float
    bpm_confidence: float
    beat_positions: list[float]  # en segundos
    estimation_method: str = "rhythm_extractor_2013"


def _choose_source_file(media_dir: Path, prefer_full_song: bool = True) -> Path:
    """
    Elige el archivo .wav a usar para análisis global de tempo.
    1) Si existe full_song.wav, lo usa.
    2) Si no, elige el .wav de mayor tamaño en bytes (suele ser el más largo).
    """
    if not media_dir.exists() or not media_dir.is_dir():
        raise FileNotFoundError(f"El directorio de medios no existe: {media_dir}")

    full_song = media_dir / "full_song.wav"
    if prefer_full_song and full_song.exists():
        return full_song

    wav_files = list(media_dir.glob("*.wav"))
    if not wav_files:
        raise FileNotFoundError(f"No se encontraron .wav en {media_dir}")

    # Excluir full_song si existe pero prefer_full_song=False
    wav_files = [p for p in wav_files if p.name.lower() != "full_song.wav"]
    if not wav_files:
        raise FileNotFoundError(f"No se encontraron .wav distintos de full_song.wav en {media_dir}")

    return max(wav_files, key=lambda p: p.stat().st_size)


def analyze_tempo(media_dir: Path, prefer_full_song: bool = True) -> TempoAnalysisResult:
    """
    Analiza el tempo global de la canción usando Essentia RhythmExtractor2013.

    :param media_dir: Carpeta con stems y/o full_song.wav (crudos).
    :param prefer_full_song: Si True, usa full_song.wav si existe.
    """
    essentia.log.infoActive = False
    essentia.log.warningActive = False

    src_path = _choose_source_file(media_dir, prefer_full_song=prefer_full_song)

    # Cargamos audio en mono a 44.1 kHz
    loader = es.MonoLoader(filename=str(src_path), sampleRate=44100)
    audio = loader()

    duration_seconds = float(len(audio)) / 44100.0
    sample_rate = 44100

    # RhythmExtractor2013 (multifeature)
    rhythm_extractor = es.RhythmExtractor2013(method="multifeature")
    bpm, beat_positions, beat_confidence, _, _ = rhythm_extractor(audio)

    result = TempoAnalysisResult(
        source_filename=src_path.name,
        source_path=src_path,
        sample_rate=sample_rate,
        duration_seconds=duration_seconds,
        bpm=float(bpm),
        bpm_confidence=float(beat_confidence),
        beat_positions=list(map(float, beat_positions)),
        estimation_method="rhythm_extractor_2013",
    )
    return result


def export_tempo_to_csv(result: TempoAnalysisResult, csv_path: Path) -> None:
    """
    Exporta el resultado de tempo a un CSV simple.

    Estructura:
      source_filename
      source_path
      sample_rate
      duration_seconds
      bpm
      bpm_confidence
      beat_positions_json (lista serializada como texto)
    """
    import json

    csv_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "source_filename",
        "source_path",
        "sample_rate",
        "duration_seconds",
        "bpm",
        "bpm_confidence",
        "estimation_method",
        "beat_positions_json",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        writer.writerow({
            "source_filename": result.source_filename,
            "source_path": str(result.source_path),
            "sample_rate": result.sample_rate,
            "duration_seconds": f"{result.duration_seconds:.6f}",
            "bpm": f"{result.bpm:.2f}",
            "bpm_confidence": f"{result.bpm_confidence:.3f}",
            "estimation_method": result.estimation_method,
            "beat_positions_json": json.dumps(result.beat_positions),
        })
