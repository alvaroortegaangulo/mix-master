# C:\mix\src\analysis\dc_offset_correction.py

from __future__ import annotations

import json
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List

import numpy as np
import soundfile as sf

from src.utils.stage_base import BaseCorrectionStage


@dataclass
class DcOffsetAnalysisRow:
    """Fila leida del analisis de DC offset."""
    filename: str
    relative_path: str
    is_full_song: bool
    sample_rate: int
    num_channels: int
    duration_seconds: float
    dc_offsets: List[float]
    max_abs_dc_offset: float


@dataclass
class DcOffsetCorrectionResult:
    """Resultado de la corrección para un archivo."""
    filename: str
    input_path: Path
    output_path: Path
    is_full_song: bool
    sample_rate: int
    num_channels: int
    duration_seconds: float
    original_dc_offsets: List[float]
    corrected_dc_offsets: List[float]
    original_max_abs_dc_offset: float
    corrected_max_abs_dc_offset: float
    original_peak_db: float
    corrected_peak_db: float
    clipped_after: bool


def _dbfs(value: float) -> float:
    """Convierte magnitud lineal a dBFS, protegiendo contra 0."""
    value = float(value)
    if value <= 0.0:
        return -120.0
    return 20.0 * np.log10(value)


def load_dc_offset_analysis(json_path: Path) -> List[DcOffsetAnalysisRow]:
    """
    Carga el JSON generado por dc_offset_detection.py.

    :param json_path: Ruta al archivo dc_offset_analysis.json.
    """
    if not json_path.exists():
        raise FileNotFoundError(f"No se encontro el JSON de analisis: {json_path}")

    rows: List[DcOffsetAnalysisRow] = []

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Formato de JSON inesperado en {json_path}")

    for item in payload:
        if not isinstance(item, dict):
            continue
        dc_offsets = item.get("dc_offsets") or []
        try:
            row = DcOffsetAnalysisRow(
                filename=item.get("filename") or item.get("file_path") or "",
                relative_path=item.get("relative_path") or item.get("filename") or item.get("file_path") or "",
                is_full_song=bool(int(item.get("is_full_song", 0)))
                if not isinstance(item.get("is_full_song"), bool)
                else bool(item.get("is_full_song")),
                sample_rate=int(item.get("sample_rate", 0)),
                num_channels=int(item.get("num_channels", 0)),
                duration_seconds=float(item.get("duration_seconds", 0.0)),
                dc_offsets=[float(x) for x in dc_offsets],
                max_abs_dc_offset=float(item.get("max_abs_dc_offset", 0.0)),
            )
        except Exception:
            continue
        rows.append(row)

    return rows


def _correct_single_file(
    row: DcOffsetAnalysisRow,
    media_root: Path,
    output_dir: Path,
) -> DcOffsetCorrectionResult:
    """
    Aplica correccion de DC offset a un archivo concreto y escribe la copia corregida.
    Se evita cargar el WAV completo usando bloques grandes y restando offsets en streaming.
    """
    input_path = (media_root / row.relative_path).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"No se encontro el WAV de entrada: {input_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = (output_dir / row.filename).resolve()

    block_size = 262144  # frames; bloques grandes reducen llamadas IO y asignaciones

    with sf.SoundFile(str(input_path), mode="r") as f_in:
        sr = f_in.samplerate
        num_channels = f_in.channels
        subtype = f_in.subtype

        # Offsets a aplicar (si el analisis no coincide en canales, se recalculan y se rebobina)
        if len(row.dc_offsets) == num_channels:
            offsets = np.asarray(row.dc_offsets, dtype=np.float32)
        else:
            sums = np.zeros(num_channels, dtype=np.float64)
            frame_count = 0
            while True:
                block = f_in.read(block_size, dtype="float32", always_2d=True)
                if block.size == 0:
                    break
                sums += block.sum(axis=0, dtype=np.float64)
                frame_count += block.shape[0]
            offsets = (
                (sums / frame_count).astype(np.float32)
                if frame_count > 0
                else np.zeros(num_channels, dtype=np.float32)
            )
            f_in.seek(0)

        original_peak = 0.0
        corrected_peak = 0.0
        corrected_sums = np.zeros(num_channels, dtype=np.float64)
        corrected_frame_count = 0

        with sf.SoundFile(
            str(output_path),
            mode="w",
            samplerate=sr,
            channels=num_channels,
            subtype=subtype,
        ) as f_out:
            while True:
                block = f_in.read(block_size, dtype="float32", always_2d=True)
                if block.size == 0:
                    break

                block_peak = float(np.max(np.abs(block)))
                if block_peak > original_peak:
                    original_peak = block_peak

                # Restar offsets por canal in-place para evitar copias extra
                np.subtract(block, offsets, out=block)

                corrected_block_peak = float(np.max(np.abs(block)))
                if corrected_block_peak > corrected_peak:
                    corrected_peak = corrected_block_peak

                corrected_sums += block.sum(axis=0, dtype=np.float64)
                corrected_frame_count += block.shape[0]

                f_out.write(block)

    if corrected_frame_count > 0:
        corrected_offsets = (corrected_sums / corrected_frame_count).astype(np.float64)
        corrected_max_abs_dc = float(np.max(np.abs(corrected_offsets)))
    else:
        corrected_offsets = np.zeros(num_channels, dtype=np.float64)
        corrected_max_abs_dc = 0.0

    original_peak_db = _dbfs(original_peak)
    corrected_peak_db = _dbfs(corrected_peak)
    clipped_after = corrected_peak > 1.0

    return DcOffsetCorrectionResult(
        filename=row.filename,
        input_path=input_path,
        output_path=output_path,
        is_full_song=row.is_full_song,
        sample_rate=sr,
        num_channels=num_channels,
        duration_seconds=row.duration_seconds,
        original_dc_offsets=row.dc_offsets,
        corrected_dc_offsets=corrected_offsets.tolist(),
        original_max_abs_dc_offset=row.max_abs_dc_offset,
        corrected_max_abs_dc_offset=corrected_max_abs_dc,
        original_peak_db=original_peak_db,
        corrected_peak_db=corrected_peak_db,
        clipped_after=clipped_after,
    )


def write_correction_log(results: List[DcOffsetCorrectionResult], log_csv_path: Path) -> None:
    """
    Escribe un CSV con el detalle de las correcciones realizadas.

    El CSV se genera en la carpeta de salida (media\\dc_offset), con columnas:
        filename
        input_path
        output_path
        is_full_song
        sample_rate
        num_channels
        duration_seconds
        original_dc_offsets
        corrected_dc_offsets
        original_max_abs_dc_offset
        corrected_max_abs_dc_offset
        original_peak_db
        corrected_peak_db
        clipped_after
    """
    log_csv_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "filename",
        "input_path",
        "output_path",
        "is_full_song",
        "sample_rate",
        "num_channels",
        "duration_seconds",
        "original_dc_offsets",
        "corrected_dc_offsets",
        "original_max_abs_dc_offset",
        "corrected_max_abs_dc_offset",
        "original_peak_db",
        "corrected_peak_db",
        "clipped_after",
    ]

    with log_csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for r in results:
            writer.writerow({
                "filename": r.filename,
                "input_path": str(r.input_path),
                "output_path": str(r.output_path),
                "is_full_song": int(r.is_full_song),
                "sample_rate": r.sample_rate,
                "num_channels": r.num_channels,
                "duration_seconds": f"{r.duration_seconds:.6f}",
                "original_dc_offsets": json.dumps(r.original_dc_offsets),
                "corrected_dc_offsets": json.dumps(r.corrected_dc_offsets),
                "original_max_abs_dc_offset": f"{r.original_max_abs_dc_offset:.8f}",
                "corrected_max_abs_dc_offset": f"{r.corrected_max_abs_dc_offset:.8f}",
                "original_peak_db": f"{r.original_peak_db:.2f}",
                "corrected_peak_db": f"{r.corrected_peak_db:.2f}",
                "clipped_after": int(r.clipped_after),
            })


class DcOffsetCorrectionStage(
    BaseCorrectionStage[DcOffsetAnalysisRow, DcOffsetCorrectionResult]
):
    """
    Etapa de corrección de DC offset usando el patrón BaseCorrectionStage.

    Reutiliza:
      - load_dc_offset_analysis  -> lectura del JSON de analisis.
      - _correct_single_file     -> corrección de cada WAV.
      - write_correction_log     -> escritura del log.
    """

    def load_rows(self) -> List[DcOffsetAnalysisRow]:
        return load_dc_offset_analysis(self.analysis_json_path)

    def process_row(self, row: DcOffsetAnalysisRow) -> DcOffsetCorrectionResult:
        return _correct_single_file(
            row=row,
            media_root=self.input_media_dir,
            output_dir=self.output_media_dir,
        )

    def write_log(self, results: List[DcOffsetCorrectionResult]) -> Path:
        log_csv_path = self.output_media_dir / "dc_offset_correction_log.csv"
        write_correction_log(results, log_csv_path)
        return log_csv_path


def run_dc_offset_correction(
    analysis_json_path: Path,
    media_dir: Path,
    output_dc_media_dir: Path,
) -> Path:
    """
    Punto de entrada de alto nivel para la correccion de DC offset.

    Esta version delega en DcOffsetCorrectionStage (BaseCorrectionStage) para:
      - leer el JSON de analisis,
      - corregir cada archivo,
      - escribir el CSV de log.
    """
    stage = DcOffsetCorrectionStage(
        analysis_json_path=analysis_json_path,
        input_media_dir=media_dir,
        output_media_dir=output_dc_media_dir,
    )
    return stage.run()
