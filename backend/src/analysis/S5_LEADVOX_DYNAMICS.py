# C:\mix-master\backend\src\analysis\S5_LEADVOX_DYNAMICS.py

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
from utils.dynamics_utils import compute_crest_factor_db  # noqa: E402


def _is_lead_vocal_profile(inst: str | None, lead_id: str) -> bool:
    """
    Determina si un instrument_profile se considera 'lead vocal' para este contrato.

    Regla mínima:
      - Igual al instrument_id del contrato (p.ej. 'Lead_Vocal_Melodic'), o
      - Empieza por 'Lead_Vocal'.
    """
    if not inst:
        return False
    if inst == lead_id:
        return True
    if inst.startswith("Lead_Vocal"):
        return True
    return False


def _analyze_stem(
    args: Tuple[Path, str, bool]
) -> Dict[str, Any]:
    """

    Recibe:
      - stem_path: ruta al .wav
      - inst_prof: instrument_profile
      - is_lead: si se considera lead vocal

    Devuelve un dict stem_entry con la misma estructura que la versión secuencial,
    añadiendo un campo "error" para que el proceso principal imprima los avisos.
    """
    stem_path, inst_prof, is_lead = args
    fname = stem_path.name

    try:
        y, sr = sf_read_limited(stem_path, always_2d=False)
    except Exception as e:
        return {
            "file_name": fname,
            "file_path": str(stem_path),
            "instrument_profile": inst_prof,
            "is_lead_vocal": is_lead,
            "samplerate_hz": None,
            "pre_rms_dbfs": None,
            "pre_peak_dbfs": None,
            "pre_crest_factor_db": None,
            "error": f"[S5_LEADVOX_DYNAMICS] Aviso: no se puede leer '{fname}': {e}.",
        }

    rms_db, peak_db, crest_db = compute_crest_factor_db(y)

    return {
        "file_name": fname,
        "file_path": str(stem_path),
        "instrument_profile": inst_prof,
        "is_lead_vocal": is_lead,
        "samplerate_hz": sr,
        "pre_rms_dbfs": rms_db,
        "pre_peak_dbfs": peak_db,
        "pre_crest_factor_db": crest_db,
        "error": None,
    }


def main() -> None:
    """
    Análisis para el contrato S5_LEADVOX_DYNAMICS.

    Uso desde stage.py:
        python analysis/S5_LEADVOX_DYNAMICS.py S5_LEADVOX_DYNAMICS
    """
    if len(sys.argv) < 2:
        print("Uso: python S5_LEADVOX_DYNAMICS.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S5_LEADVOX_DYNAMICS"

    # 1) Cargar contrato
    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    crest_min = float(metrics.get("target_crest_factor_db_min", 6.0))
    crest_max = float(metrics.get("target_crest_factor_db_max", 12.0))
    max_avg_gr = float(metrics.get("max_average_gain_reduction_db", 6.0))
    max_auto_change = float(limits.get("max_vocal_automation_change_db_per_pass", 3.0))

    # 2) Directorio temp/<contract_id> y session_config
    temp_dir = get_temp_dir(contract_id, create=True)
    cfg = load_session_config(contract_id)
    style_preset = cfg["style_preset"]
    instrument_by_file = cfg["instrument_by_file"]

    lead_profile_id = contract.get("instrument_id", "Lead_Vocal_Melodic")

    # 3) Listar stems (.wav) (excluyendo full_song.wav)
    stem_files: List[Path] = sorted(
        p for p in temp_dir.glob("*.wav")
        if p.name.lower() != "full_song.wav"
    )

    # 4) Preparar tareas para análisis paralelo
    tasks: List[Tuple[Path, str, bool]] = []
    for p in stem_files:
        fname = p.name
        inst_prof = instrument_by_file.get(fname, "Other")
        is_lead = _is_lead_vocal_profile(inst_prof, lead_profile_id)
        tasks.append((p, inst_prof, is_lead))

    # 5) Ejecutar análisis en paralelo
    if tasks:
        max_workers = min(4, os.cpu_count() or 1)
            stems_analysis: List[Dict[str, Any]] = list(ex.map(_analyze_stem, tasks))
    else:
        stems_analysis = []

    # 6) Logs y conteo de stems lead (replicando comportamiento original)
    n_lead = 0
    for stem_entry in stems_analysis:
        fname = stem_entry["file_name"]
        is_lead = stem_entry["is_lead_vocal"]
        rms_db = stem_entry["pre_rms_dbfs"]
        peak_db = stem_entry["pre_peak_dbfs"]
        crest_db = stem_entry["pre_crest_factor_db"]
        err = stem_entry.get("error")

        if err is not None:
            # Error de lectura
            print(err)
            continue

        # Solo contamos como lead si hay métricas válidas
        if is_lead and crest_db is not None:
            n_lead += 1

        if rms_db is None or peak_db is None or crest_db is None:
            # No debería ocurrir aquí salvo que se cambie compute_crest_factor_db
            continue

        if is_lead:
            print(
                f"[S5_LEADVOX_DYNAMICS] LEAD {fname}: "
                f"RMS={rms_db:.2f} dBFS, peak={peak_db:.2f} dBFS, crest={crest_db:.2f} dB."
            )
        else:
            print(
                f"[S5_LEADVOX_DYNAMICS] {fname}: "
                f"RMS={rms_db:.2f} dBFS, peak={peak_db:.2f} dBFS, crest={crest_db:.2f} dB."
            )

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "target_crest_factor_min_db": crest_min,
            "target_crest_factor_max_db": crest_max,
            "max_average_gain_reduction_db": max_avg_gr,
            "max_vocal_automation_change_db_per_pass": max_auto_change,
            "lead_profile_id": lead_profile_id,
            "num_lead_vocal_stems": n_lead,
        },
        "stems": stems_analysis,
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    print(
        f"[S5_LEADVOX_DYNAMICS] Análisis completado para {len(stems_analysis)} stems "
        f"(lead_vocals={n_lead}). JSON: {output_path}"
    )


if __name__ == "__main__":
    main()
