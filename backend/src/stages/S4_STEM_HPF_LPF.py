# C:\mix-master\backend\src\stages\S4_STEM_HPF_LPF.py

from __future__ import annotations

import sys
import os
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
from utils.filter_utils import apply_hpf_lpf  # noqa: E402


def load_analysis(contract_id: str) -> Dict[str, Any]:
    """
    Carga el JSON de análisis generado por analysis\\S4_STEM_HPF_LPF.py.
    """
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data


# --------------------------------------------------------------------
# --------------------------------------------------------------------

def _process_stem_worker(args: Tuple[str, Dict[str, Any], float, float]) -> Tuple[str, bool]:
    """
    Aplica HPF/LPF a un stem concreto.

    args:
      - contract_id
      - stem (dict con info del análisis)
      - max_hpf_step (no usado en esta versión minimalista, reservado)
      - max_lpf_step (no usado en esta versión minimalista, reservado)

    Devuelve (file_name, ok).
    """
    contract_id, stem, max_hpf_step, max_lpf_step = args  # noqa: F841 (por ahora no usamos los *step)

    fname = stem.get("file_name")
    if not fname:
        return "", False

    temp_dir = get_temp_dir(contract_id, create=False)
    path = temp_dir / fname
    if not path.exists():
        return fname, False

    hpf_target = stem.get("hpf_target_hz")
    lpf_target = stem.get("lpf_target_hz")

    # Valores por defecto si vinieran a None
    hpf = float(hpf_target) if hpf_target is not None else 20.0
    lpf = float(lpf_target) if lpf_target is not None else 20000.0

    # Clamp global por seguridad (misma lógica que la versión secuencial)
    if hpf < 0.0:
        hpf = 0.0
    if hpf > 1000.0:
        hpf = 1000.0
    if lpf < 2000.0:
        lpf = 2000.0

    try:
        data, sr = sf.read(path, always_2d=False)

        if not isinstance(data, np.ndarray):
            data = np.array(data, dtype=np.float32)
        else:
            data = data.astype(np.float32)

        if data.size == 0:
            return fname, False

        data_filt = apply_hpf_lpf(data, sr, hpf_hz=hpf, lpf_hz=lpf)
        sf.write(path, data_filt, sr)

        print(
            f"[S4_STEM_HPF_LPF] {fname}: aplicado HPF={hpf:.1f} Hz, LPF={lpf:.1f} Hz."
        )
        return fname, True

    except Exception as e:
        print(f"[S4_STEM_HPF_LPF] Error procesando {fname}: {e}")
        return fname, False


def main() -> None:
    """
    Stage S4_STEM_HPF_LPF:

      - Lee analysis_S4_STEM_HPF_LPF.json.
      - Aplica HPF/LPF por stem según instrument_profile.
    """
    if len(sys.argv) < 2:
        print("Uso: python S4_STEM_HPF_LPF.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S4_STEM_HPF_LPF"

    analysis = load_analysis(contract_id)

    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}
    stems: List[Dict[str, Any]] = analysis.get("stems", []) or []

    max_hpf_step = float(limits.get("max_hpf_change_hz_per_pass", 40.0))
    max_lpf_step = float(limits.get("max_lpf_change_hz_per_pass", 4000.0))

    # Preparar tareas para los stems válidos
    tasks: List[Tuple[str, Dict[str, Any], float, float]] = []
    for stem in stems:
        fname = stem.get("file_name")
        if not fname:
            continue
        tasks.append((contract_id, stem, max_hpf_step, max_lpf_step))

    if not tasks:
        print("[S4_STEM_HPF_LPF] No hay stems a procesar.")
        return

    processed = 0

    for fname, ok in map(_process_stem_worker, tasks):
        if ok:
            processed += 1

    print(
        f"[S4_STEM_HPF_LPF] Stage completado. Stems procesados={processed}."
    )


if __name__ == "__main__":
    main()
