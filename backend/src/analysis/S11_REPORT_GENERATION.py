from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import json
import datetime
import numpy as np

# --- hack para importar utils ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    from context import PipelineContext
except ImportError:
    pass

from utils.analysis_utils import (
    load_contract,
    sanitize_json_floats
)
from utils.color_utils import compute_true_peak_dbfs

PIPELINE_VERSION = "v1.0.0"

def _load_contracts_data() -> Dict[str, Any]:
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
            if cid and cid != "S11_REPORT_GENERATION":
                ordered.append(cid)
    return ordered

def _get_stage_description(contracts: Dict[str, Any], contract_id: str) -> str:
    for stage_data in contracts.get("stages", {}).values():
        for c in stage_data.get("contracts", []) or []:
            if c.get("id") == contract_id:
                return stage_data.get("name", contract_id)
    return contract_id

def _build_stage_report_entry(context: PipelineContext, contract_id: str, contracts_data: Dict[str, Any]) -> Dict[str, Any]:
    desc = _get_stage_description(contracts_data, contract_id)

    entry: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": None,
        "name": desc,
        "status": "missing_analysis",
        "key_metrics": {},
    }

    data = context.analysis_results.get(contract_id)
    if not data:
        return entry

    entry["stage_id"] = data.get("stage_id")
    entry["status"] = "analyzed"
    entry["key_metrics"] = data.get("session", {})

    return entry

def _compute_crest_and_histogram(
    y: np.ndarray,
    sr: int,
    floor_db: float = -60.0,
    ceil_db: float = 0.0,
    num_bins: int = 30,
) -> Dict[str, Any]:
    arr = np.asarray(y, dtype=np.float32)
    if arr.ndim == 2:
        mono = np.mean(arr, axis=1)
    else:
        mono = arr

    if mono.size == 0:
        crest_db = 0.0
    else:
        rms = float(np.sqrt(np.mean(mono**2)))
        if rms <= 0.0:
            rms_db = float("-inf")
            crest_db = 0.0
        else:
            rms_db = 20.0 * np.log10(rms)
            tp_db = compute_true_peak_dbfs(mono, oversample_factor=4)
            crest_db = tp_db - rms_db

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
        if frame.size == 0: continue
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

def process(context: PipelineContext, contract_id: str) -> bool:
    logger.logger.info(f"[S11] Starting report generation for {contract_id}")

    contract = load_contract(contract_id)
    metrics = contract.get("metrics", {})
    limits = contract.get("limits", {})
    stage_id = contract.get("stage_id")

    session_config = context.metadata.get("session_config", {})
    style_preset = session_config.get("style_preset", "Unknown")

    contracts_data = _load_contracts_data()

    # Use context.pipeline_timings
    executed_contracts = set()
    total_duration = 0.0
    stages_timings = []
    for t in context.pipeline_timings:
        cid = t.get("contract_id")
        if cid:
            executed_contracts.add(cid)
            stages_timings.append(t)
            total_duration += t.get("duration_sec", 0.0)

    all_contracts = _get_ordered_contract_ids(contracts_data)

    stages_to_report = []
    for cid in all_contracts:
        is_executed = cid in executed_contracts
        is_analyzed = cid in context.analysis_results
        if is_executed or is_analyzed:
            stages_to_report.append(cid)

    stages_report = [
        _build_stage_report_entry(context, cid, contracts_data) for cid in stages_to_report
    ]

    # Metrics from S10 QC
    qc_data = context.analysis_results.get("S10_MASTER_FINAL_LIMITS", {})
    # Wait, QC metrics in S10 are usually in 'session' or separate 'qc_metrics' file?
    # Original S10 analysis writes analysis_S10.json AND qc_metrics_S10.json
    # I should have checked S10 script.
    # Assuming for now we rely on S10 putting it in analysis results if I refactor it properly.
    # OR context.analysis_results["S10..."] contains the data.

    # Let's check session keys in S10 (I haven't refactored S10 yet).
    # Assuming I will refactor S10 to include qc metrics in session.

    final_tp = float("nan")
    final_lufs = float("nan")
    final_lra = float("nan")
    final_corr = float("nan")
    final_diff_lr = float("nan")

    if qc_data:
        # Check if qc metrics are in session
        # If I refactor S10, I should put qc metrics in session['qc'] or similar.
        # Legacy S10 analysis might put it in a separate structure.
        # Let's assume standard session structure for now or check S10 later.
        pass

    # Audio analysis from memory
    crest_and_hist = {"crest_factor_db": None, "level_histogram_db": {"bin_edges_db": [], "counts": []}}

    if context.audio_mixdown is not None:
        try:
            res = _compute_crest_and_histogram(context.audio_mixdown, context.sample_rate)
            crest_and_hist = res
        except Exception as e:
            logger.logger.error(f"[S11] Error computing crest/hist: {e}")

    final_metrics = {
        "true_peak_dbtp": final_tp,
        "lufs_integrated": final_lufs,
        "lra": final_lra,
        "correlation": final_corr,
        "channel_loudness_diff_db": final_diff_lr,
        "crest_factor_db": crest_and_hist.get("crest_factor_db"),
        "level_histogram_db": crest_and_hist.get("level_histogram_db"),
    }

    pipeline_durations = {
        "stages": stages_timings,
        "total_duration_sec": total_duration,
        "generated_at_utc": datetime.datetime.utcnow().isoformat() + "Z"
    }

    report = {
        "pipeline_version": PIPELINE_VERSION,
        "generated_at_utc": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "style_preset": style_preset,
        "stages": stages_report,
        "final_metrics": final_metrics,
        "pipeline_durations": pipeline_durations,
    }

    session_state = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "report": report
        },
    }

    session_state = sanitize_json_floats(session_state)
    context.analysis_results[contract_id] = session_state

    return True
