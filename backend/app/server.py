# /app/server.py
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Literal, Optional, Dict
import threading
import logging
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi import BackgroundTasks, HTTPException

from src.pipeline import run_full_pipeline

logger = logging.getLogger(__name__)

JobStatusType = Literal["queued", "running", "done", "error"]

PROJECT_ROOT = Path(__file__).resolve().parent
JOBS_ROOT = PROJECT_ROOT / "temp_jobs"
JOBS_ROOT.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Mix & Master API")

origins = [
    "http://localhost:3000",
    "https://frontend-vrev.onrender.com",
]

# CORS para que NextJS pueda llamar sin problemas
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@dataclass
class JobState:
    status: JobStatusType
    stage_index: int
    total_stages: int
    stage_key: str
    message: str
    progress: float  # 0.0–100.0
    error_message: Optional[str] = None
    result: Optional[dict] = None  # aquí guardaremos fullSongUrl + metrics

JOBS: Dict[str, JobState] = {}
JOBS_LOCK = threading.Lock()


# Servir ficheros de audio generados (downloads)
app.mount("/files", StaticFiles(directory=str(JOBS_ROOT)), name="files")


@app.get("/jobs/{job_id}/tree")
def get_job_tree(job_id: str):
    """
    Devuelve el árbol de directorios y ficheros para un job concreto.
    Útil para debug: verlo en /docs o en el navegador.
    """
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


def _create_job_dirs() -> tuple[str, Path, Path]:
    job_id = str(uuid4())
    job_root = JOBS_ROOT / job_id
    media_dir = job_root / "media"
    temp_root = job_root / "work"

    media_dir.mkdir(parents=True, exist_ok=True)
    temp_root.mkdir(parents=True, exist_ok=True)

    return job_id, media_dir, temp_root



def _run_pipeline_job(job_id: str, media_dir: Path, temp_root: Path) -> None:
    def progress_cb(stage_index: int, total_stages: int, stage_key: str, message: str) -> None:
        progress = (stage_index / max(total_stages, 1)) * 100.0
        with JOBS_LOCK:
            st = JOBS.get(job_id)
            if not st:
                st = JobState(
                    status="running",
                    stage_index=stage_index,
                    total_stages=total_stages,
                    stage_key=stage_key,
                    message=message,
                    progress=progress,
                )
                JOBS[job_id] = st
            else:
                st.status = "running"
                st.stage_index = stage_index
                st.total_stages = total_stages
                st.stage_key = stage_key
                st.message = message
                st.progress = progress

    try:
        logger.info("Job %s: starting pipeline", job_id)
        result = run_full_pipeline(
            project_root=PROJECT_ROOT,
            media_dir=media_dir,
            temp_root=temp_root,
            progress_callback=progress_cb,
        )

        # Construir URL al WAV final (como ya tenías)
        relative_path = result.full_song_path.relative_to(JOBS_ROOT)
        full_song_url = f"/files/{relative_path.as_posix()}"

        orig_rel = result.original_full_song_path.relative_to(JOBS_ROOT)
        original_full_song_url = f"/files/{orig_rel.as_posix()}"

        metrics_dict = asdict(result.metrics)

        job_result = {
            "jobId": job_id,
            "originalFullSongUrl": original_full_song_url,
            "fullSongUrl": full_song_url,
            "metrics": metrics_dict,
        }

        with JOBS_LOCK:
            st = JOBS.get(job_id)
            if not st:
                st = JobState(
                    status="done",
                    stage_index=result.metrics and 7 or 0,
                    total_stages=7,
                    stage_key="done",
                    message="Job completed",
                    progress=100.0,
                    result=job_result,
                )
                JOBS[job_id] = st
            else:
                st.status = "done"
                st.stage_index = st.total_stages
                st.stage_key = "done"
                st.message = "Job completed"
                st.progress = 100.0
                st.result = job_result

        logger.info("Job %s: completed successfully", job_id)

    except Exception as exc:
        logger.exception("Job %s failed: %s", job_id, exc)
        with JOBS_LOCK:
            st = JOBS.get(job_id)
            if not st:
                st = JobState(
                    status="error",
                    stage_index=0,
                    total_stages=7,
                    stage_key="error",
                    message="Job failed",
                    progress=0.0,
                    error_message=str(exc),
                )
                JOBS[job_id] = st
            else:
                st.status = "error"
                st.stage_key = "error"
                st.message = "Job failed"
                st.error_message = str(exc)



@app.get("/jobs/{job_id}/status")
def get_job_status(job_id: str):
    with JOBS_LOCK:
        st = JOBS.get(job_id)

    if not st:
        raise HTTPException(status_code=404, detail="Job not found")

    payload = {
        "jobId": job_id,
        "status": st.status,
        "stageIndex": st.stage_index,
        "totalStages": st.total_stages,
        "stageKey": st.stage_key,
        "message": st.message,
        "progress": st.progress,
    }

    if st.status == "done" and st.result:
        payload["result"] = st.result
    if st.error_message:
        payload["error"] = st.error_message

    return payload


@app.post("/mix")
async def mix_tracks(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
):
    """
    Endpoint principal de mezcla/master.
    - Recibe stems como multipart/form-data (list[UploadFile]).
    - Ejecuta run_full_pipeline.
    - Devuelve métricas + URL del wav final.
    """
    job_id, media_dir, temp_root = _create_job_dirs()

    # Guardar stems en disco para que el pipeline los use
    for f in files:
        dest_path = media_dir / f.filename
        with dest_path.open("wb") as out:
            out.write(await f.read())

    # Estado inicial del job
    with JOBS_LOCK:
        JOBS[job_id] = JobState(
            status="queued",
            stage_index=0,
            total_stages=7,
            stage_key="queued",
            message="Job queued",
            progress=0.0,
        )


    # Lanzar el pipeline en background
    background_tasks.add_task(_run_pipeline_job, job_id, media_dir, temp_root)

    # Devolvemos sólo el jobId
    return {"jobId": job_id}
