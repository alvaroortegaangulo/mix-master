# C:\mix-master\backend\src\analysis\S11_REPORT_GENERATION.py

from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any, List
import json
import datetime
import os
import math

# --- hack para importar utils ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from utils.analysis_utils import (  # noqa: E402
    load_contract,
    get_temp_dir,
    sf_read_limited,
    sanitize_json_floats
)
from utils.session_utils import load_session_config  # noqa: E402
from utils.loudness_utils import compute_lufs_and_lra  # noqa: E402
from utils.color_utils import compute_true_peak_dbfs  # noqa: E402


PIPELINE_VERSION = "v1.0.0"
TIMINGS_FILENAME = "pipeline_timings.json"

def _load_contracts_data() -> Dict[str, Any]:
    """
    Load contracts.json from backend/src/struct/contracts.json
    Replicated logic from pipeline.py to avoid complex imports.
    """
    try:
        struct_dir = SRC_DIR / "struct"
        contracts_path = struct_dir / "contracts.json"
        with contracts_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.logger.warning(f"[S11] Failed to load contracts.json: {e}")
        return {}

def _get_ordered_contract_ids(contracts: Dict[str, Any]) -> List[str]:
    ordered: List[str] = []
    for stage_data in contracts.get("stages", {}).values():
        for c in stage_data.get("contracts", []) or []:
            cid = c.get("id")
            if cid and cid != "S11_REPORT_GENERATION": # Exclude itself
                ordered.append(cid)
    return ordered

def _get_stage_description(contracts: Dict[str, Any], contract_id: str) -> str:
    # Try to find description in contracts.json (using stage name or constructing it)
    # We can search for the contract
    for stage_data in contracts.get("stages", {}).values():
        for c in stage_data.get("contracts", []) or []:
            if c.get("id") == contract_id:
                # Use stage group name + contract specific if available?
                # Or just use the group name
                return stage_data.get("name", contract_id)
    return contract_id


def _build_stage_report_entry(contract_id: str, contracts_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Construye una entrada de reporte para un contract_id concreto,
    usando analysis_<contract_id>.json si existe.
    """
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    # Get description from contracts data or fallback
    desc = _get_stage_description(contracts_data, contract_id)

    entry: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": None,
        "name": desc,
        "status": "missing_analysis",
        "key_metrics": {},
    }

    if not analysis_path.exists():
        # Check if it was executed but analysis file is missing?
        # If it's in pipeline_timings, it was executed.
        logger.logger.info(f"[S11] Analysis file not found for {contract_id} at {analysis_path}")
        return entry

    try:
        with analysis_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.logger.warning(f"[S11] Failed to read analysis for {contract_id}: {e}")
        return entry

    entry["stage_id"] = data.get("stage_id")
    entry["status"] = "analyzed"
    # Para mantenerlo genérico: guardamos el bloque "session" tal cual.
    entry["key_metrics"] = data.get("session", {})

    return entry


def _compute_crest_and_histogram(
    y: np.ndarray,
    sr: int,
    floor_db: float = -60.0,
    ceil_db: float = 0.0,
    num_bins: int = 30,
) -> Dict[str, Any]:
    """
    Calcula crest factor aproximado y un histograma de niveles (en dB).

    - Crest factor = TP_dBTP - RMS_dBFS del master (mono).
    - Histograma de niveles basado en RMS por frames.
    """
    arr = np.asarray(y, dtype=np.float32)
    if arr.ndim == 2:
        mono = np.mean(arr, axis=1)
    else:
        mono = arr

    # Crest factor
    if mono.size == 0:
        crest_db = 0.0
    else:
        rms = float(np.sqrt(np.mean(mono**2)))
        if rms <= 0.0:
            rms_db = float("-inf")
            crest_db = 0.0
        else:
            rms_db = 20.0 * np.log10(rms)
            # true peak aproximado
            tp_db = compute_true_peak_dbfs(mono, oversample_factor=4)
            crest_db = tp_db - rms_db

    # Histograma: RMS por frames
    frame_len_s = 0.4
    hop_s = 0.2
    frame_len = int(frame_len_s * sr)
    hop_len = int(hop_s * sr)
    levels_db: List[float] = []

    for start in range(0, len(mono), hop_len):
        end = start + frame_len
        if end > len(mono):
            frame = mono[start:len(mono)]
        else:
            frame = mono[start:end]
        if frame.size == 0:
            continue
        rms = float(np.sqrt(np.mean(frame**2)))
        if rms <= 0.0:
            level_db = float("-inf")
        else:
            level_db = 20.0 * np.log10(rms)
        if np.isfinite(level_db):
            levels_db.append(level_db)

    if levels_db:
        levels_arr = np.asarray(levels_db, dtype=np.float32)
        bins = np.linspace(floor_db, ceil_db, num_bins + 1)
        counts, edges = np.histogram(levels_arr, bins=bins)
        histogram = {
            "bin_edges_db": edges.tolist(),
            "counts": counts.tolist(),
        }
    else:
        histogram = {
            "bin_edges_db": [],
            "counts": [],
        }

    return {
        "crest_factor_db": crest_db,
        "level_histogram_db": histogram,
    }


def _load_pipeline_timings(contract_id: str) -> Dict[str, Any]:
    """
    Lee pipeline_timings.json desde la raiz temp del job (si existe).
    """
    temp_dir = get_temp_dir(contract_id, create=False)
    job_root = temp_dir.parent
    timings_path = job_root / TIMINGS_FILENAME

    logger.logger.info(f"[S11] Checking timings at: {timings_path}")

    if not timings_path.exists():
        logger.logger.info("[S11] Timings file not found.")
        return {"stages": [], "total_duration_sec": None}

    try:
        with timings_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        stages = data.get("stages", [])
        total = data.get("total_duration_sec")
        return {
            "stages": stages if isinstance(stages, list) else [],
            "total_duration_sec": total if isinstance(total, (int, float)) else None,
            "generated_at_utc": data.get("generated_at_utc"),
        }
    except Exception as exc:
        logger.logger.info(f"[S11_REPORT_GENERATION] Aviso: no se pudo leer timings: {exc}")
        return {"stages": [], "total_duration_sec": None}


def _crest_hist_worker(path: Path) -> Dict[str, Any]:
    """
    Devuelve métricas y posible mensaje de error.
    """
    try:
        y, sr = sf_read_limited(path, always_2d=False)
    except Exception as e:
        return {
            "crest_factor_db": None,
            "level_histogram_db": {"bin_edges_db": [], "counts": []},
            "error": f"[S11_REPORT_GENERATION] Aviso: no se pudo leer {path}: {e}",
        }

    metrics = _compute_crest_and_histogram(y, sr)
    metrics["error"] = None
    return metrics


def main() -> None:
    """
    Análisis para S11_REPORT_GENERATION.

    Genera un objeto 'report' con:
      - pipeline_version, fecha, estilo.
      - resumen por stage con métricas clave (lo que haya en 'session' de cada análisis).
      - métricas finales (LUFS, LRA, TP, correlación, crest, histograma de niveles).
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S11_REPORT_GENERATION.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S11_REPORT_GENERATION"
    logger.logger.info(f"[S11] Starting report generation for {contract_id}")

    # 1) Cargar contrato
    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    # 2) temp/<contract_id> y session_config (para estilo)
    temp_dir = get_temp_dir(contract_id, create=True)
    cfg = load_session_config(contract_id)
    style_preset = cfg["style_preset"]

    # Load contracts data for descriptions and ordering
    contracts_data = _load_contracts_data()
    if not contracts_data:
        logger.logger.error("[S11] Failed to load contracts data.")

    # Load timings to see what actually ran
    pipeline_timings = _load_pipeline_timings(contract_id)
    executed_contracts = set()
    if pipeline_timings.get("stages"):
        for s in pipeline_timings["stages"]:
            if s.get("contract_id"):
                executed_contracts.add(s["contract_id"])

    logger.logger.info(f"[S11] Executed contracts according to timings: {list(executed_contracts)}")

    # Get master list
    all_contracts = _get_ordered_contract_ids(contracts_data)
    logger.logger.info(f"[S11] Total available contracts from definition: {len(all_contracts)}")

    # Filter: Only include contracts that EITHER are in timings OR have analysis file existing.
    # This prevents showing "missing_analysis" for skipped stages.

    stages_to_report = []
    for cid in all_contracts:
        # Check existence
        c_temp = get_temp_dir(cid, create=False)
        c_ana = c_temp / f"analysis_{cid}.json"

        is_executed = cid in executed_contracts
        is_analyzed = c_ana.exists()

        if is_executed or is_analyzed:
            stages_to_report.append(cid)
        else:
            # Verbose logging only if we suspect issues
            # logger.logger.info(f"[S11] Skipping {cid} (not executed, no analysis)")
            pass

    logger.logger.info(f"[S11] Stages selected for report: {stages_to_report}")

    # 3) Construir report.stages
    stages_report: List[Dict[str, Any]] = [
        _build_stage_report_entry(cid, contracts_data) for cid in stages_to_report
    ]

    # 4) Métricas finales desde QC de S10 + audio final para crest / hist
    qc_contract_id = "S10_MASTER_FINAL_LIMITS"
    qc_dir = get_temp_dir(qc_contract_id, create=False)
    qc_path = qc_dir / "qc_metrics_S10_MASTER_FINAL_LIMITS.json"

    final_tp = float("nan")
    final_lufs = float("nan")
    final_lra = float("nan")
    final_corr = float("nan")
    final_diff_lr = float("nan")

    def _first_finite(*vals: float) -> float:
        for v in vals:
            try:
                f = float(v)
            except (TypeError, ValueError):
                continue
            if math.isfinite(f):
                return f
        return float("nan")

    # 4a) Intentar QC (S10 stage)
    if qc_path.exists():
        try:
            with qc_path.open("r", encoding="utf-8") as f:
                qc = json.load(f)
            post = qc.get("post", {}) or {}
            final_tp = float(post.get("true_peak_dbtp", float("nan")))
            final_lufs = float(post.get("lufs_integrated", float("nan")))
            final_lra = float(post.get("lra", float("nan")))
            final_corr = float(post.get("correlation", float("nan")))
            final_diff_lr = float(post.get("channel_loudness_diff_db", float("nan")))
        except Exception as e:
            logger.logger.info(f"[S11_REPORT_GENERATION] Aviso: no se pudo leer {qc_path}: {e}")
    else:
        logger.logger.info(f"[S11] QC Metrics file not found at {qc_path}")

    # 4b) Fallback: analysis de S10 si el QC falta o trae NaN
    s10_analysis_path = qc_dir / "analysis_S10_MASTER_FINAL_LIMITS.json"
    if s10_analysis_path.exists():
        try:
            with s10_analysis_path.open("r", encoding="utf-8") as f:
                s10_data = json.load(f)
            s10_session = s10_data.get("session", {}) or {}
            s10_tp = s10_session.get("true_peak_dbtp")
            s10_lufs = s10_session.get("lufs_integrated")
            s10_lra = s10_session.get("lra")
            s10_corr = s10_session.get("correlation")
            s10_diff = s10_session.get("channel_loudness_diff_db")

            final_tp = _first_finite(final_tp, s10_tp)
            final_lufs = _first_finite(final_lufs, s10_lufs)
            final_lra = _first_finite(final_lra, s10_lra)
            final_corr = _first_finite(final_corr, s10_corr)
            final_diff_lr = _first_finite(final_diff_lr, s10_diff)
        except Exception as e:
            logger.logger.info(f"[S11] Fallback a analysis_S10_MASTER_FINAL_LIMITS falló: {e}")

    # 5) Leer audio final (master) para crest & histograma
    #    Preferimos el full_song de S11; si no existe o falla, usamos el de S10.
    audio_paths = [
        temp_dir / "full_song.wav",
        qc_dir / "full_song.wav",
    ]

    crest_and_hist = {
        "crest_factor_db": None,
        "level_histogram_db": {"bin_edges_db": [], "counts": []},
    }

    found_audio = False
    for p in audio_paths:
        if not p.exists():
            continue

        result = _crest_hist_worker(p)

        if result.get("error"):
            # Logeamos el error y pasamos al siguiente path
            logger.logger.info(result["error"])
            continue

        crest_and_hist = {
            "crest_factor_db": result["crest_factor_db"],
            "level_histogram_db": result["level_histogram_db"],
        }
        found_audio = True
        break

    if not found_audio:
        logger.logger.warning("[S11] Could not find any valid full_song.wav to analyze for crest factor.")

    final_metrics: Dict[str, Any] = {
        "true_peak_dbtp": final_tp,
        "lufs_integrated": final_lufs,
        "lra": final_lra,
        "correlation": final_corr,
        "channel_loudness_diff_db": final_diff_lr,
        "crest_factor_db": crest_and_hist.get("crest_factor_db"),
        "level_histogram_db": crest_and_hist.get("level_histogram_db"),
    }

    # Reload pipeline timings in case they changed (unlikely in this flow)
    pipeline_timings = _load_pipeline_timings(contract_id)

    report: Dict[str, Any] = {
        "pipeline_version": PIPELINE_VERSION,
        "generated_at_utc": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "style_preset": style_preset,
        "stages": stages_report,
        "final_metrics": final_metrics,
        "pipeline_durations": pipeline_timings,
    }

    # 6) Envolver todo en la estructura de análisis estándar
    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "report": report
        },
    }

    # SANITIZE floats before dumping
    session_state = sanitize_json_floats(session_state)

    output_path = temp_dir / f"analysis_{contract_id}.json"
    try:
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(session_state, f, indent=2, ensure_ascii=False)
        logger.logger.info(f"[S11] Saved analysis report to {output_path}")
    except Exception as e:
        logger.logger.error(f"[S11] Failed to save analysis report: {e}")

    # logger.logger.debug(f"[S11_REPORT_GENERATION] Analysis complete. JSON: {output_path}")


if __name__ == "__main__":
    main()
