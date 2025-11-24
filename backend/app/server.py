from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from celery import states
from celery.result import AsyncResult
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from celery_app import celery_app
from tasks import run_full_pipeline_task

from src.pipeline import get_pipeline_stages_definition

logger = logging.getLogger(__name__)

# Raíz del proyecto dentro del contenedor (/app)
PROJECT_ROOT = Path(__file__).resolve().parent

# Carpeta donde se guardan todos los trabajos (compartida entre web y worker)
JOBS_ROOT = PROJECT_ROOT / "temp"
JOBS_ROOT.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Mix & Master API")

origins = [
    "http://localhost:3000",
    "http://161.97.131.133:3000",
]

# CORS para que NextJS pueda llamar sin problemas
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir ficheros de audio generados (downloads). Apunta a JOBS_ROOT.
app.mount("/files", StaticFiles(directory=str(JOBS_ROOT)), name="files")


def _create_job_dirs() -> tuple[str, Path, Path]:
    """Crea la estructura de carpetas para un nuevo job y devuelve (job_id, media_dir, temp_root)."""
    job_id = str(uuid4())
    job_root = JOBS_ROOT / job_id
    media_dir = job_root / "media"
    temp_root = job_root / "work"

    media_dir.mkdir(parents=True, exist_ok=True)
    temp_root.mkdir(parents=True, exist_ok=True)

    return job_id, media_dir, temp_root


@app.get("/jobs/{job_id}/tree")
def get_job_tree(job_id: str):
    """Devuelve el árbol de directorios y ficheros para un job concreto (debug)."""
    job_root = JOBS_ROOT / job_id
    if not job_root.exists():
        raise HTTPException(status_code=404, detail="Job not found")

    def build_tree(path: Path):
        children = []
        for p in sorted(path.iterdir()):
            if p.is_dir():
                children.append(
                    {
                        "type": "dir",
                        "name": p.name,
                        "children": build_tree(p),
                    }
                )
            else:
                children.append(
                    {
                        "type": "file",
                        "name": p.name,
                        "size": p.stat().st_size,
                    }
                )
        return children

    return {
        "jobId": job_id,
        "root": str(job_root.relative_to(JOBS_ROOT)),
        "tree": build_tree(job_root),
    }


@app.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    """Devuelve el estado del job consultando a Celery (Redis)."""
    async_result = AsyncResult(job_id, app=celery_app)

    # PENDING = Celery aún no lo ha tocado (puede estar en cola)
    if async_result.state == states.PENDING:
        return {
            "jobId": job_id,
            "status": "pending",
            "message": "Job pending in queue",
        }

    # PROGRESS = estado custom que hemos puesto en update_state en la tarea
    if async_result.state == "PROGRESS":
        meta = async_result.info or {}
        return {
            "jobId": job_id,
            "status": "running",
            **meta,
        }

    # SUCCESS = job terminado
    if async_result.state == states.SUCCESS:
        result = async_result.result or {}
        return {
            "jobId": job_id,
            "status": "finished",
            **result,
        }

    # FAILURE = job que ha fallado
    if async_result.state == states.FAILURE:
        return {
            "jobId": job_id,
            "status": "failed",
            "error": str(async_result.info),
        }

    # Otros estados posibles: RETRY, STARTED...
    return {
        "jobId": job_id,
        "status": async_result.state.lower(),
    }


@app.get("/pipeline/stages")
def get_pipeline_stages():
    """
    Devuelve la definición del pipeline (orden de stages, etiquetas, etc.)
    tal y como está configurada en src.pipeline.STAGES.
    El frontend puede usar esto para pintar el panel "Pipeline" de forma dinámica.
    """
    return get_pipeline_stages_definition()


@app.post("/mix")
async def mix_tracks(files: list[UploadFile] = File(...)):
    """Endpoint principal de mezcla/master (stems como multipart/form-data)."""
    job_id, media_dir, temp_root = _create_job_dirs()

    # Guardar stems en disco para que el pipeline (en el worker) los use
    for f in files:
        dest_path = media_dir / f.filename
        with dest_path.open("wb") as out:
            out.write(await f.read())

    # Lanzar la tarea Celery. task_id=job_id para poder consultar luego el estado.
    run_full_pipeline_task.apply_async(
        args=[job_id, str(media_dir), str(temp_root)],
        task_id=job_id,
    )

    # Devolvemos solo el jobId; el cliente consultará /jobs/{job_id}
    return {"jobId": job_id}


@app.post("/jobs")
async def create_job(file: UploadFile = File(...)):
    """Variante simple que recibe un único fichero en lugar de varios stems."""
    job_id, media_dir, temp_root = _create_job_dirs()

    dest_path = media_dir / file.filename
    with dest_path.open("wb") as out:
        out.write(await file.read())

    run_full_pipeline_task.apply_async(
        args=[job_id, str(media_dir), str(temp_root)],
        task_id=job_id,
    )

    return {"jobId": job_id}
