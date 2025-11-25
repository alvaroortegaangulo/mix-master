from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List

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
    instrument_profile: str  # puede venir vacío si el análisis aún no lo exporta
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
    recommended_hpf_cutoff_hz: float  # aquí guardamos el HPF aplicado (refinado)
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
    s = (s or "").strip()
    if not s:
        return default
    return float(s)


def _parse_notches_from_row(row: dict, max_notches: int) -> List[NotchSpec]:
    notches: List[NotchSpec] = []
    for i in range(1, max_notches + 1):
        f_str = (row.get(f"notch_{i}_freq_hz", "") or "").strip()
        if not f_str:
            continue
        q_str = (row.get(f"notch_{i}_q", "") or "").strip()
        g_str = (row.get(f"notch_{i}_gain_db", "") or "").strip()
        notches.append(
            NotchSpec(
                freq_hz=float(f_str),
                q=float(q_str) if q_str else 6.0,
                gain_db=float(g_str) if g_str else -3.0,
            )
        )
    return notches


# ----------------------------------------------------------------------
# Clasificación de instrumento (usa STEM_PROFILE_OPTIONS + fallback)
# ----------------------------------------------------------------------


def _classify_instrument_spectral(instrument_profile: str, filename: str):
    """
    Usa primero instrument_profile (frontend: drums, bass, lead_vocal, fx, ...).
    Si es auto/other/vacío, hace fallback a heurística por nombre de archivo.

    Devuelve booleans:
      is_percussive, is_bass, is_vocal, is_gtr_keys, is_fx_amb
    """
    ip = (instrument_profile or "").strip().lower()
    fname = filename.lower()

    is_percussive = False
    is_bass = False
    is_vocal = False
    is_gtr_keys = False
    is_fx_amb = False

    # 1) Mapa directo desde STEM_PROFILE_OPTIONS
    if ip in ("drums", "percussion"):
        is_percussive = True
    elif ip == "bass":
        is_bass = True
    elif ip in ("lead_vocal", "backing_vocals"):
        is_vocal = True
    elif ip in ("acoustic_guitar", "electric_guitar", "keys", "synth"):
        is_gtr_keys = True
    elif ip in ("fx", "ambience"):
        is_fx_amb = True
    # auto / other / "" → dejamos la puerta abierta al fallback

    if is_percussive or is_bass or is_vocal or is_gtr_keys or is_fx_amb:
        return is_percussive, is_bass, is_vocal, is_gtr_keys, is_fx_amb

    # 2) Fallback heurístico por nombre de archivo
    text = ip + " " + fname

    is_kick = any(t in text for t in ("kick", "bombo", "bd"))
    is_snare = any(t in text for t in ("snare", "sna", "caja"))
    is_hat = any(t in text for t in ("hihat", "hi-hat", "hat", "hh", "ride", "cym"))
    is_tom = any(t in text for t in ("tom", "timbal"))
    is_hand_perc = any(t in text for t in ("perc", "shaker", "clap", "palma", "cajon"))

    is_bass = any(t in text for t in ("bass", "bajo", "sub"))
    is_vocal = any(t in text for t in ("vocal", "vox", "voz", "lead_vocal", "backing_vocals"))
    is_gtr = any(t in text for t in ("guitar", "gtr", "acoustic_guitar", "electric_guitar"))
    is_keys = any(t in text for t in ("keys", "piano", "synth", "pad", "rhodes"))
    is_fx_amb = any(t in text for t in ("fx", "amb", "atmo", "atmos"))

    is_percussive = is_kick or is_snare or is_hat or is_tom or is_hand_perc
    is_gtr_keys = is_gtr or is_keys

    return is_percussive, is_bass, is_vocal, is_gtr_keys, is_fx_amb


# ----------------------------------------------------------------------
# Refinado "pro" de HPF + notches a partir del análisis
# ----------------------------------------------------------------------


def _refine_spectral_settings(
    row: SpectralCleanupRow,
    samplerate: int,
) -> tuple[float, List[NotchSpec]]:
    """
    Toma recomendaciones del análisis (HPF + notches) y las convierte
    en ajustes más musicales:

      - HPF:
          * clamp por tipo de instrumento (bajo, bombo, voz, guitarras, FX, ...)
          * opcionalmente subir un poco si no hay nada útil en subgraves
      - Notches:
          * descarta notches absurdos (freq fuera de rango, gain ≈ 0 o positivo)
          * protege subs en bajo/bombo (no hacer notches muy abajo)
          * clamp de Q y profundidad (gain_db)
          * merge de notches muy cercanos
          * límite de nº de notches por tipo de pista
    """
    is_perc, is_bass, is_vocal, is_gtr_keys, is_fx_amb = _classify_instrument_spectral(
        row.instrument_profile, row.filename
    )

    # ------------------------ HPF refinado ------------------------
    base_hpf = max(row.recommended_hpf_cutoff_hz, 0.0)

    # Rangos por tipo (en Hz)
    if is_bass:
        hpf_min = 20.0
        hpf_max = 45.0   # no subir más de esto salvo que el análisis sepa MUCHO
    elif is_perc:
        hpf_min = 25.0
        hpf_max = 80.0
    elif is_vocal:
        hpf_min = 60.0
        hpf_max = 120.0
    elif is_gtr_keys:
        hpf_min = 60.0
        hpf_max = 150.0
    elif is_fx_amb:
        hpf_min = 100.0
        hpf_max = 300.0
    else:
        hpf_min = 30.0
        hpf_max = 150.0

    # Si el análisis no propone HPF pero sabemos que el instrumento lo admite, ponemos uno suave
    if base_hpf <= 0.0:
        if is_vocal or is_gtr_keys or is_fx_amb:
            base_hpf = hpf_min
        else:
            # En bajo/percusiva preferimos respetar el análisis si no ha sugerido HPF
            base_hpf = 0.0

    # Ajuste ligero según la energía de subgraves
    low_0_80 = row.low_band_energy_ratio_0_40 + row.low_band_energy_ratio_40_80

    # Si no hay prácticamente nada en 0–80 Hz y no es bajo/percusión, podemos permitir un HPF algo mayor
    if not (is_bass or is_perc) and low_0_80 < 0.02:
        base_hpf = max(base_hpf, max(hpf_min, 80.0))

    # Clamp final
    if base_hpf > 0.0:
        base_hpf = max(base_hpf, hpf_min)
        base_hpf = min(base_hpf, hpf_max)

    # ------------------------ Notches refinados -------------------
    raw_notches = row.notches
    filtered: List[NotchSpec] = []

    nyq = samplerate / 2.0

    # límites de frecuencias mínimas de notches según tipo:
    if is_bass:
        notch_min_freq = 60.0   # protegemos subs/fundamental
        max_notches_type = 2
    elif is_perc:
        notch_min_freq = 70.0
        max_notches_type = 3
    elif is_vocal:
        notch_min_freq = 150.0
        max_notches_type = 4
    elif is_gtr_keys:
        notch_min_freq = 120.0
        max_notches_type = 4
    elif is_fx_amb:
        notch_min_freq = 70.0
        max_notches_type = 5
    else:
        notch_min_freq = 80.0
        max_notches_type = 3

    for n in raw_notches:
        f = float(n.freq_hz)
        g = float(n.gain_db)
        q = float(n.q)

        # Frecuencia válida
        if f <= 0.0 or f >= nyq * 0.98:
            continue

        # En esta etapa ("cleanup") asumimos que los notches son de corte.
        # Si el análisis marcó un gain positivo, lo ignoramos aquí.
        if g >= -0.1:
            continue

        # Proteger subs según tipo de pista
        if f < notch_min_freq:
            continue

        # Clamp de Q y profundidad
        q = max(2.0, min(q, 18.0))
        g = max(-12.0, min(g, -0.5))  # cortes entre -0.5 y -12 dB

        filtered.append(NotchSpec(freq_hz=f, q=q, gain_db=g))

    # Fusionar notches muy cercanos en frecuencia
    if filtered:
        filtered.sort(key=lambda n: n.freq_hz)
        merged: List[NotchSpec] = []

        for n in filtered:
            if not merged:
                merged.append(n)
                continue

            last = merged[-1]
            # Umbral de cercanía: ±max(40 Hz, 8% de la frecuencia)
            close_hz = max(40.0, last.freq_hz * 0.08)

            if abs(n.freq_hz - last.freq_hz) <= close_hz:
                # Elegimos el corte más fuerte y promediamos Q/freq un poco
                if n.gain_db < last.gain_db:  # más negativo = corte más fuerte
                    freq = 0.5 * (n.freq_hz + last.freq_hz)
                    q = 0.5 * (n.q + last.q)
                    gain_db = min(n.gain_db, last.gain_db)
                    merged[-1] = NotchSpec(freq_hz=freq, q=q, gain_db=gain_db)
                # si el anterior es más fuerte, simplemente ignoramos el nuevo
            else:
                merged.append(n)

        # Limitar nº de notches por tipo
        refined_notches = merged[:max_notches_type]
    else:
        refined_notches = []

    return base_hpf, refined_notches


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
                instrument_profile=(line.get("instrument_profile") or "").strip(),
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
    # Refinar HPF + notches según tipo de instrumento
    # ------------------------------------------------------------------
    hpf_cutoff_hz, refined_notches = _refine_spectral_settings(row, samplerate=sr)

    effects = []

    # High-pass (si aplica)
    if hpf_cutoff_hz > 0.0:
        effects.append(
            HighpassFilter(
                cutoff_frequency_hz=hpf_cutoff_hz
            )
        )

    # Notches con PeakFilter
    for notch in refined_notches:
        if abs(notch.gain_db) < 0.1:
            continue
        if notch.freq_hz <= 0.0 or notch.freq_hz >= sr / 2.0:
            continue

        effects.append(
            PeakFilter(
                cutoff_frequency_hz=notch.freq_hz,
                gain_db=notch.gain_db,
                q=notch.q,
            )
        )

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
        instrument_profile=row.instrument_profile,
        recommended_hpf_cutoff_hz=hpf_cutoff_hz,
        num_notches=len(refined_notches),
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
        "instrument_profile",
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
                "instrument_profile": r.instrument_profile,
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
