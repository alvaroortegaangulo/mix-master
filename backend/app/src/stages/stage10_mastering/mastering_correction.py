# src/stages/stage10_mastering/mastering_correction.py
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List

import numpy as np
from pedalboard import (
    Pedalboard,
    HighpassFilter,
    Compressor,
    Distortion,
    Gain,
    Limiter,
)
from pedalboard.io import AudioFile

from src.utils.stage_base import BaseCorrectionStage  # mismo patrón que en spectral_cleanup
from src.analysis.mastering_analysis import MasteringResult


# ----------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------


def _safe_dbfs(value: float, floor: float = -120.0) -> float:
    v = float(value)
    if v <= 0.0:
        return floor
    return 20.0 * np.log10(v)


def _parse_float(s: str, default: float = 0.0) -> float:
    s = s.strip()
    if not s:
        return default
    return float(s)


def _parse_bool(s: str) -> bool:
    s = s.strip().lower()
    return s in {"1", "true", "t", "yes", "y"}


# ----------------------------------------------------------------------
# Modelos de datos (CSV de análisis → corrección)
# ----------------------------------------------------------------------


@dataclass
class MasteringRow:
    filename: str
    relative_path: str
    sample_rate: int
    num_channels: int
    duration_seconds: float

    peak_dbfs: float
    rms_dbfs: float
    is_vocal: bool

    recommended_target_peak_dbfs: float
    recommended_drive_db: float


@dataclass
class MasteringCorrectionResult:
    filename: str
    input_path: Path
    output_path: Path

    sample_rate: int
    num_channels: int
    duration_seconds: float
    is_vocal: bool

    target_peak_dbfs: float
    pre_gain_db: float
    comp_threshold_dbfs: float
    comp_ratio: float
    distortion_drive_db: float

    original_peak_dbfs: float
    original_rms_dbfs: float
    resulting_peak_dbfs: float
    resulting_rms_dbfs: float


# ----------------------------------------------------------------------
# Lectura CSV de análisis
# ----------------------------------------------------------------------


def load_mastering_csv(csv_path: Path) -> List[MasteringRow]:
    if not csv_path.exists():
        raise FileNotFoundError(f"No se encontró el CSV de análisis de mastering: {csv_path}")

    rows: List[MasteringRow] = []

    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for line in reader:
            row = MasteringRow(
                filename=line["filename"],
                relative_path=line.get("relative_path") or line["filename"],
                sample_rate=int(line["sample_rate"]),
                num_channels=int(line["num_channels"]),
                duration_seconds=float(line["duration_seconds"]),
                peak_dbfs=_parse_float(line.get("peak_dbfs", "-120.0")),
                rms_dbfs=_parse_float(line.get("rms_dbfs", "-120.0")),
                is_vocal=_parse_bool(line.get("is_vocal", "0")),
                recommended_target_peak_dbfs=_parse_float(
                    line.get("recommended_target_peak_dbfs", "-1.0")
                ),
                recommended_drive_db=_parse_float(
                    line.get("recommended_drive_db", "0.0")
                ),
            )
            rows.append(row)

    return rows


# ----------------------------------------------------------------------
# Aplicación de la cadena de mastering a un stem
# ----------------------------------------------------------------------


def _apply_mastering_to_file(
    row: MasteringRow,
    input_media_dir: Path,
    vocal_tuning_media_dir: Path,
    output_media_dir: Path,
    vocal_filename: str = "vocal.wav",
) -> MasteringCorrectionResult:
    """
    Aplica mastering ligero a un stem.
    Si es la pista vocal, usa la versión afinada de vocal_tuning_media_dir si existe.
    """
    # Stem base desde static_mix_dyn
    base_input_path = (input_media_dir / row.relative_path).resolve()
    input_path = base_input_path

    # Para la pista vocal usamos la versión afinada si está disponible
    if row.is_vocal:
        tuned_path = (vocal_tuning_media_dir / vocal_filename).resolve()
        if tuned_path.exists():
            input_path = tuned_path

    if not input_path.exists():
        raise FileNotFoundError(f"No se encontró el WAV de entrada para mastering: {input_path}")

    output_media_dir.mkdir(parents=True, exist_ok=True)
    output_path = (output_media_dir / row.filename).resolve()

    # --------------------------------------------------------------
    # Leer audio con Pedalboard (float32, shape: (channels, samples))
    # --------------------------------------------------------------
    with AudioFile(str(input_path), "r") as f:
        audio = f.read(f.frames)
        sr = f.samplerate
        num_channels = f.num_channels

    audio = audio.astype(np.float32, copy=False)

    if audio.size > 0:
        original_peak = float(np.max(np.abs(audio)))
        original_rms = float(np.sqrt(np.mean(audio**2)))
    else:
        original_peak = 0.0
        original_rms = 0.0

    original_peak_dbfs = _safe_dbfs(original_peak)
    original_rms_dbfs = _safe_dbfs(original_rms)

    # --------------------------------------------------------------
    # Diseño de cadena de mastering
    # --------------------------------------------------------------
    target_peak_dbfs = row.recommended_target_peak_dbfs

    # Pre-gain sugerido por el análisis, clamp de seguridad
    pre_gain_db = max(min(row.recommended_drive_db, 12.0), -24.0)

    # Detección simple de kick por nombre de archivo
    filename_lower = row.filename.lower()
    is_kick = "kick" in filename_lower

    # Ajustes por tipo de pista
    if row.is_vocal:
        # Vocal: compresión algo más marcada pero con poca saturación
        comp_threshold_dbfs = -18.0
        comp_ratio = 2.5
        distortion_drive_db = 1.5

    elif is_kick:
        # Kick: proteger transitorios → menos compresión y menos saturación
        # Threshold más alto (menos GR) y ratio suave
        comp_threshold_dbfs = -10.0
        comp_ratio = 1.3
        distortion_drive_db = 0.0  # sin saturación adicional

        # Además, reducimos el pre-gain para no empujar tanto al limiter
        pre_gain_db = max(min(row.recommended_drive_db * 0.5, 6.0), -12.0)

    else:
        # Resto de instrumentos: ajuste por defecto
        comp_threshold_dbfs = -16.0
        comp_ratio = 2.0
        distortion_drive_db = 2.5

    effects = [
        HighpassFilter(cutoff_frequency_hz=25.0),
        Compressor(
            threshold_db=comp_threshold_dbfs,
            ratio=comp_ratio,
            attack_ms=30.0,
            release_ms=200.0,
        ),
        Distortion(drive_db=distortion_drive_db),
        Gain(gain_db=pre_gain_db),
        Limiter(
            threshold_db=-1.0,
            release_ms=100.0,
        ),
    ]

    board = Pedalboard(effects)
    processed = board(audio, sample_rate=sr)

    if processed.size > 0:
        processed_peak = float(np.max(np.abs(processed)))
        processed_rms = float(np.sqrt(np.mean(processed**2)))
    else:
        processed_peak = 0.0
        processed_rms = 0.0

    resulting_peak_dbfs = _safe_dbfs(processed_peak)
    resulting_rms_dbfs = _safe_dbfs(processed_rms)

    # --------------------------------------------------------------
    # Guardar WAV masterizado
    # --------------------------------------------------------------
    with AudioFile(str(output_path), "w", sr, num_channels) as f:
        f.write(processed.astype(np.float32, copy=False))

    return MasteringCorrectionResult(
        filename=row.filename,
        input_path=input_path,
        output_path=output_path,
        sample_rate=sr,
        num_channels=num_channels,
        duration_seconds=row.duration_seconds,
        is_vocal=row.is_vocal,
        target_peak_dbfs=target_peak_dbfs,
        pre_gain_db=pre_gain_db,
        comp_threshold_dbfs=comp_threshold_dbfs,
        comp_ratio=comp_ratio,
        distortion_drive_db=distortion_drive_db,
        original_peak_dbfs=original_peak_dbfs,
        original_rms_dbfs=original_rms_dbfs,
        resulting_peak_dbfs=resulting_peak_dbfs,
        resulting_rms_dbfs=resulting_rms_dbfs,
    )


# ----------------------------------------------------------------------
# Log de corrección
# ----------------------------------------------------------------------


def write_mastering_log(
    results: List[MasteringCorrectionResult],
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
        "is_vocal",
        "target_peak_dbfs",
        "pre_gain_db",
        "comp_threshold_dbfs",
        "comp_ratio",
        "distortion_drive_db",
        "original_peak_dbfs",
        "original_rms_dbfs",
        "resulting_peak_dbfs",
        "resulting_rms_dbfs",
    ]

    with log_csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for r in results:
            writer.writerow(
                {
                    "filename": r.filename,
                    "input_path": str(r.input_path),
                    "output_path": str(r.output_path),
                    "sample_rate": r.sample_rate,
                    "num_channels": r.num_channels,
                    "duration_seconds": f"{r.duration_seconds:.6f}",
                    "is_vocal": "1" if r.is_vocal else "0",
                    "target_peak_dbfs": f"{r.target_peak_dbfs:.2f}",
                    "pre_gain_db": f"{r.pre_gain_db:.2f}",
                    "comp_threshold_dbfs": f"{r.comp_threshold_dbfs:.2f}",
                    "comp_ratio": f"{r.comp_ratio:.2f}",
                    "distortion_drive_db": f"{r.distortion_drive_db:.2f}",
                    "original_peak_dbfs": f"{r.original_peak_dbfs:.2f}",
                    "original_rms_dbfs": f"{r.original_rms_dbfs:.2f}",
                    "resulting_peak_dbfs": f"{r.resulting_peak_dbfs:.2f}",
                    "resulting_rms_dbfs": f"{r.resulting_rms_dbfs:.2f}",
                }
            )


# ----------------------------------------------------------------------
# Stage basado en BaseCorrectionStage
# ----------------------------------------------------------------------


class MasteringStage(
    BaseCorrectionStage[MasteringRow, MasteringCorrectionResult]
):
    """
    Etapa de mastering por stems usando BaseCorrectionStage.

    Se apoya en:
      - load_mastering_csv
      - _apply_mastering_to_file
      - write_mastering_log
    """

    def __init__(
        self,
        analysis_csv_path: Path,
        input_media_dir: Path,
        vocal_tuning_media_dir: Path,
        output_media_dir: Path,
        vocal_filename: str = "vocal.wav",
    ) -> None:
        super().__init__(
            analysis_csv_path=analysis_csv_path,
            input_media_dir=input_media_dir,
            output_media_dir=output_media_dir,
        )
        self.vocal_tuning_media_dir = vocal_tuning_media_dir
        self.vocal_filename = vocal_filename

    def load_rows(self) -> List[MasteringRow]:
        return load_mastering_csv(self.analysis_csv_path)

    def process_row(self, row: MasteringRow) -> MasteringCorrectionResult:
        return _apply_mastering_to_file(
            row=row,
            input_media_dir=self.input_media_dir,
            vocal_tuning_media_dir=self.vocal_tuning_media_dir,
            output_media_dir=self.output_media_dir,
            vocal_filename=self.vocal_filename,
        )

    def write_log(
        self,
        results: List[MasteringCorrectionResult],
    ) -> Path:
        log_csv_path = self.output_media_dir / "mastering_correction_log.csv"
        write_mastering_log(results, log_csv_path)
        return log_csv_path


def run_mastering_correction(
    analysis_csv_path: Path,
    input_media_dir: Path,
    vocal_tuning_media_dir: Path,
    output_media_dir: Path,
    vocal_filename: str = "vocal.wav",
) -> Path:
    """
    Punto de entrada de alto nivel para el mastering por stems.

    Usa MasteringStage (BaseCorrectionStage) para aplicar la cadena de mastering
    a todos los stems y generar el log de corrección.
    """
    stage = MasteringStage(
        analysis_csv_path=analysis_csv_path,
        input_media_dir=input_media_dir,
        vocal_tuning_media_dir=vocal_tuning_media_dir,
        output_media_dir=output_media_dir,
        vocal_filename=vocal_filename,
    )
    return stage.run()
