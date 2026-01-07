# C:\mix-master\backend\src\stages\S1_STEM_WORKING_LOUDNESS.py
from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import os
from collections.abc import Mapping

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from utils.analysis_utils import get_temp_dir  # noqa: E402
from utils.profiles_utils import get_instrument_profile  # noqa: E402

try:
    from utils.loudness_utils import (  # type: ignore  # noqa: E402
        measure_integrated_lufs,
        measure_true_peak_dbtp,
        measure_sample_peak_dbfs,
    )
except Exception:  # pragma: no cover
    measure_integrated_lufs = None  # type: ignore
    measure_true_peak_dbtp = None  # type: ignore
    measure_sample_peak_dbfs = None  # type: ignore


def _coerce_contract_id(obj: Any) -> Optional[str]:
    """
    Resuelve contract_id de forma robusta para soportar llamadas del pipeline tipo:
      - process("CONTRACT_ID")
      - process(ctx) donde ctx es PipelineContext (usa ctx.stage_id)
      - process({"contract_id": "..."}) o {"stage_id": "..."}
      - ejecución CLI: sys.argv[1]
    """
    if obj is None:
        return None

    # Caso típico: string directo
    if isinstance(obj, str):
        s = obj.strip()
        return s if s else None

    # Algunos pipelines podrían pasar Path con el nombre del contrato
    if isinstance(obj, Path):
        s = obj.name.strip()
        return s if s else None

    # Mapping/dict
    if isinstance(obj, Mapping):
        for k in ("contract_id", "contractId", "stage_id", "stageId", "id"):
            if k in obj and obj[k] is not None:
                v = obj[k]
                if isinstance(v, str):
                    s = v.strip()
                    return s if s else None
                return str(v)

    # Duck-typing sobre objetos tipo PipelineContext
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
    # 1) Si viene por args (pipeline), intenta sacar contract_id de cualquiera de los args
    if args:
        for a in args:
            cid = _coerce_contract_id(a)
            if cid:
                return cid

    # 2) Si viene por CLI
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


def _dbfs_from_peak(peak_lin: float) -> float:
    if peak_lin <= 0.0:
        return float("-inf")
    return float(20.0 * np.log10(float(peak_lin)))


def _mixbus_peak_stream_with_gains(
    stem_paths: List[Path],
    gains_db_by_name: Dict[str, float],
    block_size: int = 65536,
) -> float:
    """
    Peak sample-peak del sumatorio aplicando gains virtualmente (sin escribir).
    """
    if not stem_paths:
        return float("-inf")

    files: List[sf.SoundFile] = []
    try:
        for p in stem_paths:
            files.append(sf.SoundFile(str(p), mode="r"))

        ch_ref = int(files[0].channels)
        peak_lin = 0.0
        done = [False] * len(files)

        while not all(done):
            mix_block = None

            for i, f in enumerate(files):
                if done[i]:
                    continue

                x = f.read(block_size, dtype="float32", always_2d=True)
                if x.size == 0:
                    done[i] = True
                    continue

                # Alinear canales a ch_ref
                if x.shape[1] != ch_ref:
                    if x.shape[1] == 1 and ch_ref == 2:
                        x = np.repeat(x, 2, axis=1)
                    elif x.shape[1] == 2 and ch_ref == 1:
                        x = np.mean(x, axis=1, keepdims=True)
                    else:
                        x = np.mean(x, axis=1, keepdims=True)
                        if ch_ref == 2:
                            x = np.repeat(x, 2, axis=1)

                g_db = float(gains_db_by_name.get(Path(getattr(f, "name", "")).name, 0.0))
                g_lin = float(10.0 ** (g_db / 20.0))
                x = (x * g_lin).astype(np.float32, copy=False)

                if mix_block is None:
                    mix_block = x
                else:
                    n = min(mix_block.shape[0], x.shape[0])
                    mix_block[:n, :] += x[:n, :]

            if mix_block is None:
                break

            blk_peak = float(np.max(np.abs(mix_block))) if mix_block.size else 0.0
            if blk_peak > peak_lin:
                peak_lin = blk_peak

        return _dbfs_from_peak(peak_lin)

    finally:
        for f in files:
            try:
                f.close()
            except Exception:
                pass


def _is_transient_stem(crest_db: float, threshold_db: float) -> bool:
    # crest_db = peak - lufs. Kick/bongo suele tener crest alto.
    if not np.isfinite(crest_db):
        return True
    return float(crest_db) >= float(threshold_db)


def _compute_stem_ceiling_gain_db(
    stem: Dict[str, Any],
    peak_target_dbfs: float,
    crest_threshold_db: float,
    max_cut_db_per_stem: float,
) -> Tuple[float, Dict[str, Any]]:
    """
    Devuelve el gain extra (<=0) por stem, además de un dict con razones.
    - Siempre aplica ceiling de peak.
    - LUFS solo si NO es transitorio (crest bajo).
    - No boostea (S1 no debe re-balancear hacia arriba).
    """
    fname = stem.get("file_name", "<unnamed>")
    prof_id = str(stem.get("instrument_profile_resolved") or stem.get("instrument_profile_requested") or "Other")

    lufs = float(stem.get("integrated_lufs", float("-inf")))
    true_peak = float(stem.get("true_peak_dbtp", stem.get("true_peak_dbfs", float("-inf"))))
    sample_peak = float(stem.get("sample_peak_dbfs", float("-inf")))
    crest = float(stem.get("crest_db", float("inf")))

    # Peak ceiling
    gain_peak = 0.0
    peak_used = true_peak if true_peak != float("-inf") else sample_peak
    if peak_used != float("-inf") and peak_used > peak_target_dbfs:
        gain_peak = float(peak_target_dbfs - peak_used)  # negativo

    # LUFS ceiling (solo si no es transitorio)
    gain_lufs = 0.0
    lufs_applied = False

    transient = _is_transient_stem(crest, crest_threshold_db)

    if not transient and lufs != float("-inf"):
        try:
            prof = get_instrument_profile(prof_id)
            lufs_min = float(prof.get("target_lufs_min", float("-inf")))
            lufs_max = float(prof.get("target_lufs_max", float("inf")))
        except Exception:
            lufs_min, lufs_max = float("-inf"), float("inf")

        if np.isfinite(lufs_max) and lufs > lufs_max:
            gain_lufs = float(lufs_max - lufs)  # negativo
            lufs_applied = True

    gain = min(0.0, float(gain_peak), float(gain_lufs))

    if gain < -abs(max_cut_db_per_stem):
        gain = -abs(max_cut_db_per_stem)

    reasons = {
        "file": fname,
        "profile": prof_id,
        "lufs": lufs,
        "true_peak_dbtp": true_peak,
        "sample_peak_dbfs": sample_peak,
        "crest": crest,
        "transient": transient,
        "gain_peak_db": float(gain_peak),
        "gain_lufs_db": float(gain_lufs),
        "lufs_ceiling_applied": bool(lufs_applied),
        "gain_extra_db": float(gain),
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
    Stage S1_STEM_WORKING_LOUDNESS (robusto):
      - Evita crash cuando stage.py llama process(context, stage_id).
      - Guarda métricas en working_loudness_metrics_S1_STEM_WORKING_LOUDNESS.json.
    """
    contract_id = _resolve_contract_id(args)
    if not contract_id:
        logger.logger.info(
            "[S1_STEM_WORKING_LOUDNESS] ERROR: No se pudo resolver contract_id. "
            "Uso CLI: python S1_STEM_WORKING_LOUDNESS.py <CONTRACT_ID> "
            "o desde pipeline: process(context, stage_id)"
        )
        return False

    temp_dir = get_temp_dir(contract_id, create=False)

    analysis = load_analysis(contract_id)
    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}
    session: Dict[str, Any] = analysis.get("session", {}) or {}
    stems: List[Dict[str, Any]] = analysis.get("stems", []) or []

    mixbus_target = float(session.get("mixbus_peak_target_max_dbfs", metrics.get("mixbus_peak_target_max_dbfs", -6.0)))
    stem_peak_target = float(
        session.get("true_peak_per_stem_target_max_dbfs", metrics.get("true_peak_per_stem_target_max_dbfs", -6.0))
    )

    max_global_step_db = float(limits.get("max_global_gain_change_db_per_pass", limits.get("max_gain_change_db_per_pass", 6.0)))
    max_cut_per_stem_db = float(limits.get("max_cut_db_per_stem_per_pass", limits.get("max_gain_change_db_per_pass", 6.0)))
    crest_transient_threshold_db = float(metrics.get("crest_transient_threshold_db", 14.0))
    min_step_db = float(metrics.get("min_gain_step_db", 0.1))

    mixbus_peak = float(session.get("mixbus_peak_dbfs_measured", float("-inf")))

    global_gain_db = 0.0
    if mixbus_peak != float("-inf") and mixbus_peak > mixbus_target:
        needed = float(mixbus_target - mixbus_peak)
        if needed < -abs(max_global_step_db):
            needed = -abs(max_global_step_db)
        global_gain_db = float(needed)

    if abs(global_gain_db) < min_step_db:
        global_gain_db = 0.0

    gain_by_file: Dict[str, float] = {}
    debug_rows: List[Dict[str, Any]] = []

    for s in stems:
        fname = s.get("file_name")
        if not fname:
            continue
        if str(fname).lower() == "full_song.wav":
            continue

        extra_gain_db, reasons = _compute_stem_ceiling_gain_db(
            stem=s,
            peak_target_dbfs=stem_peak_target,
            crest_threshold_db=crest_transient_threshold_db,
            max_cut_db_per_stem=max_cut_per_stem_db,
        )

        total_gain = float(global_gain_db + extra_gain_db)
        if abs(total_gain) < min_step_db:
            total_gain = 0.0

        gain_by_file[str(fname)] = float(total_gain)
        reasons["gain_global_db"] = float(global_gain_db)
        reasons["gain_total_db"] = float(total_gain)
        debug_rows.append(reasons)

    stem_paths = sorted(p for p in temp_dir.glob("*.wav") if p.name.lower() != "full_song.wav")
    predicted_peak = _mixbus_peak_stream_with_gains(stem_paths, gain_by_file)

    if predicted_peak != float("-inf") and predicted_peak > mixbus_target + 0.1:
        remaining = -abs(max_global_step_db) - global_gain_db
        needed2 = float(mixbus_target - predicted_peak)
        add_global = 0.0

        if remaining < 0.0:
            add_global = max(needed2, remaining)

        if abs(add_global) >= min_step_db:
            for k in list(gain_by_file.keys()):
                gain_by_file[k] = float(gain_by_file[k] + add_global)

            global_gain_db = float(global_gain_db + add_global)
            predicted_peak2 = _mixbus_peak_stream_with_gains(stem_paths, gain_by_file)
            logger.logger.info(
                f"[S1_STEM_WORKING_LOUDNESS] Ajuste global adicional {add_global:+.2f} dB "
                f"(global_total={global_gain_db:+.2f} dB). "
                f"mixbus_peak_pred {predicted_peak:.2f} -> {predicted_peak2:.2f} dBFS (target<={mixbus_target:.2f})."
            )
            predicted_peak = predicted_peak2

    touched = 0
    for p in stem_paths:
        g = float(gain_by_file.get(p.name, 0.0))
        if abs(g) < 1e-6:
            continue
        ok = _apply_gain_inplace(p, g)
        if ok:
            touched += 1

    logger.logger.info(f"[S1_STEM_WORKING_LOUDNESS] Global gain aplicado: {global_gain_db:+.2f} dB.")
    for r in debug_rows:
        logger.logger.info(
            f"[S1_STEM_WORKING_LOUDNESS] {r['file']}: total={r['gain_total_db']:+.2f} dB "
            f"(global={r['gain_global_db']:+.2f}, extra={r['gain_extra_db']:+.2f}) | "
            f"LUFS={r['lufs']:.2f}, TP={r['true_peak_dbtp']:.2f} dBTP, "
            f"sample_peak={r['sample_peak_dbfs']:.2f} dBFS, crest={r['crest']:.2f}, transient={r['transient']} | "
            f"peak_adj={r['gain_peak_db']:+.2f}, lufs_adj={r['gain_lufs_db']:+.2f}"
        )

    metrics_path = temp_dir / "working_loudness_metrics_S1_STEM_WORKING_LOUDNESS.json"
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "contract_id": contract_id,
                "mixbus_target_max_dbfs": mixbus_target,
                "stem_peak_target_max_dbfs": stem_peak_target,
                "global_gain_db": global_gain_db,
                "predicted_mixbus_peak_dbfs": predicted_peak,
                "limits": {
                    "max_global_step_db": max_global_step_db,
                    "max_cut_per_stem_db": max_cut_per_stem_db,
                    "crest_transient_threshold_db": crest_transient_threshold_db,
                    "min_step_db": min_step_db,
                },
                "per_stem": debug_rows,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    logger.logger.info(
        f"[S1_STEM_WORKING_LOUDNESS] Stage completado. stems_modificados={touched}. "
        f"mixbus_peak_pred={predicted_peak:.2f} dBFS (target<={mixbus_target:.2f}). "
        f"Métricas: {metrics_path}"
    )
    return True


def main() -> None:
    ok = process()
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
