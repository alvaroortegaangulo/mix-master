from __future__ import annotations

import os
import time
import json
import shutil
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np

# Nota: torch / splifft se importan dentro de funciones para que el backend pueda arrancar
# aunque la separación no esté instalada en todos los entornos.


DEFAULT_CONFIG_URL = (
    "https://raw.githubusercontent.com/undef13/splifft/refs/heads/main/data/config/bs_roformer.json"
)
DEFAULT_CKPT_URL = (
    "https://huggingface.co/undef13/splifft/resolve/main/roformer-fp16.pt?download=true"
)

# Tamaños mínimos “razonables” para evitar archivos truncados
MIN_CONFIG_BYTES = 200
MIN_CKPT_BYTES = 50_000_000  # ~50MB (el real suele ser bastante mayor)


@dataclass(frozen=True)
class BSRoformerAssets:
    config_path: Path
    checkpoint_path: Path


def _atomic_download(url: str, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".tmp")

    req = urllib.request.Request(url, headers={"User-Agent": "mix-master/bs-roformer"})
    with urllib.request.urlopen(req, timeout=60) as r, tmp.open("wb") as f:
        while True:
            chunk = r.read(16 * 1024 * 1024)
            if not chunk:
                break
            f.write(chunk)

    tmp.replace(dst)


def _acquire_lock(lock_path: Path, timeout_sec: int = 180) -> None:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return
        except FileExistsError:
            if time.time() - start > timeout_sec:
                raise TimeoutError(f"Timeout esperando lock: {lock_path}")
            time.sleep(0.5)


def _release_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink(missing_ok=True)
    except Exception:
        pass


def ensure_bs_roformer_assets(models_dir: Path) -> BSRoformerAssets:
    """
    Asegura que existan:
      - bs_roformer.json
      - roformer-fp16.pt

    Por defecto intenta descargarlos si no están. En producción, lo ideal es
    precachearlos en la imagen Docker y desactivar descargas.
    """
    offline = os.environ.get("MIX_OFFLINE", "").strip() == "1"

    config_path = models_dir / "bs_roformer.json"
    ckpt_path = models_dir / "roformer-fp16.pt"

    lock = models_dir / ".download.lock"
    _acquire_lock(lock)
    try:
        if (not config_path.exists()) or config_path.stat().st_size < MIN_CONFIG_BYTES:
            if offline:
                raise FileNotFoundError(
                    f"Falta config BS-RoFormer en {config_path} y MIX_OFFLINE=1"
                )
            _atomic_download(DEFAULT_CONFIG_URL, config_path)

        if (not ckpt_path.exists()) or ckpt_path.stat().st_size < MIN_CKPT_BYTES:
            if offline:
                raise FileNotFoundError(
                    f"Falta checkpoint BS-RoFormer en {ckpt_path} y MIX_OFFLINE=1"
                )
            _atomic_download(DEFAULT_CKPT_URL, ckpt_path)

    finally:
        _release_lock(lock)

    return BSRoformerAssets(config_path=config_path, checkpoint_path=ckpt_path)


def _pick_device() -> str:
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        # MPS podría existir, pero muchos pipelines no están igual de probados
        return "cpu"
    except Exception:
        return "cpu"


def _normalize_peak(x: "np.ndarray", target_peak: float = 0.99) -> Tuple["np.ndarray", float]:
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    if peak <= 0.0:
        return x, 1.0
    gain = target_peak / peak if peak > target_peak else 1.0
    return (x * gain).astype(np.float32, copy=False), gain


def _write_wav(path: Path, audio_ch_first: "np.ndarray", sr: int) -> None:
    """
    audio_ch_first: (channels, samples)
    """
    import soundfile as sf

    path.parent.mkdir(parents=True, exist_ok=True)
    # soundfile espera (samples, channels)
    data = np.transpose(audio_ch_first, (1, 0))
    sf.write(str(path), data, sr, subtype="FLOAT")


def separate_bs_roformer_to_dir(
    input_wav_44k_stereo: Path,
    output_stems_dir: Path,
    *,
    models_dir: Optional[Path] = None,
    device: Optional[str] = None,
    write_manifest: bool = True,
) -> Dict[str, Path]:
    """
    Separa un WAV (preferiblemente 44.1kHz estéreo) a stems con BS-RoFormer.
    Devuelve {stem_name: path_wav}.
    """
    if models_dir is None:
        models_dir = Path(os.environ.get("MIX_MODELS_DIR", "")).expanduser().resolve() if os.environ.get("MIX_MODELS_DIR") else None
        if models_dir is None:
            # fallback: <repo>/backend/models/bs_roformer (si lo creas)
            models_dir = Path(__file__).resolve().parents[3] / "models" / "bs_roformer"
    models_dir.mkdir(parents=True, exist_ok=True)

    assets = ensure_bs_roformer_assets(models_dir)

    if device is None:
        device = _pick_device()

    # Imports pesados aquí
    import torch
    from splifft.config import Config
    from splifft.models import ModelMetadata
    from splifft.models.bs_roformer import BSRoformer, BSRoformerParams
    from splifft.io import load_weights
    from splifft.inference import separate as splifft_separate

    # 1) Config + modelo
    config = Config.from_file(assets.config_path)
    metadata = ModelMetadata(model_type="bs_roformer", params=BSRoformerParams, model=BSRoformer)
    model_params = config.model.to_concrete(metadata.params)

    model = metadata.model(model_params)
    model = load_weights(model, assets.checkpoint_path, device=device)

    if device == "cpu":
        # checkpoint fp16 -> CPU suele ir mejor forzando float32
        model = model.float()
        try:
            config.inference.use_autocast_dtype = None  # type: ignore[attr-defined]
        except Exception:
            pass

    model.eval()

    # 2) Cargar audio (esperamos WAV 44.1k estéreo)
    import soundfile as sf

    data, sr = sf.read(str(input_wav_44k_stereo), always_2d=True, dtype="float32")  # (samples, ch)
    audio = data.T  # (ch, samples)

    # Forzar canales si el config lo pide
    try:
        force_ch = int(getattr(config.audio_io, "force_channels", audio.shape[0]))
    except Exception:
        force_ch = audio.shape[0]

    if force_ch == 2 and audio.shape[0] == 1:
        audio = np.vstack([audio, audio])
    elif force_ch == 1 and audio.shape[0] == 2:
        audio = audio[:1, :]

    # Normalización opcional (si el config lo pide)
    try:
        do_norm = bool(getattr(config.inference, "normalize_input_audio", False))
    except Exception:
        do_norm = False

    gain = 1.0
    if do_norm:
        audio, gain = _normalize_peak(audio)

    mix = torch.from_numpy(audio).to(device)

    # 3) Inferencia “chunked”
    use_autocast = None
    try:
        use_autocast = getattr(config.inference, "use_autocast_dtype", None)
    except Exception:
        use_autocast = None

    separated = splifft_separate(
        mixture_data=mix,
        chunk_cfg=config.chunking,
        model=model,
        batch_size=config.inference.batch_size,
        num_model_stems=len(config.model.output_stem_names),
        chunk_size=config.model.chunk_size,
        model_input_type=model_params.input_type,
        model_output_type=model_params.output_type,
        stft_cfg=config.stft,
        masking_cfg=config.masking,
        use_autocast_dtype=use_autocast,
    )  # (stems, ch, samples)

    separated = separated.detach().to("cpu").float().numpy()

    # Des-normalizar si normalizamos entrada
    if do_norm and gain != 1.0:
        separated = separated / gain

    # 4) Escritura
    output_stems_dir.mkdir(parents=True, exist_ok=True)
    written: Dict[str, Path] = {}

    stem_names = list(config.model.output_stem_names)
    for i, name in enumerate(stem_names):
        wav_path = output_stems_dir / f"{name}.wav"
        _write_wav(wav_path, separated[i], sr)
        written[str(name)] = wav_path

    if write_manifest:
        manifest = {
            "engine": "bs_roformer",
            "device": device,
            "input": str(input_wav_44k_stereo),
            "sample_rate": int(sr),
            "stems": {k: str(v) for k, v in written.items()},
            "assets": {
                "config_path": str(assets.config_path),
                "checkpoint_path": str(assets.checkpoint_path),
            },
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
