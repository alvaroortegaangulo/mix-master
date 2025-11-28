from __future__ import annotations

import json
import sys
import subprocess
import shutil
import logging
from pathlib import Path
from typing import Callable, Dict, Any, List, Optional

from .stages.stage import run_stage
from .utils.analysis_utils import get_temp_dir

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

    El orden es:
      S0_INPUT -> S1_TECH_PREP -> ... -> S11_REPORTING
    y dentro de cada stage, en el orden de "contracts".
    """
    ordered: List[str] = []

    for stage_data in contracts.get("stages", {}).values():
        for c in stage_data.get("contracts", []):
            cid = c.get("id")
            if cid:
                ordered.append(cid)

    return ordered


# -------------------------------------------------------------------
# Versión CLI "legacy": sin job_id explícito
# -------------------------------------------------------------------

def _run_copy_and_mixdown(src_stage: str, dst_stage: str) -> None:
    """
    Versión antigua/CLI: copia stems de temp/<src_stage> -> temp/<dst_stage>
    y hace mixdown de temp/<src_stage> a full_song.wav.

    Se deja por compatibilidad. No es job-aware.
    """
    base_dir = Path(__file__).resolve().parent      # .../src
    utils_dir = base_dir / "utils"
    copy_script = utils_dir / "copy_stems.py"
    mixdown_script = utils_dir / "mixdown_stems.py"

    # 1) Copiar stems src -> dst
    subprocess.run(
        [sys.executable, str(copy_script), src_stage, dst_stage],
        check=False,
    )

    # 2) Mixdown de los stems en la carpeta origen
    subprocess.run(
        [sys.executable, str(mixdown_script), src_stage],
        check=False,
    )


def _run_contracts_global(enabled_stage_keys: Optional[List[str]] = None) -> None:
    """
    Versión global (sin job_id) basada en contracts.json.

    Recorre todos los contratos definidos en struct/contracts.json y llama a run_stage.

    Si enabled_stage_keys no es None, interpreta que contiene contract_ids
    (S0_SESSION_FORMAT, S1_STEM_DC_OFFSET, etc.) y filtra en base a eso.
    """
    contracts = _load_contracts()
    all_contract_ids = _get_ordered_contract_ids(contracts)

    if enabled_stage_keys:
        enabled_set = set(enabled_stage_keys)
        contract_ids = [cid for cid in all_contract_ids if cid in enabled_set]
    else:
        contract_ids = all_contract_ids

    for contract_id in contract_ids:
        run_stage(contract_id)


def run_pipeline(
    enabled_stage_keys: Optional[List[str]] = None,
) -> None:
    """
    Versión CLI de toda la vida (no job-aware explícito):

      - Asume que ya tienes stems en temp/S0_MIX_ORIGINAL.
      - Copia S0_MIX_ORIGINAL -> S0_SESSION_FORMAT y hace mixdown.
      - Ejecuta todos los contracts de struct/contracts.json (o filtrados).
    """
    logger.info(
        "[pipeline] run_pipeline (modo CLI), enabled_stage_keys=%s",
        enabled_stage_keys,
    )

    # Paso inicial "legacy"
    src_stage = "S0_MIX_ORIGINAL"
    dst_stage = "S0_SESSION_FORMAT"

    _run_copy_and_mixdown(src_stage, dst_stage)
    _run_contracts_global(enabled_stage_keys=enabled_stage_keys)


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

      - Copia los stems subidos (media_dir) a S0_MIX_ORIGINAL del job.
      - Hace mixdown de S0_MIX_ORIGINAL (full_song.wav original).
      - Copia S0_MIX_ORIGINAL -> S0_SESSION_FORMAT.
      - Recorre los contratos definidos en contracts.json en orden.
      - Opcionalmente filtra por enabled_stage_keys (lista de contract_ids).
      - Después de cada contrato, llama a progress_cb(stage_index, total_stages, stage_key, message).

    Notas:
      - La resolución de directorios temp/<job_id>/<contract_id> se hace vía
        get_temp_dir(contract_id), que usa la variable de entorno MIX_JOB_ID
        que la tarea Celery ya ha definido.
      - profiles_by_name se conserva por si quieres integrarlo en tus scripts
        (leyendo temp/<job_id>/work/stem_profiles.json, etc.).
    """
    base_dir = Path(__file__).resolve().parent      # .../src

    utils_dir = base_dir / "utils"
    copy_script = utils_dir / "copy_stems.py"
    mixdown_script = utils_dir / "mixdown_stems.py"

    logger.info(
        "[pipeline] run_pipeline_for_job: job_id=%s media_dir=%s temp_root=%s enabled_stage_keys=%s",
        job_id,
        media_dir,
        temp_root,
        enabled_stage_keys,
    )

    # ------------------------------------------------------------------
    # 0) Preparar S0_MIX_ORIGINAL para este job
    # ------------------------------------------------------------------
    # get_temp_dir usa MIX_JOB_ID para resolver temp/<job_id>/S0_MIX_ORIGINAL
    s0_original_dir = get_temp_dir("S0_MIX_ORIGINAL", create=True)

    # Limpiar cualquier resto previo dentro de S0_MIX_ORIGINAL
    for p in s0_original_dir.glob("*"):
        if p.is_file():
            p.unlink()
        elif p.is_dir():
            shutil.rmtree(p, ignore_errors=True)

    # Copiar stems desde media_dir a S0_MIX_ORIGINAL (solo WAV/AIF/FLAC)
    audio_exts = {".wav", ".aif", ".aiff", ".flac"}
    for src in media_dir.iterdir():
        if not src.is_file():
            continue
        if src.suffix.lower() not in audio_exts:
            continue
        dst = s0_original_dir / src.name
        shutil.copy2(src, dst)
        logger.info("[pipeline] Copiado stem %s -> %s", src.name, dst)

    # ------------------------------------------------------------------
    # 1) Mixdown de S0_MIX_ORIGINAL (full_song.wav original)
    # ------------------------------------------------------------------
    logger.info("[pipeline] Mixdown de S0_MIX_ORIGINAL...")
    subprocess.run(
        [sys.executable, str(mixdown_script), "S0_MIX_ORIGINAL"],
        check=False,
    )

    # ------------------------------------------------------------------
    # 2) Copiar stems a S0_SESSION_FORMAT
    # ------------------------------------------------------------------
    logger.info("[pipeline] Copiando stems S0_MIX_ORIGINAL -> S0_SESSION_FORMAT...")
    subprocess.run(
        [sys.executable, str(copy_script), "S0_MIX_ORIGINAL", "S0_SESSION_FORMAT"],
        check=False,
    )

    # ------------------------------------------------------------------
    # 3) Construir lista de contratos desde contracts.json
    # ------------------------------------------------------------------
    contracts = _load_contracts()
    all_contract_ids = _get_ordered_contract_ids(contracts)

    if enabled_stage_keys:
        # IMPORTANTE: aquí interpretamos enabled_stage_keys como lista de contract_ids,
        # por ejemplo: ["S1_STEM_DC_OFFSET", "S1_STEM_WORKING_LOUDNESS", ...].
        enabled_set = set(enabled_stage_keys)
        contract_ids = [cid for cid in all_contract_ids if cid in enabled_set]
    else:
        contract_ids = all_contract_ids

    total_stages = len(contract_ids)
    if total_stages == 0:
        logger.warning(
            "[pipeline] No hay contratos a ejecutar (enabled_stage_keys=%s).",
            enabled_stage_keys,
        )
        return

    # Callback inicial de progreso (stage_index = 0)
    if progress_cb is not None:
        progress_cb(
            0,
            total_stages,
            "initializing",
            "Inicializando pipeline de mezcla...",
        )

    # ------------------------------------------------------------------
    # 4) Ejecutar cada contrato en orden
    # ------------------------------------------------------------------
    for idx, contract_id in enumerate(contract_ids, start=1):
        logger.info(
            "[pipeline] Ejecutando contrato %s (%d/%d)",
            contract_id,
            idx,
            total_stages,
        )

        # Ejecuta análisis, stage y check con reintentos, y copia al siguiente contrato
        run_stage(contract_id)

        if progress_cb is not None:
            progress_cb(
                idx,
                total_stages,
                contract_id,
                f"Stage {contract_id} completado.",
            )


if __name__ == "__main__":
    # CLI simple, sin job_id; útil si quieres probar el pipeline en local.
    run_pipeline()
