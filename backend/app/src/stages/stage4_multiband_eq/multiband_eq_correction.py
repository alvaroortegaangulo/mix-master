# src/stages/stage4_multiband_eq/multiband_eq_correction.py
from __future__ import annotations

import json
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


def _safe_dbfs(value: float, floor: float = -120.0) -> float:
    v = float(value)
    if v <= 0.0:
        return floor
    return 20.0 * np.log10(v)


def _parse_float(val, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _parse_bool(val) -> bool:
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    return str(val).strip().lower() in {"1", "true", "t", "yes", "y"}


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


def load_multiband_eq_json(json_path: Path) -> List[MultibandEQRow]:
    if not json_path.exists():
        raise FileNotFoundError(
            f"No se encontro el JSON de analisis multibanda: {json_path}"
        )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Formato JSON inesperado en {json_path}")

    rows: List[MultibandEQRow] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        rows.append(
            MultibandEQRow(
                filename=item.get("filename") or Path(item.get("file_path", "")).name,
                relative_path=item.get("relative_path") or item.get("filename") or Path(item.get("file_path", "")).name,
                sample_rate=int(item.get("sample_rate", 0)),
                num_channels=int(item.get("num_channels", 0)),
                duration_seconds=float(item.get("duration_seconds", 0.0)),
                is_vocal=_parse_bool(item.get("is_vocal", False)),
                is_bus_fx=_parse_bool(item.get("is_bus_fx", False)),
                bus_key=item.get("bus_key"),
                low_rms_dbfs=_parse_float(item.get("low_rms_dbfs"), -120.0),
                mid_rms_dbfs=_parse_float(item.get("mid_rms_dbfs"), -120.0),
                high_rms_dbfs=_parse_float(item.get("high_rms_dbfs"), -120.0),
                full_rms_dbfs=_parse_float(item.get("full_rms_dbfs"), -120.0),
                suggested_low_gain_db=_parse_float(item.get("suggested_low_gain_db"), 0.0),
                suggested_mid_gain_db=_parse_float(item.get("suggested_mid_gain_db"), 0.0),
                suggested_high_gain_db=_parse_float(item.get("suggested_high_gain_db"), 0.0),
            )
        )
    return rows


def _split_into_bands(
    audio_ch_first: np.ndarray,
    sr: int,
    low_mid_crossover_hz: float,
    mid_high_crossover_hz: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
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
    input_path = (input_media_dir / row.relative_path).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"No se encontro el stem de entrada: {input_path}")

    output_media_dir.mkdir(parents=True, exist_ok=True)
    output_path = (output_media_dir / row.filename).resolve()

    with AudioFile(str(input_path), "r") as f:
        audio = f.read(f.frames)
        sr = f.samplerate
        num_channels = f.num_channels

    audio = audio.astype(np.float32, copy=False)

    if audio.size > 0:
        original_peak_lin = float(np.max(np.abs(audio)))
        original_rms_lin = float(np.sqrt(np.mean(audio * audio)))
    else:
        original_peak_lin = 0.0
        original_rms_lin = 0.0

    original_peak_dbfs = _safe_dbfs(original_peak_lin)
    original_rms_dbfs = _safe_dbfs(original_rms_lin)

    audio_ch_first = audio  # pedalboard ya entrega (C, N)

    low, mid, high = _split_into_bands(
        audio_ch_first=audio_ch_first,
        sr=sr,
        low_mid_crossover_hz=low_mid_crossover_hz,
        mid_high_crossover_hz=mid_high_crossover_hz,
    )

    def _compute_gain_and_fx(
        band_name: str,
        suggested_gain_db: float,
        is_vocal: bool,
        is_bus_fx: bool,
    ) -> tuple[float, float, float, float]:
        gain_db = float(np.clip(suggested_gain_db, -6.0, 6.0))
        if band_name == "low":
            comp_threshold = min(row.low_rms_dbfs + 4.0, -10.0)
            comp_ratio = 2.0 if is_bus_fx else 1.8
            distortion_db = 0.5 if is_vocal else 1.0
        elif band_name == "mid":
            comp_threshold = min(row.mid_rms_dbfs + 3.0, -9.0)
            comp_ratio = 2.0 if is_bus_fx else 1.7
            distortion_db = 0.4 if is_vocal else 0.8
        else:
            comp_threshold = min(row.high_rms_dbfs + 2.0, -8.0)
            comp_ratio = 1.6 if is_bus_fx else 1.5
            distortion_db = 0.2 if is_vocal else 0.6

        if is_vocal:
            comp_ratio *= 1.05
            distortion_db *= 0.7

        return gain_db, comp_threshold, comp_ratio, distortion_db

    low_gain_db, low_comp_thr, low_comp_ratio, low_dist_db = _compute_gain_and_fx(
        "low", row.suggested_low_gain_db, row.is_vocal, row.is_bus_fx
    )
    mid_gain_db, mid_comp_thr, mid_comp_ratio, mid_dist_db = _compute_gain_and_fx(
        "mid", row.suggested_mid_gain_db, row.is_vocal, row.is_bus_fx
    )
    high_gain_db, high_comp_thr, high_comp_ratio, high_dist_db = _compute_gain_and_fx(
        "high", row.suggested_high_gain_db, row.is_vocal, row.is_bus_fx
    )

    def _build_band_chain(
        comp_threshold: float, comp_ratio: float, dist_db: float, gain_db: float
    ) -> List:
        fx = [
            Compressor(
                threshold_db=comp_threshold,
                ratio=comp_ratio,
                attack_ms=12.0,
                release_ms=160.0,
            )
        ]
        if abs(dist_db) > 0.05:
            fx.append(Distortion(drive_db=dist_db))
        if abs(gain_db) > 0.05:
            fx.append(Gain(gain_db=gain_db))
        return fx

    board_low = Pedalboard(_build_band_chain(low_comp_thr, low_comp_ratio, low_dist_db, low_gain_db))
    board_mid = Pedalboard(_build_band_chain(mid_comp_thr, mid_comp_ratio, mid_dist_db, mid_gain_db))
    board_high = Pedalboard(_build_band_chain(high_comp_thr, high_comp_ratio, high_dist_db, high_gain_db))

    low_proc = board_low(low, sample_rate=sr)
    mid_proc = board_mid(mid, sample_rate=sr)
    high_proc = board_high(high, sample_rate=sr)

    mixed = low_proc + mid_proc + high_proc

    if mixed.size > 0:
        peak_lin = float(np.max(np.abs(mixed)))
        rms_lin = float(np.sqrt(np.mean(mixed * mixed)))
    else:
        peak_lin = 0.0
        rms_lin = 0.0

    if peak_lin > 0.999:
        mixed *= (0.999 / peak_lin)
        peak_lin = 0.999

    resulting_peak_dbfs = _safe_dbfs(peak_lin)
    resulting_rms_dbfs = _safe_dbfs(rms_lin)

    with AudioFile(str(output_path), "w", sr, num_channels) as f:
        f.write(mixed.astype(np.float32, copy=False))

    return MultibandEQCorrectionResult(
        filename=row.filename,
        input_path=input_path,
        output_path=output_path,
        sample_rate=sr,
        num_channels=num_channels,
        duration_seconds=row.duration_seconds,
        is_vocal=row.is_vocal,
        is_bus_fx=row.is_bus_fx,
        bus_key=row.bus_key,
        low_mid_crossover_hz=low_mid_crossover_hz,
        mid_high_crossover_hz=mid_high_crossover_hz,
        low_comp_threshold_dbfs=low_comp_thr,
        low_comp_ratio=low_comp_ratio,
        low_distortion_drive_db=low_dist_db,
        low_gain_db=low_gain_db,
        mid_comp_threshold_dbfs=mid_comp_thr,
        mid_comp_ratio=mid_comp_ratio,
        mid_distortion_drive_db=mid_dist_db,
        mid_gain_db=mid_gain_db,
        high_comp_threshold_dbfs=high_comp_thr,
        high_comp_ratio=high_comp_ratio,
        high_distortion_drive_db=high_dist_db,
        high_gain_db=high_gain_db,
        original_peak_dbfs=original_peak_dbfs,
        original_rms_dbfs=original_rms_dbfs,
        resulting_peak_dbfs=resulting_peak_dbfs,
        resulting_rms_dbfs=resulting_rms_dbfs,
    )


def write_multiband_eq_log_json(
    results: List[MultibandEQCorrectionResult],
    log_json_path: Path,
) -> Path:
    log_json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = []
    for r in results:
        payload.append(
            {
                "filename": r.filename,
                "input_path": str(r.input_path),
                "output_path": str(r.output_path),
                "sample_rate": r.sample_rate,
                "num_channels": r.num_channels,
                "duration_seconds": r.duration_seconds,
                "is_vocal": r.is_vocal,
                "is_bus_fx": r.is_bus_fx,
                "bus_key": r.bus_key,
                "low_mid_crossover_hz": r.low_mid_crossover_hz,
                "mid_high_crossover_hz": r.mid_high_crossover_hz,
                "low_comp_threshold_dbfs": r.low_comp_threshold_dbfs,
                "low_comp_ratio": r.low_comp_ratio,
                "low_distortion_drive_db": r.low_distortion_drive_db,
                "low_gain_db": r.low_gain_db,
                "mid_comp_threshold_dbfs": r.mid_comp_threshold_dbfs,
                "mid_comp_ratio": r.mid_comp_ratio,
                "mid_distortion_drive_db": r.mid_distortion_drive_db,
                "mid_gain_db": r.mid_gain_db,
                "high_comp_threshold_dbfs": r.high_comp_threshold_dbfs,
                "high_comp_ratio": r.high_comp_ratio,
                "high_distortion_drive_db": r.high_distortion_drive_db,
                "high_gain_db": r.high_gain_db,
                "original_peak_dbfs": r.original_peak_dbfs,
                "original_rms_dbfs": r.original_rms_dbfs,
                "resulting_peak_dbfs": r.resulting_peak_dbfs,
                "resulting_rms_dbfs": r.resulting_rms_dbfs,
            }
        )
    log_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return log_json_path


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
        return load_multiband_eq_json(self.analysis_csv_path)

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
        log_json_path = self.output_media_dir / "multiband_eq_correction_log.json"
        return write_multiband_eq_log_json(results, log_json_path)


def run_multiband_eq_correction(
    analysis_json_path: Path,
    input_media_dir: Path,
    output_media_dir: Path,
    low_mid_crossover_hz: float = 120.0,
    mid_high_crossover_hz: float = 5000.0,
) -> Path:
    stage = MultibandEQStage(
        analysis_csv_path=analysis_json_path,
        input_media_dir=input_media_dir,
        output_media_dir=output_media_dir,
        low_mid_crossover_hz=low_mid_crossover_hz,
        mid_high_crossover_hz=mid_high_crossover_hz,
    )
    return stage.run()
