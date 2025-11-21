# src/analysis/spectral_cleanup_analysis.py

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np
import soundfile as sf


# ----------------------------------------------------------------------
# Parámetros globales del análisis (ajustables)
# ----------------------------------------------------------------------

FRAME_SIZE = 4096
HOP_SIZE = FRAME_SIZE // 2
EPS = 1e-12

# Candidatos de frecuencia de HPF y sus umbrales de energía relativa bajo corte
HPF_CANDIDATES_HZ = [40.0, 60.0, 80.0, 100.0, 120.0]
HPF_RATIO_THRESHOLDS = [0.02, 0.03, 0.05, 0.07, 0.10]

# Umbrales para detección de resonancias
RESONANCE_MIN_FREQ_HZ = 120.0     # no buscamos resonancias por debajo de esto
RESONANCE_MAX_FREQ_HZ = 12000.0   # límite superior
RESONANCE_PEAK_THRESHOLD_DB = 6.0  # exceso sobre baseline para considerar un pico
MAX_NOTCHES_PER_STEM = 4

# Q estándar para notches (relativamente estrechos)
DEFAULT_NOTCH_Q = 6.0


# ----------------------------------------------------------------------
# Modelos de datos
# ----------------------------------------------------------------------


@dataclass
class NotchSpec:
    freq_hz: float
    q: float
    gain_db: float


@dataclass
class SpectralCleanupResult:
    file_path: Path
    sample_rate: int
    num_channels: int
    duration_seconds: float

    # HPF recomendado (0.0 => no HPF)
    recommended_hpf_cutoff_hz: float

    # Energía relativa en bandas bajas (para logging / debugging)
    low_band_energy_ratio_0_40: float
    low_band_energy_ratio_40_80: float
    low_band_energy_ratio_80_160: float

    # Notches sugeridos
    notches: List[NotchSpec]


# ----------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------


def _compute_average_spectrum(
    audio_mono: np.ndarray,
    sr: int,
    frame_size: int = FRAME_SIZE,
    hop_size: int = HOP_SIZE,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Calcula el espectro medio de magnitud (en lineal) de un audio mono.
    Devuelve (freqs, avg_mag).
    """
    n_samples = audio_mono.shape[0]
    if n_samples < frame_size:
        pad = frame_size - n_samples
        audio_mono = np.pad(audio_mono, (0, pad), mode="constant")
        n_samples = audio_mono.shape[0]

    window = np.hanning(frame_size).astype(np.float32)

    mags = []
    for start in range(0, n_samples - frame_size + 1, hop_size):
        frame = audio_mono[start:start + frame_size] * window
        spectrum = np.fft.rfft(frame)
        mag = np.abs(spectrum)
        mags.append(mag)

    if not mags:
        avg_mag = np.zeros(frame_size // 2 + 1, dtype=np.float32)
    else:
        avg_mag = np.mean(np.stack(mags, axis=0), axis=0)

    freqs = np.fft.rfftfreq(frame_size, d=1.0 / sr)
    return freqs, avg_mag


def _band_energy_ratio(freqs: np.ndarray, mag: np.ndarray, f_lo: float, f_hi: float) -> float:
    """
    Energía (mag^2) en [f_lo, f_hi] / energía total.
    """
    power = mag ** 2
    total = float(np.sum(power) + EPS)
    band_mask = (freqs >= f_lo) & (freqs < f_hi)
    band_power = float(np.sum(power[band_mask]))
    return band_power / total if total > 0.0 else 0.0


def _suggest_hpf_cutoff(freqs: np.ndarray, mag: np.ndarray) -> float:
    """
    Sugiere una frecuencia de HPF (en Hz) basándose en la energía relativa en graves.
    Si no se considera necesario, devuelve 0.0.
    """
    power = mag ** 2
    total = float(np.sum(power) + EPS)

    best_cutoff = 0.0

    for f_cand, ratio_thresh in zip(HPF_CANDIDATES_HZ, HPF_RATIO_THRESHOLDS):
        mask_below = freqs < f_cand
        energy_below = float(np.sum(power[mask_below]))
        ratio = energy_below / total

        # Si la energía por debajo de esta frecuencia es pequeña, podemos cortar aquí
        if ratio < ratio_thresh:
            best_cutoff = f_cand

    return best_cutoff


def _detect_resonances(
    freqs: np.ndarray,
    mag: np.ndarray,
    recommended_hpf_cutoff_hz: float,
) -> List[NotchSpec]:
    """
    Detecta resonancias como picos en el espectro que sobresalen del baseline.

    Devuelve hasta MAX_NOTCHES_PER_STEM NotchSpec.
    """
    # Convertimos a dB
    mag_db = 20.0 * np.log10(mag + EPS)

    # Suavizado simple por convolución (moving average)
    kernel_size = 9
    kernel = np.ones(kernel_size, dtype=np.float32) / float(kernel_size)
    baseline_db = np.convolve(mag_db, kernel, mode="same")

    residual_db = mag_db - baseline_db

    # Rango de frecuencias donde buscamos resonancias
    f_min = max(RESONANCE_MIN_FREQ_HZ, recommended_hpf_cutoff_hz * 1.5)
    f_max = min(RESONANCE_MAX_FREQ_HZ, float(freqs[-1]) * 0.9)

    valid_mask = (freqs >= f_min) & (freqs <= f_max)
    peak_mask = (residual_db > RESONANCE_PEAK_THRESHOLD_DB) & valid_mask

    notches: List[NotchSpec] = []

    i = 0
    n_bins = freqs.shape[0]

    while i < n_bins:
        if not peak_mask[i]:
            i += 1
            continue

        # Agrupamos bins contiguos que superan el umbral
        start = i
        while i < n_bins and peak_mask[i]:
            i += 1
        end = i  # bin siguiente al último

        # Dentro de este grupo, buscamos el pico máximo
        group_idx = np.arange(start, end)
        group_residual = residual_db[group_idx]
        max_rel_idx = int(np.argmax(group_residual))
        peak_idx = group_idx[max_rel_idx]

        peak_freq = float(freqs[peak_idx])
        peak_height_db = float(group_residual[max_rel_idx])

        # Asignamos ganancia negativa en función de cuánto sobresale
        if peak_height_db > 12.0:
            gain_db = -9.0
        elif peak_height_db > 8.0:
            gain_db = -6.0
        else:
            gain_db = -3.0

        notches.append(NotchSpec(freq_hz=peak_freq, q=DEFAULT_NOTCH_Q, gain_db=gain_db))

        if len(notches) >= MAX_NOTCHES_PER_STEM:
            break

    return notches


# ----------------------------------------------------------------------
# Análisis principal
# ----------------------------------------------------------------------


def analyze_spectral_cleanup(media_dir: Path) -> List[SpectralCleanupResult]:
    """
    Analiza todos los .wav de media_dir y genera recomendaciones de:
      - HPF
      - Notches para resonancias

    :param media_dir: Carpeta con los stems ya normalizados en loudness.
    """
    if not media_dir.exists() or not media_dir.is_dir():
        raise FileNotFoundError(f"El directorio de medios no existe: {media_dir}")

    results: List[SpectralCleanupResult] = []

    for wav_path in sorted(media_dir.glob("*.wav")):
        audio, sr = sf.read(wav_path, always_2d=True)
        num_samples, num_channels = audio.shape
        duration_seconds = float(num_samples) / float(sr) if num_samples > 0 else 0.0

        audio_mono = audio.mean(axis=1).astype(np.float32)

        freqs, avg_mag = _compute_average_spectrum(audio_mono, sr)

        # Cálculo de ratios para logging
        ratio_0_40 = _band_energy_ratio(freqs, avg_mag, 0.0, 40.0)
        ratio_40_80 = _band_energy_ratio(freqs, avg_mag, 40.0, 80.0)
        ratio_80_160 = _band_energy_ratio(freqs, avg_mag, 80.0, 160.0)

        # HPF recomendado
        recommended_hpf = _suggest_hpf_cutoff(freqs, avg_mag)

        # Resonancias / notches
        notches = _detect_resonances(freqs, avg_mag, recommended_hpf)

        result = SpectralCleanupResult(
            file_path=wav_path,
            sample_rate=int(sr),
            num_channels=int(num_channels),
            duration_seconds=duration_seconds,
            recommended_hpf_cutoff_hz=recommended_hpf,
            low_band_energy_ratio_0_40=ratio_0_40,
            low_band_energy_ratio_40_80=ratio_40_80,
            low_band_energy_ratio_80_160=ratio_80_160,
            notches=notches,
        )
        results.append(result)

    return results


def export_spectral_cleanup_to_csv(
    results: List[SpectralCleanupResult],
    csv_path: Path,
) -> None:
    """
    Exporta las recomendaciones de HPF y notches a un CSV.

    Estructura:
      filename
      relative_path
      sample_rate
      num_channels
      duration_seconds
      recommended_hpf_cutoff_hz
      low_band_energy_ratio_0_40
      low_band_energy_ratio_40_80
      low_band_energy_ratio_80_160
      num_notches
      notch_1_freq_hz, notch_1_q, notch_1_gain_db
      ...
      notch_4_freq_hz, notch_4_q, notch_4_gain_db
    """
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    max_notches = MAX_NOTCHES_PER_STEM

    fieldnames = [
        "filename",
        "relative_path",
        "sample_rate",
        "num_channels",
        "duration_seconds",
        "recommended_hpf_cutoff_hz",
        "low_band_energy_ratio_0_40",
        "low_band_energy_ratio_40_80",
        "low_band_energy_ratio_80_160",
        "num_notches",
    ]

    for i in range(1, max_notches + 1):
        fieldnames.extend([
            f"notch_{i}_freq_hz",
            f"notch_{i}_q",
            f"notch_{i}_gain_db",
        ])

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for r in results:
            row = {
                "filename": r.file_path.name,
                "relative_path": r.file_path.name,
                "sample_rate": r.sample_rate,
                "num_channels": r.num_channels,
                "duration_seconds": f"{r.duration_seconds:.6f}",
                "recommended_hpf_cutoff_hz": f"{r.recommended_hpf_cutoff_hz:.2f}",
                "low_band_energy_ratio_0_40": f"{r.low_band_energy_ratio_0_40:.6f}",
                "low_band_energy_ratio_40_80": f"{r.low_band_energy_ratio_40_80:.6f}",
                "low_band_energy_ratio_80_160": f"{r.low_band_energy_ratio_80_160:.6f}",
                "num_notches": len(r.notches),
            }

            # Aplanar notches
            for i in range(1, max_notches + 1):
                if i <= len(r.notches):
                    notch = r.notches[i - 1]
                    row[f"notch_{i}_freq_hz"] = f"{notch.freq_hz:.2f}"
                    row[f"notch_{i}_q"] = f"{notch.q:.2f}"
                    row[f"notch_{i}_gain_db"] = f"{notch.gain_db:.2f}"
                else:
                    row[f"notch_{i}_freq_hz"] = ""
                    row[f"notch_{i}_q"] = ""
                    row[f"notch_{i}_gain_db"] = ""

            writer.writerow(row)
