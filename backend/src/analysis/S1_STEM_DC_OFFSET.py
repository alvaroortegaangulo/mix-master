# C:\mix-master\backend\src\analysis\S1_STEM_DC_OFFSET.py

import sys
from pathlib import Path

# Añadir .../src al sys.path para poder hacer "from utils ..."
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json
from typing import Dict, Any, List
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np  # Puede seguir siendo útil si las utils lo necesitan internamente

from utils.analysis_utils import (
    load_contract,
    get_temp_dir,
    load_audio_mono,
    compute_dc_offset,
    compute_peak_dbfs,
)


def analyze_stem(stem_path: Path) -> Dict[str, Any]:
    """
    Worker para ProcessPoolExecutor.

    Analiza un stem:
      - DC offset (lineal y en dB)
      - pico en dBFS
      - samplerate
    Devuelve un dict con la misma estructura que antes, para mantener
    compatibilidad con el resto del pipeline.
    """
    mono, sr = load_audio_mono(stem_path)

    dc_linear, dc_db = compute_dc_offset(mono)
    peak_dbfs = compute_peak_dbfs(mono)

    return {
        "file_name": stem_path.name,
        "file_path": str(stem_path),
        "samplerate_hz": sr,
        "dc_offset_linear": dc_linear,
        "dc_offset_db": dc_db,
        "peak_dbfs": peak_dbfs,
    }


def main() -> None:
    """
    Análisis para el contrato S1_STEM_DC_OFFSET.

    Uso esperado desde stage.py:
        python analysis/S1_STEM_DC_OFFSET.py S1_STEM_DC_OFFSET
    """
    if len(sys.argv) < 2:
        print("Uso: python S1_STEM_DC_OFFSET.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # debería ser "S1_STEM_DC_OFFSET"

    # 1) Cargar contrato y carpeta temp/<contract_id>
    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    temp_dir = get_temp_dir(contract_id, create=True)

    # 2) Listar stems (.wav) en temp/<contract_id>
    stem_files: List[Path] = sorted(
        p for p in temp_dir.glob("*.wav")
        if p.name.lower() != "full_song.wav"
    )

    stems_analysis: List[Dict[str, Any]] = []
    dc_offsets_db: List[float] = []
    peaks_dbfs: List[float] = []

    # --- Análisis paralelo por stem ---
    if stem_files:
        max_workers = min(4, os.cpu_count() or 1)
        with ProcessPoolExecutor(max_workers=max_workers) as ex:
            # ex.map mantiene el orden de stem_files
            results = list(ex.map(analyze_stem, stem_files))
    else:
        results = []

    # Recorremos resultados y calculamos agregados
    for stem_info in results:
        stems_analysis.append(stem_info)
        dc_offsets_db.append(stem_info["dc_offset_db"])
        peaks_dbfs.append(stem_info["peak_dbfs"])

    # 3) Métricas de sesión agregadas
    if dc_offsets_db:
        max_dc_offset_db = float(max(dc_offsets_db))   # el "peor" (más alto)
    else:
        max_dc_offset_db = float("-inf")

    if peaks_dbfs:
        max_peak_dbfs = float(max(peaks_dbfs))
    else:
        max_peak_dbfs = float("-inf")

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            # objetivos que check_metrics_limits.py deberá validar
            "dc_offset_max_db_target": metrics.get("dc_offset_max_db"),
            "true_peak_max_dbtp_target": metrics.get("true_peak_max_dbtp"),
            # medidas reales
            "max_dc_offset_db_measured": max_dc_offset_db,
            "max_peak_dbfs_measured": max_peak_dbfs,
        },
        "stems": stems_analysis,
    }

    # 4) Guardar JSON de análisis
    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    print(f"[S1_STEM_DC_OFFSET] Análisis completado. JSON guardado en: {output_path}")


if __name__ == "__main__":
    main()
