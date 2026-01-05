from __future__ import annotations

import json
import shutil
import logging
from pathlib import Path
from typing import Callable, Dict, Any, List, Optional

import numpy as np
import soundfile as sf

from .utils import mixdown_stems, copy_stems
from .stages.stage import run_stage, set_active_contract_sequence
from .utils.analysis_utils import get_temp_dir
from .context import PipelineContext
from .utils.job_store import update_job_status
from .utils.logger import logger as pipeline_logger
from .utils.waveform import compute_and_cache_peaks, ensure_preview_wav

logger = logging.getLogger(__name__)

def _mark_job_failure(temp_root: Optional[Path], message: str, job_id: Optional[str] = None) -> None:
    """
    Actualiza job_status a failure con un mensaje claro si hay temp_root disponible.
    """
    if job_id:
        logger.error("[%s] %s", job_id, message)
    else:
        logger.error("%s", message)

    if temp_root:
        try:
            update_job_status(
                temp_root,
                {
                    "status": "failure",
                    "stage_key": "error",
                    "message": message,
                },
            )
        except Exception as exc:
            logger.warning("No se pudo actualizar job_status tras fallo: %s", exc)


def _run_processing_step(
    description: str,
    func: Callable[..., bool],
    *,
    context: PipelineContext,
    args: List[Any],
    job_id: Optional[str] = None,
    temp_root: Optional[Path] = None,
) -> None:
    """
    Ejecuta una funcion de etapa (process) y marca el job como fallo si devuelve False o lanza.
    """
    try:
        res = func(context, *args)
        if res is False:
            raise RuntimeError("returned False")
    except Exception as exc:
        msg = f"{description} fallo: {exc}"
        _mark_job_failure(temp_root, msg, job_id)
        raise


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
    temp_root = get_temp_dir(src_stage, create=True).parent
    job_id = temp_root.name if temp_root else None
    context = PipelineContext(stage_id=src_stage, job_id=job_id, temp_root=temp_root)

    # 1) Copiar stems src -> dst
    _run_processing_step(
        f"Copiar stems {src_stage} -> {dst_stage}",
        copy_stems.process,
        context=context,
        args=[src_stage, dst_stage],
        job_id=job_id,
        temp_root=temp_root,
    )

    # 2) Mixdown de los stems en la carpeta origen
    _run_processing_step(
        f"Mixdown de {src_stage}",
        mixdown_stems.process,
        context=context,
        args=[src_stage],
        job_id=job_id,
        temp_root=temp_root,
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

        audio_exts = {".wav", ".aif", ".aiff", ".flac", ".mp3", ".m4a", ".ogg", ".aac"}
        stem_files = [
            p.name
            for p in stage_dir.iterdir()
            if p.is_file()
            and p.suffix.lower() in audio_exts
            and p.name.lower() != "full_song.wav"
        ]
        stems = []
        for name in sorted(stem_files):
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


def _normalize_channels_to_stereo(data: np.ndarray) -> np.ndarray:
    if data.ndim == 1:
        return np.stack((data, data), axis=1)

    if data.ndim == 2:
        channels = data.shape[1]
        if channels == 2:
            return data
        if channels == 1:
            return np.repeat(data, 2, axis=1)
        mono = data.mean(axis=1, dtype=np.float32)
        return np.stack((mono, mono), axis=1)

    return data


CONVERTIBLE_INPUT_EXTS = {".aif", ".aiff", ".mp3"}


def _load_audio_for_conversion(path: Path) -> tuple[np.ndarray, int]:
    """
    Read audio with soundfile; fallback to librosa for formats like MP3/AIFF.
    Returns float32 audio with shape (samples, channels).
    """
    try:
        data, sr = sf.read(path, always_2d=True)
        return data.astype(np.float32, copy=False), int(sr)
    except Exception:
        try:
            import librosa  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on runtime env
            raise RuntimeError(
                f"No se pudo leer {path.name}; falta backend para MP3/AIFF: {exc}"
            ) from exc

        data, sr = librosa.load(path, sr=None, mono=False)
        if data.ndim == 1:
            data = data.reshape(-1, 1)
        else:
            data = data.T
        return data.astype(np.float32, copy=False), int(sr)


def _unique_wav_path(path: Path) -> Path:
    base = path.with_suffix(".wav")
    if not base.exists():
        return base
    stem = path.stem
    for i in range(1, 1000):
        candidate = path.with_name(f"{stem}_{i}.wav")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"No se pudo encontrar nombre libre para {path.name}")


def _convert_to_wav(path: Path) -> Path:
    data, sr = _load_audio_for_conversion(path)
    wav_path = _unique_wav_path(path)
    sf.write(wav_path, data, sr, subtype="FLOAT")
    return wav_path


def _update_session_config_paths(stage_dir: Path, converted: Dict[str, str]) -> None:
    if not converted:
        return
    cfg_path = stage_dir / "session_config.json"
    if not cfg_path.exists():
        return
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return

    stems = cfg.get("stems", [])
    updated = False
    for stem in stems:
        if not isinstance(stem, dict):
            continue
        fname = stem.get("file_name")
        if fname in converted:
            stem["file_name"] = converted[fname]
            updated = True

    if updated:
        cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def _convert_inputs_to_wav(stage_dir: Path) -> Dict[str, str]:
    converted: Dict[str, str] = {}
    if not stage_dir.exists():
        return converted

    for src in stage_dir.iterdir():
        if not src.is_file():
            continue
        if src.name.lower() == "full_song.wav":
            continue
        if src.suffix.lower() not in CONVERTIBLE_INPUT_EXTS:
            continue
        try:
            wav_path = _convert_to_wav(src)
            converted[src.name] = wav_path.name
            try:
                src.unlink()
            except Exception as exc:
                logger.warning("[pipeline] No se pudo borrar %s: %s", src.name, exc)
            logger.info("[pipeline] Convertido %s -> %s", src.name, wav_path.name)
        except Exception as exc:
            logger.error("[pipeline] Error convirtiendo %s a WAV: %s", src.name, exc)
            raise

    if converted:
        _update_session_config_paths(stage_dir, converted)

    return converted


def _normalize_wav_channels_in_dir(stage_dir: Path) -> None:
    if not stage_dir.exists():
        return

    for wav_path in stage_dir.glob("*.wav"):
        if wav_path.name.lower() == "full_song.wav":
            continue
        try:
            info = sf.info(wav_path)
            if info.channels == 2:
                continue
            data, sr = sf.read(wav_path, dtype="float32", always_2d=True)
            normalized = _normalize_channels_to_stereo(data)
            if normalized.shape == data.shape:
                continue
            subtype = info.subtype or None
            sf.write(wav_path, normalized, sr, subtype=subtype)
            logger.info("[pipeline] Normalized channels to stereo for %s", wav_path.name)
        except Exception as exc:
            logger.warning("[pipeline] No se pudo normalizar canales en %s: %s", wav_path.name, exc)


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
    resume_stage_index_offset: int = 0,
    resume_total_stages: Optional[int] = None,
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
    logger.info(
        "[pipeline] run_pipeline_for_job: job_id=%s media_dir=%s temp_root=%s enabled_stage_keys=%s",
        job_id,
        media_dir,
        temp_root,
        enabled_stage_keys,
    )

    def _emit_progress(stage_index: int, total_stages: int, stage_key: str, message: str) -> None:
        status = {
            "jobId": job_id,
            "job_id": job_id,
            "status": "running",
            "stage_index": stage_index,
            "total_stages": total_stages,
            "stage_key": stage_key,
            "message": message,
            "progress": float(stage_index) / float(total_stages) * 100.0 if total_stages > 0 else 0.0,
        }
        try:
            update_job_status(temp_root, status)
        except Exception as exc:
            logger.warning("[%s] No se pudo actualizar job_status: %s", job_id, exc)
        if progress_cb is not None:
            progress_cb(stage_index, total_stages, stage_key, message)

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

    # Copiar stems desde media_dir a S0_MIX_ORIGINAL (admite formatos de entrada)
    audio_exts = {".wav", ".aif", ".aiff", ".flac", ".mp3", ".m4a", ".ogg", ".aac"}
    copied = 0
    if media_dir.exists():
        for src in media_dir.iterdir():
            if not src.is_file():
                continue
            if src.suffix.lower() not in audio_exts:
                continue
            dst = s0_original_dir / src.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src, dst)
            except FileNotFoundError:
                # Copia sin metadatos como fallback robusto si el FS no soporta copystat
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(src, dst)
            logger.info("[pipeline] Copiado stem %s -> %s", src.name, dst)
            copied += 1
    else:
        logger.warning(
            "[pipeline] media_dir %s no existe al reanudar; intentando usar stems previos del job.",
            media_dir,
        )

    # Si no hemos copiado nada desde media_dir (p.ej. reanudaciИn tras Studio
    # o el directorio de subidas fue limpiado), intentamos sembrar S0 usando
    # la mejor carpeta previa del job para evitar FileNotFound.
    if copied == 0:
        fallback_dirs = [
            temp_root / "S6_MANUAL_CORRECTION",
            temp_root / "S0_SESSION_FORMAT",
        ]
        for fb_dir in fallback_dirs:
            if not fb_dir.exists():
                continue
            candidates = [
                p for p in fb_dir.iterdir()
                if p.is_file() and p.suffix.lower() in audio_exts and p.name.lower() != "full_song.wav"
            ]
            if not candidates:
                continue
            for src in candidates:
                dst = s0_original_dir / src.name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                copied += 1
            # Copiar session_config si existe para mantener perfiles
            cfg = fb_dir / "session_config.json"
            if cfg.exists():
                shutil.copy2(cfg, s0_original_dir / "session_config.json")
            logger.info("[pipeline] Sembrado S0_MIX_ORIGINAL desde %s (%d archivos).", fb_dir, copied)
            break

    if copied == 0:
        raise FileNotFoundError("No se encontraron stems en media_dir ni en carpetas previas para iniciar el pipeline.")

    # Persistir session_config con los perfiles seleccionados
    _write_session_config(s0_original_dir, profiles_by_name)

    # Convertir MP3/AIFF a WAV antes del mixdown original.
    _convert_inputs_to_wav(s0_original_dir)

    # Normalize channels to stereo before original mixdown.
    _normalize_wav_channels_in_dir(s0_original_dir)

    # ------------------------------------------------------------------
    # 1) Mixdown de S0_MIX_ORIGINAL (full_song.wav original)
    # ------------------------------------------------------------------
    logger.info("[pipeline] Mixdown de S0_MIX_ORIGINAL...")
    context = PipelineContext(stage_id="S0_MIX_ORIGINAL", job_id=job_id, temp_root=temp_root)
    _run_processing_step(
        "Mixdown de S0_MIX_ORIGINAL",
        mixdown_stems.process,
        context=context,
        args=["S0_MIX_ORIGINAL"],
        job_id=job_id,
        temp_root=temp_root,
    )

    # ------------------------------------------------------------------
    # 2) Copiar stems a S0_SESSION_FORMAT
    # ------------------------------------------------------------------
    logger.info("[pipeline] Copiando stems S0_MIX_ORIGINAL -> S0_SESSION_FORMAT...")
    _run_processing_step(
        "Copiar stems S0_MIX_ORIGINAL -> S0_SESSION_FORMAT",
        copy_stems.process,
        context=context,
        args=["S0_MIX_ORIGINAL", "S0_SESSION_FORMAT"],
        job_id=job_id,
        temp_root=temp_root,
    )

    # Generar peaks para S0_SESSION_FORMAT, así si el usuario abre Studio antes de S6, ya están listos.
    s0_format_dir = get_temp_dir("S0_SESSION_FORMAT", create=False)
    if s0_format_dir.exists():
        logger.info("[pipeline] Pre-calculating peaks for S0_SESSION_FORMAT...")
        for stem_path in s0_format_dir.glob("*.wav"):
            if stem_path.name.lower() == "full_song.wav":
                continue
            peaks_path = s0_format_dir / "peaks" / f"{stem_path.stem}.peaks.json"
            preview_path = s0_format_dir / "previews" / f"{stem_path.stem}_preview.wav"
            compute_and_cache_peaks(stem_path, peaks_path)
            ensure_preview_wav(stem_path, preview_path)

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
    # Calcular el índice final al que llegaremos
    final_stage_index = resume_stage_index_offset + total_stages

    # Usar el total previo si existe, o el calculado
    effective_total_stages = resume_total_stages or final_stage_index

    # Corrección de seguridad: si el total efectivo es menor que el índice final,
    # lo ampliamos para evitar porcentajes > 100%.
    if effective_total_stages < final_stage_index:
        effective_total_stages = final_stage_index

    if effective_total_stages == 0:
        effective_total_stages = total_stages

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

    # Si la primera stage no es S0_SESSION_FORMAT (ej. empezamos en S7),
    # debemos copiar manualmente los datos de S0_SESSION_FORMAT a esa primera stage
    # para "arrancar" la cadena.
    if contract_ids and contract_ids[0] != "S0_SESSION_FORMAT":
        first_stage = contract_ids[0]
        first_stage_dir = get_temp_dir(first_stage, create=True)

        # Si ya hay stems en la carpeta destino (p.ej. del pipeline previo),
        # no los sobreescribimos para poder reanudar donde se quedo el Mix Tool.
        has_existing_audio = any(
            p.suffix.lower() == ".wav" and p.name.lower() != "full_song.wav"
            for p in first_stage_dir.glob("*")
        )

        if has_existing_audio:
            logger.info(
                "[pipeline] Detectados stems previos en %s; se omite copia inicial.",
                first_stage_dir,
            )
        else:
            # Intentamos arrancar desde el contrato anterior si existe salida
            source_stage = "S0_SESSION_FORMAT"
            try:
                idx_first = all_contract_ids.index(first_stage)
                if idx_first > 0:
                    prev_stage = all_contract_ids[idx_first - 1]
                    prev_dir = get_temp_dir(prev_stage, create=False)
                    prev_has_audio = prev_dir.exists() and any(
                        p.suffix.lower() == ".wav" and p.name.lower() != "full_song.wav"
                        for p in prev_dir.glob("*")
                    )
                    if prev_has_audio:
                        source_stage = prev_stage
            except ValueError:
                # first_stage no esta en contracts; usamos fallback S0
                pass

            logger.info(
                "[pipeline] Stage inicial es %s (no S0). Copiando %s -> %s...",
                first_stage,
                source_stage,
                first_stage,
            )
            bootstrap_context = PipelineContext(stage_id=source_stage, job_id=job_id, temp_root=temp_root)
            _run_processing_step(
                f"Copia inicial {source_stage} -> {first_stage}",
                copy_stems.process,
                context=bootstrap_context,
                args=[source_stage, first_stage],
                job_id=job_id,
                temp_root=temp_root,
            )

    # Callback inicial de progreso (antes de cualquier stage)
    _emit_progress(
        resume_stage_index_offset,
        effective_total_stages,
        "initializing",
        "Inicializando pipeline de mezcla...",
    )

    # Configurar logging a archivo para este job
    log_file = temp_root / "pipeline.log"
    file_handler = pipeline_logger.add_file_handler(str(log_file))
    logger.addHandler(file_handler)

    try:
        # ------------------------------------------------------------------
        # 4) Ejecutar cada contrato en orden
        # ------------------------------------------------------------------
        # Crear contexto único para todo el job
        context = PipelineContext(
            stage_id="", # Se actualizará en cada iteración
            job_id=job_id,
            temp_root=temp_root
        )

        for idx, contract_id in enumerate(contract_ids, start=1):
            current_stage_index = resume_stage_index_offset + idx
            # Check for mandatory pause before S6 if we just finished S5
            # The contract_id logic: we iterate. S5 finishes, loop continues to S6.
            # But we want to PAUSE BEFORE S6 starts if manual correction is enabled.
            # So we check if current contract_id is S6_MANUAL_CORRECTION.

            if contract_id == "S6_MANUAL_CORRECTION":
                # Solo pausamos si AUN no hay correcciones guardadas. Si el usuario ya
                # enviAІ ajustes desde Studio, debemos continuar con S6 y el resto del pipeline.
                corrections_path = temp_root / "work" / "manual_corrections.json"
                has_corrections = False
                try:
                    if corrections_path.exists():
                        raw = json.loads(corrections_path.read_text(encoding="utf-8"))
                        if isinstance(raw, dict) and isinstance(raw.get("corrections"), list):
                            has_corrections = True
                except Exception:
                    logger.warning(
                        "[pipeline] No se pudo leer manual_corrections.json en %s",
                        corrections_path,
                    )

                if not has_corrections:
                    logger.info("[pipeline] Pausing pipeline for Manual Correction (S6)...")

                    # Antes de pausar, asegurarnos de que S6 tenga peaks generados.
                    # Como aún no corrió S6, los stems en S6_MANUAL_CORRECTION son la copia de S5.
                    s6_dir = get_temp_dir("S6_MANUAL_CORRECTION", create=False)
                    if s6_dir.exists():
                        logger.info("[pipeline] Pre-calculating peaks for S6_MANUAL_CORRECTION (before pause)...")
                        for stem_path in s6_dir.glob("*.wav"):
                            if stem_path.name.lower() == "full_song.wav":
                                continue
                            peaks_path = s6_dir / "peaks" / f"{stem_path.stem}.peaks.json"
                            preview_path = s6_dir / "previews" / f"{stem_path.stem}_preview.wav"
                            compute_and_cache_peaks(stem_path, peaks_path)
                            ensure_preview_wav(stem_path, preview_path)

                    # Set status to waiting_for_correction
                    _emit_progress(
                        current_stage_index,
                        effective_total_stages,
                        "waiting_for_correction",
                        "Waiting for manual correction in Studio..."
                    )

                    # Detenemos ejecución del resto de stages hasta que lleguen correcciones.
                    return
                else:
                    logger.info(
                        "[pipeline] Correcciones manuales encontradas (%s); continuando con S6 y mastering.",
                        corrections_path,
                    )

            logger.info(
                "[pipeline] Ejecutando contrato %s (%d/%d)",
                contract_id,
                idx,
                total_stages,
            )

            # Avisamos ANTES de ejecutar el stage para que el frontend
            # muestre el stage que está EN PROGRESO.
            _emit_progress(
                current_stage_index,
                effective_total_stages,
                contract_id,
                f"Running stage {contract_id}...",
            )

            # Ejecuta análisis, stage y check con reintentos, copia al siguiente contrato, etc.
            run_stage(contract_id, context=context)
    finally:
        logger.removeHandler(file_handler)
        pipeline_logger.remove_file_handler(file_handler)


if __name__ == "__main__":
    # CLI simple, sin job_id; útil si quieres probar el pipeline en local.
    run_pipeline()
