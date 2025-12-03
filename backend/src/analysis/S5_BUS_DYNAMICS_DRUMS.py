# C:\mix-master\backend\src\analysis\S5_BUS_DYNAMICS_DRUMS.py

from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any, List
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
from utils.profiles_utils import get_instrument_family  # noqa: E402
from utils.dynamics_utils import compute_crest_factor_db  # noqa: E402


def _load_drum_mono(stem_path: Path) -> Dict[str, Any]:
    """

    Lee un stem, lo pasa a mono (float32) y devuelve un dict:
      {
        "file_name": str,
        "data": np.ndarray | None,
        "sr": int | None,
        "error": str | None,
      }
    """
    fname = stem_path.name
    try:
        y, sr = sf_read_limited(stem_path, always_2d=False)
    except Exception as e:
        return {
            "file_name": fname,
            "data": None,
            "sr": None,
            "error": f"[S5_BUS_DYNAMICS_DRUMS] Aviso: no se puede leer '{fname}': {e}.",
        }

    if not isinstance(y, np.ndarray):
        y = np.asarray(y, dtype=np.float32)
    else:
        y = y.astype(np.float32)

    if y.ndim > 1:
        y_mono = np.mean(y, axis=1)
    else:
        y_mono = y

    return {
        "file_name": fname,
        "data": y_mono,
        "sr": sr,
        "error": None,
    }


def main() -> None:
    """
    Análisis para el contrato S5_BUS_DYNAMICS_DRUMS.

    Uso desde stage.py:
        python analysis/S5_BUS_DYNAMICS_DRUMS.py S5_BUS_DYNAMICS_DRUMS
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S5_BUS_DYNAMICS_DRUMS.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S5_BUS_DYNAMICS_DRUMS"

    # 1) Cargar contrato
    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    target_family = str(metrics.get("target_family", "Drums"))
    crest_min = float(metrics.get("target_crest_factor_db_min", 6.0))
    crest_max = float(metrics.get("target_crest_factor_db_max", 10.0))
    max_avg_gr = float(limits.get("max_average_gain_reduction_db", 3.0))

    # 2) Directorio temp/<contract_id> y session_config
    temp_dir = get_temp_dir(contract_id, create=True)
    cfg = load_session_config(contract_id)
    style_preset = cfg["style_preset"]
    instrument_by_file = cfg["instrument_by_file"]

    # 3) Listar stems y filtrar los de familia Drums
    all_files: List[Path] = sorted(
        p for p in temp_dir.glob("*.wav")
        if p.name.lower() != "full_song.wav"
    )

    drum_files: List[Path] = []
    stems_analysis: List[Dict[str, Any]] = []
    sr_ref: int | None = None

    for p in all_files:
        fname = p.name
        inst_prof = instrument_by_file.get(fname, "Other")
        family = get_instrument_family(inst_prof)

        is_target = (family == target_family)

        stem_entry: Dict[str, Any] = {
            "file_name": fname,
            "file_path": str(p),
            "instrument_profile": inst_prof,
            "family": family,
            "is_target_family": is_target,
        }
        stems_analysis.append(stem_entry)

        if not is_target:
            continue

        drum_files.append(p)

    bus_rms_db = float("-inf")
    bus_peak_db = float("-inf")
    bus_crest_db = 0.0

    # 4) Construir mix de bus Drums y calcular crest
    if drum_files:
        # Carga + mono en paralelo
        max_workers = min(4, os.cpu_count() or 1)
        results: List[Dict[str, Any]] = [_load_drum_mono(f) for f in drum_files]

        buffers: List[np.ndarray] = []
        max_len = 0

        for res in results:
            fname = res["file_name"]
            err = res["error"]
            y_mono = res["data"]
            sr = res["sr"]

            if err is not None:
                # Mantenemos el mismo tipo de aviso que antes
                logger.logger.info(err)
                continue

            if y_mono is None or sr is None:
                continue

            if sr_ref is None:
                sr_ref = sr
            elif sr != sr_ref:
                logger.logger.info(
                    f"[S5_BUS_DYNAMICS_DRUMS] Aviso: samplerate inconsistente en {fname} "
                    f"(sr={sr}, ref={sr_ref}); se omite del bus."
                )
                continue

            buffers.append(y_mono)
            max_len = max(max_len, y_mono.shape[0])

        if buffers and max_len > 0:
            bus = np.zeros(max_len, dtype=np.float32)
            for y_mono in buffers:
                n = y_mono.shape[0]
                bus[:n] += y_mono

            bus_rms_db, bus_peak_db, bus_crest_db = compute_crest_factor_db(bus)
            logger.logger.info(
                f"[S5_BUS_DYNAMICS_DRUMS] Bus {target_family}: "
                f"RMS={bus_rms_db:.2f} dBFS, peak={bus_peak_db:.2f} dBFS, "
                f"crest={bus_crest_db:.2f} dB (stems={len(buffers)})."
            )
        else:
            logger.logger.info(
                f"[S5_BUS_DYNAMICS_DRUMS] Sin buffers válidos para familia {target_family}; "
                f"no se calcula crest."
            )
    else:
        logger.logger.info(
            f"[S5_BUS_DYNAMICS_DRUMS] No se han encontrado stems de familia {target_family} "
            f"en {temp_dir}."
        )

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "target_family": target_family,
            "target_crest_factor_min_db": crest_min,
            "target_crest_factor_max_db": crest_max,
            "max_average_gain_reduction_db": max_avg_gr,
            "bus_samplerate_hz": sr_ref,
            "bus_rms_dbfs": bus_rms_db,
            "bus_peak_dbfs": bus_peak_db,
            "bus_crest_factor_db": bus_crest_db,
            "num_drum_stems": len(drum_files),
        },
        "stems": stems_analysis,
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    logger.logger.info(
        f"[S5_BUS_DYNAMICS_DRUMS] Análisis completado para {len(stems_analysis)} stems "
        f"(familia objetivo={target_family}, en bus={len(drum_files)}). JSON: {output_path}"
    )


if __name__ == "__main__":
    main()
