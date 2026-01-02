# C:\mix-master\backend\src\stages\S1_STEM_WORKING_LOUDNESS.py

from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import os  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
from concurrent.futures import ThreadPoolExecutor, as_completed  # noqa: E402

from utils.analysis_utils import get_temp_dir  # noqa: E402
from utils.profiles_utils import get_instrument_profile  # noqa: E402


def load_analysis(contract_id: str) -> Dict[str, Any]:
    """
    Carga el JSON de análisis generado por analysis\\S1_STEM_WORKING_LOUDNESS.py.
    """
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _peak_dbfs_from_audio(x: np.ndarray, eps: float = 1e-12) -> float:
    if x.size == 0:
        return float("-inf")
    peak = float(np.max(np.abs(x)))
    if peak <= 0.0:
        return float("-inf")
    return float(20.0 * np.log10(peak + eps))


def compute_gain_db_for_stem(
    stem_info: Dict[str, Any],
    true_peak_target_dbtp: float,
    max_gain_change_db_per_pass: float | None,
    lufs_tolerance_db: float,
    max_cut_db_per_pass: float,
    min_active_ratio_to_adjust: float,
) -> Tuple[float, str]:
    """
    Calcula ganancia por stem de forma segura:
      - Usa active_lufs (fallback a integrated_lufs)
      - Sólo ajusta si está fuera del rango (no al punto medio)
      - Limita recortes fuertes (max_cut_db_per_pass)
      - Al subir, limita por pico para no superar true_peak_target
    """
    inst_profile_id = stem_info.get("instrument_profile_resolved", "Other")
    profile = get_instrument_profile(inst_profile_id)
    lufs_range = profile.get("work_loudness_lufs_range")

    # Loudness: preferimos active_lufs
    lufs = stem_info.get("active_lufs", None)
    if lufs is None or lufs == float("-inf"):
        lufs = stem_info.get("integrated_lufs", None)

    measured_peak_dbfs = stem_info.get("true_peak_dbfs", None)
    if measured_peak_dbfs is None or measured_peak_dbfs == float("-inf"):
        measured_peak_dbfs = -120.0

    # Actividad
    activity = stem_info.get("activity", {}) or {}
    active_ratio = float(activity.get("active_ratio", 1.0))
    if active_ratio < float(min_active_ratio_to_adjust):
        # Stem muy “espaciado” o casi vacío: no re-normalizar por loudness (evita decisiones malas).
        return 0.0, f"skip_low_activity(active_ratio={active_ratio:.3f})"

    # Si no hay rango definido o no hay loudness medible: no tocamos
    if not isinstance(lufs_range, list) or len(lufs_range) != 2 or lufs is None:
        return 0.0, "skip_no_lufs_range"

    target_min, target_max = float(lufs_range[0]), float(lufs_range[1])
    lufs_f = float(lufs)

    # Normalización por rango (no midpoint):
    upper = target_max + float(lufs_tolerance_db)
    lower = target_min - float(lufs_tolerance_db)

    if lufs_f > upper:
        # demasiado alto -> cortar hacia target_max (no hacia midpoint)
        desired_gain_db = target_max - lufs_f  # negativo
        reason = f"too_loud(lufs={lufs_f:.2f} > {upper:.2f})"
    elif lufs_f < lower:
        # demasiado bajo -> subir hacia target_min
        desired_gain_db = target_min - lufs_f  # positivo
        reason = f"too_quiet(lufs={lufs_f:.2f} < {lower:.2f})"
    else:
        return 0.0, f"in_range(lufs={lufs_f:.2f})"

    gain_db = float(desired_gain_db)

    # 1) Límite general por contrato (si existe)
    if max_gain_change_db_per_pass is not None:
        mg = float(max_gain_change_db_per_pass)
        gain_db = max(-mg, min(mg, gain_db))

    # 2) Safety cap para recortes (evita caídas tipo -7 dB)
    if gain_db < -float(max_cut_db_per_pass):
        gain_db = -float(max_cut_db_per_pass)
        reason += f" | cap_cut({max_cut_db_per_pass:.2f}dB)"

    # 3) Clamp por pico al subir (aprox: dBFS ≈ dBTP para este uso)
    if gain_db > 0.0:
        allowed_gain = float(true_peak_target_dbtp) - float(measured_peak_dbfs) - 0.05  # margen
        if gain_db > allowed_gain:
            gain_db = max(0.0, allowed_gain)
            reason += f" | peak_clamp(allowed={allowed_gain:.2f}dB)"

    # 4) Ignorar microcambios
    if abs(gain_db) < 0.10:
        return 0.0, "tiny_change"

    return float(gain_db), reason


def apply_gain_to_stem(file_path: Path, gain_db: float) -> Tuple[float, float]:
    """
    Aplica la ganancia en dB al stem y sobrescribe el archivo.
    Devuelve (peak_pre_dbfs, peak_post_dbfs) para logging.
    """
    data, sr = sf.read(file_path, always_2d=False)

    data = np.asarray(data, dtype=np.float32)
    if data.size == 0 or gain_db == 0.0:
        peak = _peak_dbfs_from_audio(data)
        return peak, peak

    peak_pre = _peak_dbfs_from_audio(data)

    scale = float(10.0 ** (gain_db / 20.0))
    data_out = data * scale

    peak_post = _peak_dbfs_from_audio(data_out)

    # Escribimos en float para mantener consistencia tras S0_SESSION_FORMAT
    sf.write(file_path, data_out, sr, subtype="FLOAT")
    return peak_pre, peak_post


def _process_one(
    stem_info: Dict[str, Any],
    true_peak_target_dbtp: float,
    max_gain_change_db_per_pass: float | None,
    lufs_tolerance_db: float,
    max_cut_db_per_pass: float,
    min_active_ratio_to_adjust: float,
) -> Tuple[str, float, str]:
    file_path = Path(stem_info["file_path"])
    stem_name = stem_info.get("file_name", file_path.name)

    gain_db, reason = compute_gain_db_for_stem(
        stem_info=stem_info,
        true_peak_target_dbtp=float(true_peak_target_dbtp),
        max_gain_change_db_per_pass=max_gain_change_db_per_pass,
        lufs_tolerance_db=float(lufs_tolerance_db),
        max_cut_db_per_pass=float(max_cut_db_per_pass),
        min_active_ratio_to_adjust=float(min_active_ratio_to_adjust),
    )

    if gain_db != 0.0:
        peak_pre, peak_post = apply_gain_to_stem(file_path, gain_db)
        logger.logger.info(
            f"[S1_STEM_WORKING_LOUDNESS] {stem_name}: gain={gain_db:+.2f} dB | "
            f"peak_pre={peak_pre:.2f} dBFS -> peak_post={peak_post:.2f} dBFS | {reason}"
        )
    else:
        logger.logger.info(
            f"[S1_STEM_WORKING_LOUDNESS] {stem_name}: gain=+0.00 dB | {reason}"
        )

    return stem_name, float(gain_db), reason


def main() -> None:
    """
    Stage S1_STEM_WORKING_LOUDNESS:
      - Lee analysis_S1_STEM_WORKING_LOUDNESS.json.
      - Ajusta stems de forma conservadora (por rango + silencios + clamp por pico).
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S1_STEM_WORKING_LOUDNESS.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]

    analysis = load_analysis(contract_id)

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    session_metrics: Dict[str, Any] = analysis.get("session", {}) or {}
    stems: List[Dict[str, Any]] = analysis.get("stems", []) or []

    true_peak_target_dbtp = float(session_metrics.get("true_peak_per_stem_target_max_dbtp", -3.0))

    # Parámetros (compatibles hacia atrás)
    max_gain_change_db_per_pass = metrics.get("max_gain_change_db_per_pass", None)

    # NUEVOS (opcionales, con defaults seguros)
    lufs_tolerance_db = float(metrics.get("lufs_tolerance_db", 1.0))
    max_cut_db_per_pass = float(metrics.get("max_cut_db_per_pass", 3.0))  # clave para evitar bajadas salvajes
    min_active_ratio_to_adjust = float(metrics.get("min_active_ratio_to_adjust", 0.05))

    max_workers = int(metrics.get("max_workers", 4))
    max_workers = max(1, min(max_workers, os.cpu_count() or 1))

    if not stems:
        logger.logger.info("[S1_STEM_WORKING_LOUDNESS] No hay stems en el análisis; nothing to do.")
        return

    # Paralelización segura en entorno daemon: threads (I/O + multiplicación)
    args = [
        (stem, true_peak_target_dbtp, max_gain_change_db_per_pass, lufs_tolerance_db, max_cut_db_per_pass, min_active_ratio_to_adjust)
        for stem in stems
    ]

    total_changed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [
            ex.submit(_process_one, *a)
            for a in args
        ]
        for fut in as_completed(futures):
            stem_name, gain_db, _reason = fut.result()
            if gain_db != 0.0:
                total_changed += 1

    logger.logger.info(
        f"[S1_STEM_WORKING_LOUDNESS] Normalización de trabajo completada para {len(stems)} stems. "
        f"Stems modificados={total_changed}."
    )


if __name__ == "__main__":
    main()
