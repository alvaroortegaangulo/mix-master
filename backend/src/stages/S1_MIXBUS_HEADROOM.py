# C:\mix-master\backend\src\stages\S1_MIXBUS_HEADROOM.py

from __future__ import annotations
from utils.logger import logger

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

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
from pedalboard import Pedalboard, Gain  # noqa: E402

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
      - Aplica pasos limitados por max_gain_change_db_per_pass hasta 8
        iteraciones, acumulando ganancia en dB (sin releer audio).
      - No sigue si dejaría LUFS por debajo de lufs_min (con margen), cuando hay métrica de LUFS.
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

    # Picos: obligatorios
    try:
        peak_dbfs_min = float(metrics["peak_dbfs_min"])
        peak_dbfs_max = float(metrics["peak_dbfs_max"])
    except Exception:
        logger.logger.info("[S1_MIXBUS_HEADROOM] Falta peak_dbfs_min/peak_dbfs_max en metrics; no se ajusta ganancia.")
        return 0.0

    # LUFS: opcionales (si no están, nos guiamos solo por pico)
    lufs_min_raw = metrics.get("lufs_integrated_min")
    lufs_max_raw = metrics.get("lufs_integrated_max")
    lufs_min = float(lufs_min_raw) if lufs_min_raw is not None else None
    lufs_max = float(lufs_max_raw) if lufs_max_raw is not None else None

    peak_tol = 0.2
    lufs_tol = 0.5
    target_peak = peak_dbfs_max - peak_tol
    target_lufs = lufs_max - lufs_tol if lufs_max is not None else None
    lufs_floor = lufs_min - lufs_tol if lufs_min is not None else None

    max_change = abs(float(limits.get("max_gain_change_db_per_pass", 3.0)))

    cur_peak = mix_peak_measured
    cur_lufs = lufs_measured
    total_gain = 0.0

    if cur_peak is None and cur_lufs is None:
        return 0.0

    # Iterar hasta cubrir excesos grandes (8 pasos de hasta 3 dB = 24 dB)
    for _ in range(8):
        gain_candidates: List[float] = []

        if cur_peak is not None and cur_peak != float("-inf"):
            if cur_peak > target_peak:
                gain_candidates.append(target_peak - cur_peak)

        if cur_lufs is not None and target_lufs is not None:
            if cur_lufs > target_lufs:
                gain_candidates.append(target_lufs - cur_lufs)

        if not gain_candidates:
            break

        step = min(gain_candidates)  # más negativo = más restrictivo

        if step < -max_change:
            step = -max_change

        if cur_lufs is not None and lufs_floor is not None:
            est_lufs_after = cur_lufs + step
            if est_lufs_after < lufs_floor:
                break

        total_gain += step

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
# Aplicación de ganancia con Pedalboard (pero IO con soundfile)
# ---------------------------------------------------------------------

def _apply_gain_worker(args: Tuple[Dict[str, Any], float]) -> None:
    """
    Worker para aplicar la ganancia global a un único stem.

    - Lee el archivo con soundfile.
    - Aplica Gain(gain_db) de Pedalboard en memoria.
    - Reescribe el archivo con soundfile.

    Pensado para ejecutarse en procesos hijos (aunque aquí se usa en serie).
    """
    stem_info, gain_db = args
    file_path = Path(stem_info["file_path"])

    # Si la ganancia es despreciable, salimos rápido
    if abs(gain_db) < 0.1:
        return

    try:
        data, sr = sf.read(file_path, always_2d=False)
    except Exception as e:
        logger.logger.info(f"[S1_MIXBUS_HEADROOM] Error leyendo stem {file_path}: {e}")
        return

    if not isinstance(data, np.ndarray):
        data = np.asarray(data, dtype=np.float32)
    else:
        data = data.astype(np.float32)

    if data.size == 0:
        logger.logger.info(f"[S1_MIXBUS_HEADROOM] {file_path.name}: archivo vacío; se omite.")
        return

    # Cadena de Pedalboard con un único Gain
    board = Pedalboard([Gain(gain_db=float(gain_db))])

    try:
        processed = board(data, sr)
    except Exception as e:
        logger.logger.info(f"[S1_MIXBUS_HEADROOM] Error aplicando Gain a {file_path}: {e}")
        return

    processed = np.asarray(processed, dtype=np.float32)

    # Reescribir archivo con el audio procesado
    try:
        sf.write(file_path, processed, sr)
    except Exception as e:
        logger.logger.info(f"[S1_MIXBUS_HEADROOM] Error escribiendo stem {file_path}: {e}")
        return


def apply_global_gain_to_stems(stems: List[Dict[str, Any]], gain_db: float) -> None:
    """
    Aplica la ganancia global en dB a todos los stems listados en el análisis.
    Procesa en serie para evitar multiproceso.
    """
    if not stems:
        return

    if abs(gain_db) < 0.1:
        return

    args_list = [(stem_info, gain_db) for stem_info in stems]
    for args in args_list:
        _apply_gain_worker(args)


def main() -> None:
    """
    Stage S1_MIXBUS_HEADROOM:
      - Lee analysis_S1_MIXBUS_HEADROOM.json.
      - Calcula una ganancia global para dejar el mixbus en un
        rango de headroom y loudness de trabajo razonables.
      - Aplica esa ganancia a todos los stems y sobrescribe los archivos.
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S1_MIXBUS_HEADROOM.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S1_MIXBUS_HEADROOM"

    analysis = load_analysis(contract_id)
    stems: List[Dict[str, Any]] = analysis.get("stems", []) or []

    gain_db = compute_global_gain_db(analysis)

    apply_global_gain_to_stems(stems, gain_db)

    logger.logger.info(
        f"[S1_MIXBUS_HEADROOM] Headroom ajustado con ganancia global de {gain_db:.2f} dB "
        f"para {len(stems)} stems."
    )


if __name__ == "__main__":
    main()
