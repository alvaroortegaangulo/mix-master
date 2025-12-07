from utils.logger import logger
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

import numpy as np  # Puede seguir siendo útil si las utils lo necesitan internamente

from utils.analysis_utils import (
    load_contract,
    get_temp_dir,
    sf_read_limited,
    compute_dc_offset,
    compute_peak_dbfs,
)


def analyze_stem(stem_path: Path) -> Dict[str, Any]:
    """

    Analiza un stem:
      - DC offset (lineal y en dB)
      - pico en dBFS
      - samplerate
    Devuelve un dict con la misma estructura que antes, para mantener
    compatibilidad con el resto del pipeline.
    """
    # Leer en stereo/multicanal siempre para detectar DC offset per channel
    # y evitar cancelación de fase (bug fix).
    data, sr = sf_read_limited(stem_path, always_2d=True)

    if not isinstance(data, np.ndarray):
        data = np.array(data, dtype=np.float32)
    else:
        data = data.astype(np.float32)

    # Calcular DC lineal por canal
    # data es (samples, channels)
    if data.size == 0:
        dc_per_channel = []
        peak_val = 0.0
    else:
        dc_per_channel = np.mean(data, axis=0).tolist()
        peak_val = float(np.max(np.abs(data)))

    # peak en dBFS
    if peak_val > 0.0:
        peak_dbfs = float(20.0 * np.log10(peak_val))
    else:
        peak_dbfs = float("-inf")

    # Calcular dc_offset_db "peor caso" (el canal con mayor DC absoluto)
    # y también dc_linear "peor caso" para la métrica escalar si se necesita (aunque retornaremos la lista)
    if not dc_per_channel:
        max_dc_abs = 0.0
        dc_linear_worst = 0.0
    else:
        # Encontramos el canal con mayor offset absoluto
        max_dc_abs = 0.0
        dc_linear_worst = 0.0
        for val in dc_per_channel:
            if abs(val) > max_dc_abs:
                max_dc_abs = abs(val)
                dc_linear_worst = val

    # Convertir max_dc_abs a dB
    eps = 1e-12
    if max_dc_abs < eps:
        dc_db = -120.0
    else:
        dc_db = 20.0 * np.log10(max_dc_abs)

    return {
        "file_name": stem_path.name,
        "file_path": str(stem_path),
        "samplerate_hz": sr,
        "dc_offset_linear": dc_per_channel, # Ahora es lista de floats
        "dc_offset_db": dc_db,              # Peor caso en dB
        "peak_dbfs": peak_dbfs,
    }


def main() -> None:
    """
    Análisis para el contrato S1_STEM_DC_OFFSET.

    Uso esperado desde stage.py:
        python analysis/S1_STEM_DC_OFFSET.py S1_STEM_DC_OFFSET
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S1_STEM_DC_OFFSET.py <CONTRACT_ID>")
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

    # Análisis por stem en serie
    results = [analyze_stem(p) for p in stem_files] if stem_files else []

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

    # logger.logger.debug("Analysis complete")


if __name__ == "__main__":
    main()
