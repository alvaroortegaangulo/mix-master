from utils.logger import logger
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

# Añadir .../src al sys.path para poder hacer "from utils ..."
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json
import numpy as np

try:
    from context import PipelineContext
except ImportError:
    PipelineContext = None # type: ignore

def load_analysis(context: PipelineContext, contract_id: str) -> Dict[str, Any]:
    """
    Carga el JSON de análisis generado por analysis\\S1_STEM_DC_OFFSET.py.
    """
    # Analysis JSONs are still on disk for now
    if context.temp_root:
        temp_dir = context.temp_root / contract_id
    else:
        # Fallback
        from utils.analysis_utils import get_temp_dir
        temp_dir = get_temp_dir(contract_id, create=False)

    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def process(context: PipelineContext, *args) -> bool:
    """
    Stage S1_STEM_DC_OFFSET:
      - Lee analysis_S1_STEM_DC_OFFSET.json.
      - Corrige el DC offset de cada stem que incumple el contrato.
      - Modifica los stems IN-MEMORY.
    """
    contract_id = context.stage_id

    try:
        analysis: Dict[str, Any] = load_analysis(context, contract_id)
    except FileNotFoundError:
        logger.error(f"[S1_STEM_DC_OFFSET] Analysis not found for {contract_id}")
        return False

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {})
    stems_info: List[Dict[str, Any]] = analysis.get("stems", [])

    dc_offset_max_db_target = metrics.get("dc_offset_max_db")

    processed_count = 0
    for stem_info in stems_info:
        file_name = Path(stem_info["file_path"]).name

        # Check if stem exists in memory
        if file_name not in context.audio_stems:
            logger.warning(f"[S1_STEM_DC_OFFSET] Stem {file_name} not found in memory.")
            continue

        # dc_offset_linear puede ser float (legacy) o lista (nuevo)
        dc_linear_raw = stem_info.get("dc_offset_linear", 0.0)
        dc_db = float(stem_info.get("dc_offset_db", -120.0))

        # Check if correction needed
        need_correction = False
        if dc_offset_max_db_target is None:
            need_correction = True
        else:
            need_correction = dc_db > dc_offset_max_db_target

        if not need_correction:
            continue

        data = context.audio_stems[file_name] # (samples, channels)

        n_channels = data.shape[1] if data.ndim > 1 else 1
        correction_vector = np.zeros(n_channels, dtype=np.float32)

        if isinstance(dc_linear_raw, list):
            count = min(len(dc_linear_raw), n_channels)
            for i in range(count):
                correction_vector[i] = float(dc_linear_raw[i])
        else:
            val = float(dc_linear_raw)
            correction_vector[:] = val

        # Apply correction in-place
        # data is mutable (numpy array)
        data -= correction_vector
        processed_count += 1

    logger.info(f"[S1_STEM_DC_OFFSET] Corrección de DC offset completada para {processed_count} stems.")
    return True

def main() -> None:
    # Legacy CLI not supported for in-memory only operations without hydration
    logger.error("[S1_STEM_DC_OFFSET] Cannot run standalone in in-memory mode.")
    sys.exit(1)

if __name__ == "__main__":
    main()
