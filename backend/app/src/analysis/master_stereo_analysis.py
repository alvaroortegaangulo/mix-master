# src/analysis/master_stereo_analysis.py
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf


def _safe_dbfs(value: float, floor: float = -120.0) -> float:
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


def analyze_master_stereo(mix_path: Path) -> MasterStereoResult:
    """
    Analiza el full mix (stéreo) en Mid/Side y propone ajustes de imagen:

      - RMS/peak de Mid y Side.
      - Ratio Side/Mid en dB.
      - Ganancia recomendada de Side (para anchura).
      - HPF en Mid y Side.
      - Compresión recomendada en Mid.
    """
    mix_path = mix_path.resolve()
    if not mix_path.exists():
        raise FileNotFoundError(f"No se encontró el full mix: {mix_path}")

    audio, sr = sf.read(str(mix_path), dtype="float32", always_2d=True)
    num_samples, num_channels = audio.shape
    duration_seconds = float(num_samples) / float(sr) if num_samples > 0 else 0.0

    if num_samples == 0:
        # Mezcla vacía -> todo a floor
        peak_dbfs = rms_dbfs = crest_factor_db = -120.0
        mid_peak_dbfs = mid_rms_dbfs = side_peak_dbfs = side_rms_dbfs = -120.0
        side_to_mid_ratio_db = -60.0
        # Defaults seguros
        recommended_mid_hpf_hz = 25.0
        recommended_side_hpf_hz = 120.0
        recommended_side_gain_db = 0.0
        recommended_mid_comp_threshold_dbfs = -18.0
        recommended_mid_comp_ratio = 1.3
        recommended_side_ir_mix = 0.18
        return MasterStereoResult(
            mix_path=mix_path,
            sample_rate=int(sr),
            num_channels=int(num_channels),
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

    # Métricas globales L/R
    if num_channels == 1:
        # Mono: Mid = canal único, Side = 0
        L = audio[:, 0]
        R = audio[:, 0]
    else:
        L = audio[:, 0]
        R = audio[:, 1]

    full = audio
    peak_lin = float(np.max(np.abs(full)))
    rms_lin = float(np.sqrt(np.mean(full**2)))

    peak_dbfs = _safe_dbfs(peak_lin)
    rms_dbfs = _safe_dbfs(rms_lin)
    crest_factor_db = peak_dbfs - rms_dbfs

    # Matriz Mid/Side (estándar)
    mid = 0.5 * (L + R)
    side = 0.5 * (L - R)

    mid_peak_lin = float(np.max(np.abs(mid)))
    mid_rms_lin = float(np.sqrt(np.mean(mid**2)))
    side_peak_lin = float(np.max(np.abs(side)))
    side_rms_lin = float(np.sqrt(np.mean(side**2)))

    mid_peak_dbfs = _safe_dbfs(mid_peak_lin)
    mid_rms_dbfs = _safe_dbfs(mid_rms_lin)
    side_peak_dbfs = _safe_dbfs(side_peak_lin)
    side_rms_dbfs = _safe_dbfs(side_rms_lin)

    side_to_mid_ratio_db = side_rms_dbfs - mid_rms_dbfs  # normalmente negativo

    # ---------------------------------------------------
    # Heurísticas:
    #   - Objetivo de ratio Side/Mid ≈ -6 dB.
    #   - Ganancia de Side limitada a ±2.5 dB.
    # ---------------------------------------------------
    target_ratio_db = -6.0
    desired_gain_db = target_ratio_db - side_to_mid_ratio_db
    recommended_side_gain_db = float(np.clip(desired_gain_db, -2.5, 2.5))

    # HPF de Mid: muy suave, depende un poco del crest factor
    if crest_factor_db < 8.0:
        recommended_mid_hpf_hz = 30.0
    elif crest_factor_db < 11.0:
        recommended_mid_hpf_hz = 26.0
    else:
        recommended_mid_hpf_hz = 22.0

    # HPF de Side: graves laterales recortados por seguridad
    recommended_side_hpf_hz = 120.0

    # Compresión de Mid: más ratio si el mix es muy dinámico
    if crest_factor_db >= 13.0:
        recommended_mid_comp_ratio = 1.6
        recommended_mid_comp_threshold_dbfs = -18.0
    elif crest_factor_db >= 10.0:
        recommended_mid_comp_ratio = 1.4
        recommended_mid_comp_threshold_dbfs = -17.0
    else:
        recommended_mid_comp_ratio = 1.3
        recommended_mid_comp_threshold_dbfs = -16.0

    # Mix de IR en Side: valor base bastante conservador
    if side_to_mid_ratio_db <= -9.0:
        recommended_side_ir_mix = 0.22
    elif side_to_mid_ratio_db <= -7.0:
        recommended_side_ir_mix = 0.20
    else:
        recommended_side_ir_mix = 0.16

    return MasterStereoResult(
        mix_path=mix_path,
        sample_rate=int(sr),
        num_channels=int(num_channels),
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


def export_master_stereo_to_csv(
    result: MasterStereoResult,
    csv_path: Path,
) -> None:
    """
    Exporta el análisis Mid/Side a CSV (una sola fila).
    """
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "mix_path",
        "sample_rate",
        "num_channels",
        "duration_seconds",
        "peak_dbfs",
        "rms_dbfs",
        "crest_factor_db",
        "mid_peak_dbfs",
        "mid_rms_dbfs",
        "side_peak_dbfs",
        "side_rms_dbfs",
        "side_to_mid_ratio_db",
        "recommended_mid_hpf_hz",
        "recommended_side_hpf_hz",
        "recommended_side_gain_db",
        "recommended_mid_comp_threshold_dbfs",
        "recommended_mid_comp_ratio",
        "recommended_side_ir_mix",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(
            {
                "mix_path": str(result.mix_path),
                "sample_rate": result.sample_rate,
                "num_channels": result.num_channels,
                "duration_seconds": f"{result.duration_seconds:.6f}",
                "peak_dbfs": f"{result.peak_dbfs:.2f}",
                "rms_dbfs": f"{result.rms_dbfs:.2f}",
                "crest_factor_db": f"{result.crest_factor_db:.2f}",
                "mid_peak_dbfs": f"{result.mid_peak_dbfs:.2f}",
                "mid_rms_dbfs": f"{result.mid_rms_dbfs:.2f}",
                "side_peak_dbfs": f"{result.side_peak_dbfs:.2f}",
                "side_rms_dbfs": f"{result.side_rms_dbfs:.2f}",
                "side_to_mid_ratio_db": f"{result.side_to_mid_ratio_db:.2f}",
                "recommended_mid_hpf_hz": f"{result.recommended_mid_hpf_hz:.1f}",
                "recommended_side_hpf_hz": f"{result.recommended_side_hpf_hz:.1f}",
                "recommended_side_gain_db": f"{result.recommended_side_gain_db:.2f}",
                "recommended_mid_comp_threshold_dbfs": f"{result.recommended_mid_comp_threshold_dbfs:.2f}",
                "recommended_mid_comp_ratio": f"{result.recommended_mid_comp_ratio:.2f}",
                "recommended_side_ir_mix": f"{result.recommended_side_ir_mix:.3f}",
            }
        )


__all__ = ["MasterStereoResult", "analyze_master_stereo", "export_master_stereo_to_csv"]
