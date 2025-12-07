from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any, List

# --- hack sys.path ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    from context import PipelineContext
except ImportError:
    pass

def _format_stem_summary(stem: Dict[str, Any]) -> str:
    file_name = stem.get("file_name")
    inst_profile = stem.get("instrument_profile")
    return f"      * {file_name} [{inst_profile}]"

def process(context: PipelineContext, contract_id: str) -> bool:
    analysis = context.analysis_results.get(contract_id)
    if not analysis:
        logger.logger.error(f"[S1_KEY_DETECTION] No analysis found for {contract_id}")
        return False

    session: Dict[str, Any] = analysis.get("session", {})
    stems: List[Dict[str, Any]] = analysis.get("stems", [])

    key_name = session.get("key_name")
    key_mode = session.get("key_mode")
    key_root_pc = session.get("key_root_pc")
    confidence = session.get("key_detection_confidence")
    scale_pcs = session.get("scale_pitch_classes")

    logger.logger.info("[S1_KEY_DETECTION] Resumen de análisis (In-Memory):")
    logger.logger.info(f"  - Tonalidad global: {key_name} (modo={key_mode}, root_pc={key_root_pc})")
    logger.logger.info(f"  - Confianza: {confidence}")
    logger.logger.info(f"  - Escala (pitch classes, C=0): {scale_pcs}")
    logger.logger.info(f"  - Número de stems analizados: {len(stems)}")
    logger.logger.info("  - Stems:")

    if stems:
        for line in map(_format_stem_summary, stems):
            logger.logger.info(line)
    else:
        logger.logger.info("      (ningún stem detectado en el análisis)")

    logger.logger.info("[S1_KEY_DETECTION] Stage completado (passthrough).")
    return True
