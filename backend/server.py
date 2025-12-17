from __future__ import annotations

import asyncio
import json
import hashlib
import hmac
import mimetypes
import logging
import os
import secrets
import shutil
import uuid
import time
import re
import zipfile
from collections import deque
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from typing import List, Dict, Optional, Any

import aiofiles
import numpy as np
import soundfile as sf
from sqlalchemy import text
try:
    import redis.asyncio as aioredis
except Exception:  # pragma: no cover - fallback si no existe redis.asyncio
    aioredis = None
from fastapi import (
    Body,
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse

from tasks import run_full_pipeline_task
from src.database import engine, Base
from src.routers import auth
from src.routers.auth import get_current_user
from src.models.user import User
from src.utils.job_store import update_job_status, write_job_status
from src.utils.waveform import compute_and_cache_peaks, ensure_preview_wav

# ---------------------------------------------------------
# Database
# ---------------------------------------------------------

def _init_db_schema() -> None:
    """
    Serializa la creacion de tablas para evitar carreras entre workers
    (Hypercorn lanza varios procesos) que terminan en duplicados de secuencias.
    """
    if engine.dialect.name == "postgresql":
        lock_id = 912345  # entero estable para pg_advisory_lock
        with engine.begin() as conn:
            conn.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": lock_id})
            try:
                Base.metadata.create_all(bind=conn)
            finally:
                conn.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": lock_id})
    else:
        Base.metadata.create_all(bind=engine)


_init_db_schema()

# ---------------------------------------------------------
# Logging
# ---------------------------------------------------------

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

logger = logging.getLogger("mix_master.server")

# ---------------------------------------------------------
# App & CORS
# ---------------------------------------------------------


def _load_allowed_origins() -> list[str]:
    raw = os.environ.get("CORS_ALLOW_ORIGINS", "")
    if raw:
        origins = [o.strip() for o in raw.split(",") if o.strip()]
        if origins:
            return origins
    # Fallback a dominios de produccion
    return [
        "https://music-mix-master.com",
        "https://api.music-mix-master.com",
    ]


app = FastAPI(title="Mix-Master API")

ALLOWED_CORS_ORIGINS = _load_allowed_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)


# ---------------------------------------------------------
# WAF middleware (simple pattern blocker)
# ---------------------------------------------------------

_WAF_REGEXES = [
    re.compile(r"(?i)union\s+select"),  # SQLi
    re.compile(r"(?i)sleep\(\d+\)"),  # time-based SQLi
    re.compile(r"(?i)or\s+1=1"),  # classic SQLi
    re.compile(r"\.\./"),  # path traversal
    re.compile(r"(?i)<script"),  # XSS tags
    re.compile(r"(?i)javascript:"),  # JS URIs
    re.compile(r"(?i)xss"),  # generic XSS token
    re.compile(r"(?i)etc/passwd"),  # path traversal / probing
]


def _is_malicious_payload(val: str) -> bool:
    for rx in _WAF_REGEXES:
        if rx.search(val):
            return True
    return False


@app.middleware("http")
async def waf_middleware(request: Request, call_next):
    """
    Bloquea solicitudes con patrones comunes de ataque (SQLi/XSS/traversal).
    """
    try:
        # Revisar path y query
        raw_parts = [request.url.path, request.url.query]

        # Revisar headers típicos donde pueden inyectar payloads
        for header_name in ("user-agent", "referer", "x-forwarded-for"):
            if header_name in request.headers:
                raw_parts.append(request.headers.get(header_name, ""))

        for raw in raw_parts:
            if raw and _is_malicious_payload(raw):
                logger.warning("WAF blocked request to %s due to pattern match", request.url)
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Request blocked by WAF"},
                )
    except Exception:
        # Si el WAF falla, no bloqueamos la petición pero registramos
        logger.exception("WAF middleware error processing request %s", request.url)

    return await call_next(request)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    """
    Captura excepciones no manejadas y evita filtrar trazas al cliente.
    """
    logger.exception("Unhandled exception en %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent  # .../backend
SRC_DIR = PROJECT_ROOT / "src"
CONTRACTS_PATH = SRC_DIR / "struct" / "contracts.json"
JOBS_ROOT = PROJECT_ROOT / "temp"
MEDIA_ROOT = PROJECT_ROOT / "media"

JOBS_ROOT.mkdir(parents=True, exist_ok=True)
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

# Auth & rate limiting
API_TOKEN = os.environ.get("MIXMASTER_API_TOKEN")
RATE_LIMIT_REQUESTS = int(os.environ.get("MIXMASTER_RATE_LIMIT_REQUESTS", "30"))
RATE_LIMIT_WINDOW_SECONDS = float(
    os.environ.get("MIXMASTER_RATE_LIMIT_WINDOW_SECONDS", "60")
)
RATE_LIMIT_REDIS_URL = os.environ.get(
    "RATE_LIMIT_REDIS_URL", os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
)
RATE_LIMIT_REDIS_PREFIX = os.environ.get("RATE_LIMIT_REDIS_PREFIX", "ratelimit:api:")

# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------


def _create_job_dirs() -> tuple[str, Path, Path]:
    """
    Crea directorios media/ y temp/ para un job nuevo.
    """
    job_id = uuid.uuid4().hex

    media_dir = MEDIA_ROOT / job_id
    temp_root = JOBS_ROOT / job_id

    media_dir.mkdir(parents=True, exist_ok=True)
    temp_root.mkdir(parents=True, exist_ok=True)

    logger.info(
        "[_create_job_dirs] job_id=%s media_dir=%s temp_root=%s",
        job_id,
        media_dir,
        temp_root,
    )
    return job_id, media_dir, temp_root


def _get_job_dirs(job_id: str) -> tuple[Path, Path]:
    """
    Dado un job_id existente, devuelve (media_dir, temp_root).
    No crea nada; solo calcula las rutas.
    """
    media_dir = MEDIA_ROOT / job_id
    temp_root = JOBS_ROOT / job_id
    return media_dir, temp_root


def _load_contracts() -> Dict[str, Any]:
    if not CONTRACTS_PATH.exists():
        raise RuntimeError(f"No se encuentra {CONTRACTS_PATH}")
    with CONTRACTS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _build_pipeline_stages() -> list[dict[str, Any]]:
    """
    Construye la definición de stages para el frontend a partir
    de struct/contracts.json.
    """
    contracts = _load_contracts()
    stages_cfg = contracts.get("stages", {}) or {}

    result: list[dict[str, Any]] = []
    idx = 0

    for stage_group_id, stage_group in stages_cfg.items():
        group_name = stage_group.get("name") or stage_group_id
        contracts_list = stage_group.get("contracts", []) or []

        for contract in contracts_list:
            contract_id = str(contract.get("id") or "").strip()
            if not contract_id:
                continue

            idx += 1
            preview_rel_path = f"/{contract_id}/full_song.wav"

            result.append(
                {
                    "key": contract_id,
                    "label": contract_id,
                    "description": group_name,
                    "index": idx,
                    "mediaSubdir": None,
                    "updatesCurrentDir": True,
                    "previewMixRelPath": preview_rel_path,
                }
            )

    logger.info(
        "[_build_pipeline_stages] Cargadas %d stages desde contracts.json",
        len(result),
    )

    return result


def _write_initial_job_status(job_id: str, temp_root: Path, owner_email: Optional[str] = None) -> None:
    """
    Crea un job_status.json inicial en estado 'pending'.
    """
    status = {
        "jobId": job_id,
        "job_id": job_id,
        "owner_email": owner_email,
        "status": "pending",
        "stage_index": 0,
        "total_stages": 0,
        "stage_key": "queued",
        "message": "Job pending in queue",
        "progress": 0.0,
    }
    write_job_status(temp_root, status)

    logger.info(
        "[_write_initial_job_status] job_status.json inicial escrito para job_id=%s",
        job_id,
    )


def _load_job_status_from_fs(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Lee temp/<job_id>/job_status.json si existe.
    """
    status_path = JOBS_ROOT / job_id / "job_status.json"
    if not status_path.exists():
        logger.info(
            "[_load_job_status_from_fs] No existe job_status.json para job_id=%s",
            job_id,
        )
        return None


def _assert_job_owner(job_id: str, current_user: User) -> Dict[str, Any]:
    """
    Valida que el job pertenezca al usuario actual. Si no hay owner, lo asigna.
    """
    data = _load_job_status_from_fs(job_id)
    job_root = JOBS_ROOT / job_id

    if data is None:
        # Si no existe estado, lo creamos con el propietario actual para permitir reintentos tras limpieza
        status = {
            "jobId": job_id,
            "job_id": job_id,
            "owner_email": current_user.email,
            "status": "pending",
            "stage_index": 0,
            "total_stages": 0,
            "stage_key": "queued",
            "message": "Job pending in queue",
            "progress": 0.0,
        }
        job_root.mkdir(parents=True, exist_ok=True)
        write_job_status(job_root, status)
        return status

    owner = data.get("owner_email")
    if owner and owner != current_user.email:
        raise HTTPException(status_code=403, detail="Job does not belong to current user")

    if not owner:
        # Asignar propietario y persistir
        data["owner_email"] = current_user.email
        try:
            write_job_status(job_root, data)
        except Exception:
            logger.warning("No se pudo persistir owner_email para job %s", job_id)

    return data
    try:
        with status_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data.setdefault("jobId", job_id)
            data.setdefault("job_id", job_id)
            return data
        logger.warning(
            "[_load_job_status_from_fs] job_status.json para job_id=%s no es un dict",
            job_id,
        )
        return None
    except Exception as exc:
        logger.warning(
            "No se pudo leer job_status.json para job_id=%s: %s",
            job_id,
            exc,
        )
        return None


PROFILES_PATH = SRC_DIR / "struct" / "profiles.json"


def _load_profiles() -> Dict[str, Any]:
    if not PROFILES_PATH.exists():
        raise RuntimeError(f"No se encuentra {PROFILES_PATH}")
    with PROFILES_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _parse_bool_flag(value: Optional[str]) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    v = str(value).strip().lower()
    return v in ("1", "true", "yes", "on")


# ---------------------------------------------------------
# Auth / rate limiting helpers
# ---------------------------------------------------------


class RedisRateLimiter:
    def __init__(self, redis_url: str, key_prefix: str, max_requests: int, window_seconds: float):
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self.max_requests = max_requests
        self.window_ms = int(window_seconds * 1000)
        if not aioredis:
            raise RuntimeError("redis.asyncio es obligatorio para rate limiting distribuido")
        self.client = aioredis.from_url(redis_url, decode_responses=False)

    async def hit(self, key: str) -> None:
        now_ms = int(time.time() * 1000)
        bucket_key = f"{self.key_prefix}{key}"
        member = f"{now_ms}-{uuid.uuid4().hex}"
        try:
            async with self.client.pipeline(transaction=True) as pipe:
                pipe.zremrangebyscore(bucket_key, 0, now_ms - self.window_ms)
                pipe.zadd(bucket_key, {member: now_ms})
                pipe.zcard(bucket_key)
                pipe.expire(bucket_key, int(RATE_LIMIT_WINDOW_SECONDS) + 10)
                _, _, count, _ = await pipe.execute()
            if count > self.max_requests:
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests, try again later",
                )
        except HTTPException:
            raise
        except Exception as exc:  # no fallback silencioso: observabilidad y bloqueo
            logger.error("Rate limiter Redis fallo; rechazando peticion para proteger el servicio: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="Rate limiting unavailable; try again later",
            )


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.hits: Dict[str, deque[float]] = {}
        self.lock = asyncio.Lock()

    async def hit(self, key: str) -> None:
        now = time.time()
        cutoff = now - self.window_seconds
        async with self.lock:
            bucket = self.hits.setdefault(key, deque())
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_requests:
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests, try again later",
                )
            bucket.append(now)


_memory_rate_limiter = SlidingWindowRateLimiter(
    max_requests=RATE_LIMIT_REQUESTS,
    window_seconds=RATE_LIMIT_WINDOW_SECONDS,
)

rate_limiter = RedisRateLimiter(
    redis_url=RATE_LIMIT_REDIS_URL,
    key_prefix=RATE_LIMIT_REDIS_PREFIX,
    max_requests=RATE_LIMIT_REQUESTS,
    window_seconds=RATE_LIMIT_WINDOW_SECONDS,
)


def _require_api_key(api_key: Optional[str]) -> None:
    if not API_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Servicio no configurado: falta MIXMASTER_API_TOKEN",
        )
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key invalida",
        )
    try:
        api_key_bytes = api_key.encode("utf-8")
        token_bytes = API_TOKEN.encode("utf-8")
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="API key invalida",
        )
    if not secrets.compare_digest(api_key_bytes, token_bytes):
        raise HTTPException(
            status_code=401,
            detail="API key invalida",
        )


def _extract_api_key(request: Request, header_api_key: Optional[str]) -> Optional[str]:
    if header_api_key:
        return header_api_key
    return request.query_params.get("api_key")


def _sign_download_path(path: str, exp_ts: int) -> str:
    msg = f"{path}|{exp_ts}".encode("utf-8")
    key = (API_TOKEN or "").encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def _sign_studio_token(job_id: str, exp_ts: int) -> str:
    """
    Token estable para Studio (HMAC job_id + exp_ts). Devuelve "exp.sig".
    """
    msg = f"{job_id}|{exp_ts}|studio".encode("utf-8")
    key = (API_TOKEN or "").encode("utf-8")
    sig = hmac.new(key, msg, hashlib.sha256).hexdigest()
    return f"{exp_ts}.{sig}"


def _verify_signed_download(path: str, sig: Optional[str], exp: Optional[str]) -> bool:
    if not API_TOKEN or not sig or not exp:
        return False
    try:
        exp_ts = int(exp)
    except (TypeError, ValueError):
        return False
    if exp_ts < int(time.time()):
        return False
    expected = _sign_download_path(path, exp_ts)
    try:
        return hmac.compare_digest(sig, expected)
    except Exception:
        return False


def _verify_studio_token(token: Optional[str], job_id: str) -> Optional[int]:
    """
    Devuelve exp_ts si token es válido para job_id, o None.
    """
    if not API_TOKEN or not token:
        return None
    try:
        exp_str, sig = token.split(".", 1)
        exp_ts = int(exp_str)
    except Exception:
        return None
    if exp_ts < int(time.time()):
        return None
    msg = f"{job_id}|{exp_ts}|studio".encode("utf-8")
    key = (API_TOKEN or "").encode("utf-8")
    expected = hmac.new(key, msg, hashlib.sha256).hexdigest()
    try:
        if hmac.compare_digest(sig, expected):
            return exp_ts
    except Exception:
        return None
    return None


def _get_effective_base_url(request: Request) -> str:
    """
    Devuelve base_url respetando X-Forwarded-Proto/Host para evitar http:// en proxys.
    """
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}".rstrip("/")


def _build_signed_url(request: Request, job_id: str, relative_path: str, expires_in: int = 900) -> str:
    """
    Construye una URL firmada para /files/{job_id}/<path>.

    Admite que `relative_path` venga ya con prefijo /files/<job_id>/ o incluso
    como URL absoluta; normalizamos para evitar duplicar el segmento /files/.
    Además descartamos query params anteriores (?exp=...&sig=...) antes de
    volver a firmar.
    """
    parsed = urlparse(str(relative_path or ""))
    path = parsed.path or ""

    clean_rel = path.lstrip("/")

    # Si ya viene con prefijo /files/<job_id>/..., lo retiramos para no
    # duplicarlo al construir rel_path.
    prefix_with_job = f"files/{job_id}/"
    if clean_rel.startswith(prefix_with_job):
        clean_rel = clean_rel[len(prefix_with_job) :]
    elif clean_rel.startswith("files/"):
        clean_rel = clean_rel[len("files/") :]
    elif clean_rel.startswith(f"{job_id}/"):
        clean_rel = clean_rel[len(f"{job_id}/") :]

    if not clean_rel:
        return ""
    exp_ts = int(time.time()) + expires_in
    rel_path = f"/files/{job_id}/{clean_rel}"
    sig = _sign_download_path(rel_path, exp_ts)
    base_url = _get_effective_base_url(request)
    return f"{base_url}{rel_path}?exp={exp_ts}&sig={sig}"


async def _guard_heavy_endpoint(
    request: Request, api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> None:
    # Si llega un Bearer token, asumimos que el endpoint validar‡ JWT v’a get_current_user;
    # en ese caso no exigimos API key aqu’ para no bloquear tras login.
    auth_header = request.headers.get("authorization", "")
    is_bearer = auth_header.lower().startswith("bearer ")

    key = _extract_api_key(request, api_key)
    if not is_bearer:
        _require_api_key(key)

    # No apliques rate limit al polling de estado (GET /jobs/{job_id})
    if request.method.upper() == "GET" and str(request.url.path).startswith("/jobs/"):
        return

    client_ip = request.client.host if request.client else "unknown"
    job_id = request.path_params.get("job_id") if isinstance(request.path_params, dict) else None
    token_hash = None
    if is_bearer:
        try:
            import hashlib
            token_hash = hashlib.sha256(auth_header.encode("utf-8")).hexdigest()[:16]
        except Exception:
            token_hash = None
    limiter_key_parts = [
        f"api:{key}" if key else None,
        f"ip:{client_ip}",
        f"job:{job_id}" if job_id else None,
        f"auth:{token_hash}" if token_hash else None,
        f"path:{request.url.path}",
    ]
    limiter_key = "|".join([p for p in limiter_key_parts if p])
    await rate_limiter.hit(limiter_key)


# ---------------------------------------------------------
# Upload helpers
# ---------------------------------------------------------

ALLOWED_UPLOAD_EXTENSIONS = {".wav"}
ALLOWED_UPLOAD_MIME_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/vnd.wave",
}
MAX_UPLOAD_SIZE_BYTES = 512 * 1024 * 1024  # 512 MiB
MAX_JOB_TOTAL_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB total por job
SIGNED_URL_STEMS_TTL = int(os.environ.get("STEMS_SIGNED_URL_TTL", str(6 * 3600)))
SIGNED_URL_STEMS_TTL = max(600, min(SIGNED_URL_STEMS_TTL, 24 * 3600))
STEM_PEAKS_DESIRED_BARS = 800


def _sanitize_filename(filename: str) -> str:
    """
    Limpia el nombre recibido del cliente para evitar path traversal y
    caracteres raros. Solo conserva [A-Za-z0-9._-]; el resto -> "_".
    """
    base_name = Path(filename or "").name  # elimina rutas tipo ../../
    cleaned = "".join(
        ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in base_name
    ).strip("._")
    if not cleaned:
        cleaned = f"upload_{uuid.uuid4().hex}"
    return cleaned[:255]


def _ensure_dest_inside(base_dir: Path, dest_path: Path) -> None:
    """
    Verifica que dest_path esta dentro de base_dir (sin traversal).
    """
    try:
        dest_path.resolve().relative_to(base_dir.resolve())
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Nombre de archivo no permitido",
        )


def _validate_upload(upload: UploadFile, safe_name: str) -> None:
    ext = Path(safe_name).suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Solo se permiten archivos WAV (.wav)",
        )
    content_type = (upload.content_type or "").lower()
    if content_type and content_type not in ALLOWED_UPLOAD_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo MIME no permitido ({content_type}); usa audio/wav",
        )


def _prepare_upload_destination(base_dir: Path, upload: UploadFile) -> tuple[Path, str]:
    """
    Devuelve (dest_path, safe_name) listo para escribir en base_dir.
    """
    safe_name = _sanitize_filename(upload.filename or "")
    _validate_upload(upload, safe_name)
    dest_path = base_dir / safe_name
    _ensure_dest_inside(base_dir, dest_path)
    if dest_path.exists():
        raise HTTPException(
            status_code=400,
            detail="Ya existe un archivo con ese nombre en este job",
        )
    return dest_path, safe_name


def _is_wav_magic(chunk: bytes) -> bool:
    """
    Valida la cabecera RIFF/WAVE de un WAV. Espera al menos 12 bytes.
    """
    return len(chunk) >= 12 and chunk.startswith(b"RIFF") and chunk[8:12] == b"WAVE"


def _get_media_dir_size(media_dir: Path) -> int:
    total = 0
    if media_dir.exists():
        for entry in media_dir.iterdir():
            try:
                if entry.is_file():
                    total += entry.stat().st_size
            except FileNotFoundError:
                continue
    return total


async def _stream_upload_file(
    upload: UploadFile,
    dest_path: Path,
    *,
    max_total_bytes: Optional[int] = None,
    already_written: int = 0,
) -> int:
    """
    Copia el UploadFile a dest_path validando el tamano maximo.
    """
    chunk_size = 1024 * 1024  # 1 MiB
    bytes_written = 0
    first_chunk = True
    try:
        async with aiofiles.open(dest_path, "wb") as out:
            while True:
                chunk = await upload.read(chunk_size)
                if not chunk:
                    break
                if first_chunk:
                    if not _is_wav_magic(chunk):
                        raise HTTPException(
                            status_code=400,
                            detail="Archivo no parece WAV (cabecera RIFF/WAVE invalida)",
                        )
                    first_chunk = False
                new_size = bytes_written + len(chunk)
                overall_size = already_written + new_size
                if new_size > MAX_UPLOAD_SIZE_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            f"Archivo demasiado grande "
                            f"(limite {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MiB)"
                        ),
                    )
                if max_total_bytes is not None and overall_size > max_total_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            "Límite total de subida del job excedido "
                            f"({max_total_bytes // (1024 * 1024 * 1024)} GiB)"
                        ),
                    )
                await out.write(chunk)
                bytes_written = new_size
    except Exception:
        try:
            dest_path.unlink()
        except FileNotFoundError:
            pass
        raise
    return bytes_written


def _stream_file_response(
    request: Request,
    target_path: Path,
    media_type: Optional[str],
    cache_seconds: int,
    extra_headers: Optional[Dict[str, str]] = None,
):
    """
    Devuelve FileResponse o StreamingResponse con soporte Range (206).
    """
    headers = {
        "Accept-Ranges": "bytes",
        **(extra_headers or {}),
    }
    if cache_seconds > 0:
        headers["Cache-Control"] = f"public, max-age={cache_seconds}"

    range_header = request.headers.get("range")
    file_size = target_path.stat().st_size

    if not range_header or not range_header.startswith("bytes=") or file_size == 0:
        return FileResponse(target_path, media_type=media_type, headers=headers)

    match = re.match(r"bytes=(\d*)-(\d*)", range_header)
    if not match:
        return FileResponse(target_path, media_type=media_type, headers=headers)

    start_str, end_str = match.groups()
    try:
        if start_str:
            start = int(start_str)
            end = int(end_str) if end_str else file_size - 1
        else:
            # sufijo: bytes=-N
            suffix = int(end_str) if end_str else 0
            start = max(file_size - suffix, 0)
            end = file_size - 1
    except ValueError:
        raise HTTPException(status_code=416, detail="Invalid Range header")

    if start < 0 or end < start or start >= file_size:
        raise HTTPException(status_code=416, detail="Requested range not satisfiable")

    end = min(end, file_size - 1)
    chunk_size = end - start + 1

    def file_iterator(path: Path, offset: int, length: int):
        with path.open("rb") as f:
            f.seek(offset)
            remaining = length
            while remaining > 0:
                data = f.read(min(64 * 1024, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    headers.update(
        {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(chunk_size),
        }
    )

    return StreamingResponse(
        file_iterator(target_path, start, chunk_size),
        status_code=206,
        media_type=media_type,
        headers=headers,
    )


# ---------------------------------------------------------
# Endpoints
# ---------------------------------------------------------


def _collect_stem_paths(stage_dir: Path) -> List[Path]:
    """
    Devuelve la lista de rutas .wav (excluyendo full_song.wav) en un stage.
    """
    wavs: List[Path] = []
    if not stage_dir.exists():
        return wavs
    for item in stage_dir.iterdir():
        if (
            item.is_file()
            and item.suffix.lower() == ".wav"
            and item.name.lower() != "full_song.wav"
        ):
            wavs.append(item)
    return sorted(wavs)




@app.post("/mix")
async def mix_tracks(
    files: List[UploadFile] = File(...),
    stages_json: Optional[str] = Form(None),
    stem_profiles_json: Optional[str] = Form(None),
    space_depth_bus_styles_json: Optional[str] = Form(None),
    upload_mode: str = Form("song"),
    _: None = Depends(_guard_heavy_endpoint),
    current_user: User = Depends(get_current_user),
):
    """
    Endpoint clásico: un solo POST con todos los WAV.
    Lo usamos sobre todo cuando solo hay 1 fichero.
    """
    request_start_ts = time.time()
    request_start_iso = datetime.utcnow().isoformat()

    logger.info(
        "[/mix] HTTP request recibido a %s (UTC). n_files=%d upload_mode=%s",
        request_start_iso,
        len(files),
        upload_mode,
    )

    job_id, media_dir, temp_root = _create_job_dirs()
    logger.info(
        "[/mix] Nuevo job de mezcla creado. job_id=%s media_dir=%s temp_root=%s",
        job_id,
        media_dir,
        temp_root,
    )

    _write_initial_job_status(job_id, temp_root, owner_email=current_user.email)

    job_root = temp_root
    work_dir = job_root / "work"
    work_dir.mkdir(parents=True, exist_ok=True)

    # Perfiles de stems
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
            logger.info(
                "[/mix] Perfiles de stems parseados para job_id=%s: %d entradas",
                job_id,
                len(raw_profiles),
            )
        except Exception as exc:
            logger.warning(
                "[/mix] No se pudo parsear stem_profiles_json=%r: %s",
                stem_profiles_json,
                exc,
            )

    # Space/depth styles
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
                logger.info(
                    "[/mix] space_depth_bus_styles.json escrito para job_id=%s",
                    job_id,
                )
        except Exception as exc:
            logger.warning(
                "[/mix] No se pudo parsear space_depth_bus_styles_json=%r: %s",
                space_depth_bus_styles_json,
                exc,
            )

    # Guardar los ficheros (usando aiofiles y streaming para evitar bloqueo)
    total_uploaded = 0
    for f in files:
        dest_path, safe_name = _prepare_upload_destination(media_dir, f)
        bytes_written = await _stream_upload_file(
            f,
            dest_path,
            max_total_bytes=MAX_JOB_TOTAL_BYTES,
            already_written=total_uploaded,
        )
        total_uploaded += bytes_written

        logger.info(
            "[/mix] Archivo subido guardado para job_id=%s -> %s (%d bytes)",
            job_id,
            dest_path,
            bytes_written,
        )

    if raw_profiles:
        profiles_path = job_root / "work" / "stem_profiles.json"
        profiles_path.parent.mkdir(parents=True, exist_ok=True)
        profiles_path.write_text(
            json.dumps(raw_profiles, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(
            "[/mix] stem_profiles.json escrito para job_id=%s con %d perfiles",
            job_id,
            len(raw_profiles),
        )

    # Stages habilitadas
    enabled_stage_keys: Optional[List[str]] = None
    if stages_json:
        try:
            parsed = json.loads(stages_json)
            if isinstance(parsed, list):
                enabled_stage_keys = [str(k) for k in parsed]
            logger.info(
                "[/mix] stages_json parseado para job_id=%s: %d stages habilitadas",
                job_id,
                len(enabled_stage_keys or []),
            )
        except Exception as exc:
            logger.warning(
                "[/mix] No se pudo parsear stages_json=%r: %s",
                stages_json,
                exc,
            )
    else:
        logger.info(
            "[/mix] No se recibió stages_json; se usarán las stages por defecto para job_id=%s",
            job_id,
        )

    # Encolar tarea Celery
    pre_enqueue_ts = time.time()
    logger.info(
        "[/mix] Preparación completada para job_id=%s en %.3fs. Encolando tarea Celery...",
        job_id,
        pre_enqueue_ts - request_start_ts,
    )

    try:
        result = run_full_pipeline_task.apply_async(
            args=[
                job_id,
                str(media_dir),
                str(temp_root),
                enabled_stage_keys,
                profiles_by_name,
            ]
        )
        task_id = getattr(result, "id", None)
        if task_id:
            update_job_status(temp_root, {"celery_task_id": task_id})
    except Exception as exc:
        logger.exception(
            "[/mix] Error en apply_async para job_id=%s",
            job_id,
        )
        raise HTTPException(
            status_code=500,
            detail="No se pudo encolar la tarea de mezcla",
        ) from exc

    after_enqueue_ts = time.time()
    logger.info(
        "[/mix] Celery: tarea encolada job_id=%s celery_id=%s state=%s. Latencia total desde HTTP=%.3fs",
        job_id,
        result.id,
        result.state,
        after_enqueue_ts - request_start_ts,
    )

    return {"jobId": job_id}


# ---------------------------------------------------------
# Flujo multi-step (subidas paralelas, sin compresión)
# ---------------------------------------------------------


@app.post("/mix/init")
async def init_mix_job(
    stages_json: Optional[str] = Form(None),
    stem_profiles_json: Optional[str] = Form(None),
    space_depth_bus_styles_json: Optional[str] = Form(None),
    upload_mode: str = Form("song"),
    _: None = Depends(_guard_heavy_endpoint),
    current_user: User = Depends(get_current_user),
):
    """
    Inicializa un job SIN subir todavía los WAV.
    1) /mix/init
    2) /mix/{job_id}/upload-file  (paralelo)
    3) /mix/{job_id}/start
    """
    request_start_ts = time.time()
    request_start_iso = datetime.utcnow().isoformat()

    logger.info(
        "[/mix/init] HTTP request recibido a %s (UTC). upload_mode=%s",
        request_start_iso,
        upload_mode,
    )

    job_id, media_dir, temp_root = _create_job_dirs()
    logger.info(
        "[/mix/init] Nuevo job creado. job_id=%s media_dir=%s temp_root=%s",
        job_id,
        media_dir,
        temp_root,
    )

    _write_initial_job_status(job_id, temp_root, owner_email=current_user.email)

    job_root = temp_root
    work_dir = job_root / "work"
    work_dir.mkdir(parents=True, exist_ok=True)


    # Perfiles de stems
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
                        raw_profiles.append({"name": name, "profile": profile})
            logger.info(
                "[/mix/init] Perfiles de stems parseados para job_id=%s: %d entradas",
                job_id,
                len(raw_profiles),
            )
        except Exception as exc:
            logger.warning(
                "[/mix/init] No se pudo parsear stem_profiles_json=%r: %s",
                stem_profiles_json,
                exc,
            )

    if raw_profiles:
        profiles_path = work_dir / "stem_profiles.json"
        profiles_path.write_text(
            json.dumps(raw_profiles, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(
            "[/mix/init] stem_profiles.json escrito para job_id=%s con %d perfiles",
            job_id,
            len(raw_profiles),
        )

    # Space/depth styles
    if space_depth_bus_styles_json:
        try:
            parsed = json.loads(space_depth_bus_styles_json)
            if isinstance(parsed, dict):
                sd_path = work_dir / "space_depth_bus_styles.json"
                sd_path.write_text(
                    json.dumps(parsed, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                logger.info(
                    "[/mix/init] space_depth_bus_styles.json escrito para job_id=%s",
                    job_id,
                )
        except Exception as exc:
            logger.warning(
                "[/mix/init] No se pudo parsear space_depth_bus_styles_json=%r: %s",
                space_depth_bus_styles_json,
                exc,
            )

    # Stages habilitadas
    enabled_stage_keys: Optional[List[str]] = None
    if stages_json:
        try:
            parsed = json.loads(stages_json)
            if isinstance(parsed, list):
                enabled_stage_keys = [str(k) for k in parsed]
            logger.info(
                "[/mix/init] stages_json parseado para job_id=%s: %d stages habilitadas",
                job_id,
                len(enabled_stage_keys or []),
            )
        except Exception as exc:
            logger.warning(
                "[/mix/init] No se pudo parsear stages_json=%r: %s",
                stages_json,
                exc,
            )
    else:
        logger.info(
            "[/mix/init] No se recibió stages_json; se usarán las stages por defecto para job_id=%s",
            job_id,
        )

    if enabled_stage_keys is not None:
        enabled_path = work_dir / "enabled_stages.json"
        enabled_path.write_text(
            json.dumps(enabled_stage_keys, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(
            "[/mix/init] enabled_stages.json escrito para job_id=%s con %d entradas",
            job_id,
            len(enabled_stage_keys),
        )

    elapsed = time.time() - request_start_ts
    logger.info(
        "[/mix/init] Preparación completada para job_id=%s en %.3fs. Esperando uploads.",
        job_id,
        elapsed,
    )

    return {"jobId": job_id}


@app.post("/mix/{job_id}/upload-file")
async def upload_file_for_job(
    job_id: str,
    file: UploadFile = File(...),
    _: None = Depends(_guard_heavy_endpoint),
    current_user: User = Depends(get_current_user),
):
    """
    Recibe un archivo para un job existente.
    SIN compresión. Copia en streaming usando aiofiles para no bloquear el loop.
    """
    # Validar propietario y asegurar que las carpetas existen
    data = _assert_job_owner(job_id, current_user)
    media_dir, temp_root = _get_job_dirs(job_id)
    temp_root.mkdir(parents=True, exist_ok=True)
    media_dir.mkdir(parents=True, exist_ok=True)

    # Si job_status existía pero el fs se limpió, reescribir estado mínimo para evitar 404 posteriores
    if data and isinstance(data, dict):
        try:
            write_job_status(temp_root, data)
        except Exception:
            logger.warning("No se pudo reescribir job_status para job %s tras recrear carpetas", job_id)

    dest_path, safe_name = _prepare_upload_destination(media_dir, file)
    existing_total = _get_media_dir_size(media_dir)
    bytes_written = await _stream_upload_file(
        file,
        dest_path,
        max_total_bytes=MAX_JOB_TOTAL_BYTES,
        already_written=existing_total,
    )

    logger.info(
        "[/mix/%s/upload-file] Archivo subido -> %s (%d bytes) (async streaming)",
        job_id,
        dest_path,
        bytes_written,
    )

    return {"ok": True, "filename": safe_name, "bytes": bytes_written}


@app.post("/mix/{job_id}/start")
async def start_mix_job_endpoint(
    job_id: str,
    stages_override: Optional[Dict[str, List[str]]] = None,
    _: None = Depends(_guard_heavy_endpoint),
    current_user: User = Depends(get_current_user),
):
    """
    Lanza la tarea Celery para un job ya inicializado y con WAVs subidos.
    Allows passing 'stages' list in body to override enabled_stages.
    """
    request_start_ts = time.time()

    data = _assert_job_owner(job_id, current_user)
    media_dir, temp_root = _get_job_dirs(job_id)
    media_dir.mkdir(parents=True, exist_ok=True)
    temp_root.mkdir(parents=True, exist_ok=True)
    if data and isinstance(data, dict):
        try:
            write_job_status(temp_root, data)
        except Exception:
            logger.warning("No se pudo reescribir job_status para job %s tras recrear carpetas", job_id)

    job_root = temp_root
    work_dir = job_root / "work"

    # Stages habilitadas
    enabled_stage_keys: Optional[List[str]] = None

    # Check if we have an override in the body
    if stages_override and "stages" in stages_override and isinstance(stages_override["stages"], list):
        enabled_stage_keys = stages_override["stages"]
        logger.info(
            "[/mix/%s/start] Usando override de stages desde body: %s",
            job_id,
            enabled_stage_keys
        )
    else:
        # Fallback to enabled_stages.json
        enabled_path = work_dir / "enabled_stages.json"
        if enabled_path.exists():
            try:
                parsed = json.loads(enabled_path.read_text(encoding="utf-8"))
                if isinstance(parsed, list):
                    enabled_stage_keys = [str(k) for k in parsed]
                logger.info(
                    "[/mix/%s/start] enabled_stages.json cargado con %d entradas",
                    job_id,
                    len(enabled_stage_keys or []),
                )
            except Exception as exc:
                logger.warning(
                    "[/mix/%s/start] No se pudo leer enabled_stages.json: %s",
                    job_id,
                    exc,
                )

    # Perfiles de stems
    profiles_by_name: Dict[str, str] = {}
    stem_profiles_path = work_dir / "stem_profiles.json"
    if stem_profiles_path.exists():
        try:
            raw_profiles = json.loads(
                stem_profiles_path.read_text(encoding="utf-8")
            )
            if isinstance(raw_profiles, list):
                for item in raw_profiles:
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get("name") or "").strip()
                    profile = str(item.get("profile") or "").strip() or "auto"
                    if name:
                        profiles_by_name[name] = profile
            logger.info(
                "[/mix/%s/start] stem_profiles.json cargado con %d perfiles",
                job_id,
                len(profiles_by_name),
            )
        except Exception as exc:
            logger.warning(
                "[/mix/%s/start] No se pudo leer stem_profiles.json: %s",
                job_id,
                exc,
            )

    # Force immediate status update to avoid race condition with frontend polling
    # fetching old "waiting_for_correction" status before Celery worker starts.
    update_job_status(job_root, {
        "status": "queued",
        "message": "Job queued for processing...",
        "stage_key": "queued",
    })

    # Encolar tarea Celery
    try:
        result = run_full_pipeline_task.apply_async(
            args=[
                job_id,
                str(media_dir),
                str(temp_root),
                enabled_stage_keys,
                profiles_by_name,
            ]
        )
        task_id = getattr(result, "id", None)
        if task_id:
            update_job_status(temp_root, {"celery_task_id": task_id})
    except Exception as exc:
        logger.exception(
            "[/mix/%s/start] Error en apply_async",
            job_id,
        )
        raise HTTPException(
            status_code=500,
            detail="No se pudo encolar la tarea de mezcla",
        ) from exc

    after_enqueue_ts = time.time()
    logger.info(
        "[/mix/%s/start] Celery: tarea encolada celery_id=%s state=%s. Latencia total desde HTTP=%.3fs",
        job_id,
        result.id,
        result.state,
        after_enqueue_ts - request_start_ts,
    )

    return {"jobId": job_id}


@app.get("/jobs/{job_id}/stems")
def get_job_stems(
    job_id: str,
    request: Request,
    _: None = Depends(_guard_heavy_endpoint),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Devuelve stems con URL firmada + preview + peaks, priorizando S6_MANUAL_CORRECTION.
    """
    _, temp_root = _get_job_dirs(job_id)
    if not temp_root.exists():
        raise HTTPException(status_code=404, detail="Job not found")

    _assert_job_owner(job_id, current_user)

    preferred_stage_ids = [
        "S6_MANUAL_CORRECTION",
        "S6_MANUAL_CORRECTION_ADJUSTMENT",
        "S5_LEADVOX_DYNAMICS",
        "S5_STEM_DYNAMICS_GENERIC",
        "S4_STEM_RESONANCE_CONTROL",
        "S0_SESSION_FORMAT",
        "S0_MIX_ORIGINAL",
    ]

    selected_stage: Optional[Path] = None
    stem_paths: List[Path] = []

    for stage_id in preferred_stage_ids:
        candidate = temp_root / stage_id
        stem_paths = _collect_stem_paths(candidate)
        if stem_paths:
            selected_stage = candidate
            break

    if not selected_stage:
        # Fallback: busca cualquier stage con stems wav
        for stage_dir in sorted(temp_root.iterdir()):
            if not stage_dir.is_dir():
                continue
            stem_paths = _collect_stem_paths(stage_dir)
            if stem_paths:
                selected_stage = stage_dir
                break

    if not selected_stage or not stem_paths:
        raise HTTPException(status_code=404, detail="No stems found")

    payload: List[Dict[str, Any]] = []

    for stem_path in stem_paths:
        rel_path = f"{selected_stage.name}/{stem_path.name}"
        signed_url = _build_signed_url(
            request, job_id, rel_path, expires_in=SIGNED_URL_STEMS_TTL
        )

        peaks_path = selected_stage / "peaks" / f"{stem_path.stem}.peaks.json"
        peaks = compute_and_cache_peaks(stem_path, peaks_path)

        preview_url = None
        preview_rel = f"{selected_stage.name}/previews/{stem_path.stem}_preview.wav"
        preview_path = selected_stage / "previews" / f"{stem_path.stem}_preview.wav"
        if ensure_preview_wav(stem_path, preview_path):
            preview_url = _build_signed_url(
                request, job_id, preview_rel, expires_in=SIGNED_URL_STEMS_TTL
            )

        payload.append(
            {
                "file": stem_path.name,
                "stage": selected_stage.name,
                "url": signed_url,
                "preview_url": preview_url,
                "peaks": peaks,
            }
        )

    return {
        "stage": selected_stage.name,
        "count": len(payload),
        "stems": payload,
    }

@app.get("/jobs/{job_id}/download-stems-zip")
async def download_stems_zip(
    job_id: str,
    _: None = Depends(_guard_heavy_endpoint),
    current_user: User = Depends(get_current_user),
):
    """
    Zips current stems and returns file.
    """
    _, temp_root = _get_job_dirs(job_id)
    if not temp_root.exists():
        raise HTTPException(status_code=404, detail="Job not found")

    _assert_job_owner(job_id, current_user)

    # Reuse logic to find best stems
    def _get_best_stage_dir() -> Optional[Path]:
        preferred_order = [
            temp_root / "S11_REPORT_GENERATION",
            temp_root / "S10_MASTER_FINAL_LIMITS",
            temp_root / "S6_MANUAL_CORRECTION",
            temp_root / "S0_SESSION_FORMAT",
            temp_root / "S0_MIX_ORIGINAL",
        ]
        for stage_dir in preferred_order:
            if stage_dir.exists() and any(f.suffix == '.wav' and f.name != 'full_song.wav' for f in stage_dir.iterdir()):
                return stage_dir
        return None

    stage_dir = _get_best_stage_dir()
    if not stage_dir:
        raise HTTPException(status_code=404, detail="No stems found to zip")

    zip_filename = f"{job_id}_stems.zip"
    zip_path = temp_root / zip_filename

    # Create zip if not exists or return existing? Better recreate to ensure freshness if resumed.
    # Note: blocking IO in async def, but zip can be heavy. Should run in threadpool.
    from fastapi.concurrency import run_in_threadpool

    def _create_zip():
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for item in stage_dir.iterdir():
                if item.is_file() and item.suffix.lower() == ".wav" and item.name.lower() != "full_song.wav":
                    zf.write(item, arcname=item.name)

    await run_in_threadpool(_create_zip)

    return FileResponse(zip_path, filename=zip_filename, media_type='application/zip')

@app.get("/jobs/{job_id}/download-mixdown")
async def download_mixdown_endpoint(
    job_id: str,
    _: None = Depends(_guard_heavy_endpoint),
    current_user: User = Depends(get_current_user),
):
    """
    Runs mixdown_stems and downloads the result.
    """
    _, temp_root = _get_job_dirs(job_id)
    if not temp_root.exists():
        raise HTTPException(status_code=404, detail="Job not found")

    _assert_job_owner(job_id, current_user)

    # Determine best stage to mixdown
    best_stage_dir = None
    preferred_order = [
        temp_root / "S11_REPORT_GENERATION",
        temp_root / "S10_MASTER_FINAL_LIMITS",
        temp_root / "S6_MANUAL_CORRECTION",
        temp_root / "S5_LEADVOX_DYNAMICS",
        temp_root / "S0_SESSION_FORMAT",
    ]
    for d in preferred_order:
        if d.exists() and any(f.suffix == '.wav' for f in d.iterdir()):
            best_stage_dir = d
            break

    if not best_stage_dir:
        raise HTTPException(status_code=404, detail="No audio to mixdown")

    # Run mixdown script on this folder
    # We call mixdown_stems.py

    from src.utils import mixdown_stems
    # We need a context
    from src.context import PipelineContext
    # Mock context or real?
    # Mixdown stems uses context.get_stage_dir() mainly or arguments.
    # It seems to take context and use `context.get_stage_dir(stage_id)`.
    # Wait, mixdown_stems.process(context) uses context.audio_stems if available, or loads from disk?

    # Let's inspect mixdown_stems.py usage in stage.py: `_run_script(mixdown_script, context, stage_id)`
    # This implies it uses sys.argv if not process()?
    # stage.py tries process(context) first.

    # We can create a context for this stage.
    stage_id = best_stage_dir.name
    context = PipelineContext(stage_id=stage_id, job_id=job_id, temp_root=temp_root)

    # Run in threadpool
    from fastapi.concurrency import run_in_threadpool

    def _run_mixdown():
        try:
            # We might need to ensure stems are loaded into context if mixdown relies on it,
            # or if mixdown reads from disk.
            # Assuming mixdown reads from disk if context.audio_stems is empty.
            # Let's import mixdown_stems directly.
            import src.utils.mixdown_stems as md
            md.process(context)
        except Exception as e:
            logger.error(f"Mixdown failed: {e}")
            raise HTTPException(status_code=500, detail=f"Mixdown failed: {e}")

    await run_in_threadpool(_run_mixdown)

    full_song = best_stage_dir / "full_song.wav"
    if not full_song.exists():
        raise HTTPException(status_code=500, detail="Mixdown failed to generate file")

    return FileResponse(full_song, filename=f"{job_id}_mixdown.wav", media_type="audio/wav")


@app.post("/jobs/{job_id}/correction")
async def post_job_correction(
    job_id: str,
    payload: Dict[str, Any],
    _: None = Depends(_guard_heavy_endpoint),
    current_user: User = Depends(get_current_user),
):
    """
    Recibe parametros de correccion manual y los guarda en work/manual_corrections.json
    para que el pipeline (S6) los consuma al reanudarse.
    """
    _, temp_root = _get_job_dirs(job_id)
    if not temp_root.exists():
        raise HTTPException(status_code=404, detail="Job not found")

    _assert_job_owner(job_id, current_user)

    corrections = payload.get("corrections")
    # Allow empty list (no corrections)
    if corrections is None or not isinstance(corrections, list):
        raise HTTPException(status_code=400, detail="corrections list required")

    work_dir = temp_root / "work"
    work_dir.mkdir(parents=True, exist_ok=True)

    # Guardar manual_corrections.json
    corrections_path = work_dir / "manual_corrections.json"
    try:
        # Wrap in "corrections" key to match S6 expectations
        data = {"corrections": corrections}
        corrections_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    except Exception as e:
        logger.error(f"Error escribiendo manual_corrections.json: {e}")
        raise HTTPException(status_code=500, detail="Failed to save corrections")

    return {"status": "saved", "message": "Corrections saved. Call /start to resume pipeline."}


@app.get("/jobs/{job_id}")
def get_job_status(
    job_id: str,
    request: Request,
    response: Response,
    _: None = Depends(_guard_heavy_endpoint),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    data = _assert_job_owner(job_id, current_user)
    if data is None:
        logger.info(
            "[/jobs/%s] job_status.json no encontrado; devolviendo estado pending.",
            job_id,
        )
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
    logger.info(
        "[/jobs/%s] Estado leído de job_status.json: status=%s stage_index=%s/%s",
        job_id,
        data.get("status"),
        data.get("stage_index"),
        data.get("total_stages"),
    )

    # Firmar URLs de media si están presentes
    rel_full = data.get("full_song_url") or data.get("fullSongUrl")
    if isinstance(rel_full, str) and rel_full:
        data["full_song_url"] = _build_signed_url(request, job_id, rel_full)
    rel_orig = data.get("original_full_song_url") or data.get("originalFullSongUrl")
    if isinstance(rel_orig, str) and rel_orig:
        data["original_full_song_url"] = _build_signed_url(request, job_id, rel_orig)

    return data


@app.post("/cleanup-temp")
async def cleanup_temp(_: None = Depends(_guard_heavy_endpoint)):
    """
    Limpia el contenido de temp/ y media/ (no borra los directorios raíz).
    """
    for sub in ("temp", "media"):
        dir_path = PROJECT_ROOT / sub
        try:
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
                logger.info(
                    "[/cleanup-temp] Directorio %s no existía; creado.",
                    dir_path,
                )
                continue

            for entry in dir_path.iterdir():
                full_path = dir_path / entry.name
                if full_path.is_dir():
                    shutil.rmtree(full_path, ignore_errors=True)
                else:
                    try:
                        full_path.unlink()
                    except FileNotFoundError:
                        pass
            logger.info(
                "[/cleanup-temp] Limpiado contenido de %s",
                dir_path,
            )
        except Exception as e:
            logger.error(
                "Error limpiando %s: %s",
                dir_path,
                e,
            )

    return {"status": "ok"}


@app.get("/files/{job_id}/{file_path:path}")
async def get_job_file(
    job_id: str,
    file_path: str,
    request: Request,
):
    """
    Devuelve un fichero de temp/<job_id> protegido por API key.
    """
    # Permitir api_key por header/query, enlace firmado (?sig=...&exp=...) o token estable (?t=...).
    sig = request.query_params.get("sig")
    exp = request.query_params.get("exp")
    token = request.query_params.get("t")
    rel_path = f"/files/{job_id}/{file_path}"
    token_exp = _verify_studio_token(token, job_id)
    signed_ok = _verify_signed_download(rel_path, sig, exp)
    if not (token_exp or signed_ok):
        key = _extract_api_key(request, request.headers.get("X-API-Key"))
        _require_api_key(key)

    _, temp_root = _get_job_dirs(job_id)
    if not temp_root.exists():
        raise HTTPException(status_code=404, detail="Job not found")

    target_path = (temp_root / file_path).resolve()
    _ensure_dest_inside(temp_root, target_path)
    if not target_path.exists() or not target_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    media_type, _ = mimetypes.guess_type(target_path.name)
    headers = {"Cross-Origin-Resource-Policy": "cross-origin"}
    cache_seconds = 7 * 24 * 3600 if token_exp else (3600 if signed_ok else 300)

    return _stream_file_response(
        request,
        target_path,
        media_type,
        cache_seconds=cache_seconds,
        extra_headers=headers,
    )


@app.post("/jobs/{job_id}/studio-token")
async def create_studio_token(
    job_id: str,
    request: Request,
    payload: Optional[Dict[str, Any]] = Body(None),
    api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """
    Devuelve un token estable (t) para Studio, con TTL largo para cachear WAVs.
    """
    req_api_key = _extract_api_key(request, api_key)
    _require_api_key(req_api_key)

    ttl_days = 7
    if payload and isinstance(payload, dict):
        try:
            ttl_days = int(payload.get("ttl_days", ttl_days))
        except Exception:
            ttl_days = 7
    ttl_days = max(1, min(ttl_days, 30))
    exp_ts = int(time.time()) + ttl_days * 24 * 3600
    token = _sign_studio_token(job_id, exp_ts)
    return {"token": token, "expires": exp_ts}


@app.post("/files/{job_id}/sign")
async def sign_job_file(
    job_id: str,
    payload: Dict[str, Any],
    request: Request,
    _: None = Depends(_guard_heavy_endpoint),
):
    """
    Devuelve una URL firmada temporalmente para un fichero de temp/<job_id>.
    """
    raw_path = str(payload.get("filePath") or payload.get("file_path") or "").strip()
    file_path = raw_path.lstrip("/")
    prefix = f"{job_id}/"
    if file_path.startswith(prefix):
        file_path = file_path[len(prefix) :]
    if not file_path:
        raise HTTPException(status_code=400, detail="file_path requerido")
    expires_in = int(payload.get("expires_in") or 600)
    expires_in = max(60, min(expires_in, 3600))

    _, temp_root = _get_job_dirs(job_id)
    target_path = (temp_root / file_path).resolve()
    _ensure_dest_inside(temp_root, target_path)

    # [MODIFIED] No verificamos existencia del archivo para permitir firmar
    # URLs de archivos que se están generando o que fallaron pero queremos intentar descargar.
    # if not target_path.exists() or not target_path.is_file():
    #     raise HTTPException(status_code=404, detail="File not found")

    exp_ts = int(time.time()) + expires_in
    rel_path = f"/files/{job_id}/{file_path}"
    sig = _sign_download_path(rel_path, exp_ts)
    base_url = _get_effective_base_url(request)
    signed_url = f"{base_url}{rel_path}?exp={exp_ts}&sig={sig}"

    return {"url": signed_url, "expires": exp_ts}


@app.post("/files/sign")
async def sign_job_file_generic(
    payload: Dict[str, Any],
    request: Request,
    _: None = Depends(_guard_heavy_endpoint),
):
    """
    Variante genérica: body {jobId, filePath, expires_in?}
    """
    job_id = str(payload.get("jobId") or payload.get("job_id") or "").strip()
    file_path = str(payload.get("filePath") or payload.get("file_path") or "").strip()
    if not job_id or not file_path:
        raise HTTPException(status_code=400, detail="jobId y filePath requeridos")
    # reutiliza la lógica del endpoint específico
    return await sign_job_file(job_id, payload, request, None)


@app.get("/pipeline/stages")
def get_pipeline_stages() -> list[dict[str, Any]]:
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
