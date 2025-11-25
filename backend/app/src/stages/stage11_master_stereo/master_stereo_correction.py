# src/stages/stage12_master_stereo/master_stereo_correction.py
from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from pedalboard import (
    Pedalboard,
    HighpassFilter,
    Compressor,
    Gain,
    Convolution,
)
from pedalboard.io import AudioFile

logger = logging.getLogger(__name__)


def _safe_dbfs(value: float, floor: float = -120.0) -> float:
    v = float(value)
    if v <= 0.0:
        return floor
    return 20.0 * np.log10(v)


@dataclass
class MasterStereoSettings:
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
    side_to_mid_ratio_db: float

    mid_hpf_hz: float
    side_hpf_hz: float
    side_gain_db: float
    mid_comp_threshold_dbfs: float
    mid_comp_ratio: float
    side_ir_mix: float


@dataclass
class MasterStereoCorrectionResult:
    input_path: Path
    output_path: Path

    sample_rate: int
    num_channels: int
    duration_seconds: float

    original_peak_dbfs: float
    original_rms_dbfs: float
    resulting_peak_dbfs: float
    resulting_rms_dbfs: float

    mid_hpf_hz: float
    side_hpf_hz: float
    side_gain_db: float
    mid_comp_threshold_dbfs: float
    mid_comp_ratio: float
    side_ir_path: Optional[Path]
    side_ir_mix: float


# ----------------------------------------------------------------------
# Lectura CSV
# ----------------------------------------------------------------------


def load_master_stereo_csv(csv_path: Path) -> MasterStereoSettings:
    if not csv_path.exists():
        raise FileNotFoundError(
            f"No se encontró el CSV de análisis master_stereo: {csv_path}"
        )

    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        try:
            row = next(reader)
        except StopIteration:
            raise RuntimeError(f"CSV master_stereo vacío: {csv_path}")

    def _pf(name: str, default: float = 0.0) -> float:
        v = (row.get(name) or "").strip()
        return float(v) if v else default

    mix_path = Path(row["mix_path"]).resolve()

    return MasterStereoSettings(
        mix_path=mix_path,
        sample_rate=int(row["sample_rate"]),
        num_channels=int(row["num_channels"]),
        duration_seconds=float(row["duration_seconds"]),
        peak_dbfs=_pf("peak_dbfs", -120.0),
        rms_dbfs=_pf("rms_dbfs", -120.0),
        crest_factor_db=_pf("crest_factor_db", 0.0),
        mid_peak_dbfs=_pf("mid_peak_dbfs", -120.0),
        mid_rms_dbfs=_pf("mid_rms_dbfs", -120.0),
        side_peak_dbfs=_pf("side_peak_dbfs", -120.0),
        side_rms_dbfs=_pf("side_rms_dbfs", -120.0),
        side_to_mid_ratio_db=_pf("side_to_mid_ratio_db", -60.0),
        mid_hpf_hz=_pf("recommended_mid_hpf_hz", 25.0),
        side_hpf_hz=_pf("recommended_side_hpf_hz", 120.0),
        side_gain_db=_pf("recommended_side_gain_db", 0.0),
        mid_comp_threshold_dbfs=_pf("recommended_mid_comp_threshold_dbfs", -18.0),
        mid_comp_ratio=_pf("recommended_mid_comp_ratio", 1.3),
        side_ir_mix=_pf("recommended_side_ir_mix", 0.18),
    )


# ----------------------------------------------------------------------
# Aplicación M/S
# ----------------------------------------------------------------------


def _apply_master_stereo(
    settings: MasterStereoSettings,
    side_ir_path: Optional[Path],
    side_ir_mix_override: Optional[float],
    overwrite: bool = True,
    output_path: Optional[Path] = None,
) -> MasterStereoCorrectionResult:
    input_path = settings.mix_path
    if not input_path.exists():
        raise FileNotFoundError(f"No se encontró el full mix para master_stereo: {input_path}")

    if output_path is None:
        output_path = input_path if overwrite else input_path.with_name(
            input_path.stem + "_masterstereo.wav"
        )

    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with AudioFile(str(input_path), "r") as f:
        audio = f.read(f.frames)  # (C, N)
        sr = f.samplerate
        num_channels = f.num_channels

    audio = audio.astype(np.float32, copy=False)

    if audio.size > 0:
        original_peak_lin = float(np.max(np.abs(audio)))
        original_rms_lin = float(np.sqrt(np.mean(audio**2)))
    else:
        original_peak_lin = 0.0
        original_rms_lin = 0.0

    original_peak_dbfs = _safe_dbfs(original_peak_lin)
    original_rms_dbfs = _safe_dbfs(original_rms_lin)

    # Mono: si sólo hay 1 canal, procesamos como Mid puro y dejamos Side=0
    if num_channels == 1:
        L = audio[0]
        R = audio[0]
    else:
        L = audio[0]
        R = audio[1]

    # Matriz M/S
    mid = 0.5 * (L + R)
    side = 0.5 * (L - R)

    # ------------------------------
    # Cadena Mid
    # ------------------------------
    mid_board_fx = [
        HighpassFilter(cutoff_frequency_hz=settings.mid_hpf_hz),
        Compressor(
            threshold_db=settings.mid_comp_threshold_dbfs,
            ratio=settings.mid_comp_ratio,
            attack_ms=30.0,
            release_ms=250.0,
        ),
    ]
    board_mid = Pedalboard(mid_board_fx)
    mid_proc = board_mid(mid[np.newaxis, :], sample_rate=sr)[0]

    # ------------------------------
    # Cadena Side
    # ------------------------------
    side_fx = [
        HighpassFilter(cutoff_frequency_hz=settings.side_hpf_hz),
    ]

    # IR opcional para dar sensación de room/cab en el campo lateral
    eff_side_ir_path: Optional[Path] = None
    eff_side_ir_mix: float = settings.side_ir_mix

    if side_ir_mix_override is not None:
        eff_side_ir_mix = float(side_ir_mix_override)

    if side_ir_path is not None:
        side_ir_path = side_ir_path.resolve()
        if side_ir_path.exists():
            eff_side_ir_path = side_ir_path
            logger.info(
                "[MASTER_STEREO] Insertando IR en Side: %s (mix=%.3f)",
                side_ir_path,
                eff_side_ir_mix,
            )
            side_fx.append(
                Convolution(
                    str(side_ir_path),
                    mix=float(eff_side_ir_mix),
                )
            )
        else:
            logger.warning(
                "[MASTER_STEREO] IR de Side no encontrada, se omite: %s",
                side_ir_path,
            )

    # Ganancia de anchura en Side
    if abs(settings.side_gain_db) > 0.05:
        side_fx.append(Gain(gain_db=settings.side_gain_db))

    board_side = Pedalboard(side_fx)
    side_proc = board_side(side[np.newaxis, :], sample_rate=sr)[0]

    # ------------------------------
    # Reconversión a L/R
    # ------------------------------
    L_out = mid_proc + side_proc
    R_out = mid_proc - side_proc

    if num_channels == 1:
        processed = np.stack([L_out], axis=0)
        num_channels_out = 1
    elif num_channels >= 2:
        if num_channels == 2:
            processed = np.stack([L_out, R_out], axis=0)
        else:
            # Dejamos canales extra tal cual (por si hubiera stems raros multicanal)
            others = audio[2:, :]
            processed = np.concatenate(
                [np.stack([L_out, R_out], axis=0), others],
                axis=0,
            )
        num_channels_out = processed.shape[0]
    else:
        # Caso extremo: sin canales -> no hacemos nada
        processed = audio
        num_channels_out = num_channels

    # Métricas de salida
    if processed.size > 0:
        peak_lin = float(np.max(np.abs(processed)))
        rms_lin = float(np.sqrt(np.mean(processed**2)))
    else:
        peak_lin = 0.0
        rms_lin = 0.0

    # Seguridad anti-clipping suave
    if peak_lin > 0.999:
        processed *= (0.999 / peak_lin)
        peak_lin = 0.999

    resulting_peak_dbfs = _safe_dbfs(peak_lin)
    resulting_rms_dbfs = _safe_dbfs(rms_lin)

    # Guardar
    with AudioFile(str(output_path), "w", sr, num_channels_out) as f:
        f.write(processed.astype(np.float32, copy=False))

    return MasterStereoCorrectionResult(
        input_path=input_path,
        output_path=output_path,
        sample_rate=sr,
        num_channels=num_channels_out,
        duration_seconds=settings.duration_seconds,
        original_peak_dbfs=original_peak_dbfs,
        original_rms_dbfs=original_rms_dbfs,
        resulting_peak_dbfs=resulting_peak_dbfs,
        resulting_rms_dbfs=resulting_rms_dbfs,
        mid_hpf_hz=settings.mid_hpf_hz,
        side_hpf_hz=settings.side_hpf_hz,
        side_gain_db=settings.side_gain_db,
        mid_comp_threshold_dbfs=settings.mid_comp_threshold_dbfs,
        mid_comp_ratio=settings.mid_comp_ratio,
        side_ir_path=eff_side_ir_path,
        side_ir_mix=eff_side_ir_mix,
    )


# ----------------------------------------------------------------------
# Log
# ----------------------------------------------------------------------


def write_master_stereo_log(
    result: MasterStereoCorrectionResult,
    csv_path: Path,
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "input_path",
        "output_path",
        "sample_rate",
        "num_channels",
        "duration_seconds",
        "original_peak_dbfs",
        "original_rms_dbfs",
        "resulting_peak_dbfs",
        "resulting_rms_dbfs",
        "mid_hpf_hz",
        "side_hpf_hz",
        "side_gain_db",
        "mid_comp_threshold_dbfs",
        "mid_comp_ratio",
        "side_ir_path",
        "side_ir_mix",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(
            {
                "input_path": str(result.input_path),
                "output_path": str(result.output_path),
                "sample_rate": result.sample_rate,
                "num_channels": result.num_channels,
                "duration_seconds": f"{result.duration_seconds:.6f}",
                "original_peak_dbfs": f"{result.original_peak_dbfs:.2f}",
                "original_rms_dbfs": f"{result.original_rms_dbfs:.2f}",
                "resulting_peak_dbfs": f"{result.resulting_peak_dbfs:.2f}",
                "resulting_rms_dbfs": f"{result.resulting_rms_dbfs:.2f}",
                "mid_hpf_hz": f"{result.mid_hpf_hz:.1f}",
                "side_hpf_hz": f"{result.side_hpf_hz:.1f}",
                "side_gain_db": f"{result.side_gain_db:.2f}",
                "mid_comp_threshold_dbfs": f"{result.mid_comp_threshold_dbfs:.2f}",
                "mid_comp_ratio": f"{result.mid_comp_ratio:.2f}",
                "side_ir_path": str(result.side_ir_path) if result.side_ir_path else "",
                "side_ir_mix": f"{result.side_ir_mix:.3f}",
            }
        )


# ----------------------------------------------------------------------
# Entry point de alto nivel
# ----------------------------------------------------------------------


def run_master_stereo_correction(
    analysis_csv_path: Path,
    log_csv_path: Path,
    side_ir_path: Optional[Path] = None,
    side_ir_mix_override: Optional[float] = None,
    overwrite: bool = True,
    output_path: Optional[Path] = None,
) -> MasterStereoCorrectionResult:
    settings = load_master_stereo_csv(analysis_csv_path)
    result = _apply_master_stereo(
        settings=settings,
        side_ir_path=side_ir_path,
        side_ir_mix_override=side_ir_mix_override,
        overwrite=overwrite,
        output_path=output_path,
    )
    write_master_stereo_log(result, log_csv_path)
    return result


__all__ = [
    "MasterStereoSettings",
    "MasterStereoCorrectionResult",
    "run_master_stereo_correction",
    "load_master_stereo_csv",
    "write_master_stereo_log",
]
