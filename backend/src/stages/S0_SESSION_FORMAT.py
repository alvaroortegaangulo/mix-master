from utils.logger import logger

import json
import sys
from pathlib import Path
from typing import Dict, Any, Tuple

import numpy as np
import soundfile as sf

try:
    # Resample de buena calidad si SciPy está disponible
    from scipy.signal import resample_poly  # type: ignore
except ImportError:
    resample_poly = None

from utils.analysis_utils import get_temp_dir


def _using_daemonic_process() -> bool:
    """
    Devuelve True si el proceso actual es daemon (por ejemplo, worker prefork de Celery).
    Los procesos daemon no pueden crear nuevos procesos hijos, por lo que
    deberiamos evitar ProcessPoolExecutor en ese contexto.
    """
    try:
        import multiprocessing
        return bool(multiprocessing.current_process().daemon)
    except Exception:
        return False

def load_analysis(contract_id: str) -> Dict[str, Any]:
    """Carga el JSON de análisis de analysis\\S0_SESSION_FORMAT.py en temp/<contract_id>."""
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def resample_audio(
    data: np.ndarray, sr: int, target_sr: int | None
) -> Tuple[np.ndarray, int]:
    """
    Re-muestrea el audio a target_sr si es necesario.
    Usa scipy.signal.resample_poly si está disponible; si no, hace un
    fallback sencillo con interpolación lineal.
    """
    if target_sr is None or target_sr == sr:
        return data, sr

    if data.ndim == 1:
        channels = 1
        data_ch = [data]
    else:
        channels = data.shape[1]
        data_ch = [data[:, ch] for ch in range(channels)]

    resampled_channels = []

    if resample_poly is not None:
        # Resample de buena calidad
        import math

        g = math.gcd(sr, target_sr)
        up = target_sr // g
        down = sr // g

        for ch_data in data_ch:
            resampled = resample_poly(ch_data, up, down)
            resampled_channels.append(resampled.astype(np.float32))
    else:
        # Fallback simple con interpolación lineal
        for ch_data in data_ch:
            n_samples = len(ch_data)
            n_target = int(round(n_samples * target_sr / sr))
            x_old = np.linspace(0, 1, n_samples, endpoint=False)
            x_new = np.linspace(0, 1, n_target, endpoint=False)
            resampled = np.interp(x_new, x_old, ch_data)
            resampled_channels.append(resampled.astype(np.float32))

    if channels == 1:
        resampled_data = resampled_channels[0]
    else:
        resampled_data = np.stack(resampled_channels, axis=1)

    return resampled_data, target_sr


def normalize_channels_to_stereo(data: np.ndarray) -> np.ndarray:
    """
    Normalize stems to stereo so mixdown doesn't drop mono files.
    """
    if data.ndim == 1:
        return np.stack((data, data), axis=1)

    if data.ndim == 2:
        channels = data.shape[1]
        if channels == 2:
            return data
        if channels == 1:
            return np.repeat(data, 2, axis=1)
        # Fallback: downmix to mono then upmix to stereo.
        mono = data.mean(axis=1, dtype=np.float32)
        return np.stack((mono, mono), axis=1)

    return data


def apply_peak_normalization(
    data: np.ndarray, max_peak_dbfs: float | None
) -> np.ndarray:
    """
    Garantiza que el pico máximo no supera max_peak_dbfs.
    No sube el nivel si el audio ya está por debajo; solo reduce si es necesario.
    """
    if max_peak_dbfs is None:
        return data

    target_linear = 10.0 ** (max_peak_dbfs / 20.0)
    peak = float(np.max(np.abs(data))) if data.size > 0 else 0.0

    if peak <= 0.0:
        return data

    if peak > target_linear:
        scale = target_linear / peak
        data = data * scale

    return data


def process_stem(stem_info: Dict[str, Any], metrics: Dict[str, Any]) -> None:
    """
    Aplica las conversiones de formato a un stem:
      - samplerate_hz
      - bit_depth_internal (float32)
      - normalización de picos
    Sobrescribe el archivo original.
    """
    file_path = Path(stem_info["file_path"])
    target_sr = metrics.get("samplerate_hz")
    target_bit_depth = metrics.get("bit_depth_internal")
    max_peak_dbfs = metrics.get("max_peak_dbfs")

    # 1) Leer audio
    data, sr = sf.read(file_path, always_2d=False)

    # 2) Convertir a float32 interno
    if data.dtype != np.float32:
        data = data.astype(np.float32)

    # 3) Resample si es necesario
    data, sr = resample_audio(data, sr, target_sr)

    # Normalizar canales a stereo (evita mismatches en mixdown)
    data = normalize_channels_to_stereo(data)

    # 4) Normalización de picos según contrato
    data = apply_peak_normalization(data, max_peak_dbfs)

    # 5) Escribir de vuelta el archivo con formato consistente
    #    Bit depth interno -> usamos FLOAT (32-bit float)
    subtype = "FLOAT" if target_bit_depth == 32 else None
    # soundfile seleccionará un subtype por defecto si subtype es None
    sf.write(file_path, data, sr, subtype=subtype)


# -------------------------------------------------------------------
# -------------------------------------------------------------------

def _process_stem_worker(args: Tuple[Dict[str, Any], Dict[str, Any]]) -> None:
    """
    Wrapper para ejecutar process_stem en un proceso hijo.
    """
    stem_info, metrics = args
    process_stem(stem_info, metrics)


def main() -> None:
    """
    Stage S0_SESSION_FORMAT:
      - Lee analysis_S0_SESSION_FORMAT.json.
      - Aplica conversiones de formato a cada stem (en paralelo).
      - Sobrescribe los stems en temp/<contract_id>/.
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S0_SESSION_FORMAT.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S0_SESSION_FORMAT"

    analysis = load_analysis(contract_id)

    metrics = analysis.get("metrics_from_contract", {})
    stems = analysis.get("stems", [])

    if not stems:
        logger.logger.info("[S0_SESSION_FORMAT] No hay stems en el análisis; nada que procesar.")
        return

    # Procesar stems en paralelo
    args_list = [(stem_info, metrics) for stem_info in stems]

    # Usar ProcessPoolExecutor para paralelizar el re-muestreo y conversión
    import concurrent.futures
    import os

    max_workers = min(len(stems), os.cpu_count() or 1)
    if max_workers < 1:
        max_workers = 1

    logger.logger.info(f"[S0_SESSION_FORMAT] Procesando {len(stems)} stems con {max_workers} workers.")

    use_process_pool = not _using_daemonic_process()
    executor_cls = concurrent.futures.ProcessPoolExecutor if use_process_pool else concurrent.futures.ThreadPoolExecutor

    if not use_process_pool:
        logger.logger.info("[S0_SESSION_FORMAT] Proceso daemon detectado; usando ThreadPoolExecutor en lugar de procesos.")

    with executor_cls(max_workers=max_workers) as executor:
        list(executor.map(_process_stem_worker, args_list))

    logger.logger.info(f"[S0_SESSION_FORMAT] Conversión de formato completada para {len(stems)} stems.")


if __name__ == "__main__":
    main()
