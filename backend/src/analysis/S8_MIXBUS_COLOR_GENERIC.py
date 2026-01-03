from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any

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
from utils.color_utils import (  # noqa: E402
    compute_rms_dbfs,
    compute_true_peak_dbfs,
)


def _estimate_noise_floor_dbfs(y: np.ndarray, sr: int) -> float:
    """
    Estimación pragmática del noise floor basada en RMS por frames.
    - Mono (promedio si es estéreo).
    - RMS por ventanas cortas (50 ms).
    - Percentil 10 del RMS (dBFS) como "cola baja" robusta.

    Nota: esto NO separa ruido real de pasajes suaves; sirve como proxy comparativo
    entre PRE/POST para detectar incrementos anómalos.
    """
    arr = np.asarray(y, dtype=np.float32)
    if arr.ndim > 1:
        arr = np.mean(arr, axis=1).astype(np.float32)

    n = int(arr.size)
    if n <= 0 or sr <= 0:
        return float("-inf")

    frame_len = max(256, int(round(0.050 * sr)))  # 50 ms
    hop = frame_len  # no solapado para ser barato/estable

    eps = 1e-12
    rms_vals: list[float] = []
    for start in range(0, n - frame_len + 1, hop):
        seg = arr[start:start + frame_len]
        rms = float(np.sqrt(np.mean(seg * seg) + eps))
        rms_vals.append(rms)

    if not rms_vals:
        rms = float(np.sqrt(np.mean(arr * arr) + eps))
        return 20.0 * np.log10(rms + eps)

    p10 = float(np.percentile(np.array(rms_vals, dtype=np.float32), 10.0))
    return 20.0 * np.log10(p10 + eps)


def _analyze_mixbus_color(full_song_path: Path) -> Dict[str, Any]:
    """
    Lee full_song.wav y calcula:
      - true peak
      - RMS
      - noise floor proxy
    """
    try:
        y, sr = sf_read_limited(full_song_path, always_2d=False)
    except Exception as e:
        return {
            "sr_mix": None,
            "pre_true_peak_dbtp": float("-inf"),
            "pre_rms_dbfs": float("-inf"),
            "pre_noise_floor_dbfs": float("-inf"),
            "pre_snr_db": None,
            "error": f"[S8_MIXBUS_COLOR_GENERIC] Aviso: no se puede leer full_song.wav: {e}.",
        }

    pre_true_peak_dbtp = compute_true_peak_dbfs(y, oversample_factor=4)
    pre_rms_dbfs = compute_rms_dbfs(y)
    pre_noise_floor_dbfs = _estimate_noise_floor_dbfs(y, int(sr))

    pre_snr_db = None
    if pre_noise_floor_dbfs != float("-inf") and pre_true_peak_dbtp != float("-inf"):
        pre_snr_db = float(pre_true_peak_dbtp - pre_noise_floor_dbfs)

    return {
        "sr_mix": int(sr),
        "pre_true_peak_dbtp": float(pre_true_peak_dbtp),
        "pre_rms_dbfs": float(pre_rms_dbfs),
        "pre_noise_floor_dbfs": float(pre_noise_floor_dbfs),
        "pre_snr_db": pre_snr_db,
        "error": None,
    }


def main() -> None:
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S8_MIXBUS_COLOR_GENERIC.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]

    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {}) or {}
    limits: Dict[str, Any] = contract.get("limits", {}) or {}
    stage_id: str | None = contract.get("stage_id")

    tp_min = float(metrics.get("target_true_peak_range_dbtp_min", -4.0))
    tp_max = float(metrics.get("target_true_peak_range_dbtp_max", -2.0))
    max_thd_percent = float(metrics.get("max_thd_percent", 3.0))
    max_sat_per_pass_db = float(limits.get("max_additional_saturation_per_pass", 1.0))

    temp_dir = get_temp_dir(contract_id, create=True)
    cfg = load_session_config(contract_id)
    style_preset = cfg["style_preset"]

    full_song_path = temp_dir / "full_song.wav"

    sr_mix: int | None = None
    pre_true_peak_dbtp = float("-inf")
    pre_rms_dbfs = float("-inf")
    pre_noise_floor_dbfs = float("-inf")
    pre_snr_db = None

    if full_song_path.exists():
        result = _analyze_mixbus_color(full_song_path)
        if result["error"] is not None:
            logger.logger.info(result["error"])
        else:
            sr_mix = result["sr_mix"]
            pre_true_peak_dbtp = result["pre_true_peak_dbtp"]
            pre_rms_dbfs = result["pre_rms_dbfs"]
            pre_noise_floor_dbfs = result["pre_noise_floor_dbfs"]
            pre_snr_db = result["pre_snr_db"]

            logger.logger.info(
                f"[S8_MIXBUS_COLOR_GENERIC] full_song.wav analizado (sr={sr_mix}). "
                f"true_peak={pre_true_peak_dbtp:.2f} dBTP, RMS={pre_rms_dbfs:.2f} dBFS, "
                f"noise_floor≈{pre_noise_floor_dbfs:.2f} dBFS."
            )
    else:
        logger.logger.info(
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
            "pre_noise_floor_dbfs": pre_noise_floor_dbfs,
            "pre_snr_db": pre_snr_db,
            "target_true_peak_range_dbtp_min": tp_min,
            "target_true_peak_range_dbtp_max": tp_max,
            "max_thd_percent": max_thd_percent,
            "max_additional_saturation_per_pass_db": max_sat_per_pass_db,
        },
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    logger.logger.info(f"[S8_MIXBUS_COLOR_GENERIC] Análisis completado. JSON: {output_path}")


if __name__ == "__main__":
    main()
