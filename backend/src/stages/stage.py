from __future__ import annotations

import sys
import os
import json
import time
import datetime
import importlib
from pathlib import Path
from typing import List, Optional, Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from stages.pipeline_context import PipelineContext

# Stages que trabajan en mixbus/master y necesitan full_song.wav
# generado a partir de stems ANTES del análisis
MIXDOWN_STAGES = {
    "S7_MIXBUS_TONAL_BALANCE",
    "S8_MIXBUS_COLOR_GENERIC",
    "S9_MASTER_GENERIC",
    "S10_MASTER_FINAL_LIMITS",
}

# -------------------------------------------------------------------
# Secuencia activa de contratos (subset ordenado de contracts.json)
# -------------------------------------------------------------------
# La rellena pipeline.run_pipeline / run_pipeline_for_job con la lista
# de contract_ids que realmente se van a ejecutar para el job actual.
ACTIVE_CONTRACT_SEQUENCE: Optional[List[str]] = None
TIMINGS_FILENAME = "pipeline_timings.json"

# Cache for imported modules to avoid re-importing
_MODULE_CACHE = {}


def _get_job_temp_root(create: bool = False) -> Path:
    """
    Raiz temporal del job (respeta MIX_TEMP_ROOT y MIX_JOB_ID).
    Usa /dev/shm por defecto para aprovechar RAM; si falla, cae a backend/temp.
    Copia la logica de utils.analysis_utils pero sin dependencias
    para que stage.py pueda ejecutarse como script suelto.
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
            # fallback a backend/temp
            fallback = (
                project_root / "temp" / job_id_env if job_id_env else project_root / "temp"
            )
            fallback.mkdir(parents=True, exist_ok=True)
            base = fallback

    return base


def _record_stage_timing(stage_id: str, duration_sec: float) -> None:
    """
    Guarda/actualiza un JSON con la duracion por etapa y el total acumulado.
    """
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
    """
    Define la secuencia efectiva de contratos que se están ejecutando
    para el proceso actual.

    Si es None o una lista vacía, se usará el orden completo de
    struct/contracts.json como fallback.
    """
    global ACTIVE_CONTRACT_SEQUENCE
    if ordered_contract_ids:
        # Copia defensiva para evitar modificaciones externas.
        ACTIVE_CONTRACT_SEQUENCE = list(ordered_contract_ids)
    else:
        ACTIVE_CONTRACT_SEQUENCE = None


def _get_next_contract_id(base_dir: Path, current_contract_id: str) -> str | None:
    """
    Devuelve el id del siguiente contrato en la secuencia efectiva.

    1) Si ACTIVE_CONTRACT_SEQUENCE está definido, se usa como orden
       principal (subset filtrado que respeta el orden del pipeline).
    2) Si no está definido o current_contract_id no está en esa lista,
       se cae al orden completo de struct/contracts.json (modo legacy).
    """
    # 1) Intentar usar la secuencia activa (subset filtrado)
    if ACTIVE_CONTRACT_SEQUENCE:
        try:
            idx = ACTIVE_CONTRACT_SEQUENCE.index(current_contract_id)
        except ValueError:
            # current_contract_id no está en la secuencia activa
            # (fallback a orden completo).
            pass
        else:
            if idx + 1 < len(ACTIVE_CONTRACT_SEQUENCE):
                return ACTIVE_CONTRACT_SEQUENCE[idx + 1]
            # Es el último contrato habilitado
            return None

    # 2) Fallback legacy: usar TODO contracts.json
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


def _import_and_get_process_func(module_name: str) -> Callable[[PipelineContext], Any]:
    """
    Importa un módulo (si no está ya en caché) y devuelve su función process(context).
    """
    if module_name in _MODULE_CACHE:
        return _MODULE_CACHE[module_name]

    try:
        module = importlib.import_module(module_name)
    except ImportError as e:
        raise ImportError(f"No se pudo importar el módulo {module_name}: {e}")

    process_fn = getattr(module, "process", None)
    if not callable(process_fn):
        raise AttributeError(f"El módulo {module_name} no expone una función process(context).")

    _MODULE_CACHE[module_name] = process_fn
    return process_fn


def run_stage(stage_id: str) -> None:
    """
    Ejecuta el análisis, el procesamiento y la validación de un contrato
    concreto (stage_id = contract_id), generando su full_song.wav y
    copiando los stems al siguiente contrato según la secuencia activa.
    """
    base_dir = Path(__file__).resolve().parent.parent  # .../src

    # Import locally to avoid issues when running as standalone script before sys.path hack
    from stages.pipeline_context import PipelineContext

    # Utility modules names
    mixdown_module_name = "utils.mixdown_stems"
    copy_module_name = "utils.copy_stems"
    cleanup_module_name = "utils.cleanup_stage_stems"
    check_metrics_module_name = "utils.check_metrics_limits"

    # Stage specific modules names
    analysis_module_name = f"analysis.{stage_id}"
    stage_module_name = f"stages.{stage_id}"

    success = False

    print(f"Running stage: {stage_id}")
    stage_start = time.perf_counter()

    # Context setup
    next_contract_id = _get_next_contract_id(base_dir, stage_id)
    ctx = PipelineContext(
        contract_id=stage_id,
        next_contract_id=next_contract_id
    )

    # Helper to run a process step
    def run_step(module_name: str, context: PipelineContext) -> Any:
        try:
            func = _import_and_get_process_func(module_name)
            return func(context)
        except Exception as e:
            print(f"[stage] Error ejecutando {module_name}: {e}")
            raise

    # Para stages de mixbus/master, primero necesitamos un full_song.wav
    # actualizado a partir de los stems de este stage.
    if stage_id in MIXDOWN_STAGES:
        run_step(mixdown_module_name, ctx)

    # 1) Análisis previo
    run_step(analysis_module_name, ctx)

    # 2) Procesamiento principal de la etapa
    run_step(stage_module_name, ctx)

    # 3) Análisis posterior
    run_step(analysis_module_name, ctx)

    # 4) Validación de métricas (check_metrics_limits.py)
    try:
        ret = run_step(check_metrics_module_name, ctx)
        # check_metrics_limits refactored to return bool.
        # Strict check for True to avoid False == 0 pitfall if mixed types were possible,
        # but here we expect boolean from the process function.
        if ret is True:
            success = True
        else:
            success = False
    except Exception:
        success = False

    resultado = "éxito" if success else "fracaso"
    print(f"Resultado {stage_id}: {resultado}")

    # Para el resto de stages (no master), el mixdown se hace al final
    # para dejar preparado full_song.wav de este contrato.
    if stage_id not in MIXDOWN_STAGES:
        run_step(mixdown_module_name, ctx)

    # Copiar stems a la carpeta del siguiente contrato de la secuencia
    if next_contract_id is not None:
        run_step(copy_module_name, ctx)

    # Limpiar stems del stage actual (conserva full_song.wav)
    run_step(cleanup_module_name, ctx)

    # Ensure analysis file exists is now implicit since we run analysis step.
    # But the original code had a retry mechanism `_ensure_analysis_file`.
    # With direct calls, if analysis fails, it likely raised an exception or printed error.
    # We can add a check here if needed, but if the process call succeeded, the file should be there.
    # Let's verify existence just in case.
    temp_dir = _get_job_temp_root(create=True) / stage_id
    analysis_path = temp_dir / f"analysis_{stage_id}.json"
    if not analysis_path.exists():
         print(f"[stage] analysis_{stage_id}.json no encontrado, reintentando analisis...")
         run_step(analysis_module_name, ctx)

    duration_sec = time.perf_counter() - stage_start
    _record_stage_timing(stage_id, duration_sec)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python stage.py <STAGE_ID>")
    else:
        # Hack to make sure backend/src is in sys.path
        # When running from stage.py, we need parent folder
        BASE_DIR = Path(__file__).resolve().parent.parent
        if str(BASE_DIR) not in sys.path:
            sys.path.insert(0, str(BASE_DIR))

        run_stage(sys.argv[1])
