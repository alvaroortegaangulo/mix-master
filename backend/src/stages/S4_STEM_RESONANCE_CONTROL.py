# C:\mix-master\backend\src\stages\S4_STEM_RESONANCE_CONTROL.py

from __future__ import annotations

import sys
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Dict, Any, List, Tuple

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from utils.analysis_utils import get_temp_dir
from utils.resonance_utils import apply_resonance_cuts  # noqa: E402


def load_analysis(contract_id: str) -> Dict[str, Any]:
    """
    Carga el JSON de análisis generado por analysis\\S4_STEM_RESONANCE_CONTROL.py.
    """
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def _build_notches_for_stem(
    stem: Dict[str, Any],
    max_res_peak_db: float,
    max_cuts_db: float,
    max_filters_per_band: int,
) -> List[Dict[str, float]]:
    """
    A partir de la info de resonancias de un stem, construye la lista de notches
    (freq_hz, cut_db) ya filtrada y limitada.

    Se ejecuta en el proceso padre para evitar pasar 'stem' completo
    a los workers.
    """
    resonances = stem.get("resonances", []) or []
    if not resonances:
        return []

    # Ordenar resonancias por severidad (gain_above_local_db descendente)
    resonances_sorted = sorted(
        resonances,
        key=lambda r: float(r.get("gain_above_local_db", 0.0)),
        reverse=True,
    )

    notches: List[Dict[str, float]] = []

    for res in resonances_sorted:
        if len(notches) >= max_filters_per_band:
            break

        try:
            gain_above = float(res.get("gain_above_local_db", 0.0))
            freq_hz = float(res.get("freq_hz", 0.0))
        except (TypeError, ValueError):
            continue

        if freq_hz <= 0.0:
            continue

        # Exceso sobre el umbral permitido
        excess_db = gain_above - max_res_peak_db
        if excess_db <= 0.0:
            continue

        cut_db = min(excess_db, max_cuts_db)
        if cut_db <= 0.0:
            continue

        notches.append(
            {
                "freq_hz": freq_hz,
                "cut_db": cut_db,
            }
        )

    return notches


# --------------------------------------------------------------------
# Worker para ProcessPoolExecutor
# --------------------------------------------------------------------


def _process_stem_worker(
    args: Tuple[str, str, List[Dict[str, float]]]
) -> Tuple[str, int]:
    """
    Aplica los cortes de resonancia a un stem concreto.

    args:
      - temp_dir_str: carpeta temporal del contrato
      - file_name: nombre del stem
      - notches: lista de dicts {"freq_hz": float, "cut_db": float}

    Devuelve:
      (file_name, num_notches_aplicadas)
    """
    temp_dir_str, fname, notches = args

    if not fname or not notches:
        return fname or "", 0

    temp_dir = Path(temp_dir_str)
    path = temp_dir / fname
    if not path.exists():
        return fname, 0

    try:
        data, sr = sf.read(path, always_2d=False)

        if not isinstance(data, np.ndarray):
            data = np.array(data, dtype=np.float32)
        else:
            data = data.astype(np.float32)

        if data.size == 0:
            return fname, 0

        data_filt = apply_resonance_cuts(data, sr, notches)
        sf.write(path, data_filt, sr)

        notch_str = ", ".join(
            f"{n['freq_hz']:.0f}Hz/{n['cut_db']:.1f}dB" for n in notches
        )
        print(
            f"[S4_STEM_RESONANCE_CONTROL] {fname}: aplicadas {len(notches)} notches "
            f"({notch_str})."
        )

        return fname, len(notches)

    except Exception as e:
        print(f"[S4_STEM_RESONANCE_CONTROL] Error procesando {fname}: {e}")
        return fname, 0


def main() -> None:
    """
    Stage S4_STEM_RESONANCE_CONTROL:

      - Lee analysis_S4_STEM_RESONANCE_CONTROL.json.
      - Para cada stem, calcula cortes por resonancia y aplica notches en frecuencia.
      - Respeta:
          * max_resonance_peak_db_above_local (umbral de "aceptable").
          * max_resonant_cuts_db (corte máx. por resonancia).
          * max_resonant_filters_per_band (máx. resonancias aplicadas por stem).
      - Usa ProcessPoolExecutor para procesar stems en paralelo.
    """
    if len(sys.argv) < 2:
        print("Uso: python S4_STEM_RESONANCE_CONTROL.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S4_STEM_RESONANCE_CONTROL"

    analysis = load_analysis(contract_id)

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}
    stems: List[Dict[str, Any]] = analysis.get("stems", []) or []

    max_res_peak_db = float(metrics.get("max_resonance_peak_db_above_local", 12.0))
    max_cuts_db = float(limits.get("max_resonant_cuts_db", 8.0))
    max_filters_per_band = int(limits.get("max_resonant_filters_per_band", 3))

    temp_dir = get_temp_dir(contract_id, create=False)
    temp_dir_str = str(temp_dir)

    # Preparar tareas solo para stems que tengan notches efectivos
    tasks: List[Tuple[str, str, List[Dict[str, float]]]] = []

    for stem in stems:
        fname = stem.get("file_name")
        if not fname:
            continue

        resonances = stem.get("resonances", []) or []
        if not resonances:
            continue

        notches = _build_notches_for_stem(
            stem=stem,
            max_res_peak_db=max_res_peak_db,
            max_cuts_db=max_cuts_db,
            max_filters_per_band=max_filters_per_band,
        )
        if not notches:
            continue

        tasks.append((temp_dir_str, fname, notches))

    if not tasks:
        print(
            "[S4_STEM_RESONANCE_CONTROL] No hay stems con resonancias a procesar. "
            "Stage completado sin cambios."
        )
        return

    stems_touched = 0
    total_notches_applied = 0

    # Utiliza todos los cores disponibles, pero no más que el número de tareas
    cpu_count = os.cpu_count() or 1
    max_workers = min(cpu_count, len(tasks))

    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        for fname, num_notches in ex.map(_process_stem_worker, tasks):
            if num_notches > 0:
                stems_touched += 1
                total_notches_applied += num_notches

    print(
        f"[S4_STEM_RESONANCE_CONTROL] Stage completado. "
        f"stems procesados={stems_touched}, notches totales={total_notches_applied}."
    )


if __name__ == "__main__":
    main()
