# src/stages/stage4_multiband_eq/multiband_eq_correction.py
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np
from pedalboard import (
    Pedalboard,
    HighpassFilter,
    LowpassFilter,
    Compressor,
    Distortion,
    Gain,
)
from pedalboard.io import AudioFile

from src.utils.stage_base import BaseCorrectionStage


EPS = 1e-12


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


@dataclass
class MultibandEQRow:
    filename: str
    relative_path: str
    sample_rate: int
    num_channels: int
    duration_seconds: float

    is_vocal: bool
    is_bus_fx: bool
    bus_key: Optional[str]

    low_rms_dbfs: float
    mid_rms_dbfs: float
    high_rms_dbfs: float
    full_rms_dbfs: float

    suggested_low_gain_db: float
    suggested_mid_gain_db: float
    suggested_high_gain_db: float


@dataclass
class MultibandEQCorrectionResult:
    filename: str
    input_path: Path
    output_path: Path

    sample_rate: int
    num_channels: int
    duration_seconds: float

    is_vocal: bool
    is_bus_fx: bool
    bus_key: Optional[str]

    low_mid_crossover_hz: float
    mid_high_crossover_hz: float

    # Parámetros finales aplicados por banda (para logging)
    low_comp_threshold_dbfs: float
    low_comp_ratio: float
    low_distortion_drive_db: float
    low_gain_db: float

    mid_comp_threshold_dbfs: float
    mid_comp_ratio: float
    mid_distortion_drive_db: float
    mid_gain_db: float

    high_comp_threshold_dbfs: float
    high_comp_ratio: float
    high_distortion_drive_db: float
    high_gain_db: float

    original_peak_dbfs: float
    original_rms_dbfs: float
    resulting_peak_dbfs: float
    resulting_rms_dbfs: float


# ----------------------------------------------------------------------
# Lectura del CSV de análisis
# ----------------------------------------------------------------------


def load_multiband_eq_csv(csv_path: Path) -> List[MultibandEQRow]:
    if not csv_path.exists():
        raise FileNotFoundError(
            f"No se encontró el CSV de análisis multibanda: {csv_path}"
        )

    rows: List[MultibandEQRow] = []

    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for line in reader:
            rows.append(
                MultibandEQRow(
                    filename=line["filename"],
                    relative_path=line.get("relative_path") or line["filename"],
                    sample_rate=int(line["sample_rate"]),
                    num_channels=int(line["num_channels"]),
                    duration_seconds=float(line["duration_seconds"]),
                    is_vocal=_parse_bool(line.get("is_vocal", "0")),
                    is_bus_fx=_parse_bool(line.get("is_bus_fx", "0")),
                    bus_key=(line.get("bus_key") or "").strip() or None,
                    low_rms_dbfs=_parse_float(line.get("low_rms_dbfs", "-120.0")),
                    mid_rms_dbfs=_parse_float(line.get("mid_rms_dbfs", "-120.0")),
                    high_rms_dbfs=_parse_float(line.get("high_rms_dbfs", "-120.0")),
                    full_rms_dbfs=_parse_float(line.get("full_rms_dbfs", "-120.0")),
                    suggested_low_gain_db=_parse_float(
                        line.get("suggested_low_gain_db", "0.0")
                    ),
                    suggested_mid_gain_db=_parse_float(
                        line.get("suggested_mid_gain_db", "0.0")
                    ),
                    suggested_high_gain_db=_parse_float(
                        line.get("suggested_high_gain_db", "0.0")
                    ),
                )
            )

    return rows


# ----------------------------------------------------------------------
# Split en bandas y procesado
# ----------------------------------------------------------------------


def _split_into_bands(
    audio_ch_first: np.ndarray,
    sr: int,
    low_mid_crossover_hz: float,
    mid_high_crossover_hz: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Igual que en el análisis: audio (C, N) → (low, mid, high) (C, N).
    """
    board_low = Pedalboard(
        [LowpassFilter(cutoff_frequency_hz=low_mid_crossover_hz)]
    )
    board_mid = Pedalboard(
        [
            HighpassFilter(cutoff_frequency_hz=low_mid_crossover_hz),
            LowpassFilter(cutoff_frequency_hz=mid_high_crossover_hz),
        ]
    )
    board_high = Pedalboard(
        [HighpassFilter(cutoff_frequency_hz=mid_high_crossover_hz)]
    )

    low = board_low(audio_ch_first, sr)
    mid = board_mid(audio_ch_first, sr)
    high = board_high(audio_ch_first, sr)

    return low, mid, high


def _apply_multiband_eq_to_file(
    row: MultibandEQRow,
    input_media_dir: Path,
    output_media_dir: Path,
    low_mid_crossover_hz: float,
    mid_high_crossover_hz: float,
) -> MultibandEQCorrectionResult:
    """
    Aplica multiband comp/EQ "casero pero profesional" a un stem:

      - Split en 3 bandas (low/mid/high).
      - Compresión y saturación ligera por banda, adaptada a:
          * pista vocal
          * bus FX
          * resto de instrumentos
      - Ganas por banda basadas en suggested_* del análisis.
    """
    base_input_path = (input_media_dir / row.relative_path).resolve()
    input_path = base_input_path

    if not input_path.exists():
        raise FileNotFoundError(
            f"No se encontró el WAV de entrada para multiband EQ: {input_path}"
        )

    output_media_dir.mkdir(parents=True, exist_ok=True)
    output_path = (output_media_dir / row.filename).resolve()

    # Leer audio como (C, N)
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

    # Split en bandas
    low, mid, high = _split_into_bands(
        audio,
        sr,
        low_mid_crossover_hz=low_mid_crossover_hz,
        mid_high_crossover_hz=mid_high_crossover_hz,
    )

    # ------------------------------------------------------------------
    # Parámetros por tipo de pista
    # ------------------------------------------------------------------
    is_vocal = row.is_vocal
    is_bus_fx = row.is_bus_fx

    # Ganancias de EQ propuestas (ya moderadas en el análisis)
    low_gain_db = row.suggested_low_gain_db
    mid_gain_db = row.suggested_mid_gain_db
    high_gain_db = row.suggested_high_gain_db

    # Clamps adicionales por seguridad
    if is_bus_fx:
        # No queremos reventar FX: EQ muy suave
        low_gain_db = float(np.clip(low_gain_db, -2.0, 2.0))
        mid_gain_db = float(np.clip(mid_gain_db, -2.0, 2.0))
        high_gain_db = float(np.clip(high_gain_db, -2.0, 2.0))
    else:
        # En instrumentos normales permitimos hasta ±4 dB
        low_gain_db = float(np.clip(low_gain_db, -4.0, 4.0))
        mid_gain_db = float(np.clip(mid_gain_db, -4.0, 4.0))
        high_gain_db = float(np.clip(high_gain_db, -4.0, 4.0))

    # Compresión / saturación por tipo
    if is_vocal and not is_bus_fx:
        # Voz: comp media en medios/altos, muy poca saturación
        low_thresh = -28.0
        low_ratio = 2.0
        low_drive = 0.0

        mid_thresh = -22.0
        mid_ratio = 2.5
        mid_drive = 1.5

        high_thresh = -24.0
        high_ratio = 1.8
        high_drive = 1.5

    elif is_bus_fx:
        # Buses FX: prácticamente solo glue, cero distorsión
        low_thresh = -26.0
        low_ratio = 1.3
        low_drive = 0.0

        mid_thresh = -26.0
        mid_ratio = 1.2
        mid_drive = 0.0

        high_thresh = -26.0
        high_ratio = 1.2
        high_drive = 0.0

    else:
        # Instrumentos generales (drums, bass, guitars, keys...)
        low_thresh = -24.0
        low_ratio = 2.5
        low_drive = 0.5  # un pelín de saturación en graves

        mid_thresh = -20.0
        mid_ratio = 2.0
        mid_drive = 1.5  # presencia

        high_thresh = -22.0
        high_ratio = 1.5
        high_drive = 1.0  # aire suave

    # ------------------------------------------------------------------
    # Cadenas por banda
    # ------------------------------------------------------------------
    board_low = Pedalboard(
        [
            Compressor(
                threshold_db=low_thresh,
                ratio=low_ratio,
                attack_ms=25.0,
                release_ms=220.0,
            ),
            Distortion(drive_db=low_drive),
            Gain(gain_db=low_gain_db),
        ]
    )

    board_mid = Pedalboard(
        [
            Compressor(
                threshold_db=mid_thresh,
                ratio=mid_ratio,
                attack_ms=20.0,
                release_ms=180.0,
            ),
            Distortion(drive_db=mid_drive),
            Gain(gain_db=mid_gain_db),
        ]
    )

    board_high = Pedalboard(
        [
            Compressor(
                threshold_db=high_thresh,
                ratio=high_ratio,
                attack_ms=10.0,
                release_ms=120.0,
            ),
            Distortion(drive_db=high_drive),
            Gain(gain_db=high_gain_db),
        ]
    )

    low_proc = board_low(low, sample_rate=sr)
    mid_proc = board_mid(mid, sample_rate=sr)
    high_proc = board_high(high, sample_rate=sr)

    processed = low_proc + mid_proc + high_proc

    if processed.size > 0:
        processed_peak = float(np.max(np.abs(processed)))
        processed_rms = float(np.sqrt(np.mean(processed**2)))
    else:
        processed_peak = 0.0
        processed_rms = 0.0

    # Anti-clipping global
    if processed_peak > 0.98:
        norm_gain = 0.98 / processed_peak
        processed *= norm_gain
        processed_peak *= norm_gain
        processed_rms *= norm_gain

    resulting_peak_dbfs = _safe_dbfs(processed_peak)
    resulting_rms_dbfs = _safe_dbfs(processed_rms)

    # Guardar WAV procesado
    with AudioFile(str(output_path), "w", sr, num_channels) as f:
        f.write(processed.astype(np.float32, copy=False))

    return MultibandEQCorrectionResult(
        filename=row.filename,
        input_path=input_path,
        output_path=output_path,
        sample_rate=sr,
        num_channels=num_channels,
        duration_seconds=row.duration_seconds,
        is_vocal=is_vocal,
        is_bus_fx=is_bus_fx,
        bus_key=row.bus_key,
        low_mid_crossover_hz=low_mid_crossover_hz,
        mid_high_crossover_hz=mid_high_crossover_hz,
        low_comp_threshold_dbfs=low_thresh,
        low_comp_ratio=low_ratio,
        low_distortion_drive_db=low_drive,
        low_gain_db=low_gain_db,
        mid_comp_threshold_dbfs=mid_thresh,
        mid_comp_ratio=mid_ratio,
        mid_distortion_drive_db=mid_drive,
        mid_gain_db=mid_gain_db,
        high_comp_threshold_dbfs=high_thresh,
        high_comp_ratio=high_ratio,
        high_distortion_drive_db=high_drive,
        high_gain_db=high_gain_db,
        original_peak_dbfs=original_peak_dbfs,
        original_rms_dbfs=original_rms_dbfs,
        resulting_peak_dbfs=resulting_peak_dbfs,
        resulting_rms_dbfs=resulting_rms_dbfs,
    )


# ----------------------------------------------------------------------
# Log CSV
# ----------------------------------------------------------------------


def write_multiband_eq_log(
    results: List[MultibandEQCorrectionResult],
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
        "is_bus_fx",
        "bus_key",
        "low_mid_crossover_hz",
        "mid_high_crossover_hz",
        "low_comp_threshold_dbfs",
        "low_comp_ratio",
        "low_distortion_drive_db",
        "low_gain_db",
        "mid_comp_threshold_dbfs",
        "mid_comp_ratio",
        "mid_distortion_drive_db",
        "mid_gain_db",
        "high_comp_threshold_dbfs",
        "high_comp_ratio",
        "high_distortion_drive_db",
        "high_gain_db",
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
                    "is_bus_fx": "1" if r.is_bus_fx else "0",
                    "bus_key": r.bus_key or "",
                    "low_mid_crossover_hz": f"{r.low_mid_crossover_hz:.2f}",
                    "mid_high_crossover_hz": f"{r.mid_high_crossover_hz:.2f}",
                    "low_comp_threshold_dbfs": f"{r.low_comp_threshold_dbfs:.2f}",
                    "low_comp_ratio": f"{r.low_comp_ratio:.2f}",
                    "low_distortion_drive_db": f"{r.low_distortion_drive_db:.2f}",
                    "low_gain_db": f"{r.low_gain_db:.2f}",
                    "mid_comp_threshold_dbfs": f"{r.mid_comp_threshold_dbfs:.2f}",
                    "mid_comp_ratio": f"{r.mid_comp_ratio:.2f}",
                    "mid_distortion_drive_db": f"{r.mid_distortion_drive_db:.2f}",
                    "mid_gain_db": f"{r.mid_gain_db:.2f}",
                    "high_comp_threshold_dbfs": f"{r.high_comp_threshold_dbfs:.2f}",
                    "high_comp_ratio": f"{r.high_comp_ratio:.2f}",
                    "high_distortion_drive_db": f"{r.high_distortion_drive_db:.2f}",
                    "high_gain_db": f"{r.high_gain_db:.2f}",
                    "original_peak_dbfs": f"{r.original_peak_dbfs:.2f}",
                    "original_rms_dbfs": f"{r.original_rms_dbfs:.2f}",
                    "resulting_peak_dbfs": f"{r.resulting_peak_dbfs:.2f}",
                    "resulting_rms_dbfs": f"{r.resulting_rms_dbfs:.2f}",
                }
            )


# ----------------------------------------------------------------------
# Stage basado en BaseCorrectionStage
# ----------------------------------------------------------------------


class MultibandEQStage(
    BaseCorrectionStage[MultibandEQRow, MultibandEQCorrectionResult]
):
    def __init__(
        self,
        analysis_csv_path: Path,
        input_media_dir: Path,
        output_media_dir: Path,
        low_mid_crossover_hz: float = 120.0,
        mid_high_crossover_hz: float = 5000.0,
    ) -> None:
        super().__init__(
            analysis_csv_path=analysis_csv_path,
            input_media_dir=input_media_dir,
            output_media_dir=output_media_dir,
        )
        self.low_mid_crossover_hz = low_mid_crossover_hz
        self.mid_high_crossover_hz = mid_high_crossover_hz

    def load_rows(self) -> List[MultibandEQRow]:
        return load_multiband_eq_csv(self.analysis_csv_path)

    def process_row(self, row: MultibandEQRow) -> MultibandEQCorrectionResult:
        return _apply_multiband_eq_to_file(
            row=row,
            input_media_dir=self.input_media_dir,
            output_media_dir=self.output_media_dir,
            low_mid_crossover_hz=self.low_mid_crossover_hz,
            mid_high_crossover_hz=self.mid_high_crossover_hz,
        )

    def write_log(
        self,
        results: List[MultibandEQCorrectionResult],
    ) -> Path:
        log_csv_path = self.output_media_dir / "multiband_eq_correction_log.csv"
        write_multiband_eq_log(results, log_csv_path)
        return log_csv_path


def run_multiband_eq_correction(
    analysis_csv_path: Path,
    input_media_dir: Path,
    output_media_dir: Path,
    low_mid_crossover_hz: float = 120.0,
    mid_high_crossover_hz: float = 5000.0,
) -> Path:
    """
    Punto de entrada de alto nivel para aplicar multiband EQ / comp a todos
    los stems de un directorio.
    """
    stage = MultibandEQStage(
        analysis_csv_path=analysis_csv_path,
        input_media_dir=input_media_dir,
        output_media_dir=output_media_dir,
        low_mid_crossover_hz=low_mid_crossover_hz,
        mid_high_crossover_hz=mid_high_crossover_hz,
    )
    return stage.run()
