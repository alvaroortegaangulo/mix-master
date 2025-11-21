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
) -> FullSongRenderResult:
    """
    Mezcla todos los stems WAV de output_media_dir en un único full_song.wav.

    Convención de shapes con Pedalboard:
    - Audio de entrada/salida: (num_channels, num_samples)

    Pasos:
      1. Lee todos los .wav de la carpeta (excepto full_song.wav si ya existe).
      2. Homogeniza a estéreo (2 canales).
      3. Hace padding hasta la longitud máxima y suma.
      4. Aplica un pequeño ajuste de ganancia si hace falta para evitar clipping.
      5. Escribe full_song.wav y devuelve métricas.
    """
    full_song_path = (output_media_dir / full_song_name).resolve()

    stem_paths = [
        p for p in sorted(output_media_dir.glob("*.wav"))
        if p.name.lower() != full_song_name.lower()
    ]

    if not stem_paths:
        raise RuntimeError(f"No se encontraron stems WAV en {output_media_dir} para mezclar.")

    audio_tracks: List[np.ndarray] = []
    sr_ref: Optional[int] = None

    # Leer y homogenizar canales a estéreo (shape: 2, N)
    for stem_path in stem_paths:
        with AudioFile(str(stem_path), "r") as f:
            audio = f.read(f.frames)  # shape: (channels, samples)
            sr = f.samplerate
            ch = f.num_channels

        if sr_ref is None:
            sr_ref = sr
        elif sr != sr_ref:
            raise RuntimeError(
                f"El archivo {stem_path} tiene sample rate {sr} Hz, "
                f"distinto del de referencia {sr_ref} Hz."
            )

        # Aseguramos 2 canales
        if ch == 1:
            # (1, N) -> (2, N)
            audio = np.repeat(audio, 2, axis=0)
        elif ch > 2:
            # Nos quedamos con los dos primeros canales
            audio = audio[:2, :]

        audio_tracks.append(audio.astype(np.float32))

    # Número máximo de samples entre todos los stems
    max_len = max(track.shape[1] for track in audio_tracks)

    # Mezcla estéreo: shape (2, max_len)
    mix = np.zeros((2, max_len), dtype=np.float32)

    for track in audio_tracks:
        length = track.shape[1]  # número de samples de este stem
        mix[:, :length] += track

    # Métricas antes de aplicar ganancia de seguridad
    peak_before = float(np.max(np.abs(mix))) if mix.size > 0 else 0.0
    rms_before = float(np.sqrt(np.mean(mix**2))) if mix.size > 0 else 0.0

    clipped_before = peak_before > 1.0
    mix_gain_db = 0.0

    # Evitar clipping en el master: dejamos un margen de ~0.98
    if peak_before > 1.0:
        scale = 0.98 / peak_before
        mix *= scale
        mix_gain_db += _safe_dbfs(scale)

    peak_after = float(np.max(np.abs(mix))) if mix.size > 0 else 0.0
    rms_after = float(np.sqrt(np.mean(mix**2))) if mix.size > 0 else 0.0

    clipped_after = peak_after > 1.0

    peak_dbfs = _safe_dbfs(peak_after)
    rms_dbfs = _safe_dbfs(rms_after)

    assert sr_ref is not None
    with AudioFile(str(full_song_path), "w", sr_ref, 2) as f:
        f.write(mix)

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
