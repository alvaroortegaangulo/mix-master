from __future__ import annotations

import json
import logging
import shutil
import uuid
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from io import BytesIO

import aiofiles
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.concurrency import run_in_threadpool

from tasks import run_full_pipeline_task
from src.utils.job_store import JobStore

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

logger = logging.getLogger("mix_master.server")

app = FastAPI(title="Mix-Master API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://music-mix-master.com",
        "https://api.music-mix-master.com",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
CONTRACTS_PATH = SRC_DIR / "struct" / "contracts.json"
MEDIA_ROOT = PROJECT_ROOT / "media"
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

job_store = JobStore()

def _create_job_dirs() -> tuple[str, Path]:
    job_id = uuid.uuid4().hex
    media_dir = MEDIA_ROOT / job_id
    media_dir.mkdir(parents=True, exist_ok=True)
    logger.info("[_create_job_dirs] job_id=%s media_dir=%s", job_id, media_dir)
    return job_id, media_dir

def _get_media_dir(job_id: str) -> Path:
    return MEDIA_ROOT / job_id

def _load_contracts() -> Dict[str, Any]:
    if not CONTRACTS_PATH.exists():
        raise RuntimeError(f"No se encuentra {CONTRACTS_PATH}")
    with CONTRACTS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)

def _build_pipeline_stages() -> list[dict[str, Any]]:
    contracts = _load_contracts()
    stages_cfg = contracts.get("stages", {}) or {}
    result: list[dict[str, Any]] = []
    idx = 0
    for stage_group_id, stage_group in stages_cfg.items():
        group_name = stage_group.get("name") or stage_group_id
        contracts_list = stage_group.get("contracts", []) or []
        for contract in contracts_list:
            contract_id = str(contract.get("id") or "").strip()
            if not contract_id: continue
            idx += 1
            preview_rel_path = f"/{contract_id}/full_song.wav"
            result.append({
                "key": contract_id,
                "label": contract_id,
                "description": group_name,
                "index": idx,
                "mediaSubdir": None,
                "updatesCurrentDir": True,
                "previewMixRelPath": preview_rel_path,
            })
    return result

PROFILES_PATH = SRC_DIR / "struct" / "profiles.json"
def _load_profiles() -> Dict[str, Any]:
    if not PROFILES_PATH.exists():
        raise RuntimeError(f"No se encuentra {PROFILES_PATH}")
    with PROFILES_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)

@app.post("/mix")
async def mix_tracks(
    files: List[UploadFile] = File(...),
    stages_json: Optional[str] = Form(None),
    stem_profiles_json: Optional[str] = Form(None),
    space_depth_bus_styles_json: Optional[str] = Form(None),
    upload_mode: str = Form("song"),
):
    job_id, media_dir = _create_job_dirs()

    status = {
        "jobId": job_id,
        "job_id": job_id,
        "status": "pending",
        "stage_index": 0,
        "total_stages": 0,
        "stage_key": "queued",
        "message": "Job pending in queue",
        "progress": 0.0,
    }
    job_store.set_status(job_id, status)

    raw_mode = (upload_mode or "song").strip().lower()
    is_stems_upload = raw_mode in {"stems", "upload_stems", "stems_true", "true", "1"}
    normalized_mode = "stems" if is_stems_upload else "song"
    upload_info = {"upload_mode": normalized_mode, "stems": is_stems_upload}

    profiles_by_name: Dict[str, str] = {}
    if stem_profiles_json:
        try:
            parsed = json.loads(stem_profiles_json)
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict):
                        name = str(item.get("name") or "").strip()
                        profile = str(item.get("profile") or "").strip() or "auto"
                        if name: profiles_by_name[name] = profile
        except Exception: pass

    space_depth_styles = {}
    if space_depth_bus_styles_json:
        try:
            space_depth_styles = json.loads(space_depth_bus_styles_json)
        except Exception: pass

    enabled_stage_keys: Optional[List[str]] = None
    if stages_json:
        try:
            parsed = json.loads(stages_json)
            if isinstance(parsed, list): enabled_stage_keys = [str(k) for k in parsed]
        except Exception: pass

    for f in files:
        content = await f.read()
        await run_in_threadpool(job_store.save_input_file, job_id, f.filename, content)

    try:
        run_full_pipeline_task.apply_async(
            args=[job_id, str(media_dir), enabled_stage_keys, profiles_by_name, upload_info, space_depth_styles],
            task_id=job_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="No se pudo encolar la tarea")

    return {"jobId": job_id}

@app.post("/mix/init")
async def init_mix_job(
    stages_json: Optional[str] = Form(None),
    stem_profiles_json: Optional[str] = Form(None),
    space_depth_bus_styles_json: Optional[str] = Form(None),
    upload_mode: str = Form("song"),
):
    job_id, media_dir = _create_job_dirs()

    status = {
        "jobId": job_id,
        "job_id": job_id,
        "status": "pending",
        "stage_index": 0,
        "total_stages": 0,
        "stage_key": "queued",
        "message": "Job pending in queue",
        "progress": 0.0,
    }
    job_store.set_status(job_id, status)

    raw_mode = (upload_mode or "song").strip().lower()
    is_stems_upload = raw_mode in {"stems", "upload_stems", "stems_true", "true", "1"}
    normalized_mode = "stems" if is_stems_upload else "song"

    config = {
        "upload_mode": {"upload_mode": normalized_mode, "stems": is_stems_upload},
        "profiles_by_name": {},
        "space_depth_styles": {},
        "enabled_stage_keys": None
    }

    if stem_profiles_json:
        try:
            parsed = json.loads(stem_profiles_json)
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict):
                        name = str(item.get("name") or "").strip()
                        profile = str(item.get("profile") or "").strip() or "auto"
                        if name: config["profiles_by_name"][name] = profile
        except Exception: pass

    if space_depth_bus_styles_json:
        try:
            config["space_depth_styles"] = json.loads(space_depth_bus_styles_json)
        except Exception: pass

    if stages_json:
        try:
            parsed = json.loads(stages_json)
            if isinstance(parsed, list): config["enabled_stage_keys"] = [str(k) for k in parsed]
        except Exception: pass

    job_store.save_config(job_id, config)
    return {"jobId": job_id}

@app.post("/mix/{job_id}/upload-file")
async def upload_file_for_job(job_id: str, file: UploadFile = File(...)):
    # Read file into memory and save to Redis
    content = await file.read()
    await run_in_threadpool(job_store.save_input_file, job_id, file.filename, content)
    return {"ok": True, "filename": file.filename, "bytes": len(content)}

@app.post("/mix/{job_id}/start")
async def start_mix_job_endpoint(job_id: str):
    media_dir = _get_media_dir(job_id)
    if not media_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    config = job_store.get_config(job_id)

    try:
        run_full_pipeline_task.apply_async(
            args=[
                job_id,
                str(media_dir),
                config.get("enabled_stage_keys"),
                config.get("profiles_by_name"),
                config.get("upload_mode"),
                config.get("space_depth_styles")
            ],
            task_id=job_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="No se pudo encolar la tarea")

    return {"jobId": job_id}

@app.get("/jobs/{job_id}")
def get_job_status_endpoint(job_id: str) -> Dict[str, Any]:
    data = job_store.get_status(job_id)
    if data is None:
        return {"jobId": job_id, "status": "pending", "message": "Job pending or not found"}
    return data

@app.get("/jobs/{job_id}/artifacts/{filename}")
def get_job_artifact(job_id: str, filename: str):
    data = job_store.get_artifact(job_id, filename)
    if not data: raise HTTPException(status_code=404, detail="Artifact not found")
    media_type = "application/octet-stream"
    if filename.endswith(".json"): media_type = "application/json"
    elif filename.endswith(".png"): media_type = "image/png"
    elif filename.endswith(".jpg"): media_type = "image/jpeg"
    return Response(content=data, media_type=media_type)

@app.get("/files/{job_id}/{path:path}")
def get_legacy_files(job_id: str, path: str):
    if path == "report.json": return get_job_artifact(job_id, "report.json")
    if path.startswith("S11_REPORT_GENERATION/") or path.endswith(".png") or path.endswith(".jpg"):
        return get_job_artifact(job_id, Path(path).name)
    raise HTTPException(status_code=404, detail="File not found")

@app.post("/cleanup-temp")
async def cleanup_temp_endpoint():
    dir_path = MEDIA_ROOT
    if dir_path.exists():
        for entry in dir_path.iterdir():
            if entry.is_dir(): shutil.rmtree(entry, ignore_errors=True)
            else:
                try: entry.unlink()
                except FileNotFoundError: pass
    return {"status": "ok"}

@app.get("/pipeline/stages")
def get_pipeline_stages_endpoint() -> list[dict[str, Any]]: return _build_pipeline_stages()

@app.get("/profiles/instruments")
def get_instrument_profiles_endpoint() -> List[Dict[str, Any]]:
    data = _load_profiles()
    inst = data.get("instrument_profiles", {}) or {}
    result = []
    for pid, cfg in inst.items():
        result.append({"id": pid, "family": cfg.get("family", ""), "label": pid.replace("_", " "), "notes": cfg.get("notes", "")})
    return result

@app.get("/profiles/styles")
def get_style_profiles_endpoint() -> List[Dict[str, Any]]:
    data = _load_profiles()
    styles = data.get("style_profiles", {}) or {}
    result = []
    for sid, cfg in styles.items():
        result.append({"id": sid, "label": sid.replace("_", " "), "has_reverb_profiles": bool(cfg.get("reverb_profile_by_bus"))})
    return result
