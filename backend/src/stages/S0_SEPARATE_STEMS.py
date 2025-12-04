# backend/src/stages/S0_SEPARATE_STEMS.py

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Any

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402

from utils.analysis_utils import get_temp_dir  # type: ignore  # noqa: E402


def load_analysis(contract_id: str) -> Dict[str, Any]:
    """
    Carga el JSON de análisis generado por analysis\\S0_SEPARATE_STEMS.py.
    """
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def main() -> None:
    """
    Stage S0_SEPARATE_STEMS:

      - Lee analysis_S0_SEPARATE_STEMS.json.
      - Imprime por pantalla si el usuario ha subido una canción
        o ha subido stems.
    """
    if len(sys.argv) < 2:
        print("Uso: python S0_SEPARATE_STEMS.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S0_SEPARATE_STEMS"

    analysis = load_analysis(contract_id)
    session: Dict[str, Any] = analysis.get("session", {}) or {}

    upload_mode = str(session.get("upload_mode", "song"))
    is_stems_upload = bool(
        session.get("is_stems_upload", upload_mode.strip().lower() == "stems")
    )

    if is_stems_upload:
        msg = "El usuario ha subido stems"
    else:
        msg = "El usuario ha subido una canción"

    print(f"[S0_SEPARATE_STEMS] {msg}.")

    # De momento no hacemos nada más (no hay procesamiento de audio en S0).


if __name__ == "__main__":
    main()
