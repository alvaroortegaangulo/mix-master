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
    is_bus_fx: bool
    bus_key: str | None

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
    is_bus_fx: bool
    bus_key: str | None

    target_peak_dbfs: float
    pre_gain_db: float
    comp_threshold_dbfs: float
    comp_ratio: float
    distortion_drive_db: float
    hpf_cutoff_hz: float
    limiter_threshold_db: float

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
                is_bus_fx=_parse_bool(line.get("is_bus_fx", "0")),
                bus_key=(line.get("bus_key") or "").strip() or None,
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
    Aplica un mastering muy sutil a un stem.

    Filosofía:
      - Esta etapa NO rehace la mezcla ni la dinámica. Es un "polish" final.
      - Compresión suave, ratio baja y thresholds adaptados a la dinámica original.
      - El pre-gain se basa en el headroom real hacia el target_peak, escalado.
      - La percusión mantiene transitorios, la voz no se dispara en volumen.
      - Buses FX quedan más de fondo (no se empujan hacia delante).
      - Distorsión sólo como toque sutil cuando tiene sentido y en muy baja cantidad.
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
        original_rms = float(np.sqrt(np.mean(audio ** 2)))
    else:
        original_peak = 0.0
        original_rms = 0.0

    original_peak_dbfs = _safe_dbfs(original_peak)
    original_rms_dbfs = _safe_dbfs(original_rms)

    # --------------------------------------------------------------
    # Perfil del stem (voz, percusión, FX, etc.)
    # --------------------------------------------------------------
    filename_lower = row.filename.lower()
    bus_key = (row.bus_key or "").lower()

    is_bus_fx = row.is_bus_fx
    is_vocal = row.is_vocal and not is_bus_fx

    is_kick = "kick" in filename_lower
    is_snare = "snare" in filename_lower or "clap" in filename_lower
    is_perc_name = "perc" in filename_lower or "cajon" in filename_lower or "timbal" in filename_lower
    is_drum_bus = bus_key == "drums"

    is_percussive = is_kick or is_snare or is_perc_name or is_drum_bus

    # --------------------------------------------------------------
    # Target y pre-gain: más conservador, basado en headroom real
    # --------------------------------------------------------------
    target_peak_dbfs = row.recommended_target_peak_dbfs
    # Si el análisis dio algo raro, fija un target razonable
    if target_peak_dbfs > -0.5 or target_peak_dbfs < -18.0:
        target_peak_dbfs = -1.0

    headroom_db = target_peak_dbfs - original_peak_dbfs  # cuánto podemos subir antes de llegar al target
    # Drive sugerido por análisis, pero no le permitimos más que el headroom real
    raw_drive = min(row.recommended_drive_db, headroom_db)

    # Mastering muy sutil: sólo usamos un % del drive recomendado
    base_pre_gain = raw_drive * 0.6

    # Ajustes por tipo de pista
    if is_bus_fx:
        # Los buses FX no deben adelantarse, nunca subimos por encima de 0 dB de pre-gain
        pre_gain_db = min(base_pre_gain, 0.0)
        pre_gain_db = max(pre_gain_db, -6.0)
    elif is_vocal:
        # La voz ya suele estar bastante presente. Pequeños ajustes +/- pocos dB.
        pre_gain_db = base_pre_gain
        pre_gain_db = min(pre_gain_db, 1.5)
        pre_gain_db = max(pre_gain_db, -3.0)
    elif is_percussive:
        # Percusión: preservar punch. Ganancias moderadas.
        pre_gain_db = base_pre_gain
        pre_gain_db = min(pre_gain_db, 2.0)
        pre_gain_db = max(pre_gain_db, -4.0)
    else:
        # Resto de instrumentos
        pre_gain_db = base_pre_gain
        pre_gain_db = max(min(pre_gain_db, 3.0), -6.0)

    # --------------------------------------------------------------
    # HPF por tipo
    # --------------------------------------------------------------
    if is_bus_fx:
        # FX: limpiar mucho low-end para no embarrar la mezcla
        if bus_key in {"drums", "bass"}:
            hpf_cutoff_hz = 150.0
        elif bus_key in {"lead_vocal", "backing_vocals"}:
            hpf_cutoff_hz = 170.0
        else:
            hpf_cutoff_hz = 180.0
    elif is_vocal:
        hpf_cutoff_hz = 55.0
    elif is_percussive:
        hpf_cutoff_hz = 25.0
    else:
        hpf_cutoff_hz = 30.0

    # --------------------------------------------------------------
    # Compresión: umbral adaptado a la dinámica real
    # --------------------------------------------------------------
    # Dinámica aproximada
    dynamic_range_db = max(original_peak_dbfs - original_rms_dbfs, 4.0)

    # Threshold base: trabajamos en el "top" del rango, no aplastamos todo
    base_threshold = original_rms_dbfs + dynamic_range_db * 0.75

    if is_bus_fx:
        # Compresión casi simbólica en FX
        comp_threshold_dbfs = base_threshold + 2.0
        comp_ratio = 1.2
        comp_attack_ms = 35.0
        comp_release_ms = 280.0
    elif is_vocal:
        # Voz: control suave, no radio-voice; 1–3 dB de GR típico
        comp_threshold_dbfs = base_threshold - 1.5
        comp_ratio = 1.8
        comp_attack_ms = 15.0
        comp_release_ms = 160.0
    elif is_percussive:
        # Transitorios vivos, sólo domesticar un pelín
        comp_threshold_dbfs = base_threshold - 0.5
        comp_ratio = 1.3
        comp_attack_ms = 25.0
        comp_release_ms = 140.0
    else:
        # Instrumentos generales
        comp_threshold_dbfs = base_threshold
        comp_ratio = 1.4
        comp_attack_ms = 20.0
        comp_release_ms = 180.0

    # Clamp de seguridad para el threshold
    comp_threshold_dbfs = min(comp_threshold_dbfs, -2.0)

    # --------------------------------------------------------------
    # Distorsión: casi siempre 0, salvo toques muy sutiles
    # --------------------------------------------------------------
    distortion_drive_db = 0.0

    if not is_bus_fx:
        if is_percussive:
            # Un toque opcional de saturación muy suave si el análisis propone algo
            distortion_drive_db = max(min(row.recommended_drive_db * 0.3, 1.5), 0.0)
        elif not is_vocal:
            # Guitarras / keys: un poco de color, pero con muchísimo cuidado
            distortion_drive_db = max(min(row.recommended_drive_db * 0.25, 1.0), 0.0)
        else:
            # Vocal: casi nada, sólo si el análisis lo sugiere
            distortion_drive_db = max(min(row.recommended_drive_db * 0.2, 0.5), 0.0)

    # Si es ridículamente pequeño, lo forzamos a 0 para ahorrar CPU
    if distortion_drive_db < 0.1:
        distortion_drive_db = 0.0

    # --------------------------------------------------------------
    # Limiter: techo ligado al target, sin aplastar
    # --------------------------------------------------------------
    if is_bus_fx:
        limiter_threshold_db = min(target_peak_dbfs, -3.0)
    else:
        limiter_threshold_db = min(target_peak_dbfs, -0.8)

    # Clamp adicional por seguridad
    limiter_threshold_db = max(limiter_threshold_db, -8.0)

    # --------------------------------------------------------------
    # Construcción de la cadena de efectos
    # --------------------------------------------------------------
    effects = [
        HighpassFilter(cutoff_frequency_hz=hpf_cutoff_hz),
    ]

    if comp_ratio > 1.0:
        effects.append(
            Compressor(
                threshold_db=comp_threshold_dbfs,
                ratio=comp_ratio,
                attack_ms=comp_attack_ms,
                release_ms=comp_release_ms,
            )
        )

    if distortion_drive_db > 0.0:
        effects.append(Distortion(drive_db=distortion_drive_db))

    if abs(pre_gain_db) > 0.05:
        effects.append(Gain(gain_db=pre_gain_db))

    effects.append(
        Limiter(
            threshold_db=limiter_threshold_db,
            release_ms=100.0,
        )
    )

    board = Pedalboard(effects)
    processed = board(audio, sample_rate=sr)

    if processed.size > 0:
        processed_peak = float(np.max(np.abs(processed)))
        processed_rms = float(np.sqrt(np.mean(processed ** 2)))
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
        is_bus_fx=row.is_bus_fx,
        bus_key=row.bus_key,
        target_peak_dbfs=target_peak_dbfs,
        pre_gain_db=pre_gain_db,
        comp_threshold_dbfs=comp_threshold_dbfs,
        comp_ratio=comp_ratio,
        distortion_drive_db=distortion_drive_db,
        hpf_cutoff_hz=hpf_cutoff_hz,
        limiter_threshold_db=limiter_threshold_db,
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
        "is_bus_fx",
        "bus_key",
        "target_peak_dbfs",
        "pre_gain_db",
        "comp_threshold_dbfs",
        "comp_ratio",
        "distortion_drive_db",
        "hpf_cutoff_hz",
        "limiter_threshold_db",
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
                    "target_peak_dbfs": f"{r.target_peak_dbfs:.2f}",
                    "pre_gain_db": f"{r.pre_gain_db:.2f}",
                    "comp_threshold_dbfs": f"{r.comp_threshold_dbfs:.2f}",
                    "comp_ratio": f"{r.comp_ratio:.2f}",
                    "distortion_drive_db": f"{r.distortion_drive_db:.2f}",
                    "hpf_cutoff_hz": f"{r.hpf_cutoff_hz:.1f}",
                    "limiter_threshold_db": f"{r.limiter_threshold_db:.2f}",
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
