from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any
import json
import numpy as np

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pedalboard import (
    Pedalboard,
    LowShelfFilter,
    HighShelfFilter,
    PeakFilter,
)

from utils.analysis_utils import get_temp_dir
from utils.tonal_balance_utils import (
    get_freq_bands,
    compute_band_energies,
    get_style_tonal_profile,
    compute_tonal_error,
)
try:
    from context import PipelineContext
except ImportError:
    PipelineContext = None # type: ignore


def load_analysis_with_context(context: PipelineContext) -> Dict[str, Any]:
    stage_id = context.stage_id
    if context.temp_root:
        temp_dir = context.temp_root / stage_id
    else:
        temp_dir = get_temp_dir(stage_id, create=False)

    analysis_path = temp_dir / f"analysis_{stage_id}.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def _build_pedalboard_eq(eq_gains_db: Dict[str, float], sr: int) -> Pedalboard:
    bands = get_freq_bands()
    nyquist = float(sr) / 2.0 if sr > 0 else None
    plugins = []

    if not bands:
        return Pedalboard([])

    n_bands = len(bands)

    for idx, band in enumerate(bands):
        band_id = band.get("id")
        if band_id is None:
            continue

        gain_db = float(eq_gains_db.get(band_id, 0.0))
        if abs(gain_db) < 1e-3:
            continue

        f_min = float(band.get("f_min", 0.0))
        f_max = float(band.get("f_max", 0.0))

        if nyquist is not None and nyquist > 0.0:
            f_min = max(0.0, min(f_min, nyquist))
            f_max = max(0.0, min(f_max, nyquist))

        if f_max <= 0.0:
            continue

        if idx == 0 or f_min <= 0.0:
            cutoff = max(20.0, f_max if nyquist is None else min(f_max, nyquist))
            q = 0.707
            plugins.append(LowShelfFilter(cutoff_frequency_hz=cutoff, gain_db=gain_db, q=q))
            continue

        if idx == n_bands - 1 or (nyquist is not None and f_max >= nyquist * 0.9):
            cutoff = max(20.0, f_min if nyquist is None else min(f_min, nyquist))
            q = 0.707
            plugins.append(HighShelfFilter(cutoff_frequency_hz=cutoff, gain_db=gain_db, q=q))
            continue

        if f_min <= 0.0:
            center = f_max
        else:
            center = (f_min * f_max) ** 0.5

        if nyquist is not None:
            center = max(20.0, min(center, nyquist))

        bandwidth = max(f_max - f_min, 1.0)
        q = float(center / bandwidth) if bandwidth > 0.0 else 1.0
        q = max(0.1, min(q, 4.0))

        plugins.append(PeakFilter(cutoff_frequency_hz=center, gain_db=gain_db, q=q))

    return Pedalboard(plugins)


def _apply_multiband_eq_pedalboard(audio: np.ndarray, sr: int, eq_gains_db: Dict[str, float]) -> np.ndarray:
    x = np.asarray(audio, dtype=np.float32)

    if x.size == 0 or sr <= 0:
        return x

    if not eq_gains_db or all(abs(v) < 1e-3 for v in eq_gains_db.values()):
        return x

    board = _build_pedalboard_eq(eq_gains_db, sr)

    if len(board) == 0:
        return x

    y = board(x, sr)
    y = np.asarray(y, dtype=np.float32)
    y = np.clip(y, -1.5, 1.5)

    return y


def _save_tonal_metrics(
    temp_dir: Path,
    contract_id: str,
    style_preset: str,
    pre_band_db: Dict[str, float],
    post_band_db: Dict[str, float],
    target_band_db: Dict[str, float],
    pre_error_rms: float,
    post_error_rms: float,
    eq_gains_db: Dict[str, float],
    max_tonal_error_db: float,
    max_eq_change_db: float,
) -> None:
    temp_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = temp_dir / "tonal_metrics_S7_MIXBUS_TONAL_BALANCE.json"
    data = {
        "contract_id": contract_id,
        "style_preset": style_preset,
        "max_tonal_balance_error_db": max_tonal_error_db,
        "max_eq_change_db_per_band_per_pass": max_eq_change_db,
        "pre": {
            "band_db": pre_band_db,
            "error_rms_db": pre_error_rms,
        },
        "post": {
            "band_db": post_band_db,
            "error_rms_db": post_error_rms,
        },
        "target_band_db": target_band_db,
        "eq_gains_db": eq_gains_db,
    }

    try:
        with metrics_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"[S7] Failed to save tonal metrics: {e}")


def process(context: PipelineContext, *args) -> bool:
    """
    IN-MEMORY processing for S7_MIXBUS_TONAL_BALANCE
    Modifies context.audio_mixdown IN-PLACE.
    """
    contract_id = context.stage_id
    temp_dir = context.get_stage_dir()

    try:
        analysis = load_analysis_with_context(context)
    except FileNotFoundError:
        logger.error(f"[S7_MIXBUS_TONAL_BALANCE] Analysis not found.")
        return False

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}
    session: Dict[str, Any] = analysis.get("session", {}) or {}

    style_preset = analysis.get("style_preset", "default")
    tonal_info: Dict[str, Any] = session.get("tonal_bands", {}) or {}

    prev_error_rms = float(tonal_info.get("error_rms_db", 0.0))
    current_band_db = tonal_info.get("current_band_db", {}) or {}
    target_band_db = tonal_info.get("target_band_db", {}) or {}

    max_tonal_error_db = float(metrics.get("max_tonal_balance_error_db", 3.0))
    max_eq_change_db = float(limits.get("max_eq_change_db_per_band_per_pass", 1.5))

    if context.audio_mixdown is None:
        logger.warning("[S7_MIXBUS_TONAL_BALANCE] No mixdown in memory to process.")
        _save_tonal_metrics(
            temp_dir=temp_dir,
            contract_id=contract_id,
            style_preset=style_preset,
            pre_band_db=current_band_db,
            post_band_db=current_band_db,
            target_band_db=target_band_db,
            pre_error_rms=prev_error_rms,
            post_error_rms=prev_error_rms,
            eq_gains_db={},
            max_tonal_error_db=max_tonal_error_db,
            max_eq_change_db=max_eq_change_db,
        )
        return True

    if not target_band_db:
        target_band_db = get_style_tonal_profile(style_preset)

    MARGIN_RMS = 0.25
    if prev_error_rms <= max_tonal_error_db + MARGIN_RMS:
        logger.info(f"[S7_MIXBUS_TONAL_BALANCE] error_RMS={prev_error_rms:.2f} <= threshold. No-op.")
        _save_tonal_metrics(
            temp_dir=temp_dir,
            contract_id=contract_id,
            style_preset=style_preset,
            pre_band_db=current_band_db,
            post_band_db=current_band_db,
            target_band_db=target_band_db,
            pre_error_rms=prev_error_rms,
            post_error_rms=prev_error_rms,
            eq_gains_db={},
            max_tonal_error_db=max_tonal_error_db,
            max_eq_change_db=max_eq_change_db,
        )
        return True

    errors_by_band, _ = compute_tonal_error(current_band_db, target_band_db)
    eq_gains_db: Dict[str, float] = {}

    for band_id, err_db in errors_by_band.items():
        desired_gain = -float(err_db)
        gain = max(-max_eq_change_db, min(max_eq_change_db, desired_gain))
        if abs(gain) < 0.1:
            gain = 0.0
        eq_gains_db[band_id] = float(gain)

    # Process in memory
    y = context.audio_mixdown
    y_eq = _apply_multiband_eq_pedalboard(y, context.sample_rate, eq_gains_db)

    # Update context
    context.audio_mixdown = y_eq

    logger.info("[S7_MIXBUS_TONAL_BALANCE] EQ applied in memory.")

    post_band_db = compute_band_energies(y_eq, context.sample_rate)
    _, post_error_rms = compute_tonal_error(post_band_db, target_band_db)

    _save_tonal_metrics(
        temp_dir=temp_dir,
        contract_id=contract_id,
        style_preset=style_preset,
        pre_band_db=current_band_db,
        post_band_db=post_band_db,
        target_band_db=target_band_db,
        pre_error_rms=prev_error_rms,
        post_error_rms=post_error_rms,
        eq_gains_db=eq_gains_db,
        max_tonal_error_db=max_tonal_error_db,
        max_eq_change_db=max_eq_change_db,
    )
    return True

def main() -> None:
    pass

if __name__ == "__main__":
    main()
