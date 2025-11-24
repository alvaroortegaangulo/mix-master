# src/stages/stage1_loudness/loudness_correction.py

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from pedalboard import Pedalboard, Gain
from pedalboard.io import AudioFile

from src.utils.mixdown import mix_corrected_stems_to_full_song, FullSongRenderResult

from src.utils.stage_base import BaseCorrectionStage


# ----------------------------------------------------------------------
# Modelos de datos
# ----------------------------------------------------------------------


@dataclass
class LoudnessAnalysisRow:
    """Fila del CSV de loudness_analysis.csv."""
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
    """Resultado de la corrección de loudness de un stem."""
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
# Utilidades numéricas
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


# ----------------------------------------------------------------------
# Lectura del CSV de análisis
# ----------------------------------------------------------------------


def load_loudness_analysis(csv_path: Path) -> List[LoudnessAnalysisRow]:
    """
    Carga loudness_analysis.csv generado en la fase de análisis.

    :param csv_path: Ruta al archivo loudness_analysis.csv.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"No se encontró el CSV de análisis de loudness: {csv_path}")

    rows: List[LoudnessAnalysisRow] = []

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for line in reader:
            loudness_stevens = _parse_optional_float(line.get("loudness_stevens", "").strip())
            replaygain_gain_db = _parse_optional_float(line.get("replaygain_gain_db", "").strip())

            row = LoudnessAnalysisRow(
                filename=line["filename"],
                relative_path=line.get("relative_path") or line["filename"],
                is_full_song=bool(int(line["is_full_song"])),
                sample_rate=int(line["sample_rate"]),
                num_channels=int(line["num_channels"]),
                duration_seconds=float(line["duration_seconds"]),
                peak_dbfs=float(line["peak_dbfs"]),
                rms_dbfs=float(line["rms_dbfs"]),
                loudness_stevens=loudness_stevens,
                replaygain_gain_db=replaygain_gain_db,
                target_rms_dbfs=float(line["target_rms_dbfs"]),
                gain_db_to_target_rms=float(line["gain_db_to_target_rms"]),
            )
            rows.append(row)

    return rows


# ----------------------------------------------------------------------
# Corrección de loudness de un solo stem
# ----------------------------------------------------------------------


def _apply_loudness_correction_to_file(
    row: LoudnessAnalysisRow,
    input_media_dir: Path,
    output_media_dir: Path,
    mode: str = "rms",  # "rms" o "replaygain"
) -> LoudnessCorrectionResult:
    """
    Aplica la corrección de loudness a un único archivo usando Pedalboard.

    :param row: Fila del CSV de análisis de loudness.
    :param input_media_dir: Directorio donde están los WAV de entrada.
    :param output_media_dir: Directorio donde se escribirán los WAV corregidos.
    :param mode: "rms" -> usa gain_db_to_target_rms;
                 "replaygain" -> usa replaygain_gain_db si está disponible.
    """
    input_path = (input_media_dir / row.relative_path).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"No se encontró el WAV de entrada: {input_path}")

    output_media_dir.mkdir(parents=True, exist_ok=True)
    output_path = (output_media_dir / row.filename).resolve()

    # Elegir ganancia base
    if mode == "replaygain" and row.replaygain_gain_db is not None:
        base_gain_db = row.replaygain_gain_db
    else:
        # Modo por defecto: target RMS
        base_gain_db = row.gain_db_to_target_rms

    # Leer audio con Pedalboard
    with AudioFile(str(input_path), "r") as f:
        audio = f.read(f.frames)  # shape: (frames, channels)
        sr = f.samplerate
        num_channels = f.num_channels

    audio = audio.astype(np.float32, copy=False)

    # Métricas originales
    original_peak = float(np.max(np.abs(audio))) if audio.size > 0 else 0.0
    original_rms = float(np.sqrt(np.mean(audio**2))) if audio.size > 0 else 0.0

    original_peak_dbfs = _safe_dbfs(original_peak)
    original_rms_dbfs = _safe_dbfs(original_rms)

    # Construir la cadena de efectos: de momento solo Gain.
    board = Pedalboard([Gain(gain_db=base_gain_db)])

    # Aplicar la cadena
    processed = board(audio, sample_rate=sr)

    # Comprobar clipping y normalizar si es necesario
    processed_peak = float(np.max(np.abs(processed))) if processed.size > 0 else 0.0
    clipped_after = processed_peak > 1.0

    applied_gain_db = base_gain_db

    if processed_peak > 1.0:
        # Reducimos para que el pico máximo sea 0.98 (un pequeño margen)
        scale = 0.98 / processed_peak
        processed *= scale
        applied_gain_db += _safe_dbfs(scale)  # ajuste efectivo en dB

        # Recalcular picos tras el escalado
        processed_peak = float(np.max(np.abs(processed))) if processed.size > 0 else 0.0

    # Métricas resultantes
    processed_rms = float(np.sqrt(np.mean(processed**2))) if processed.size > 0 else 0.0

    resulting_peak_dbfs = _safe_dbfs(processed_peak)
    resulting_rms_dbfs = _safe_dbfs(processed_rms)

    # Escribir archivo corregido
    with AudioFile(str(output_path), "w", sr, num_channels) as f:
        f.write(processed)

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
# Escritura del log de corrección
# ----------------------------------------------------------------------


def write_loudness_correction_log(
    stem_results: List[LoudnessCorrectionResult],
    full_song_result: FullSongRenderResult,
    log_csv_path: Path,
) -> None:
    """
    Crea un CSV con el detalle de las correcciones aplicadas a cada stem
    y el render del full_song.
    """
    log_csv_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "filename",
        "type",  # stem / full_song
        "input_path",
        "output_path",
        "is_full_song_source",
        "sample_rate",
        "num_channels",
        "duration_seconds",
        "original_peak_dbfs",
        "original_rms_dbfs",
        "original_replaygain_gain_db",
        "original_gain_db_to_target_rms",
        "applied_gain_db",
        "resulting_peak_dbfs",
        "resulting_rms_dbfs",
        "clipped_after",
        "mix_gain_db",
        "full_song_peak_dbfs",
        "full_song_rms_dbfs",
        "full_song_clipped_before_mix_gain",
        "full_song_clipped_after_mix_gain",
    ]

    with log_csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        # Stems
        for r in stem_results:
            writer.writerow({
                "filename": r.filename,
                "type": "stem",
                "input_path": str(r.input_path),
                "output_path": str(r.output_path),
                "is_full_song_source": int(r.is_full_song_source),
                "sample_rate": r.sample_rate,
                "num_channels": r.num_channels,
                "duration_seconds": f"{r.duration_seconds:.6f}",
                "original_peak_dbfs": f"{r.original_peak_dbfs:.2f}",
                "original_rms_dbfs": f"{r.original_rms_dbfs:.2f}",
                "original_replaygain_gain_db": (
                    "" if r.original_replaygain_gain_db is None else f"{r.original_replaygain_gain_db:.2f}"
                ),
                "original_gain_db_to_target_rms": f"{r.original_gain_db_to_target_rms:.2f}",
                "applied_gain_db": f"{r.applied_gain_db:.2f}",
                "resulting_peak_dbfs": f"{r.resulting_peak_dbfs:.2f}",
                "resulting_rms_dbfs": f"{r.resulting_rms_dbfs:.2f}",
                "clipped_after": int(r.clipped_after),
                # Campos del full_song se dejan vacíos para los stems
                "mix_gain_db": "",
                "full_song_peak_dbfs": "",
                "full_song_rms_dbfs": "",
                "full_song_clipped_before_mix_gain": "",
                "full_song_clipped_after_mix_gain": "",
            })

        # Fila del full_song
        writer.writerow({
            "filename": full_song_result.filename,
            "type": "full_song",
            "input_path": "",
            "output_path": str(full_song_result.output_path),
            "is_full_song_source": 1,
            "sample_rate": full_song_result.sample_rate,
            "num_channels": full_song_result.num_channels,
            "duration_seconds": f"{full_song_result.duration_seconds:.6f}",
            "original_peak_dbfs": "",
            "original_rms_dbfs": "",
            "original_replaygain_gain_db": "",
            "original_gain_db_to_target_rms": "",
            "applied_gain_db": "",
            "resulting_peak_dbfs": "",
            "resulting_rms_dbfs": "",
            "clipped_after": "",
            "mix_gain_db": f"{full_song_result.mix_gain_db:.2f}",
            "full_song_peak_dbfs": f"{full_song_result.peak_dbfs:.2f}",
            "full_song_rms_dbfs": f"{full_song_result.rms_dbfs:.2f}",
            "full_song_clipped_before_mix_gain": int(full_song_result.clipped_before_mix_gain),
            "full_song_clipped_after_mix_gain": int(full_song_result.clipped_after_mix_gain),
        })


# ----------------------------------------------------------------------
# Punto de entrada de alto nivel
# ----------------------------------------------------------------------

class LoudnessCorrectionStage(
    BaseCorrectionStage[LoudnessAnalysisRow, LoudnessCorrectionResult]
):
    """
    Etapa de corrección de loudness basada en BaseCorrectionStage.

    Adicionalmente:
      - Mezcla los stems corregidos a full_song.wav.
      - Permite elegir modo "rms" o "replaygain".
    """

    def __init__(
        self,
        analysis_csv_path: Path,
        input_media_dir: Path,
        output_media_dir: Path,
        mode: str = "rms",
    ) -> None:
        super().__init__(
            analysis_csv_path=analysis_csv_path,
            input_media_dir=input_media_dir,
            output_media_dir=output_media_dir,
        )
        self.mode = mode

    def load_rows(self) -> List[LoudnessAnalysisRow]:
        return load_loudness_analysis(self.analysis_csv_path)

    def process_row(self, row: LoudnessAnalysisRow) -> LoudnessCorrectionResult:
        return _apply_loudness_correction_to_file(
            row=row,
            input_media_dir=self.input_media_dir,
            output_media_dir=self.output_media_dir,
            mode=self.mode,
        )

    def write_log(self, results: List[LoudnessCorrectionResult]) -> Path:
        """
        Implementación por si alguien usa stage.run() directamente.
        Mezcla los stems y genera full_song.wav, pero devuelve solo la ruta al CSV.
        """
        full_song_result = mix_corrected_stems_to_full_song(self.output_media_dir)
        log_csv_path = self.output_media_dir / "loudness_correction_log.csv"
        write_loudness_correction_log(results, full_song_result, log_csv_path)
        return log_csv_path

    def run(self) -> Tuple[Path, Path]:
        """
        Ejecuta la etapa de loudness y devuelve:
            (ruta_csv_log_correccion, ruta_full_song_corregido)
        """
        stem_results = self.process_all_rows()
        full_song_result = mix_corrected_stems_to_full_song(self.output_media_dir)
        log_csv_path = self.output_media_dir / "loudness_correction_log.csv"
        write_loudness_correction_log(stem_results, full_song_result, log_csv_path)
        return log_csv_path, full_song_result.output_path


def run_loudness_correction(
    analysis_csv_path: Path,
    input_media_dir: Path,
    output_media_dir: Path,
    mode: str = "rms",
) -> Tuple[Path, Path]:
    """
    Punto de entrada de alto nivel para la corrección de loudness.

    Implementado mediante LoudnessCorrectionStage para unificar el patrón de etapas.
    """
    stage = LoudnessCorrectionStage(
        analysis_csv_path=analysis_csv_path,
        input_media_dir=input_media_dir,
        output_media_dir=output_media_dir,
        mode=mode,
    )
    return stage.run()
