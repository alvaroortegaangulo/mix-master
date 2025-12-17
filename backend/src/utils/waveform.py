import json
import logging
from pathlib import Path
from typing import List
import soundfile as sf
import numpy as np

logger = logging.getLogger(__name__)

STEM_PEAKS_DESIRED_BARS = 800

def compute_and_cache_peaks(
    stem_path: Path, peaks_path: Path, desired_bars: int = STEM_PEAKS_DESIRED_BARS
) -> List[float]:
    """
    Devuelve una lista de peaks RMS normalizados. Si existe un fichero cacheado, lo usa.
    """
    if peaks_path.exists():
        try:
            data = json.loads(peaks_path.read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                return [float(x) for x in data]
        except Exception:
            logger.warning("No se pudo leer peaks cacheados en %s", peaks_path)
            # Proceed to re-calculate

    try:
        # Read full file as float32
        audio, _ = sf.read(str(stem_path), dtype="float32", always_2d=True)
        if audio.ndim == 2 and audio.shape[1] > 1:
            audio_mono = audio.mean(axis=1)
        else:
            audio_mono = audio.squeeze()

        total_samples = len(audio_mono)
        if total_samples == 0:
            return []

        bars = max(10, desired_bars)
        samples_per_bar = max(1, total_samples // bars)
        trim = (total_samples // samples_per_bar) * samples_per_bar
        window = audio_mono[:trim].reshape(-1, samples_per_bar)
        rms = np.sqrt(np.mean(np.square(window), axis=1))

        max_peak = float(np.max(rms)) if rms.size else 1.0
        norm = max_peak if max_peak > 0 else 1.0
        peaks = (rms / norm).tolist()

        peaks_path.parent.mkdir(parents=True, exist_ok=True)
        peaks_path.write_text(json.dumps(peaks), encoding="utf-8")
        logger.info("Peaks generated for %s -> %s", stem_path.name, peaks_path)
        return peaks
    except Exception as exc:
        logger.warning("No se pudo calcular peaks para %s: %s", stem_path.name, exc)
        return []

def ensure_preview_wav(
    stem_path: Path, preview_path: Path, target_sr: int = 32000
) -> bool:
    """
    Genera un wav de preview mono/downsampleado si no existe.
    """
    if preview_path.exists():
        return True

    try:
        audio, sr = sf.read(str(stem_path), dtype="float32", always_2d=True)
        if audio.ndim == 2 and audio.shape[1] > 1:
            mono = audio.mean(axis=1)
        else:
            mono = audio.squeeze()

        if sr != target_sr and len(mono) > 0:
            # Reescalar simple via interpolación lineal para evitar dependencias extra.
            new_len = max(1, int(len(mono) * (target_sr / sr)))
            x_old = np.linspace(0, 1, num=len(mono), endpoint=False)
            x_new = np.linspace(0, 1, num=new_len, endpoint=False)
            mono = np.interp(x_new, x_old, mono).astype("float32")
        else:
            mono = mono.astype("float32")

        preview_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(preview_path), mono, target_sr)
        logger.info("Preview generated for %s -> %s", stem_path.name, preview_path)
        return True
    except Exception as exc:
        logger.warning("No se pudo generar preview para %s: %s", stem_path.name, exc)
        return False
