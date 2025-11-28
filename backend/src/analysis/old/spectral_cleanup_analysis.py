from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional

import numpy as np
import soundfile as sf

# ----------------------------------------------------------------------
# Parametros globales del analisis
# ----------------------------------------------------------------------

FRAME_SIZE = 4096
HOP_SIZE = FRAME_SIZE // 2
EPS = 1e-12

HPF_CANDIDATES_HZ = [40.0, 60.0, 80.0, 100.0, 120.0]
HPF_RATIO_THRESHOLDS = [0.02, 0.03, 0.05, 0.07, 0.10]

RESONANCE_MIN_FREQ_HZ = 120.0
RESONANCE_MAX_FREQ_HZ = 12000.0
RESONANCE_PEAK_THRESHOLD_DB = 6.0
MAX_NOTCHES_PER_STEM = 4
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
    instrument_profile: str
    recommended_hpf_cutoff_hz: float
    low_band_energy_ratio_0_40: float
    low_band_energy_ratio_40_80: float
    low_band_energy_ratio_80_160: float
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
    Calcula el espectro medio de magnitud (lineal) sin almacenar todos los frames.
    """
    n_samples = audio_mono.shape[0]
    if n_samples < frame_size:
        audio_mono = np.pad(audio_mono, (0, frame_size - n_samples), mode="constant")
        n_samples = audio_mono.shape[0]

    window = np.hanning(frame_size).astype(np.float32)
    sum_mag: Optional[np.ndarray] = None
    frame_count = 0

    for start in range(0, n_samples - frame_size + 1, hop_size):
        frame = audio_mono[start : start + frame_size] * window
        spectrum = np.fft.rfft(frame)
        mag = np.abs(spectrum)

        if sum_mag is None:
            sum_mag = mag
        else:
            sum_mag += mag

        frame_count += 1

    if sum_mag is None or frame_count == 0:
        avg_mag = np.zeros(frame_size // 2 + 1, dtype=np.float32)
    else:
        avg_mag = (sum_mag / float(frame_count)).astype(np.float32)

    freqs = np.fft.rfftfreq(frame_size, d=1.0 / sr)
    return freqs, avg_mag


def _band_energy_ratio(freqs: np.ndarray, mag: np.ndarray, f_lo: float, f_hi: float) -> float:
    power = mag ** 2
    total = float(np.sum(power) + EPS)
    band_mask = (freqs >= f_lo) & (freqs < f_hi)
    band_power = float(np.sum(power[band_mask]))
    return band_power / total if total > 0.0 else 0.0


def _suggest_hpf_cutoff(freqs: np.ndarray, mag: np.ndarray) -> float:
    power = mag ** 2
    total = float(np.sum(power) + EPS)

    best_cutoff = 0.0
    for f_cand, ratio_thresh in zip(HPF_CANDIDATES_HZ, HPF_RATIO_THRESHOLDS):
        energy_below = float(np.sum(power[freqs < f_cand]))
        ratio = energy_below / total
        if ratio < ratio_thresh:
            best_cutoff = f_cand

    return best_cutoff


def _detect_resonances(
    freqs: np.ndarray,
    mag: np.ndarray,
    recommended_hpf_cutoff_hz: float,
) -> List[NotchSpec]:
    mag_db = 20.0 * np.log10(mag + EPS)

    kernel = np.ones(9, dtype=np.float32) / 9.0
    baseline_db = np.convolve(mag_db, kernel, mode="same")
    residual_db = mag_db - baseline_db

    f_min = max(RESONANCE_MIN_FREQ_HZ, recommended_hpf_cutoff_hz * 1.5)
    f_max = min(RESONANCE_MAX_FREQ_HZ, float(freqs[-1]) * 0.9)

    valid_mask = (freqs >= f_min) & (freqs <= f_max)
    peak_mask = (residual_db > RESONANCE_PEAK_THRESHOLD_DB) & valid_mask

    notches: List[NotchSpec] = []
    i = 0
    n_bins = freqs.shape[0]

    while i < n_bins and len(notches) < MAX_NOTCHES_PER_STEM:
        if not peak_mask[i]:
            i += 1
            continue

        start = i
        while i < n_bins and peak_mask[i]:
            i += 1
        end = i

        group_idx = np.arange(start, end)
        group_residual = residual_db[group_idx]
        peak_idx = group_idx[int(np.argmax(group_residual))]

        peak_freq = float(freqs[peak_idx])
        peak_height_db = float(group_residual.max())

        if peak_height_db > 12.0:
            gain_db = -9.0
        elif peak_height_db > 8.0:
            gain_db = -6.0
        else:
            gain_db = -3.0

        notches.append(NotchSpec(freq_hz=peak_freq, q=DEFAULT_NOTCH_Q, gain_db=gain_db))

    return notches


# ----------------------------------------------------------------------
# Analisis principal
# ----------------------------------------------------------------------


def analyze_spectral_cleanup(media_dir: Path) -> List[SpectralCleanupResult]:
    if not media_dir.exists() or not media_dir.is_dir():
        raise FileNotFoundError(f"El directorio de medios no existe: {media_dir}")

    results: List[SpectralCleanupResult] = []

    for wav_path in sorted(media_dir.glob("*.wav")):
        audio, sr = sf.read(wav_path, dtype="float32", always_2d=True)
        num_samples, num_channels = audio.shape
        duration_seconds = float(num_samples) / float(sr) if num_samples > 0 else 0.0

        audio_mono = audio.mean(axis=1, dtype=np.float32)

        freqs, avg_mag = _compute_average_spectrum(audio_mono, sr)

        ratio_0_40 = _band_energy_ratio(freqs, avg_mag, 0.0, 40.0)
        ratio_40_80 = _band_energy_ratio(freqs, avg_mag, 40.0, 80.0)
        ratio_80_160 = _band_energy_ratio(freqs, avg_mag, 80.0, 160.0)

        recommended_hpf = _suggest_hpf_cutoff(freqs, avg_mag)
        notches = _detect_resonances(freqs, avg_mag, recommended_hpf)

        results.append(
            SpectralCleanupResult(
                file_path=wav_path,
                sample_rate=int(sr),
                num_channels=int(num_channels),
                duration_seconds=duration_seconds,
                instrument_profile="",
                recommended_hpf_cutoff_hz=recommended_hpf,
                low_band_energy_ratio_0_40=ratio_0_40,
                low_band_energy_ratio_40_80=ratio_40_80,
                low_band_energy_ratio_80_160=ratio_80_160,
                notches=notches,
            )
        )

    return results


def export_spectral_cleanup_to_json(
    results: List[SpectralCleanupResult],
    json_path: Path,
) -> None:
    """
    Exporta las recomendaciones de HPF y notches a JSON.
    """
    json_path.parent.mkdir(parents=True, exist_ok=True)

    payload = []
    for r in results:
        item = asdict(r)
        item["file_path"] = r.file_path.name
        item["relative_path"] = r.file_path.name
        item["notches"] = [asdict(n) for n in r.notches]
        payload.append(item)

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
