# C:\mix-master\backend\src\analysis\S4_STEM_RESONANCE_CONTROL.py

from __future__ import annotations
from utils.logger import logger

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


def _to_mono(y: np.ndarray) -> np.ndarray:
    arr = np.asarray(y, dtype=np.float32)
    if arr.ndim > 1:
        return np.mean(arr, axis=1).astype(np.float32)
    return arr.astype(np.float32)


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
    Analiza un stem y detecta resonancias con el detector de utils.resonance_utils.
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
        logger.logger.info(f"[S4_STEM_RESONANCE_CONTROL] Aviso: no se puede leer '{fname}': {e}.")
        return {
            "file_name": fname,
            "file_path": str(stem_path),
            "instrument_profile": inst_prof,
            "samplerate_hz": None,
            "resonances": [],
            "num_resonances_detected": 0,
        }

    y_mono = _to_mono(np.asarray(y, dtype=np.float32))

    freqs, mag_lin = compute_magnitude_spectrum(y_mono, int(sr))
    resonances = detect_resonances(
        freqs=freqs,
        mag_lin=mag_lin,
        fmin=float(fmin),
        fmax=float(fmax),
        threshold_db=float(max_res_peak_db),
        local_window_hz=float(local_window_hz),
        max_resonances=int(max_filters_per_band),
    )

    return {
        "file_name": fname,
        "file_path": str(stem_path),
        "instrument_profile": inst_prof,
        "samplerate_hz": int(sr),
        "resonances": resonances,
        "num_resonances_detected": int(len(resonances)),
    }


def main() -> None:
    """
    Análisis para el contrato S4_STEM_RESONANCE_CONTROL.
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S4_STEM_RESONANCE_CONTROL.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S4_STEM_RESONANCE_CONTROL"

    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {}) or {}
    limits: Dict[str, Any] = contract.get("limits", {}) or {}
    stage_id: str | None = contract.get("stage_id")

    max_res_peak_db = float(metrics.get("max_resonance_peak_db_above_local", 12.0))
    max_cuts_db = float(limits.get("max_resonant_cuts_db", 8.0))
    max_filters_per_band = int(limits.get("max_resonant_filters_per_band", 3))

    # Banda (puedes parametrizarlo en contrato si quieres)
    BAND_FMIN = float(metrics.get("res_band_fmin_hz", 200.0))
    BAND_FMAX = float(metrics.get("res_band_fmax_hz", 12000.0))
    LOCAL_WINDOW_HZ = float(metrics.get("res_local_window_hz", 200.0))

    temp_dir = get_temp_dir(contract_id, create=True)
    cfg = load_session_config(contract_id)
    style_preset = cfg["style_preset"]
    instrument_by_file = cfg["instrument_by_file"]

    stem_files: List[Path] = sorted(
        p for p in temp_dir.glob("*.wav")
        if p.name.lower() != "full_song.wav"
    )

    tasks: List[Tuple[Path, str, float, float, float, float, float, int]] = []
    for p in stem_files:
        inst_prof = instrument_by_file.get(p.name, "Other")
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

    stems_analysis: List[Dict[str, Any]] = list(map(_analyze_stem, tasks)) if tasks else []

    total_resonances = sum(int(s.get("num_resonances_detected", 0) or 0) for s in stems_analysis)

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
            "res_band_fmin_hz": BAND_FMIN,
            "res_band_fmax_hz": BAND_FMAX,
            "res_local_window_hz": LOCAL_WINDOW_HZ,
            "total_resonances_detected": int(total_resonances),
        },
        "stems": stems_analysis,
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    logger.logger.info(
        f"[S4_STEM_RESONANCE_CONTROL] Análisis completado para {len(stems_analysis)} stems. "
        f"Resonancias totales detectadas={total_resonances}. JSON: {output_path}"
    )


if __name__ == "__main__":
    main()
