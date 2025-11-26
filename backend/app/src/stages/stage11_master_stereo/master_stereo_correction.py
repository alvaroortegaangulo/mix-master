from __future__ import annotations

import json
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
# Lectura JSON
# ----------------------------------------------------------------------


def load_master_stereo_json(json_path: Path) -> MasterStereoSettings:
    if not json_path.exists():
        raise FileNotFoundError(
            f"No se encontro el JSON de analisis master_stereo: {json_path}"
        )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Formato JSON inesperado en {json_path}")

    def _get_float(name: str, default: float = 0.0) -> float:
        v = payload.get(name)
        try:
            return float(v)
        except Exception:
            return default

    mix_path_raw = payload.get("mix_path") or payload.get("full_mix_path") or ""
    mix_path = Path(mix_path_raw).resolve()

    return MasterStereoSettings(
        mix_path=mix_path,
        sample_rate=int(payload.get("sample_rate", 0)),
        num_channels=int(payload.get("num_channels", 0)),
        duration_seconds=float(payload.get("duration_seconds", 0.0)),
        peak_dbfs=_get_float("peak_dbfs", -120.0),
        rms_dbfs=_get_float("rms_dbfs", -120.0),
        crest_factor_db=_get_float("crest_factor_db", 0.0),
        mid_peak_dbfs=_get_float("mid_peak_dbfs", -120.0),
        mid_rms_dbfs=_get_float("mid_rms_dbfs", -120.0),
        side_peak_dbfs=_get_float("side_peak_dbfs", -120.0),
        side_rms_dbfs=_get_float("side_rms_dbfs", -120.0),
        side_to_mid_ratio_db=_get_float("side_to_mid_ratio_db", -60.0),
        mid_hpf_hz=_get_float("recommended_mid_hpf_hz", 24.0),
        side_hpf_hz=_get_float("recommended_side_hpf_hz", 110.0),
        side_gain_db=_get_float("recommended_side_gain_db", 0.0),
        mid_comp_threshold_dbfs=_get_float("recommended_mid_comp_threshold_dbfs", -14.0),
        mid_comp_ratio=_get_float("recommended_mid_comp_ratio", 1.0),
        side_ir_mix=_get_float("recommended_side_ir_mix", 0.10),
    )


# ----------------------------------------------------------------------
# Aplicacion M/S
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
        raise FileNotFoundError(f"No se encontro el full mix para master_stereo: {input_path}")

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

    # Mono: si solo hay 1 canal, procesamos como Mid puro y dejamos Side=0
    if num_channels == 1:
        L = audio[0]
        R = audio[0]
    else:
        L = audio[0]
        R = audio[1]

    mid = 0.5 * (L + R)
    side = 0.5 * (L - R)

    # ------------------------------------------------------------------
    # Saneado de parámetros (criterios sutiles)
    # ------------------------------------------------------------------
    mid_hpf_hz = float(np.clip(settings.mid_hpf_hz, 18.0, 35.0))
    side_hpf_hz = float(np.clip(settings.side_hpf_hz, 80.0, 150.0))
    side_gain_db = float(np.clip(settings.side_gain_db, -2.0, 2.0))
    mid_comp_ratio = float(np.clip(settings.mid_comp_ratio, 1.0, 1.4))
    mid_comp_threshold_dbfs = float(np.clip(settings.mid_comp_threshold_dbfs, -24.0, -8.0))

    eff_side_ir_mix = settings.side_ir_mix
    if side_ir_mix_override is not None:
        eff_side_ir_mix = float(side_ir_mix_override)
    eff_side_ir_mix = float(np.clip(eff_side_ir_mix, 0.0, 0.25))

    # ------------------------------
    # Cadena Mid
    # ------------------------------
    mid_board_fx = [
        HighpassFilter(cutoff_frequency_hz=mid_hpf_hz),
    ]

    # Si ratio==1.0 prácticamente no actúa, pero mantenemos el bloque
    mid_board_fx.append(
        Compressor(
            threshold_db=mid_comp_threshold_dbfs,
            ratio=mid_comp_ratio,
            attack_ms=30.0,
            release_ms=250.0,
        )
    )

    board_mid = Pedalboard(mid_board_fx)
    mid_proc = board_mid(mid[np.newaxis, :], sample_rate=sr)[0]

    # ------------------------------
    # Cadena Side
    # ------------------------------
    side_fx = [
        HighpassFilter(cutoff_frequency_hz=side_hpf_hz),
    ]

    eff_side_ir_path: Optional[Path] = None
    if side_ir_path is not None:
        side_ir_path = side_ir_path.resolve()
        if side_ir_path.exists() and eff_side_ir_mix > 0.0:
            eff_side_ir_path = side_ir_path
            logger.info(
                "[MASTER_STEREO] Insertando IR en Side: %s (mix=%.3f)",
                side_ir_path,
                eff_side_ir_mix,
            )
            side_fx.append(
                Convolution(
                    str(side_ir_path),
                    mix=eff_side_ir_mix,
                )
            )
        elif not side_ir_path.exists():
            logger.warning(
                "[MASTER_STEREO] IR de Side no encontrada, se omite: %s",
                side_ir_path,
            )

    if abs(side_gain_db) > 0.05:
        side_fx.append(Gain(gain_db=side_gain_db))

    board_side = Pedalboard(side_fx)
    side_proc = board_side(side[np.newaxis, :], sample_rate=sr)[0]

    # ------------------------------
    # Reconversion a L/R
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
            others = audio[2:, :]
            processed = np.concatenate(
                [np.stack([L_out, R_out], axis=0), others],
                axis=0,
            )
        num_channels_out = processed.shape[0]
    else:
        processed = audio
        num_channels_out = num_channels

    if processed.size > 0:
        peak_lin = float(np.max(np.abs(processed)))
        rms_lin = float(np.sqrt(np.mean(processed**2)))
    else:
        peak_lin = 0.0
        rms_lin = 0.0

    if peak_lin > 0.999:
        processed *= (0.999 / peak_lin)
        peak_lin = 0.999

    resulting_peak_dbfs = _safe_dbfs(peak_lin)
    resulting_rms_dbfs = _safe_dbfs(rms_lin)

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
        mid_hpf_hz=mid_hpf_hz,
        side_hpf_hz=side_hpf_hz,
        side_gain_db=side_gain_db,
        mid_comp_threshold_dbfs=mid_comp_threshold_dbfs,
        mid_comp_ratio=mid_comp_ratio,
        side_ir_path=eff_side_ir_path,
        side_ir_mix=eff_side_ir_mix,
    )


# ----------------------------------------------------------------------
# Log
# ----------------------------------------------------------------------


def write_master_stereo_log_json(
    result: MasterStereoCorrectionResult,
    log_json_path: Path,
) -> Path:
    log_json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "input_path": str(result.input_path),
        "output_path": str(result.output_path),
        "sample_rate": result.sample_rate,
        "num_channels": result.num_channels,
        "duration_seconds": result.duration_seconds,
        "original_peak_dbfs": result.original_peak_dbfs,
        "original_rms_dbfs": result.original_rms_dbfs,
        "resulting_peak_dbfs": result.resulting_peak_dbfs,
        "resulting_rms_dbfs": result.resulting_rms_dbfs,
        "mid_hpf_hz": result.mid_hpf_hz,
        "side_hpf_hz": result.side_hpf_hz,
        "side_gain_db": result.side_gain_db,
        "mid_comp_threshold_dbfs": result.mid_comp_threshold_dbfs,
        "mid_comp_ratio": result.mid_comp_ratio,
        "side_ir_path": str(result.side_ir_path) if result.side_ir_path else None,
        "side_ir_mix": result.side_ir_mix,
    }
    log_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return log_json_path


# ----------------------------------------------------------------------
# Entry point de alto nivel
# ----------------------------------------------------------------------


def run_master_stereo_correction(
    analysis_json_path: Path,
    log_json_path: Path,
    side_ir_path: Optional[Path] = None,
    side_ir_mix_override: Optional[float] = None,
    overwrite: bool = True,
    output_path: Optional[Path] = None,
) -> MasterStereoCorrectionResult:
    settings = load_master_stereo_json(analysis_json_path)
    result = _apply_master_stereo(
        settings=settings,
        side_ir_path=side_ir_path,
        side_ir_mix_override=side_ir_mix_override,
        overwrite=overwrite,
        output_path=output_path,
    )
    write_master_stereo_log_json(result, log_json_path)
    return result


__all__ = [
    "MasterStereoSettings",
    "MasterStereoCorrectionResult",
    "run_master_stereo_correction",
    "load_master_stereo_json",
    "write_master_stereo_log_json",
]
