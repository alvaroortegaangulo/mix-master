from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np
from pedalboard.io import AudioFile


def _safe_dbfs(value: float, floor: float = -120.0) -> float:
    """Convierte magnitud lineal a dBFS evitando log(0)."""
    value = float(value)
    if value <= 0.0:
        return floor
    return 20.0 * np.log10(value)


@dataclass
class FullSongRenderResult:
    """Resultado de generar el full_song a partir de varios stems ya corregidos."""
    filename: str
    output_path: Path
    sample_rate: int
    num_channels: int
    duration_seconds: float
    mix_gain_db: float
    peak_dbfs: float
    rms_dbfs: float
    clipped_before_mix_gain: bool
    clipped_after_mix_gain: bool


def mix_corrected_stems_to_full_song(
    output_media_dir: Path,
    full_song_name: str = "full_song.wav",
    block_size: int = 65536,
) -> FullSongRenderResult:
    """
    Mezcla todos los stems WAV de output_media_dir en un único full_song.wav,
    leyendo por bloques para no cargar todos los stems en memoria.

    Estrategia:
      - Pasada 1 (solo lectura): calcula el peak y RMS del mix sin ganancia
        de seguridad, para decidir el factor de escala (mix_gain_db).
      - Pasada 2: vuelve a leer por bloques, aplica el scale, escribe el
        fichero final y calcula métricas "after".
    """

    output_media_dir = Path(output_media_dir)
    output_media_dir.mkdir(parents=True, exist_ok=True)

    full_song_path = output_media_dir / full_song_name

    # Listar stems: todos los .wav menos el full_song.wav (por si existe)
    stem_paths = sorted(
        p for p in output_media_dir.glob("*.wav") if p.name != full_song_name
    )

    if not stem_paths:
        raise RuntimeError(
            f"No se encontraron stems WAV en {output_media_dir} para el mixdown."
        )

    # ----------------------------------------------------------------------
    # 1) Leer SOLO metadatos: sample rate y número de frames de cada stem
    # ----------------------------------------------------------------------
    sr_ref: Optional[int] = None
    max_len: int = 0

    for stem_path in stem_paths:
        with AudioFile(str(stem_path), "r") as f:
            sr = f.samplerate
            frames = f.frames

        if sr_ref is None:
            sr_ref = sr
        elif sr != sr_ref:
            raise RuntimeError(
                f"El archivo {stem_path} tiene sample rate {sr} Hz, "
                f"distinto del de referencia {sr_ref} Hz."
            )

        if frames > max_len:
            max_len = frames

    assert sr_ref is not None, "No se pudo determinar el sample rate de referencia"

    # ----------------------------------------------------------------------
    # 2) Pasada 1: calcular peak y RMS del mix sin ganancia de seguridad
    # ----------------------------------------------------------------------
    peak_before = 0.0
    sum_squares_before = 0.0
    total_samples_before = 0  # cuenta canales * samples

    files = [AudioFile(str(p), "r") for p in stem_paths]
    try:
        while True:
            # Buffer de mezcla para este bloque: (2, block_size)
            mix_block = np.zeros((2, block_size), dtype=np.float32)
            block_len = 0

            for f in files:
                chunk = f.read(block_size)  # (channels, samples)
                if chunk.size == 0:
                    continue

                ch, n = chunk.shape

                # Homogeneizar a 2 canales
                if ch == 1:
                    chunk = np.repeat(chunk, 2, axis=0)
                elif ch > 2:
                    chunk = chunk[:2, :]

                n = chunk.shape[1]
                if n == 0:
                    continue

                if n > block_len:
                    block_len = n

                mix_block[:, :n] += chunk.astype(np.float32)

            if block_len == 0:
                # No queda nada que leer en ningún stem
                break

            block = mix_block[:, :block_len]

            # Peak por bloque
            b_peak = float(np.max(np.abs(block)))
            if b_peak > peak_before:
                peak_before = b_peak

            # RMS acumulado: mean(mix**2) sobre todos los canales
            sum_squares_before += float(np.sum(block**2))
            total_samples_before += block.size  # 2 * block_len
    finally:
        for f in files:
            f.close()

    if total_samples_before > 0:
        rms_before = float(
            np.sqrt(sum_squares_before / float(total_samples_before))
        )
    else:
        rms_before = 0.0

    clipped_before = peak_before > 1.0
    mix_gain_db = 0.0
    scale = 1.0

    # Margen de seguridad: si el peak supera 0 dBFS, escalamos a 0.98
    if peak_before > 1.0:
        scale = 0.98 / peak_before
        mix_gain_db = 20.0 * np.log10(scale)

    # ----------------------------------------------------------------------
    # 3) Pasada 2: aplicar scale, escribir WAV final y calcular métricas "after"
    # ----------------------------------------------------------------------
    peak_after = 0.0
    sum_squares_after = 0.0
    total_samples_after = 0

    files = [AudioFile(str(p), "r") for p in stem_paths]
    try:
        with AudioFile(str(full_song_path), "w", sr_ref, 2) as f_out:
            while True:
                mix_block = np.zeros((2, block_size), dtype=np.float32)
                block_len = 0

                for f in files:
                    chunk = f.read(block_size)
                    if chunk.size == 0:
                        continue

                    ch, n = chunk.shape

                    if ch == 1:
                        chunk = np.repeat(chunk, 2, axis=0)
                    elif ch > 2:
                        chunk = chunk[:2, :]

                    n = chunk.shape[1]
                    if n == 0:
                        continue

                    if n > block_len:
                        block_len = n

                    mix_block[:, :n] += chunk.astype(np.float32)

                if block_len == 0:
                    break

                block = mix_block[:, :block_len] * scale

                # Métricas after
                b_peak = float(np.max(np.abs(block))) if block.size > 0 else 0.0
                if b_peak > peak_after:
                    peak_after = b_peak

                sum_squares_after += float(np.sum(block**2))
                total_samples_after += block.size

                # Escribir bloque al WAV final
                f_out.write(block)
    finally:
        for f in files:
            f.close()

    if total_samples_after > 0:
        rms_after = float(
            np.sqrt(sum_squares_after / float(total_samples_after))
        )
    else:
        rms_after = 0.0

    clipped_after = peak_after > 1.0

    peak_dbfs = _safe_dbfs(peak_after)
    rms_dbfs = _safe_dbfs(rms_after)

    duration_seconds = float(max_len) / float(sr_ref)

    return FullSongRenderResult(
        filename=full_song_name,
        output_path=full_song_path,
        sample_rate=sr_ref,
        num_channels=2,
        duration_seconds=duration_seconds,
        mix_gain_db=mix_gain_db,
        peak_dbfs=peak_dbfs,
        rms_dbfs=rms_dbfs,
        clipped_before_mix_gain=clipped_before,
        clipped_after_mix_gain=clipped_after,
    )
