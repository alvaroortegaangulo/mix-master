# C:\mix-master\backend\src\stages\stage.py

import sys
import json
import subprocess
from pathlib import Path

MAX_RETRIES = 3


def _run_python_script(script_path: Path, *args: str) -> int:
    cmd = [sys.executable, str(script_path), *args]
    result = subprocess.run(cmd)
    return result.returncode


def _get_next_contract_id(base_dir: Path, current_contract_id: str) -> str | None:
    """
    Lee struct/contracts.json y devuelve el id del siguiente contrato
    en la secuencia completa (S0_SESSION_FORMAT, S1_STEM_DC_OFFSET, ...).
    Si current_contract_id es el último, devuelve None.
    """
    contracts_path = base_dir / "struct" / "contracts.json"
    with contracts_path.open("r", encoding="utf-8") as f:
        contracts = json.load(f)

    all_contract_ids = []
    for stage_data in contracts.get("stages", {}).values():
        for c in stage_data.get("contracts", []):
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
    base_dir = Path(__file__).resolve().parent.parent  # .../src

    analysis_script = base_dir / "analysis" / f"{stage_id}.py"
    stage_script = base_dir / "stages" / f"{stage_id}.py"
    check_script = base_dir / "utils" / "check_metrics_limits.py"
    select_script = base_dir / "utils" / "select_stems.py"
    mixdown_script = base_dir / "utils" / "mixdown_stems.py"
    copy_script = base_dir / "utils" / "copy_stems.py"

    success = False
    attempt = 0

    print(f"Running stage: {stage_id}")

    while attempt < MAX_RETRIES:
        attempt += 1

        _run_python_script(analysis_script, stage_id)
        _run_python_script(stage_script, stage_id)
        _run_python_script(analysis_script, stage_id)

        ret = _run_python_script(check_script, stage_id)
        success = (ret == 0)

        if success:
            break

    resultado = "éxito" if success else "fracaso"
    print(f"Resultado {stage_id}: {resultado}")


    _run_python_script(mixdown_script, stage_id)

    next_contract_id = _get_next_contract_id(base_dir, stage_id)
    if next_contract_id is not None:
        _run_python_script(copy_script, stage_id, next_contract_id)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python stage.py <STAGE_ID>")
    else:
        run_stage(sys.argv[1])







