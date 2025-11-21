# C:\mix\src\analysis\dc_offset_correction.py

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List

import numpy as np
import soundfile as sf


@dataclass
class DcOffsetAnalysisRow:
    """Fila leída del CSV de análisis de DC offset."""
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


def load_dc_offset_analysis(csv_path: Path) -> List[DcOffsetAnalysisRow]:
    """
    Carga el CSV generado por dc_offset_detection.py.

    :param csv_path: Ruta al archivo dc_offset_analysis.csv.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"No se encontró el CSV de análisis: {csv_path}")

    rows: List[DcOffsetAnalysisRow] = []

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for line in reader:
            dc_offsets = json.loads(line["dc_offsets"])
            row = DcOffsetAnalysisRow(
                filename=line["filename"],
                relative_path=line.get("relative_path") or line["filename"],
                is_full_song=bool(int(line["is_full_song"])),
                sample_rate=int(line["sample_rate"]),
                num_channels=int(line["num_channels"]),
                duration_seconds=float(line["duration_seconds"]),
                dc_offsets=[float(x) for x in dc_offsets],
                max_abs_dc_offset=float(line["max_abs_dc_offset"]),
            )
            rows.append(row)

    return rows


def _correct_single_file(
    row: DcOffsetAnalysisRow,
    media_root: Path,
    output_dir: Path,
) -> DcOffsetCorrectionResult:
    """
    Aplica corrección de DC offset a un archivo concreto y escribe la copia corregida.

    :param row: Datos de análisis para este archivo.
    :param media_root: Carpeta raíz donde están los WAV originales (p.ej. C:\\mix\\media).
    :param output_dir: Carpeta donde se escribirán los WAV corregidos.
    """
    input_path = (media_root / row.relative_path).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"No se encontró el WAV de entrada: {input_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = (output_dir / row.filename).resolve()

    # Leer audio como matriz (n_muestras, n_canales)
    audio, sr = sf.read(input_path, always_2d=True)
    if sr != row.sample_rate:
        # No es crítico, pero lo anotamos mentalmente: el fichero ha cambiado desde el análisis
        pass

    num_channels = audio.shape[1]

    # Pico original
    original_peak = float(np.max(np.abs(audio)))
    original_peak_db = _dbfs(original_peak)

    # Offsets a aplicar (si el CSV no coincide en nº de canales, recalculamos)
    if len(row.dc_offsets) == num_channels:
        offsets = np.array(row.dc_offsets, dtype=np.float64)[np.newaxis, :]  # shape (1, C)
    else:
        offsets = audio.mean(axis=0, keepdims=True)  # recalcular por si acaso

    # Corrección: restar el DC offset por canal
    corrected_audio = audio - offsets

    # Recalcular offset tras corrección
    corrected_offsets = corrected_audio.mean(axis=0)
    corrected_max_abs_dc = float(np.max(np.abs(corrected_offsets)))

    # Picos después de la corrección
    corrected_peak = float(np.max(np.abs(corrected_audio)))
    corrected_peak_db = _dbfs(corrected_peak)

    # Marcar si el archivo queda por encima del rango típico [-1, 1]
    clipped_after = corrected_peak > 1.0

    # Escribir a disco preservando subtype en la medida de lo posible
    info = sf.info(input_path)
    subtype = info.subtype or None

    sf.write(
        file=output_path,
        data=corrected_audio,
        samplerate=info.samplerate,
        subtype=subtype,
    )

    return DcOffsetCorrectionResult(
        filename=row.filename,
        input_path=input_path,
        output_path=output_path,
        is_full_song=row.is_full_song,
        sample_rate=info.samplerate,
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


def run_dc_offset_correction(
    analysis_csv_path: Path,
    media_dir: Path,
    output_dc_media_dir: Path,
) -> Path:
    """
    Punto de entrada de alto nivel:

    - Lee el CSV de análisis de DC offset.
    - Corrige todos los WAV encontrados en el CSV.
    - Escribe los WAV corregidos en output_dc_media_dir.
    - Genera un log CSV en esa misma carpeta.

    :return: Ruta al CSV de log de corrección.
    """
    rows = load_dc_offset_analysis(analysis_csv_path)

    results: List[DcOffsetCorrectionResult] = []
    for row in rows:
        result = _correct_single_file(row, media_dir, output_dc_media_dir)
        results.append(result)

    log_csv_path = output_dc_media_dir / "dc_offset_correction_log.csv"
    write_correction_log(results, log_csv_path)

    return log_csv_path
