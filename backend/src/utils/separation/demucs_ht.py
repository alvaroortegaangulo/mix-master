from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Dict, Optional


def _pick_device() -> str:
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


def _parse_bool_env(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None
    val = value.strip().lower()
    if val in {"1", "true", "yes", "on"}:
        return True
    if val in {"0", "false", "no", "off"}:
        return False
    return None


def separate_demucs_htdemucs_ft_to_dir(
    input_wav_44k_stereo: Path,
    output_stems_dir: Path,
    *,
    model_name: Optional[str] = None,
    device: Optional[str] = None,
    shifts: Optional[int] = None,
    overlap: Optional[float] = None,
    split: Optional[bool] = None,
    write_manifest: bool = True,
) -> Dict[str, Path]:
    """
    Separa un WAV con Demucs usando el modelo htdemucs_ft (por defecto).
    Devuelve {stem_name: path_wav}.
    """
    try:
        import torch
        import torchaudio
        from demucs.audio import AudioFile, convert_audio
        from demucs.apply import apply_model
        from demucs.pretrained import get_model
    except ImportError as exc:
        raise ImportError(
            "Demucs no esta instalado. Instala 'demucs' y 'torchaudio' en el entorno."
        ) from exc

    if model_name is None:
        model_name = os.environ.get("MIX_DEMUCS_MODEL", "htdemucs_ft")

    if device is None:
        device = os.environ.get("MIX_DEMUCS_DEVICE") or _pick_device()

    if shifts is None:
        env_shifts = os.environ.get("MIX_DEMUCS_SHIFTS")
        try:
            shifts = int(env_shifts) if env_shifts else 1
        except ValueError:
            shifts = 1

    if overlap is None:
        env_overlap = os.environ.get("MIX_DEMUCS_OVERLAP")
        try:
            overlap = float(env_overlap) if env_overlap else 0.25
        except ValueError:
            overlap = 0.25

    if split is None:
        split_env = _parse_bool_env(os.environ.get("MIX_DEMUCS_SPLIT"))
        split = split_env if split_env is not None else (device == "cpu")

    if os.environ.get("MIX_OFFLINE") == "1":
        os.environ.setdefault("HF_HUB_OFFLINE", "1")

    cache_root = os.environ.get("MIX_MODELS_DIR")
    if cache_root:
        cache_dir = Path(cache_root).expanduser()
        cache_dir.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("HF_HOME", str(cache_dir))
        os.environ.setdefault("HF_HUB_CACHE", str(cache_dir / "huggingface"))
        os.environ.setdefault("TORCH_HOME", str(cache_dir))

    model = get_model(model_name)
    model.to(device)
    model.eval()

    audio = AudioFile(str(input_wav_44k_stereo)).read(
        streams=0,
        samplerate=model.samplerate,
        channels=model.audio_channels,
    )
    audio = convert_audio(audio, model.samplerate, model.samplerate, model.audio_channels)

    mean = float(audio.mean())
    std = float(audio.std().clamp(min=1e-4))
    audio = (audio - mean) / std

    mix = audio[None].to(device)
    with torch.no_grad():
        sources = apply_model(
            model,
            mix,
            shifts=shifts,
            overlap=overlap,
            split=split,
            progress=False,
            device=device,
        )[0]

    sources = sources * std + mean
    sources = sources.cpu()

    output_stems_dir.mkdir(parents=True, exist_ok=True)
    written: Dict[str, Path] = {}
    sr = int(getattr(model, "samplerate", 44100))
    for source, name in zip(sources, model.sources):
        dst = output_stems_dir / f"{name}.wav"
        torchaudio.save(str(dst), source, sample_rate=sr)
        written[str(name)] = dst

    if write_manifest:
        manifest = {
            "engine": "demucs",
            "model": model_name,
            "device": device,
            "sample_rate": sr,
            "shifts": shifts,
            "overlap": overlap,
            "split": bool(split),
            "input": str(input_wav_44k_stereo),
            "stems": {k: str(v) for k, v in written.items()},
        }
        with (output_stems_dir / "stems_manifest.json").open("w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

    return written


def copy_uploaded_stems_to_stage(work_stems_dir: Path, stage_stems_dir: Path) -> Dict[str, Path]:
    """
    Copia stems subidos por el usuario al directorio del stage.
    Copia todos los archivos de audio directos del directorio.
    """
    stage_stems_dir.mkdir(parents=True, exist_ok=True)
    exts = {".wav", ".flac", ".aiff", ".aif", ".ogg", ".m4a", ".mp3"}
    copied: Dict[str, Path] = {}

    for p in sorted(work_stems_dir.glob("*")):
        if p.is_file() and p.suffix.lower() in exts:
            dst = stage_stems_dir / p.name
            shutil.copy2(p, dst)
            copied[p.stem] = dst

    if not copied:
        raise FileNotFoundError(f"No se encontraron stems en {work_stems_dir}")

    return copied
