# src/stages/stage1_static_mix/spectral_cleanup_correction.py

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import math
import numpy as np
from pedalboard import Pedalboard, HighpassFilter, PeakFilter
from pedalboard.io import AudioFile

from src.utils.stage_base import BaseCorrectionStage

# ----------------------------------------------------------------------
# Modelos de datos
# ----------------------------------------------------------------------


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
    notches: List[NotchSpec]


@dataclass
class SpectralCleanupCorrectionResult:
    filename: str
    input_path: Path
    output_path: Path
    sample_rate: int
    num_channels: int
    duration_seconds: float
    recommended_hpf_cutoff_hz: float
    num_notches: int

    original_peak_dbfs: float
    original_rms_dbfs: float
    resulting_peak_dbfs: float
    resulting_rms_dbfs: float


# ----------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------


def _safe_dbfs(value: float, floor: float = -120.0) -> float:
    value = float(value)
    if value <= 0.0:
        return floor
    return 20.0 * np.log10(value)


def _parse_float(s: str, default: float = 0.0) -> float:
    s = s.strip()
    if not s:
        return default
    return float(s)


def _parse_notches_from_row(row: dict, max_notches: int) -> List[NotchSpec]:
    notches: List[NotchSpec] = []
    for i in range(1, max_notches + 1):
        f_str = row.get(f"notch_{i}_freq_hz", "").strip()
        if not f_str:
            continue
        q_str = row.get(f"notch_{i}_q", "").strip()
        g_str = row.get(f"notch_{i}_gain_db", "").strip()
        notches.append(
            NotchSpec(
                freq_hz=float(f_str),
                q=float(q_str) if q_str else 6.0,
                gain_db=float(g_str) if g_str else -3.0,
            )
        )
    return notches


def _design_peaking_eq(fs: float, f0: float, q: float, gain_db: float):
    """
    Diseña un biquad tipo 'peaking EQ' (bell) estándar.
    Con gain_db negativo se convierte en un notch suave.
    Devuelve coeficientes normalizados: b0, b1, b2, a1, a2.
    """
    # Proteger de frecuencias inválidas
    if f0 <= 0.0 or f0 >= fs / 2.0:
        # Coeficientes idénticos (filtro pasa-todo)
        return 1.0, 0.0, 0.0, 0.0, 0.0

    A = 10.0 ** (gain_db / 40.0)
    omega = 2.0 * math.pi * f0 / fs
    alpha = math.sin(omega) / (2.0 * q)
    cosw = math.cos(omega)

    b0 = 1.0 + alpha * A
    b1 = -2.0 * cosw
    b2 = 1.0 - alpha * A
    a0 = 1.0 + alpha / A
    a1 = -2.0 * cosw
    a2 = 1.0 - alpha / A

    # Normalizamos por a0
    b0 /= a0
    b1 /= a0
    b2 /= a0
    a1 /= a0
    a2 /= a0

    return b0, b1, b2, a1, a2


def _apply_biquad_peaking_eq(
    audio: np.ndarray,
    fs: float,
    f0: float,
    q: float,
    gain_db: float,
) -> np.ndarray:
    """
    Aplica un biquad peaking EQ canal por canal.
    audio: shape (channels, samples)
    """
    b0, b1, b2, a1, a2 = _design_peaking_eq(fs, f0, q, gain_db)

    if b0 == 1.0 and b1 == 0.0 and b2 == 0.0 and a1 == 0.0 and a2 == 0.0:
        # Filtro identidad
        return audio

    out = np.zeros_like(audio, dtype=np.float32)

    # Procesamos canal a canal
    for ch in range(audio.shape[0]):
        x = audio[ch]
        y = out[ch]

        x1 = x2 = 0.0
        y1 = y2 = 0.0

        for n in range(x.shape[0]):
            xn = float(x[n])
            yn = b0 * xn + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2

            y[n] = yn

            x2 = x1
            x1 = xn
            y2 = y1
            y1 = yn

    return out


# ----------------------------------------------------------------------
# Lectura CSV de análisis
# ----------------------------------------------------------------------


def load_spectral_cleanup_csv(csv_path: Path, max_notches: int = 4) -> List[SpectralCleanupRow]:
    if not csv_path.exists():
        raise FileNotFoundError(f"No se encontró el CSV de análisis espectral: {csv_path}")

    rows: List[SpectralCleanupRow] = []

    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for line in reader:
            notches = _parse_notches_from_row(line, max_notches=max_notches)

            row = SpectralCleanupRow(
                filename=line["filename"],
                relative_path=line.get("relative_path") or line["filename"],
                sample_rate=int(line["sample_rate"]),
                num_channels=int(line["num_channels"]),
                duration_seconds=float(line["duration_seconds"]),
                recommended_hpf_cutoff_hz=float(line["recommended_hpf_cutoff_hz"]),
                low_band_energy_ratio_0_40=float(line["low_band_energy_ratio_0_40"]),
                low_band_energy_ratio_40_80=float(line["low_band_energy_ratio_40_80"]),
                low_band_energy_ratio_80_160=float(line["low_band_energy_ratio_80_160"]),
                notches=notches,
            )
            rows.append(row)

    return rows


# ----------------------------------------------------------------------
# Aplicación de HPF + Notches
# ----------------------------------------------------------------------


def _apply_spectral_cleanup_to_file(
    row: SpectralCleanupRow,
    input_media_dir: Path,
    output_media_dir: Path,
) -> SpectralCleanupCorrectionResult:
    input_path = (input_media_dir / row.relative_path).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"No se encontró el WAV de entrada: {input_path}")

    output_media_dir.mkdir(parents=True, exist_ok=True)
    output_path = (output_media_dir / row.filename).resolve()

    # ------------------------------------------------------------------
    # Leer audio con Pedalboard (float32, shape: (channels, samples))
    # ------------------------------------------------------------------
    with AudioFile(str(input_path), "r") as f:
        audio = f.read(f.frames)
        sr = f.samplerate
        num_channels = f.num_channels

    audio = audio.astype(np.float32, copy=False)

    # Métricas originales
    if audio.size > 0:
        original_peak = float(np.max(np.abs(audio)))
        original_rms = float(np.sqrt(np.mean(audio**2)))
    else:
        original_peak = 0.0
        original_rms = 0.0

    original_peak_dbfs = _safe_dbfs(original_peak)
    original_rms_dbfs = _safe_dbfs(original_rms)

    # ------------------------------------------------------------------
    # 1) Construir la cadena de efectos: HPF + notches (PeakFilter)
    # ------------------------------------------------------------------
    effects = []

    # High-pass recomendado por el análisis
    if row.recommended_hpf_cutoff_hz > 0.0:
        effects.append(
            HighpassFilter(
                cutoff_frequency_hz=row.recommended_hpf_cutoff_hz
            )
        )

    # Notches: usamos PeakFilter de Pedalboard
    #   - freq_hz  -> cutoff_frequency_hz
    #   - gain_db  -> gain_db (negativo => notch)
    #   - q        -> q
    for notch in row.notches:
        # Si el gain está muy cerca de 0 dB, nos lo saltamos (no hace nada)
        if abs(notch.gain_db) < 0.1:
            continue

        # Proteger de frecuencias fuera de rango
        if notch.freq_hz <= 0.0 or notch.freq_hz >= sr / 2.0:
            continue

        effects.append(
            PeakFilter(
                cutoff_frequency_hz=notch.freq_hz,
                gain_db=notch.gain_db,
                q=notch.q,
            )
        )

    # Si no hay efectos, no procesamos nada
    if effects:
        board = Pedalboard(effects)
        processed = board(audio, sample_rate=sr)
    else:
        processed = audio

    # ------------------------------------------------------------------
    # Métricas resultantes
    # ------------------------------------------------------------------
    if processed.size > 0:
        processed_peak = float(np.max(np.abs(processed)))
        processed_rms = float(np.sqrt(np.mean(processed**2)))
    else:
        processed_peak = 0.0
        processed_rms = 0.0

    resulting_peak_dbfs = _safe_dbfs(processed_peak)
    resulting_rms_dbfs = _safe_dbfs(processed_rms)

    # ------------------------------------------------------------------
    # Guardar WAV corregido
    # ------------------------------------------------------------------
    with AudioFile(str(output_path), "w", sr, num_channels) as f:
        f.write(processed.astype(np.float32, copy=False))

    return SpectralCleanupCorrectionResult(
        filename=row.filename,
        input_path=input_path,
        output_path=output_path,
        sample_rate=sr,
        num_channels=num_channels,
        duration_seconds=row.duration_seconds,
        recommended_hpf_cutoff_hz=row.recommended_hpf_cutoff_hz,
        num_notches=len(row.notches),
        original_peak_dbfs=original_peak_dbfs,
        original_rms_dbfs=original_rms_dbfs,
        resulting_peak_dbfs=resulting_peak_dbfs,
        resulting_rms_dbfs=resulting_rms_dbfs,
    )


# ----------------------------------------------------------------------
# Log de corrección
# ----------------------------------------------------------------------


def write_spectral_cleanup_log(
    results: List[SpectralCleanupCorrectionResult],
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
        "recommended_hpf_cutoff_hz",
        "num_notches",
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
                "recommended_hpf_cutoff_hz": f"{r.recommended_hpf_cutoff_hz:.2f}",
                "num_notches": r.num_notches,
                "original_peak_dbfs": f"{r.original_peak_dbfs:.2f}",
                "original_rms_dbfs": f"{r.original_rms_dbfs:.2f}",
                "resulting_peak_dbfs": f"{r.resulting_peak_dbfs:.2f}",
                "resulting_rms_dbfs": f"{r.resulting_rms_dbfs:.2f}",
            })


# ----------------------------------------------------------------------
# Punto de entrada de alto nivel
# ----------------------------------------------------------------------

class SpectralCleanupStage(
    BaseCorrectionStage[SpectralCleanupRow, SpectralCleanupCorrectionResult]
):
    """
    Etapa de limpieza espectral (HPF + notches) usando BaseCorrectionStage.

    Se apoya en:
      - load_spectral_cleanup_csv
      - _apply_spectral_cleanup_to_file
      - write_spectral_cleanup_log
    """

    def __init__(
        self,
        analysis_csv_path: Path,
        input_media_dir: Path,
        output_media_dir: Path,
        max_notches: int = 4,
    ) -> None:
        super().__init__(
            analysis_csv_path=analysis_csv_path,
            input_media_dir=input_media_dir,
            output_media_dir=output_media_dir,
        )
        self.max_notches = max_notches

    def load_rows(self) -> List[SpectralCleanupRow]:
        return load_spectral_cleanup_csv(
            csv_path=self.analysis_csv_path,
            max_notches=self.max_notches,
        )

    def process_row(
        self,
        row: SpectralCleanupRow,
    ) -> SpectralCleanupCorrectionResult:
        return _apply_spectral_cleanup_to_file(
            row=row,
            input_media_dir=self.input_media_dir,
            output_media_dir=self.output_media_dir,
        )

    def write_log(
        self,
        results: List[SpectralCleanupCorrectionResult],
    ) -> Path:
        log_csv_path = self.output_media_dir / "spectral_cleanup_correction_log.csv"
        write_spectral_cleanup_log(results, log_csv_path)
        return log_csv_path



def run_spectral_cleanup_correction(
    analysis_csv_path: Path,
    input_media_dir: Path,
    output_media_dir: Path,
    max_notches: int = 4,
) -> Path:
    """
    Punto de entrada de alto nivel para la limpieza espectral.

    Usa SpectralCleanupStage (BaseCorrectionStage) para aplicar HPF + notches
    a todos los stems y generar el log de corrección.
    """
    stage = SpectralCleanupStage(
        analysis_csv_path=analysis_csv_path,
        input_media_dir=input_media_dir,
        output_media_dir=output_media_dir,
        max_notches=max_notches,
    )
    return stage.run()
