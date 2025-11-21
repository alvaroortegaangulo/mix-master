from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List

import numpy as np
from pedalboard import Pedalboard, Compressor, Limiter, Gain
from pedalboard.io import AudioFile


@dataclass
class DynamicsRow:
    filename: str
    relative_path: str
    sample_rate: int
    num_channels: int
    duration_seconds: float
    rms_dbfs: float
    peak_dbfs: float
    crest_factor_db: float
    transient_crest_db: float
    instrument_profile: str
    comp_enabled: bool
    comp_threshold_dbfs: float
    comp_ratio: float
    comp_attack_ms: float
    comp_release_ms: float
    comp_makeup_gain_db: float
    limiter_enabled: bool
    limiter_threshold_dbfs: float
    limiter_release_ms: float


@dataclass
class DynamicsCorrectionResult:
    filename: str
    input_path: Path
    output_path: Path
    sample_rate: int
    num_channels: int
    duration_seconds: float
    instrument_profile: str
    comp_enabled: bool
    comp_threshold_dbfs: float
    comp_ratio: float
    comp_attack_ms: float
    comp_release_ms: float
    comp_makeup_gain_db: float
    limiter_enabled: bool
    limiter_threshold_dbfs: float
    limiter_release_ms: float
    original_peak_dbfs: float
    original_rms_dbfs: float
    resulting_peak_dbfs: float
    resulting_rms_dbfs: float


def _safe_dbfs(x: float, floor: float = -120.0) -> float:
    x = float(x)
    if x <= 0.0:
        return floor
    return 20.0 * np.log10(x)


def _parse_bool(v: str) -> bool:
    v = v.strip()
    if not v:
        return False
    return v in ("1", "true", "True", "YES", "yes")


def _parse_float(v: str, default: float = 0.0) -> float:
    v = v.strip()
    if not v:
        return default
    return float(v)


# ----------------------------------------------------------------------
# Lectura del CSV de análisis
# ----------------------------------------------------------------------


def load_dynamics_csv(csv_path: Path) -> List[DynamicsRow]:
    if not csv_path.exists():
        raise FileNotFoundError(f"No se encontró el CSV de análisis de dinámica: {csv_path}")

    rows: List[DynamicsRow] = []

    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for line in reader:
            row = DynamicsRow(
                filename=line["filename"],
                relative_path=line.get("relative_path") or line["filename"],
                sample_rate=int(line["sample_rate"]),
                num_channels=int(line["num_channels"]),
                duration_seconds=float(line["duration_seconds"]),
                rms_dbfs=float(line["rms_dbfs"]),
                peak_dbfs=float(line["peak_dbfs"]),
                crest_factor_db=float(line["crest_factor_db"]),
                transient_crest_db=float(line["transient_crest_db"]),
                instrument_profile=line.get("instrument_profile", ""),
                comp_enabled=_parse_bool(line.get("comp_enabled", "0")),
                comp_threshold_dbfs=_parse_float(line.get("comp_threshold_dbfs", "0.0")),
                comp_ratio=_parse_float(line.get("comp_ratio", "1.0")),
                comp_attack_ms=_parse_float(line.get("comp_attack_ms", "10.0")),
                comp_release_ms=_parse_float(line.get("comp_release_ms", "100.0")),
                comp_makeup_gain_db=_parse_float(line.get("comp_makeup_gain_db", "0.0")),
                limiter_enabled=_parse_bool(line.get("limiter_enabled", "0")),
                limiter_threshold_dbfs=_parse_float(line.get("limiter_threshold_dbfs", "-0.5")),
                limiter_release_ms=_parse_float(line.get("limiter_release_ms", "100.0")),
            )
            rows.append(row)

    return rows


# ----------------------------------------------------------------------
# Aplicación de compresor + limitador
# ----------------------------------------------------------------------


def _apply_dynamics_to_file(
    row: DynamicsRow,
    input_media_dir: Path,
    output_media_dir: Path,
) -> DynamicsCorrectionResult:
    input_path = (input_media_dir / row.relative_path).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"No se encontró el WAV de entrada: {input_path}")

    output_media_dir.mkdir(parents=True, exist_ok=True)
    output_path = (output_media_dir / row.filename).resolve()

    # Leer audio
    with AudioFile(str(input_path), "r") as f:
        audio = f.read(f.frames)  # (channels, samples)
        sr = f.samplerate
        num_channels = f.num_channels

    audio = audio.astype(np.float32, copy=False)

    # Métricas originales
    original_peak = float(np.max(np.abs(audio))) if audio.size > 0 else 0.0
    original_rms = float(np.sqrt(np.mean(audio**2))) if audio.size > 0 else 0.0

    original_peak_dbfs = _safe_dbfs(original_peak)
    original_rms_dbfs = _safe_dbfs(original_rms)

    # Construir cadena de efectos
    effects = []

    if row.comp_enabled:
        # 1) Compresor sin makeup_gain_db (no lo soporta esta versión de Pedalboard)
        comp = Compressor(
            threshold_db=row.comp_threshold_dbfs,
            ratio=row.comp_ratio,
            attack_ms=row.comp_attack_ms,
            release_ms=row.comp_release_ms,
        )
        effects.append(comp)

        # 2) Si queremos aplicar gain de compensación, lo hacemos con un Gain aparte
        if abs(row.comp_makeup_gain_db) > 0.01:
            effects.append(Gain(gain_db=row.comp_makeup_gain_db))

    if row.limiter_enabled:
        effects.append(
            Limiter(
                threshold_db=row.limiter_threshold_dbfs,
                release_ms=row.limiter_release_ms,
            )
        )

    board = Pedalboard(effects)
    processed = board(audio, sample_rate=sr) if effects else audio

    # Métricas resultantes
    processed_peak = float(np.max(np.abs(processed))) if processed.size > 0 else 0.0
    processed_rms = float(np.sqrt(np.mean(processed**2))) if processed.size > 0 else 0.0

    resulting_peak_dbfs = _safe_dbfs(processed_peak)
    resulting_rms_dbfs = _safe_dbfs(processed_rms)

    # Escribir archivo corregido
    with AudioFile(str(output_path), "w", sr, num_channels) as f:
        f.write(processed)

    return DynamicsCorrectionResult(
        filename=row.filename,
        input_path=input_path,
        output_path=output_path,
        sample_rate=sr,
        num_channels=num_channels,
        duration_seconds=row.duration_seconds,
        instrument_profile=row.instrument_profile,
        comp_enabled=row.comp_enabled,
        comp_threshold_dbfs=row.comp_threshold_dbfs,
        comp_ratio=row.comp_ratio,
        comp_attack_ms=row.comp_attack_ms,
        comp_release_ms=row.comp_release_ms,
        comp_makeup_gain_db=row.comp_makeup_gain_db,
        limiter_enabled=row.limiter_enabled,
        limiter_threshold_dbfs=row.limiter_threshold_dbfs,
        limiter_release_ms=row.limiter_release_ms,
        original_peak_dbfs=original_peak_dbfs,
        original_rms_dbfs=original_rms_dbfs,
        resulting_peak_dbfs=resulting_peak_dbfs,
        resulting_rms_dbfs=resulting_rms_dbfs,
    )


# ----------------------------------------------------------------------
# Log de corrección
# ----------------------------------------------------------------------


def write_dynamics_correction_log(
    results: List[DynamicsCorrectionResult],
    log_csv_path: Path,
) -> None:
    log_csv_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "filename",
        "input_path",
        "output_path",
        "sample_rate",
        "num_channels",
        "duration_seconds",
        "instrument_profile",
        "comp_enabled",
        "comp_threshold_dbfs",
        "comp_ratio",
        "comp_attack_ms",
        "comp_release_ms",
        "comp_makeup_gain_db",
        "limiter_enabled",
        "limiter_threshold_dbfs",
        "limiter_release_ms",
        "original_peak_dbfs",
        "original_rms_dbfs",
        "resulting_peak_dbfs",
        "resulting_rms_dbfs",
    ]

    with log_csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for r in results:
            writer.writerow({
                "filename": r.filename,
                "input_path": str(r.input_path),
                "output_path": str(r.output_path),
                "sample_rate": r.sample_rate,
                "num_channels": r.num_channels,
                "duration_seconds": f"{r.duration_seconds:.6f}",
                "instrument_profile": r.instrument_profile,
                "comp_enabled": int(r.comp_enabled),
                "comp_threshold_dbfs": f"{r.comp_threshold_dbfs:.2f}",
                "comp_ratio": f"{r.comp_ratio:.2f}",
                "comp_attack_ms": f"{r.comp_attack_ms:.2f}",
                "comp_release_ms": f"{r.comp_release_ms:.2f}",
                "comp_makeup_gain_db": f"{r.comp_makeup_gain_db:.2f}",
                "limiter_enabled": int(r.limiter_enabled),
                "limiter_threshold_dbfs": f"{r.limiter_threshold_dbfs:.2f}",
                "limiter_release_ms": f"{r.limiter_release_ms:.2f}",
                "original_peak_dbfs": f"{r.original_peak_dbfs:.2f}",
                "original_rms_dbfs": f"{r.original_rms_dbfs:.2f}",
                "resulting_peak_dbfs": f"{r.resulting_peak_dbfs:.2f}",
                "resulting_rms_dbfs": f"{r.resulting_rms_dbfs:.2f}",
            })


# ----------------------------------------------------------------------
# Punto de entrada de alto nivel
# ----------------------------------------------------------------------


def run_dynamics_correction(
    analysis_csv_path: Path,
    input_media_dir: Path,
    output_media_dir: Path,
) -> Path:
    """
    Ejecuta la corrección de dinámica de todos los stems (compresor + limitador).

    :param analysis_csv_path: Ruta al CSV de análisis de dinámica.
    :param input_media_dir: Carpeta con los WAV de entrada (stems ya ecualizados).
    :param output_media_dir: Carpeta donde se guardarán los WAV corregidos.
    :return: Ruta al CSV de log de corrección.
    """
    rows = load_dynamics_csv(analysis_csv_path)

    results: List[DynamicsCorrectionResult] = []

    for row in rows:
        result = _apply_dynamics_to_file(row, input_media_dir, output_media_dir)
        results.append(result)

    log_csv_path = output_media_dir / "dynamics_correction_log.csv"
    write_dynamics_correction_log(results, log_csv_path)

    return log_csv_path
