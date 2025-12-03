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

# Agregar backend/src al path para importar context
BASE_DIR = Path(__file__).resolve().parents[1]  # .../src
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from context import PipelineContext
except ImportError:
    # Fallback por si acaso
    # We can't use logger here if imports are broken, but try anyway as it is imported above
    try:
        logger.logger.warning("[stage] Warning: Could not import PipelineContext from context")
    except:
        print("[stage] Warning: Could not import PipelineContext from context")
    PipelineContext = None

from utils.logger import logger



# Stages que trabajan en mixbus/master y necesitan full_song.wav
# generado a partir de stems ANTES del análisis
MIXDOWN_STAGES = {
    "S7_MIXBUS_TONAL_BALANCE",
    "S8_MIXBUS_COLOR_GENERIC",
    "S9_MASTER_GENERIC",
    "S10_MASTER_FINAL_LIMITS",
}

# Secuencia activa de contratos
ACTIVE_CONTRACT_SEQUENCE: Optional[List[str]] = None
TIMINGS_FILENAME = "pipeline_timings.json"

# Cache de módulos para evitar re-importación constante
_MODULE_CACHE: Dict[Path, object] = {}

def _get_job_temp_root(create: bool = False) -> Path:
    """
    Raiz temporal del job (respeta MIX_TEMP_ROOT y MIX_JOB_ID).
    Legacy fallback si no se pasa contexto.
    """
    temp_root_env = os.environ.get("MIX_TEMP_ROOT")
    job_id_env = os.environ.get("MIX_JOB_ID")
    project_root = Path(__file__).resolve().parents[2]  # .../backend

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
    """
    Guarda/actualiza un JSON con la duracion por etapa y el total acumulado.
    """
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
    """
    Importa un módulo desde una ruta, usando caché si está disponible.
    """
    if script_path in _MODULE_CACHE:
        return _MODULE_CACHE[script_path]

    # Usamos el nombre del archivo (sin extensión) como nombre del módulo
    # para evitar conflictos si hay scripts con el mismo nombre en diferentes carpetas,
    # aunque aquí usualmente son únicos por carpeta o el path completo ayuda.
    # Pero sys.modules necesita un nombre único.
    # Usaremos una combinación para ser seguros.
    module_name = f"pipeline.{script_path.parent.name}.{script_path.stem}"

    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if not spec or not spec.loader:
        return None

    module = importlib.util.module_from_spec(spec)

    # No lo registramos en sys.modules globalmente para evitar polución si no queremos,
    # pero para que funcionen los imports relativos dentro del modulo (si los hubiera)
    # a veces es necesario. Aquí asumimos scripts "standalone".

    try:
        spec.loader.exec_module(module)
        _MODULE_CACHE[script_path] = module
        return module
    except Exception as e:
        logger.logger.info(f"[stage] Error importing {script_path}: {e}")
        traceback.print_exc()
        return None


def _run_script(script_path: Path, context: PipelineContext, *args: str) -> int:
    """
    Ejecuta un script.
    1) Intenta usar process(context, *args).
    2) Si no existe, intenta usar main() manipulando sys.argv (legacy).
    """
    module = _import_module(script_path)
    if not module:
        logger.logger.error(f"[stage] No se pudo cargar el módulo {script_path}")
        return 1

    # 1. Intentar método process(context, *args)
    if hasattr(module, 'process'):
        try:
            # Asumimos que process devuelve True (éxito), False (fallo) o None (éxito implícito)
            res = module.process(context, *args)
            if res is False:
                return 1
            return 0
        except Exception as exc:
            logger.logger.error(f"[stage] Excepción en process() de {script_path.name}: {exc}")
            traceback.print_exc()
            return 1

    # 2. Fallback a main() con sys.argv
    old_argv = sys.argv[:]
    # args son strings adicionales. sys.argv[0] es el nombre del script.
    sys.argv = [script_path.name, *args]

    try:
        main_fn = getattr(module, "main", None)
        if callable(main_fn):
            main_fn()
            return 0

        logger.logger.error(f"[stage] El script {script_path} no expone process() ni main()")
        return 1
    except SystemExit as exc:
        code = exc.code
        if isinstance(code, int):
            return code
        return 1
    except Exception as exc:
        logger.logger.error(f"[stage] Excepción en main() de {script_path}: {exc}")
        traceback.print_exc()
        return 1
    finally:
        sys.argv = old_argv


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
    """
    Garantiza que exista analysis_<stage_id>.json.
    """
    if context.temp_root:
        temp_dir = context.temp_root / stage_id
    else:
        temp_dir = _get_job_temp_root(create=True) / stage_id

    analysis_path = temp_dir / f"analysis_{stage_id}.json"
    if analysis_path.exists():
        return

    logger.logger.warning(f"[stage] analysis_{stage_id}.json no encontrado, reintentando analisis...")
    # Pasamos stage_id como argumento por si es legacy, aunque context ya lo tiene
    _run_script(analysis_script, context, stage_id)


def _load_analysis_json(context: PipelineContext, stage_id: str) -> Dict:
    """Helper to load analysis JSON safely."""
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
    Ejecuta el análisis, el procesamiento y la validación de un contrato.
    Ahora acepta un contexto opcional.
    """
    base_dir = Path(__file__).resolve().parent.parent  # .../src

    # Si no hay contexto, creamos uno legacy
    if context is None:
        job_id = os.environ.get("MIX_JOB_ID", "legacy_cli")
        temp_root = _get_job_temp_root(create=False)
        context = PipelineContext(stage_id=stage_id, job_id=job_id, temp_root=temp_root)
    else:
        # Actualizamos el stage_id del contexto para este run
        context.stage_id = stage_id

    analysis_script = base_dir / "analysis" / f"{stage_id}.py"
    stage_script = base_dir / "stages" / f"{stage_id}.py"
    check_script = base_dir / "utils" / "check_metrics_limits.py"
    mixdown_script = base_dir / "utils" / "mixdown_stems.py"
    copy_script = base_dir / "utils" / "copy_stems.py"
    cleanup_stems_script = base_dir / "utils" / "cleanup_stage_stems.py"

    logger.print_header(f"Running stage: {stage_id}")
    stage_start = time.perf_counter()

    # Pre-Mixdown (Legacy args: stage_id)
    if stage_id in MIXDOWN_STAGES:
        _run_script(mixdown_script, context, stage_id)

    # 1) Análisis previo (Legacy args: stage_id)
    _run_script(analysis_script, context, stage_id)
    pre_analysis = _load_analysis_json(context, stage_id)

    # 2) Procesamiento principal (Legacy args: stage_id)
    _run_script(stage_script, context, stage_id)

    # 3) Análisis posterior (Legacy args: stage_id)
    _run_script(analysis_script, context, stage_id)
    post_analysis = _load_analysis_json(context, stage_id)

    # Log Comparison
    if pre_analysis and post_analysis:
        logger.print_comparison(pre_analysis, post_analysis)

    # 4) Validación (Legacy args: stage_id)
    logger.print_section("Metrics Limits Check")
    ret = _run_script(check_script, context, stage_id)
    success = (ret == 0)

    logger.log_stage_result(stage_id, success)

    # Post-Mixdown
    if stage_id not in MIXDOWN_STAGES:
        _run_script(mixdown_script, context, stage_id)

    # Copiar stems
    next_contract_id = _get_next_contract_id(base_dir, stage_id)
    if next_contract_id is not None:
        # Copy script toma src_stage, dst_stage
        _run_script(copy_script, context, stage_id, next_contract_id)

    # Limpiar
    _run_script(cleanup_stems_script, context, stage_id)

    # Asegurar análisis
    _ensure_analysis_file(stage_id, analysis_script, context)

    duration_sec = time.perf_counter() - stage_start
    _record_stage_timing(stage_id, duration_sec, context)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python stage.py <STAGE_ID>")
    else:
        run_stage(sys.argv[1])
