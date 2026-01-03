# C:\mix-master\backend\src\stages\S3_LEADVOX_AUDIBILITY.py

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
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from utils.analysis_utils import get_temp_dir  # noqa: E402

try:
    # True peak oversampled (mismo enfoque que tu mastering)
    from utils.color_utils import compute_true_peak_dbfs  # type: ignore
except Exception:
    compute_true_peak_dbfs = None  # type: ignore


def load_analysis(contract_id: str) -> Dict[str, Any]:
    """
    Carga el JSON de análisis generado por analysis\\S3_LEADVOX_AUDIBILITY.py.
    """
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def _compute_lead_gain_db(
    session: Dict[str, Any],
    metrics: Dict[str, Any],
    limits: Dict[str, Any],
) -> tuple[float, float]:
    """
    Calcula el gain global a aplicar a las pistas de lead vocal.

    offset = LUFS_lead_short_term - LUFS_bed_short_term (media global).
    Queremos que offset esté dentro de [offset_min, offset_max].

    Devuelve:
      - gain_db
      - target_offset_db usado
    """
    offset_min = float(metrics.get("short_term_lufs_offset_vs_mixbus_min_db", -3.0))
    offset_max = float(metrics.get("short_term_lufs_offset_vs_mixbus_max_db", 3.0))

    offset_mean = session.get("global_short_term_offset_mean_db")
    if offset_mean is None:
        return 0.0, 0.0

    try:
        offset_mean = float(offset_mean)
    except (TypeError, ValueError):
        return 0.0, 0.0

    max_gain_step = float(limits.get("max_gain_change_db_per_pass", 2.0))
    max_steps = int(limits.get("max_steps_per_pass", 2))  # default conservador
    max_total_gain = max_gain_step * max_steps

    # Margen coherente con QC
    MARGIN_DB = 0.5
    if offset_min - MARGIN_DB <= offset_mean <= offset_max + MARGIN_DB:
        # Ya está OK → no-op
        return 0.0, float(metrics.get("target_lead_offset_db", 0.0) or 0.0)

    # Target explícito (opcional)
    target_offset = metrics.get("target_lead_offset_db")
    if target_offset is None:
        # Default conservador: 2/3 del rango (menos “adelante” que ir siempre a 0/centro)
        target_offset = offset_min + 0.66 * (offset_max - offset_min)

    try:
        target_offset = float(target_offset)
    except (TypeError, ValueError):
        target_offset = 0.5 * (offset_min + offset_max)

    desired_gain = target_offset - offset_mean

    # Clamp por pasos
    if desired_gain > max_total_gain:
        gain_db = max_total_gain
    elif desired_gain < -max_total_gain:
        gain_db = -max_total_gain
    else:
        gain_db = desired_gain

    # Ignorar micro-cambios
    if abs(gain_db) < 0.1:
        gain_db = 0.0

    logger.logger.info(
        f"[S3_LEADVOX_AUDIBILITY] offset_mean={offset_mean:.2f} dB (vs BED), "
        f"target_offset={target_offset:.2f} dB, desired_gain={desired_gain:.2f} dB, "
        f"gain_db_clamped={gain_db:.2f} dB (max_total={max_total_gain:.2f} dB)."
    )

    return float(gain_db), float(target_offset)


def _measure_true_peak_dbfs(arr: np.ndarray, sr: int) -> float:
    """
    Mide true peak (preferente) o peak sample si no hay util disponible.
    """
    x = np.asarray(arr, dtype=np.float32)
    if x.size == 0:
        return float("-inf")

    if compute_true_peak_dbfs is not None:
        try:
            return float(compute_true_peak_dbfs(x, oversample_factor=4))
        except Exception:
            pass

    pk = float(np.max(np.abs(x))) if x.size else 0.0
    if pk <= 0.0:
        return float("-inf")
    return float(20.0 * np.log10(pk))


def _apply_gain_to_lead_worker(
    args: Tuple[str, Dict[str, Any], float]
) -> bool:
    """
    Aplica el gain lineal a un stem de lead vocal y sobrescribe el archivo.

    Escribe en FLOAT para evitar clipping por formato PCM.
    """
    temp_dir_str, stem, gain_lin = args
    temp_dir = Path(temp_dir_str)

    if not stem.get("is_lead_vocal", False):
        return False

    fname = stem.get("file_name")
    if not fname:
        return False

    path = temp_dir / fname
    if not path.exists():
        return False

    data, sr = sf.read(path, always_2d=False)
    data = np.asarray(data, dtype=np.float32)

    if data.size == 0:
        return False

    data_out = data * float(gain_lin)

    # Escritura segura en FLOAT
    sf.write(path, data_out.astype(np.float32), int(sr), subtype="FLOAT")

    logger.logger.info(
        f"[S3_LEADVOX_AUDIBILITY] {fname}: aplicado gain {20.0 * np.log10(gain_lin):.2f} dB."
    )

    return True


def _save_leadvox_metrics(
    temp_dir: Path,
    contract_id: str,
    offset_min: float,
    offset_max: float,
    pre_offset_mean: float | None,
    target_offset: float,
    gain_db_applied: float,
    lead_tp_target: float,
    lead_pre_tp_max: float | None,
    lead_pred_post_tp_max: float | None,
) -> Path:
    """
    Guarda métricas del stage para QC.
    """
    metrics_path = temp_dir / "leadvox_metrics_S3_LEADVOX_AUDIBILITY.json"
    data = {
        "contract_id": contract_id,
        "offset_band_db": {"min": float(offset_min), "max": float(offset_max)},
        "pre": {"offset_mean_db": pre_offset_mean},
        "decision": {
            "target_offset_db": float(target_offset),
            "gain_db_applied": float(gain_db_applied),
        },
        "true_peak": {
            "lead_true_peak_target_max_dbtp": float(lead_tp_target),
            "lead_pre_tp_max_dbtp": lead_pre_tp_max,
            "lead_pred_post_tp_max_dbtp": lead_pred_post_tp_max,
        },
    }

    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.logger.info(
        f"[S3_LEADVOX_AUDIBILITY] Métricas guardadas en: {metrics_path}"
    )
    return metrics_path


def main() -> None:
    """
    Stage S3_LEADVOX_AUDIBILITY:

      - Lee analysis_S3_LEADVOX_AUDIBILITY.json (offset vs BED).
      - Calcula gain global en dB para lead vocal.
      - Limita el boost por true-peak objetivo (headroom real del stem vocal).
      - Aplica gain a stems lead vocal y escribe en FLOAT.
      - Guarda métricas del stage para QC.
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S3_LEADVOX_AUDIBILITY.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S3_LEADVOX_AUDIBILITY"

    analysis = load_analysis(contract_id)

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}
    session: Dict[str, Any] = analysis.get("session", {}) or {}
    stems: List[Dict[str, Any]] = analysis.get("stems", []) or []

    try:
        offset_min = float(metrics.get("short_term_lufs_offset_vs_mixbus_min_db", -3.0))
        offset_max = float(metrics.get("short_term_lufs_offset_vs_mixbus_max_db", 3.0))
    except (TypeError, ValueError):
        offset_min, offset_max = -3.0, 3.0

    pre_offset_mean = session.get("global_short_term_offset_mean_db")
    if pre_offset_mean is not None:
        try:
            pre_offset_mean = float(pre_offset_mean)
        except (TypeError, ValueError):
            pre_offset_mean = None

    # Filtrar stems lead
    lead_stems: List[Dict[str, Any]] = [s for s in stems if s.get("is_lead_vocal", False)]
    temp_dir = get_temp_dir(contract_id, create=False)

    if not lead_stems or pre_offset_mean is None:
        logger.logger.info(
            "[S3_LEADVOX_AUDIBILITY] Sin stems lead o sin datos de offset; no-op."
        )
        _save_leadvox_metrics(
            temp_dir=temp_dir,
            contract_id=contract_id,
            offset_min=offset_min,
            offset_max=offset_max,
            pre_offset_mean=pre_offset_mean,
            target_offset=float(metrics.get("target_lead_offset_db", 0.0) or 0.0),
            gain_db_applied=0.0,
            lead_tp_target=float(limits.get("lead_true_peak_target_max_dbtp", -3.0)),
            lead_pre_tp_max=None,
            lead_pred_post_tp_max=None,
        )
        return

    gain_db, target_offset = _compute_lead_gain_db(session, metrics, limits)

    # Cap por true-peak real del stem vocal
    lead_tp_target = float(limits.get("lead_true_peak_target_max_dbtp", -3.0))

    pre_tps: List[float] = []
    for s in lead_stems:
        fname = s.get("file_name")
        if not fname:
            continue
        p = temp_dir / fname
        if not p.exists():
            continue
        y, sr = sf.read(p, always_2d=False)
        arr = np.asarray(y, dtype=np.float32)
        if arr.size == 0:
            continue
        tp = _measure_true_peak_dbfs(arr, int(sr))
        pre_tps.append(tp)

    lead_pre_tp_max = max(pre_tps) if pre_tps else None

    if gain_db > 0.0 and lead_pre_tp_max is not None:
        allowed_gain = lead_tp_target - float(lead_pre_tp_max)
        if allowed_gain < gain_db:
            logger.logger.info(
                f"[S3_LEADVOX_AUDIBILITY] Cap por true-peak: gain {gain_db:.2f} -> {allowed_gain:.2f} dB "
                f"(lead_tp_target={lead_tp_target:.2f}, pre_tp_max={lead_pre_tp_max:.2f})."
            )
            gain_db = max(0.0, float(allowed_gain))

    if abs(gain_db) < 1e-6:
        logger.logger.info(
            "[S3_LEADVOX_AUDIBILITY] Lead vocal ya en rango / cap por TP / sin necesidad; no-op."
        )
        lead_pred_post_tp_max = (
            (lead_pre_tp_max + 0.0) if lead_pre_tp_max is not None else None
        )
        _save_leadvox_metrics(
            temp_dir=temp_dir,
            contract_id=contract_id,
            offset_min=offset_min,
            offset_max=offset_max,
            pre_offset_mean=float(pre_offset_mean),
            target_offset=target_offset,
            gain_db_applied=0.0,
            lead_tp_target=lead_tp_target,
            lead_pre_tp_max=lead_pre_tp_max,
            lead_pred_post_tp_max=lead_pred_post_tp_max,
        )
        return

    gain_lin = float(10.0 ** (gain_db / 20.0))

    args_list: List[Tuple[str, Dict[str, Any], float]] = [
        (str(temp_dir), stem, gain_lin) for stem in lead_stems
    ]

    results = [bool(_apply_gain_to_lead_worker(args)) for args in args_list]
    processed = sum(1 for r in results if r)

    # Predicción post (para QC): TP_post ≈ TP_pre + gain_db
    lead_pred_post_tp_max = (
        (float(lead_pre_tp_max) + float(gain_db)) if lead_pre_tp_max is not None else None
    )

    _save_leadvox_metrics(
        temp_dir=temp_dir,
        contract_id=contract_id,
        offset_min=offset_min,
        offset_max=offset_max,
        pre_offset_mean=float(pre_offset_mean),
        target_offset=target_offset,
        gain_db_applied=float(gain_db),
        lead_tp_target=lead_tp_target,
        lead_pre_tp_max=lead_pre_tp_max,
        lead_pred_post_tp_max=lead_pred_post_tp_max,
    )

    logger.logger.info(
        f"[S3_LEADVOX_AUDIBILITY] Aplicado gain global de {gain_db:.2f} dB "
        f"a {processed} stems de lead vocal (ref=BED)."
    )


if __name__ == "__main__":
    main()
