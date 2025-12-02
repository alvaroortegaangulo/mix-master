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

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from utils.analysis_utils import get_temp_dir
from utils.phase_utils import apply_time_shift_samples  # noqa: E402


def load_analysis(contract_id: str) -> Dict[str, Any]:
    """
    Carga el JSON de análisis generado por analysis\\S2_GROUP_PHASE_DRUMS.py.
    """
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data


# -------------------------------------------------------------------
# -------------------------------------------------------------------
def _process_stem_worker(
    args: Tuple[str, Dict[str, Any], float]
) -> bool:
    """
    Aplica alineación de fase/tiempo y posible flip de polaridad
    a un único stem de familia Drums (excepto la referencia).

    Convención (coherente con utils.phase_utils.estimate_best_lag_and_corr):

      - El análisis devuelve 'lag_samples' TAL Y COMO SE MIDE:
          lag > 0  => el candidato está retrasado respecto a la referencia.
          lag < 0  => el candidato está adelantado.

      - Para corregirlo, debemos aplicar un shift de signo opuesto:
          shift_samples = -lag_samples

      - apply_time_shift_samples implementa:
          new_y[n] = y[n - lag_samples]

        de forma que:
          * lag_samples > 0 desplaza el audio hacia ADELANTE (más tarde).
          * lag_samples < 0 desplaza el audio hacia ATRÁS (antes).

    Devuelve True si el stem ha sido procesado, False en caso contrario.
    """
    temp_dir_str, stem_info, min_shift_ms = args
    temp_dir = Path(temp_dir_str)

    # Solo procesamos stems de familia Drums que no son referencia
    if not stem_info.get("in_family", False):
        return False
    if stem_info.get("is_reference", False):
        return False

    file_name = stem_info.get("file_name")
    if not file_name:
        return False

    file_path = temp_dir / file_name
    if not file_path.exists():
        return False

    # Datos del análisis
    lag_samples = stem_info.get("lag_samples", 0.0)
    lag_ms = stem_info.get("lag_ms", 0.0)
    use_flip = bool(stem_info.get("use_polarity_flip", False))

    try:
        lag_ms = float(lag_ms)
        lag_samples = float(lag_samples)
    except (TypeError, ValueError):
        return False

    # Para evitar micro-ajustes ridículos y mantener idempotencia:
    # si el lag es muy pequeño y no hay flip, no tocamos.
    if abs(lag_ms) < min_shift_ms and not use_flip:
        return False

    # Leer audio
    data, sr = sf.read(file_path, always_2d=False)
    if not isinstance(data, np.ndarray):
        data = np.array(data, dtype=np.float32)
    else:
        data = data.astype(np.float32)

    if data.size == 0:
        return False

    # Shift a aplicar ES EL OPUESTO del lag medido
    shift_samples = -int(round(lag_samples))
    shift_ms = -lag_ms  # mismo cálculo conceptual, solo para log

    # Aplicar shift temporal
    shifted = apply_time_shift_samples(data, shift_samples)

    # Flip de polaridad si procede
    if use_flip:
        shifted = -shifted

    sf.write(file_path, shifted, sr)

    print(
        f"[S2_GROUP_PHASE_DRUMS] {file_name}: "
        f"lag_inicial={lag_ms:.3f} ms, "
        f"shift_aplicado={shift_samples} samples ({shift_ms:.3f} ms aprox), "
        f"flip={use_flip}"
    )

    return True


def main() -> None:
    """
    Stage S2_GROUP_PHASE_DRUMS:
      - Lee analysis_S2_GROUP_PHASE_DRUMS.json.
      - Aplica alineación de fase/tiempo y posible flip de polaridad
        a los stems de familia Drums (excepto la referencia).
      - Sobrescribe los archivos .wav correspondientes, procesando en serie.
    """
    if len(sys.argv) < 2:
        print("Uso: python S2_GROUP_PHASE_DRUMS.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S2_GROUP_PHASE_DRUMS"

    analysis = load_analysis(contract_id)

    session: Dict[str, Any] = analysis.get("session", {}) or {}
    stems: List[Dict[str, Any]] = analysis.get("stems", []) or []

    reference_name = session.get("reference_stem_name")

    # Umbral mínimo en ms para no mover si ya está prácticamente alineado
    # (esto SOLO se usa para decidir si aplicamos shift, no se usa en el análisis).
    MIN_SHIFT_MS = 0.1

    temp_dir = get_temp_dir(contract_id, create=False)

    # Stems candidatos: Drums no referencia
    candidate_stems: List[Dict[str, Any]] = [
        s
        for s in stems
        if s.get("in_family", False) and not s.get("is_reference", False)
    ]

    processed = 0
    if candidate_stems:
        args_list: List[Tuple[str, Dict[str, Any], float]] = [
            (str(temp_dir), stem_info, MIN_SHIFT_MS)
            for stem_info in candidate_stems
        ]

        # Procesamos en serie para mantenerlo simple y estable
        for args in args_list:
            if _process_stem_worker(args):
                processed += 1

    print(
        f"[S2_GROUP_PHASE_DRUMS] Stage completado. "
        f"Referencia={reference_name}, stems procesados={processed}."
    )


if __name__ == "__main__":
    main()
