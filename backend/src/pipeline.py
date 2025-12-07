from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable, Dict, Any, List, Optional

from .stages.stage import run_stage, set_active_contract_sequence
from .context import PipelineContext
from .utils.audio_memory import load_stems_from_job_store, perform_mixdown_in_memory, save_memory_to_disk
from .utils.job_store import JobStore

logger = logging.getLogger(__name__)

def _load_contracts() -> Dict[str, Any]:
    base_dir = Path(__file__).resolve().parent
    contracts_path = base_dir / "struct" / "contracts.json"
    with contracts_path.open("r", encoding="utf-8") as f:
        return json.load(f)

def _get_ordered_contract_ids(contracts: Dict[str, Any]) -> List[str]:
    ordered: List[str] = []
    for stage_data in contracts.get("stages", {}).values():
        for c in stage_data.get("contracts", []) or []:
            cid = c.get("id")
            if cid: ordered.append(cid)
    return ordered

def _generate_session_config(context: PipelineContext) -> None:
    # Generates session_config in memory and stores it in context.metadata
    profiles_map = context.metadata.get("profiles_by_name", {})
    space_depth_bus_styles = context.metadata.get("space_depth_bus_styles", {})

    stems = []
    for name in sorted(context.audio_stems.keys()):
        prof = profiles_map.get(name, "auto")
        stems.append({"file_name": name, "instrument_profile": prof})

    cfg = {
        "style_preset": "Unknown",
        "stems": stems,
        "space_depth_bus_styles": space_depth_bus_styles,
    }
    context.metadata["session_config"] = cfg

def run_pipeline_for_job(
    job_id: str,
    media_dir: Path,
    enabled_stage_keys: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    progress_cb: Optional[Callable[[int, int, str, str], None]] = None,
) -> PipelineContext:

    logger.info("[pipeline] run_pipeline_for_job: job_id=%s media_dir=%s", job_id, media_dir)

    context = PipelineContext(
        stage_id="S0_MIX_ORIGINAL",
        job_id=job_id,
    )
    if metadata:
        context.metadata.update(metadata)

    logger.info("[pipeline] Loading stems into memory from JobStore (Redis)...")
    job_store = JobStore()
    load_stems_from_job_store(context, job_store)

    _generate_session_config(context)

    logger.info("[pipeline] Mixdown inicial (in-memory)...")
    perform_mixdown_in_memory(context)

    contracts = _load_contracts()
    all_contract_ids = _get_ordered_contract_ids(contracts)

    if enabled_stage_keys:
        enabled_set = set(enabled_stage_keys)
        contract_ids = [cid for cid in all_contract_ids if cid in enabled_set]
    else:
        contract_ids = all_contract_ids

    total_stages = len(contract_ids)
    if total_stages == 0:
        logger.warning("[pipeline] No hay contratos a ejecutar.")
        return context

    set_active_contract_sequence(contract_ids)

    if progress_cb: progress_cb(0, total_stages, "initializing", "Inicializando pipeline de mezcla...")

    for idx, contract_id in enumerate(contract_ids, start=1):
        context.stage_id = contract_id
        logger.info("[pipeline] Ejecutando contrato %s (%d/%d)", contract_id, idx, total_stages)
        if progress_cb: progress_cb(idx, total_stages, contract_id, f"Running stage {contract_id}...")

        run_stage(contract_id, context=context)

    # Note: We do NOT save memory to disk here. The task will extract report/metrics.
    # If users want WAVs, we'd need to store them or save to Redis (heavy).
    # Since the goal is "in memory treatment", we leave them in context.

    return context
