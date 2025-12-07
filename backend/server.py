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
from fastapi import HTTPException

from tasks import run_full_pipeline_task

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Mix-Master API")

# CORS (ajusta origins a tu frontend según necesites)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://161.97.131.133:3000"],
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
    previewMixRelPath -> ruta relativa al job_root donde está el full_song
                         de ese contrato: "/<CONTRACT_ID>/full_song.wav"
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

            # Asumimos que para cada contrato existe un bounce en:
            #   temp/<job_id>/<CONTRACT_ID>/full_song.wav
            # y lo exponemos como:
            #   /files/<job_id>/<CONTRACT_ID>/full_song.wav
            preview_rel_path = f"/{contract_id}/full_song.wav"

            result.append(
                {
                    "key": contract_id,        # lo que el frontend enviará como enabledStageKeys
                    "label": contract_id,      # puedes refinarlo si quieres algo más bonito
                    "description": group_name, # nombre del bloque (Technical Preparation, etc.)
                    "index": idx,              # orden global
                    "mediaSubdir": None,
                    "updatesCurrentDir": True,
                    "previewMixRelPath": preview_rel_path,
                }
            )

    return result


def _write_initial_job_status(job_id: str, temp_root: Path) -> None:
    """
    Crea un job_status.json inicial en estado 'pending', para que el frontend
    pueda mostrar la cola incluso antes de que arranque el worker.
    """
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
    status_path = temp_root / "job_status.json"
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(
        json.dumps(status, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _load_job_status_from_fs(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Lee temp/<job_id>/job_status.json si existe.
    """
    status_path = JOBS_ROOT / job_id / "job_status.json"
    if not status_path.exists():
        return None
    try:
        with status_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data.setdefault("jobId", job_id)
            data.setdefault("job_id", job_id)
            return data
        return None
    except Exception as exc:
        logger.warning(
            "No se pudo leer job_status.json para job_id=%s: %s", job_id, exc
        )
        return None


PROFILES_PATH = SRC_DIR / "struct" / "profiles.json"


def _load_profiles() -> Dict[str, Any]:
    if not PROFILES_PATH.exists():
        raise RuntimeError(f"No se encuentra {PROFILES_PATH}")
    with PROFILES_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _parse_bool_flag(value: Optional[str]) -> bool:
    """
    Convierte un string de formulario ('true', 'false', '1', '0', etc.)
    a bool. Si viene None, devuelve False.
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    v = str(value).strip().lower()
    return v in ("1", "true", "yes", "on")


# -------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------


@app.post("/mix")
async def mix_tracks(
    files: List[UploadFile] = File(...),
    stages_json: Optional[str] = Form(None),
    stem_profiles_json: Optional[str] = Form(None),
    space_depth_bus_styles_json: Optional[str] = Form(None),
    upload_mode: str = Form("song"),  # <-- NUEVO: "song" o "stems"
):
    job_id, media_dir, temp_root = _create_job_dirs()
    logger.info(
        "Nuevo job de mezcla: job_id=%s, n_files=%d, upload_mode=%s",
        job_id,
        len(files),
        upload_mode,
    )

    # -----------------------------
    # 1) job_status inicial (pending)
    # -----------------------------
    _write_initial_job_status(job_id, temp_root)

    # -----------------------------
    # 1b) Persistir modo de subida (song/stems) para S0_SEPARATE_STEMS
    # -----------------------------
    raw_mode = (upload_mode or "song").strip().lower()
    is_stems_upload = raw_mode in {"stems", "upload_stems", "stems_true", "true", "1"}

    normalized_mode = "stems" if is_stems_upload else "song"

    job_root = temp_root
    work_dir = job_root / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    upload_info_path = work_dir / "upload_mode.json"

    upload_info = {
        "upload_mode": normalized_mode,
        "stems": is_stems_upload,
    }
    upload_info_path.write_text(
        json.dumps(upload_info, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # -----------------------------
    # 2) Parsear perfiles de stems
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
    # 3) Guardar los stems en disco
    # -----------------------------
    for f in files:
        dest_path = media_dir / f.filename
        with dest_path.open("wb") as out:
            out.write(await f.read())

    # Persistir mapping a disco (para stages posteriores, depuración, etc.)
    if raw_profiles:
        profiles_path = job_root / "work" / "stem_profiles.json"
        profiles_path.parent.mkdir(parents=True, exist_ok=True)
        profiles_path.write_text(
            json.dumps(raw_profiles, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # -----------------------------
    # 4) Parsear stages_json (lista de contract_id habilitados)
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
    # 5) Lanzar tarea Celery
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
def get_job_status(job_id: str) -> Dict[str, Any]:
    """
    Devuelve el estado del job para el frontend, LEYÉNDOLO DE DISCO
    (temp/<job_id>/job_status.json), que es lo que va actualizando el worker.
    """
    data = _load_job_status_from_fs(job_id)
    if data is None:
        # Si no hay fichero, devolvemos un "pending" neutro
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
    return data


@app.post("/cleanup-temp")
async def cleanup_temp():
    """
    Limpia el contenido de temp/ y media/, pero sin borrar los directorios raíz.
    Es compatible con root filesystem read-only + volúmenes en /app/temp y /app/media.
    """
    for sub in ("temp", "media"):
        dir_path = PROJECT_ROOT / sub
        try:
            # Si no existe, la creamos (en tu caso, el volumen montado en /app/temp / /app/media)
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
                continue

            # Si existe, limpiamos SOLO el contenido
            for entry in dir_path.iterdir():
                full_path = dir_path / entry.name
                if full_path.is_dir():
                    shutil.rmtree(full_path, ignore_errors=True)
                else:
                    try:
                        full_path.unlink()
                    except FileNotFoundError:
                        pass
        except Exception as e:
            # Log, pero NO rompemos el endpoint
            logger.error(f"Error limpiando {dir_path}: {e}")

    return {"status": "ok"}


@app.get("/pipeline/stages")
def get_pipeline_stages() -> list[dict[str, Any]]:
    """
    Devuelve la definición de etapas del pipeline en términos de contract_id,
    para que el frontend pueda habilitar/deshabilitar contracts concretos.
    """
    return _build_pipeline_stages()


@app.get("/profiles/instruments")
def get_instrument_profiles() -> List[Dict[str, Any]]:
    data = _load_profiles()
    inst = data.get("instrument_profiles", {}) or {}
    result: List[Dict[str, Any]] = []
    for pid, cfg in inst.items():
        result.append(
            {
                "id": pid,
                "family": cfg.get("family", ""),
                "label": pid.replace("_", " "),
                "notes": cfg.get("notes", ""),
            }
        )
    return result


@app.get("/profiles/styles")
def get_style_profiles() -> List[Dict[str, Any]]:
    data = _load_profiles()
    styles = data.get("style_profiles", {}) or {}
    result: List[Dict[str, Any]] = []
    for sid, cfg in styles.items():
        result.append(
            {
                "id": sid,
                "label": sid.replace("_", " "),
                "has_reverb_profiles": bool(cfg.get("reverb_profile_by_bus")),
            }
        )
    return result
