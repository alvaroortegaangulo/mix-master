from __future__ import annotations

import inspect
import json
import os
import shutil
from pathlib import Path
from typing import Dict, Optional


def _parse_bool_env(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None
    val = value.strip().lower()
    if val in {"1", "true", "yes", "on"}:
        return True
    if val in {"0", "false", "no", "off"}:
        return False
    return None


def _parse_int_env(value: Optional[str], *, minimum: int = 1) -> Optional[int]:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed < minimum:
        return None
    return parsed


def _configure_models_dir() -> Optional[Path]:
    """
    Configura la carpeta de modelos para cachear descargas de Spleeter.
    Respeta MIX_MODELS_DIR si esta definida, dentro crea una subcarpeta spleeter.
    """
    root = os.environ.get("MIX_MODELS_DIR")
    if not root:
        return None

    models_dir = Path(root).expanduser().resolve() / "spleeter"
    models_dir.mkdir(parents=True, exist_ok=True)

    # Compatibilidad con diferentes variables que usa Spleeter/TF para la cache.
    for env_name in (
        "MODEL_PATH",
        "MODELS_PATH",
        "SPLEETER_MODEL_PATH",
        "SPLEETER_CACHE_DIR",
    ):
        os.environ.setdefault(env_name, str(models_dir))

    return models_dir


def _configure_tensorflow(device_preference: Optional[str], cpu_threads: Optional[int]) -> str:
    """
    Ajusta TensorFlow para rendimiento: memoria gradual en GPU, limite de logs,
    hilos de CPU y bloquea GPU si se pide explicitamente CPU.
    Devuelve "gpu" si se pudieron listar GPUs y no se forzo CPU, si no "cpu".
    """
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    device = "cpu"

    try:
        import tensorflow as tf

        gpu_requested = device_preference not in {"cpu", "none", "off", "0"}
        if gpu_requested:
            gpus = tf.config.list_physical_devices("GPU")
            if gpus:
                try:
                    for gpu in gpus:
                        tf.config.experimental.set_memory_growth(gpu, True)
                    tf.config.set_visible_devices(gpus, "GPU")
                    device = "gpu"
                except Exception:
                    # Si falla el setup, dejamos que TF decida pero reportamos gpu.
                    device = "gpu"
        else:
            try:
                tf.config.set_visible_devices([], "GPU")
            except Exception:
                pass

        if cpu_threads:
            try:
                tf.config.threading.set_intra_op_parallelism_threads(cpu_threads)
                tf.config.threading.set_inter_op_parallelism_threads(max(1, cpu_threads // 2))
            except Exception:
                pass
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise ImportError(
            "Spleeter requiere tensorflow instalado. Anade 'tensorflow' o 'tensorflow-gpu' al entorno."
        ) from exc
    except Exception:
        pass

    return device


def separate_spleeter_to_dir(
    input_wav_44k_stereo: Path,
    output_stems_dir: Path,
    *,
    model_spec: Optional[str] = None,
    device: Optional[str] = None,
    stft_backend: Optional[str] = None,
    mwf: Optional[bool] = None,
    cpu_threads: Optional[int] = None,
    write_manifest: bool = True,
) -> Dict[str, Path]:
    """
    Separa un WAV con Spleeter. Devuelve {stem_name: path_wav}.

    Optimizaciones:
    - Usa 5 stems por defecto (vocals/drums/bass/piano/other).
    - Fuerza backend de STFT en TensorFlow (mas rapido que librosa).
    - Activa memory growth en GPU y permite configurar hilos CPU.
    - Usa MIX_MODELS_DIR/spleeter como cache de modelos si esta disponible.
    """
    try:
        from spleeter.audio.adapter import AudioAdapter
        from spleeter.separator import Separator
    except ImportError as exc:  # pragma: no cover - depende de deps externas
        raise ImportError(
            "Spleeter no esta instalado. Instala 'spleeter' (y tensorflow/tensorflow-gpu) en el entorno."
        ) from exc

    model_dir = _configure_models_dir()

    if model_spec is None:
        model_spec = os.environ.get("MIX_SPLEETER_MODEL", "spleeter:5stems")

    if stft_backend is None:
        stft_backend = os.environ.get("MIX_SPLEETER_STFT", "tensorflow").strip().lower()

    if mwf is None:
        mwf_env = _parse_bool_env(os.environ.get("MIX_SPLEETER_MWF"))
        mwf = False if mwf_env is None else mwf_env

    if cpu_threads is None:
        cpu_threads = _parse_int_env(os.environ.get("MIX_SPLEETER_THREADS"))

    device_pref = (device or os.environ.get("MIX_SPLEETER_DEVICE") or "").strip().lower() or None
    device_used = _configure_tensorflow(device_pref, cpu_threads)

    # Construimos kwargs en funcion de lo soportado por la version instalada.
    separator_kwargs = {"stft_backend": stft_backend}
    if mwf is not None:
        separator_kwargs["MWF"] = bool(mwf)
    if model_dir is not None:
        separator_kwargs["model_directory"] = str(model_dir)

    multiprocess_env = _parse_bool_env(os.environ.get("MIX_SPLEETER_MULTIPROCESS"))
    if multiprocess_env is not None:
        separator_kwargs["multiprocess"] = multiprocess_env

    try:
        sig = inspect.signature(Separator.__init__)
        separator_kwargs = {k: v for k, v in separator_kwargs.items() if k in sig.parameters}
    except Exception:
        separator_kwargs = {"stft_backend": stft_backend, "MWF": mwf}

    separator = Separator(model_spec, **separator_kwargs)

    audio_adapter = AudioAdapter.default()
    waveform, sr = audio_adapter.load(
        str(input_wav_44k_stereo),
        sample_rate=44100,
    )
    waveform = waveform.astype("float32", copy=False)

    prediction = separator.separate(waveform)

    output_stems_dir.mkdir(parents=True, exist_ok=True)
    written: Dict[str, Path] = {}
    for stem_name, audio in prediction.items():
        dst = output_stems_dir / f"{stem_name}.wav"
        audio_adapter.save(str(dst), audio, sample_rate=sr, codec="wav")
        written[str(stem_name)] = dst

    if write_manifest:
        manifest = {
            "engine": "spleeter",
            "model": model_spec,
            "device": device_used,
            "stft_backend": stft_backend,
            "mwf": bool(mwf),
            "sample_rate": int(sr),
            "input": str(input_wav_44k_stereo),
            "stems": {k: str(v) for k, v in written.items()},
            "threads": cpu_threads,
        }
        if model_dir:
            manifest["model_dir"] = str(model_dir)
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
