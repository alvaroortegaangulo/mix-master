# C:\mix-master\backend\src\stages\S9_MASTER_GENERIC.py

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

from pedalboard import Pedalboard, Gain, Limiter  # noqa: E402

from utils.analysis_utils import get_temp_dir
from utils.loudness_utils import compute_lufs_and_lra  # noqa: E402
from utils.color_utils import compute_true_peak_dbfs  # noqa: E402
from utils.mastering_profiles_utils import get_mastering_profile  # noqa: E402


# Sample rate global para el limitador de Pedalboard
_MASTER_SAMPLE_RATE: float | None = None


def load_analysis(contract_id: str) -> Dict[str, Any]:
    """
    Carga el JSON de análisis generado por analysis\\S9_MASTER_GENERIC.py.
    """
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def _apply_limiter(
    x: np.ndarray,
    pre_gain_db: float,
    ceiling_dbtp: float,
) -> tuple[np.ndarray, float]:
    """
    Aplica:

      - pre-gain en dB (vía pedalboard.Gain)
      - limitador (vía pedalboard.Limiter) con threshold en ceiling_dbtp

    Devuelve:
      - audio limitado
      - gain reduction máxima en picos (dB aprox).
    """
    global _MASTER_SAMPLE_RATE
    if _MASTER_SAMPLE_RATE is None:
        raise RuntimeError(
            "Sample rate no definido en _MASTER_SAMPLE_RATE antes de llamar a _apply_limiter."
        )

    sr = _MASTER_SAMPLE_RATE

    # Normalizar a float32
    arr = np.asarray(x, dtype=np.float32)

    # Para medir GR, calculamos el peak tras pre-gain pero antes del limitador
    pre_gain_lin = 10.0 ** (pre_gain_db / 20.0)
    y_pre = arr * pre_gain_lin
    pre_peak = compute_true_peak_dbfs(y_pre, oversample_factor=4)

    # Cadena de mastering: Gain (pre-gain) -> Limiter (ceiling)
    board = Pedalboard(
        [
            Gain(gain_db=float(pre_gain_db)),
            Limiter(threshold_db=float(ceiling_dbtp)),
        ]
    )

    # Ejecutar limitador
    y_lim = board(arr, sr)

    # Medir peak tras el limitador
    y_lim = np.asarray(y_lim, dtype=np.float32)
    post_peak = compute_true_peak_dbfs(y_lim, oversample_factor=4)

    # GR aproximada en el peor pico
    gr_db = max(0.0, (pre_peak - post_peak))

    # Mantener la forma original: si entrada era 1D, devolvemos 1D
    if x.ndim == 1 and y_lim.ndim == 2 and y_lim.shape[1] == 1:
        y_lim = y_lim[:, 0]

    return y_lim.astype(np.float32), gr_db


def _apply_ms_width(
    x: np.ndarray,
    width_factor: float,
) -> tuple[np.ndarray, float, float]:
    """
    Aplica un cambio de anchura estéreo en dominio M/S.

    - width_factor: factor multiplicador de S (1.0 = neutro).

    Devuelve:
      - audio procesado
      - ratio_pre = RMS(S)/RMS(M) antes
      - ratio_post = RMS(S)/RMS(M) después

    Si la señal es mono, no se aplica cambio (factor efectivo=1).
    """
    arr = np.asarray(x, dtype=np.float32)
    if arr.ndim == 1 or (arr.ndim == 2 and arr.shape[1] == 1):
        # Mono; sin cambio
        mono = arr if arr.ndim == 1 else arr[:, 0]
        return mono.astype(np.float32), 0.0, 0.0

    # Esperamos forma (N, 2)
    if arr.ndim != 2 or arr.shape[1] < 2:
        raise ValueError("Se esperaba audio estéreo (N, 2) para M/S width.")

    L = arr[:, 0]
    R = arr[:, 1]

    M = 0.5 * (L + R)
    S = 0.5 * (L - R)

    # RMS M/S pre
    eps = 1e-9
    rms_M_pre = float(np.sqrt(np.mean(M**2)) + eps)
    rms_S_pre = float(np.sqrt(np.mean(S**2)) + eps)
    ratio_pre = rms_S_pre / rms_M_pre if rms_M_pre > 0 else 0.0

    # Aplicar factor
    S_proc = S * float(width_factor)

    rms_S_post = float(np.sqrt(np.mean(S_proc**2)) + eps)
    ratio_post = rms_S_post / rms_M_pre if rms_M_pre > 0 else 0.0

    # Reconstrucción L/R
    L_out = M + S_proc
    R_out = M - S_proc

    y = np.stack([L_out, R_out], axis=1)

    # Clamp suave por seguridad
    y = np.clip(y, -1.0, 1.0)

    return y.astype(np.float32), ratio_pre, ratio_post


def _process_master_worker(
    full_song_path_str: str,
    max_limiter_gr_db: float,
    max_width_change_pct: float,
    target_lufs: float,
    target_lra_min: float,
    target_lra_max: float,
    target_ceiling: float,
    target_width_factor_style: float,
) -> Dict[str, float]:
    """
    Worker que realiza todo el procesado de mastering:

      - Lee full_song.wav.
      - Calcula métricas pre (TP, LUFS, LRA).
      - Calcula pre_gain_db limitado por max_limiter_gr_db.
      - Aplica limitador (Pedalboard) con ceiling target_ceiling.
      - Aplica cambio de anchura M/S limitado por max_width_change_pct.
      - Escribe el audio procesado en full_song.wav.
      - Devuelve todas las métricas necesarias.
    """
    global _MASTER_SAMPLE_RATE

    full_song_path = Path(full_song_path_str)

    # Leer audio actual
    y, sr = sf.read(full_song_path, always_2d=False)
    if not isinstance(y, np.ndarray):
        y = np.asarray(y, dtype=np.float32)
    else:
        y = y.astype(np.float32)

    _MASTER_SAMPLE_RATE = float(sr)

    pre_true_peak = compute_true_peak_dbfs(y, oversample_factor=4)
    pre_lufs, pre_lra = compute_lufs_and_lra(y, sr)

    logger.logger.info(
        f"[S9_MASTER_GENERIC] PRE: true_peak={pre_true_peak:.2f} dBTP, "
        f"LUFS={pre_lufs:.2f}, LRA={pre_lra:.2f}."
    )

    # 1) Calcular pre-gain para acercar LUFS al target, respetando límite de GR
    delta_lufs = target_lufs - pre_lufs  # cuánto nos gustaría subir/bajar

    pre_gain_db = 0.0
    if delta_lufs > 0.0:
        # Queremos subir volumen. Limitamos por GR:
        # pre_peak + pre_gain_db - target_ceiling <= max_limiter_gr_db
        allowed_gain_by_gr = max_limiter_gr_db + target_ceiling - pre_true_peak
        pre_gain_db = min(delta_lufs, allowed_gain_by_gr)
        pre_gain_db = max(pre_gain_db, 0.0)
    else:
        # Si estamos por encima del target, atenuamos (no limitado por GR)
        pre_gain_db = delta_lufs  # valor negativo

    logger.logger.info(
        f"[S9_MASTER_GENERIC] delta_lufs={delta_lufs:+.2f} dB, "
        f"pre_gain_db aplicado={pre_gain_db:+.2f} dB (limitado por GR máx={max_limiter_gr_db:.1f} dB)."
    )

    # 2) Aplicar limitador con ceiling target_ceiling (Pedalboard)
    y_limited, limiter_gr_db = _apply_limiter(y, pre_gain_db, target_ceiling)

    # Métricas tras limitador (antes de width)
    post_true_peak_lim = compute_true_peak_dbfs(y_limited, oversample_factor=4)
    post_lufs_lim, post_lra_lim = compute_lufs_and_lra(y_limited, sr)

    logger.logger.info(
        f"[S9_MASTER_GENERIC] POST-LIMITER: true_peak={post_true_peak_lim:.2f} dBTP, "
        f"LUFS={post_lufs_lim:.2f}, LRA={post_lra_lim:.2f}, "
        f"limiter_GR_max≈{limiter_gr_db:.2f} dB."
    )

    # 3) Ajuste moderado de anchura estéreo M/S
    max_width_delta = max_width_change_pct / 100.0  # p.ej. 0.10

    # Queremos movernos hacia el factor objetivo de estilo, pero acotado
    raw_delta = target_width_factor_style - 1.0
    clamped_delta = max(-max_width_delta, min(max_width_delta, raw_delta))
    width_factor = 1.0 + clamped_delta

    logger.logger.info(
        f"[S9_MASTER_GENERIC] target_width_style={target_width_factor_style:.2f}, "
        f"width_factor_aplicado={width_factor:.2f} (máx cambio={max_width_delta*100:.1f}%)."
    )

    y_ms, width_ratio_pre, width_ratio_post = _apply_ms_width(y_limited, width_factor)

    # 4) Métricas post-width (antes de trim de seguridad)
    post_true_peak = compute_true_peak_dbfs(y_ms, oversample_factor=4)
    post_lufs, post_lra = compute_lufs_and_lra(y_ms, sr)

    # 4.b) Trim de seguridad para asegurar que TP_final queda bajo el ceiling
    CEIL_SAFETY_DB = 0.3  # dejaremos el pico aprox. a ceiling - 0.3 dB
    trim_peak_db = 0.0
    if post_true_peak > target_ceiling:
        # Queremos llevar el pico a (ceiling - CEIL_SAFETY_DB)
        trim_peak_db = (target_ceiling - CEIL_SAFETY_DB) - post_true_peak
        trim_lin = 10.0 ** (trim_peak_db / 20.0)
        y_ms = (y_ms * trim_lin).astype(np.float32)

        # Recalcular métricas tras el safety trim
        post_true_peak = compute_true_peak_dbfs(y_ms, oversample_factor=4)
        post_lufs, post_lra = compute_lufs_and_lra(y_ms, sr)

        logger.logger.info(
            f"[S9_MASTER_GENERIC] Safety trim adicional de {trim_peak_db:+.2f} dB "
            f"para respetar ceiling {target_ceiling:.2f} dBTP con holgura."
        )

    logger.logger.info(
        f"[S9_MASTER_GENERIC] POST-FINAL: true_peak={post_true_peak:.2f} dBTP, "
        f"LUFS={post_lufs:.2f}, LRA={post_lra:.2f}, "
        f"width_ratio_pre={width_ratio_pre:.3f}, width_ratio_post={width_ratio_post:.3f}."
    )

    # Clamp final por seguridad
    y_ms = np.clip(y_ms, -1.0, 1.0).astype(np.float32)

    # Escribir master final (sobrescribiendo full_song.wav)
    sf.write(full_song_path, y_ms, sr)
    logger.logger.info(f"[S9_MASTER_GENERIC] Master final reescrito en {full_song_path}.")


    return {
        "pre_true_peak_dbtp": float(pre_true_peak),
        "pre_lufs_integrated": float(pre_lufs),
        "pre_lra": float(pre_lra),
        "pre_gain_db": float(pre_gain_db),
        "post_true_peak_lim_dbtp": float(post_true_peak_lim),
        "post_lufs_lim": float(post_lufs_lim),
        "post_lra_lim": float(post_lra_lim),
        "limiter_gr_db": float(limiter_gr_db),
        "post_true_peak_final_dbtp": float(post_true_peak),
        "post_lufs_final": float(post_lufs),
        "post_lra_final": float(post_lra),
        "width_ratio_pre": float(width_ratio_pre),
        "width_ratio_post": float(width_ratio_post),
        "width_factor_applied": float(width_factor),
    }


def main() -> None:
    """
    Stage S9_MASTER_GENERIC:

      - Lee analysis_S9_MASTER_GENERIC.json y el full_song.wav actual.
      - Calcula objetivos de mastering a partir de contrato + perfil de estilo.
      - El worker aplica pre-gain + limitador (Pedalboard) + ajuste M/S.
      - Recalcula métricas post y las guarda en master_metrics_S9_MASTER_GENERIC.json.
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S9_MASTER_GENERIC.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S9_MASTER_GENERIC"

    analysis = load_analysis(contract_id)

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
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
        logger.logger.info(
            f"[S9_MASTER_GENERIC] No existe {full_song_path}; "
            "no se puede aplicar mastering."
        )
        return

    # Procesar master en serie
    result = _process_master_worker(
        str(full_song_path),
        max_limiter_gr_db,
        max_width_change_pct,
        target_lufs,
        target_lra_min,
        target_lra_max,
        target_ceiling,
        target_width_factor_style,
    )

    # Guardar métricas para el futuro check
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
                    "lufs_integrated": result["pre_lufs_integrated"],
                    "lra": result["pre_lra"],
                },
                "post_limiter": {
                    "true_peak_dbtp": result["post_true_peak_lim_dbtp"],
                    "lufs_integrated": result["post_lufs_lim"],
                    "lra": result["post_lra_lim"],
                    "limiter_gr_db": result["limiter_gr_db"],
                    "pre_gain_db": result["pre_gain_db"],
                },
                "post_final": {
                    "true_peak_dbtp": result["post_true_peak_final_dbtp"],
                    "lufs_integrated": result["post_lufs_final"],
                    "lra": result["post_lra_final"],
                    "width_ratio_pre": result["width_ratio_pre"],
                    "width_ratio_post": result["width_ratio_post"],
                    "width_factor_applied": result["width_factor_applied"],
                },
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    logger.logger.info(
        f"[S9_MASTER_GENERIC] Métricas de mastering guardadas en: {metrics_path}"
    )


if __name__ == "__main__":
    main()
