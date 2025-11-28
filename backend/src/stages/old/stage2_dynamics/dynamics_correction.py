from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import List

import numpy as np
from pedalboard import Pedalboard, Compressor, Limiter, Gain
from pedalboard.io import AudioFile

from src.utils.stage_base import BaseCorrectionStage


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


def load_dynamics_json(json_path: Path) -> List[DynamicsRow]:
    if not json_path.exists():
        raise FileNotFoundError(f"No se encontro el JSON de analisis de dinamica: {json_path}")

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Formato de JSON inesperado en {json_path}")

    rows: List[DynamicsRow] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        try:
            rows.append(
                DynamicsRow(
                    filename=item.get("filename") or item.get("file_path") or "",
                    relative_path=item.get("relative_path") or item.get("filename") or item.get("file_path") or "",
                    sample_rate=int(item.get("sample_rate", 0)),
                    num_channels=int(item.get("num_channels", 0)),
                    duration_seconds=float(item.get("duration_seconds", 0.0)),
                    rms_dbfs=float(item.get("rms_dbfs", 0.0)),
                    peak_dbfs=float(item.get("peak_dbfs", 0.0)),
                    crest_factor_db=float(item.get("crest_factor_db", 0.0)),
                    transient_crest_db=float(item.get("transient_crest_db", 0.0)),
                    instrument_profile=item.get("instrument_profile", ""),
                    comp_enabled=bool(item.get("comp_enabled", False)),
                    comp_threshold_dbfs=float(item.get("comp_threshold_dbfs", 0.0)),
                    comp_ratio=float(item.get("comp_ratio", 1.0)),
                    comp_attack_ms=float(item.get("comp_attack_ms", 10.0)),
                    comp_release_ms=float(item.get("comp_release_ms", 100.0)),
                    comp_makeup_gain_db=float(item.get("comp_makeup_gain_db", 0.0)),
                    limiter_enabled=bool(item.get("limiter_enabled", False)),
                    limiter_threshold_dbfs=float(item.get("limiter_threshold_dbfs", -0.5)),
                    limiter_release_ms=float(item.get("limiter_release_ms", 100.0)),
                )
            )
        except Exception:
            continue
    return rows


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


def _apply_dynamics_to_file(
    row: DynamicsRow,
    input_media_dir: Path,
    output_media_dir: Path,
) -> DynamicsCorrectionResult:
    input_path = (input_media_dir / row.relative_path).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"No se encontro el WAV de entrada: {input_path}")

    output_media_dir.mkdir(parents=True, exist_ok=True)
    output_path = (output_media_dir / row.filename).resolve()

    block_size = 262144  # frames; streaming evita cargar todo el audio
    original_peak = 0.0
    original_sum_sq = 0.0
    original_frames = 0

    processed_peak = 0.0
    processed_sum_sq = 0.0
    processed_frames = 0

    effects = []
    if row.comp_enabled:
        effects.append(
            Compressor(
                threshold_db=row.comp_threshold_dbfs,
                ratio=row.comp_ratio,
                attack_ms=row.comp_attack_ms,
                release_ms=row.comp_release_ms,
            )
        )
        if abs(row.comp_makeup_gain_db) > 0.01:
            effects.append(Gain(gain_db=row.comp_makeup_gain_db))

    if row.limiter_enabled:
        effects.append(
            Limiter(
                threshold_db=row.limiter_threshold_dbfs,
                release_ms=row.limiter_release_ms,
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
                    block_abs = np.abs(block)
                    block_peak = float(block_abs.max())
                    if block_peak > original_peak:
                        original_peak = block_peak
                    original_sum_sq += float(np.square(block, dtype=np.float32).sum())
                    original_frames += block.shape[0] * block.shape[1]

                if board is not None:
                    block = board(block, sample_rate=sr)

                if block.size:
                    block_abs_proc = np.abs(block)
                    proc_peak = float(block_abs_proc.max())
                    if proc_peak > processed_peak:
                        processed_peak = proc_peak
                    processed_sum_sq += float(np.square(block, dtype=np.float32).sum())
                    processed_frames += block.shape[0] * block.shape[1]

                f_out.write(block.astype(np.float32, copy=False))

    original_rms = math.sqrt(original_sum_sq / original_frames) if original_frames > 0 else 0.0
    processed_rms = math.sqrt(processed_sum_sq / processed_frames) if processed_frames > 0 else 0.0

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
        original_peak_dbfs=_safe_dbfs(original_peak),
        original_rms_dbfs=_safe_dbfs(original_rms),
        resulting_peak_dbfs=_safe_dbfs(processed_peak),
        resulting_rms_dbfs=_safe_dbfs(processed_rms),
    )


def write_dynamics_correction_log(
    results: List[DynamicsCorrectionResult],
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
                "comp_enabled": bool(r.comp_enabled),
                "comp_threshold_dbfs": r.comp_threshold_dbfs,
                "comp_ratio": r.comp_ratio,
                "comp_attack_ms": r.comp_attack_ms,
                "comp_release_ms": r.comp_release_ms,
                "comp_makeup_gain_db": r.comp_makeup_gain_db,
                "limiter_enabled": bool(r.limiter_enabled),
                "limiter_threshold_dbfs": r.limiter_threshold_dbfs,
                "limiter_release_ms": r.limiter_release_ms,
                "original_peak_dbfs": r.original_peak_dbfs,
                "original_rms_dbfs": r.original_rms_dbfs,
                "resulting_peak_dbfs": r.resulting_peak_dbfs,
                "resulting_rms_dbfs": r.resulting_rms_dbfs,
            }
        )

    log_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class DynamicsCorrectionStage(BaseCorrectionStage[DynamicsRow, DynamicsCorrectionResult]):
    def load_rows(self) -> List[DynamicsRow]:
        return load_dynamics_json(self.analysis_json_path)

    def process_row(self, row: DynamicsRow) -> DynamicsCorrectionResult:
        return _apply_dynamics_to_file(
            row=row,
            input_media_dir=self.input_media_dir,
            output_media_dir=self.output_media_dir,
        )

    def write_log(self, results: List[DynamicsCorrectionResult]) -> Path:
        log_json_path = self.output_media_dir / "dynamics_correction_log.json"
        write_dynamics_correction_log(results, log_json_path)
        return log_json_path


def run_dynamics_correction(
    analysis_json_path: Path,
    input_media_dir: Path,
    output_media_dir: Path,
) -> Path:
    stage = DynamicsCorrectionStage(
        analysis_json_path=analysis_json_path,
        input_media_dir=input_media_dir,
        output_media_dir=output_media_dir,
    )
    return stage.run()
