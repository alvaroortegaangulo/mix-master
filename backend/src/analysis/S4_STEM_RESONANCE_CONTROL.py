# C:\mix-master\backend\src\analysis\S4_STEM_RESONANCE_CONTROL.py

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple
import os

# --- hack para importar utils ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from utils.analysis_utils import (  # noqa: E402
    load_contract,
    get_temp_dir,
    sf_read_limited,
)
from utils.session_utils import load_session_config  # noqa: E402
from utils.resonance_utils import (  # noqa: E402
    compute_magnitude_spectrum,
    detect_resonances,
)


def _analyze_stem(
    args: Tuple[
        Path,
        str,
        float,
        float,
        float,
        float,
        float,
        int,
    ]
) -> Dict[str, Any]:
    """

    Recibe:
      - stem_path: ruta al .wav
      - inst_prof: instrument_profile
      - max_res_peak_db: umbral en dB por encima de la media local
      - max_cuts_db: límite máximo de corte (no usado directamente aquí, pero devuelto en JSON global)
      - fmin, fmax: rango de frecuencia a analizar
      - local_window_hz: ventana local para cálculo de resonancias
      - max_filters_per_band: máximo de resonancias a reportar

    Devuelve un dict de análisis por stem.
    """
    (
        stem_path,
        inst_prof,
        max_res_peak_db,
        max_cuts_db,
        fmin,
        fmax,
        local_window_hz,
        max_filters_per_band,
    ) = args

    fname = stem_path.name

    try:
        y, sr = sf_read_limited(stem_path, always_2d=False)
    except Exception as e:
        print(f"[S4_STEM_RESONANCE_CONTROL] Aviso: no se puede leer '{fname}': {e}.")
        return {
            "file_name": fname,
            "file_path": str(stem_path),
            "instrument_profile": inst_prof,
            "samplerate_hz": None,
            "resonances": [],
            "num_resonances_detected": 0,
        }

    freqs, mag_lin = compute_magnitude_spectrum(y, sr)
    resonances = detect_resonances(
        freqs=freqs,
        mag_lin=mag_lin,
        fmin=fmin,
        fmax=fmax,
        threshold_db=max_res_peak_db,
        local_window_hz=local_window_hz,
        max_resonances=max_filters_per_band,
    )

    num_res = len(resonances)

    return {
        "file_name": fname,
        "file_path": str(stem_path),
        "instrument_profile": inst_prof,
        "samplerate_hz": sr,
        "resonances": resonances,
        "num_resonances_detected": num_res,
    }


def main() -> None:
    """
    Análisis para el contrato S4_STEM_RESONANCE_CONTROL.

    Uso desde stage.py:
        python analysis/S4_STEM_RESONANCE_CONTROL.py S4_STEM_RESONANCE_CONTROL
    """
    if len(sys.argv) < 2:
        print("Uso: python S4_STEM_RESONANCE_CONTROL.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S4_STEM_RESONANCE_CONTROL"

    # 1) Cargar contrato
    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    max_res_peak_db = float(metrics.get("max_resonance_peak_db_above_local", 12.0))
    max_cuts_db = float(limits.get("max_resonant_cuts_db", 8.0))
    max_filters_per_band = int(limits.get("max_resonant_filters_per_band", 3))

    # Parámetros de banda (como en la versión original)
    BAND_FMIN = 200.0
    BAND_FMAX = 12000.0
    LOCAL_WINDOW_HZ = 200.0

    # 2) Directorio temp/<contract_id> y session_config
    temp_dir = get_temp_dir(contract_id, create=True)
    cfg = load_session_config(contract_id)
    style_preset = cfg["style_preset"]
    instrument_by_file = cfg["instrument_by_file"]

    # 3) Listar stems (.wav) de este stage (excluyendo full_song)
    stem_files: List[Path] = sorted(
        p for p in temp_dir.glob("*.wav")
        if p.name.lower() != "full_song.wav"
    )

    # 4) Preparar tareas para análisis paralelo
    tasks: List[
        Tuple[Path, str, float, float, float, float, float, int]
    ] = []

    for p in stem_files:
        fname = p.name
        inst_prof = instrument_by_file.get(fname, "Other")
        tasks.append(
            (
                p,
                inst_prof,
                max_res_peak_db,
                max_cuts_db,
                BAND_FMIN,
                BAND_FMAX,
                LOCAL_WINDOW_HZ,
                max_filters_per_band,
            )
        )

    # 5) Ejecutar análisis en paralelo
    if tasks:
        max_workers = min(4, os.cpu_count() or 1)
            stems_analysis: List[Dict[str, Any]] = list(ex.map(_analyze_stem, tasks))
    else:
        stems_analysis = []

    # 6) Agregados y logs por stem (como la versión original)
    total_resonances = 0
    for stem_entry in stems_analysis:
        num_res = stem_entry.get("num_resonances_detected", 0)
        total_resonances += num_res
        if num_res > 0 and stem_entry.get("samplerate_hz") is not None:
            print(
                f"[S4_STEM_RESONANCE_CONTROL] {stem_entry['file_name']}: detectadas "
                f"{num_res} resonancias por encima de {max_res_peak_db:.1f} dB sobre la "
                f"media local."
            )

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "max_resonance_peak_db_above_local": max_res_peak_db,
            "max_resonant_cuts_db": max_cuts_db,
            "max_resonant_filters_per_band": max_filters_per_band,
            "total_resonances_detected": total_resonances,
        },
        "stems": stems_analysis,
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    print(
        f"[S4_STEM_RESONANCE_CONTROL] Análisis completado para {len(stems_analysis)} stems. "
        f"Resonancias totales detectadas={total_resonances}. JSON: {output_path}"
    )


if __name__ == "__main__":
    main()
