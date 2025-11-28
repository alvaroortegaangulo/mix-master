# C:\mix-master\backend\src\stages\S2_GROUP_PHASE_DRUMS.py

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
from utils.phase_utils import apply_time_shift_samples  # noqa: E402


def load_analysis(contract_id: str) -> Dict[str, Any]:
    """
    Carga el JSON de análisis generado por analysis\\S2_GROUP_PHASE_DRUMS.py.
    """
    temp_dir = PROJECT_ROOT / "temp" / contract_id
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data


# -------------------------------------------------------------------
# Worker para ProcessPoolExecutor
# -------------------------------------------------------------------
def _process_stem_worker(
    args: Tuple[str, Dict[str, Any], float]
) -> bool:
    """
    Worker que aplica alineación de fase/tiempo y posible flip de polaridad
    a un único stem de familia Drums (excepto la referencia).

    Devuelve True si el stem ha sido procesado, False en caso contrario.
    """
    temp_dir_str, stem_info, min_shift_ms = args
    temp_dir = Path(temp_dir_str)

    if not stem_info.get("in_family", False):
        return False
    if stem_info.get("is_reference", False):
        return False

    file_name = stem_info.get("file_name")
    if not file_name:
        return False

    file_path = temp_dir / file_name

    lag_samples = stem_info.get("lag_samples", 0.0)
    lag_ms = stem_info.get("lag_ms", 0.0)
    use_flip = bool(stem_info.get("use_polarity_flip", False))

    # Si el lag calculado es muy pequeño y no hay flip, no tocamos (para idempotencia)
    if abs(lag_ms) < min_shift_ms and not use_flip:
        return False

    data, sr = sf.read(file_path, always_2d=False)

    if not isinstance(data, np.ndarray):
        data = np.array(data, dtype=np.float32)
    else:
        data = data.astype(np.float32)

    if data.size == 0:
        return False

    # El análisis da el lag "medido"; para corregirlo lo aplicamos con signo contrario
    lag_samples_from_analysis = float(lag_samples)
    shift_samples = -int(round(lag_samples_from_analysis))

    shifted = apply_time_shift_samples(data, shift_samples)

    # Aplicar flip de polaridad si procede
    if use_flip:
        shifted = -shifted

    sf.write(file_path, shifted, sr)

    print(
        f"[S2_GROUP_PHASE_DRUMS] {file_name}: "
        f"lag_aplicado={shift_samples} samples ({-lag_ms:.3f} ms aprox), flip={use_flip}"
    )

    return True


def main() -> None:
    """
    Stage S2_GROUP_PHASE_DRUMS:
      - Lee analysis_S2_GROUP_PHASE_DRUMS.json.
      - Aplica alineación de fase/tiempo y posible flip de polaridad
        a los stems de familia Drums (excepto la referencia).
      - Sobrescribe los archivos .wav correspondientes, procesando en paralelo.
    """
    if len(sys.argv) < 2:
        print("Uso: python S2_GROUP_PHASE_DRUMS.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S2_GROUP_PHASE_DRUMS"

    analysis = load_analysis(contract_id)

    session: Dict[str, Any] = analysis.get("session", {})
    stems: List[Dict[str, Any]] = analysis.get("stems", [])

    max_time_shift_ms = float(session.get("max_time_shift_ms", 2.0))
    reference_name = session.get("reference_stem_name")

    # Umbral mínimo para no mover más si ya está prácticamente alineado
    MIN_SHIFT_MS = 0.1

    temp_dir = PROJECT_ROOT / "temp" / contract_id

    # Preparamos lista de stems candidatos (familia Drums no referencia)
    candidate_stems: List[Dict[str, Any]] = [
        s
        for s in stems
        if s.get("in_family", False) and not s.get("is_reference", False)
    ]

    processed = 0
    if candidate_stems:
        max_workers = min(4, os.cpu_count() or 1)
        args_list: List[Tuple[str, Dict[str, Any], float]] = [
            (str(temp_dir), stem_info, MIN_SHIFT_MS)
            for stem_info in candidate_stems
        ]

        with ProcessPoolExecutor(max_workers=max_workers) as ex:
            results = list(ex.map(_process_stem_worker, args_list))

        processed = sum(1 for r in results if r)

    print(
        f"[S2_GROUP_PHASE_DRUMS] Stage completado. "
        f"Referencia={reference_name}, stems procesados={processed}."
    )


if __name__ == "__main__":
    main()
