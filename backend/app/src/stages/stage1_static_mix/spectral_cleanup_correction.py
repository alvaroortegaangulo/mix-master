from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List

import math
import numpy as np
from pedalboard import Pedalboard, HighpassFilter, PeakFilter
from pedalboard.io import AudioFile

from src.utils.stage_base import BaseCorrectionStage


@dataclass
class NotchSpec:
    freq_hz: float
    q: float
    gain_db: float


@dataclass
class SpectralCleanupRow:
    filename: str
    relative_path: str
    sample_rate: int
    num_channels: int
    duration_seconds: float
    recommended_hpf_cutoff_hz: float
    low_band_energy_ratio_0_40: float
    low_band_energy_ratio_40_80: float
    low_band_energy_ratio_80_160: float
    instrument_profile: str
    notches: List[NotchSpec]


@dataclass
class SpectralCleanupCorrectionResult:
    filename: str
    input_path: Path
    output_path: Path
    sample_rate: int
    num_channels: int
    duration_seconds: float
    instrument_profile: str
    recommended_hpf_cutoff_hz: float
    num_notches: int
    original_peak_dbfs: float
    original_rms_dbfs: float
    resulting_peak_dbfs: float
    resulting_rms_dbfs: float


def _safe_dbfs(value: float, floor: float = -120.0) -> float:
    value = float(value)
    if value <= 0.0:
        return floor
    return 20.0 * np.log10(value)


def load_spectral_cleanup_json(json_path: Path, max_notches: int = 4) -> List[SpectralCleanupRow]:
    if not json_path.exists():
        raise FileNotFoundError(f"No se encontro el JSON de analisis espectral: {json_path}")

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Formato de JSON inesperado en {json_path}")

    rows: List[SpectralCleanupRow] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        notches_raw = item.get("notches") or []
        notches: List[NotchSpec] = []
        for n in notches_raw[:max_notches]:
            try:
                notches.append(
                    NotchSpec(
                        freq_hz=float(n.get("freq_hz", 0.0)),
                        q=float(n.get("q", 6.0)),
                        gain_db=float(n.get("gain_db", -3.0)),
                    )
                )
            except Exception:
                continue
        try:
            rows.append(
                SpectralCleanupRow(
                    filename=item.get("filename") or item.get("file_path") or "",
                    relative_path=item.get("relative_path") or item.get("filename") or item.get("file_path") or "",
                    sample_rate=int(item.get("sample_rate", 0)),
                    num_channels=int(item.get("num_channels", 0)),
                    duration_seconds=float(item.get("duration_seconds", 0.0)),
                    recommended_hpf_cutoff_hz=float(item.get("recommended_hpf_cutoff_hz", 0.0)),
                    low_band_energy_ratio_0_40=float(item.get("low_band_energy_ratio_0_40", 0.0)),
                    low_band_energy_ratio_40_80=float(item.get("low_band_energy_ratio_40_80", 0.0)),
                    low_band_energy_ratio_80_160=float(item.get("low_band_energy_ratio_80_160", 0.0)),
                    instrument_profile=item.get("instrument_profile", ""),
                    notches=notches,
                )
            )
        except Exception:
            continue
    return rows


def _apply_spectral_cleanup_to_file(
    row: SpectralCleanupRow,
    input_media_dir: Path,
    output_media_dir: Path,
) -> SpectralCleanupCorrectionResult:
    input_path = (input_media_dir / row.relative_path).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"No se encontro el WAV de entrada: {input_path}")

    output_media_dir.mkdir(parents=True, exist_ok=True)
    output_path = (output_media_dir / row.filename).resolve()

    block_size = 262144
    original_peak = 0.0
    original_sum_sq = 0.0
    original_frames = 0
    processed_peak = 0.0
    processed_sum_sq = 0.0
    processed_frames = 0

    effects = []
    if row.recommended_hpf_cutoff_hz > 0.0:
        effects.append(HighpassFilter(cutoff_frequency_hz=row.recommended_hpf_cutoff_hz))

    nyq = row.sample_rate / 2.0 if row.sample_rate else None
    for notch in row.notches:
        if abs(notch.gain_db) < 0.1:
            continue
        if nyq and (notch.freq_hz <= 0.0 or notch.freq_hz >= nyq):
            continue
        effects.append(
            PeakFilter(
                cutoff_frequency_hz=notch.freq_hz,
                gain_db=notch.gain_db,
                q=notch.q,
            )
        )

    board = Pedalboard(effects) if effects else None

    with AudioFile(str(input_path), "r") as f_in:
        sr = f_in.samplerate
        num_channels = f_in.num_channels

        with AudioFile(str(output_path), "w", sr, num_channels) as f_out:
            while True:
                block = f_in.read(block_size)
                if block.size == 0:
                    break

                block = block.astype(np.float32, copy=False)

                if block.size:
                    abs_block = np.abs(block)
                    peak_block = float(abs_block.max())
                    if peak_block > original_peak:
                        original_peak = peak_block
                    original_sum_sq += float(np.square(block, dtype=np.float32).sum())
                    original_frames += block.shape[0] * block.shape[1]

                if board is not None:
                    block = board(block, sample_rate=sr)

                if block.size:
                    abs_proc = np.abs(block)
                    proc_peak = float(abs_proc.max())
                    if proc_peak > processed_peak:
                        processed_peak = proc_peak
                    processed_sum_sq += float(np.square(block, dtype=np.float32).sum())
                    processed_frames += block.shape[0] * block.shape[1]

                f_out.write(block.astype(np.float32, copy=False))

    original_rms = math.sqrt(original_sum_sq / original_frames) if original_frames > 0 else 0.0
    processed_rms = math.sqrt(processed_sum_sq / processed_frames) if processed_frames > 0 else 0.0

    return SpectralCleanupCorrectionResult(
        filename=row.filename,
        input_path=input_path,
        output_path=output_path,
        sample_rate=sr,
        num_channels=num_channels,
        duration_seconds=row.duration_seconds,
        instrument_profile=row.instrument_profile,
        recommended_hpf_cutoff_hz=row.recommended_hpf_cutoff_hz,
        num_notches=len(row.notches),
        original_peak_dbfs=_safe_dbfs(original_peak),
        original_rms_dbfs=_safe_dbfs(original_rms),
        resulting_peak_dbfs=_safe_dbfs(processed_peak),
        resulting_rms_dbfs=_safe_dbfs(processed_rms),
    )


def write_spectral_cleanup_log(
    results: List[SpectralCleanupCorrectionResult],
    log_json_path: Path,
) -> None:
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
                "instrument_profile": r.instrument_profile,
                "recommended_hpf_cutoff_hz": r.recommended_hpf_cutoff_hz,
                "num_notches": r.num_notches,
                "original_peak_dbfs": r.original_peak_dbfs,
                "original_rms_dbfs": r.original_rms_dbfs,
                "resulting_peak_dbfs": r.resulting_peak_dbfs,
                "resulting_rms_dbfs": r.resulting_rms_dbfs,
            }
        )

    log_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class SpectralCleanupStage(BaseCorrectionStage[SpectralCleanupRow, SpectralCleanupCorrectionResult]):
    def __init__(
        self,
        analysis_json_path: Path,
        input_media_dir: Path,
        output_media_dir: Path,
        max_notches: int = 4,
    ) -> None:
        super().__init__(
            analysis_json_path=analysis_json_path,
            input_media_dir=input_media_dir,
            output_media_dir=output_media_dir,
        )
        self.max_notches = max_notches

    def load_rows(self) -> List[SpectralCleanupRow]:
        return load_spectral_cleanup_json(self.analysis_json_path, max_notches=self.max_notches)

    def process_row(self, row: SpectralCleanupRow) -> SpectralCleanupCorrectionResult:
        return _apply_spectral_cleanup_to_file(
            row=row,
            input_media_dir=self.input_media_dir,
            output_media_dir=self.output_media_dir,
        )

    def write_log(self, results: List[SpectralCleanupCorrectionResult]) -> Path:
        log_json_path = self.output_media_dir / "spectral_cleanup_correction_log.json"
        write_spectral_cleanup_log(results, log_json_path)
        return log_json_path


def run_spectral_cleanup_correction(
    analysis_json_path: Path,
    input_media_dir: Path,
    output_media_dir: Path,
    max_notches: int = 4,
) -> Path:
    stage = SpectralCleanupStage(
        analysis_json_path=analysis_json_path,
        input_media_dir=input_media_dir,
        output_media_dir=output_media_dir,
        max_notches=max_notches,
    )
    return stage.run()
