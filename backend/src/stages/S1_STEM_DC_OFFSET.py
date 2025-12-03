import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Añadir .../src al sys.path para poder hacer "from utils ..."
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from stages.pipeline_context import PipelineContext

import json
import os

import numpy as np
import soundfile as sf

from utils.analysis_utils import get_temp_dir


def load_analysis(contract_id: str) -> Dict[str, Any]:
    """
    Carga el JSON de análisis generado por analysis\\S1_STEM_DC_OFFSET.py.
    Ruta esperada:
        <PROJECT_ROOT>/temp/<contract_id>/analysis_<contract_id>.json
    """
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def process_stem(
    stem_info: Dict[str, Any],
    dc_offset_max_db_target: float | None,
) -> None:
    """
    Corrige el DC offset de un stem si supera el umbral del contrato.

    Estrategia minimalista:
      - Usamos dc_offset_linear ya calculado en el análisis (mono promedio).
      - Si dc_offset_db > dc_offset_max_db_target (por ejemplo -40 dB > -60 dB),
        consideramos que hace falta corrección.
      - Restamos dc_offset_linear a todas las muestras de todos los canales.
    """
    file_path = Path(stem_info["file_path"])
    dc_linear = float(stem_info.get("dc_offset_linear", 0.0))
    dc_db = float(stem_info.get("dc_offset_db", -120.0))

    # Si no hay objetivo, corregimos siempre; si lo hay, solo si se excede
    need_correction = False
    if dc_offset_max_db_target is None:
        need_correction = True
    else:
        # Ambos suelen ser negativos, p.ej. target -60 dB, medido -40 dB.
        # Si el medido es "menos negativo" (más cercano a 0), es peor.
        need_correction = dc_db > dc_offset_max_db_target

    if not need_correction:
        return

    # Leer el audio completo en multicanal
    data, sr = sf.read(file_path, always_2d=True)

    if not isinstance(data, np.ndarray):
        data = np.array(data, dtype=np.float32)
    else:
        data = data.astype(np.float32)

    if data.size == 0:
        return

    # Restar el offset (mismo valor en todos los canales; suficiente y estable)
    data_corrected = data - dc_linear

    # Sobrescribir el archivo (manteniendo samplerate, formato por defecto)
    sf.write(file_path, data_corrected, sr)


# -------------------------------------------------------------------
# -------------------------------------------------------------------
def _process_stem_worker(args: Tuple[Dict[str, Any], float | None]) -> None:
    """
    Wrapper para ejecutar process_stem en un proceso hijo.
    """
    stem_info, dc_offset_max_db_target = args
    process_stem(stem_info, dc_offset_max_db_target)


def process(context: PipelineContext) -> None:
    """
    Stage S1_STEM_DC_OFFSET:
      - Lee analysis_S1_STEM_DC_OFFSET.json.
      - Corrige el DC offset de cada stem que incumple el contrato.
      - Sobrescribe los stems in-place en temp/<contract_id>/ (en paralelo).
    """

    contract_id = context.contract_id  # "S1_STEM_DC_OFFSET"

    analysis: Dict[str, Any] = load_analysis(contract_id)

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {})
    stems: List[Dict[str, Any]] = analysis.get("stems", [])

    dc_offset_max_db_target = metrics.get("dc_offset_max_db")

    if stems:
        args_list = [(stem_info, dc_offset_max_db_target) for stem_info in stems]
        for args in args_list:
            _process_stem_worker(args)

    print(f"[S1_STEM_DC_OFFSET] Corrección de DC offset completada para {len(stems)} stems.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Uso: python {Path(__file__).name} <CONTRACT_ID>")
        sys.exit(1)

    from dataclasses import dataclass
    @dataclass
    class _MockContext:
        contract_id: str
        next_contract_id: str | None = None

    process(_MockContext(contract_id=sys.argv[1]))
