# backend/src/analysis/S0_SEPARATE_STEMS.py

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Any
import json

# --- hack para importar utils ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.analysis_utils import (  # type: ignore  # noqa: E402
    load_contract,
    get_temp_dir,
)


def _load_upload_mode_from_job_root(temp_dir: Path) -> Dict[str, Any]:
    """
    Lee temp/<job_id>/work/upload_mode.json si existe y devuelve:

      {
        "upload_mode": "song" | "stems",
        "is_stems_upload": bool
      }

    Si no existe, asume por defecto "song".
    """
    job_root = temp_dir.parent  # temp/<job_id>/<CONTRACT_ID> -> temp/<job_id>
    work_dir = job_root / "work"
    info_path = work_dir / "upload_mode.json"

    upload_mode = "song"
    is_stems_upload = False

    if info_path.exists():
        try:
            with info_path.open("r", encoding="utf-8") as f:
                data = json.load(f) or {}

            # Admite tanto bandera booleana como string
            if isinstance(data, dict):
                raw_mode = str(data.get("upload_mode", "")).strip().lower()
                raw_stems = data.get("stems")

                if isinstance(raw_stems, bool):
                    is_stems_upload = raw_stems
                elif raw_mode in {"stems", "upload_stems"}:
                    is_stems_upload = True
                else:
                    is_stems_upload = False

                upload_mode = "stems" if is_stems_upload else "song"
        except Exception as exc:  # pragma: no cover (defensivo)
            print(
                f"[S0_SEPARATE_STEMS] Aviso: no se pudo leer {info_path}: {exc}. "
                "Se asume upload_mode='song'."
            )

    return {
        "upload_mode": upload_mode,
        "is_stems_upload": is_stems_upload,
    }


def main() -> None:
    """
    Análisis para S0_SEPARATE_STEMS.

    Uso desde stage.py:
        python analysis/S0_SEPARATE_STEMS.py S0_SEPARATE_STEMS
    """
    if len(sys.argv) < 2:
        print("Uso: python S0_SEPARATE_STEMS.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S0_SEPARATE_STEMS"

    # 1) Cargar contrato (por si en el futuro añadimos métricas / límites)
    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {}) or {}
    limits: Dict[str, Any] = contract.get("limits", {}) or {}
    stage_id: str | None = contract.get("stage_id")

    # 2) temp/<job_id>/<contract_id>
    temp_dir = get_temp_dir(contract_id, create=True)

    # 3) Leer el modo de subida desde temp/<job_id>/work/upload_mode.json
    upload_info = _load_upload_mode_from_job_root(temp_dir)
    upload_mode = upload_info["upload_mode"]
    is_stems_upload = upload_info["is_stems_upload"]

    print(
        f"[S0_SEPARATE_STEMS] Análisis: upload_mode={upload_mode}, "
        f"is_stems_upload={is_stems_upload}."
    )

    # 4) Guardar analysis_<CONTRACT_ID>.json
    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "upload_mode": upload_mode,
            "is_stems_upload": is_stems_upload,
        },
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    print(
        f"[S0_SEPARATE_STEMS] Análisis completado. JSON: {output_path}"
    )


if __name__ == "__main__":
    main()
