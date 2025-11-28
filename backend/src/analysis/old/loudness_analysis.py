from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional

import numpy as np
import soundfile as sf

try:
    import essentia
    import essentia.standard as es
except ImportError as e:
    raise ImportError(
        "Essentia no esta instalado. Instalala con 'pip install essentia' "
        "y asegurate de tener las dependencias del sistema."
    ) from e


@dataclass
class LoudnessResult:
    """Resultado de analisis de loudness para un stem o full_song."""
    file_path: Path
    is_full_song: bool
    sample_rate: int
    num_channels: int
    duration_seconds: float

    peak_dbfs: float
    rms_dbfs: float
    loudness_stevens: Optional[float]
    replaygain_gain_db: Optional[float]
    target_rms_dbfs: float
    gain_db_to_target_rms: float


def _safe_dbfs(value: float, floor: float = -120.0) -> float:
    value = float(value)
    if value <= 0.0:
        return floor
    return 20.0 * np.log10(value)


def _analyze_single_file(
    path: Path,
    target_rms_dbfs: float,
) -> LoudnessResult:
    """
    Analiza loudness de un unico fichero de audio (peak, RMS, loudness, ReplayGain).
    """
    audio, sr = sf.read(path, dtype="float32", always_2d=True)

    num_samples, num_channels = audio.shape
    duration_seconds = float(num_samples) / float(sr) if sr > 0 else 0.0

    audio_mono = audio.mean(axis=1).astype(np.float32)

    if num_samples == 0 or np.allclose(audio_mono, 0.0):
        peak = 0.0
        rms = 0.0
        loudness_stevens = None
        replaygain_gain_db = None
    else:
        peak = float(np.max(np.abs(audio_mono)))
        rms = float(np.sqrt(np.mean(audio_mono ** 2)))
        loudness_stevens = float(es.Loudness()(audio_mono))
        replaygain_gain_db = float(es.ReplayGain()(audio_mono))

    peak_dbfs = _safe_dbfs(peak)
    rms_dbfs = _safe_dbfs(rms)
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
    """
    if not media_dir.exists() or not media_dir.is_dir():
        raise FileNotFoundError(f"El directorio de medios no existe: {media_dir}")

    return [
        _analyze_single_file(path=wav_path, target_rms_dbfs=target_rms_dbfs)
        for wav_path in sorted(media_dir.glob("*.wav"))
    ]


def export_loudness_to_json(results: List[LoudnessResult], json_path: Path) -> None:
    """
    Exporta los resultados de loudness a JSON (lista de objetos).
    """
    json_path.parent.mkdir(parents=True, exist_ok=True)

    payload = []
    for r in results:
        item = asdict(r)
        item["file_path"] = r.file_path.name
        item["relative_path"] = r.file_path.name
        payload.append(item)

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
