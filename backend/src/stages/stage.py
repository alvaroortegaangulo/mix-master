from __future__ import annotations
from utils.logger import logger

import sys
import os
import json
import time
import importlib.util
import uuid
import datetime
import traceback
from pathlib import Path
from typing import List, Optional, Dict
import numpy as np

# Agregar backend/src al path para importar context
BASE_DIR = Path(__file__).resolve().parents[1]  # .../src
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from context import PipelineContext
except ImportError:
    # Fallback por si acaso
    try:
        logger.logger.warning("[stage] Warning: Could not import PipelineContext from context")
    except:
        print("[stage] Warning: Could not import PipelineContext from context")
    PipelineContext = None

from utils.logger import logger
# from utils.plot_utils import generate_comparison_plots # Plot utils rely on files

# Stages que trabajan en mixbus/master y necesitan full_song.wav
MIXDOWN_STAGES = {
    "S7_MIXBUS_TONAL_BALANCE",
    "S8_MIXBUS_COLOR_GENERIC",
    "S9_MASTER_GENERIC",
    "S10_MASTER_FINAL_LIMITS",
}

ACTIVE_CONTRACT_SEQUENCE: Optional[List[str]] = None
TIMINGS_FILENAME = "pipeline_timings.json"
_MODULE_CACHE: Dict[Path, object] = {}

def _get_job_temp_root(create: bool = False) -> Path:
    temp_root_env = os.environ.get("MIX_TEMP_ROOT")
    job_id_env = os.environ.get("MIX_JOB_ID")
    project_root = Path(__file__).resolve().parents[2]

    preferred_base = Path("/dev/shm/mix-master/temp")

    if temp_root_env:
        base = Path(temp_root_env)
    else:
        base = preferred_base / job_id_env if job_id_env else preferred_base

    if create:
        try:
            base.mkdir(parents=True, exist_ok=True)
        except OSError:
            fallback = (
                project_root / "temp" / job_id_env if job_id_env else project_root / "temp"
            )
            fallback.mkdir(parents=True, exist_ok=True)
            base = fallback

    return base


def _record_stage_timing(stage_id: str, duration_sec: float, context: Optional[PipelineContext] = None) -> None:
    if context and context.temp_root:
        job_root = context.temp_root
        if not job_root.exists():
            job_root.mkdir(parents=True, exist_ok=True)
    else:
        job_root = _get_job_temp_root(create=True)

    timings_path = job_root / TIMINGS_FILENAME

    data: dict = {"stages": [], "total_duration_sec": 0.0}
    if timings_path.exists():
        try:
            with timings_path.open("r", encoding="utf-8") as f:
                existing = json.load(f)
            if isinstance(existing, dict):
                data.update(existing)
        except Exception:
            data = {"stages": [], "total_duration_sec": 0.0}

    stages = data.get("stages", [])
    if not isinstance(stages, list):
        stages = []

    stages = [s for s in stages if s.get("contract_id") != stage_id]
    stages.append(
        {"contract_id": stage_id, "duration_sec": round(float(duration_sec), 3)}
    )
    data["stages"] = stages
    data["total_duration_sec"] = round(
        sum(s.get("duration_sec", 0.0) for s in stages), 3
    )
    data["generated_at_utc"] = (
        datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    )

    with timings_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


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

    contracts_path = base_dir / "struct" / "contracts.json"
    with contracts_path.open("r", encoding="utf-8") as f:
        contracts = json.load(f)

    all_contract_ids: List[str] = []
    for stage_data in contracts.get("stages", {}).values():
        for c in stage_data.get("contracts", []) or []:
            cid = c.get("id")
            if cid:
                all_contract_ids.append(cid)

    for i, cid in enumerate(all_contract_ids):
        if cid == current_contract_id:
            if i + 1 < len(all_contract_ids):
                return all_contract_ids[i + 1]
            return None

    return None


def _ensure_analysis_file(stage_id: str, analysis_script: Path, context: PipelineContext) -> None:
    if context.temp_root:
        temp_dir = context.temp_root / stage_id
    else:
        temp_dir = _get_job_temp_root(create=True) / stage_id

    analysis_path = temp_dir / f"analysis_{stage_id}.json"
    if analysis_path.exists():
        return

    logger.logger.warning(f"[stage] analysis_{stage_id}.json no encontrado, reintentando analisis...")
    _run_script(analysis_script, context, stage_id)


def _load_analysis_json(context: PipelineContext, stage_id: str) -> Dict:
    if context.temp_root:
        temp_dir = context.temp_root / stage_id
    else:
        temp_dir = _get_job_temp_root(create=True) / stage_id

    path = temp_dir / f"analysis_{stage_id}.json"
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.logger.error(f"Failed to load analysis JSON: {e}")
    return {}


def run_stage(stage_id: str, context: Optional[PipelineContext] = None) -> None:
    """
    IN-MEMORY MODE
    """
    base_dir = Path(__file__).resolve().parent.parent  # .../src

    if context is None:
        logger.error("[stage] In-memory pipeline requires a valid context.")
        return

    # Update context stage_id
    context.stage_id = stage_id

    analysis_script = base_dir / "analysis" / f"{stage_id}.py"
    stage_script = base_dir / "stages" / f"{stage_id}.py"
    check_script = base_dir / "utils" / "check_metrics_limits.py"
    mixdown_script = base_dir / "utils" / "mixdown_stems.py"
    copy_script = base_dir / "utils" / "copy_stems.py"
    cleanup_stems_script = base_dir / "utils" / "cleanup_stage_stems.py"

    logger.print_header(f"Running stage: {stage_id}", color="\033[34m")
    stage_start = time.perf_counter()

    # Pre-Mixdown
    if stage_id in MIXDOWN_STAGES:
        _run_script(mixdown_script, context, stage_id)

    # Capture 'Pre' state for comparison
    pre_audio_mixdown = None
    if stage_id in MIXDOWN_STAGES and context.audio_mixdown is not None:
         pre_audio_mixdown = context.audio_mixdown.copy()

    # 1) Análisis previo
    _run_script(analysis_script, context, stage_id)
    pre_analysis = _load_analysis_json(context, stage_id)

    # 2) Procesamiento principal
    _run_script(stage_script, context, stage_id)

    # 3) Análisis posterior
    _run_script(analysis_script, context, stage_id)
    post_analysis = _load_analysis_json(context, stage_id)

    # Log Comparison
    if pre_analysis and post_analysis:
        logger.print_comparison(pre_analysis, post_analysis)

    # TODO: Generate Plots using pre_audio_mixdown vs context.audio_mixdown
    # Requires updating plot_utils to accept numpy arrays.
    # For now we skip plots or assume they are not generated.
    # BUT user said "keep all audios in memory".
    # The frontend expects images. We should probably write images to disk.
    # We can write temporary WAVs just for plotting if plot_utils expects files.
    # Or refactor plot_utils. Refactoring plot_utils is safer.

    # 4) Validación
    logger.logger.info("") # Blank line
    logger.print_section("Metrics Limits Check", color="\033[36m")
    ret = _run_script(check_script, context, stage_id)
    success = (ret == 0)

    logger.log_stage_result(stage_id, success)

    # Post-Mixdown
    if stage_id not in MIXDOWN_STAGES:
        _run_script(mixdown_script, context, stage_id)

    # Copiar stems (No-op in memory, but logical next step)
    next_contract_id = _get_next_contract_id(base_dir, stage_id)
    if next_contract_id is not None:
        _run_script(copy_script, context, stage_id, next_contract_id)

    # Limpiar (No-op in memory)
    _run_script(cleanup_stems_script, context, stage_id)

    # Asegurar análisis
    _ensure_analysis_file(stage_id, analysis_script, context)

    duration_sec = time.perf_counter() - stage_start
    _record_stage_timing(stage_id, duration_sec, context)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python stage.py <STAGE_ID>")
    else:
        # Legacy not supported
        pass
