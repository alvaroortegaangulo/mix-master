from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import soundfile as sf


def _safe_dbfs(value: float, floor: float = -120.0) -> float:
    """Convierte magnitud lineal a dBFS con un floor seguro para ceros."""
    v = float(value)
    if v <= 0.0:
        return floor
    return 20.0 * np.log10(v)


def _classify_stem_for_mastering(
    filename: str,
    vocal_filename: str,
) -> Tuple[bool, bool, Optional[str]]:
    """
    Devuelve (is_vocal, is_bus_fx, bus_key) en funcion del nombre de archivo.

    - is_vocal: solo la pista vocal principal (vocal_filename).
    - is_bus_fx: nombre tipo bus_<bus_key>_space.wav.
    - bus_key: por ejemplo 'drums', 'guitars', 'lead_vocal', 'fx', etc.
    """
    lower = filename.lower()
    is_vocal = lower == vocal_filename.lower()
    is_bus_fx = False
    bus_key: Optional[str] = None

    if lower.startswith("bus_") and "_space" in lower:
        is_bus_fx = True
        stem = Path(filename).stem.lower()  # ej: "bus_drums_space"
        core = stem[4:] if stem.startswith("bus_") else stem
        core = core[:-6] if core.endswith("_space") else core
        bus_key = core or None
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


def _compute_peak_rms(path: Path, block_size: int = 131072) -> Tuple[float, float, int, int, float]:
    """
    Calcula peak/rms y metadatos leyendo en bloques para minimizar memoria.
    Devuelve (peak_dbfs, rms_dbfs, sample_rate, num_channels, duration_seconds).
    """
    peak = 0.0
    sum_squares = 0.0
    total_samples = 0

    with sf.SoundFile(path, "r") as f:
        sr = int(f.samplerate)
        num_channels = int(f.channels)
        frames = int(len(f))

        while True:
            data = f.read(block_size, dtype="float32", always_2d=True)
            if data.size == 0:
                break
            abs_block = np.abs(data)
            peak = max(peak, float(abs_block.max()))
            sum_squares += float(np.sum(data * data))
            total_samples += data.size

    if total_samples == 0:
        return _safe_dbfs(0.0), _safe_dbfs(0.0), sr, num_channels, 0.0

    rms = np.sqrt(sum_squares / float(total_samples))
    duration_seconds = float(frames) / float(sr) if frames else float(total_samples) / float(sr * num_channels)
    return _safe_dbfs(peak), _safe_dbfs(rms), sr, num_channels, duration_seconds


def analyze_mastering(
    media_dir: Path,
    vocal_tuning_media_dir: Optional[Path] = None,
    vocal_filename: str = "vocal.wav",
) -> List[MasteringResult]:
    """
    Analiza todos los stems de media_dir (static_mix_dyn) y usa la voz afinada
    si esta disponible para la pista principal.
    """
    if not media_dir.exists() or not media_dir.is_dir():
        raise FileNotFoundError(f"El directorio de medios no existe: {media_dir}")

    results: List[MasteringResult] = []
    for wav_path in sorted(media_dir.glob("*.wav")):
        is_vocal, is_bus_fx, bus_key = _classify_stem_for_mastering(
            wav_path.name, vocal_filename
        )

        analysis_path = wav_path
        if is_vocal and vocal_tuning_media_dir is not None:
            tuned_path = vocal_tuning_media_dir / vocal_filename
            if tuned_path.exists():
                analysis_path = tuned_path

        peak_dbfs, rms_dbfs, sr, num_channels, duration_seconds = _compute_peak_rms(analysis_path)

        # ----------------------------------------------------------
        # Target MUCHO MÁS CONSERVADOR (pensado para stems, no loudness war)
        # ----------------------------------------------------------
        if is_bus_fx:
            # FX más bajos que el resto
            target_peak = -7.0 if bus_key == "fx" else -6.0
        elif is_vocal:
            # Voz 1 dB por debajo de lo que tenías (-3 en vez de -2)
            target_peak = -3.0
        else:
            # Instrumentos / buses: en torno a -3.5 / -4
            target_peak = -3.5

        # Drive recomendado muy acotado: ±6 dB máx
        drive_db = target_peak - peak_dbfs
        drive_db = max(min(drive_db, 6.0), -6.0)

        results.append(
            MasteringResult(
                file_path=wav_path,
                sample_rate=sr,
                num_channels=num_channels,
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


def export_mastering_to_json(
    results: List[MasteringResult],
    json_path: Path,
) -> Path:
    """Exporta el analisis de mastering a JSON."""
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = []
    for r in results:
        row = asdict(r)
        row["file_path"] = str(r.file_path)
        row["filename"] = r.file_path.name
        row["relative_path"] = r.file_path.name
        payload.append(row)

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return json_path
