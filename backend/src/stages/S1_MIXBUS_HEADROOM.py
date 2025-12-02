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

from utils.analysis_utils import get_temp_dir  # noqa: E402


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

    Estrategia:
      - Solo atenuar.
      - Objetivo con colchón: peak <= peak_dbfs_max - peak_tol y
        LUFS <= lufs_integrated_max - lufs_tol (absorbe el margen del check).
      - Aplica pasos limitados por max_gain_change_db_per_pass hasta 3
        iteraciones, acumulando ganancia en dB (sin releer audio).
      - No sigue si dejaría LUFS por debajo de lufs_min (con margen).
    """
    session: Dict[str, Any] = analysis.get("session", {}) or {}
    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}

    mix_peak_measured = session.get("mixbus_peak_dbfs_measured")
    lufs_measured = session.get("mixbus_lufs_integrated_measured")

    try:
        mix_peak_measured = float(mix_peak_measured)
    except (TypeError, ValueError):
        mix_peak_measured = None

    try:
        lufs_measured = float(lufs_measured) if lufs_measured is not None else None
    except (TypeError, ValueError):
        lufs_measured = None

    peak_dbfs_min = float(metrics.get("peak_dbfs_min", -12.0))
    peak_dbfs_max = float(metrics.get("peak_dbfs_max", -6.0))
    lufs_min = float(metrics.get("lufs_integrated_min", -26.0))
    lufs_max = float(metrics.get("lufs_integrated_max", -20.0))

    peak_tol = 0.2
    lufs_tol = 0.5
    target_peak = peak_dbfs_max - peak_tol
    target_lufs = lufs_max - lufs_tol
    lufs_floor = lufs_min - lufs_tol

    max_change = abs(float(limits.get("max_gain_change_db_per_pass", 3.0)))

    cur_peak = mix_peak_measured
    cur_lufs = lufs_measured
    total_gain = 0.0

    # Sin métricas fiables, no hacemos nada
    if cur_peak is None and cur_lufs is None:
        return 0.0

    # Hasta 3 iteraciones para acercarnos al objetivo
    for _ in range(3):
        gain_candidates: List[float] = []

        if cur_peak is not None and cur_peak != float("-inf"):
            if cur_peak > target_peak:
                gain_candidates.append(target_peak - cur_peak)

        if cur_lufs is not None:
            if cur_lufs > target_lufs:
                gain_candidates.append(target_lufs - cur_lufs)

        if not gain_candidates:
            break

        step = min(gain_candidates)  # más negativo = más restrictivo

        # Limitar por max_gain_change_db_per_pass
        if step < -max_change:
            step = -max_change

        # Evitar dejar LUFS por debajo del mínimo permitido
        if cur_lufs is not None:
            est_lufs_after = cur_lufs + step
            if est_lufs_after < lufs_floor:
                break

        total_gain += step

        # Actualizar estimaciones (aprox lineal en dB)
        if cur_peak is not None and cur_peak != float("-inf"):
            cur_peak += step
        if cur_lufs is not None:
            cur_lufs += step

        if abs(step) < 0.1:
            break

    if abs(total_gain) < 0.1:
        return 0.0
    return total_gain


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
        # Cambios pequeños no compensan el coste de reescribir
        return

    max_workers = min(4, os.cpu_count() or 1)
    args_list = [(stem_info, gain_db) for stem_info in stems]

    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        list(ex.map(_apply_gain_worker, args_list))


def main() -> None:
    """
    Stage S1_MIXBUS_HEADROOM:
      - Lee analysis_S1_MIXBUS_HEADROOM.json.
      - Calcula una ganancia global para dejar el mixbus en un
        rango de headroom y loudness de trabajo razonables.
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
