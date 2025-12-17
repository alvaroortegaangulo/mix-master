# C:\mix-master\backend\src\utils\analysis_utils.py

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional

import numpy as np
import soundfile as sf
import math

# Límite global de segundos para análisis (se puede sobrescribir con MIX_ANALYSIS_MAX_SECONDS)
# Solo se aplica en helpers de análisis; NO se toca el comportamiento global de soundfile.read
MAX_ANALYSIS_SECONDS = float(os.getenv("MIX_ANALYSIS_MAX_SECONDS", 90.0))

# ---------------------------------------------------------------------
# Paths base del proyecto
# ---------------------------------------------------------------------

# .../src
BASE_DIR = Path(__file__).resolve().parent.parent
# .../backend
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_PATH = BASE_DIR / "struct" / "contracts.json"


# ---------------------------------------------------------------------
# Carga de contratos
# ---------------------------------------------------------------------

def load_contract(contract_id: str) -> Dict[str, Any]:
    """
    Carga contracts.json y devuelve el contrato cuyo id == contract_id.
    """
    with CONTRACTS_PATH.open("r", encoding="utf-8") as f:
        contracts = json.load(f)

    for stage_data in contracts.get("stages", {}).values():
        for c in stage_data.get("contracts", []):
            if c.get("id") == contract_id:
                return c

    raise ValueError(
        f"No se ha encontrado contrato con id '{contract_id}' en {CONTRACTS_PATH}"
    )


# ---------------------------------------------------------------------
# Gestión de carpetas temporales (single-job vs multi-job)
# ---------------------------------------------------------------------

def _get_job_temp_root(create: bool = False) -> Path:
    """
    Devuelve la raíz temporal del job en disco.
    Usa backend/temp como base por defecto; si MIX_TEMP_ROOT está definido se toma como base.
    Si hay MIX_JOB_ID y la ruta base no lo incluye, se añade como subcarpeta.
    """
    temp_root_env = os.getenv("MIX_TEMP_ROOT")
    job_id_env = os.getenv("MIX_JOB_ID")

    base = Path(temp_root_env) if temp_root_env else (PROJECT_ROOT / "temp")

    if job_id_env and job_id_env not in base.parts:
        base = base / job_id_env

    if create:
        try:
            base.mkdir(parents=True, exist_ok=True)
        except OSError:
            fallback = PROJECT_ROOT / "temp"
            if job_id_env:
                fallback = fallback / job_id_env
            fallback.mkdir(parents=True, exist_ok=True)
            base = fallback

    return base


def get_temp_dir(contract_id: str, create: bool = False) -> Path:
    job_root = _get_job_temp_root(create=create)
    temp_dir = job_root / contract_id
    if create:
        temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


# ---------------------------------------------------------------------
# Utilidades de audio
# ---------------------------------------------------------------------

def sf_read_limited(path: Path, always_2d: bool = False, max_seconds: float | None = MAX_ANALYSIS_SECONDS):
    """
    Lectura limitada a max_seconds (si se especifica) usando soundfile.
    """
    info = sf.info(path)
    frames = None
    if max_seconds is not None:
        frames = min(info.frames, int(info.samplerate * max_seconds))
    data, sr = sf.read(path, frames=frames, always_2d=always_2d)
    return data, sr


def load_audio_mono(path: Path, max_seconds: float | None = MAX_ANALYSIS_SECONDS) -> Tuple[np.ndarray, int]:
    data, sr = sf_read_limited(path, always_2d=False, max_seconds=max_seconds)

    if not isinstance(data, np.ndarray):
        data = np.array(data, dtype=np.float32)
    else:
        data = data.astype(np.float32)

    if data.ndim == 1:
        mono = data
    else:
        mono = np.mean(data, axis=1).astype(np.float32)

    return mono, sr


def compute_dc_offset(mono: np.ndarray) -> Tuple[float, float]:
    if mono.size == 0:
        return 0.0, float("-inf")

    dc_linear = float(np.mean(mono))

    eps = 1e-12
    if abs(dc_linear) < eps:
        dc_db = -120.0
    else:
        dc_db = 20.0 * np.log10(abs(dc_linear))

    return dc_linear, float(dc_db)


def compute_peak_dbfs(mono: np.ndarray) -> float:
    if mono.size == 0:
        return float("-inf")

    peak = float(np.max(np.abs(mono)))
    if peak <= 0.0:
        return float("-inf")

    return float(20.0 * np.log10(peak))


def compute_mixbus_peak_dbfs(stem_paths: List[Path], max_seconds: float | None = MAX_ANALYSIS_SECONDS) -> float:
    if not stem_paths:
        return float("-inf")

    sr_ref: Optional[int] = None
    ch_ref: Optional[int] = None
    valid_paths: List[Path] = []

    for p in stem_paths:
        try:
            with sf.SoundFile(p, "r") as f:
                sr = f.samplerate
                ch = f.channels
        except Exception:
            continue

        if sr_ref is None:
            sr_ref = sr
            ch_ref = ch
        else:
            if sr != sr_ref or ch != ch_ref:
                continue
        valid_paths.append(p)

    if not valid_paths or ch_ref is None:
        return float("-inf")

    blocksize = 65536
    max_frames = int(sr_ref * max_seconds) if (sr_ref is not None and max_seconds is not None) else None
    peak_val = 0.0
    files = [sf.SoundFile(p, "r") for p in valid_paths]
    frames_read = 0
    try:
        while True:
            sum_block = np.zeros((blocksize, ch_ref), dtype=np.float32)
            max_len = 0
            for f in files:
                read_size = blocksize
                if max_frames is not None:
                    remaining = max_frames - frames_read
                    if remaining <= 0:
                        data = np.zeros((0, ch_ref), dtype=np.float32)
                    else:
                        read_size = min(read_size, remaining)
                        data = f.read(read_size, dtype="float32", always_2d=True)
                else:
                    data = f.read(read_size, dtype="float32", always_2d=True)
                if data.size == 0:
                    continue
                n = data.shape[0]
                max_len = max(max_len, n)
                sum_block[:n, :] += data
            if max_len == 0:
                break
            peak_val = max(peak_val, float(np.max(np.abs(sum_block[:max_len]))))
            if max_frames is not None:
                frames_read += max_len
                if frames_read >= max_frames:
                    break
    finally:
        for f in files:
            f.close()

    if peak_val <= 0.0:
        return float("-inf")
    return float(20.0 * np.log10(peak_val))


def compute_integrated_loudness_lufs(mono: np.ndarray, sr: int) -> float:
    if mono.size == 0:
        return float("-inf")

    try:
        import pyloudnorm as pyln  # local import to avoid module-level dependency
    except ImportError:
        pyln = None

    if pyln is not None:
        meter = pyln.Meter(sr)
        lufs = meter.integrated_loudness(mono.astype(np.float32))
        return float(lufs)

    rms = float(np.sqrt(np.mean(mono ** 2)))
    if rms <= 0.0:
        return float("-inf")

    return float(20.0 * np.log10(rms) - 0.691)


def sanitize_json_floats(obj: Any) -> Any:
    """
    Recursively replaces Infinity, -Infinity, and NaN with None
    so that JSON serialization produces valid JSON (null) instead of invalid tokens.
    """
    if isinstance(obj, float):
        if not math.isfinite(obj):
            return None
        return obj
    elif isinstance(obj, (np.floating, np.integer)):
        val = float(obj)
        if not math.isfinite(val):
            return None
        return val
    elif isinstance(obj, dict):
        return {k: sanitize_json_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_json_floats(v) for v in obj]
    elif isinstance(obj, tuple):
        return tuple(sanitize_json_floats(v) for v in obj)
    return obj

def compute_interactive_data(audio: np.ndarray, sr: int) -> Dict[str, Any]:
    """
    Generates data for interactive charts:
    1. Dynamics: RMS & Peak over time (e.g. 100ms windows)
    2. Spectrum: Average magnitude spectrum (log-spaced bands)
    """
    if audio is None or len(audio) == 0:
        return {}

    if audio.ndim > 1:
        # Mix to mono for analysis
        mono = np.mean(audio, axis=1)
    else:
        mono = audio

    # --- Dynamics (RMS & Peak) ---
    window_sec = 0.1  # 100ms
    window_samples = int(sr * window_sec)
    if window_samples == 0: window_samples = 1024

    # Pad to multiple of window
    pad_len = (window_samples - (len(mono) % window_samples)) % window_samples
    if pad_len > 0:
        mono_padded = np.pad(mono, (0, pad_len))
    else:
        mono_padded = mono

    # Reshape
    chunks = mono_padded.reshape(-1, window_samples)

    # RMS per chunk
    rms_vals = np.sqrt(np.mean(chunks**2, axis=1))
    rms_db = 20 * np.log10(np.maximum(rms_vals, 1e-9))

    # Peak per chunk
    peak_vals = np.max(np.abs(chunks), axis=1)
    peak_db = 20 * np.log10(np.maximum(peak_vals, 1e-9))

    # Clean up limits
    rms_db = np.clip(rms_db, -90, 0)
    peak_db = np.clip(peak_db, -90, 0)

    dynamics = {
        "time_step": window_sec,
        "rms_db": [round(float(x), 2) for x in rms_db],
        "peak_db": [round(float(x), 2) for x in peak_db],
        "duration_sec": len(mono) / sr
    }

    # --- Spectrum (Averaged Log Bands) ---
    n_fft = 4096

    # Take up to 100 chunks spread across the file to estimate average spectrum
    step = len(mono) // 100
    if step < n_fft:
        step = n_fft

    indices = np.arange(0, len(mono) - n_fft, step)
    if len(indices) == 0:
        # Fallback for short files
        indices = [0]
        if len(mono) < n_fft:
            n_fft = len(mono)
            if n_fft == 0:
                return {"dynamics": dynamics}

    magnitudes = []
    window = np.hanning(n_fft)

    for idx in indices:
        if idx + n_fft > len(mono): break
        chunk = mono[idx:idx+n_fft] * window
        fft = np.fft.rfft(chunk)
        mag = np.abs(fft)
        magnitudes.append(mag)

    if not magnitudes:
        avg_mag = np.zeros(n_fft//2 + 1)
    else:
        avg_mag = np.mean(magnitudes, axis=0)

    freqs = np.fft.rfftfreq(n_fft, 1/sr)

    # Log Bins
    min_freq = 20
    max_freq = sr / 2
    num_bands = 64

    log_freqs = np.logspace(np.log10(min_freq), np.log10(max_freq), num_bands + 1)
    band_energies = []
    band_centers = []

    for i in range(num_bands):
        f_start = log_freqs[i]
        f_end = log_freqs[i+1]
        mask = (freqs >= f_start) & (freqs < f_end)

        if np.any(mask):
            # Mean Power
            energy = np.mean(avg_mag[mask]**2)
            db = 10 * np.log10(np.maximum(energy, 1e-12))
            band_energies.append(db)
        else:
            band_energies.append(-90.0)

        band_centers.append(np.sqrt(f_start * f_end))

    # Normalize spectrum for display (relative to max)
    # max_db = max(band_energies) if band_energies else -90
    # Or keep absolute? Absolute is hard to interpret without calibration.
    # But relative is fine. Let's keep absolute dBFS-ish (calculated from normalized audio).

    spectrum = {
        "frequencies": [round(float(f), 1) for f in band_centers],
        "magnitudes_db": [round(float(m), 2) for m in band_energies]
    }

    return {
        "dynamics": dynamics,
        "spectrum": spectrum
    }
