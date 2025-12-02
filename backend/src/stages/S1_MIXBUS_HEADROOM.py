# C:\mix-master\backend\src\stages\S1_MIXBUS_HEADROOM.py

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import os  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from utils.analysis_utils import get_temp_dir


def load_analysis(contract_id: str) -> Dict[str, Any]:
    """
    Carga el JSON de análisis generado por analysis\\S1_MIXBUS_HEADROOM.py.
    """
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def compute_global_gain_db(analysis: Dict[str, Any]) -> float:
    """
    Calcula la ganancia global en dB a aplicar a todos los stems.

    Nuevo comportamiento más "musical":

      - Se apoya en metrics.peak_dbfs_min / peak_dbfs_max del contrato.
      - Solo atenuamos si el pico de mixbus supera peak_dbfs_max.
      - No subimos mezclas que ya estén por debajo del rango.
      - Respetamos limits.max_gain_change_db_per_pass cuando exista.
    """
    session: Dict[str, Any] = analysis.get("session", {}) or {}
    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}

    mix_peak_measured = session.get("mixbus_peak_dbfs_measured")
    if mix_peak_measured is None:
        return 0.0

    try:
        mix_peak_measured = float(mix_peak_measured)
    except (TypeError, ValueError):
        return 0.0

    # Si no hay mezcla real (silencio), no hacemos nada
    if mix_peak_measured == float("-inf"):
        return 0.0

    peak_dbfs_min = float(metrics.get("peak_dbfs_min", -12.0))
    peak_dbfs_max = float(metrics.get("peak_dbfs_max", -6.0))

    # Filosofía: SOLO atenuar si estamos por encima del techo permitido.
    # Si ya estamos por debajo o dentro del rango, no tocamos nada.
    if mix_peak_measured <= peak_dbfs_max:
        return 0.0

    # Queremos llevar el pico hasta el techo del rango
    target_dbfs = peak_dbfs_max
    gain_db = target_dbfs - mix_peak_measured  # será negativo (atenuar)

    # Respetar max_gain_change_db_per_pass si se ha definido
    max_change = float(limits.get("max_gain_change_db_per_pass", 3.0))
    max_change = abs(max_change)

    if gain_db < -max_change:
        gain_db = -max_change

    # Ignoramos cambios ridículos
    if abs(gain_db) < 0.1:
        return 0.0

    return gain_db



# ---------------------------------------------------------------------
# Worker para ProcessPoolExecutor: aplica ganancia a un solo stem
# ---------------------------------------------------------------------
def _apply_gain_worker(args: Tuple[Dict[str, Any], float]) -> None:
    """
    Worker para aplicar la ganancia global a un único stem.
    Pensado para ejecutarse en procesos hijos.
    """
    stem_info, gain_db = args
    file_path = Path(stem_info["file_path"])

    data, sr = sf.read(file_path, always_2d=False)

    if not isinstance(data, np.ndarray):
        data = np.array(data, dtype=np.float32)
    else:
        data = data.astype(np.float32)

    if data.size == 0:
        return

    scale = 10.0 ** (gain_db / 20.0)
    data_out = data * scale
    sf.write(file_path, data_out, sr)


def apply_global_gain_to_stems(stems: List[Dict[str, Any]], gain_db: float) -> None:
    """
    Aplica la ganancia global en dB a todos los stems listados en el análisis.
    Usa ProcessPoolExecutor para paralelizar el procesado por archivo.
    """
    if not stems:
        return

    if abs(gain_db) < 0.1:
        # Cambios ridículos los ignoramos
        return

    max_workers = min(4, os.cpu_count() or 1)
    args_list = [(stem_info, gain_db) for stem_info in stems]

    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        list(ex.map(_apply_gain_worker, args_list))


def main() -> None:
    """
    Stage S1_MIXBUS_HEADROOM:
      - Lee analysis_S1_MIXBUS_HEADROOM.json.
      - Calcula una ganancia global para dejar el mixbus en un rango de headroom razonable.
      - Aplica esa ganancia a todos los stems y sobrescribe los archivos (en paralelo).
    """
    if len(sys.argv) < 2:
        print("Uso: python S1_MIXBUS_HEADROOM.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S1_MIXBUS_HEADROOM"

    analysis = load_analysis(contract_id)
    stems: List[Dict[str, Any]] = analysis.get("stems", [])

    gain_db = compute_global_gain_db(analysis)

    apply_global_gain_to_stems(stems, gain_db)

    print(
        f"[S1_MIXBUS_HEADROOM] Headroom ajustado con ganancia global de {gain_db:.2f} dB "
        f"para {len(stems)} stems."
    )



if __name__ == "__main__":
    main()
