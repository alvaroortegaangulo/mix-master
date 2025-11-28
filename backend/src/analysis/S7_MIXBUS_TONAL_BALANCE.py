# C:\mix-master\backend\src\analysis\S7_MIXBUS_TONAL_BALANCE.py

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Any
import os
from concurrent.futures import ProcessPoolExecutor

# --- hack para importar utils ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import soundfile as sf  # noqa: E402

from utils.analysis_utils import (  # noqa: E402
    load_contract,
    get_temp_dir,
)
from utils.session_utils import load_session_config  # noqa: E402
from utils.tonal_balance_utils import (  # noqa: E402
    get_freq_bands,
    compute_band_energies,
    get_style_tonal_profile,
    compute_tonal_error,
)

def _analyze_mixbus(full_song_path: Path) -> Dict[str, Any]:
    """
    Worker para ProcessPoolExecutor.

    Lee full_song.wav y calcula las energías por banda.
    Devuelve:
      - band_current_db: dict band_id -> nivel dB
      - sr_mix: samplerate
      - error: mensaje de error o None
    """
    try:
        y, sr = sf.read(full_song_path, always_2d=False)
    except Exception as e:
        return {
            "band_current_db": None,
            "sr_mix": None,
            "error": f"[S7_MIXBUS_TONAL_BALANCE] Aviso: no se puede leer full_song.wav: {e}.",
        }

    band_current_db = compute_band_energies(y, sr)
    return {
        "band_current_db": band_current_db,
        "sr_mix": sr,
        "error": None,
    }


def main() -> None:
    """
    Análisis para el contrato S7_MIXBUS_TONAL_BALANCE.

    Uso desde stage.py:
        python S7_MIXBUS_TONAL_BALANCE.py S7_MIXBUS_TONAL_BALANCE
    """
    if len(sys.argv) < 2:
        print("Uso: python S7_MIXBUS_TONAL_BALANCE.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S7_MIXBUS_TONAL_BALANCE"

    # 1) Cargar contrato
    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    max_tonal_error_db = float(metrics.get("max_tonal_balance_error_db", 3.0))
    max_eq_change_db = float(limits.get("max_eq_change_db_per_band_per_pass", 1.5))

    # 2) temp/<contract_id> y session_config
    temp_dir = get_temp_dir(contract_id, create=True)
    cfg = load_session_config(contract_id)
    style_preset = cfg["style_preset"]

    # 3) Leer mixbus (full_song.wav)
    full_song_path = temp_dir / "full_song.wav"
    band_current_db: Dict[str, float] = {}
    band_target_db: Dict[str, float] = {}
    band_error_db: Dict[str, float] = {}
    error_rms_db: float = 0.0
    sr_mix: int | None = None

    freq_bands = get_freq_bands()
    style_profile = get_style_tonal_profile(style_preset)

    if full_song_path.exists():
        # Procesar full_song.wav en un ProcessPoolExecutor (aunque sea una única tarea)
        max_workers = min(4, os.cpu_count() or 1)
        with ProcessPoolExecutor(max_workers=max_workers) as ex:
            result = list(ex.map(_analyze_mixbus, [full_song_path]))[0]

        if result["error"] is not None:
            # Error al leer o procesar el mixbus
            print(result["error"])
            band_current_db = {b["id"]: float("-inf") for b in freq_bands}
            band_target_db = style_profile
            band_error_db = {}
            error_rms_db = 0.0
        else:
            sr_mix = result["sr_mix"]
            band_current_db = result["band_current_db"]
            band_target_db = style_profile
            band_error_db, error_rms_db = compute_tonal_error(
                band_current_db, band_target_db
            )
            print(
                f"[S7_MIXBUS_TONAL_BALANCE] full_song.wav analizado (sr={sr_mix}). "
                f"error_RMS={error_rms_db:.2f} dB."
            )
    else:
        print(
            f"[S7_MIXBUS_TONAL_BALANCE] Aviso: no existe {full_song_path}, "
            "no se puede medir el tonal balance del mixbus."
        )
        band_current_db = {b["id"]: float("-inf") for b in freq_bands}
        band_target_db = style_profile
        band_error_db = {}
        error_rms_db = 0.0

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "samplerate_hz": sr_mix,
            "max_tonal_balance_error_db": max_tonal_error_db,
            "max_eq_change_db_per_band_per_pass": max_eq_change_db,
            "tonal_bands": {
                "bands": freq_bands,
                "current_band_db": band_current_db,
                "target_band_db": band_target_db,
                "error_by_band_db": band_error_db,
                "error_rms_db": error_rms_db,
            },
        },
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    print(
        f"[S7_MIXBUS_TONAL_BALANCE] Análisis completado. error_RMS={error_rms_db:.2f} dB. "
        f"JSON: {output_path}"
    )


if __name__ == "__main__":
    main()
