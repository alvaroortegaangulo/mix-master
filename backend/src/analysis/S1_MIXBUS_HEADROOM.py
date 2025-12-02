# C:\mix-master\backend\src\analysis\S1_MIXBUS_HEADROOM.py

import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

# --- hack para poder importar utils cuando se ejecuta como script suelto ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import os  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from utils.analysis_utils import (  # noqa: E402
    load_contract,
    get_temp_dir,
    sf_read_limited,
)
from utils.loudness_utils import compute_lufs_and_lra  # noqa: E402


# ---------------------------------------------------------------------------
# Workers para cálculo paralelo del mix preliminar (suma de stems)
# ---------------------------------------------------------------------------

def _load_stem_for_mix(stem_path_str: str):
    """
    Worker: lee un stem a float32 y lo devuelve con su samplerate.

    Devuelve (data_2d, sr). Si hay error, devuelve (None, None).
    """
    stem_path = Path(stem_path_str)
    try:
        data, sr = sf_read_limited(stem_path, always_2d=True)  # (n_samples, n_channels)
        data = data.astype(np.float32)
        return data, sr
    except Exception as e:
        print(f"[S1_MIXBUS_HEADROOM] Aviso: no se pudo leer {stem_path}: {e}")
        return None, None


def _compute_mixbus_peak_and_lufs_parallel(
    stem_paths: List[Path],
) -> Tuple[float, float | None]:
    """
    Calcula el pico del mix preliminar (suma unity de todos los stems) en paralelo
    y el LUFS integrado aproximado de ese mix.

    Devuelve (peak_dbfs, lufs_integrated) donde lufs_integrated puede ser None
    si hay algún problema de cálculo.
    """
    if not stem_paths:
        return float("-inf"), None

    stem_path_strs = [str(p) for p in stem_paths]
    max_workers = min(4, os.cpu_count() or 1)

    data_list = []
    sr_ref = None
    ch_ref = None

    # 1) Cargar stems en paralelo
    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        for data, sr in ex.map(_load_stem_for_mix, stem_path_strs):
            if data is None or sr is None:
                continue

            if sr_ref is None:
                sr_ref = sr
                ch_ref = data.shape[1]

            data_list.append(data)

    if not data_list or ch_ref is None or sr_ref is None:
        return float("-inf"), None

    # 2) Sumar a un único buffer mix
    max_len = max(d.shape[0] for d in data_list)
    mix = np.zeros((max_len, ch_ref), dtype=np.float32)

    for d in data_list:
        n = d.shape[0]
        mix[:n, :] += d

    # 3) Peak en dBFS
    peak = float(np.max(np.abs(mix)))
    if peak <= 0.0:
        peak_dbfs = float("-inf")
    else:
        peak_dbfs = float(20.0 * np.log10(peak))

    # 4) LUFS integrado del mix preliminar
    lufs_integrated: float | None = None
    if peak_dbfs != float("-inf"):
        try:
            lufs_integrated, _ = compute_lufs_and_lra(mix, sr_ref)
            lufs_integrated = float(lufs_integrated)
        except Exception as e:
            print(
                f"[S1_MIXBUS_HEADROOM] Aviso: no se pudo calcular LUFS del mixbus: {e}"
            )
            lufs_integrated = None

    return peak_dbfs, lufs_integrated


def main() -> None:
    """
    Análisis para el contrato S1_MIXBUS_HEADROOM.

    Uso esperado desde stage.py:
        python analysis/S1_MIXBUS_HEADROOM.py S1_MIXBUS_HEADROOM
    """
    if len(sys.argv) < 2:
        print("Uso: python S1_MIXBUS_HEADROOM.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S1_MIXBUS_HEADROOM"

    # 1) Cargar contrato y directorio temp/<contract_id>
    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    temp_dir = get_temp_dir(contract_id, create=True)

    # 2) Listar stems (.wav) en temp/<contract_id>, excluyendo full_song.wav
    stem_files: List[Path] = sorted(
        p for p in temp_dir.glob("*.wav") if p.name.lower() != "full_song.wav"
    )

    # 3) Calcular pico de mixbus + LUFS de trabajo en paralelo
    mixbus_peak_dbfs_measured, mixbus_lufs_integrated_measured = (
        _compute_mixbus_peak_and_lufs_parallel(stem_files)
    )

    # Rango objetivo desde el contrato (con defaults razonables)
    peak_dbfs_min = float(metrics.get("peak_dbfs_min", -12.0))
    peak_dbfs_max = float(metrics.get("peak_dbfs_max", -6.0))
    lufs_integrated_min = float(metrics.get("lufs_integrated_min", -26.0))
    lufs_integrated_max = float(metrics.get("lufs_integrated_max", -20.0))

    # Target de pico: por defecto, el techo del rango
    mixbus_peak_target_dbfs = float(
        metrics.get("mixbus_peak_target_dbfs", peak_dbfs_max)
    )

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "mixbus_peak_target_dbfs": mixbus_peak_target_dbfs,
            "mixbus_peak_dbfs_measured": mixbus_peak_dbfs_measured,
            "mixbus_lufs_integrated_measured": mixbus_lufs_integrated_measured,
            "peak_dbfs_min": peak_dbfs_min,
            "peak_dbfs_max": peak_dbfs_max,
            "lufs_integrated_min": lufs_integrated_min,
            "lufs_integrated_max": lufs_integrated_max,
        },
        "stems": [
            {
                "file_name": p.name,
                "file_path": str(p),
            }
            for p in stem_files
        ],
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    print(f"[S1_MIXBUS_HEADROOM] Análisis completado. JSON guardado en: {output_path}")


if __name__ == "__main__":
    main()
