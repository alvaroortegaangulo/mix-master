# src/stages/stage1_loudness/loudness_correction.py

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import soundfile as sf

from src.utils.mixdown import mix_corrected_stems_to_full_song, FullSongRenderResult
from src.utils.stage_base import BaseCorrectionStage


# ----------------------------------------------------------------------
# Modelos de datos
# ----------------------------------------------------------------------


@dataclass
class LoudnessAnalysisRow:
    """Fila del JSON de loudness_analysis."""
    filename: str
    relative_path: str
    is_full_song: bool
    sample_rate: int
    num_channels: int
    duration_seconds: float
    peak_dbfs: float
    rms_dbfs: float
    loudness_stevens: Optional[float]
    replaygain_gain_db: Optional[float]
    target_rms_dbfs: float
    gain_db_to_target_rms: float


@dataclass
class LoudnessCorrectionResult:
    """Resultado de la correccion de loudness de un stem."""
    filename: str
    input_path: Path
    output_path: Path
    is_full_song_source: bool
    sample_rate: int
    num_channels: int
    duration_seconds: float

    original_peak_dbfs: float
    original_rms_dbfs: float
    original_replaygain_gain_db: Optional[float]
    original_gain_db_to_target_rms: float

    applied_gain_db: float
    resulting_peak_dbfs: float
    resulting_rms_dbfs: float
    clipped_after: bool


# ----------------------------------------------------------------------
# Utilidades numericas
# ----------------------------------------------------------------------


def _safe_dbfs(value: float, floor: float = -120.0) -> float:
    value = float(value)
    if value <= 0.0:
        return floor
    return 20.0 * np.log10(value)


def _parse_optional_float(s: str) -> Optional[float]:
    s = s.strip()
    if not s:
        return None
    return float(s)


def _dbfs_to_linear(db_value: float) -> float:
    if db_value <= -120.0:
        return 0.0
    return float(10.0 ** (db_value / 20.0))


# ----------------------------------------------------------------------
# Lectura del JSON de analisis
# ----------------------------------------------------------------------


def load_loudness_analysis(json_path: Path) -> List[LoudnessAnalysisRow]:
    """Carga loudness_analysis.json generado en la fase de analisis."""
    if not json_path.exists():
        raise FileNotFoundError(f"No se encontro el JSON de analisis de loudness: {json_path}")

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Formato de JSON inesperado en {json_path}")

    rows: List[LoudnessAnalysisRow] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        loudness_stevens = _parse_optional_float(str(item.get("loudness_stevens", "")).strip())
        replaygain_gain_db = _parse_optional_float(str(item.get("replaygain_gain_db", "")).strip())
        try:
            rows.append(
                LoudnessAnalysisRow(
                    filename=item.get("filename") or item.get("file_path") or "",
                    relative_path=item.get("relative_path") or item.get("filename") or item.get("file_path") or "",
                    is_full_song=bool(item.get("is_full_song", False)),
                    sample_rate=int(item.get("sample_rate", 0)),
                    num_channels=int(item.get("num_channels", 0)),
                    duration_seconds=float(item.get("duration_seconds", 0.0)),
                    peak_dbfs=float(item.get("peak_dbfs", 0.0)),
                    rms_dbfs=float(item.get("rms_dbfs", 0.0)),
                    loudness_stevens=loudness_stevens,
                    replaygain_gain_db=replaygain_gain_db,
                    target_rms_dbfs=float(item.get("target_rms_dbfs", -18.0)),
                    gain_db_to_target_rms=float(item.get("gain_db_to_target_rms", 0.0)),
                )
            )
        except Exception:
            continue
    return rows


# ----------------------------------------------------------------------
# Correccion de loudness de un solo stem
# ----------------------------------------------------------------------


def _apply_loudness_correction_to_file(
    row: LoudnessAnalysisRow,
    input_media_dir: Path,
    output_media_dir: Path,
    mode: str = "rms",  # "rms" o "replaygain"
) -> LoudnessCorrectionResult:
    """
    Aplica la correccion de loudness a un unico archivo (streaming, sin cargar todo en memoria).
    """
    input_path = (input_media_dir / row.relative_path).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"No se encontro el WAV de entrada: {input_path}")

    output_media_dir.mkdir(parents=True, exist_ok=True)
    output_path = (output_media_dir / row.filename).resolve()

    if mode == "replaygain" and row.replaygain_gain_db is not None:
        base_gain_db = row.replaygain_gain_db
    else:
        base_gain_db = row.gain_db_to_target_rms

    original_peak_dbfs = row.peak_dbfs
    original_rms_dbfs = row.rms_dbfs
    original_peak_lin = _dbfs_to_linear(original_peak_dbfs)
    original_rms_lin = _dbfs_to_linear(original_rms_dbfs)

    base_gain_lin = 10.0 ** (base_gain_db / 20.0)
    predicted_peak = original_peak_lin * base_gain_lin

    scale_factor = 1.0
    if predicted_peak > 0.98:
        scale_factor = 0.98 / max(predicted_peak, 1e-9)

    total_gain_lin = base_gain_lin * scale_factor
    applied_gain_db = base_gain_db + _safe_dbfs(scale_factor)

    resulting_peak_lin = original_peak_lin * total_gain_lin
    resulting_rms_lin = original_rms_lin * total_gain_lin
    resulting_peak_dbfs = _safe_dbfs(resulting_peak_lin)
    resulting_rms_dbfs = _safe_dbfs(resulting_rms_lin)
    clipped_after = resulting_peak_lin > 1.0

    block_size = 262144  # frames; reduce overhead de IO
    sr = row.sample_rate
    num_channels = row.num_channels

    with sf.SoundFile(str(input_path), mode="r") as f_in, sf.SoundFile(
        str(output_path),
        mode="w",
        samplerate=f_in.samplerate,
        channels=f_in.channels,
        subtype=f_in.subtype,
    ) as f_out:
        sr = f_in.samplerate
        num_channels = f_in.channels
        while True:
            block = f_in.read(block_size, dtype="float32", always_2d=True)
            if block.size == 0:
                break
            np.multiply(block, total_gain_lin, out=block)
            f_out.write(block)

    return LoudnessCorrectionResult(
        filename=row.filename,
        input_path=input_path,
        output_path=output_path,
        is_full_song_source=row.is_full_song,
        sample_rate=sr,
        num_channels=num_channels,
        duration_seconds=row.duration_seconds,
        original_peak_dbfs=original_peak_dbfs,
        original_rms_dbfs=original_rms_dbfs,
        original_replaygain_gain_db=row.replaygain_gain_db,
        original_gain_db_to_target_rms=row.gain_db_to_target_rms,
        applied_gain_db=applied_gain_db,
        resulting_peak_dbfs=resulting_peak_dbfs,
        resulting_rms_dbfs=resulting_rms_dbfs,
        clipped_after=clipped_after,
    )


# ----------------------------------------------------------------------
# Escritura del log de correccion
# ----------------------------------------------------------------------


def write_loudness_correction_log(
    stem_results: List[LoudnessCorrectionResult],
    full_song_result: FullSongRenderResult,
    log_json_path: Path,
) -> None:
    """
    Crea un JSON con el detalle de las correcciones aplicadas a cada stem y el render del full_song.
    """
    log_json_path.parent.mkdir(parents=True, exist_ok=True)

    stems_payload = []
    for r in stem_results:
        stems_payload.append({
            "filename": r.filename,
            "type": "stem",
            "input_path": str(r.input_path),
            "output_path": str(r.output_path),
            "is_full_song_source": bool(r.is_full_song_source),
            "sample_rate": r.sample_rate,
            "num_channels": r.num_channels,
            "duration_seconds": r.duration_seconds,
            "original_peak_dbfs": r.original_peak_dbfs,
            "original_rms_dbfs": r.original_rms_dbfs,
            "original_replaygain_gain_db": r.original_replaygain_gain_db,
            "original_gain_db_to_target_rms": r.original_gain_db_to_target_rms,
            "applied_gain_db": r.applied_gain_db,
            "resulting_peak_dbfs": r.resulting_peak_dbfs,
            "resulting_rms_dbfs": r.resulting_rms_dbfs,
            "clipped_after": bool(r.clipped_after),
        })

    full_song_payload = {
        "filename": full_song_result.filename,
        "type": "full_song",
        "output_path": str(full_song_result.output_path),
        "sample_rate": full_song_result.sample_rate,
        "num_channels": full_song_result.num_channels,
        "duration_seconds": full_song_result.duration_seconds,
        "mix_gain_db": full_song_result.mix_gain_db,
        "full_song_peak_dbfs": full_song_result.peak_dbfs,
        "full_song_rms_dbfs": full_song_result.rms_dbfs,
        "full_song_clipped_before_mix_gain": bool(full_song_result.clipped_before_mix_gain),
        "full_song_clipped_after_mix_gain": bool(full_song_result.clipped_after_mix_gain),
    }

    payload = {
        "stems": stems_payload,
        "full_song": full_song_payload,
    }

    log_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


# ----------------------------------------------------------------------
# Punto de entrada de alto nivel
# ----------------------------------------------------------------------


class LoudnessCorrectionStage(
    BaseCorrectionStage[LoudnessAnalysisRow, LoudnessCorrectionResult]
):
    """
    Etapa de correccion de loudness basada en BaseCorrectionStage.

    Adicionalmente:
      - Mezcla los stems corregidos a full_song.wav.
      - Permite elegir modo "rms" o "replaygain".
    """

    def __init__(
        self,
        analysis_json_path: Path,
        input_media_dir: Path,
        output_media_dir: Path,
        mode: str = "rms",
    ) -> None:
        super().__init__(
            analysis_json_path=analysis_json_path,
            input_media_dir=input_media_dir,
            output_media_dir=output_media_dir,
        )
        self.mode = mode

    def load_rows(self) -> List[LoudnessAnalysisRow]:
        return load_loudness_analysis(self.analysis_json_path)

    def process_row(self, row: LoudnessAnalysisRow) -> LoudnessCorrectionResult:
        return _apply_loudness_correction_to_file(
            row=row,
            input_media_dir=self.input_media_dir,
            output_media_dir=self.output_media_dir,
            mode=self.mode,
        )

    def write_log(self, results: List[LoudnessCorrectionResult]) -> Path:
        """
        Implementacion por si alguien usa stage.run() directamente.
        Mezcla los stems y genera full_song.wav, pero devuelve solo la ruta al log JSON.
        """
        full_song_result = mix_corrected_stems_to_full_song(self.output_media_dir)
        log_json_path = self.output_media_dir / "loudness_correction_log.json"
        write_loudness_correction_log(results, full_song_result, log_json_path)
        return log_json_path

    def run(self) -> Tuple[Path, Path]:
        """
        Ejecuta la etapa de loudness y devuelve:
            (ruta_log_json, ruta_full_song_corregido)
        """
        stem_results = self.process_all_rows()
        full_song_result = mix_corrected_stems_to_full_song(self.output_media_dir)
        log_json_path = self.output_media_dir / "loudness_correction_log.json"
        write_loudness_correction_log(stem_results, full_song_result, log_json_path)
        return log_json_path, full_song_result.output_path


def run_loudness_correction(
    analysis_json_path: Path,
    input_media_dir: Path,
    output_media_dir: Path,
    mode: str = "rms",
) -> Tuple[Path, Path]:
    """
    Punto de entrada de alto nivel para la correccion de loudness.

    Implementado mediante LoudnessCorrectionStage para unificar el patron de etapas.
    """
    stage = LoudnessCorrectionStage(
        analysis_json_path=analysis_json_path,
        input_media_dir=input_media_dir,
        output_media_dir=output_media_dir,
        mode=mode,
    )
    return stage.run()
