# C:\mix-master\backend\src\stages\S1_STEM_WORKING_LOUDNESS.py

from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any, List

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import os  # noqa: E402

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from utils.analysis_utils import get_temp_dir
from utils.profiles_utils import get_instrument_profile  # noqa: E402


def load_analysis(contract_id: str) -> Dict[str, Any]:
    """
    Carga el JSON de análisis generado por analysis\\S1_STEM_WORKING_LOUDNESS.py.
    """
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def compute_gain_db_for_stem(
    stem_info: Dict[str, Any],
    true_peak_target_dbtp: float | None,
    max_gain_change_db_per_pass: float | None,
) -> float:
    """
    Calcula la ganancia en dB a aplicar a un stem concreto:

      1) Usa instrument_profile_resolved para obtener work_loudness_lufs_range.
      2) Target = punto medio del rango.
      3) gain_db = target_lufs - integrated_lufs_medida.
      4) Limita |gain_db| por max_gain_change_db_per_pass si existe.
      5) (Opcional) Comprueba que el nuevo true peak no supere true_peak_target_dbtp.
         (por ahora no se aplica recorte adicional, solo se deja el parámetro previsto).
    """
    inst_profile_id = stem_info.get("instrument_profile_resolved", "Other")
    profile = get_instrument_profile(inst_profile_id)
    lufs_range = profile.get("work_loudness_lufs_range")

    integrated_lufs = stem_info.get("integrated_lufs")
    measured_peak_dbfs = stem_info.get("true_peak_dbfs")

    if integrated_lufs is None or integrated_lufs == float("-inf"):
        return 0.0
    if measured_peak_dbfs is None or measured_peak_dbfs == float("-inf"):
        measured_peak_dbfs = -120.0

    # Si no hay rango definido, no tocamos
    if not isinstance(lufs_range, list) or len(lufs_range) != 2:
        return 0.0

    target_min, target_max = float(lufs_range[0]), float(lufs_range[1])
    target_lufs = 0.5 * (target_min + target_max)

    gain_db = target_lufs - float(integrated_lufs)

    # Limitar por max_gain_change_db_per_pass
    if max_gain_change_db_per_pass is not None:
        max_gain = float(max_gain_change_db_per_pass)
        if gain_db > max_gain:
            gain_db = max_gain
        elif gain_db < -max_gain:
            gain_db = -max_gain

    # Pequeños cambios (p.ej. < 0.1 dB) los ignoramos para evitar ruido innecesario
    if abs(gain_db) < 0.1:
        return 0.0

    return gain_db


def apply_gain_to_stem(file_path: Path, gain_db: float) -> None:
    """
    Aplica la ganancia en dB al stem y sobrescribe el archivo.
    """
    data, sr = sf.read(file_path, always_2d=False)

    if not isinstance(data, np.ndarray):
        data = np.array(data, dtype=np.float32)
    else:
        data = data.astype(np.float32)

    if data.size == 0 or gain_db == 0.0:
        return

    scale = 10.0 ** (gain_db / 20.0)
    data_out = data * scale

    sf.write(file_path, data_out, sr)


# -------------------------------------------------------------------
# -------------------------------------------------------------------
def _process_stem_worker(
    args: tuple[Dict[str, Any], float | None, float | None]
) -> None:
    """
    Worker que calcula la ganancia para un stem y la aplica.
    Pensado para ejecutarse en procesos hijos.
    """
    stem_info, true_peak_target_dbtp, max_gain_change_db_per_pass = args
    file_path = Path(stem_info["file_path"])

    gain_db = compute_gain_db_for_stem(
        stem_info,
        true_peak_target_dbtp=true_peak_target_dbtp,
        max_gain_change_db_per_pass=max_gain_change_db_per_pass,
    )

    if gain_db != 0.0:
        apply_gain_to_stem(file_path, gain_db)


def main() -> None:
    """
    Stage S1_STEM_WORKING_LOUDNESS:
      - Lee analysis_S1_STEM_WORKING_LOUDNESS.json.
      - Calcula la ganancia por stem según instrument_profile y objetivos de trabajo.
      - Aplica la ganancia y sobrescribe los stems (en paralelo por archivo).
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S1_STEM_WORKING_LOUDNESS.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S1_STEM_WORKING_LOUDNESS"

    analysis = load_analysis(contract_id)

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {})
    session_metrics: Dict[str, Any] = analysis.get("session", {})
    stems: List[Dict[str, Any]] = analysis.get("stems", [])

    # Targets desde análisis/contrato
    true_peak_target_dbtp = session_metrics.get(
        "true_peak_per_stem_target_max_dbtp", -3.0
    )
    max_gain_change_db_per_pass = metrics.get("max_gain_change_db_per_pass", None)

    if stems:
        max_workers = min(4, os.cpu_count() or 1)
        args_list: List[tuple[Dict[str, Any], float | None, float | None]] = [
            (stem_info, true_peak_target_dbtp, max_gain_change_db_per_pass)
            for stem_info in stems
        ]

        for args in args_list:
            _process_stem_worker(args)

    logger.logger.info(
        f"[S1_STEM_WORKING_LOUDNESS] Normalización de trabajo completada para {len(stems)} stems."
    )


if __name__ == "__main__":
    main()
