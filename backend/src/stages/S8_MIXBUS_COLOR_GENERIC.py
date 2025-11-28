# C:\mix-master\backend\src\stages\S8_MIXBUS_COLOR_GENERIC.py

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Any

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from utils.analysis_utils import get_temp_dir
from utils.color_utils import (  # noqa: E402
    compute_rms_dbfs,
    compute_true_peak_dbfs,
    apply_soft_saturation,
    estimate_thd_percent,
)


def load_analysis(contract_id: str) -> Dict[str, Any]:
    """
    Carga el JSON de análisis generado por analysis\\S8_MIXBUS_COLOR_GENERIC.py.
    """
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def _style_saturation_factor(style_preset: str) -> float:
    """
    Factor estilístico simple para la cantidad de saturación:

      - Flamenco/Rumba: 0.7 (muy discreto).
      - Urbano/Trap/EDM/Club: 1.0 (puede tolerar más color).
      - Acústico/Jazz: 0.5.
      - Resto: 0.8.
    """
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


def _process_mixbus_color_worker(
    full_song_path_str: str,
    style_preset: str,
    tp_min: float,
    tp_max: float,
    max_thd_percent: float,
    max_sat_per_pass_db: float,
) -> Dict[str, float]:
    """
    Worker que realiza todo el procesado de color en el mixbus:

      - Lee full_song.wav.
      - Calcula métricas pre.
      - Determina drive de saturación según estilo y límites.
      - Aplica saturación suave y, si es necesario, ajusta drive para respetar THD.
      - Aplica trim suave para acercar el true peak al rango objetivo.
      - Escribe el audio procesado en el mismo full_song.wav.
      - Devuelve métricas clave (pre/post, drive, trim, THD).
    """
    full_song_path = Path(full_song_path_str)

    # Leer audio actual
    y, sr = sf.read(full_song_path, always_2d=False)
    if not isinstance(y, np.ndarray):
        y = np.asarray(y, dtype=np.float32)
    else:
        y = y.astype(np.float32)

    pre_true_peak_dbtp = compute_true_peak_dbfs(y, oversample_factor=4)
    pre_rms_dbfs = compute_rms_dbfs(y)

    print(
        f"[S8_MIXBUS_COLOR_GENERIC] PRE: true_peak={pre_true_peak_dbtp:.2f} dBTP, "
        f"RMS={pre_rms_dbfs:.2f} dBFS."
    )

    # Factor por estilo
    style_factor = _style_saturation_factor(style_preset)
    drive_db = max_sat_per_pass_db * style_factor

    # Si el drive resultante es muy pequeño, casi no hacemos nada
    if drive_db < 0.1:
        print(
            "[S8_MIXBUS_COLOR_GENERIC] Drive calculado < 0.1 dB; "
            "se considera no-op en cuanto a saturación."
        )
        y_sat = y.copy()
        thd_pct = 0.0
    else:
        # Aplicar saturación inicial
        y_sat = apply_soft_saturation(y, drive_db=drive_db, curve_strength=1.5)

        # Estimar THD incremental
        thd_pct = estimate_thd_percent(y, y_sat)
        print(
            f"[S8_MIXBUS_COLOR_GENERIC] THD estimada con drive={drive_db:.2f} dB: "
            f"{thd_pct:.2f} % (límite={max_thd_percent:.2f} %)."
        )

        # Si nos pasamos de THD, ajustamos drive hacia abajo
        if thd_pct > max_thd_percent:
            scale = max_thd_percent / max(thd_pct, 1e-6)
            new_drive = drive_db * scale
            if new_drive < 0.1:
                print(
                    "[S8_MIXBUS_COLOR_GENERIC] Para respetar THD el drive caería < 0.1 dB; "
                    "se deja sin saturar."
                )
                drive_db = 0.0
                y_sat = y.copy()
                thd_pct = 0.0
            else:
                drive_db = float(new_drive)
                print(
                    f"[S8_MIXBUS_COLOR_GENERIC] Ajustando drive a {drive_db:.2f} dB "
                    "para respetar THD."
                )
                y_sat = apply_soft_saturation(y, drive_db=drive_db, curve_strength=1.5)
                thd_pct = estimate_thd_percent(y, y_sat)
                print(
                    f"[S8_MIXBUS_COLOR_GENERIC] THD tras ajuste: {thd_pct:.2f} %."
                )

    # True peak tras saturación (antes de trim)
    post_true_peak_dbtp_raw = compute_true_peak_dbfs(y_sat, oversample_factor=4)

    # Ajuste de trim ligero para acercar true peak al rango objetivo
    target_mid = 0.5 * (tp_min + tp_max)  # p.ej. -3 dBTP
    needed_trim = target_mid - post_true_peak_dbtp_raw

    # Limitar trim a ±1 dB para mantener cambios suaves
    MAX_TRIM_DB = 1.0
    trim_db = max(-MAX_TRIM_DB, min(MAX_TRIM_DB, needed_trim))

    if abs(trim_db) > 0.05:
        trim_lin = 10.0 ** (trim_db / 20.0)
        y_out = (y_sat * trim_lin).astype(np.float32)
        print(
            f"[S8_MIXBUS_COLOR_GENERIC] Aplicando trim de {trim_db:+.2f} dB "
            f"hacia true_peak objetivo ≈ {target_mid:.2f} dBTP."
        )
    else:
        trim_db = 0.0
        y_out = y_sat
        print(
            "[S8_MIXBUS_COLOR_GENERIC] True peak ya cercano al objetivo; "
            "no se aplica trim significativo."
        )

    # Clamp final por seguridad
    y_out = np.clip(y_out, -1.0, 1.0)

    post_true_peak_dbtp = compute_true_peak_dbfs(y_out, oversample_factor=4)
    post_rms_dbfs = compute_rms_dbfs(y_out)

    print(
        f"[S8_MIXBUS_COLOR_GENERIC] POST: true_peak={post_true_peak_dbtp:.2f} dBTP, "
        f"RMS={post_rms_dbfs:.2f} dBFS, THD≈{thd_pct:.2f} %."
    )

    # Escribir mix procesado
    sf.write(full_song_path, y_out, sr)
    print(
        f"[S8_MIXBUS_COLOR_GENERIC] Mixbus coloreado reescrito en {full_song_path}."
    )

    return {
        "pre_true_peak_dbtp": float(pre_true_peak_dbtp),
        "pre_rms_dbfs": float(pre_rms_dbfs),
        "post_true_peak_dbtp": float(post_true_peak_dbtp),
        "post_rms_dbfs": float(post_rms_dbfs),
        "drive_db_used": float(drive_db),
        "trim_db_applied": float(trim_db),
        "thd_percent": float(thd_pct),
    }


def main() -> None:
    """
    Stage S8_MIXBUS_COLOR_GENERIC:

      - Lee analysis_S8_MIXBUS_COLOR_GENERIC.json.
      - Calcula parámetros de saturación en función de estilo y límites del contrato.
      - Lanza un ProcessPoolExecutor para procesar full_song.wav en un worker.
      - El worker aplica saturación suave y trim de true peak.
      - Se guardan métricas en color_metrics_S8_MIXBUS_COLOR_GENERIC.json.
    """
    if len(sys.argv) < 2:
        print("Uso: python S8_MIXBUS_COLOR_GENERIC.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S8_MIXBUS_COLOR_GENERIC"

    analysis = load_analysis(contract_id)

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}
    session: Dict[str, Any] = analysis.get("session", {}) or {}

    style_preset = analysis.get("style_preset", "default")

    tp_min = float(metrics.get("target_true_peak_range_dbtp_min", -4.0))
    tp_max = float(metrics.get("target_true_peak_range_dbtp_max", -2.0))
    max_thd_percent = float(metrics.get("max_thd_percent", 3.0))
    max_sat_per_pass_db = float(limits.get("max_additional_saturation_per_pass", 1.0))

    temp_dir = PROJECT_ROOT / "temp" / contract_id
    full_song_path = temp_dir / "full_song.wav"

    if not full_song_path.exists():
        print(
            f"[S8_MIXBUS_COLOR_GENERIC] No existe {full_song_path}; "
            "no se aplica color de mixbus."
        )
        return

    # Procesar el mixbus en un proceso separado
    with ProcessPoolExecutor(max_workers=1) as ex:
        future = ex.submit(
            _process_mixbus_color_worker,
            str(full_song_path),
            style_preset,
            tp_min,
            tp_max,
            max_thd_percent,
            max_sat_per_pass_db,
        )
        color_result = future.result()

    # Guardar métricas para el futuro check
    metrics_path = temp_dir / "color_metrics_S8_MIXBUS_COLOR_GENERIC.json"
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "contract_id": contract_id,
                "style_preset": style_preset,
                "target_true_peak_range_dbtp_min": tp_min,
                "target_true_peak_range_dbtp_max": tp_max,
                "max_thd_percent": max_thd_percent,
                "max_additional_saturation_per_pass_db": max_sat_per_pass_db,
                "pre_true_peak_dbtp": color_result["pre_true_peak_dbtp"],
                "pre_rms_dbfs": color_result["pre_rms_dbfs"],
                "post_true_peak_dbtp": color_result["post_true_peak_dbtp"],
                "post_rms_dbfs": color_result["post_rms_dbfs"],
                "drive_db_used": color_result["drive_db_used"],
                "trim_db_applied": color_result["trim_db_applied"],
                "thd_percent": color_result["thd_percent"],
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(
        f"[S8_MIXBUS_COLOR_GENERIC] Métricas de color guardadas en: {metrics_path}"
    )


if __name__ == "__main__":
    main()
