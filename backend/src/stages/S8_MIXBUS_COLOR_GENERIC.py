# C:\mix-master\backend\src\stages\S8_MIXBUS_COLOR_GENERIC.py
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
    compute_sample_peak_dbfs,
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
    """
    Estimación pragmática del noise floor basada en RMS por frames (50 ms),
    percentil 10 como cola baja robusta. Proxy (no separa ruido real vs pasajes suaves).
    """
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


def _apply_pedalboard_saturation(y: np.ndarray, sr: int, color_drive_db: float) -> np.ndarray:
    """
    Saturación/Distortion (color). NO debe usarse como makeup gain.
    """
    arr = np.asarray(y, dtype=np.float32)
    dist = Distortion()
    dist.drive_db = float(color_drive_db)
    y_sat = dist(arr, int(sr))
    return np.asarray(y_sat, dtype=np.float32)


def _db_to_lin(db: float) -> float:
    return float(10.0 ** (db / 20.0))


def _clamp(x: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, x)))


def _process_mixbus_color_worker(
    full_song_path_str: str,
    style_preset: str,
    tp_min: float,
    tp_max: float,
    max_thd_percent: float,
    max_sat_per_pass_db: float,
    # Opcionales: si quieres un rango pre-master distinto sin tocar tp_min/tp_max del contrato
    premaster_tp_min: float | None = None,
    premaster_tp_max: float | None = None,
) -> Dict[str, Any]:
    """
    S8 MIXBUS COLOR (corregido):
      - Separa explícitamente:
          * color_drive_db: saturación (color), controlada por THD y estilo.
          * makeup_gain_clean_db: ganancia LIMPIA post-color para dejar el mixbus en rango útil.
      - Under-levelled mode:
          * Reduce/omite drive (evita aspereza).
          * NO capa la ganancia limpia necesaria (makeup), porque eso es nivelado pre-master.
      - Escribe WAV en FLOAT para evitar cuantización.
      - Safety trim si el true peak se pasa del techo del rango.
    """
    full_song_path = Path(full_song_path_str)

    y, sr = sf.read(full_song_path, always_2d=False)
    y = np.asarray(y, dtype=np.float32)
    sr = int(sr)

    pre_tp = float(compute_true_peak_dbfs(y, oversample_factor=4))
    pre_sample_peak = float(compute_sample_peak_dbfs(y))
    pre_rms = float(compute_rms_dbfs(y))
    pre_nf = float(_estimate_noise_floor_dbfs(y, sr))

    logger.logger.info(
        f"[S8_MIXBUS_COLOR_GENERIC] PRE: true_peak={pre_tp:.2f} dBTP, sample_peak={pre_sample_peak:.2f} dBFS, "
        f"RMS={pre_rms:.2f} dBFS, noise_floor≈{pre_nf:.2f} dBFS."
    )

    # --------------------------------------------------------------
    # Objetivo de nivel PRE-MASTER (por defecto usa tp_min/tp_max).
    # Puedes pasar premaster_tp_min/max si quieres por contrato.
    # --------------------------------------------------------------
    target_tp_min = float(premaster_tp_min) if premaster_tp_min is not None else float(tp_min)
    target_tp_max = float(premaster_tp_max) if premaster_tp_max is not None else float(tp_max)
    target_mid = 0.5 * (target_tp_min + target_tp_max)

    # --------------------------------------------------------------
    # Detectar "under-levelled" (solo para limitar DRIVE, no makeup limpio)
    # --------------------------------------------------------------
    TP_MARGIN = 0.3
    pre_in_range = (target_tp_min - TP_MARGIN) <= pre_tp <= (target_tp_max + TP_MARGIN)

    # Heurística: muy por debajo del rango objetivo o RMS muy bajo
    UNDERLEVEL_TP_DBTP = target_tp_min - 6.0
    UNDERLEVEL_RMS_DBFS = -28.0
    under_levelled = (pre_tp < UNDERLEVEL_TP_DBTP) or (pre_rms < UNDERLEVEL_RMS_DBFS)

    # --------------------------------------------------------------
    # 1) COLOR: Saturación controlada (drive) - NO es makeup gain
    # --------------------------------------------------------------
    IDEMP_DRIVE_MAX_DB = 0.5
    style_factor = _style_saturation_factor(style_preset)
    color_drive_db = float(max_sat_per_pass_db * style_factor)

    # Idempotencia si ya estamos en rango
    if pre_in_range and color_drive_db > IDEMP_DRIVE_MAX_DB:
        color_drive_db = IDEMP_DRIVE_MAX_DB

    # Under-levelled => reducimos drive para no añadir dureza
    if under_levelled:
        color_drive_db = min(color_drive_db, 0.2)  # casi no-op (ajústalo a 0.0 si quieres)

    # Aplicar saturación + control THD
    if color_drive_db < 0.1:
        y_color = y.copy()
        thd_pct = 0.0
        logger.logger.info("[S8_MIXBUS_COLOR_GENERIC] Color omitido (color_drive_db < 0.1 dB).")
    else:
        y_color = _apply_pedalboard_saturation(y, sr, color_drive_db=color_drive_db)
        thd_pct = float(estimate_thd_percent(y, y_color))

        logger.logger.info(
            f"[S8_MIXBUS_COLOR_GENERIC] THD estimada con color_drive_db={color_drive_db:.2f} dB: "
            f"{thd_pct:.2f}% (límite={max_thd_percent:.2f}%)."
        )

        if thd_pct > max_thd_percent:
            scale = max_thd_percent / max(thd_pct, 1e-6)
            new_drive = float(color_drive_db * scale)

            if new_drive < 0.1:
                color_drive_db = 0.0
                y_color = y.copy()
                thd_pct = 0.0
                logger.logger.info(
                    "[S8_MIXBUS_COLOR_GENERIC] Color desactivado para respetar THD (drive ajustado < 0.1 dB)."
                )
            else:
                color_drive_db = new_drive
                y_color = _apply_pedalboard_saturation(y, sr, color_drive_db=color_drive_db)
                thd_pct = float(estimate_thd_percent(y, y_color))
                logger.logger.info(
                    f"[S8_MIXBUS_COLOR_GENERIC] Color_drive ajustado a {color_drive_db:.2f} dB, THD≈{thd_pct:.2f}%."
                )

    tp_after_color = float(compute_true_peak_dbfs(y_color, oversample_factor=4))

    # --------------------------------------------------------------
    # 2) MAKEUP GAIN LIMPIO: nivelado post-color para dejar pre-master en rango útil
    #    (NO lo capamos agresivamente en under-levelled; ese era el bug).
    # --------------------------------------------------------------
    makeup_needed_db = float(target_mid - tp_after_color)

    # Caps razonables (no por miedo a “ruido/aspereza”, sino por estabilidad/idempotencia)
    IDEMP_MAKEUP_MAX_DB = 0.5

    # Si ya estamos en rango, cambios pequeños
    if pre_in_range:
        max_makeup_up_db = IDEMP_MAKEUP_MAX_DB
        max_makeup_down_db = IDEMP_MAKEUP_MAX_DB
    else:
        # Permitir recuperar mezclas bajas (fix: no capar a 1.5 dB)
        # Ajusta si quieres: 12 dB suele ser suficiente para casos tipo +5.55 dB.
        max_makeup_up_db = 12.0
        max_makeup_down_db = 6.0

    if makeup_needed_db >= 0.0:
        makeup_gain_clean_db = min(makeup_needed_db, max_makeup_up_db)
    else:
        makeup_gain_clean_db = max(makeup_needed_db, -max_makeup_down_db)

    if abs(makeup_gain_clean_db) > 0.05:
        y_out = (y_color * _db_to_lin(makeup_gain_clean_db)).astype(np.float32)
        logger.logger.info(
            f"[S8_MIXBUS_COLOR_GENERIC] Makeup limpio aplicado={makeup_gain_clean_db:+.2f} dB "
            f"(needed={makeup_needed_db:+.2f}, cap_up={max_makeup_up_db:.2f})."
        )
    else:
        makeup_gain_clean_db = 0.0
        y_out = y_color.copy()
        logger.logger.info("[S8_MIXBUS_COLOR_GENERIC] Makeup limpio no significativo; no-op.")

    # --------------------------------------------------------------
    # Safety trim para NO pasarnos del techo del rango (evita clipping / TP runaway)
    # --------------------------------------------------------------
    post_tp = float(compute_true_peak_dbfs(y_out, oversample_factor=4))
    post_sample_peak = float(compute_sample_peak_dbfs(y_out))
    safety_trim_db = 0.0

    CEIL_MARGIN = 0.05
    if post_tp > (target_tp_max + CEIL_MARGIN):
        # dejamos holgura pequeña bajo el techo
        target_tp = target_tp_max - 0.2
        safety_trim_db = float(target_tp - post_tp)
        y_out = (y_out * _db_to_lin(safety_trim_db)).astype(np.float32)
        post_tp = float(compute_true_peak_dbfs(y_out, oversample_factor=4))
        post_sample_peak = float(compute_sample_peak_dbfs(y_out))
        logger.logger.info(
            f"[S8_MIXBUS_COLOR_GENERIC] Safety trim adicional {safety_trim_db:+.2f} dB "
            f"para respetar target_tp_max={target_tp_max:.2f} dBTP."
        )

    post_rms = float(compute_rms_dbfs(y_out))
    post_nf = float(_estimate_noise_floor_dbfs(y_out, sr))

    nf_delta = post_nf - pre_nf if (pre_nf != float("-inf") and post_nf != float("-inf")) else None

    # Compensado por gains lineales (makeup + safety), para aislar "suciedad añadida" del color
    gain_total_db = float(makeup_gain_clean_db + safety_trim_db)
    post_nf_comp = (post_nf - gain_total_db) if (post_nf != float("-inf")) else None
    nf_comp_delta = (post_nf_comp - pre_nf) if (post_nf_comp is not None and pre_nf != float("-inf")) else None

    logger.logger.info(
        f"[S8_MIXBUS_COLOR_GENERIC] POST: true_peak={post_tp:.2f} dBTP, sample_peak={post_sample_peak:.2f} dBFS, "
        f"RMS={post_rms:.2f} dBFS, noise_floor≈{post_nf:.2f} dBFS, THD≈{thd_pct:.2f}%."
    )

    # Guardar como FLOAT para NO introducir cuantización/dureza
    sf.write(full_song_path, y_out.astype(np.float32), sr, subtype="FLOAT")
    logger.logger.info(f"[S8_MIXBUS_COLOR_GENERIC] Mixbus reescrito (FLOAT) en {full_song_path}.")

    return {
        "pre_true_peak_dbtp": pre_tp,
        "pre_sample_peak_dbfs": pre_sample_peak,
        "pre_rms_dbfs": pre_rms,
        "pre_noise_floor_dbfs": pre_nf,
        "post_true_peak_dbtp": post_tp,
        "post_sample_peak_dbfs": post_sample_peak,
        "post_rms_dbfs": post_rms,
        "post_noise_floor_dbfs": post_nf,
        "noise_floor_delta_db": nf_delta,
        "post_noise_floor_compensated_dbfs": post_nf_comp,
        "noise_floor_compensated_delta_db": nf_comp_delta,
        # Color vs makeup (separados)
        "color_drive_db_used": float(color_drive_db),
        "makeup_gain_clean_db": float(makeup_gain_clean_db),
        "safety_trim_db": float(safety_trim_db),
        "gain_total_db": float(gain_total_db),
        "thd_percent": float(thd_pct),
        "under_levelled_mode": bool(under_levelled),
        "tp_after_color_dbtp": float(tp_after_color),
        "target_tp_min_used": float(target_tp_min),
        "target_tp_max_used": float(target_tp_max),
        "target_tp_mid_used": float(target_mid),
        "max_makeup_up_db_used": float(max_makeup_up_db),
        # Backward-compat: mantenemos nombres antiguos para no romper consumidores
        "drive_db_used": float(color_drive_db),
        "trim_db_applied": float(makeup_gain_clean_db),
        "trim_total_db": float(gain_total_db),
        "tp_after_saturation_dbtp": float(tp_after_color),
        "max_trim_up_db_used": float(max_makeup_up_db),
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

    # Rango “default” (si no defines nada extra)
    tp_min = float(metrics.get("target_true_peak_range_dbtp_min", -4.0))
    tp_max = float(metrics.get("target_true_peak_range_dbtp_max", -2.0))

    # Si quieres un rango específico pre-master en S8 (recomendado), añade en el contrato:
    #   premaster_true_peak_range_dbtp_min: -6.0
    #   premaster_true_peak_range_dbtp_max: -4.0
    premaster_tp_min = metrics.get("premaster_true_peak_range_dbtp_min", None)
    premaster_tp_max = metrics.get("premaster_true_peak_range_dbtp_max", None)
    premaster_tp_min_f = float(premaster_tp_min) if premaster_tp_min is not None else None
    premaster_tp_max_f = float(premaster_tp_max) if premaster_tp_max is not None else None

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
        premaster_tp_min=premaster_tp_min_f,
        premaster_tp_max=premaster_tp_max_f,
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
                    "premaster_true_peak_range_dbtp_min": premaster_tp_min_f,
                    "premaster_true_peak_range_dbtp_max": premaster_tp_max_f,
                    "max_thd_percent": max_thd_percent,
                    "max_additional_saturation_per_pass_db": max_sat_per_pass_db,
                },
                "pre": {
                    "true_peak_dbtp": res["pre_true_peak_dbtp"],
                    "sample_peak_dbfs": res["pre_sample_peak_dbfs"],
                    "rms_dbfs": res["pre_rms_dbfs"],
                    "noise_floor_dbfs": res["pre_noise_floor_dbfs"],
                },
                "post": {
                    "true_peak_dbtp": res["post_true_peak_dbtp"],
                    "sample_peak_dbfs": res["post_sample_peak_dbfs"],
                    "rms_dbfs": res["post_rms_dbfs"],
                    "noise_floor_dbfs": res["post_noise_floor_dbfs"],
                    "noise_floor_delta_db": res["noise_floor_delta_db"],
                    "noise_floor_compensated_dbfs": res["post_noise_floor_compensated_dbfs"],
                    "noise_floor_compensated_delta_db": res["noise_floor_compensated_delta_db"],
                },
                "process": {
                    "color_drive_db_used": res["color_drive_db_used"],
                    "makeup_gain_clean_db": res["makeup_gain_clean_db"],
                    "safety_trim_db": res["safety_trim_db"],
                    "gain_total_db": res["gain_total_db"],
                    "tp_after_color_dbtp": res["tp_after_color_dbtp"],
                    "thd_percent": res["thd_percent"],
                    "under_levelled_mode": res["under_levelled_mode"],
                    "target_tp_min_used": res["target_tp_min_used"],
                    "target_tp_max_used": res["target_tp_max_used"],
                    "target_tp_mid_used": res["target_tp_mid_used"],
                    "max_makeup_up_db_used": res["max_makeup_up_db_used"],
                    "written_subtype": "FLOAT",
                    # backward-compat
                    "drive_db_used": res["drive_db_used"],
                    "trim_db_applied": res["trim_db_applied"],
                    "trim_total_db": res["trim_total_db"],
                    "tp_after_saturation_dbtp": res["tp_after_saturation_dbtp"],
                    "max_trim_up_db_used": res["max_trim_up_db_used"],
                },
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    logger.logger.info(f"[S8_MIXBUS_COLOR_GENERIC] Métricas guardadas en: {metrics_path}")


if __name__ == "__main__":
    main()
