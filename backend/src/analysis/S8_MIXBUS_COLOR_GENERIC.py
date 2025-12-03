# C:\mix-master\backend\src\analysis\S8_MIXBUS_COLOR_GENERIC.py

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Any
import os

# --- hack para importar utils ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from stages.pipeline_context import PipelineContext

import json  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from utils.analysis_utils import (  # noqa: E402
    load_contract,
    get_temp_dir,
    sf_read_limited,
)
from utils.session_utils import load_session_config  # noqa: E402
from utils.color_utils import (  # noqa: E402
    compute_rms_dbfs,
    compute_true_peak_dbfs,
)


def _estimate_noise_floor_dbfs(y: np.ndarray) -> float:
    """
    Estima un noise floor aproximado como percentil bajo de niveles instantáneos.
    Muy pragmático, sólo para tener una referencia de cambio de ruido.
    """
    arr = np.asarray(y, dtype=np.float32)
    if arr.ndim > 1:
        arr = np.mean(arr, axis=1)

    if arr.size == 0:
        return float("-inf")

    eps = 1e-9
    inst_db = 20.0 * np.log10(np.abs(arr) + eps)
    # percentil 10 como aproximación de "cola baja"
    p10 = float(np.percentile(inst_db, 10.0))
    return p10


def _analyze_mixbus_color(full_song_path: Path) -> Dict[str, Any]:
    """

    Lee full_song.wav y calcula:
      - true peak
      - RMS
      - noise floor aproximado

    Devuelve:
      {
        "sr_mix": int | None,
        "pre_true_peak_dbtp": float,
        "pre_rms_dbfs": float,
        "noise_floor_dbfs": float,
        "error": str | None,
      }
    """
    try:
        y, sr = sf_read_limited(full_song_path, always_2d=False)
    except Exception as e:
        return {
            "sr_mix": None,
            "pre_true_peak_dbtp": float("-inf"),
            "pre_rms_dbfs": float("-inf"),
            "noise_floor_dbfs": float("-inf"),
            "error": f"[S8_MIXBUS_COLOR_GENERIC] Aviso: no se puede leer full_song.wav: {e}.",
        }

    pre_true_peak_dbtp = compute_true_peak_dbfs(y, oversample_factor=4)
    pre_rms_dbfs = compute_rms_dbfs(y)
    noise_floor_dbfs = _estimate_noise_floor_dbfs(y)

    return {
        "sr_mix": sr,
        "pre_true_peak_dbtp": pre_true_peak_dbtp,
        "pre_rms_dbfs": pre_rms_dbfs,
        "noise_floor_dbfs": noise_floor_dbfs,
        "error": None,
    }


def process(context: PipelineContext) -> None:
    """
    Análisis para S8_MIXBUS_COLOR_GENERIC.

    Uso desde stage.py:
        python analysis/S8_MIXBUS_COLOR_GENERIC.py S8_MIXBUS_COLOR_GENERIC
    """

    contract_id = context.contract_id  # "S8_MIXBUS_COLOR_GENERIC"

    # 1) Cargar contrato
    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    tp_min = float(metrics.get("target_true_peak_range_dbtp_min", -4.0))
    tp_max = float(metrics.get("target_true_peak_range_dbtp_max", -2.0))
    max_thd_percent = float(metrics.get("max_thd_percent", 3.0))
    max_sat_per_pass_db = float(limits.get("max_additional_saturation_per_pass", 1.0))

    # 2) temp/<contract_id> y session_config
    temp_dir = get_temp_dir(contract_id, create=True)
    cfg = load_session_config(contract_id)
    style_preset = cfg["style_preset"]

    # 3) Leer mixbus (full_song.wav)
    full_song_path = temp_dir / "full_song.wav"
    pre_true_peak_dbtp = float("-inf")
    pre_rms_dbfs = float("-inf")
    noise_floor_dbfs = float("-inf")
    sr_mix: int | None = None

    if full_song_path.exists():
        result = _analyze_mixbus_color(full_song_path)

        if result['error'] is not None:
            # Error al leer/procesar
            print(result['error'])
        else:
            sr_mix = result['sr_mix']
            pre_true_peak_dbtp = result['pre_true_peak_dbtp']
            pre_rms_dbfs = result['pre_rms_dbfs']
            noise_floor_dbfs = result['noise_floor_dbfs']

            print(
                f"[S8_MIXBUS_COLOR_GENERIC] full_song.wav analizado (sr={sr_mix}). "
                f"true_peak={pre_true_peak_dbtp:.2f} dBTP, RMS={pre_rms_dbfs:.2f} dBFS, "
                f"noise_floor={noise_floor_dbfs:.2f} dBFS."
            )
    else:
        print(
            f"[S8_MIXBUS_COLOR_GENERIC] Aviso: no existe {full_song_path}, "
            "no se puede medir color del mixbus."
        )

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "samplerate_hz": sr_mix,
            "pre_true_peak_dbtp": pre_true_peak_dbtp,
            "pre_rms_dbfs": pre_rms_dbfs,
            "noise_floor_dbfs": noise_floor_dbfs,
            "target_true_peak_range_dbtp_min": tp_min,
            "target_true_peak_range_dbtp_max": tp_max,
            "max_thd_percent": max_thd_percent,
            "max_additional_saturation_per_pass_db": max_sat_per_pass_db,
        },
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    print(
        f"[S8_MIXBUS_COLOR_GENERIC] Análisis completado. JSON: {output_path}"
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Uso: python {Path(__file__).name} <CONTRACT_ID>")
        sys.exit(1)

    from dataclasses import dataclass
    @dataclass
    class _MockContext:
        contract_id: str
        next_contract_id: str | None = None

    process(_MockContext(contract_id=sys.argv[1]))
