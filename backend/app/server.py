# /app/server.py
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.pipeline import run_full_pipeline

PROJECT_ROOT = Path(__file__).resolve().parent
JOBS_ROOT = PROJECT_ROOT / "temp_jobs"
JOBS_ROOT.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Mix & Master API")

# CORS para que NextJS pueda llamar sin problemas
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # en producción, pon tu dominio
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir ficheros de audio generados (downloads)
app.mount("/files", StaticFiles(directory=str(JOBS_ROOT)), name="files")


def _create_job_dirs() -> tuple[str, Path, Path]:
    job_id = str(uuid4())
    job_root = JOBS_ROOT / job_id
    media_dir = job_root / "media"
    temp_root = job_root / "work"

    media_dir.mkdir(parents=True, exist_ok=True)
    temp_root.mkdir(parents=True, exist_ok=True)

    return job_id, media_dir, temp_root


@app.post("/mix")
async def mix_tracks(
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

    # Ejecutar el pipeline
    result = run_full_pipeline(
        project_root=PROJECT_ROOT,
        media_dir=media_dir,
        temp_root=temp_root,
        # export_csv=False,  # si añades el parámetro
    )

    # Construir URL pública relativa (la servirá StaticFiles)
    full_song_rel = result.full_song_path.name  # p.ej. "full_song.wav"
    full_song_url = f"/files/{job_id}/work/{full_song_rel}"

    # Convertir dataclasses a dict
    metrics_dict = asdict(result.metrics)

    return {
        "jobId": job_id,
        "fullSongUrl": full_song_url,
        "metrics": metrics_dict,
    }
