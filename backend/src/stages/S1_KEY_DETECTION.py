# C:\mix-master\backend\src\stages\S1_KEY_DETECTION.py

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Any, List

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import os  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402

from utils.analysis_utils import get_temp_dir


def load_analysis(contract_id: str) -> Dict[str, Any]:
    """
    Carga el JSON de análisis generado por analysis\\S1_KEY_DETECTION.py.
    """
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data


# ---------------------------------------------------------------------
# Worker para ProcessPoolExecutor: formatea una línea de resumen de stem
# ---------------------------------------------------------------------
def _format_stem_summary(stem: Dict[str, Any]) -> str:
    """
    Devuelve una línea de texto con el resumen de un stem,
    pensada para imprimirse en el listado del stage.
    """
    file_name = stem.get("file_name")
    inst_profile = stem.get("instrument_profile")
    return f"      * {file_name} [{inst_profile}]"


def main() -> None:
    """
    Stage S1_KEY_DETECTION:
      - Lee analysis_S1_KEY_DETECTION.json.
      - Muestra por pantalla la tonalidad detectada.
      - No modifica stems (passthrough), para integrarse con stage.py (copy_stems + mixdown_stems).
    """
    if len(sys.argv) < 2:
        print("Uso: python S1_KEY_DETECTION.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S1_KEY_DETECTION"

    analysis = load_analysis(contract_id)

    session: Dict[str, Any] = analysis.get("session", {})
    stems: List[Dict[str, Any]] = analysis.get("stems", [])

    key_name = session.get("key_name")
    key_mode = session.get("key_mode")
    key_root_pc = session.get("key_root_pc")
    confidence = session.get("key_detection_confidence")
    scale_pcs = session.get("scale_pitch_classes")

    print("[S1_KEY_DETECTION] Resumen de análisis:")
    print(f"  - Tonalidad global: {key_name} (modo={key_mode}, root_pc={key_root_pc})")
    print(f"  - Confianza: {confidence}")
    print(f"  - Escala (pitch classes, C=0): {scale_pcs}")
    print(f"  - Número de stems analizados: {len(stems)}")
    print("  - Stems:")

    if stems:
        # Usamos ProcessPoolExecutor para construir las líneas de resumen en paralelo.
        max_workers = min(4, os.cpu_count() or 1)
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            for line in executor.map(_format_stem_summary, stems):
                print(line)
    else:
        print("      (ningún stem detectado en el análisis)")

    # No tocamos audio. stage.py hará:
    #   - re-análisis
    #   - check_metrics_limits (sin check específico -> éxito por defecto)
    #   - copy_stems + mixdown_stems para el siguiente contrato.

    print("[S1_KEY_DETECTION] Stage completado (passthrough).")


if __name__ == "__main__":
    main()
