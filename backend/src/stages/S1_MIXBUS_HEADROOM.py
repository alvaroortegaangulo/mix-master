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

from utils.analysis_utils import PROJECT_ROOT  # noqa: E402


def load_analysis(contract_id: str) -> Dict[str, Any]:
    """
    Carga el JSON de análisis generado por analysis\\S1_MIXBUS_HEADROOM.py.
    """
    temp_dir = PROJECT_ROOT / "temp" / contract_id
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def compute_global_gain_db(session: Dict[str, Any]) -> float:
    """
    Calcula la ganancia global en dB a aplicar a todos los stems:

      gain_db = mixbus_peak_target_dbfs - mixbus_peak_dbfs_measured

    - Solo se atenúa (si el mix ya está por debajo del target, no se sube).
    - Se puede limitar por max_gain_change_db_per_pass si está en limits.
    """
    mix_peak_target = session.get("mixbus_peak_target_dbfs")
    mix_peak_measured = session.get("mixbus_peak_dbfs_measured")

    if mix_peak_target is None or mix_peak_measured is None:
        return 0.0

    mix_peak_target = float(mix_peak_target)
    mix_peak_measured = float(mix_peak_measured)

    # Si no hay mezcla (o es silencio), no hacemos nada
    if mix_peak_measured == float("-inf"):
        return 0.0

    gain_db = mix_peak_target - mix_peak_measured  # suele ser negativo (atenuar)

    # Si el mix ya está más bajo que el target (más headroom), no lo subimos
    if gain_db >= 0.0:
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
      - Calcula una ganancia global para dejar el mixbus en el headroom objetivo.
      - Aplica esa ganancia a todos los stems y sobrescribe los archivos (en paralelo).
    """
    if len(sys.argv) < 2:
        print("Uso: python S1_MIXBUS_HEADROOM.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S1_MIXBUS_HEADROOM"

    analysis = load_analysis(contract_id)

    session: Dict[str, Any] = analysis.get("session", {})
    stems: List[Dict[str, Any]] = analysis.get("stems", [])

    gain_db = compute_global_gain_db(session)

    apply_global_gain_to_stems(stems, gain_db)

    print(
        f"[S1_MIXBUS_HEADROOM] Headroom ajustado con ganancia global de {gain_db:.2f} dB "
        f"para {len(stems)} stems."
    )


if __name__ == "__main__":
    main()
