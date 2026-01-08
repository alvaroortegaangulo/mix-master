# C:\mix-master\backend\src\stages\S1_STEM_WORKING_LOUDNESS.py
from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import os
from collections.abc import Mapping

import json  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.analysis_utils import get_temp_dir, sf_read_limited  # noqa: E402
from utils.profiles_utils import get_instrument_profile  # noqa: E402

try:
    from utils.loudness_utils import (  # type: ignore  # noqa: E402
        measure_true_peak_dbtp,
    )
except Exception:  # pragma: no cover
    measure_true_peak_dbtp = None  # type: ignore


def _coerce_contract_id(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    if isinstance(obj, str):
        s = obj.strip()
        return s if s else None
    if isinstance(obj, Path):
        s = obj.name.strip()
        return s if s else None
    if isinstance(obj, Mapping):
        for k in ("contract_id", "contractId", "stage_id", "stageId", "id"):
            if k in obj and obj[k] is not None:
                v = obj[k]
                if isinstance(v, str):
                    s = v.strip()
                    return s if s else None
                return str(v)
    for attr in ("contract_id", "contractId", "stage_id", "stageId", "id"):
        if hasattr(obj, attr):
            v = getattr(obj, attr)
            if v is None:
                continue
            if isinstance(v, str):
                s = v.strip()
                return s if s else None
            return str(v)
    return None


def _resolve_contract_id(args: tuple[Any, ...]) -> Optional[str]:
    if args:
        for a in args:
            cid = _coerce_contract_id(a)
            if cid:
                return cid
    if len(sys.argv) >= 2:
        cid = _coerce_contract_id(sys.argv[1])
        if cid:
            return cid
    return None


def load_analysis(contract_id: str) -> Dict[str, Any]:
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"
    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")
    with analysis_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _db_from_peak_lin(peak_lin: float) -> float:
    if peak_lin <= 0.0:
        return float("-inf")
    return float(20.0 * np.log10(float(peak_lin)))


def _align_channels(x: np.ndarray, ch_ref: int) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    if x.ndim == 1:
        x = x[:, None]
    ch = int(x.shape[1])

    if ch == ch_ref:
        return x
    if ch == 1 and ch_ref == 2:
        return np.repeat(x, 2, axis=1)
    if ch == 2 and ch_ref == 1:
        return np.mean(x, axis=1, keepdims=True)

    x = np.mean(x, axis=1, keepdims=True)
    if ch_ref == 2:
        x = np.repeat(x, 2, axis=1)
    return x


def _mixbus_true_peak_sum_with_gains_limited(
    stem_paths: List[Path],
    gains_db_by_name: Dict[str, float],
) -> Tuple[float, str]:
    """
    Predicción de mixbus TRUE PEAK (dBTP) aplicando gains virtualmente (sin escribir).
    Estrategia: carga limitada (sf_read_limited) + suma en memoria + TP.
    Devuelve (value_db, kind) donde kind ∈ {"dBTP","dBFS_sample_peak_fallback"}.
    """
    if not stem_paths:
        return float("-inf"), "dBTP"

    y_sum: Optional[np.ndarray] = None
    sr_ref: Optional[int] = None
    ch_ref: Optional[int] = None

    for p in stem_paths:
        try:
            y, sr = sf_read_limited(p, always_2d=True)
        except Exception as e:
            logger.logger.info(f"[S1_STEM_WORKING_LOUDNESS] WARN: no se pudo leer {p.name}: {e}")
            continue

        x = np.asarray(y, dtype=np.float32)
        if sr_ref is None:
            sr_ref = int(sr)
            ch_ref = int(x.shape[1]) if x.ndim == 2 else 1
        else:
            if int(sr) != int(sr_ref):
                logger.logger.info(
                    f"[S1_STEM_WORKING_LOUDNESS] WARN: sr distinto en {p.name} ({sr} vs {sr_ref}); suma sin resample."
                )

        x = _align_channels(x, int(ch_ref or 2))

        g_db = float(gains_db_by_name.get(p.name, 0.0))
        g_lin = float(10.0 ** (g_db / 20.0))
        x = (x * g_lin).astype(np.float32)

        if y_sum is None:
            y_sum = x
        else:
            max_len = max(int(y_sum.shape[0]), int(x.shape[0]))
            if y_sum.shape[0] < max_len:
                pad = np.zeros((max_len - y_sum.shape[0], y_sum.shape[1]), dtype=np.float32)
                y_sum = np.vstack([y_sum, pad])
            if x.shape[0] < max_len:
                pad = np.zeros((max_len - x.shape[0], x.shape[1]), dtype=np.float32)
                x = np.vstack([x, pad])
            y_sum = (y_sum + x).astype(np.float32)

    if y_sum is None or sr_ref is None:
        return float("-inf"), "dBTP"

    if measure_true_peak_dbtp is not None:
        try:
            tp = float(measure_true_peak_dbtp(y_sum, int(sr_ref)))
            return tp, "dBTP"
        except Exception as e:
            logger.logger.info(f"[S1_STEM_WORKING_LOUDNESS] WARN: TP pred mixbus falló, fallback sample peak: {e}")

    pk = float(np.max(np.abs(y_sum))) if y_sum.size else 0.0
    return _db_from_peak_lin(pk), "dBFS_sample_peak_fallback"


def _is_transient_by_family_budget(
    crest_db: float,
    family: str,
    crest_budget_by_family_db: Dict[str, float],
    default_budget_db: float,
) -> bool:
    if not np.isfinite(crest_db):
        return True
    budget = float(crest_budget_by_family_db.get(family, default_budget_db))
    return float(crest_db) >= budget


def _extract_profile_ranges(profile_id: str) -> Tuple[Optional[str], Optional[Tuple[float, float]]]:
    """
    Devuelve (family, work_lufs_range) si existe.
    work_lufs_range proviene de profiles.json -> work_loudness_lufs_range.
    """
    try:
        prof = get_instrument_profile(profile_id)
        fam = prof.get("family")
        rng = prof.get("work_loudness_lufs_range")
        if isinstance(rng, (list, tuple)) and len(rng) == 2:
            return str(fam) if fam is not None else None, (float(rng[0]), float(rng[1]))
        return str(fam) if fam is not None else None, None
    except Exception:
        return None, None


def _compute_stem_cut_db(
    stem: Dict[str, Any],
    *,
    stem_tp_target_max_dbtp: float,
    max_cut_db_per_stem: float,
    crest_budget_by_family_db: Dict[str, float],
    crest_budget_default_db: float,
) -> Tuple[float, Dict[str, Any]]:
    """
    S1 aplica SOLO recortes (<=0).
    Política:
      - ceiling por True Peak del stem (dBTP) -> siempre
      - ceiling por LUFS (work range) -> SOLO si NO es transitorio según crest budget por familia
    """
    fname = stem.get("file_name", "<unnamed>")
    prof_id = str(stem.get("instrument_profile_resolved") or stem.get("instrument_profile_requested") or "Other")

    lufs = float(stem.get("integrated_lufs", float("-inf")))
    tp = float(stem.get("true_peak_dbtp", stem.get("true_peak_dbfs", float("-inf"))))
    crest = float(stem.get("crest_db", float("inf")))

    family, work_rng = _extract_profile_ranges(prof_id)
    fam = family or str(stem.get("family") or "Other")

    transient = _is_transient_by_family_budget(
        crest_db=crest,
        family=fam,
        crest_budget_by_family_db=crest_budget_by_family_db,
        default_budget_db=crest_budget_default_db,
    )

    # 1) True Peak ceiling
    gain_tp = 0.0
    if tp != float("-inf") and tp > stem_tp_target_max_dbtp:
        gain_tp = float(stem_tp_target_max_dbtp - tp)  # negativo

    # 2) LUFS ceiling (solo no-transient)
    gain_lufs = 0.0
    lufs_ceiling_applied = False
    if (not transient) and (work_rng is not None) and (lufs != float("-inf")):
        _min_lufs, max_lufs = float(work_rng[0]), float(work_rng[1])
        if np.isfinite(max_lufs) and lufs > max_lufs:
            gain_lufs = float(max_lufs - lufs)  # negativo
            lufs_ceiling_applied = True

    gain = min(0.0, float(gain_tp), float(gain_lufs))

    if gain < -abs(max_cut_db_per_stem):
        gain = -abs(max_cut_db_per_stem)

    reasons = {
        "file": fname,
        "profile": prof_id,
        "family": fam,
        "work_lufs_range": work_rng,
        "lufs": lufs,
        "true_peak_dbtp": tp,
        "crest": crest,
        "crest_budget_db": float(crest_budget_by_family_db.get(fam, crest_budget_default_db)),
        "transient": bool(transient),
        "gain_tp_db": float(gain_tp),
        "gain_lufs_db": float(gain_lufs),
        "lufs_ceiling_applied": bool(lufs_ceiling_applied),
        "gain_stem_cut_db": float(gain),
    }
    return float(gain), reasons


def _apply_gain_inplace(path: Path, gain_db: float) -> bool:
    try:
        data, sr = sf.read(path, always_2d=False)
        x = np.asarray(data, dtype=np.float32)
        if x.size == 0:
            return False
        g_lin = float(10.0 ** (float(gain_db) / 20.0))
        y = (x * g_lin).astype(np.float32)
        sf.write(path, y, int(sr), subtype="FLOAT")
        return True
    except Exception as e:
        logger.logger.info(f"[S1_STEM_WORKING_LOUDNESS] Error aplicando gain a {path.name}: {e}")
        return False


def process(*args) -> bool:
    """
    Stage S1_STEM_WORKING_LOUDNESS (mejorado):
      - Pivota a True Peak (dBTP) para control global y por stem.
      - Objetivo mixbus: TP en rango [-8..-6] dBTP, sin boost (solo recorta si > -6).
      - Crest budget por familia para decidir si aplicar ceiling por LUFS en stems.
    """
    contract_id = _resolve_contract_id(args)
    if not contract_id:
        logger.logger.info(
            "[S1_STEM_WORKING_LOUDNESS] ERROR: No se pudo resolver contract_id."
        )
        return False

    temp_dir = get_temp_dir(contract_id, create=False)
    analysis = load_analysis(contract_id)

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}
    session: Dict[str, Any] = analysis.get("session", {}) or {}
    stems: List[Dict[str, Any]] = analysis.get("stems", []) or []

    # Targets (TP)
    mixbus_tp_min = float(session.get("mixbus_true_peak_target_min_dbtp", metrics.get("mixbus_true_peak_target_min_dbtp", -8.0)))
    mixbus_tp_max = float(session.get("mixbus_true_peak_target_max_dbtp", metrics.get("mixbus_true_peak_target_max_dbtp", -6.0)))
    stem_tp_target_max = float(session.get("true_peak_per_stem_target_max_dbtp", metrics.get("true_peak_per_stem_target_max_dbtp", -6.0)))

    # Medición pre de mixbus TP (primaria) y fallback legacy
    mixbus_tp_measured = session.get("mixbus_true_peak_dbtp_measured")
    if mixbus_tp_measured is not None:
        try:
            mixbus_tp_measured = float(mixbus_tp_measured)
        except Exception:
            mixbus_tp_measured = None

    mixbus_peak_legacy_dbfs = session.get("mixbus_peak_dbfs_measured")
    if mixbus_peak_legacy_dbfs is not None:
        try:
            mixbus_peak_legacy_dbfs = float(mixbus_peak_legacy_dbfs)
        except Exception:
            mixbus_peak_legacy_dbfs = None

    # Límites de cambios
    max_global_step_db = float(limits.get("max_global_gain_change_db_per_pass", limits.get("max_gain_change_db_per_pass", 6.0)))
    max_cut_per_stem_db = float(limits.get("max_cut_db_per_stem_per_pass", limits.get("max_gain_change_db_per_pass", 6.0)))
    min_step_db = float(metrics.get("min_gain_step_db", 0.1))

    # Crest budgets por familia (configurable)
    # Si no está en contract/metrics, se usan defaults razonables.
    crest_budget_by_family_db: Dict[str, float] = dict(metrics.get("crest_budget_by_family_db", {}) or {})
    crest_budget_default_db = float(metrics.get("crest_budget_default_db", 14.0))

    # Defaults recomendados si no vienen definidos
    if not crest_budget_by_family_db:
        crest_budget_by_family_db = {
            "Drums": 18.0,
            "Percussion": 18.0,
            "Bass": 14.0,
            "LeadVox": 12.5,
            "BGV": 12.5,
            "Guitars": 14.0,
            "Keys": 14.0,
            "Synths": 14.0,
            "Winds": 14.5,
            "FX": 18.0,
            "Ambience": 16.0,
            "Other": crest_budget_default_db,
        }

    # ------------------------------------------------------------
    # 1) Gain global basado en mixbus TRUE PEAK (dBTP)
    #    - No boost: solo recorta si supera mixbus_tp_max.
    # ------------------------------------------------------------
    global_gain_db = 0.0
    if mixbus_tp_measured is not None and np.isfinite(mixbus_tp_measured):
        if mixbus_tp_measured > mixbus_tp_max:
            needed = float(mixbus_tp_max - mixbus_tp_measured)  # negativo
            if needed < -abs(max_global_step_db):
                needed = -abs(max_global_step_db)
            global_gain_db = float(needed)
    else:
        # Fallback: si no hay TP (analysis viejo/medidor ausente), mantenemos legacy sample peak
        if mixbus_peak_legacy_dbfs is not None and np.isfinite(mixbus_peak_legacy_dbfs):
            legacy_target = float(session.get("mixbus_peak_target_max_dbfs", metrics.get("mixbus_peak_target_max_dbfs", -6.0)))
            if mixbus_peak_legacy_dbfs > legacy_target:
                needed = float(legacy_target - mixbus_peak_legacy_dbfs)
                if needed < -abs(max_global_step_db):
                    needed = -abs(max_global_step_db)
                global_gain_db = float(needed)

    if abs(global_gain_db) < min_step_db:
        global_gain_db = 0.0

    # ------------------------------------------------------------
    # 2) Per-stem cuts (TP + LUFS sólo si no-transient)
    # ------------------------------------------------------------
    gain_by_file: Dict[str, float] = {}
    debug_rows: List[Dict[str, Any]] = []

    for s in stems:
        fname = s.get("file_name")
        if not fname:
            continue
        if str(fname).lower() == "full_song.wav":
            continue

        stem_cut_db, reasons = _compute_stem_cut_db(
            stem=s,
            stem_tp_target_max_dbtp=stem_tp_target_max,
            max_cut_db_per_stem=max_cut_per_stem_db,
            crest_budget_by_family_db=crest_budget_by_family_db,
            crest_budget_default_db=crest_budget_default_db,
        )

        total_gain = float(global_gain_db + stem_cut_db)
        if abs(total_gain) < min_step_db:
            total_gain = 0.0

        gain_by_file[str(fname)] = float(total_gain)
        reasons["gain_global_db"] = float(global_gain_db)
        reasons["gain_total_db"] = float(total_gain)

        # Predicción TP post por stem: TP_post ≈ TP_pre + gain_total_db
        tp_pre = float(s.get("true_peak_dbtp", s.get("true_peak_dbfs", float("-inf"))))
        reasons["tp_pred_post_dbtp"] = (float(tp_pre) + float(total_gain)) if (tp_pre != float("-inf")) else None

        debug_rows.append(reasons)

    stem_paths = sorted(p for p in temp_dir.glob("*.wav") if p.name.lower() != "full_song.wav")

    # Predicción de mixbus TP tras gains (primaria)
    pred_mix_tp, pred_kind = _mixbus_true_peak_sum_with_gains_limited(stem_paths, gain_by_file)

    # Opcional: si aún está por encima del max, intentamos un ajuste global adicional (solo recorte)
    if pred_mix_tp != float("-inf") and np.isfinite(pred_mix_tp) and (pred_mix_tp > mixbus_tp_max + 0.1):
        remaining = -abs(max_global_step_db) - global_gain_db  # negativo o 0
        needed2 = float(mixbus_tp_max - pred_mix_tp)  # negativo
        add_global = 0.0

        if remaining < 0.0:
            add_global = max(needed2, remaining)

        if abs(add_global) >= min_step_db:
            for k in list(gain_by_file.keys()):
                gain_by_file[k] = float(gain_by_file[k] + add_global)

            global_gain_db = float(global_gain_db + add_global)
            pred_mix_tp2, pred_kind2 = _mixbus_true_peak_sum_with_gains_limited(stem_paths, gain_by_file)

            logger.logger.info(
                f"[S1_STEM_WORKING_LOUDNESS] Ajuste global adicional {add_global:+.2f} dB "
                f"(global_total={global_gain_db:+.2f} dB). "
                f"mixbus_pred {pred_mix_tp:.2f} -> {pred_mix_tp2:.2f} ({pred_kind2}) "
                f"(target_max={mixbus_tp_max:.2f} dBTP)."
            )

            pred_mix_tp, pred_kind = pred_mix_tp2, pred_kind2

            # refrescar también en debug_rows
            for r in debug_rows:
                r["gain_global_db"] = float(global_gain_db)
                r["gain_total_db"] = float(gain_by_file.get(r["file"], 0.0))
                tp_pre = r.get("true_peak_dbtp", None)
                if tp_pre is None:
                    # usar campo previo de reasons si está
                    pass

    # ------------------------------------------------------------
    # 3) Aplicar gains in-place (FLOAT)
    # ------------------------------------------------------------
    touched = 0
    for p in stem_paths:
        g = float(gain_by_file.get(p.name, 0.0))
        if abs(g) < 1e-6:
            continue
        ok = _apply_gain_inplace(p, g)
        if ok:
            touched += 1

    logger.logger.info(f"[S1_STEM_WORKING_LOUDNESS] Global gain aplicado (TP): {global_gain_db:+.2f} dB.")

    # Log conciso por stem (manteniendo trazabilidad)
    for r in debug_rows:
        logger.logger.info(
            f"[S1_STEM_WORKING_LOUDNESS] {r['file']}: total={r['gain_total_db']:+.2f} dB "
            f"(global={r['gain_global_db']:+.2f}, stem_cut={r['gain_stem_cut_db']:+.2f}) | "
            f"fam={r['family']} crest={r['crest']:.2f} (budget={r['crest_budget_db']:.2f}) transient={r['transient']} | "
            f"LUFS={r['lufs']:.2f} TP={r['true_peak_dbtp']:.2f} dBTP -> pred={r['tp_pred_post_dbtp']}"
        )

    # ------------------------------------------------------------
    # 4) Guardar métricas (retrocompatibles + nuevas)
    # ------------------------------------------------------------
    metrics_path = temp_dir / "working_loudness_metrics_S1_STEM_WORKING_LOUDNESS.json"
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "contract_id": contract_id,

                # NUEVO: targets TP para headroom real
                "mixbus_true_peak_target_range_dbtp": [float(mixbus_tp_min), float(mixbus_tp_max)],
                "stem_true_peak_target_max_dbtp": float(stem_tp_target_max),

                # Medición pre
                "mixbus_true_peak_dbtp_measured": mixbus_tp_measured,
                "mixbus_sample_peak_dbfs_measured_legacy": mixbus_peak_legacy_dbfs,

                # Decisión
                "global_gain_db": float(global_gain_db),

                # Predicción post
                "predicted_mixbus_true_peak": {
                    "value": float(pred_mix_tp),
                    "kind": str(pred_kind),
                },

                # Crest budgets
                "crest_budget_by_family_db": crest_budget_by_family_db,
                "crest_budget_default_db": float(crest_budget_default_db),

                "limits": {
                    "max_global_step_db": float(max_global_step_db),
                    "max_cut_per_stem_db": float(max_cut_per_stem_db),
                    "min_step_db": float(min_step_db),
                },
                "per_stem": debug_rows,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    logger.logger.info(
        f"[S1_STEM_WORKING_LOUDNESS] Stage completado. stems_modificados={touched}. "
        f"mixbus_pred_TP={pred_mix_tp:.2f} ({pred_kind}) target_max={mixbus_tp_max:.2f} dBTP. "
        f"Métricas: {metrics_path}"
    )
    return True


def main() -> None:
    ok = process()
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
