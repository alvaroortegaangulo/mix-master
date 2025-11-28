from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import essentia
import essentia.standard as es


@dataclass
class KeyAnalysisResult:
    source_filename: str
    source_path: Path
    sample_rate: int
    duration_seconds: float

    key: str        # e.g. "C", "D#", etc.
    scale: str      # "major" / "minor"
    strength: float # confianza [0,1] aprox
    estimation_method: str = "key_extractor"


def _choose_source_file(media_dir: Path, prefer_full_song: bool = True) -> Path:
    """
    Elige el archivo .wav a usar para análisis global de tonalidad.
    1) Si existe full_song.wav, lo usa.
    2) Si no, elige el .wav de mayor tamaño en bytes.
    """
    if not media_dir.exists() or not media_dir.is_dir():
        raise FileNotFoundError(f"El directorio de medios no existe: {media_dir}")

    full_song = media_dir / "full_song.wav"
    if prefer_full_song and full_song.exists():
        return full_song

    wav_files = list(media_dir.glob("*.wav"))
    if not wav_files:
        raise FileNotFoundError(f"No se encontraron .wav en {media_dir}")

    wav_files = [p for p in wav_files if p.name.lower() != "full_song.wav"]
    if not wav_files:
        raise FileNotFoundError(f"No se encontraron .wav distintos de full_song.wav en {media_dir}")

    return max(wav_files, key=lambda p: p.stat().st_size)


def analyze_key(media_dir: Path, prefer_full_song: bool = True) -> KeyAnalysisResult:
    """
    Analiza la tonalidad global de la canción usando Essentia KeyExtractor.

    :param media_dir: Carpeta con stems y/o full_song.wav.
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

    key_extractor = es.KeyExtractor()
    key, scale, strength = key_extractor(audio)

    result = KeyAnalysisResult(
        source_filename=src_path.name,
        source_path=src_path,
        sample_rate=sample_rate,
        duration_seconds=duration_seconds,
        key=str(key),
        scale=str(scale),
        strength=float(strength),
        estimation_method="key_extractor",
    )
    return result


def export_key_to_csv(result: KeyAnalysisResult, csv_path: Path) -> None:
    """
    Exporta el resultado de tonalidad a un CSV simple.

    Estructura:
      source_filename
      source_path
      sample_rate
      duration_seconds
      key
      scale
      strength
      estimation_method
    """
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "source_filename",
        "source_path",
        "sample_rate",
        "duration_seconds",
        "key",
        "scale",
        "strength",
        "estimation_method",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        writer.writerow({
            "source_filename": result.source_filename,
            "source_path": str(result.source_path),
            "sample_rate": result.sample_rate,
            "duration_seconds": f"{result.duration_seconds:.6f}",
            "key": result.key,
            "scale": result.scale,
            "strength": f"{result.strength:.3f}",
            "estimation_method": result.estimation_method,
        })
