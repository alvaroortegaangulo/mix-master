from utils.logger import logger
import sys
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
import json
import numpy as np

try:
    from scipy.signal import resample_poly  # type: ignore
except ImportError:
    resample_poly = None

try:
    from context import PipelineContext
except ImportError:
    PipelineContext = None # type: ignore

from utils.analysis_utils import get_temp_dir

def load_analysis(context: PipelineContext, contract_id: str) -> Dict[str, Any]:
    if context.temp_root:
        temp_dir = context.temp_root / contract_id
    else:
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
        import math
        g = math.gcd(sr, target_sr)
        up = target_sr // g
        down = sr // g
        for ch_data in data_ch:
            resampled = resample_poly(ch_data, up, down)
            resampled_channels.append(resampled.astype(np.float32))
    else:
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


def apply_peak_normalization(
    data: np.ndarray, max_peak_dbfs: float | None
) -> np.ndarray:
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


def process(context: PipelineContext, *args) -> bool:
    """
    IN-MEMORY processing for S0_SESSION_FORMAT
    """
    contract_id = context.stage_id
    try:
        analysis = load_analysis(context, contract_id)
    except FileNotFoundError:
        logger.error(f"[S0_SESSION_FORMAT] Analysis not found for {contract_id}")
        return False

    metrics = analysis.get("metrics_from_contract", {})
    stems_info = analysis.get("stems", [])

    target_sr = metrics.get("samplerate_hz")
    target_bit_depth = metrics.get("bit_depth_internal")
    max_peak_dbfs = metrics.get("max_peak_dbfs")

    # Update global context sample rate if changed
    if target_sr is not None and target_sr != context.sample_rate:
        logger.info(f"[S0_SESSION_FORMAT] Updating global sample rate from {context.sample_rate} to {target_sr}")
        context.sample_rate = target_sr

    processed_count = 0
    for stem_info in stems_info:
        file_name = Path(stem_info["file_path"]).name
        if file_name not in context.audio_stems:
            continue

        data = context.audio_stems[file_name]
        sr = stem_info.get("samplerate_hz", context.sample_rate)

        # 1. Resample
        data, new_sr = resample_audio(data, sr, target_sr)

        # 2. Peak Norm
        data = apply_peak_normalization(data, max_peak_dbfs)

        # Update memory
        context.audio_stems[file_name] = data
        processed_count += 1

    logger.info(f"[S0_SESSION_FORMAT] Processed {processed_count} stems in memory.")
    return True

def main() -> None:
    pass

if __name__ == "__main__":
    main()
