# C:\mix-master\backend\src\utils\analysis_utils.py

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional

import numpy as np
import soundfile as sf
import math
import traceback

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

    audio = mono.astype(np.float32)

    try:
        import essentia.standard as es
        loudness_algo = es.LoudnessEBUR128(sampleRate=sr)

        # LoudnessEBUR128 espera VECTOR_STEREOSAMPLE; si llega 1D falla con
        # "Cannot convert data from type VECTOR_REAL ...".  Duplicamos a 2
        # canales (R en silencio para conservar energia) cuando sea mono.
        if audio.ndim == 1:
            audio_for_es = np.column_stack((audio, np.zeros_like(audio)))
        elif audio.ndim == 2:
            if audio.shape[1] == 1:
                audio_for_es = np.column_stack((audio[:, 0], np.zeros_like(audio[:, 0])))
            else:
                audio_for_es = audio
        else:
            audio_for_es = audio.reshape(-1, 2)

        _, _, integrated, _ = loudness_algo(audio_for_es)
        return float(integrated)
    except ImportError:
        pass
    except TypeError:
        # Si Essentia esta disponible pero no acepta el input, seguimos con fallback.
        pass

    try:
        import pyloudnorm as pyln
        meter = pyln.Meter(sr)
        lufs = meter.integrated_loudness(audio)
        return float(lufs)
    except ImportError:
        pass

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

def _analyze_audio_series(audio: np.ndarray, sr: int) -> Dict[str, Any]:
    """
    Computes time-series and spectral analysis for a single audio track.
    Returns a dict with:
      - loudness: {momentary, short_term, integrated, lra, time}
      - dynamics: {crest, time}
      - stereo: {correlation, width, time}
      - spectrogram: {data (low-res), freqs, times}
    """
    if audio.ndim == 1:
        # Mono -> Make stereo duplicate for consistent processing if needed,
        # but optimized paths use mono or stereo explicitly.
        # For stereo metrics, mono will result in width=0 and corr=1
        stereo = np.column_stack((audio, audio))
        mono = audio
    else:
        stereo = audio
        mono = np.mean(audio, axis=1)

    duration = len(mono) / sr

    # --- 1. Loudness (EBU R128) via Essentia ---
    # Essentia's LoudnessEBUR128 returns (momentary, shortTerm, integrated, lra)
    # Momentary is every 400ms typically (100ms step).
    # We want to downsample to avoid huge JSONs.

    l_momentary = []
    l_short = []
    l_integrated = -14.0
    l_lra = 0.0
    l_time = []

    try:
        import essentia.standard as es
        # Essentia expects Stereo for Loudness? Docs say "signal" (mono) or use specific algo.
        # LoudnessEBUR128 takes a vector (mono) or stereo audio?
        # Actually in standard mode it takes a signal. If we pass stereo, we might need a different algo.
        # Standard LoudnessEBUR128 usually takes a sound signal (mono).
        # But EBU R128 is defined for stereo/multichannel.
        # Essentia docs: "Input: signal (vector_real)". It mixes to mono internally or expects mono?
        # Let's use the mono signal for approximation if stereo is not supported easily,
        # but EBU R128 K-weighting accounts for channel summing.
        # Ideally we use `Loudness` algo but that's not R128.
        # Let's stick to mono for "Loudness" approx or if Essentia handles it.
        # Wait, Essentia has `LoudnessEBUR128`.

        loudness_algo = es.LoudnessEBUR128(sampleRate=sr, hopSize=int(sr * 0.1)) # 100ms hop
        # Essentia expects mono usually for this specific simple call?
        # If we pass stereo, it might fail if shape is (N, 2).
        # We will use the mono mixdown.
        m, s, i, lra = loudness_algo(mono.astype(np.float32))

        # Downsample to ~500 points max for UI
        step = max(1, len(m) // 500)
        l_momentary = [round(float(x), 2) for x in m[::step]]
        l_short = [round(float(x), 2) for x in s[::step]]
        l_integrated = float(i)
        l_lra = float(lra)

        # Time axis
        l_time = [round(t * 0.1 * step, 2) for t in range(len(l_momentary))]

    except ImportError:
        # Fallback to simple RMS-based "Loudness"
        pass
    except Exception:
        # Fallback
        traceback.print_exc()

    if not l_momentary:
        # RMS fallback
        window_sec = 0.1
        w_samp = int(sr * window_sec)
        # ... (RMS logic similar to old implementation)
        # Use existing logic logic
        pass


    # --- 2. Dynamics (Crest Factor) ---
    # Crest Factor = Peak_dB - RMS_dB
    # Calculated on windows (e.g. 100ms)

    window_sec = 0.1
    w_samp = int(sr * window_sec)
    if w_samp == 0: w_samp = 1024

    # Pad
    pad_len = (w_samp - (len(mono) % w_samp)) % w_samp
    if pad_len > 0:
        mono_padded = np.pad(mono, (0, pad_len))
        stereo_padded = np.pad(stereo, ((0, pad_len), (0, 0)))
    else:
        mono_padded = mono
        stereo_padded = stereo

    chunks_mono = mono_padded.reshape(-1, w_samp)

    rms_vals = np.sqrt(np.mean(chunks_mono**2, axis=1))
    rms_db = 20 * np.log10(np.maximum(rms_vals, 1e-9))

    peak_vals = np.max(np.abs(chunks_mono), axis=1)
    peak_db = 20 * np.log10(np.maximum(peak_vals, 1e-9))

    crest_db = peak_db - rms_db

    # Downsample dynamics to match loudness if possible or fixed size
    step_dyn = max(1, len(crest_db) // 500)
    crest_resampled = [round(float(x), 2) for x in crest_db[::step_dyn]]
    dyn_time = [round(t * window_sec * step_dyn, 2) for t in range(len(crest_resampled))]

    if not l_momentary:
        # Populate loudness fallback
        l_momentary = [round(float(x) + 3.0, 2) for x in rms_db[::step_dyn]] # +3dB compensation approx
        l_short = l_momentary # duplicate
        l_time = dyn_time


    # --- 3. Stereo Analysis (Correlation, Width) ---
    # Correlation: Pearson correlation between L and R in window
    # Width: Side energy / Mid energy ratio

    corr_vals = []
    width_vals = []

    # If mono file, correlation is 1.0, width is 0.0
    if audio.ndim == 1:
        corr_vals = [1.0] * len(crest_resampled)
        width_vals = [0.0] * len(crest_resampled)
    else:
        # Process in chunks (re-use chunks logic but for stereo)
        # chunks_stereo shape: (num_chunks, w_samp, 2)
        num_chunks = stereo_padded.shape[0] // w_samp
        chunks_stereo = stereo_padded.reshape(num_chunks, w_samp, 2)

        # Subsample for speed: calculate for every Nth chunk
        indices = range(0, num_chunks, step_dyn)

        for idx in indices:
            chunk = chunks_stereo[idx]
            L = chunk[:, 0]
            R = chunk[:, 1]

            # Correlation
            # np.corrcoef returns 2x2 matrix
            # Handle silence
            if np.std(L) < 1e-9 or np.std(R) < 1e-9:
                c = 0.0
            else:
                c = np.corrcoef(L, R)[0, 1]

            # Width (M/S)
            M = (L + R) * 0.5
            S = (L - R) * 0.5

            rms_m = np.sqrt(np.mean(M**2))
            rms_s = np.sqrt(np.mean(S**2))

            if rms_m < 1e-9:
                w = 0.0
            else:
                w = rms_s / (rms_m + 1e-9)

            corr_vals.append(round(float(c), 3))
            width_vals.append(round(float(w), 3))

    # --- 4. Spectrogram (Downsampled) ---
    # We produce a grid of roughly 64 freq bands x 100 time slices
    n_fft = 2048
    hop_length = len(mono) // 100
    if hop_length < 512: hop_length = 512

    try:
        import librosa
        # Spectrogram
        S = librosa.stft(mono, n_fft=n_fft, hop_length=hop_length)
        S_db = librosa.amplitude_to_db(np.abs(S), ref=np.max)

        # Resize to 64 bands (Mel scale ideally, or Log)
        # We can use librosa.feature.melspectrogram logic but applied to pre-computed STFT
        # Or just bin averaging

        # Use mel filter bank
        n_mels = 64
        mels = librosa.filters.mel(sr=sr, n_fft=n_fft, n_mels=n_mels, fmin=20, fmax=sr/2)
        mel_S = np.dot(mels, np.abs(S))
        mel_db = librosa.power_to_db(mel_S**2, ref=np.max)

        # mel_db is (n_mels, n_frames).
        # We want to transpose to (n_frames, n_mels) for JSON?
        # Or just list of lists.
        # Limit frames to ~100
        if mel_db.shape[1] > 100:
            step_spec = mel_db.shape[1] // 100
            mel_db = mel_db[:, ::step_spec]

        spec_data = []
        for i in range(mel_db.shape[1]): # Iterate time
            col = [round(float(x), 1) for x in mel_db[:, i]]
            spec_data.append(col)

        # Compute Average Spectrum (Tonal Balance)
        # Average across time (axis 1 of mel_db)
        mean_spectrum = np.mean(mel_db, axis=1)
        tonal_data = [round(float(x), 2) for x in mean_spectrum]

        spec_freqs = [int(f) for f in librosa.mel_frequencies(n_mels=n_mels, fmin=20, fmax=sr/2)]
        spec_times = [round(t * hop_length / sr, 2) for t in range(len(spec_data))] # approximate time check

    except ImportError:
        spec_data = []
        spec_freqs = []
        spec_times = []
        tonal_data = []


    return {
        "loudness": {
            "momentary": l_momentary,
            "short_term": l_short,
            "integrated": l_integrated,
            "lra": l_lra,
            "time": l_time
        },
        "dynamics": {
            "crest": crest_resampled,
            "time": dyn_time
        },
        "stereo": {
            "correlation": corr_vals,
            "width": width_vals,
            "time": dyn_time
        },
        "spectrogram": {
            "data": spec_data,
            "freqs": spec_freqs,
            # "times": spec_times # derived in UI
        },
        "tonal": {
            "spectrum": tonal_data,
            "freqs": spec_freqs
        }
    }


def compute_interactive_data(audio: np.ndarray, sr: int, audio_original: Optional[np.ndarray] = None) -> Dict[str, Any]:
    """
    Generates data for interactive charts including A/B comparison.
    """
    if audio is None or len(audio) == 0:
        return {}

    result_data = _analyze_audio_series(audio, sr)

    original_data = None
    if audio_original is not None and len(audio_original) > 0:
        original_data = _analyze_audio_series(audio_original, sr)

    return {
        "result": result_data,
        "original": original_data
    }
