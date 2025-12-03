# C:\mix-master\backend\src\analysis\S3_MIXBUS_HEADROOM.py

from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any, List
import os

# --- hack para importar utils cuando se ejecuta como script suelto ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from utils.analysis_utils import (  # noqa: E402
    load_contract,
    get_temp_dir,
    sf_read_limited,
)
from utils.session_utils import load_session_config  # noqa: E402
from utils.loudness_utils import (  # noqa: E402
    measure_integrated_lufs,
    measure_true_peak_dbfs,
)


def _load_stem_mono(stem_path: Path) -> tuple[np.ndarray, int]:
    """

    Lee un stem, lo pasa a mono (float32) y devuelve (y_mono, sr).
    """
    y, sr = sf_read_limited(stem_path, always_2d=False)
    if isinstance(y, np.ndarray) and y.ndim > 1:
        y_mono = np.mean(y, axis=1).astype(np.float32)
    else:
        y_mono = np.asarray(y, dtype=np.float32)
    return y_mono, sr


def _mix_stems_to_mono(stem_files: List[Path]) -> tuple[np.ndarray, int]:
    """
    Mezcla sencilla de todos los stems a mono para medir peak/LUFS del MixBus.

    - Asume que todos los stems tienen el mismo samplerate (garantizado por S0).
    - Normaliza la mezcla para evitar saturación durante la suma.
    """
    if not stem_files:
        return np.zeros(1, dtype=np.float32), 44100

    # Cargar y pasar a mono en paralelo
    max_workers = min(4, os.cpu_count() or 1)
    results = list(map(_load_stem_mono, stem_files))

    data_list: List[np.ndarray] = []
    sr_ref: int | None = None

    for y_mono, sr in results:
        if y_mono.size == 0:
            continue
        if sr_ref is None:
            sr_ref = sr
        data_list.append(y_mono)

    if not data_list:
        return np.zeros(1, dtype=np.float32), (sr_ref or 44100)

    max_len = max(len(y) for y in data_list)
    mix = np.zeros(max_len, dtype=np.float32)

    for y in data_list:
        n = len(y)
        mix[:n] += y

    # Normalizar para evitar saturación extrema (solo afecta a la medición, no al audio real)
    peak = float(np.max(np.abs(mix))) if mix.size > 0 else 0.0
    if peak > 1.0:
        mix /= peak

    return mix, (sr_ref or 44100)


def main() -> None:
    """
    Análisis para el contrato S3_MIXBUS_HEADROOM.

    Uso esperado desde stage.py:
        python analysis/S3_MIXBUS_HEADROOM.py S3_MIXBUS_HEADROOM
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S3_MIXBUS_HEADROOM.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S3_MIXBUS_HEADROOM"

    # 1) Cargar contrato
    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    peak_dbfs_min = float(metrics.get("peak_dbfs_min", -12.0))
    peak_dbfs_max = float(metrics.get("peak_dbfs_max", -6.0))
    lufs_min = float(metrics.get("lufs_integrated_min", -28.0))
    lufs_max = float(metrics.get("lufs_integrated_max", -20.0))

    # 2) Directorio temp/<contract_id> y session_config
    temp_dir = get_temp_dir(contract_id, create=True)

    cfg = load_session_config(contract_id)
    style_preset = cfg["style_preset"]
    instrument_by_file = cfg["instrument_by_file"]

    # 3) Listar stems (.wav) excluyendo full_song.wav
    stem_files: List[Path] = sorted(
        p for p in temp_dir.glob("*.wav")
        if p.name.lower() != "full_song.wav"
    )

    # 4) Mezcla a mono para medir headroom del MixBus (con carga de stems en paralelo)
    mix_mono, sr = _mix_stems_to_mono(stem_files)

    if mix_mono.size == 0:
        mix_peak_dbfs = float("-inf")
        mix_lufs_integrated = float("-inf")
    else:
        mix_peak_dbfs = measure_true_peak_dbfs(mix_mono, sr)
        mix_lufs_integrated = measure_integrated_lufs(mix_mono, sr)

    # 5) Montar estructura de análisis
    stems_info: List[Dict[str, Any]] = []
    for p in stem_files:
        fname = p.name
        inst = instrument_by_file.get(fname, "Other")
        stems_info.append(
            {
                "file_name": fname,
                "file_path": str(p),
                "instrument_profile": inst,
            }
        )

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
            "stage_id": stage_id,
            "style_preset": style_preset,
            "metrics_from_contract": metrics,
            "limits_from_contract": limits,
            "session": {
                "peak_dbfs_min_target": peak_dbfs_min,
                "peak_dbfs_max_target": peak_dbfs_max,
                "lufs_integrated_min_target": lufs_min,
                "lufs_integrated_max_target": lufs_max,
                "mix_peak_dbfs_measured": mix_peak_dbfs,
                "mix_lufs_integrated_measured": mix_lufs_integrated,
            },
            "stems": stems_info,
        }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    logger.logger.info(
        f"[S3_MIXBUS_HEADROOM] Análisis completado. "
        f"peak={mix_peak_dbfs:.2f} dBFS, LUFS={mix_lufs_integrated:.2f}. "
        f"JSON: {output_path}"
    )


if __name__ == "__main__":
    main()
