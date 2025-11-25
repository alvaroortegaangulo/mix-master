from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import soundfile as sf


def _safe_dbfs(value: float, floor: float = -120.0) -> float:
    """Convierte magnitud lineal a dBFS con floor seguro."""
    v = float(value)
    if v <= 0.0:
        return floor
    return 20.0 * float(np.log10(v))


@dataclass
class MixBusColorResult:
    mix_path: Path
    sample_rate: int
    num_channels: int
    duration_seconds: float

    peak_dbfs: float
    rms_dbfs: float
    crest_factor_db: float

    recommended_hpf_hz: float
    recommended_saturation_drive_db: float
    recommended_tape_mix: float
    recommended_console_mix: float


def _compute_basic_metrics(path: Path, block_size: int = 262144) -> tuple:
    """
    Calcula peak/rms y duracion leyendo en bloques para minimizar memoria.
    Devuelve (peak_dbfs, rms_dbfs, crest_factor_db, duration_seconds, sr, channels).
    """
    with sf.SoundFile(path, "r") as f:
        sr = int(f.samplerate)
        num_channels = int(f.channels)
        frames_total = int(len(f))

        peak_lin = 0.0
        sum_squares = 0.0
        total_samples = 0

        while True:
            data = f.read(block_size, dtype="float32", always_2d=True)
            if data.size == 0:
                break
            abs_block = np.abs(data)
            peak_lin = max(peak_lin, float(abs_block.max()))
            sum_squares += float(np.sum(data * data))
            total_samples += data.size

        duration_seconds = float(frames_total) / float(sr) if frames_total else float(total_samples) / float(sr * max(num_channels, 1))

        if total_samples == 0:
            return -120.0, -120.0, 0.0, duration_seconds, sr, num_channels

        rms_lin = np.sqrt(sum_squares / float(total_samples))
        peak_dbfs = _safe_dbfs(peak_lin)
        rms_dbfs = _safe_dbfs(rms_lin)
        return peak_dbfs, rms_dbfs, peak_dbfs - rms_dbfs, duration_seconds, sr, num_channels


def analyze_mix_bus_color(mix_path: Path) -> MixBusColorResult:
    """
    Analiza el full mix para decidir un color de bus sutil pero con caracter.
    Se asume que mix_path apunta al full mix ya masterizado por stems.
    """
    mix_path = mix_path.resolve()
    if not mix_path.exists():
        raise FileNotFoundError(f"No se encontro el full mix: {mix_path}")

    peak_dbfs, rms_dbfs, crest_factor_db, duration_seconds, sr, num_channels = _compute_basic_metrics(mix_path)

    if peak_dbfs <= -119.0 and rms_dbfs <= -119.0:
        sat_drive_db = 0.5
        hpf_hz = 28.0
        tape_mix = 0.18
        console_mix = 0.15
        return MixBusColorResult(
            mix_path=mix_path,
            sample_rate=sr,
            num_channels=num_channels,
            duration_seconds=duration_seconds,
            peak_dbfs=peak_dbfs,
            rms_dbfs=rms_dbfs,
            crest_factor_db=crest_factor_db,
            recommended_hpf_hz=hpf_hz,
            recommended_saturation_drive_db=sat_drive_db,
            recommended_tape_mix=tape_mix,
            recommended_console_mix=console_mix,
        )

    if rms_dbfs <= -20.0:
        sat_drive_db = 4.0
    elif rms_dbfs <= -16.0:
        sat_drive_db = 3.0
    elif rms_dbfs <= -14.0:
        sat_drive_db = 2.0
    elif rms_dbfs <= -12.0:
        sat_drive_db = 1.5
    elif rms_dbfs <= -10.0:
        sat_drive_db = 1.0
    else:
        sat_drive_db = 0.5

    if crest_factor_db < 8.0:
        hpf_hz = 30.0
    elif crest_factor_db < 10.0:
        hpf_hz = 27.0
    else:
        hpf_hz = 24.0

    if crest_factor_db >= 13.0:
        tape_mix = 0.35
        console_mix = 0.22
    elif crest_factor_db >= 10.0:
        tape_mix = 0.28
        console_mix = 0.20
    elif crest_factor_db >= 8.0:
        tape_mix = 0.22
        console_mix = 0.18
    else:
        tape_mix = 0.18
        console_mix = 0.15

    return MixBusColorResult(
        mix_path=mix_path,
        sample_rate=sr,
        num_channels=num_channels,
        duration_seconds=duration_seconds,
        peak_dbfs=peak_dbfs,
        rms_dbfs=rms_dbfs,
        crest_factor_db=crest_factor_db,
        recommended_hpf_hz=hpf_hz,
        recommended_saturation_drive_db=sat_drive_db,
        recommended_tape_mix=tape_mix,
        recommended_console_mix=console_mix,
    )


def export_mix_bus_color_to_json(
    result: MixBusColorResult,
    json_path: Path,
) -> Path:
    """Exporta el analisis de mix-bus a JSON (una sola fila)."""
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(result)
    payload["mix_path"] = str(result.mix_path)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return json_path


__all__ = ["MixBusColorResult", "analyze_mix_bus_color", "export_mix_bus_color_to_json"]
