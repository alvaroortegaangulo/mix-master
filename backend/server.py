# C:\mix-master\backend\server.py

from __future__ import annotations

import json
import logging
import shutil
import uuid
from pathlib import Path
from typing import List, Dict, Optional, Any

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from celery.result import AsyncResult
from celery import states

from celery_app import celery_app
from tasks import run_full_pipeline_task

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Mix-Master API")

# CORS (ajusta origins a tu frontend según necesites)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ROOT = Path(__file__).resolve().parent          # .../backend
SRC_DIR = PROJECT_ROOT / "src"
CONTRACTS_PATH = SRC_DIR / "struct" / "contracts.json"
JOBS_ROOT = PROJECT_ROOT / "temp"

# Exponer /files/{jobId}/... -> backend/temp/{jobId}/...
app.mount(
    "/files",
    StaticFiles(directory=JOBS_ROOT, html=False),
    name="files",
)


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _create_job_dirs() -> tuple[str, Path, Path]:
    """
    Crea la estructura de carpetas para un job nuevo.

    Devuelve:
      - job_id
      - media_dir (donde se guardan los stems originales)
      - temp_root (raíz temporal del job, p.ej. backend/temp/<job_id>)
    """
    job_id = uuid.uuid4().hex

    media_dir = PROJECT_ROOT / "media" / job_id
    temp_root = PROJECT_ROOT / "temp" / job_id

    media_dir.mkdir(parents=True, exist_ok=True)
    temp_root.mkdir(parents=True, exist_ok=True)

    return job_id, media_dir, temp_root


def _load_contracts() -> Dict[str, Any]:
    if not CONTRACTS_PATH.exists():
        raise RuntimeError(f"No se encuentra {CONTRACTS_PATH}")
    with CONTRACTS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _get_ordered_contract_ids(enabled_contract_ids: Optional[List[str]] = None) -> List[str]:
    """
    Devuelve la lista de contract_id en el orden definido en contracts.json.
    Si enabled_contract_ids no es None, filtra por esa lista.
    """
    contracts = _load_contracts()
    stages = contracts.get("stages", {}) or {}

    ordered: List[str] = []
    for _stage_group_key, stage_group in stages.items():
        for c in stage_group.get("contracts", []) or []:
            cid = c.get("id")
            if not cid:
                continue
            if enabled_contract_ids is not None and cid not in enabled_contract_ids:
                continue
            ordered.append(cid)

    return ordered


def _build_pipeline_stage_list() -> List[Dict[str, Any]]:
    """
    Construye la lista de PipelineStage que el frontend espera, alineada con contracts.json.

    key            -> contract_id (p.ej. "S1_STEM_DC_OFFSET")
    label          -> contract_id (o lo que quieras enseñar)
    description    -> texto corto basado en el stage group y target_scope
    index          -> orden global 1..N según contracts.json
    mediaSubdir    -> "/<contract_id>" (no se usa ahora mismo en frontend)
    updatesCurrentDir -> True (todas las etapas actualizan su carpeta)
    previewMixRelPath -> "/<contract_id>/full_song.wav"
    """
    contracts = _load_contracts()
    stages = contracts.get("stages", {}) or {}

    result: List[Dict[str, Any]] = []
    idx = 0

    for stage_group_key, stage_group in stages.items():
        group_name = stage_group.get("name", stage_group_key)
        for c in stage_group.get("contracts", []) or []:
            cid = c.get("id")
            if not cid:
                continue
            idx += 1

            target_scope = c.get("target_scope", "")
            description = f"{group_name} (scope: {target_scope})"

            result.append(
                {
                    "key": cid,                         # muy importante: contract_id
                    "label": cid,                       # puedes refinarlo más adelante
                    "description": description,
                    "index": idx,
                    "mediaSubdir": f"/{cid}",
                    "updatesCurrentDir": True,
                    "previewMixRelPath": f"/{cid}/full_song.wav",
                }
            )

    return result


def _load_job_config(job_id: str) -> Dict[str, Any]:
    """
    Lee temp/<job_id>/job_config.json si existe (enabled_stage_keys, perfiles, etc.).
    """
    cfg_path = JOBS_ROOT / job_id / "job_config.json"
    if not cfg_path.exists():
        return {}
    try:
        with cfg_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("No se pudo leer job_config.json para job_id=%s: %s", job_id, exc)
        return {}


def _build_pipeline_stages() -> list[dict[str, Any]]:
    """
    Lee struct/contracts.json y construye la lista de PipelineStage
    que espera el frontend, en términos de contract_id.
    """
    with CONTRACTS_PATH.open("r", encoding="utf-8") as f:
        contracts = json.load(f)

    stages_cfg = contracts.get("stages", {}) or {}
    result: list[dict[str, Any]] = []
    idx = 0

    # Recorremos en el mismo orden que en contracts.json
    for stage_group_id, stage_group in stages_cfg.items():
        group_name = stage_group.get("name") or stage_group_id
        contracts_list = stage_group.get("contracts", []) or []

        for contract in contracts_list:
            contract_id = str(contract.get("id") or "").strip()
            if not contract_id:
                continue

            idx += 1

            # Mapeo mínimo para que coincida con PipelineStage del frontend
            result.append(
                {
                    "key": contract_id,               # lo que el frontend enviará como enabledStageKeys
                    "label": contract_id,             # puedes refinarlo si quieres algo más bonito
                    "description": group_name,        # nombre del bloque (Technical Preparation, etc.)
                    "index": idx,                     # orden global
                    "mediaSubdir": None,              # por ahora sin previews por etapa
                    "updatesCurrentDir": True,        # todas las etapas actualizan la sesión
                    "previewMixRelPath": None,        # más adelante: f"{contract_id}/full_song.wav"
                }
            )

    return result


def _build_final_urls_and_metrics(job_id: str) -> Dict[str, Any]:
    """
    Intenta construir:
      - full_song_url
      - original_full_song_url
      - metrics (si existen en el report de S11)

    Todo basado en el sistema de ficheros y analysis_S11_REPORT_GENERATION.json.
    """
    job_root = JOBS_ROOT / job_id

    # 1) full_song_url: preferimos S11, luego S10, luego el último contract_id que tenga full_song.wav
    contracts_all = _get_ordered_contract_ids()
    full_rel: Optional[str] = None

    # Intentos preferentes
    preferred = ["S11_REPORT_GENERATION", "S10_MASTER_FINAL_LIMITS"]
    for cid in preferred:
        p = job_root / cid / "full_song.wav"
        if p.exists():
            full_rel = f"/{cid}/full_song.wav"
            break

    # Si no están, buscamos el último contract con full_song.wav
    if full_rel is None:
        for cid in reversed(contracts_all):
            p = job_root / cid / "full_song.wav"
            if p.exists():
                full_rel = f"/{cid}/full_song.wav"
                break

    # 2) original_full_song_url: usamos S0_SESSION_FORMAT/full_song.wav si existe
    orig_rel: Optional[str] = None
    p_orig = job_root / "S0_SESSION_FORMAT" / "full_song.wav"
    if p_orig.exists():
        orig_rel = "/S0_SESSION_FORMAT/full_song.wav"

    # 3) metrics desde analysis_S11_REPORT_GENERATION.json (si existe)
    metrics: Dict[str, Any] = {}
    s11_analysis = job_root / "S11_REPORT_GENERATION" / "analysis_S11_REPORT_GENERATION.json"
    if s11_analysis.exists():
        try:
            with s11_analysis.open("r", encoding="utf-8") as f:
                data = json.load(f)
            session = data.get("session", {}) or {}
            report = (session.get("report", {}) or {})
            final_metrics = report.get("final_metrics", {}) or {}

            # Mapear a la estructura de MixMetrics del frontend.
            # Usamos defaults razonables; si no existen campos, quedarán en 0 o vacío.
            metrics = {
                "final_peak_dbfs": final_metrics.get("final_true_peak_dbfs")
                or final_metrics.get("final_peak_dbfs")
                or 0.0,
                "final_rms_dbfs": final_metrics.get("final_rms_dbfs") or 0.0,
                "tempo_bpm": final_metrics.get("tempo_bpm") or 0.0,
                "tempo_confidence": final_metrics.get("tempo_confidence") or 0.0,
                "key": final_metrics.get("key") or "",
                "scale": final_metrics.get("scale") or "",
                "key_strength": final_metrics.get("key_strength") or 0.0,
                "vocal_shift_min": final_metrics.get("vocal_shift_min") or 0.0,
                "vocal_shift_max": final_metrics.get("vocal_shift_max") or 0.0,
                "vocal_shift_mean": final_metrics.get("vocal_shift_mean") or 0.0,
            }
        except Exception as exc:
            logger.warning(
                "No se pudo leer métricas finales de %s: %s", s11_analysis, exc
            )

    result: Dict[str, Any] = {
        "full_song_url": f"/files/{job_id}{full_rel}" if full_rel else "",
        "original_full_song_url": f"/files/{job_id}{orig_rel}" if orig_rel else "",
        "metrics": metrics,
    }
    return result


# -------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------

@app.post("/mix")
async def mix_tracks(
    files: List[UploadFile] = File(...),
    stages_json: Optional[str] = Form(None),
    stem_profiles_json: Optional[str] = Form(None),
    space_depth_bus_styles_json: Optional[str] = Form(None),
):
    job_id, media_dir, temp_root = _create_job_dirs()
    logger.info(
        "Nuevo job de mezcla: job_id=%s, n_files=%d", job_id, len(files)
    )

    # -----------------------------
    # 1) Parsear perfiles de stems
    # -----------------------------
    profiles_by_name: Dict[str, str] = {}
    raw_profiles: List[Dict[str, str]] = []

    if stem_profiles_json:
        try:
            parsed = json.loads(stem_profiles_json)
            if isinstance(parsed, list):
                for item in parsed:
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get("name") or "").strip()
                    profile = str(item.get("profile") or "").strip() or "auto"
                    if name:
                        profiles_by_name[name] = profile
                        raw_profiles.append({"name": name, "profile": profile})
        except Exception as exc:
            logger.warning(
                "No se pudo parsear stem_profiles_json=%r: %s",
                stem_profiles_json,
                exc,
            )

    # -----------------------------
    # 2) Guardar los stems en disco
    # -----------------------------
    for f in files:
        dest_path = media_dir / f.filename
        with dest_path.open("wb") as out:
            out.write(await f.read())

    # Persistir mapping a disco (para stages posteriores, depuración, etc.)
    if raw_profiles:
        job_root = temp_root
        profiles_path = job_root / "work" / "stem_profiles.json"
        profiles_path.parent.mkdir(parents=True, exist_ok=True)
        profiles_path.write_text(
            json.dumps(raw_profiles, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # -----------------------------
    # 3) Parsear stages_json (lista de contract_id habilitados)
    # -----------------------------
    enabled_stage_keys: Optional[List[str]] = None
    if stages_json:
        try:
            parsed = json.loads(stages_json)
            if isinstance(parsed, list):
                enabled_stage_keys = [str(k) for k in parsed]
        except Exception as exc:
            logger.warning(
                "No se pudo parsear stages_json=%r: %s", stages_json, exc
            )

    # -----------------------------
    # 3b) Parsear estilos de space/depth (bus -> estilo)
    # -----------------------------
    space_depth_bus_styles: Dict[str, str] = {}
    if space_depth_bus_styles_json:
        try:
            parsed = json.loads(space_depth_bus_styles_json)
            if isinstance(parsed, dict):
                space_depth_bus_styles = {
                    str(k): str(v) for k, v in parsed.items()
                }
        except Exception as exc:
            logger.warning(
                "No se pudo parsear space_depth_bus_styles_json=%r: %s",
                space_depth_bus_styles_json,
                exc,
            )

    # Guardar job_config.json para que /jobs pueda conocer qué contracts se han pedido
    job_config = {
        "job_id": job_id,
        "enabled_stage_keys": enabled_stage_keys,
        "profiles_by_name": profiles_by_name,
        "space_depth_bus_styles": space_depth_bus_styles,
    }
    cfg_path = temp_root / "job_config.json"
    cfg_path.write_text(
        json.dumps(job_config, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # -----------------------------
    # 4) Lanzar tarea Celery
    # -----------------------------
    run_full_pipeline_task.apply_async(
        args=[
            job_id,
            str(media_dir),
            str(temp_root),
            enabled_stage_keys,
            profiles_by_name,
        ],
        task_id=job_id,
    )

    return {"jobId": job_id}


@app.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    """
    Devuelve el estado del job en el formato que el frontend espera.
    """
    result = AsyncResult(job_id, app=celery_app)

    if result is None:
        raise HTTPException(status_code=404, detail="Job not found")

    job_cfg = _load_job_config(job_id)
    enabled_stage_keys = job_cfg.get("enabled_stage_keys")
    if not isinstance(enabled_stage_keys, list):
        enabled_stage_keys = None

    # nº de contracts totales para este job (filtrando si hace falta)
    contract_ids = _get_ordered_contract_ids(
        enabled_contract_ids=enabled_stage_keys
    )
    total_stages = len(contract_ids) if contract_ids else 0

    state = result.state

    # PENDING => en cola
    if state == states.PENDING:
        return {
            "job_id": job_id,
            "status": "pending",
            "stage_index": 0,
            "total_stages": total_stages,
            "stage_key": "queued",
            "message": "Job pending in queue",
            "progress": 0.0,
        }

    # STARTED / PROGRESS => en ejecución, usamos meta de Celery
    if state in (states.STARTED, "PROGRESS"):
        info = result.info or {}
        stage_index = int(info.get("stage_index") or 0)
        stage_key = info.get("stage_key") or ""
        message = info.get("message") or "Processing mix..."
        progress = float(info.get("progress") or 0.0)

        # Si el worker conoce mejor total_stages, lo usamos
        meta_total = info.get("total_stages")
        if isinstance(meta_total, int) and meta_total > 0:
            total_stages = meta_total

        return {
            "job_id": job_id,
            "status": "running",
            "stage_index": stage_index,
            "total_stages": total_stages,
            "stage_key": stage_key,
            "message": message,
            "progress": progress,
        }

    # SUCCESS => pipeline terminado. Construimos URLs y métricas.
    if state == states.SUCCESS:
        # Intentamos usar lo que devuelva la tarea, pero tenemos fallback al FS.
        task_result = result.result or {}
        # Fallback: construir a partir del sistema de ficheros y S11.
        fs_info = _build_final_urls_and_metrics(job_id)

        full_song_url = task_result.get("full_song_url") or fs_info["full_song_url"]
        original_full_song_url = (
            task_result.get("original_full_song_url")
            or fs_info["original_full_song_url"]
        )
        metrics = task_result.get("metrics") or fs_info["metrics"]

        return {
            "job_id": job_id,
            "status": "success",
            "stage_index": total_stages,
            "total_stages": total_stages,
            "stage_key": "finished",
            "message": "Mix finished",
            "progress": 100.0,
            "full_song_url": full_song_url,
            "original_full_song_url": original_full_song_url,
            "metrics": metrics,
        }

    # FAILURE / REVOKED => error
    if state in (states.FAILURE, states.REVOKED):
        error_msg = str(result.info) if result.info else "Unknown error"
        return {
            "job_id": job_id,
            "status": "failure",
            "stage_index": 0,
            "total_stages": total_stages,
            "stage_key": "error",
            "message": error_msg,
            "progress": 0.0,
            "error": error_msg,
        }

    # Otros estados raros
    return {
        "job_id": job_id,
        "status": "failure",
        "stage_index": 0,
        "total_stages": total_stages,
        "stage_key": "unknown",
        "message": f"Estado Celery desconocido: {state}",
        "progress": 0.0,
        "error": f"Estado Celery desconocido: {state}",
    }


@app.post("/cleanup-temp")
async def cleanup_temp():
    """
    Limpia carpetas temp/ y media/ completas.
    El frontend lo llama al arrancar o al hacer reset.
    """
    for sub in ("temp", "media"):
        dir_path = PROJECT_ROOT / sub
        if dir_path.exists():
            shutil.rmtree(dir_path, ignore_errors=True)
        dir_path.mkdir(parents=True, exist_ok=True)

    return {"status": "ok"}


@app.get("/pipeline/stages")
def get_pipeline_stages():
    """
    Devuelve la lista de contratos en orden, para que el frontend
    seleccione/des-seleccione directamente por contract_id.
    """
    stages = _build_pipeline_stage_list()
    return stages


@app.get("/pipeline/stages")
def get_pipeline_stages() -> list[dict[str, Any]]:
    """
    Devuelve la definición de etapas del pipeline en términos de contract_id,
    para que el frontend pueda habilitar/deshabilitar contracts concretos.
    """
    return _build_pipeline_stages()