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

from utils.analysis_utils import (  # noqa: E402
    load_contract,
    get_temp_dir,
    sf_read_limited,
)
from utils.session_utils import load_session_config  # noqa: E402
from utils.loudness_utils import compute_lufs_and_lra  # noqa: E402
from utils.color_utils import compute_true_peak_dbfs, compute_sample_peak_dbfs  # noqa: E402
from utils.mastering_profiles_utils import get_mastering_profile  # noqa: E402


def _analyze_master(full_song_path: Path) -> Dict[str, Any]:
    """
    Lee full_song.wav y calcula:
      - true peak (dBTP)
      - sample peak (dBFS)
      - LUFS integrados
      - LRA
    """
    try:
        y, sr = sf_read_limited(full_song_path, always_2d=False)
    except Exception as e:
        return {
            "sr_mix": None,
            "pre_true_peak_dbtp": float("-inf"),
            "pre_sample_peak_dbfs": float("-inf"),
            "pre_lufs_integrated": float("-inf"),
            "pre_lra": 0.0,
            "error": f"[S9_MASTER_GENERIC] Aviso: no se puede leer full_song.wav: {e}.",
        }

    pre_true_peak_dbtp = compute_true_peak_dbfs(y, oversample_factor=4)
    pre_sample_peak_dbfs = compute_sample_peak_dbfs(y)
    pre_lufs_integrated, pre_lra = compute_lufs_and_lra(y, sr)

    return {
        "sr_mix": int(sr),
        "pre_true_peak_dbtp": float(pre_true_peak_dbtp),
        "pre_sample_peak_dbfs": float(pre_sample_peak_dbfs),
        "pre_lufs_integrated": float(pre_lufs_integrated),
        "pre_lra": float(pre_lra),
        "error": None,
    }


def main() -> None:
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S9_MASTER_GENERIC.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]

    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    max_limiter_gr_db = float(limits.get("max_limiter_gain_reduction_db", 4.0))
    max_eq_change_db = float(limits.get("max_eq_change_db_per_band_per_pass", 2.0))
    max_width_change_pct = float(limits.get("max_stereo_width_change_percent", 10.0))

    # Nuevo (opcional): cuánto peak-shave permitimos por clipping antes del limiter.
    # Si tu contract no lo tiene, default conservador 2 dB.
    max_clipper_peak_shave_db = float(limits.get("max_clipper_peak_shave_db", 2.0))

    temp_dir = get_temp_dir(contract_id, create=True)
    cfg = load_session_config(contract_id)
    style_preset = cfg["style_preset"]

    m_profile = get_mastering_profile(style_preset)
    target_lufs = float(m_profile.get("target_lufs_integrated", -11.0))
    target_lra_min = float(m_profile.get("target_lra_min", 5.0))
    target_lra_max = float(m_profile.get("target_lra_max", 10.0))
    target_ceiling_dbtp = float(m_profile.get("target_ceiling_dbtp", -1.0))
    target_ms_width_factor = float(m_profile.get("target_ms_width_factor", 1.0))

    full_song_path = temp_dir / "full_song.wav"

    pre_true_peak_dbtp = float("-inf")
    pre_sample_peak_dbfs = float("-inf")
    pre_lufs_integrated = float("-inf")
    pre_lra = 0.0
    sr_mix: int | None = None

    # Recomendaciones (para que stage decida clipper)
    delta_to_target = 0.0
    headroom_to_ceiling_db = float("-inf")
    limiting_needed_no_clip_db = 0.0
    clipper_recommended_peak_shave_db = 0.0
    gain_max_by_gr = 0.0

    if full_song_path.exists():
        result = _analyze_master(full_song_path)
        if result["error"] is not None:
            logger.logger.info(result["error"])
        else:
            sr_mix = result["sr_mix"]
            pre_true_peak_dbtp = result["pre_true_peak_dbtp"]
            pre_sample_peak_dbfs = result["pre_sample_peak_dbfs"]
            pre_lufs_integrated = result["pre_lufs_integrated"]
            pre_lra = result["pre_lra"]

            delta_to_target = float(target_lufs - pre_lufs_integrated)
            headroom_to_ceiling_db = float(target_ceiling_dbtp - pre_true_peak_dbtp)

            # Cuánto limiting necesitaría si quisiéramos llegar al target SOLO con limiter (sin clipper)
            if delta_to_target > 0.0 and headroom_to_ceiling_db != float("-inf"):
                limiting_needed_no_clip_db = float(max(0.0, delta_to_target - headroom_to_ceiling_db))
            else:
                limiting_needed_no_clip_db = 0.0

            # Si el limiting requerido excede el max permitido, recomendamos clipper para “shave” de picos.
            # Además, si la subida es grande (EDM / -9 LUFS etc.), recomendamos 1–2 dB aunque no exceda por mucho,
            # para evitar bombeo y “aplastamiento”.
            if delta_to_target > 0.0:
                # Caso 1: excedemos GR max -> clipper cubre el exceso
                excess_over_gr = limiting_needed_no_clip_db - max_limiter_gr_db
                if excess_over_gr > 0.0:
                    clipper_recommended_peak_shave_db = min(max_clipper_peak_shave_db, float(excess_over_gr))

                # Caso 2: aunque no exceda, si vamos a empujar bastante, recomendación mínima
                if clipper_recommended_peak_shave_db < 0.5:
                    if delta_to_target >= 4.0 or target_lufs <= -10.0:
                        clipper_recommended_peak_shave_db = min(max_clipper_peak_shave_db, 1.5)
                    elif delta_to_target >= 2.5:
                        clipper_recommended_peak_shave_db = min(max_clipper_peak_shave_db, 1.0)

            gain_max_by_gr = max_limiter_gr_db + target_ceiling_dbtp - pre_true_peak_dbtp

            logger.logger.info(
                f"[S9_MASTER_GENERIC] PRE (sr={sr_mix}): TP={pre_true_peak_dbtp:.2f} dBTP, "
                f"sample_peak={pre_sample_peak_dbfs:.2f} dBFS, "
                f"LUFS={pre_lufs_integrated:.2f}, LRA={pre_lra:.2f}. "
                f"Delta→target={delta_to_target:+.2f} LU, headroom={headroom_to_ceiling_db:+.2f} dB, "
                f"limiting_needed_no_clip≈{limiting_needed_no_clip_db:.2f} dB, "
                f"clipper_reco≈{clipper_recommended_peak_shave_db:.2f} dB, "
                f"gain_max_by_GR≈{gain_max_by_gr:.2f} dB."
            )
    else:
        logger.logger.info(
            f"[S9_MASTER_GENERIC] Aviso: no existe {full_song_path}, no se puede analizar el mastering."
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
            "pre_sample_peak_dbfs": pre_sample_peak_dbfs,
            "pre_lufs_integrated": pre_lufs_integrated,
            "pre_lra": pre_lra,
            "delta_lufs_to_target": float(delta_to_target),
            "headroom_to_ceiling_db": float(headroom_to_ceiling_db),
            "limiting_needed_no_clip_db": float(limiting_needed_no_clip_db),
            "max_limiter_gain_reduction_db": max_limiter_gr_db,
            "max_eq_change_db_per_band_per_pass": max_eq_change_db,
            "max_stereo_width_change_percent": max_width_change_pct,
            "max_clipper_peak_shave_db": max_clipper_peak_shave_db,
            "clipper_recommended_peak_shave_db": float(clipper_recommended_peak_shave_db),
            "mastering_targets": {
                "target_lufs_integrated": target_lufs,
                "target_lra_min": target_lra_min,
                "target_lra_max": target_lra_max,
                "target_ceiling_dbtp": target_ceiling_dbtp,
                "target_ms_width_factor": target_ms_width_factor,
            },
        },
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    logger.logger.info(f"[S9_MASTER_GENERIC] Análisis completado. JSON: {output_path}")


if __name__ == "__main__":
    main()
