from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import soundfile as sf


def _safe_dbfs(value: float, floor: float = -120.0) -> float:
    """Convierte magnitud lineal a dBFS con un floor seguro para ceros."""
    v = float(value)
    if v <= 0.0:
        return floor
    return 20.0 * float(np.log10(v))


@dataclass
class MasterStereoResult:
    mix_path: Path
    sample_rate: int
    num_channels: int
    duration_seconds: float

    peak_dbfs: float
    rms_dbfs: float
    crest_factor_db: float

    mid_peak_dbfs: float
    mid_rms_dbfs: float
    side_peak_dbfs: float
    side_rms_dbfs: float
    side_to_mid_ratio_db: float  # side - mid (en dB)

    recommended_mid_hpf_hz: float
    recommended_side_hpf_hz: float
    recommended_side_gain_db: float
    recommended_mid_comp_threshold_dbfs: float
    recommended_mid_comp_ratio: float
    recommended_side_ir_mix: float


def _compute_ms_metrics(path: Path, block_size: int = 131072) -> tuple:
    """
    Calcula en streaming las métricas Mid/Side para reducir uso de memoria.
    Devuelve:
      (peak_dbfs, rms_dbfs, crest_factor_db,
       mid_peak_dbfs, mid_rms_dbfs, side_peak_dbfs, side_rms_dbfs,
       duration_seconds, sample_rate, num_channels)
    """
    with sf.SoundFile(path, "r") as f:
        sr = int(f.samplerate)
        num_channels = int(f.channels)
        frames_total = int(len(f))

        peak_lin = 0.0
        sum_squares = 0.0
        mid_peak_lin = 0.0
        mid_sum_squares = 0.0
        side_peak_lin = 0.0
        side_sum_squares = 0.0
        total_samples = 0

        while True:
            data = f.read(block_size, dtype="float32", always_2d=True)
            if data.size == 0:
                break

            L = data[:, 0]
            R = data[:, 0] if data.shape[1] == 1 else data[:, 1]

            full_abs = np.abs(data)
            peak_lin = max(peak_lin, float(full_abs.max()))
            sum_squares += float(np.sum(data * data))
            total_samples += data.size

            mid = 0.5 * (L + R)
            side = 0.5 * (L - R)

            mid_abs = np.abs(mid)
            side_abs = np.abs(side)

            mid_peak_lin = max(mid_peak_lin, float(mid_abs.max()))
            side_peak_lin = max(side_peak_lin, float(side_abs.max()))
            mid_sum_squares += float(np.sum(mid * mid))
            side_sum_squares += float(np.sum(side * side))

        duration_seconds = float(frames_total) / float(sr) if frames_total else float(total_samples) / float(sr * max(num_channels, 1))

        if total_samples == 0:
            return (
                -120.0,
                -120.0,
                0.0,
                -120.0,
                -120.0,
                -120.0,
                -120.0,
                duration_seconds,
                sr,
                num_channels,
            )

        rms_lin = np.sqrt(sum_squares / float(total_samples))
        mid_rms_lin = np.sqrt(mid_sum_squares / float(total_samples))
        side_rms_lin = np.sqrt(side_sum_squares / float(total_samples))

        peak_dbfs = _safe_dbfs(peak_lin)
        rms_dbfs = _safe_dbfs(rms_lin)
        crest_factor_db = peak_dbfs - rms_dbfs

        mid_peak_dbfs = _safe_dbfs(mid_peak_lin)
        mid_rms_dbfs = _safe_dbfs(mid_rms_lin)
        side_peak_dbfs = _safe_dbfs(side_peak_lin)
        side_rms_dbfs = _safe_dbfs(side_rms_lin)

        return (
            peak_dbfs,
            rms_dbfs,
            crest_factor_db,
            mid_peak_dbfs,
            mid_rms_dbfs,
            side_peak_dbfs,
            side_rms_dbfs,
            duration_seconds,
            sr,
            num_channels,
        )


def analyze_master_stereo(mix_path: Path) -> MasterStereoResult:
    """
    Analiza el full mix (estéreo) en Mid/Side y propone ajustes de imagen.
    """
    mix_path = mix_path.resolve()
    if not mix_path.exists():
        raise FileNotFoundError(f"No se encontro el full mix: {mix_path}")

    (
        peak_dbfs,
        rms_dbfs,
        crest_factor_db,
        mid_peak_dbfs,
        mid_rms_dbfs,
        side_peak_dbfs,
        side_rms_dbfs,
        duration_seconds,
        sr,
        num_channels,
    ) = _compute_ms_metrics(mix_path)

    if peak_dbfs <= -119.0 and rms_dbfs <= -119.0:
        # Mezcla vacía -> defaults seguros
        side_to_mid_ratio_db = -60.0
        recommended_mid_hpf_hz = 25.0
        recommended_side_hpf_hz = 120.0
        recommended_side_gain_db = 0.0
        recommended_mid_comp_threshold_dbfs = -18.0
        recommended_mid_comp_ratio = 1.3
        recommended_side_ir_mix = 0.18
        return MasterStereoResult(
            mix_path=mix_path,
            sample_rate=sr,
            num_channels=num_channels,
            duration_seconds=duration_seconds,
            peak_dbfs=peak_dbfs,
            rms_dbfs=rms_dbfs,
            crest_factor_db=crest_factor_db,
            mid_peak_dbfs=mid_peak_dbfs,
            mid_rms_dbfs=mid_rms_dbfs,
            side_peak_dbfs=side_peak_dbfs,
            side_rms_dbfs=side_rms_dbfs,
            side_to_mid_ratio_db=side_to_mid_ratio_db,
            recommended_mid_hpf_hz=recommended_mid_hpf_hz,
            recommended_side_hpf_hz=recommended_side_hpf_hz,
            recommended_side_gain_db=recommended_side_gain_db,
            recommended_mid_comp_threshold_dbfs=recommended_mid_comp_threshold_dbfs,
            recommended_mid_comp_ratio=recommended_mid_comp_ratio,
            recommended_side_ir_mix=recommended_side_ir_mix,
        )

    side_to_mid_ratio_db = side_rms_dbfs - mid_rms_dbfs

    target_ratio_db = -6.0
    desired_gain_db = target_ratio_db - side_to_mid_ratio_db
    recommended_side_gain_db = float(np.clip(desired_gain_db, -2.5, 2.5))

    if crest_factor_db < 8.0:
        recommended_mid_hpf_hz = 30.0
    elif crest_factor_db < 11.0:
        recommended_mid_hpf_hz = 26.0
    else:
        recommended_mid_hpf_hz = 22.0

    recommended_side_hpf_hz = 120.0

    if crest_factor_db >= 13.0:
        recommended_mid_comp_ratio = 1.6
        recommended_mid_comp_threshold_dbfs = -18.0
    elif crest_factor_db >= 10.0:
        recommended_mid_comp_ratio = 1.4
        recommended_mid_comp_threshold_dbfs = -17.0
    else:
        recommended_mid_comp_ratio = 1.3
        recommended_mid_comp_threshold_dbfs = -16.0

    if side_to_mid_ratio_db <= -9.0:
        recommended_side_ir_mix = 0.22
    elif side_to_mid_ratio_db <= -7.0:
        recommended_side_ir_mix = 0.20
    else:
        recommended_side_ir_mix = 0.16

    return MasterStereoResult(
        mix_path=mix_path,
        sample_rate=sr,
        num_channels=num_channels,
        duration_seconds=duration_seconds,
        peak_dbfs=peak_dbfs,
        rms_dbfs=rms_dbfs,
        crest_factor_db=crest_factor_db,
        mid_peak_dbfs=mid_peak_dbfs,
        mid_rms_dbfs=mid_rms_dbfs,
        side_peak_dbfs=side_peak_dbfs,
        side_rms_dbfs=side_rms_dbfs,
        side_to_mid_ratio_db=side_to_mid_ratio_db,
        recommended_mid_hpf_hz=recommended_mid_hpf_hz,
        recommended_side_hpf_hz=recommended_side_hpf_hz,
        recommended_side_gain_db=recommended_side_gain_db,
        recommended_mid_comp_threshold_dbfs=recommended_mid_comp_threshold_dbfs,
        recommended_mid_comp_ratio=recommended_mid_comp_ratio,
        recommended_side_ir_mix=recommended_side_ir_mix,
    )


def export_master_stereo_to_json(
    result: MasterStereoResult,
    json_path: Path,
) -> Path:
    """Exporta el analisis Mid/Side a JSON (una sola fila)."""
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(result)
    payload["mix_path"] = str(result.mix_path)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return json_path


__all__ = ["MasterStereoResult", "analyze_master_stereo", "export_master_stereo_to_json"]
