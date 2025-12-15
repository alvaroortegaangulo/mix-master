from __future__ import annotations

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional, Any

THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.analysis_utils import get_temp_dir  # type: ignore  # noqa: E402
from utils.separation.demucs_ht import (  # type: ignore  # noqa: E402
    separate_demucs_htdemucs_ft_to_dir,
)

try:
    from context import PipelineContext  # type: ignore
except Exception:  # pragma: no cover
    PipelineContext = None


AUDIO_EXTS = {".wav", ".flac", ".mp3", ".m4a", ".aac", ".ogg", ".aiff", ".aif"}


def _stage_dir(contract_id: str, context: Optional["PipelineContext"] = None) -> Path:
    if context is not None and getattr(context, "temp_root", None):
        return Path(context.temp_root) / contract_id
    return get_temp_dir(contract_id, create=True)


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


def _find_full_song(stage_dir: Path, job_root: Path) -> Optional[Path]:
    """
    Busca el full_song final del pipeline, priorizando S11_REPORT_GENERATION.
    """
    candidates = [
        stage_dir / "full_song.wav",
        job_root / "S11_REPORT_GENERATION" / "full_song.wav",
        job_root / "S10_MASTER_FINAL_LIMITS" / "full_song.wav",
        job_root / "S9_MASTER_GENERIC" / "full_song.wav",
        job_root / "S8_MIXBUS_COLOR_GENERIC" / "full_song.wav",
        job_root / "S7_MIXBUS_TONAL_BALANCE" / "full_song.wav",
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c

    # fallback: busca el full_song más reciente en el job
    found: list[Path] = []
    for p in job_root.rglob("full_song.wav"):
        if p.is_file():
            found.append(p)
    if found:
        found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return found[0]
    return None


def _clear_previous_audio(stage_dir: Path) -> None:
    """
    Elimina stems previos para dejar solo el nuevo resultado.
    Conserva full_song.wav y archivos JSON/imagen.
    """
    for item in stage_dir.iterdir():
        if not item.is_file():
            continue
        if item.name.lower() == "full_song.wav":
            continue
        if item.suffix.lower() in {".json", ".png", ".jpg", ".jpeg"}:
            continue
        if item.suffix.lower() in AUDIO_EXTS:
            try:
                item.unlink()
            except Exception:
                pass

    legacy_input = stage_dir / "input"
    if legacy_input.exists():
        shutil.rmtree(legacy_input, ignore_errors=True)


def process(context: "PipelineContext", contract_id: str) -> bool:
    return _process_impl(contract_id, context)


def _process_impl(contract_id: str, context: Optional["PipelineContext"] = None) -> bool:
    stage_dir = _stage_dir(contract_id, context)
    stage_dir.mkdir(parents=True, exist_ok=True)
    job_root = stage_dir.parent

    _clear_previous_audio(stage_dir)

    full_song = _find_full_song(stage_dir, job_root)
    if full_song is None:
        raise FileNotFoundError(
            f"[S12_SEPARATE_STEMS] No encuentro full_song.wav final en el job_root {job_root}"
        )

    # Copia el full_song de referencia para dejarlo accesible en el stage.
    target_full = stage_dir / "full_song.wav"
    shutil.copy2(full_song, target_full)

    input_dir = stage_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)

    tmp_wav = input_dir / "work_in.wav"
    wav_path = _ensure_wav_44100_stereo(target_full, tmp_wav)

    written = separate_demucs_htdemucs_ft_to_dir(
        wav_path,
        stage_dir,
        model_name=os.environ.get("MIX_DEMUCS_MODEL", "htdemucs_ft"),
        device=os.environ.get("MIX_DEMUCS_DEVICE") or None,
        write_manifest=True,
    )

    try:
        tmp_wav.unlink(missing_ok=True)
    except Exception:
        pass

    print(f"[S12_SEPARATE_STEMS] Separación completada. Stems: {list(written.keys())}")
    return True


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python S12_SEPARATE_STEMS.py <CONTRACT_ID>")
        sys.exit(1)
    contract_id = sys.argv[1]
    ok = _process_impl(contract_id, context=None)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
