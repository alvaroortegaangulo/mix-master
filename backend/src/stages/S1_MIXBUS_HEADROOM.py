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

    Comportamiento:

      - Usa metrics.peak_dbfs_min / peak_dbfs_max y
        metrics.lufs_integrated_min / lufs_integrated_max del contrato.
      - Solo ATENÚA (no sube nivel en este stage).
      - Atenúa si:
          * el pico de mixbus supera peak_dbfs_max, y/o
          * el loudness integrado supera lufs_integrated_max.
      - No atenúa si el loudness ya está por debajo de lufs_integrated_min
        para evitar dejar la mezcla "muerta".
      - Respeta limits.max_gain_change_db_per_pass cuando exista.
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

    if mix_peak_measured is None and lufs_measured is None:
        return 0.0

    peak_dbfs_min = float(metrics.get("peak_dbfs_min", -12.0))
    peak_dbfs_max = float(metrics.get("peak_dbfs_max", -6.0))
    lufs_min = float(metrics.get("lufs_integrated_min", -26.0))
    lufs_max = float(metrics.get("lufs_integrated_max", -20.0))

    # ---------------------------------------------------------------
    # 1) Candidatos de ganancia desde peak y desde LUFS (solo atenuar)
    # ---------------------------------------------------------------
    gain_peak = 0.0
    if mix_peak_measured is not None and mix_peak_measured != float("-inf"):
        if mix_peak_measured > peak_dbfs_max:
            # Pico por encima del techo => atenuamos
            gain_peak = peak_dbfs_max - mix_peak_measured  # negativo
        else:
            # Si el pico está dentro o por debajo del rango, no tocamos por peak
            gain_peak = 0.0

    gain_lufs = 0.0
    if lufs_measured is not None:
        if lufs_measured > lufs_max:
            # Loudness demasiado alto => atenuamos
            gain_lufs = lufs_max - lufs_measured  # negativo
        else:
            # Si el loudness está dentro o por debajo del rango de trabajo,
            # no atenuamos más SOLO por LUFS.
            gain_lufs = 0.0

    candidate_gains = [g for g in (gain_peak, gain_lufs) if g < 0.0]
    if not candidate_gains:
        # Nada que atenuar por peak/LUFS
        return 0.0

    # Ajuste más restrictivo (el que más atenuación pide)
    gain_db = min(candidate_gains)

    # ---------------------------------------------------------------
    # 2) Protección para no bajar por debajo del loudness mínimo
    #    (aproximación 1 dB ≈ 1 LU)
    # ---------------------------------------------------------------
    if lufs_measured is not None:
        approx_lufs_after = lufs_measured + gain_db
        if approx_lufs_after < lufs_min:
            # Si esta atenuación nos dejaría por debajo del mínimo de LUFS de trabajo,
            # preferimos NO atenuar más en este stage.
            return 0.0

    # ---------------------------------------------------------------
    # 3) Respetar max_gain_change_db_per_pass
    # ---------------------------------------------------------------
    max_change = float(limits.get("max_gain_change_db_per_pass", 3.0))
    max_change = abs(max_change)

    if gain_db < -max_change:
        gain_db = -max_change

    # Ignorar cambios ridículos
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
