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


def _write_session_config(stage_dir: Path, profiles_by_name: Optional[Dict[str, str]]) -> None:
    """
    Genera session_config.json en stage_dir con los instrument_profile
    seleccionados en frontend. Se basa en los wav presentes en stage_dir.
    """
    def _load_profiles_from_work() -> Dict[str, str]:
        """
        Si el mapping no llega por argumento (p.ej. por cambios de API),
        intentamos cargarlo del fichero persistido en work/stem_profiles.json.
        """
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
        """
        Recupera estilos por bus seleccionados en frontend (Space/Depth)
        si existen en work/space_depth_bus_styles.json.
        """
        path = stage_dir.parent / "work" / "space_depth_bus_styles.json"
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    try:
        # Prioridad: mapping recibido -> fallback al persistido en work/
        profiles_map = dict(profiles_by_name or {})
        if not profiles_map:
            profiles_map = _load_profiles_from_work()

        space_depth_bus_styles = _load_space_depth_bus_styles()

        wavs = [
            p.name
            for p in stage_dir.glob("*.wav")
            if p.is_file() and p.name.lower() != "full_song.wav"
        ]
        stems = []
        for name in sorted(wavs):
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
    except Exception as exc:
        logger.warning("[pipeline] No se pudo escribir session_config en %s: %s", stage_dir, exc)


def _run_contracts_global(enabled_stage_keys: Optional[List[str]] = None) -> None:
    """
    Versión global (sin job_id) basada en contracts.json.

    Recorre los contratos definidos en struct/contracts.json y llama a run_stage.
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

    # Propagamos la secuencia efectiva al módulo stage.py para que
    # _get_next_contract_id pueda copiar siempre al siguiente contrato habilitado.
    set_active_contract_sequence(contract_ids)

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
      - Antes de ejecutar cada contrato llama a progress_cb(stage_index, total_stages, stage_key, message)
        indicando el stage que está EN PROGRESO.
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

    # Persistir session_config con los perfiles seleccionados
    _write_session_config(s0_original_dir, profiles_by_name)

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

    # Propagar la secuencia efectiva a stage.py para que las copias
    # de stems vayan siempre al siguiente contrato HABILITADO y no a
    # cualquier contrato del pipeline completo.
    set_active_contract_sequence(contract_ids)

    # Callback inicial de progreso (antes de cualquier stage)
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

        # Avisamos ANTES de ejecutar el stage para que el frontend
        # muestre el stage que está EN PROGRESO.
        if progress_cb is not None:
            progress_cb(
                idx,
                total_stages,
                contract_id,
                f"Running stage {contract_id}...",
            )

        # Ejecuta análisis, stage y check con reintentos, copia al siguiente contrato, etc.
        run_stage(contract_id)


if __name__ == "__main__":
    # CLI simple, sin job_id; útil si quieres probar el pipeline en local.
    run_pipeline()
