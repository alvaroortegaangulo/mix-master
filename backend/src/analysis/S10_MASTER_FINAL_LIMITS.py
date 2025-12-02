# C:\mix-master\backend\src\analysis\S10_MASTER_FINAL_LIMITS.py

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

import json  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from utils.analysis_utils import (  # noqa: E402
    load_contract,
    get_temp_dir,
    sf_read_limited,
)
from utils.session_utils import load_session_config  # noqa: E402
from utils.loudness_utils import compute_lufs_and_lra  # noqa: E402
from utils.color_utils import compute_true_peak_dbfs  # noqa: E402
from utils.mastering_profiles_utils import get_mastering_profile  # noqa: E402


def _compute_channel_lufs_diff(y: np.ndarray, sr: int) -> Dict[str, float]:
    """
    Calcula LUFS por canal (L/R) y la diferencia absoluta.
    Devuelve dict con:
        - lufs_L
        - lufs_R
        - channel_loudness_diff_db
    """
    arr = np.asarray(y, dtype=np.float32)
    if arr.ndim == 1:
        # Mono: L y R iguales
        lufs_L, _ = compute_lufs_and_lra(arr, sr)
        lufs_R = lufs_L
        diff = 0.0
        return {
            "lufs_L": lufs_L,
            "lufs_R": lufs_R,
            "channel_loudness_diff_db": diff,
        }

    if arr.ndim == 2 and arr.shape[1] >= 2:
        L = arr[:, 0]
        R = arr[:, 1]
        lufs_L, _ = compute_lufs_and_lra(L, sr)
        lufs_R, _ = compute_lufs_and_lra(R, sr)
        if lufs_L == float("-inf") or lufs_R == float("-inf"):
            diff = 0.0
        else:
            diff = abs(lufs_L - lufs_R)
        return {
            "lufs_L": lufs_L,
            "lufs_R": lufs_R,
            "channel_loudness_diff_db": diff,
        }

    # MÃ¡s de 2 canales: usamos primer par como L/R
    L = arr[:, 0]
    R = arr[:, 1]
    lufs_L, _ = compute_lufs_and_lra(L, sr)
    lufs_R, _ = compute_lufs_and_lra(R, sr)
    diff = abs(lufs_L - lufs_R) if (lufs_L != float("-inf") and lufs_R != float("-inf")) else 0.0
    return {
        "lufs_L": lufs_L,
        "lufs_R": lufs_R,
        "channel_loudness_diff_db": diff,
    }


def _compute_stereo_correlation(y: np.ndarray) -> float:
    """
    CorrelaciÃ³n estÃ©reo global simple entre L y R (Pearson).
    Si es mono, devuelve 1.0.
    """
    arr = np.asarray(y, dtype=np.float32)
    if arr.ndim == 1:
        return 1.0
    if arr.ndim == 2 and arr.shape[1] >= 2:
        L = arr[:, 0].astype(np.float32)
        R = arr[:, 1].astype(np.float32)
    else:
        # mÃ¡s canales: usamos primero par
        L = arr[:, 0].astype(np.float32)
        R = arr[:, 1].astype(np.float32)

    Lm = L - np.mean(L)
    Rm = R - np.mean(R)
    denom = float(np.sqrt(np.sum(Lm**2) * np.sum(Rm**2)) + 1e-12)
    if denom <= 0.0:
        return 0.0
    corr = float(np.sum(Lm * Rm) / denom)
    # clamp
    return max(-1.0, min(1.0, corr))


def _analyze_master_final(full_song_path: Path) -> Dict[str, Any]:
    """

    Lee full_song.wav y calcula:
      - true_peak_dbtp
      - lufs_integrated
      - lra
      - lufs por canal L/R y diferencia
      - correlaciÃ³n estÃ©reo

    Devuelve un dict con mÃ©tricas + posible mensaje de error.
    """
    try:
        y, sr = sf_read_limited(full_song_path, always_2d=False)
    except Exception as e:
        return {
            "sr_mix": None,
            "true_peak_dbtp": float("-inf"),
            "lufs_integrated": float("-inf"),
            "lra": 0.0,
            "channel_lufs_L": float("-inf"),
            "channel_lufs_R": float("-inf"),
            "channel_diff_db": 0.0,
            "correlation": 1.0,
            "error": f"[S10_MASTER_FINAL_LIMITS] Aviso: no se puede leer full_song.wav: {e}.",
        }

    true_peak_dbtp = compute_true_peak_dbfs(y, oversample_factor=4)
    lufs_integrated, lra = compute_lufs_and_lra(y, sr)
    ch_info = _compute_channel_lufs_diff(y, sr)
    correlation = _compute_stereo_correlation(y)

    return {
        "sr_mix": sr,
        "true_peak_dbtp": true_peak_dbtp,
        "lufs_integrated": lufs_integrated,
        "lra": lra,
        "channel_lufs_L": ch_info["lufs_L"],
        "channel_lufs_R": ch_info["lufs_R"],
        "channel_diff_db": ch_info["channel_loudness_diff_db"],
        "correlation": correlation,
        "error": None,
    }


def main() -> None:
    """
    AnÃ¡lisis para S10_MASTER_FINAL_LIMITS.

    Uso desde stage.py:
        python analysis/S10_MASTER_FINAL_LIMITS.py S10_MASTER_FINAL_LIMITS
    """
    if len(sys.argv) < 2:
        print("Uso: python S10_MASTER_FINAL_LIMITS.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S10_MASTER_FINAL_LIMITS"

    # 1) Cargar contrato
    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    true_peak_max_dbtp = float(metrics.get("true_peak_max_dbtp", -1.0))
    max_channel_diff_db = float(metrics.get("max_channel_loudness_diff_db", 0.5))
    correlation_min = float(metrics.get("correlation_min", -0.2))

    max_eq_trim_db_per_band = float(limits.get("max_eq_trim_db_per_band", 0.5))
    max_output_ceiling_adjust_db = float(limits.get("max_output_ceiling_adjust_db", 0.2))

    # 2) temp/<contract_id> y session_config
    temp_dir = get_temp_dir(contract_id, create=True)
    cfg = load_session_config(contract_id)
    style_preset = cfg["style_preset"]

    # 3) Perfil de mastering para obtener el target de LUFS (tolerancia de estilo)
    m_profile = get_mastering_profile(style_preset)
    target_lufs = float(m_profile.get("target_lufs_integrated", -11.0))
    # Tolerancia QC mÃ¡s estricta: Â±0.5 LU
    style_lufs_tolerance = 0.5

    full_song_path = temp_dir / "full_song.wav"
    true_peak_dbtp = float("-inf")
    lufs_integrated = float("-inf")
    lra = 0.0
    channel_lufs_L = float("-inf")
    channel_lufs_R = float("-inf")
    channel_diff_db = 0.0
    correlation = 1.0
    sr_mix: int | None = None

    if full_song_path.exists():
        result = _analyze_master_final(full_song_path)

        if result["error"] is not None:
            # Error de lectura/procesado
            print(result["error"])
        else:
            sr_mix = result["sr_mix"]
            true_peak_dbtp = result["true_peak_dbtp"]
            lufs_integrated = result["lufs_integrated"]
            lra = result["lra"]
            channel_lufs_L = result["channel_lufs_L"]
            channel_lufs_R = result["channel_lufs_R"]
            channel_diff_db = result["channel_diff_db"]
            correlation = result["correlation"]

            print(
                "[S10_MASTER_FINAL_LIMITS] full_song.wav analizado (sr=" + str(sr_mix) + "). " +
                "TP=" + f"{true_peak_dbtp:.2f}" + " dBTP, " +
                "LUFS=" + f"{lufs_integrated:.2f}" + ", LRA=" + f"{lra:.2f}" + ". " +
                "diff_LR=" + f"{channel_diff_db:.2f}" + " dB, corr=" + f"{correlation:.3f}" + "."
            )
    else:
        print(
            "[S10_MASTER_FINAL_LIMITS] Aviso: no existe " + str(full_song_path) + ", " +
            "no se puede analizar el master final."
        )

    # 5) Evaluar si LUFS estÃ¡ dentro de tolerancia de estilo
    lufs_within_style = False
    if lufs_integrated != float("-inf"):
        if abs(lufs_integrated - target_lufs) <= style_lufs_tolerance:
            lufs_within_style = True

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "samplerate_hz": sr_mix,
            "true_peak_dbtp": true_peak_dbtp,
            "true_peak_max_dbtp_target": true_peak_max_dbtp,
            "lufs_integrated": lufs_integrated,
            "target_lufs_integrated": target_lufs,
            "style_lufs_tolerance": style_lufs_tolerance,
            "lufs_integrated_within_style_tolerance": lufs_within_style,
            "lra": lra,
            "lra_target_min": float(m_profile.get("target_lra_min", 5.0)),
            "lra_target_max": float(m_profile.get("target_lra_max", 10.0)),
            "channel_lufs_L": channel_lufs_L,
            "channel_lufs_R": channel_lufs_R,
            "channel_loudness_diff_db": channel_diff_db,
            "max_channel_loudness_diff_db_target": max_channel_diff_db,
            "correlation": correlation,
            "correlation_min_target": correlation_min,
            "max_eq_trim_db_per_band": max_eq_trim_db_per_band,
            "max_output_ceiling_adjust_db": max_output_ceiling_adjust_db,
        },
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    print(
        f"[S10_MASTER_FINAL_LIMITS] AnÃ¡lisis completado. JSON: {output_path}"
    )


if __name__ == "__main__":
    main()
