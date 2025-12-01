from __future__ import annotations

import sys
import json
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


def _run_python_script(script_path: Path, *args: str) -> int:
    cmd = [sys.executable, str(script_path), *args]
    result = subprocess.run(cmd)
    return result.returncode


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

    while attempt < MAX_RETRIES:
        attempt += 1

        # Para stages de mixbus/master, primero necesitamos un full_song.wav
        # actualizado a partir de los stems de este stage.
        if stage_id in MIXDOWN_STAGES:
            _run_python_script(mixdown_script, stage_id)

        # 1) Análisis previo
        _run_python_script(analysis_script, stage_id)

        # 2) Procesamiento principal de la etapa
        _run_python_script(stage_script, stage_id)

        # 3) Análisis posterior
        _run_python_script(analysis_script, stage_id)

        # 4) Validación de métricas (check_metrics_limits.py)
        ret = _run_python_script(check_script, stage_id)
        success = (ret == 0)

        if success:
            break

    resultado = "éxito" if success else "fracaso"
    print(f"Resultado {stage_id}: {resultado}")

    # Para el resto de stages (no master), el mixdown se hace al final
    # para dejar preparado full_song.wav de este contrato.
    if stage_id not in MIXDOWN_STAGES:
        _run_python_script(mixdown_script, stage_id)

    # Copiar stems a la carpeta del siguiente contrato de la secuencia
    next_contract_id = _get_next_contract_id(base_dir, stage_id)
    if next_contract_id is not None:
        _run_python_script(copy_script, stage_id, next_contract_id)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python stage.py <STAGE_ID>")
    else:
        run_stage(sys.argv[1])
