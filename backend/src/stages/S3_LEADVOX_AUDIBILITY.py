# C:\mix-master\backend\src\stages\S3_LEADVOX_AUDIBILITY.py

from __future__ import annotations

import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.analysis_utils import get_temp_dir  # noqa: E402

try:
    # True peak oversampled (mismo enfoque que tu mastering)
    from utils.color_utils import compute_true_peak_dbfs  # type: ignore
except Exception:
    compute_true_peak_dbfs = None  # type: ignore


# ---------------------------------------------------------------------
# Logger robusto
# ---------------------------------------------------------------------
def _get_log(name: str) -> logging.Logger:
    try:
        from utils.logger import logger as _logger_singleton  # type: ignore
        if hasattr(_logger_singleton, "logger"):
            return _logger_singleton.logger
        return _logger_singleton
    except Exception:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        )
        return logging.getLogger(name)


LOG = _get_log("S3_LEADVOX_AUDIBILITY_STAGE")


def load_analysis(contract_id: str) -> Dict[str, Any]:
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"
    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")
    with analysis_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _measure_true_peak_dbfs(arr: np.ndarray, sr: int) -> float:
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


def _moving_average(x: np.ndarray, win: int) -> np.ndarray:
    if win <= 1 or x.size == 0:
        return x
    win = int(win)
    if win % 2 == 0:
        win += 1
    pad = win // 2
    xp = np.pad(x, (pad, pad), mode="edge")
    k = np.ones(win, dtype=np.float32) / float(win)
    y = np.convolve(xp, k, mode="valid")
    return y.astype(np.float32)


def _build_gain_curve_db(
    offsets_db: List[float],
    window_starts_sec: List[float],
    window_sec: float,
    *,
    offset_min: float,
    offset_max: float,
    target_offset: float,
    gain_limit_abs_db: float,
    smoothing_win: int,
) -> Dict[str, Any]:
    """
    Construye automation curve en dB por ventana:
      - Si offset dentro del rango => gain=0
      - Si fuera => gain = target_offset - offset (clamp ±gain_limit_abs_db)
    """
    n = min(len(offsets_db), len(window_starts_sec))
    if n <= 0:
        return {
            "window_centers_sec": [],
            "gain_db": [],
            "gain_db_smoothed": [],
        }

    offsets = np.array(offsets_db[:n], dtype=np.float32)
    starts = np.array(window_starts_sec[:n], dtype=np.float32)

    # Centros de ventana (más estable para interpolación)
    centers = starts + float(window_sec) * 0.5

    gain = np.zeros(n, dtype=np.float32)
    for i in range(n):
        off = float(offsets[i])
        if off > offset_max:
            g = float(target_offset - off)
        elif off < offset_min:
            g = float(target_offset - off)
        else:
            g = 0.0
        g = float(np.clip(g, -float(gain_limit_abs_db), float(gain_limit_abs_db)))
        gain[i] = float(g)

    gain_sm = _moving_average(gain, int(smoothing_win))

    return {
        "window_centers_sec": [float(x) for x in centers.tolist()],
        "gain_db": [float(x) for x in gain.tolist()],
        "gain_db_smoothed": [float(x) for x in gain_sm.tolist()],
    }


def _apply_gain_envelope_to_audio(
    y: np.ndarray,
    sr: int,
    centers_sec: List[float],
    gain_db: List[float],
) -> np.ndarray:
    """
    Interpola gain(dB) a nivel de sample usando np.interp y aplica en linear.
    """
    x = np.asarray(y, dtype=np.float32)
    if x.size == 0 or sr <= 0 or not centers_sec or not gain_db:
        return x

    t = (np.arange(x.size, dtype=np.float32) / float(sr)).astype(np.float32)
    xp = np.array(centers_sec, dtype=np.float32)
    fp = np.array(gain_db, dtype=np.float32)

    # Asegura monotonicidad por robustez
    order = np.argsort(xp)
    xp = xp[order]
    fp = fp[order]

    # Interpola (extrapola manteniendo extremos)
    g_db = np.interp(t, xp, fp, left=float(fp[0]), right=float(fp[-1])).astype(np.float32)

    gain_lin = (10.0 ** (g_db / 20.0)).astype(np.float32)
    return (x * gain_lin).astype(np.float32)


def _cap_positive_gains_by_true_peak(
    gain_db: np.ndarray,
    *,
    lead_pre_tp_max_dbtp: Optional[float],
    lead_tp_target_max_dbtp: float,
) -> np.ndarray:
    """
    Si hay boosts positivos, limita su magnitud según headroom real del stem:
      allowed_boost_db = tp_target - tp_pre_max
    Si allowed_boost < max_positive_gain, escalamos SOLO la parte positiva.

    Nota: escalado en dB (factor 0..1). Negativos se mantienen.
    """
    g = np.asarray(gain_db, dtype=np.float32)
    if g.size == 0:
        return g

    if lead_pre_tp_max_dbtp is None or not np.isfinite(float(lead_pre_tp_max_dbtp)):
        return g

    max_pos = float(np.max(g[g > 0.0])) if np.any(g > 0.0) else 0.0
    if max_pos <= 1e-9:
        return g

    allowed = float(lead_tp_target_max_dbtp) - float(lead_pre_tp_max_dbtp)

    if allowed <= 0.0:
        # No se permite boost
        out = g.copy()
        out[out > 0.0] = 0.0
        return out

    if allowed >= max_pos:
        return g

    factor = float(np.clip(allowed / max_pos, 0.0, 1.0))
    out = g.copy()
    out[out > 0.0] = out[out > 0.0] * factor
    return out.astype(np.float32)


def _save_stage_metrics(
    temp_dir: Path,
    contract_id: str,
    data: Dict[str, Any],
) -> Path:
    metrics_path = temp_dir / "leadvox_metrics_S3_LEADVOX_AUDIBILITY.json"
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    LOG.info("[S3_LEADVOX_AUDIBILITY] Métricas guardadas en: %s", metrics_path)
    return metrics_path


def _save_gaincurve_debug(
    temp_dir: Path,
    contract_id: str,
    curve: Dict[str, Any],
) -> Path:
    p = temp_dir / f"leadvox_gaincurve_{contract_id}.json"
    with p.open("w", encoding="utf-8") as f:
        json.dump(curve, f, indent=2, ensure_ascii=False)
    return p


def main() -> None:
    """
    Stage S3_LEADVOX_AUDIBILITY (nuevo comportamiento):
      - Lee analysis_{cid}.json
      - Decide con gates por p95(offset) y max(offset) (series global lead_sum vs bed)
      - Construye automation curve (por ventana) limitada ±2 dB
      - Aplica envelope a stems lead vocal (escritura FLOAT)
      - Cap de boosts por true-peak objetivo
      - No rompe pipeline: si no hay datos => no-op con métricas
    """
    if len(sys.argv) < 2:
        LOG.info("Uso: python S3_LEADVOX_AUDIBILITY.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]
    analysis = load_analysis(contract_id)

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}
    session: Dict[str, Any] = analysis.get("session", {}) or {}
    stems: List[Dict[str, Any]] = analysis.get("stems", []) or []

    temp_dir = get_temp_dir(contract_id, create=False)

    # Targets de offset (lead - bed)
    offset_min = float(metrics.get("short_term_lufs_offset_vs_mixbus_min_db", -3.0))
    offset_max = float(metrics.get("short_term_lufs_offset_vs_mixbus_max_db", 3.0))

    # Política nueva: gate con p95 y max (no mean)
    margin_db = float(metrics.get("lead_audibility_gate_margin_db", 0.25))

    # Límite de automation ±2 dB (configurable)
    gain_limit_abs_db = float(limits.get("lead_gain_automation_limit_abs_db", 2.0))

    # Ventanas (deben coincidir con análisis)
    window_sec = float(session.get("short_term_window_sec", metrics.get("short_term_window_sec", 3.0)))
    hop_sec = float(session.get("short_term_hop_sec", metrics.get("short_term_hop_sec", 1.0)))

    smoothing_win = int(metrics.get("lead_gain_curve_smoothing_windows", 3))
    if smoothing_win < 1:
        smoothing_win = 1

    # Target offset (si no está, conservador)
    target_offset = metrics.get("target_lead_offset_db")
    if target_offset is None:
        target_offset = offset_min + 0.66 * (offset_max - offset_min)
    try:
        target_offset = float(target_offset)
    except Exception:
        target_offset = 0.5 * (offset_min + offset_max)

    # Series global (preferida) para decisión y curve
    offsets_db: List[float] = list(session.get("lead_sum_short_term_offsets_db", []) or [])
    starts_sec: List[float] = list(session.get("lead_sum_window_starts_sec", []) or [])

    global_p95 = session.get("global_short_term_offset_p95_db")
    global_max = session.get("global_short_term_offset_max_db")
    global_mean = session.get("global_short_term_offset_mean_db")
    global_median = session.get("global_short_term_offset_median_db")

    # Fallback: si no hay series (análisis viejo), degradar a mean global (antiguo)
    using_fallback = False
    if (not offsets_db) or (not starts_sec) or (len(offsets_db) != len(starts_sec)):
        using_fallback = True
        LOG.warning("[S3_LEADVOX_AUDIBILITY] No hay series global (analysis viejo). Fallback a comportamiento no-op/mean.")
        offsets_db = []
        starts_sec = []

    # Filtrar stems lead
    lead_stems: List[Dict[str, Any]] = [s for s in stems if s.get("is_lead_vocal", False)]
    if not lead_stems:
        LOG.info("[S3_LEADVOX_AUDIBILITY] Sin stems lead; no-op.")
        _save_stage_metrics(
            temp_dir=temp_dir,
            contract_id=contract_id,
            data={
                "contract_id": contract_id,
                "decision": {"status": "NOOP", "reason": "no_lead_stems"},
                "targets": {"offset_min_db": offset_min, "offset_max_db": offset_max, "target_offset_db": target_offset},
                "series": {"available": bool(not using_fallback), "windows": 0},
            },
        )
        return

    # Si fallback y sin mean válido => no-op
    if using_fallback:
        if global_mean is None:
            LOG.info("[S3_LEADVOX_AUDIBILITY] Sin datos suficientes (fallback). no-op.")
            _save_stage_metrics(
                temp_dir=temp_dir,
                contract_id=contract_id,
                data={
                    "contract_id": contract_id,
                    "decision": {"status": "NOOP", "reason": "missing_series_and_mean"},
                    "targets": {"offset_min_db": offset_min, "offset_max_db": offset_max, "target_offset_db": target_offset},
                    "globals": {"mean_db": global_mean, "median_db": global_median, "p95_db": global_p95, "max_db": global_max},
                    "series": {"available": False, "windows": 0},
                },
            )
            return
        # Mantener pipeline estable: no aplicamos global gain (tu petición es cambiar a curve).
        LOG.info("[S3_LEADVOX_AUDIBILITY] Fallback activo: no se aplica corrección (evitar global gain).")
        _save_stage_metrics(
            temp_dir=temp_dir,
            contract_id=contract_id,
            data={
                "contract_id": contract_id,
                "decision": {"status": "NOOP", "reason": "fallback_no_curve"},
                "targets": {"offset_min_db": offset_min, "offset_max_db": offset_max, "target_offset_db": target_offset},
                "globals": {"mean_db": global_mean, "median_db": global_median, "p95_db": global_p95, "max_db": global_max},
                "series": {"available": False, "windows": 0},
            },
        )
        return

    # Recalcular p95 y max desde series por robustez (no confiar solo en session)
    arr = np.array(offsets_db, dtype=np.float32)
    p95 = float(np.percentile(arr, 95.0)) if arr.size else None
    mx = float(np.max(arr)) if arr.size else None
    mn = float(np.min(arr)) if arr.size else None
    med = float(np.median(arr)) if arr.size else None
    mean = float(np.mean(arr)) if arr.size else None

    # Gates por p95 y max
    need_boost = (p95 is not None) and (p95 < (offset_min - margin_db))
    need_cut_peaks = (mx is not None) and (mx > (offset_max + margin_db))

    if not need_boost and not need_cut_peaks:
        LOG.info(
            "[S3_LEADVOX_AUDIBILITY] Gate OK (no-op): p95=%s, max=%s dentro de [%+.2f..%+.2f]±%.2f",
            None if p95 is None else f"{p95:+.2f}",
            None if mx is None else f"{mx:+.2f}",
            offset_min, offset_max, margin_db,
        )
        _save_stage_metrics(
            temp_dir=temp_dir,
            contract_id=contract_id,
            data={
                "contract_id": contract_id,
                "decision": {"status": "NOOP", "reason": "gate_ok"},
                "targets": {"offset_min_db": offset_min, "offset_max_db": offset_max, "target_offset_db": target_offset},
                "globals": {"mean_db": mean, "median_db": med, "p95_db": p95, "max_db": mx, "min_db": mn},
                "series": {"available": True, "windows": int(arr.size), "window_sec": window_sec, "hop_sec": hop_sec},
            },
        )
        return

    # Construir gain curve (ventanas)
    curve = _build_gain_curve_db(
        offsets_db=offsets_db,
        window_starts_sec=starts_sec,
        window_sec=window_sec,
        offset_min=offset_min,
        offset_max=offset_max,
        target_offset=target_offset,
        gain_limit_abs_db=gain_limit_abs_db,
        smoothing_win=smoothing_win,
    )

    centers_sec = curve["window_centers_sec"]
    gain_db_smoothed = curve["gain_db_smoothed"]

    # Aplicar a cada stem lead, con cap por true-peak para boosts
    lead_tp_target = float(limits.get("lead_true_peak_target_max_dbtp", -3.0))

    processed = 0
    per_stem_tp: Dict[str, Any] = {}

    for stem in lead_stems:
        fname = stem.get("file_name")
        if not fname:
            continue
        p = temp_dir / fname
        if not p.exists():
            continue

        y, sr = sf.read(p, always_2d=False)
        x = np.asarray(y, dtype=np.float32)
        if x.size == 0:
            continue

        # Para TP, medimos sobre mono o multicanal? (TP en canal más alto)
        if x.ndim == 1:
            tp_pre = _measure_true_peak_dbfs(x, int(sr))
        else:
            # max TP entre canales
            tps = [_measure_true_peak_dbfs(x[:, ch], int(sr)) for ch in range(x.shape[1])]
            tp_pre = float(np.max(np.array(tps, dtype=np.float32))) if tps else float("-inf")

        # Cap de boosts positivos según headroom real
        g = np.array(gain_db_smoothed, dtype=np.float32)
        g_capped = _cap_positive_gains_by_true_peak(
            g,
            lead_pre_tp_max_dbtp=tp_pre if np.isfinite(tp_pre) else None,
            lead_tp_target_max_dbtp=lead_tp_target,
        )

        # Aplicar envelope por canal
        if x.ndim == 1:
            y_out = _apply_gain_envelope_to_audio(x, int(sr), centers_sec, g_capped.tolist())
        else:
            chans = []
            for ch in range(x.shape[1]):
                chans.append(_apply_gain_envelope_to_audio(x[:, ch], int(sr), centers_sec, g_capped.tolist()))
            y_out = np.stack(chans, axis=1).astype(np.float32)

        # Escritura segura
        sf.write(p, y_out.astype(np.float32), int(sr), subtype="FLOAT")
        processed += 1

        # Predicción simple TP post: tp_pre + max_pos_gain (capped)
        max_pos = float(np.max(g_capped[g_capped > 0.0])) if np.any(g_capped > 0.0) else 0.0
        per_stem_tp[fname] = {
            "tp_pre_max_dbtp": float(tp_pre) if np.isfinite(tp_pre) else None,
            "tp_pred_post_max_dbtp": float(tp_pre + max_pos) if np.isfinite(tp_pre) else None,
            "max_positive_gain_db_used": float(max_pos),
        }

    curve_path = _save_gaincurve_debug(temp_dir, contract_id, curve)

    LOG.info(
        "[S3_LEADVOX_AUDIBILITY] Applied automation curve (limit=±%.2f dB, smooth=%d) to %d lead stems. Curve: %s",
        gain_limit_abs_db, smoothing_win, processed, curve_path
    )

    _save_stage_metrics(
        temp_dir=temp_dir,
        contract_id=contract_id,
        data={
            "contract_id": contract_id,
            "decision": {
                "status": "APPLIED_AUTOMATION",
                "need_boost": bool(need_boost),
                "need_cut_peaks": bool(need_cut_peaks),
                "gate_policy": "p95_and_max",
                "margin_db": float(margin_db),
            },
            "targets": {
                "offset_min_db": float(offset_min),
                "offset_max_db": float(offset_max),
                "target_offset_db": float(target_offset),
                "gain_limit_abs_db": float(gain_limit_abs_db),
                "smoothing_windows": int(smoothing_win),
            },
            "globals": {
                "mean_db": mean,
                "median_db": med,
                "p95_db": p95,
                "max_db": mx,
                "min_db": mn,
                "windows": int(arr.size),
                "window_sec": float(window_sec),
                "hop_sec": float(hop_sec),
            },
            "true_peak": {
                "lead_true_peak_target_max_dbtp": float(lead_tp_target),
                "per_stem": per_stem_tp,
            },
            "outputs": {
                "gaincurve_json": str(curve_path),
            },
        },
    )


if __name__ == "__main__":
    main()
