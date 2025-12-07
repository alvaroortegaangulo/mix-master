from __future__ import annotations
from utils.logger import logger

import sys
import os
import json
import time
import importlib.util
import datetime
import traceback
from pathlib import Path
from typing import List, Optional, Dict, Any

# Agregar backend/src al path para importar context
BASE_DIR = Path(__file__).resolve().parents[1]  # .../src
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from context import PipelineContext
except ImportError:
    PipelineContext = None

# Stages que trabajan en mixbus/master
MIXDOWN_STAGES = {
    "S7_MIXBUS_TONAL_BALANCE",
    "S8_MIXBUS_COLOR_GENERIC",
    "S9_MASTER_GENERIC",
    "S10_MASTER_FINAL_LIMITS",
}

ACTIVE_CONTRACT_SEQUENCE: Optional[List[str]] = None
_MODULE_CACHE: Dict[Path, object] = {}

def _record_stage_timing(stage_id: str, duration_sec: float, context: Optional[PipelineContext] = None) -> None:
    if context:
        context.pipeline_timings.append({
            "contract_id": stage_id,
            "duration_sec": round(float(duration_sec), 3),
            "generated_at_utc": datetime.datetime.utcnow().isoformat() + "Z"
        })

def set_active_contract_sequence(ordered_contract_ids: Optional[List[str]]) -> None:
    global ACTIVE_CONTRACT_SEQUENCE
    if ordered_contract_ids:
        ACTIVE_CONTRACT_SEQUENCE = list(ordered_contract_ids)
    else:
        ACTIVE_CONTRACT_SEQUENCE = None

def _import_module(script_path: Path):
    if script_path in _MODULE_CACHE:
        return _MODULE_CACHE[script_path]

    module_name = f"pipeline.{script_path.parent.name}.{script_path.stem}"

    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if not spec or not spec.loader:
        return None

    module = importlib.util.module_from_spec(spec)

    try:
        spec.loader.exec_module(module)
        _MODULE_CACHE[script_path] = module
        return module
    except Exception as e:
        logger.logger.info(f"[stage] Error importing {script_path}: {e}")
        traceback.print_exc()
        return None

def _run_script(script_path: Path, context: PipelineContext, *args: str) -> int:
    module = _import_module(script_path)
    if not module:
        logger.logger.error(f"[stage] No se pudo cargar el módulo {script_path}")
        return 1

    if hasattr(module, 'process'):
        try:
            # We pass context. Arguments like stage_id might be needed if process accepts them,
            # but standard signature is process(context).
            # If the script expects more args, we must check signature or pass *args?
            # Legacy code passed *args. We should check.
            # Usually process(context) is enough because context has stage_id.
            # But let's pass *args just in case.
            res = module.process(context, *args)
            if res is False:
                return 1
            return 0
        except Exception as exc:
            logger.logger.error(f"[stage] Excepción en process() de {script_path.name}: {exc}")
            traceback.print_exc()
            return 1

    logger.logger.error(f"[stage] El script {script_path} no expone process() (Required for in-memory mode)")
    return 1

def _get_next_contract_id(base_dir: Path, current_contract_id: str) -> str | None:
    if ACTIVE_CONTRACT_SEQUENCE:
        try:
            idx = ACTIVE_CONTRACT_SEQUENCE.index(current_contract_id)
        except ValueError:
            pass
        else:
            if idx + 1 < len(ACTIVE_CONTRACT_SEQUENCE):
                return ACTIVE_CONTRACT_SEQUENCE[idx + 1]
            return None
    return None

def _ensure_analysis(stage_id: str, analysis_script: Path, context: PipelineContext) -> None:
    if stage_id in context.analysis_results:
        return
    logger.logger.warning(f"[stage] Analysis for {stage_id} missing, running...")
    _run_script(analysis_script, context, stage_id)

def _load_analysis_result(context: PipelineContext, stage_id: str) -> Dict:
    return context.analysis_results.get(stage_id, {})

def run_stage(stage_id: str, context: Optional[PipelineContext] = None) -> None:
    base_dir = Path(__file__).resolve().parent.parent

    if context is None:
        logger.error("[stage] In-memory pipeline requires a valid context.")
        return

    context.stage_id = stage_id

    analysis_script = base_dir / "analysis" / f"{stage_id}.py"
    stage_script = base_dir / "stages" / f"{stage_id}.py"
    check_script = base_dir / "utils" / "check_metrics_limits.py"
    mixdown_script = base_dir / "utils" / "mixdown_stems.py"
    copy_script = base_dir / "utils" / "copy_stems.py"
    cleanup_stems_script = base_dir / "utils" / "cleanup_stage_stems.py"

    logger.print_header(f"Running stage: {stage_id}", color="\033[34m")
    stage_start = time.perf_counter()

    if stage_id in MIXDOWN_STAGES:
        _run_script(mixdown_script, context, stage_id)

    # 1) Análisis previo
    _run_script(analysis_script, context, stage_id)
    pre_analysis = _load_analysis_result(context, stage_id)

    # 2) Procesamiento principal
    _run_script(stage_script, context, stage_id)

    # 3) Análisis posterior
    _run_script(analysis_script, context, stage_id)
    post_analysis = _load_analysis_result(context, stage_id)

    if pre_analysis and post_analysis:
        logger.print_comparison(pre_analysis, post_analysis)

    logger.logger.info("")
    logger.print_section("Metrics Limits Check", color="\033[36m")
    ret = _run_script(check_script, context, stage_id)
    success = (ret == 0)

    logger.log_stage_result(stage_id, success)

    if stage_id not in MIXDOWN_STAGES:
        _run_script(mixdown_script, context, stage_id)

    next_contract_id = _get_next_contract_id(base_dir, stage_id)
    if next_contract_id is not None:
        _run_script(copy_script, context, stage_id, next_contract_id)

    _run_script(cleanup_stems_script, context, stage_id)
    _ensure_analysis(stage_id, analysis_script, context)

    duration_sec = time.perf_counter() - stage_start
    _record_stage_timing(stage_id, duration_sec, context)

if __name__ == "__main__":
    pass
