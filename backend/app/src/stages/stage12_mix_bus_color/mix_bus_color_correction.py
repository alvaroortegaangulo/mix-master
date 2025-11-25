# src/stages/stage12_mix_bus_color/mix_bus_color_correction.py
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np
from pedalboard import (
    Pedalboard,
    HighpassFilter,
    Distortion,
    Gain,
    Limiter,
    Convolution,
    load_plugin,
)
from pedalboard.io import AudioFile

logger = logging.getLogger(__name__)


def _safe_dbfs(value: float, floor: float = -120.0) -> float:
    v = float(value)
    if v <= 0.0:
        return floor
    return 20.0 * np.log10(v)


@dataclass
class MixBusColorSettings:
    mix_path: Path
    sample_rate: int
    num_channels: int
    duration_seconds: float

    peak_dbfs: float
    rms_dbfs: float
    crest_factor_db: float

    hpf_hz: float
    saturation_drive_db: float
    tape_mix: float
    console_mix: float


@dataclass
class MixBusColorCorrectionResult:
    input_path: Path
    output_path: Path

    sample_rate: int
    num_channels: int
    duration_seconds: float

    original_peak_dbfs: float
    original_rms_dbfs: float
    resulting_peak_dbfs: float
    resulting_rms_dbfs: float

    hpf_hz: float
    saturation_drive_db: float
    tape_ir_path: Optional[Path]
    console_ir_path: Optional[Path]
    tape_mix: float
    console_mix: float
    vst3_plugins_loaded: List[str]


# ----------------------------------------------------------------------
# Lectura JSON
# ----------------------------------------------------------------------


def load_mix_bus_color_json(json_path: Path) -> MixBusColorSettings:
    """
    Lee el JSON generado por mix_bus_color_analysis y devuelve los ajustes.
    """
    if not json_path.exists():
        raise FileNotFoundError(f"No se encontro el JSON de mix-bus color: {json_path}")

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Formato JSON inesperado en {json_path}")

    def _gf(name: str, default: float = 0.0) -> float:
        v = payload.get(name)
        try:
            return float(v)
        except Exception:
            return default

    mix_path = Path(payload.get("mix_path", "")).resolve()

    return MixBusColorSettings(
        mix_path=mix_path,
        sample_rate=int(payload.get("sample_rate", 0)),
        num_channels=int(payload.get("num_channels", 0)),
        duration_seconds=float(payload.get("duration_seconds", 0.0)),
        peak_dbfs=_gf("peak_dbfs", -120.0),
        rms_dbfs=_gf("rms_dbfs", -120.0),
        crest_factor_db=_gf("crest_factor_db", 0.0),
        hpf_hz=_gf("recommended_hpf_hz", 25.0),
        saturation_drive_db=_gf("recommended_saturation_drive_db", 1.0),
        tape_mix=_gf("recommended_tape_mix", 0.2),
        console_mix=_gf("recommended_console_mix", 0.2),
    )


# ----------------------------------------------------------------------
# Aplicacion de color
# ----------------------------------------------------------------------


def _apply_mix_bus_color(
    settings: MixBusColorSettings,
    tape_ir_path: Optional[Path],
    console_ir_path: Optional[Path],
    vst3_plugin_paths: Optional[List[Path]],
    overwrite: bool = True,
    output_path: Optional[Path] = None,
) -> MixBusColorCorrectionResult:
    """
    Aplica la cadena de color de mix-bus sobre el full mix.
    """
    input_path = settings.mix_path
    if not input_path.exists():
        raise FileNotFoundError(f"No se encontro el full mix de entrada: {input_path}")

    if output_path is None:
        output_path = input_path if overwrite else input_path.with_name(
            input_path.stem + "_buscolor.wav"
        )
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with AudioFile(str(input_path), "r") as f:
        audio = f.read(f.frames)
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

    effects = []

    if settings.hpf_hz > 0.0:
        effects.append(HighpassFilter(cutoff_frequency_hz=settings.hpf_hz))

    pre_gain_db = min(max(settings.saturation_drive_db * 0.4, 0.0), 2.0)
    if abs(pre_gain_db) > 0.05:
        effects.append(Gain(gain_db=pre_gain_db))

    if tape_ir_path is not None:
        tape_ir_path = tape_ir_path.resolve()
        if tape_ir_path.exists():
            logger.info(
                "[MIX_BUS_COLOR] Insertando IR de tape: %s (mix=%.3f)",
                tape_ir_path,
                settings.tape_mix,
            )
            effects.append(
                Convolution(
                    str(tape_ir_path),
                    mix=float(settings.tape_mix),
                )
            )
        else:
            logger.warning(
                "[MIX_BUS_COLOR] IR de tape no encontrada, se omite: %s",
                tape_ir_path,
            )

    if console_ir_path is not None:
        console_ir_path = console_ir_path.resolve()
        if console_ir_path.exists():
            logger.info(
                "[MIX_BUS_COLOR] Insertando IR de consola: %s (mix=%.3f)",
                console_ir_path,
                settings.console_mix,
            )
            effects.append(
                Convolution(
                    str(console_ir_path),
                    mix=float(settings.console_mix),
                )
            )
        else:
            logger.warning(
                "[MIX_BUS_COLOR] IR de consola no encontrada, se omite: %s",
                console_ir_path,
            )

    if abs(settings.saturation_drive_db) > 0.05:
        effects.append(Distortion(drive_db=float(settings.saturation_drive_db)))

    vst3_plugins_loaded: List[str] = []
    for vst_path in vst3_plugin_paths or []:
        try:
            vst_path = vst_path.resolve()
            if not vst_path.exists():
                logger.warning(
                    "[MIX_BUS_COLOR] VST3 no encontrado, se omite: %s", vst_path
                )
                continue
            plugin = load_plugin(str(vst_path))
            effects.append(plugin)
            vst3_plugins_loaded.append(str(vst_path))
            logger.info("[MIX_BUS_COLOR] VST3 cargado: %s", vst_path)
        except Exception as exc:  # pragma: no cover - defensivo
            logger.warning(
                "[MIX_BUS_COLOR] Error cargando VST3 %s: %s", vst_path, exc
            )

    effects.append(Gain(gain_db=-0.5))
    effects.append(
        Limiter(
            threshold_db=-0.8,
            release_ms=100.0,
        )
    )

    board = Pedalboard(effects)
    processed = board(audio, sample_rate=sr)

    if processed.size > 0:
        peak_lin = float(np.max(np.abs(processed)))
        rms_lin = float(np.sqrt(np.mean(processed**2)))
    else:
        peak_lin = 0.0
        rms_lin = 0.0

    if peak_lin > 0.999:
        processed = processed * (0.999 / peak_lin)
        peak_lin = 0.999

    resulting_peak_dbfs = _safe_dbfs(peak_lin)
    resulting_rms_dbfs = _safe_dbfs(rms_lin)

    with AudioFile(str(output_path), "w", sr, num_channels) as f:
        f.write(processed.astype(np.float32, copy=False))

    return MixBusColorCorrectionResult(
        input_path=input_path,
        output_path=output_path,
        sample_rate=sr,
        num_channels=num_channels,
        duration_seconds=settings.duration_seconds,
        original_peak_dbfs=original_peak_dbfs,
        original_rms_dbfs=original_rms_dbfs,
        resulting_peak_dbfs=resulting_peak_dbfs,
        resulting_rms_dbfs=resulting_rms_dbfs,
        hpf_hz=settings.hpf_hz,
        saturation_drive_db=settings.saturation_drive_db,
        tape_ir_path=tape_ir_path,
        console_ir_path=console_ir_path,
        tape_mix=settings.tape_mix,
        console_mix=settings.console_mix,
        vst3_plugins_loaded=vst3_plugins_loaded,
    )


def write_mix_bus_color_log_json(
    result: MixBusColorCorrectionResult,
    json_path: Path,
) -> Path:
    json_path.parent.mkdir(parents=True, exist_ok=True)
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
        "hpf_hz": result.hpf_hz,
        "saturation_drive_db": result.saturation_drive_db,
        "tape_ir_path": str(result.tape_ir_path) if result.tape_ir_path else None,
        "console_ir_path": str(result.console_ir_path) if result.console_ir_path else None,
        "tape_mix": result.tape_mix,
        "console_mix": result.console_mix,
        "vst3_plugins_loaded": result.vst3_plugins_loaded,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return json_path


def run_mix_bus_color_correction(
    analysis_json_path: Path,
    log_json_path: Path,
    tape_ir_path: Optional[Path] = None,
    console_ir_path: Optional[Path] = None,
    vst3_plugin_paths: Optional[List[Path]] = None,
    overwrite: bool = True,
    output_path: Optional[Path] = None,
) -> MixBusColorCorrectionResult:
    """
    Punto de entrada de alto nivel para aplicar el color de mix-bus.
    """
    settings = load_mix_bus_color_json(analysis_json_path)
    result = _apply_mix_bus_color(
        settings=settings,
        tape_ir_path=tape_ir_path,
        console_ir_path=console_ir_path,
        vst3_plugin_paths=vst3_plugin_paths,
        overwrite=overwrite,
        output_path=output_path,
    )
    write_mix_bus_color_log_json(result, log_json_path)
    return result


__all__ = [
    "MixBusColorSettings",
    "MixBusColorCorrectionResult",
    "run_mix_bus_color_correction",
    "load_mix_bus_color_json",
    "write_mix_bus_color_log_json",
]
