# C:\mix-master\backend\server.py

from __future__ import annotations

import json
import logging
import shutil
import uuid
from pathlib import Path
from typing import List, Dict, Optional, Any

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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
JOBS_ROOT.mkdir(parents=True, exist_ok=True)
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


def _build_pipeline_stages() -> list[dict[str, Any]]:
    """
    Lee struct/contracts.json y construye la lista de PipelineStage
    que espera el frontend, en términos de contract_id.

    key            -> contract_id (p.ej. "S1_STEM_DC_OFFSET")
    label          -> contract_id (o lo que quieras enseñar)
    description    -> nombre del grupo (Technical Preparation, etc.)
    index          -> orden global 1..N según contracts.json
    mediaSubdir    -> None (de momento no lo usamos)
    updatesCurrentDir -> True
    previewMixRelPath -> None (podríamos usar /<contract_id>/full_song.wav más adelante)
    """
    contracts = _load_contracts()
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

            result.append(
                {
                    "key": contract_id,        # lo que el frontend enviará como enabledStageKeys
                    "label": contract_id,      # puedes refinarlo si quieres algo más bonito
                    "description": group_name, # nombre del bloque (Technical Preparation, etc.)
                    "index": idx,              # orden global
                    "mediaSubdir": None,
                    "updatesCurrentDir": True,
                    "previewMixRelPath": None,
                }
            )

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

    # También podemos persistir estilos de space/depth si vienen
    if space_depth_bus_styles_json:
        try:
            parsed = json.loads(space_depth_bus_styles_json)
            if isinstance(parsed, dict):
                job_root = temp_root
                sd_path = job_root / "work" / "space_depth_bus_styles.json"
                sd_path.parent.mkdir(parents=True, exist_ok=True)
                sd_path.write_text(
                    json.dumps(parsed, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
        except Exception as exc:
            logger.warning(
                "No se pudo parsear space_depth_bus_styles_json=%r: %s",
                space_depth_bus_styles_json,
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
    # 4) Lanzar tarea Celery
    # -----------------------------
    # IMPORTANTE: usamos task_id = job_id para que frontend y backend
    # hablen del mismo identificador.
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
def get_job_status(job_id: str) -> Dict[str, Any]:
    """
    Devuelve el estado del job para el frontend.

    Usa run_full_pipeline_task.AsyncResult(job_id) para asegurarse de que
    se consulta el mismo Celery app/backend que el worker.
    """
    result = run_full_pipeline_task.AsyncResult(job_id)

    state = result.state  # 'PENDING', 'PROGRESS', 'SUCCESS', 'FAILURE', etc.

    # Caso 1: todavía no hay info en Redis (pendiente en la cola)
    if state == states.PENDING:
        return {
            "jobId": job_id,
            "job_id": job_id,
            "status": "pending",
            "stage_index": 0,
            "total_stages": 0,
            "stage_key": "queued",
            "message": "Job pending in queue",
            "progress": 0.0,
        }

    # Caso 2: en progreso (nuestro task usa state="PROGRESS")
    if state in ("PROGRESS", states.STARTED):
        meta = result.info or {}
        # meta viene del update_state(state="PROGRESS", meta={...})
        stage_index = int(meta.get("stage_index", 0))
        total_stages = int(meta.get("total_stages", 0))
        stage_key = str(meta.get("stage_key", "running"))
        message = str(meta.get("message", "Processing mix..."))
        progress = float(meta.get("progress", 0.0))

        return {
            "jobId": job_id,
            "job_id": job_id,
            "status": "running",
            "stage_index": stage_index,
            "total_stages": total_stages,
            "stage_key": stage_key,
            "message": message,
            "progress": progress,
        }

    # Caso 3: terminado con éxito
    if state == states.SUCCESS:
        payload = result.result or {}
        if not isinstance(payload, dict):
            payload = {"raw_result": payload}

        # Compatibilidad con el frontend (usa jobId/job_id y status)
        payload.setdefault("jobId", job_id)
        payload.setdefault("job_id", job_id)
        payload.setdefault("status", "success")

        # Aseguramos que existen métricas, aunque sea dict vacío
        metrics = payload.get("metrics") or {}
        payload["metrics"] = metrics

        return payload

    # Caso 4: fallo o estado terminal raro
    info = result.info
    if isinstance(info, Exception):
        error_msg = f"{type(info).__name__}: {info}"
    elif isinstance(info, dict):
        error_msg = info.get("exc_message") or str(info)
    else:
        error_msg = str(info)

    return {
        "jobId": job_id,
        "job_id": job_id,
        "status": "failure",
        "stage_index": 0,
        "total_stages": 0,
        "stage_key": "error",
        "message": error_msg or "Error while processing mix",
        "progress": 0.0,
        "error": error_msg or None,
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
def get_pipeline_stages() -> list[dict[str, Any]]:
    """
    Devuelve la definición de etapas del pipeline en términos de contract_id,
    para que el frontend pueda habilitar/deshabilitar contracts concretos.
    """
    return _build_pipeline_stages()
