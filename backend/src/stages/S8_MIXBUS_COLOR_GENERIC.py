from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
from pedalboard import Distortion  # noqa: E402

from utils.analysis_utils import get_temp_dir  # noqa: E402
from utils.color_utils import (  # noqa: E402
    compute_rms_dbfs,
    compute_true_peak_dbfs,
    estimate_thd_percent,
)


def load_analysis(contract_id: str) -> Dict[str, Any]:
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"
    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")
    with analysis_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _style_saturation_factor(style_preset: str) -> float:
    s = (style_preset or "").lower()
    if "flamenco" in s or "rumba" in s:
        return 0.7
    if "urbano" in s or "trap" in s or "reggaeton" in s:
        return 1.0
    if "edm" in s or "club" in s or "house" in s:
        return 1.0
    if "acoustic" in s or "acústico" in s or "jazz" in s:
        return 0.5
    return 0.8


def _estimate_noise_floor_dbfs(y: np.ndarray, sr: int) -> float:
    arr = np.asarray(y, dtype=np.float32)
    if arr.ndim > 1:
        arr = np.mean(arr, axis=1).astype(np.float32)

    n = int(arr.size)
    if n <= 0 or sr <= 0:
        return float("-inf")

    frame_len = max(256, int(round(0.050 * sr)))  # 50 ms
    hop = frame_len

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


def _apply_pedalboard_saturation(y: np.ndarray, sr: int, drive_db: float) -> np.ndarray:
    arr = np.asarray(y, dtype=np.float32)
    dist = Distortion()
    dist.drive_db = float(drive_db)
    y_sat = dist(arr, int(sr))
    return np.asarray(y_sat, dtype=np.float32)


def _process_mixbus_color_worker(
    full_song_path_str: str,
    style_preset: str,
    tp_min: float,
    tp_max: float,
    max_thd_percent: float,
    max_sat_per_pass_db: float,
) -> Dict[str, Any]:
    """
    Cambios clave:
      - Under-levelled mode: si la mezcla llega muy baja, NO hacemos lift grande aquí.
      - Si hay que levantar mucho, reducimos/omitimos saturación (evita dureza).
      - Medimos noise_floor PRE/POST y guardamos delta y delta compensada por trim.
      - Escribimos WAV en FLOAT para evitar cuantización (dureza/ruido).
      - Evitamos clip por np.clip; usamos safety trim si TP se pasa.
    """
    full_song_path = Path(full_song_path_str)

    y, sr = sf.read(full_song_path, always_2d=False)
    y = np.asarray(y, dtype=np.float32)
    sr = int(sr)

    pre_tp = float(compute_true_peak_dbfs(y, oversample_factor=4))
    pre_rms = float(compute_rms_dbfs(y))
    pre_nf = float(_estimate_noise_floor_dbfs(y, sr))

    logger.logger.info(
        f"[S8_MIXBUS_COLOR_GENERIC] PRE: true_peak={pre_tp:.2f} dBTP, RMS={pre_rms:.2f} dBFS, "
        f"noise_floor≈{pre_nf:.2f} dBFS."
    )

    # --------------------------------------------------------------
    # Detectar mezcla sub-nivelada (para no convertir S8 en makeup gain)
    # --------------------------------------------------------------
    TP_MARGIN = 0.3
    pre_in_range = (tp_min - TP_MARGIN) <= pre_tp <= (tp_max + TP_MARGIN)

    # Heurística: si el TP está MUY por debajo del rango, o el RMS es muy bajo,
    # consideramos "under-levelled" y limitamos el lift aquí.
    UNDERLEVEL_TP_DBTP = tp_min - 6.0  # p.ej. -10 dBTP si tp_min=-4
    UNDERLEVEL_RMS_DBFS = -28.0
    under_levelled = (pre_tp < UNDERLEVEL_TP_DBTP) or (pre_rms < UNDERLEVEL_RMS_DBFS)

    # --------------------------------------------------------------
    # Saturación (drive) controlada por estilo + idempotencia + underlevelled
    # --------------------------------------------------------------
    IDEMP_DRIVE_MAX_DB = 0.5
    style_factor = _style_saturation_factor(style_preset)
    drive_db = float(max_sat_per_pass_db * style_factor)

    if pre_in_range and drive_db > IDEMP_DRIVE_MAX_DB:
        drive_db = IDEMP_DRIVE_MAX_DB

    # Si llega sub-nivelado, evitamos meter saturación “porque sí”
    # cuando probablemente luego el master va a subir bastante.
    if under_levelled:
        drive_db = min(drive_db, 0.2)  # casi no-op; puedes poner 0.0 si quieres

    # Aplicar saturación + control THD
    if drive_db < 0.1:
        y_sat = y.copy()
        thd_pct = 0.0
        logger.logger.info("[S8_MIXBUS_COLOR_GENERIC] Saturación omitida (drive < 0.1 dB).")
    else:
        y_sat = _apply_pedalboard_saturation(y, sr, drive_db=drive_db)
        thd_pct = float(estimate_thd_percent(y, y_sat))

        logger.logger.info(
            f"[S8_MIXBUS_COLOR_GENERIC] THD estimada con drive={drive_db:.2f} dB: "
            f"{thd_pct:.2f} % (límite={max_thd_percent:.2f} %)."
        )

        if thd_pct > max_thd_percent:
            scale = max_thd_percent / max(thd_pct, 1e-6)
            new_drive = float(drive_db * scale)
            if new_drive < 0.1:
                drive_db = 0.0
                y_sat = y.copy()
                thd_pct = 0.0
                logger.logger.info(
                    "[S8_MIXBUS_COLOR_GENERIC] Saturación desactivada para respetar THD (drive ajustado < 0.1 dB)."
                )
            else:
                drive_db = new_drive
                y_sat = _apply_pedalboard_saturation(y, sr, drive_db=drive_db)
                thd_pct = float(estimate_thd_percent(y, y_sat))
                logger.logger.info(f"[S8_MIXBUS_COLOR_GENERIC] Drive ajustado a {drive_db:.2f} dB, THD≈{thd_pct:.2f}%.")

    tp_after_sat = float(compute_true_peak_dbfs(y_sat, oversample_factor=4))

    # --------------------------------------------------------------
    # Trim: objetivo TP, pero cap estricto si under-levelled
    # --------------------------------------------------------------
    target_mid = 0.5 * (tp_min + tp_max)  # p.ej. -3 dBTP
    needed_trim = float(target_mid - tp_after_sat)

    IDEMP_TRIM_MAX_DB = 0.5
    if pre_in_range:
        max_trim_up_db = IDEMP_TRIM_MAX_DB
        max_trim_down_db = IDEMP_TRIM_MAX_DB
    elif under_levelled:
        # Clave: NO levantar fuerte en S8 (evita subir ruido/dureza aquí)
        max_trim_up_db = 1.5
        max_trim_down_db = 2.0
    else:
        max_trim_up_db = 6.0
        max_trim_down_db = 2.0

    if needed_trim >= 0.0:
        trim_db = min(needed_trim, max_trim_up_db)
    else:
        trim_db = max(needed_trim, -max_trim_down_db)

    trim_lin = float(10.0 ** (trim_db / 20.0))
    y_out = (y_sat * trim_lin).astype(np.float32) if abs(trim_db) > 0.05 else y_sat.copy()
    if abs(trim_db) > 0.05:
        logger.logger.info(
            f"[S8_MIXBUS_COLOR_GENERIC] Trim aplicado={trim_db:+.2f} dB "
            f"(needed={needed_trim:+.2f}, cap_up={max_trim_up_db:.2f})."
        )
    else:
        trim_db = 0.0
        logger.logger.info("[S8_MIXBUS_COLOR_GENERIC] Trim no significativo; no-op.")

    # --------------------------------------------------------------
    # Safety trim para NO pasarnos del techo del rango (evita clipping)
    # --------------------------------------------------------------
    post_tp = float(compute_true_peak_dbfs(y_out, oversample_factor=4))
    safety_trim_db = 0.0
    CEIL_MARGIN = 0.05
    if post_tp > (tp_max + CEIL_MARGIN):
        target_tp = tp_max - 0.2  # holgura
        safety_trim_db = float(target_tp - post_tp)
        safety_lin = float(10.0 ** (safety_trim_db / 20.0))
        y_out = (y_out * safety_lin).astype(np.float32)
        post_tp = float(compute_true_peak_dbfs(y_out, oversample_factor=4))
        logger.logger.info(
            f"[S8_MIXBUS_COLOR_GENERIC] Safety trim adicional {safety_trim_db:+.2f} dB "
            f"para respetar tp_max={tp_max:.2f} dBTP."
        )

    post_rms = float(compute_rms_dbfs(y_out))
    post_nf = float(_estimate_noise_floor_dbfs(y_out, sr))

    nf_delta = post_nf - pre_nf if (pre_nf != float("-inf") and post_nf != float("-inf")) else None
    # “Compensado”: si solo subiste gain, post_nf ≈ pre_nf + trim_total. Esto intenta aislar “suciedad añadida”.
    trim_total_db = float(trim_db + safety_trim_db)
    post_nf_comp = (post_nf - trim_total_db) if (post_nf != float("-inf")) else None
    nf_comp_delta = (post_nf_comp - pre_nf) if (post_nf_comp is not None and pre_nf != float("-inf")) else None

    logger.logger.info(
        f"[S8_MIXBUS_COLOR_GENERIC] POST: true_peak={post_tp:.2f} dBTP, RMS={post_rms:.2f} dBFS, "
        f"noise_floor≈{post_nf:.2f} dBFS, THD≈{thd_pct:.2f}%."
    )

    # Guardar como FLOAT para NO introducir cuantización/dureza
    sf.write(full_song_path, y_out.astype(np.float32), sr, subtype="FLOAT")
    logger.logger.info(f"[S8_MIXBUS_COLOR_GENERIC] Mixbus reescrito (FLOAT) en {full_song_path}.")

    return {
        "pre_true_peak_dbtp": pre_tp,
        "pre_rms_dbfs": pre_rms,
        "pre_noise_floor_dbfs": pre_nf,
        "post_true_peak_dbtp": post_tp,
        "post_rms_dbfs": post_rms,
        "post_noise_floor_dbfs": post_nf,
        "noise_floor_delta_db": nf_delta,
        "post_noise_floor_compensated_dbfs": post_nf_comp,
        "noise_floor_compensated_delta_db": nf_comp_delta,
        "drive_db_used": float(drive_db),
        "trim_db_applied": float(trim_db),
        "safety_trim_db": float(safety_trim_db),
        "trim_total_db": float(trim_total_db),
        "thd_percent": float(thd_pct),
        "under_levelled_mode": bool(under_levelled),
        "tp_after_saturation_dbtp": float(tp_after_sat),
        "max_trim_up_db_used": float(max_trim_up_db),
    }


def main() -> None:
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S8_MIXBUS_COLOR_GENERIC.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]
    analysis = load_analysis(contract_id)

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}

    style_preset = analysis.get("style_preset", "default")

    tp_min = float(metrics.get("target_true_peak_range_dbtp_min", -4.0))
    tp_max = float(metrics.get("target_true_peak_range_dbtp_max", -2.0))
    max_thd_percent = float(metrics.get("max_thd_percent", 3.0))
    max_sat_per_pass_db = float(limits.get("max_additional_saturation_per_pass", 1.0))

    temp_dir = get_temp_dir(contract_id, create=False)
    full_song_path = temp_dir / "full_song.wav"

    if not full_song_path.exists():
        logger.logger.info(f"[S8_MIXBUS_COLOR_GENERIC] No existe {full_song_path}; no se aplica color.")
        return

    res = _process_mixbus_color_worker(
        str(full_song_path),
        style_preset,
        tp_min,
        tp_max,
        max_thd_percent,
        max_sat_per_pass_db,
    )

    metrics_path = temp_dir / "color_metrics_S8_MIXBUS_COLOR_GENERIC.json"
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "contract_id": contract_id,
                "style_preset": style_preset,
                "targets": {
                    "target_true_peak_range_dbtp_min": tp_min,
                    "target_true_peak_range_dbtp_max": tp_max,
                    "max_thd_percent": max_thd_percent,
                    "max_additional_saturation_per_pass_db": max_sat_per_pass_db,
                },
                "pre": {
                    "true_peak_dbtp": res["pre_true_peak_dbtp"],
                    "rms_dbfs": res["pre_rms_dbfs"],
                    "noise_floor_dbfs": res["pre_noise_floor_dbfs"],
                },
                "post": {
                    "true_peak_dbtp": res["post_true_peak_dbtp"],
                    "rms_dbfs": res["post_rms_dbfs"],
                    "noise_floor_dbfs": res["post_noise_floor_dbfs"],
                    "noise_floor_delta_db": res["noise_floor_delta_db"],
                    "noise_floor_compensated_dbfs": res["post_noise_floor_compensated_dbfs"],
                    "noise_floor_compensated_delta_db": res["noise_floor_compensated_delta_db"],
                },
                "process": {
                    "drive_db_used": res["drive_db_used"],
                    "thd_percent": res["thd_percent"],
                    "trim_db_applied": res["trim_db_applied"],
                    "safety_trim_db": res["safety_trim_db"],
                    "trim_total_db": res["trim_total_db"],
                    "tp_after_saturation_dbtp": res["tp_after_saturation_dbtp"],
                    "under_levelled_mode": res["under_levelled_mode"],
                    "max_trim_up_db_used": res["max_trim_up_db_used"],
                    "written_subtype": "FLOAT",
                },
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    logger.logger.info(f"[S8_MIXBUS_COLOR_GENERIC] Métricas guardadas en: {metrics_path}")


if __name__ == "__main__":
    main()
