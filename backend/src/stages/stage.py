from __future__ import annotations

import sys
import os
import json
import time
import importlib.util
import uuid
import datetime
import subprocess
from pathlib import Path
from typing import List, Optional

MAX_RETRIES = 3

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


def _get_job_temp_root(create: bool = False) -> Path:
    """
    Raiz temporal del job (respeta MIX_TEMP_ROOT y MIX_JOB_ID).
    Copia la logica de utils.analysis_utils pero sin dependencias
    para que stage.py pueda ejecutarse como script suelto.
    """
    temp_root_env = os.environ.get("MIX_TEMP_ROOT")
    job_id_env = os.environ.get("MIX_JOB_ID")
    project_root = Path(__file__).resolve().parents[2]  # .../backend

    if temp_root_env:
        base = Path(temp_root_env)
    elif job_id_env:
        base = project_root / "temp" / job_id_env
    else:
        base = project_root / "temp"

    if create:
        base.mkdir(parents=True, exist_ok=True)

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


def _ensure_analysis_file(stage_id: str, analysis_script: Path) -> None:
    """
    Garantiza que exista analysis_<stage_id>.json; si no, re-ejecuta el
    análisis vía subprocess (fallback).
    """
    temp_dir = _get_job_temp_root(create=True) / stage_id
    analysis_path = temp_dir / f"analysis_{stage_id}.json"
    if analysis_path.exists():
        return

    print(f"[stage] analysis_{stage_id}.json no encontrado, reintentando análisis vía subprocess...")
    try:
        subprocess.run(
          [sys.executable, str(analysis_script), stage_id],
          check=False,
        )
    except Exception as exc:
        print(f"[stage] Error al reintentar análisis de {stage_id}: {exc}")


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


def _run_script_main(script_path: Path, *args: str) -> int:
    """
    Ejecuta el main() de un script Python (analysis, stage o utils) en el
    mismo proceso en lugar de lanzar un nuevo intérprete. Esto evita el
    overhead de crear subprocesos y acelera el pipeline.
    """
    spec = importlib.util.spec_from_file_location(
        f"_pipeline_{script_path.stem}_{uuid.uuid4().hex}", script_path
    )
    if spec is None or spec.loader is None:
        print(f"[stage] No se pudo cargar el módulo {script_path}")
        return 1

    module = importlib.util.module_from_spec(spec)
    old_argv = sys.argv[:]
    sys.argv = [script_path.name, *args]

    try:
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        main_fn = getattr(module, "main", None)
        if callable(main_fn):
            main_fn()
            return 0

        print(f"[stage] El script {script_path} no expone main()")
        return 1
    except SystemExit as exc:  # scripts pueden llamar sys.exit
        code = exc.code
        if isinstance(code, int):
            return code
        return 1
    except Exception as exc:  # pragma: no cover - logging defensivo
        print(f"[stage] Excepción ejecutando {script_path}: {exc}", file=sys.stderr)
        return 1
    finally:
        sys.argv = old_argv
        # evitar fugas en sys.modules (no compartimos estado entre invocaciones)
        if spec.name in sys.modules:
            sys.modules.pop(spec.name, None)


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


def run_stage(stage_id: str) -> None:
    """
    Ejecuta el análisis, el procesamiento y la validación de un contrato
    concreto (stage_id = contract_id), generando su full_song.wav y
    copiando los stems al siguiente contrato según la secuencia activa.
    """
    base_dir = Path(__file__).resolve().parent.parent  # .../src

    analysis_script = base_dir / "analysis" / f"{stage_id}.py"
    stage_script = base_dir / "stages" / f"{stage_id}.py"
    check_script = base_dir / "utils" / "check_metrics_limits.py"
    mixdown_script = base_dir / "utils" / "mixdown_stems.py"
    copy_script = base_dir / "utils" / "copy_stems.py"

    success = False
    attempt = 0

    print(f"Running stage: {stage_id}")
    stage_start = time.perf_counter()

    while attempt < MAX_RETRIES:
        attempt += 1

        # Para stages de mixbus/master, primero necesitamos un full_song.wav
        # actualizado a partir de los stems de este stage.
        if stage_id in MIXDOWN_STAGES:
            _run_script_main(mixdown_script, stage_id)

        # 1) Análisis previo
        _run_script_main(analysis_script, stage_id)

        # 2) Procesamiento principal de la etapa
        _run_script_main(stage_script, stage_id)

        # 3) Análisis posterior
        _run_script_main(analysis_script, stage_id)

        # 4) Validación de métricas (check_metrics_limits.py)
        ret = _run_script_main(check_script, stage_id)
        success = (ret == 0)

        if success:
            break

    resultado = "éxito" if success else "fracaso"
    print(f"Resultado {stage_id}: {resultado}")

    # Para el resto de stages (no master), el mixdown se hace al final
    # para dejar preparado full_song.wav de este contrato.
    if stage_id not in MIXDOWN_STAGES:
        _run_script_main(mixdown_script, stage_id)

    # Copiar stems a la carpeta del siguiente contrato de la secuencia
    next_contract_id = _get_next_contract_id(base_dir, stage_id)
    if next_contract_id is not None:
        _run_script_main(copy_script, stage_id, next_contract_id)

    # Asegurar que el análisis existe (fallback a subprocess si falta)
    _ensure_analysis_file(stage_id, analysis_script)

    duration_sec = time.perf_counter() - stage_start
    _record_stage_timing(stage_id, duration_sec)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python stage.py <STAGE_ID>")
    else:
        run_stage(sys.argv[1])
