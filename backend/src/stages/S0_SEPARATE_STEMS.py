from __future__ import annotations

import sys
import os
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.analysis_utils import get_temp_dir  # type: ignore  # noqa: E402
from utils.separation.bs_roformer import (  # type: ignore  # noqa: E402
    separate_bs_roformer_to_dir,
    copy_uploaded_stems_to_stage,
)

try:
    from context import PipelineContext  # type: ignore
except Exception:  # pragma: no cover
    PipelineContext = None


AUDIO_EXTS = {".wav", ".flac", ".mp3", ".m4a", ".aac", ".ogg", ".aiff", ".aif"}


def _list_audio_files(
    base: Path,
    *,
    recursive: bool = False,
    skip_names: Optional[set[str]] = None,
) -> list[Path]:
    skip = {n.lower() for n in (skip_names or set())}
    iterator = base.rglob("*") if recursive else base.glob("*")
    files: list[Path] = []
    for p in iterator:
        if not p.is_file():
            continue
        if p.suffix.lower() not in AUDIO_EXTS:
            continue
        if p.name.lower() in skip:
            continue
        files.append(p)
    return sorted(files)


def _move_legacy_stems_to_root(stage_dir: Path) -> list[Path]:
    """
    Older versions left stems inside stage_dir/stems. Move them to stage root so
    copy_stems and mixdown scripts can see them.
    """
    legacy_dir = stage_dir / "stems"
    moved: list[Path] = []

    if not legacy_dir.exists():
        return moved

    for p in sorted(legacy_dir.glob("*")):
        if not p.is_file() or p.suffix.lower() not in AUDIO_EXTS:
            continue
        dst = stage_dir / p.name
        try:
            dst.unlink(missing_ok=True)
        except Exception:
            pass
        shutil.move(str(p), dst)
        moved.append(dst)

    try:
        legacy_dir.rmdir()
    except OSError:
        pass

    return moved


def _get_media_dir_from_env() -> Optional[Path]:
    media_env = os.environ.get("MIX_MEDIA_DIR")
    if not media_env:
        return None
    media_dir = Path(media_env)
    return media_dir if media_dir.exists() else None


def _stage_dir(contract_id: str, context: Optional["PipelineContext"] = None) -> Path:
    if context is not None and getattr(context, "temp_root", None):
        return Path(context.temp_root) / contract_id
    return get_temp_dir(contract_id, create=True)


def load_analysis(contract_id: str, context: Optional["PipelineContext"] = None) -> Dict[str, Any]:
    temp_dir = _stage_dir(contract_id, context)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"
    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")
    with analysis_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _job_work_dir(stage_dir: Path) -> Path:
    job_root = stage_dir.parent
    return job_root / "work"


def _find_work_stems_dir(work_dir: Path) -> Optional[Path]:
    candidates = [
        work_dir / "stems",
        work_dir / "uploads" / "stems",
        work_dir / "media" / "stems",
        work_dir / "input" / "stems",
    ]
    for c in candidates:
        if c.exists() and any(p.is_file() and p.suffix.lower() in AUDIO_EXTS for p in c.glob("*")):
            return c

    # fallback: busca un directorio llamado stems con audios dentro
    for c in work_dir.rglob("*"):
        if c.is_dir() and c.name.lower() == "stems":
            if any(p.is_file() and p.suffix.lower() in AUDIO_EXTS for p in c.glob("*")):
                return c
    return None


def _find_uploaded_song(
    work_dir: Path,
    stage_dir: Path,
    media_dir: Optional[Path] = None,
) -> Optional[Path]:
    """
    Busca la cancion subida sin depender del nombre del archivo.
    Prioriza lo que ya esta en la carpeta del stage, luego media/, y por
    ultimo las heuristicas antiguas en work/.
    """
    skip = {"full_song.wav"}

    stage_audio = _list_audio_files(stage_dir, skip_names=skip)
    if stage_audio:
        return stage_audio[0]

    input_dir = stage_dir / "input"
    if input_dir.exists():
        input_audio = _list_audio_files(input_dir, recursive=True, skip_names=skip)
        if input_audio:
            return input_audio[0]

    if media_dir is not None:
        media_audio = _list_audio_files(media_dir, skip_names=skip)
        if media_audio:
            return media_audio[0]

    preferred = [
        work_dir / "song.wav",
        work_dir / "song.flac",
        work_dir / "input.wav",
        work_dir / "input.flac",
        work_dir / "uploaded.wav",
        work_dir / "uploaded.flac",
        work_dir / "full_song.wav",
    ]
    for p in preferred:
        if p.exists() and p.is_file():
            return p

    for p in _list_audio_files(work_dir, recursive=True, skip_names=skip):
        if "stems" in {part.lower() for part in p.parts}:
            continue
        return p
    return None


def _ensure_wav_44100_stereo(src: Path, dst: Path) -> Path:
    """
    Convierte a WAV 44.1kHz estéreo float32 usando ffmpeg si está disponible.
    Si src ya es wav, copia.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() == ".wav":
        shutil.copy2(src, dst)
        return dst

    ffmpeg = os.environ.get("FFMPEG_BIN", "ffmpeg")
    try:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(src),
                "-ac",
                "2",
                "-ar",
                "44100",
                "-c:a",
                "pcm_f32le",
                str(dst),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return dst
    except Exception as exc:
        raise RuntimeError(
            f"No se pudo convertir {src.name} a WAV (ffmpeg requerido para {src.suffix}). "
            f"Instala ffmpeg o sube WAV/FLAC compatible. Error: {exc}"
        )


def process(context: "PipelineContext", contract_id: str) -> bool:
    return _process_impl(contract_id, context)


def _process_impl(contract_id: str, context: Optional["PipelineContext"] = None) -> bool:
    stage_dir = _stage_dir(contract_id, context)
    stage_dir.mkdir(parents=True, exist_ok=True)

    analysis = load_analysis(contract_id, context)
    session: Dict[str, Any] = analysis.get("session", {}) or {}

    upload_mode = str(session.get("upload_mode", "song")).strip().lower()
    is_stems_upload = bool(session.get("is_stems_upload", upload_mode == "stems"))

    work_dir = _job_work_dir(stage_dir)
    media_dir = _get_media_dir_from_env()
    input_dir = stage_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)

    legacy_moved = _move_legacy_stems_to_root(stage_dir)

    # Si venimos de un layout legacy, saca la cancion del root del stage para que
    # no se copie como stem al siguiente stage.
    if legacy_moved and not is_stems_upload:
        for p in _list_audio_files(stage_dir, skip_names={"full_song.wav"}):
            if p not in legacy_moved:
                target = input_dir / p.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(p), target)

    # Idempotencia: si ya hay stems en el root del stage, listo.
    existing = _list_audio_files(stage_dir, skip_names={"full_song.wav"})
    if len(existing) >= 2 or (is_stems_upload and existing):
        print(f"[S0_SEPARATE_STEMS] Stems ya presentes en {stage_dir}. Skip.")
        return True

    if is_stems_upload:
        copied_total = 0
        if media_dir:
            try:
                copied = copy_uploaded_stems_to_stage(media_dir, stage_dir)
                copied_total += len(copied)
            except FileNotFoundError:
                pass

        if copied_total == 0:
            work_stems = _find_work_stems_dir(work_dir)
            if work_stems:
                copied = copy_uploaded_stems_to_stage(work_stems, stage_dir)
                copied_total += len(copied)

        existing = _list_audio_files(stage_dir, skip_names={"full_song.wav"})
        if not existing:
            raise FileNotFoundError(
                f"[S0_SEPARATE_STEMS] upload_mode=stems pero no encuentro stems en {stage_dir}"
            )
        print(f"[S0_SEPARATE_STEMS] Stems listos en {stage_dir} (copiados {copied_total}).")
        return True

    # upload_mode = song -> separar
    song_path = _find_uploaded_song(work_dir, stage_dir, media_dir)
    if not song_path:
        raise FileNotFoundError(
            f"[S0_SEPARATE_STEMS] No encuentro cancion subida en {stage_dir} ni en {work_dir}"
        )

    if song_path.parent == stage_dir:
        target = input_dir / song_path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(song_path), target)
        song_path = target
    elif song_path.parent != input_dir:
        target = input_dir / song_path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(song_path, target)
        song_path = target

    # Limpia posibles restos de stems viejos en el root antes de escribir los nuevos.
    for old in _list_audio_files(stage_dir, skip_names={"full_song.wav"}):
        try:
            old.unlink()
        except Exception:
            pass

    tmp_wav = input_dir / "work_in.wav"
    wav_path = _ensure_wav_44100_stereo(song_path, tmp_wav)

    written = separate_bs_roformer_to_dir(
        wav_path,
        stage_dir,
        models_dir=Path(os.environ.get("MIX_MODELS_DIR", stage_dir.parent / "models" / "bs_roformer")),
        device=os.environ.get("MIX_BS_ROFORMER_DEVICE") or None,
        write_manifest=True,
    )

    try:
        tmp_wav.unlink(missing_ok=True)
    except Exception:
        pass

    print(f"[S0_SEPARATE_STEMS] Separacion completada. Stems: {list(written.keys())}")
    return True


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python S0_SEPARATE_STEMS.py <CONTRACT_ID>")
        sys.exit(1)
    contract_id = sys.argv[1]
    ok = _process_impl(contract_id, context=None)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
