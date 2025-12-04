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
    Devuelve la raíz temporal del job. Por defecto usa /dev/shm (RAM)
    para minimizar I/O en disco; si no existe o falla, cae a backend/temp.
    Se puede sobrescribir con MIX_TEMP_ROOT.
    """
    temp_root_env = os.getenv("MIX_TEMP_ROOT")
    job_id_env = os.getenv("MIX_JOB_ID")

    preferred_base = Path("/dev/shm/mix-master/temp")

    if temp_root_env:
        # Si el usuario define MIX_TEMP_ROOT, lo usamos tal cual (sin añadir job_id de nuevo)
        base = Path(temp_root_env)
    else:
        base = preferred_base / job_id_env if job_id_env else preferred_base

    if create:
        try:
            base.mkdir(parents=True, exist_ok=True)
        except OSError:
            # fallback a backend/temp
            fallback = (PROJECT_ROOT / "temp" / job_id_env) if job_id_env else (PROJECT_ROOT / "temp")
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
