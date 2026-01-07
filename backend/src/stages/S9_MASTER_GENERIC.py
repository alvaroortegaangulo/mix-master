# C:\mix-master\backend\src\stages\S9_MASTER_GENERIC.py

from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any, Tuple

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from pedalboard import Pedalboard, Gain, Limiter  # noqa: E402

from utils.analysis_utils import get_temp_dir  # noqa: E402
from utils.loudness_utils import compute_lufs_and_lra  # noqa: E402
from utils.mastering_profiles_utils import get_mastering_profile  # noqa: E402


# ------------------------------------------------------------
# Medición de pico / true-peak
# ------------------------------------------------------------

def _peak_dbfs_sample(x: np.ndarray) -> float:
    """
    Pico sample-peak (no true-peak). Devuelve dBFS pudiendo ser > 0 si hay overs.
    """
    arr = np.asarray(x, dtype=np.float32)
    if arr.size == 0:
        return float("-inf")

    if arr.ndim == 1:
        peak = float(np.max(np.abs(arr)))
    else:
        peak = float(np.max(np.abs(arr)))

    if peak <= 0.0:
        return float("-inf")
    return float(20.0 * np.log10(peak))


def _true_peak_dbfs(x: np.ndarray, sr: int, oversample_factor: int = 4) -> float:
    """
    True-peak aproximado por oversampling.
    - Si SciPy está disponible, usa resample_poly (mejor).
    - Si no, cae a sample-peak.
    """
    arr = np.asarray(x, dtype=np.float32)
    if arr.size == 0 or sr <= 0:
        return float("-inf")

    try:
        from scipy.signal import resample_poly  # type: ignore
    except Exception:
        return _peak_dbfs_sample(arr)

    # Trabajar por canales sin mezclar
    if arr.ndim == 1:
        chans = [arr]
    elif arr.ndim == 2:
        chans = [arr[:, ch] for ch in range(arr.shape[1])]
    else:
        return _peak_dbfs_sample(arr)

    peaks = []
    for y in chans:
        # oversample (up = factor, down = 1)
        y_os = resample_poly(y, oversample_factor, 1)
        peaks.append(float(np.max(np.abs(y_os))) if y_os.size else 0.0)

    peak = float(max(peaks)) if peaks else 0.0
    if peak <= 0.0:
        return float("-inf")
    return float(20.0 * np.log10(peak))


def _measure_tp_dbfs(x: np.ndarray, sr: int) -> float:
    """
    Medición robusta: intenta true-peak; si algo falla, sample-peak.
    """
    try:
        return _true_peak_dbfs(x, sr, oversample_factor=4)
    except Exception:
        return _peak_dbfs_sample(x)


# ------------------------------------------------------------
# Procesos
# ------------------------------------------------------------

def load_analysis(contract_id: str) -> Dict[str, Any]:
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"
    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")
    with analysis_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _apply_limiter_chain(
    x: np.ndarray,
    sr: int,
    pre_gain_db: float,
    ceiling_db: float,
) -> np.ndarray:
    """
    Gain -> Limiter.
    Nota: Limiter de Pedalboard es dBFS (no true-peak). Aun así debe controlar overs sample-peak.
    """
    board = Pedalboard(
        [
            Gain(gain_db=float(pre_gain_db)),
            Limiter(threshold_db=float(ceiling_db)),
        ]
    )
    y = board(np.asarray(x, dtype=np.float32), sr)
    return np.asarray(y, dtype=np.float32)


def _apply_ms_width(
    x: np.ndarray,
    width_factor: float,
) -> Tuple[np.ndarray, float, float]:
    """
    Cambia anchura estéreo en M/S SIN hacer clip.
    Devuelve:
      y, ratio_pre, ratio_post   (RMS(S)/RMS(M))
    """
    arr = np.asarray(x, dtype=np.float32)

    # Mono -> no tocar
    if arr.ndim == 1 or (arr.ndim == 2 and arr.shape[1] == 1):
        mono = arr if arr.ndim == 1 else arr[:, 0]
        return mono.astype(np.float32), 0.0, 0.0

    if arr.ndim != 2 or arr.shape[1] < 2:
        raise ValueError("Se esperaba audio estéreo (N, 2+) para M/S width.")

    L = arr[:, 0]
    R = arr[:, 1]

    M = 0.5 * (L + R)
    S = 0.5 * (L - R)

    eps = 1e-12
    rms_M = float(np.sqrt(np.mean(M**2)) + eps)
    rms_S_pre = float(np.sqrt(np.mean(S**2)) + eps)
    ratio_pre = rms_S_pre / rms_M if rms_M > 0 else 0.0

    S_proc = S * float(width_factor)

    rms_S_post = float(np.sqrt(np.mean(S_proc**2)) + eps)
    ratio_post = rms_S_post / rms_M if rms_M > 0 else 0.0

    L_out = M + S_proc
    R_out = M - S_proc

    # mantener solo 2 canales (consistente con tu pipeline)
    y = np.stack([L_out, R_out], axis=1).astype(np.float32)
    return y, ratio_pre, ratio_post


def _enforce_ceiling_with_trim(
    x: np.ndarray,
    sr: int,
    ceiling_db: float,
    safety_db: float = 0.3,
) -> Tuple[np.ndarray, float, float]:
    """
    Asegura ceiling por trim global (NO clip).
    Devuelve:
      y_trim, trim_db, post_tp_db
    """
    tp = _measure_tp_dbfs(x, sr)
    target_tp = float(ceiling_db) - float(safety_db)

    if tp == float("-inf"):
        return x.astype(np.float32), 0.0, tp

    if tp <= target_tp:
        return x.astype(np.float32), 0.0, tp

    trim_db = target_tp - tp
    lin = 10.0 ** (trim_db / 20.0)
    y = (np.asarray(x, dtype=np.float32) * lin).astype(np.float32)
    tp2 = _measure_tp_dbfs(y, sr)
    return y, float(trim_db), float(tp2)


def _process_master(
    full_song_path: Path,
    max_limiter_gr_db: float,
    max_width_change_pct: float,
    target_lufs: float,
    target_lra_min: float,
    target_lra_max: float,
    target_ceiling: float,
    target_width_factor_style: float,
) -> Dict[str, float]:
    """
    Master robusto:
      - Pre métricas
      - Pre-gain (limitado por headroom+GR)
      - Gain->Limiter
      - M/S width (limitado)
      - Ceiling enforcement con trim (sin clip)
      - Write FLOAT
    """
    y, sr = sf.read(full_song_path, always_2d=False)
    y = np.asarray(y, dtype=np.float32)

    pre_tp = _measure_tp_dbfs(y, sr)
    pre_sample_peak = _peak_dbfs_sample(y)
    pre_lufs, pre_lra = compute_lufs_and_lra(y, sr)

    logger.logger.info(
        f"[S9_MASTER_GENERIC] PRE: TP={pre_tp:.2f} dBTP, sample_peak={pre_sample_peak:.2f} dBFS, "
        f"LUFS={pre_lufs:.2f}, LRA={pre_lra:.2f}."
    )

    # ------------------------------------------------------------
    # 1) Calcular pre_gain_db hacia target LUFS, respetando GR máx.
    # ------------------------------------------------------------
    desired_gain_db = float(target_lufs - pre_lufs)

    # headroom hasta ceiling (si subes más, necesitarás limiting)
    headroom_db = float(target_ceiling - pre_tp)  # puede ser negativo

    if desired_gain_db > 0.0:
        # limiting requerido si deseamos superar el headroom
        limiting_needed_db = max(0.0, desired_gain_db - headroom_db)
        if limiting_needed_db > max_limiter_gr_db:
            # cap por GR: solo puedo exceder el headroom en max_limiter_gr_db
            pre_gain_db = headroom_db + max_limiter_gr_db
        else:
            pre_gain_db = desired_gain_db

        # no tiene sentido aplicar pre_gain negativo aquí
        pre_gain_db = max(0.0, float(pre_gain_db))
    else:
        # estamos por encima de target -> atenuar sin necesidad de GR
        pre_gain_db = float(desired_gain_db)

    # ignorar microcambios
    if abs(pre_gain_db) < 0.05:
        pre_gain_db = 0.0

    # Sanity: si el pre_tp es raro, evitamos subir una barbaridad
    HARD_PREGAIN_CAP = 12.0
    if pre_gain_db > HARD_PREGAIN_CAP:
        logger.logger.info(
            f"[S9_MASTER_GENERIC] Aviso: pre_gain_db={pre_gain_db:.2f} dB demasiado alto; "
            f"cap a {HARD_PREGAIN_CAP:.2f} dB por seguridad."
        )
        pre_gain_db = HARD_PREGAIN_CAP

    logger.logger.info(
        f"[S9_MASTER_GENERIC] desired_gain={desired_gain_db:+.2f} dB, "
        f"headroom_to_ceiling={headroom_db:+.2f} dB, "
        f"pre_gain_aplicado={pre_gain_db:+.2f} dB (GRmax={max_limiter_gr_db:.2f} dB)."
    )

    # ------------------------------------------------------------
    # 2) Gain -> Limiter
    # ------------------------------------------------------------
    tp_pre_limiter = _measure_tp_dbfs(y * (10.0 ** (pre_gain_db / 20.0)), sr)
    y_lim = _apply_limiter_chain(y, sr, pre_gain_db, target_ceiling)

    tp_post_limiter = _measure_tp_dbfs(y_lim, sr)
    sample_peak_post_limiter = _peak_dbfs_sample(y_lim)
    post_lim_lufs, post_lim_lra = compute_lufs_and_lra(y_lim, sr)

    # Estimación de GR “de pico” (no perfecta, pero consistente)
    limiter_gr_est = max(0.0, float(tp_pre_limiter - tp_post_limiter))

    logger.logger.info(
        f"[S9_MASTER_GENERIC] POST-LIMITER: TP={tp_post_limiter:.2f} dBTP, "
        f"sample_peak={sample_peak_post_limiter:.2f} dBFS, "
        f"LUFS={post_lim_lufs:.2f}, LRA={post_lim_lra:.2f}, "
        f"GR_est≈{limiter_gr_est:.2f} dB."
    )

    # Si el limitador no está controlando picos (anómalo), lo dejamos registrado
    if tp_post_limiter > target_ceiling + 0.2 and limiter_gr_est < 0.2 and pre_gain_db > 3.0:
        logger.logger.info(
            "[S9_MASTER_GENERIC] WARNING: El limitador parece no estar conteniendo picos "
            f"(TP_post={tp_post_limiter:.2f} > ceiling={target_ceiling:.2f} con GR≈{limiter_gr_est:.2f}). "
            "Se aplicará enforcement por trim final."
        )

    # ------------------------------------------------------------
    # 3) M/S width (limitado)
    # ------------------------------------------------------------
    max_width_delta = float(max_width_change_pct) / 100.0
    raw_delta = float(target_width_factor_style) - 1.0
    clamped_delta = max(-max_width_delta, min(max_width_delta, raw_delta))
    width_factor = 1.0 + clamped_delta

    logger.logger.info(
        f"[S9_MASTER_GENERIC] width_target_style={target_width_factor_style:.2f}, "
        f"width_factor_aplicado={width_factor:.3f} (maxΔ={max_width_delta*100:.1f}%)."
    )

    y_ms, width_ratio_pre, width_ratio_post = _apply_ms_width(y_lim, width_factor)

    post_tp_pretrim = _measure_tp_dbfs(y_ms, sr)
    post_lufs_pretrim, post_lra_pretrim = compute_lufs_and_lra(y_ms, sr)

    # ------------------------------------------------------------
    # 4) Ceiling enforcement (trim) SIN clip
    # ------------------------------------------------------------
    y_final, trim_db, post_tp = _enforce_ceiling_with_trim(
        y_ms, sr, target_ceiling, safety_db=0.3
    )
    post_lufs, post_lra = compute_lufs_and_lra(y_final, sr)
    post_sample_peak = _peak_dbfs_sample(y_final)

    if trim_db != 0.0:
        logger.logger.info(
            f"[S9_MASTER_GENERIC] Trim final aplicado {trim_db:+.2f} dB "
            f"(TP antes={post_tp_pretrim:.2f} dB, después={post_tp:.2f} dB)."
        )

    logger.logger.info(
        f"[S9_MASTER_GENERIC] POST-FINAL: TP={post_tp:.2f} dBTP, sample_peak={post_sample_peak:.2f} dBFS, "
        f"LUFS={post_lufs:.2f}, LRA={post_lra:.2f}, "
        f"width_ratio_pre={width_ratio_pre:.3f}, width_ratio_post={width_ratio_post:.3f}."
    )

    # ------------------------------------------------------------
    # 5) Escritura FLOAT para evitar clip por PCM
    # ------------------------------------------------------------
    sf.write(full_song_path, y_final, sr, subtype="FLOAT")
    logger.logger.info(f"[S9_MASTER_GENERIC] Master reescrito (FLOAT) en {full_song_path}.")

    return {
        "pre_true_peak_dbtp": float(pre_tp),
        "pre_sample_peak_dbfs": float(pre_sample_peak),
        "pre_lufs_integrated": float(pre_lufs),
        "pre_lra": float(pre_lra),
        "pre_gain_db": float(pre_gain_db),

        "post_true_peak_lim_dbtp": float(tp_post_limiter),
        "post_sample_peak_lim_dbfs": float(sample_peak_post_limiter),
        "post_lufs_lim": float(post_lim_lufs),
        "post_lra_lim": float(post_lim_lra),
        "limiter_gr_db": float(limiter_gr_est),

        "post_true_peak_final_dbtp": float(post_tp),
        "post_sample_peak_final_dbfs": float(post_sample_peak),
        "post_lufs_final": float(post_lufs),
        "post_lra_final": float(post_lra),

        "width_ratio_pre": float(width_ratio_pre),
        "width_ratio_post": float(width_ratio_post),
        "width_factor_applied": float(width_factor),

        "trim_db": float(trim_db),
        "post_tp_pretrim": float(post_tp_pretrim),
        "post_lufs_pretrim": float(post_lufs_pretrim),
        "post_lra_pretrim": float(post_lra_pretrim),
    }


def main() -> None:
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S9_MASTER_GENERIC.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]
    analysis = load_analysis(contract_id)

    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}
    session: Dict[str, Any] = analysis.get("session", {}) or {}
    style_preset = analysis.get("style_preset", "default")

    max_limiter_gr_db = float(limits.get("max_limiter_gain_reduction_db", 4.0))
    max_width_change_pct = float(limits.get("max_stereo_width_change_percent", 10.0))

    mastering_targets: Dict[str, Any] = session.get("mastering_targets", {}) or {}
    m_profile = get_mastering_profile(style_preset)

    target_lufs = float(
        mastering_targets.get("target_lufs_integrated")
        or m_profile.get("target_lufs_integrated", -11.0)
    )
    target_lra_min = float(
        mastering_targets.get("target_lra_min")
        or m_profile.get("target_lra_min", 5.0)
    )
    target_lra_max = float(
        mastering_targets.get("target_lra_max")
        or m_profile.get("target_lra_max", 10.0)
    )
    target_ceiling = float(
        mastering_targets.get("target_ceiling_dbtp")
        or m_profile.get("target_ceiling_dbtp", -1.0)
    )
    target_width_factor_style = float(
        mastering_targets.get("target_ms_width_factor")
        or m_profile.get("target_ms_width_factor", 1.0)
    )

    temp_dir = get_temp_dir(contract_id, create=False)
    full_song_path = temp_dir / "full_song.wav"
    if not full_song_path.exists():
        logger.logger.info(f"[S9_MASTER_GENERIC] No existe {full_song_path}; no se puede aplicar mastering.")
        return

    result = _process_master(
        full_song_path=full_song_path,
        max_limiter_gr_db=max_limiter_gr_db,
        max_width_change_pct=max_width_change_pct,
        target_lufs=target_lufs,
        target_lra_min=target_lra_min,
        target_lra_max=target_lra_max,
        target_ceiling=target_ceiling,
        target_width_factor_style=target_width_factor_style,
    )

    metrics_path = temp_dir / "master_metrics_S9_MASTER_GENERIC.json"
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "contract_id": contract_id,
                "style_preset": style_preset,
                "targets": {
                    "target_lufs_integrated": target_lufs,
                    "target_lra_min": target_lra_min,
                    "target_lra_max": target_lra_max,
                    "target_ceiling_dbtp": target_ceiling,
                    "target_ms_width_factor": target_width_factor_style,
                    "max_limiter_gain_reduction_db": max_limiter_gr_db,
                    "max_stereo_width_change_percent": max_width_change_pct,
                },
                "pre": {
                    "true_peak_dbtp": result["pre_true_peak_dbtp"],
                    "sample_peak_dbfs": result["pre_sample_peak_dbfs"],
                    "lufs_integrated": result["pre_lufs_integrated"],
                    "lra": result["pre_lra"],
                },
                "post_limiter": {
                    "true_peak_dbtp": result["post_true_peak_lim_dbtp"],
                    "sample_peak_dbfs": result["post_sample_peak_lim_dbfs"],
                    "lufs_integrated": result["post_lufs_lim"],
                    "lra": result["post_lra_lim"],
                    "limiter_gr_db": result["limiter_gr_db"],
                    "pre_gain_db": result["pre_gain_db"],
                },
                "post_final": {
                    "true_peak_dbtp": result["post_true_peak_final_dbtp"],
                    "sample_peak_dbfs": result["post_sample_peak_final_dbfs"],
                    "lufs_integrated": result["post_lufs_final"],
                    "lra": result["post_lra_final"],
                    "width_ratio_pre": result["width_ratio_pre"],
                    "width_ratio_post": result["width_ratio_post"],
                    "width_factor_applied": result["width_factor_applied"],
                    "trim_db": result["trim_db"],
                    "post_tp_pretrim": result["post_tp_pretrim"],
                    "post_lufs_pretrim": result["post_lufs_pretrim"],
                    "post_lra_pretrim": result["post_lra_pretrim"],
                },
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    logger.logger.info(f"[S9_MASTER_GENERIC] Métricas guardadas en: {metrics_path}")


if __name__ == "__main__":
    main()
