from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List

import numpy as np
import soundfile as sf


@dataclass
class DcOffsetResult:
    """Resultado de analisis de DC offset para un archivo de audio."""
    file_path: Path
    is_full_song: bool
    sample_rate: int
    num_channels: int
    duration_seconds: float
    dc_offsets: List[float]
    max_abs_dc_offset: float


def _analyze_single_file(path: Path) -> DcOffsetResult:
    """
    Analiza el DC offset de un unico fichero WAV usando streaming para no cargar todo en memoria.
    """
    with sf.SoundFile(str(path), mode="r") as f:
        sr = f.samplerate
        num_channels = f.channels
        total_frames = f.frames

        block_size = 262144  # frames; bloques grandes reducen I/O
        sums = np.zeros(num_channels, dtype=np.float64)
        frames_read = 0

        while True:
            block = f.read(block_size, dtype="float32", always_2d=True)
            if block.size == 0:
                break
            sums += block.sum(axis=0, dtype=np.float64)
            frames_read += block.shape[0]

        if frames_read > 0:
            dc_offsets = (sums / frames_read).astype(float)
        else:
            dc_offsets = np.zeros(num_channels, dtype=float)

    max_abs_dc_offset = float(np.max(np.abs(dc_offsets))) if dc_offsets.size else 0.0
    duration_seconds = float(total_frames / sr) if sr > 0 else 0.0

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
    """
    if not media_dir.exists() or not media_dir.is_dir():
        raise FileNotFoundError(f"El directorio de medios no existe: {media_dir}")

    return [_analyze_single_file(p) for p in sorted(media_dir.glob("*.wav"))]


def export_dc_offset_to_json(results: List[DcOffsetResult], json_path: Path) -> None:
    """
    Exporta los resultados de DC offset a JSON (lista de objetos).
    """
    json_path.parent.mkdir(parents=True, exist_ok=True)

    payload = []
    for r in results:
        item = asdict(r)
        item["file_path"] = r.file_path.name  # solo el nombre del archivo
        item["relative_path"] = r.file_path.name
        payload.append(item)

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
