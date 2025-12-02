# C:\mix-master\backend\src\utils\analysis_utils.py

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional

import numpy as np
import soundfile as sf

# Opcional: mejor cálculo de LUFS si está disponible
try:
    import pyloudnorm as pyln  # pip install pyloudnorm
except ImportError:
    pyln = None

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

    Levanta ValueError si no lo encuentra.
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
    Devuelve la raíz temporal del job actual.

    Orden de prioridad:
      1) MIX_TEMP_ROOT (ruta completa a temp/<job_id>).
      2) PROJECT_ROOT/temp/MIX_JOB_ID si MIX_JOB_ID está definida.
      3) PROJECT_ROOT/temp (modo single-job / CLI).

    Si create=True, se asegura de que la carpeta exista.
    """
    temp_root_env = os.getenv("MIX_TEMP_ROOT")
    job_id_env = os.getenv("MIX_JOB_ID")

    if temp_root_env:
        base = Path(temp_root_env)
    elif job_id_env:
        base = PROJECT_ROOT / "temp" / job_id_env
    else:
        base = PROJECT_ROOT / "temp"

    if create:
        base.mkdir(parents=True, exist_ok=True)

    return base


def get_temp_dir(contract_id: str, create: bool = False) -> Path:
    """
    Devuelve la carpeta temporal para un contrato concreto.

    - En modo "single-job" (CLI):
        PROJECT_ROOT/temp/<contract_id>
    - En modo multi-job (Celery u otro):
        PROJECT_ROOT/temp/<MIX_JOB_ID>/<contract_id>
      o bien MIX_TEMP_ROOT/<contract_id> si MIX_TEMP_ROOT ya apunta a temp/<job_id>.

    Esto permite que:
      - stage.py siga igual (sólo pasa contract_id).
      - El namespacing por job se consiga sólo con env vars.
    """
    job_root = _get_job_temp_root(create=create)
    temp_dir = job_root / contract_id

    if create:
        temp_dir.mkdir(parents=True, exist_ok=True)

    return temp_dir


# ---------------------------------------------------------------------
# Utilidades de audio
# ---------------------------------------------------------------------

def load_audio_mono(path: Path) -> Tuple[np.ndarray, int]:
    """
    Lee un archivo de audio y devuelve (mono, samplerate).

    - Convierte a float32.
    - Si es estéreo/multicanal, hace media de canales (promedio).
    """
    data, sr = sf.read(path, always_2d=False)

    if not isinstance(data, np.ndarray):
        data = np.array(data, dtype=np.float32)
    else:
        data = data.astype(np.float32)

    if data.ndim == 1:
        mono = data
    else:
        # media de canales
        mono = np.mean(data, axis=1).astype(np.float32)

    return mono, sr


def compute_dc_offset(mono: np.ndarray) -> Tuple[float, float]:
    """
    Devuelve (dc_offset_linear, dc_offset_db).

    dc_offset_linear = media de la señal en [-1, 1].
    dc_offset_db = 20 * log10(|dc_offset_linear|)
                   o un valor muy bajo si es casi 0.
    """
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
    """
    Devuelve el pico máximo en dBFS (aprox. true peak a nivel de muestra).
    """
    if mono.size == 0:
        return float("-inf")

    peak = float(np.max(np.abs(mono)))
    if peak <= 0.0:
        return float("-inf")

    return float(20.0 * np.log10(peak))


def compute_mixbus_peak_dbfs(stem_paths: List[Path]) -> float:
    """
    Calcula el pico m?ximo en dBFS de la suma unity de todos los stems.

    - Asume mismo samplerate y n? de canales (garantizado por S0_SESSION_FORMAT).
    - Si detecta stems con sr o canales distintos, los omite.
    - Si no hay stems v?lidos, devuelve -inf.
    """
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
    peak_val = 0.0
    files = [sf.SoundFile(p, "r") for p in valid_paths]
    try:
        while True:
            sum_block = np.zeros((blocksize, ch_ref), dtype=np.float32)
            max_len = 0
            for f in files:
                data = f.read(blocksize, dtype="float32", always_2d=True)
                if data.size == 0:
                    continue
                n = data.shape[0]
                max_len = max(max_len, n)
                sum_block[:n, :] += data
            if max_len == 0:
                break
            peak_val = max(peak_val, float(np.max(np.abs(sum_block[:max_len]))))
    finally:
        for f in files:
            f.close()

    if peak_val <= 0.0:
        return float("-inf")
    return float(20.0 * np.log10(peak_val))


def compute_integrated_loudness_lufs(mono: np.ndarray, sr: int) -> float:
    """
    Devuelve el loudness integrado en LUFS.

    - Si pyloudnorm está disponible, usa ITU-R BS.1770 (más preciso).
    - Si no, hace un fallback aproximado: LUFS ≈ 20*log10(rms) - 0.691
      suficiente para 'working loudness' por rangos.

    En caso de señal vacía o silencio absoluto, devuelve -inf.
    """
    if mono.size == 0:
        return float("-inf")

    if pyln is not None:
        # Modo EBU R128 (por defecto). La señal debe ser float32/64.
        meter = pyln.Meter(sr)
        lufs = meter.integrated_loudness(mono.astype(np.float32))
        return float(lufs)

    # Fallback aproximado
    rms = float(np.sqrt(np.mean(mono ** 2)))
    if rms <= 0.0:
        return float("-inf")

    # Aproximación simple de LUFS a partir de RMS
    return float(20.0 * np.log10(rms) - 0.691)
