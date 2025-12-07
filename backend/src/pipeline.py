from __future__ import annotations

import json
import sys
import subprocess
import shutil
import logging
from pathlib import Path
from typing import Callable, Dict, Any, List, Optional

from .stages.stage import run_stage, set_active_contract_sequence
from .utils.analysis_utils import get_temp_dir
from .context import PipelineContext
from .utils.audio_memory import load_stems_into_memory, perform_mixdown_in_memory, save_memory_to_disk

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Utilidades comunes: cargar contracts.json y ordenar contratos
# -------------------------------------------------------------------

def _load_contracts() -> Dict[str, Any]:
    """
    Carga struct/contracts.json y devuelve el dict completo.
    """
    base_dir = Path(__file__).resolve().parent      # .../src
    contracts_path = base_dir / "struct" / "contracts.json"

    with contracts_path.open("r", encoding="utf-8") as f:
        contracts = json.load(f)

    return contracts


def _get_ordered_contract_ids(contracts: Dict[str, Any]) -> List[str]:
    """
    Devuelve la lista ordenada de contract_ids según aparecen en contracts.json.

    El orden es el definido por "stages" y, dentro de cada stage, por la lista
    "contracts".
    """
    ordered: List[str] = []

    for stage_data in contracts.get("stages", {}).values():
        for c in stage_data.get("contracts", []) or []:
            cid = c.get("id")
            if cid:
                ordered.append(cid)

    return ordered

def _write_session_config(stage_dir: Path, profiles_by_name: Optional[Dict[str, str]], context: PipelineContext) -> None:
    """
    Genera session_config.json en stage_dir con los instrument_profile
    seleccionados en frontend. Se basa en los stems en memoria.
    """
    def _load_profiles_from_work() -> Dict[str, str]:
        work_profiles = stage_dir.parent / "work" / "stem_profiles.json"
        if not work_profiles.exists():
            return {}
        try:
            raw = json.loads(work_profiles.read_text(encoding="utf-8"))
        except Exception:
            return {}

        mapping: Dict[str, str] = {}
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                profile = str(item.get("profile") or "").strip() or "auto"
                if name:
                    mapping[name] = profile
        return mapping

    def _load_space_depth_bus_styles() -> Dict[str, str]:
        path = stage_dir.parent / "work" / "space_depth_bus_styles.json"
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    try:
        profiles_map = dict(profiles_by_name or {})
        if not profiles_map:
            profiles_map = _load_profiles_from_work()

        space_depth_bus_styles = _load_space_depth_bus_styles()

        # Iterate over memory keys
        stems = []
        for name in sorted(context.audio_stems.keys()):
            prof = profiles_map.get(name, "auto")
            stems.append({"file_name": name, "instrument_profile": prof})

        cfg = {
            "style_preset": "Unknown",
            "stems": stems,
            "space_depth_bus_styles": space_depth_bus_styles,
        }

        cfg_path = stage_dir / "session_config.json"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

        # Also store in context metadata
        context.metadata["session_config"] = cfg

    except Exception as exc:
        logger.warning("[pipeline] No se pudo escribir session_config en %s: %s", stage_dir, exc)

# -------------------------------------------------------------------
# Versión job-aware para Celery: run_pipeline_for_job
# -------------------------------------------------------------------

def run_pipeline_for_job(
    job_id: str,
    media_dir: Path,
    temp_root: Path,
    enabled_stage_keys: Optional[List[str]] = None,
    profiles_by_name: Optional[Dict[str, str]] = None,
    progress_cb: Optional[Callable[[int, int, str, str], None]] = None,
) -> None:
    """
    Pipeline para un job concreto (usado por Celery):
    IN-MEMORY MODE
    """

    logger.info(
        "[pipeline] run_pipeline_for_job: job_id=%s media_dir=%s temp_root=%s enabled_stage_keys=%s",
        job_id,
        media_dir,
        temp_root,
        enabled_stage_keys,
    )

    # Crear contexto único para todo el job con audio en memoria
    context = PipelineContext(
        stage_id="S0_MIX_ORIGINAL",
        job_id=job_id,
        temp_root=temp_root
    )

    # ------------------------------------------------------------------
    # 0) Cargar Stems en Memoria (S0_MIX_ORIGINAL equivalent)
    # ------------------------------------------------------------------
    logger.info("[pipeline] Loading stems into memory from media_dir...")
    load_stems_into_memory(context, media_dir)

    # We need to simulate the file structure for S0_MIX_ORIGINAL because frontend might expect it?
    # Or just write session_config.
    # The frontend downloads files from /files/job_id/stage_id/...
    # If we want the frontend to work, we MUST write files to disk at some point?
    # The user said "keep in memory to optimize processing".
    # Typically, only the FINAL result needs to be on disk, or intermediate artifacts for debugging/reporting.
    # The report viewer shows images and maybe audio previews.
    # If the user wants previews for every stage, we have to write them.
    # But writing WAVs is slow.
    # Maybe we only write MP3s or nothing?
    # Assuming we proceed with full in-memory, and only write JSONs/Images.

    # However, legacy code writes session_config.
    s0_original_dir = context.get_stage_dir("S0_MIX_ORIGINAL")
    s0_original_dir.mkdir(parents=True, exist_ok=True)
    _write_session_config(s0_original_dir, profiles_by_name, context)

    # ------------------------------------------------------------------
    # 1) Mixdown Inicial
    # ------------------------------------------------------------------
    logger.info("[pipeline] Mixdown inicial (in-memory)...")
    perform_mixdown_in_memory(context)

    # Save initial mixdown for preview?
    # save_memory_to_disk(context, s0_original_dir, save_stems=False, save_mixdown=True)

    # ------------------------------------------------------------------
    # 2) "Copy" to S0_SEPARATE_STEMS
    # ------------------------------------------------------------------
    # In memory, this is just changing the stage_id reference in the loop.
    # But we should ensure session_config is available if S0_SEPARATE_STEMS needs it.

    # ------------------------------------------------------------------
    # 3) Construir lista de contratos
    # ------------------------------------------------------------------
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
        return

    set_active_contract_sequence(contract_ids)

    if progress_cb is not None:
        progress_cb(0, total_stages, "initializing", "Inicializando pipeline de mezcla...")

    # ------------------------------------------------------------------
    # 4) Ejecutar cada contrato en orden
    # ------------------------------------------------------------------
    for idx, contract_id in enumerate(contract_ids, start=1):
        context.stage_id = contract_id

        logger.info(
            "[pipeline] Ejecutando contrato %s (%d/%d)",
            contract_id,
            idx,
            total_stages,
        )

        if progress_cb is not None:
            progress_cb(
                idx,
                total_stages,
                contract_id,
                f"Running stage {contract_id}...",
            )

        run_stage(contract_id, context=context)

    # Finally, maybe save the result of the last stage?
    # The last stage is typically mastering.
    # The user usually downloads the result from the last executed stage.
    last_stage = contract_ids[-1]
    last_stage_dir = context.get_stage_dir(last_stage)
    logger.info(f"[pipeline] Saving final result to {last_stage_dir}...")
    save_memory_to_disk(context, last_stage_dir, save_stems=True, save_mixdown=True)


if __name__ == "__main__":
    # CLI simple no longer supported without hydration
    pass
