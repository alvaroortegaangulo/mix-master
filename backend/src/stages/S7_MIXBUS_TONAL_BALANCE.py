# C:\mix-master\backend\src\stages\S7_MIXBUS_TONAL_BALANCE.py

from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from pedalboard import (  # noqa: E402
    Pedalboard,
    LowShelfFilter,
    HighShelfFilter,
    PeakFilter,
)

from utils.analysis_utils import get_temp_dir  # noqa: E402
from utils.tonal_balance_utils import (  # noqa: E402
    get_freq_bands,
    compute_band_energies,
    get_style_tonal_profile,
)

try:
    from context import PipelineContext
except ImportError:
    PipelineContext = None  # type: ignore


# ---------------------------------------------------------------------
# Helpers REL / error consistente
# ---------------------------------------------------------------------

def _finite_values(d: Dict[str, float]) -> list[float]:
    vals: list[float] = []
    for v in d.values():
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if fv == float("-inf"):
            continue
        vals.append(fv)
    return vals


def normalize_bands_db(
    band_db_abs: Dict[str, float],
) -> Tuple[Dict[str, float], float]:
    vals = _finite_values(band_db_abs)
    if not vals:
        return {k: float("-inf") for k in band_db_abs.keys()}, 0.0
    mean_abs = sum(vals) / float(len(vals))
    rel: Dict[str, float] = {}
    for k, v in band_db_abs.items():
        try:
            fv = float(v)
        except (TypeError, ValueError):
            rel[k] = float("-inf")
            continue
        if fv == float("-inf"):
            rel[k] = float("-inf")
        else:
            rel[k] = float(fv - mean_abs)
    return rel, float(mean_abs)


def compute_error_by_band_rel(
    current_rel: Dict[str, float],
    target_rel: Dict[str, float],
) -> Tuple[Dict[str, float], float]:
    err: Dict[str, float] = {}
    sq: list[float] = []

    keys = set(current_rel.keys()) | set(target_rel.keys())
    for k in keys:
        c = current_rel.get(k, float("-inf"))
        t = target_rel.get(k, float("-inf"))
        try:
            cf = float(c)
            tf = float(t)
        except (TypeError, ValueError):
            continue
        if cf == float("-inf") or tf == float("-inf"):
            continue
        e = float(cf - tf)  # definido: current - target
        err[k] = e
        sq.append(e * e)

    rms = (sum(sq) / float(len(sq))) ** 0.5 if sq else 0.0
    return err, float(rms)


# ---------------------------------------------------------------------
# Load analysis
# ---------------------------------------------------------------------

def load_analysis(contract_id: str) -> Dict[str, Any]:
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"
    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")
    with analysis_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_analysis_with_context(context: PipelineContext) -> Dict[str, Any]:
    stage_id = context.stage_id
    temp_dir = context.get_stage_dir()
    analysis_path = temp_dir / f"analysis_{stage_id}.json"
    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")
    with analysis_path.open("r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------
# EQ multibanda con Pedalboard
# ---------------------------------------------------------------------

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

        # Low shelf
        if idx == 0 or f_min <= 0.0:
            cutoff = max(20.0, f_max if nyquist is None else min(f_max, nyquist))
            plugins.append(LowShelfFilter(cutoff_frequency_hz=cutoff, gain_db=gain_db, q=0.707))
            continue

        # High shelf
        if idx == n_bands - 1 or (nyquist is not None and f_max >= nyquist * 0.9):
            cutoff = max(20.0, f_min if nyquist is None else min(f_min, nyquist))
            plugins.append(HighShelfFilter(cutoff_frequency_hz=cutoff, gain_db=gain_db, q=0.707))
            continue

        # Peak
        center = (f_min * f_max) ** 0.5 if f_min > 0.0 else f_max
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
    return np.asarray(y, dtype=np.float32)


# ---------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------

def _save_tonal_metrics(
    temp_dir: Path,
    contract_id: str,
    style_preset: str,
    pre_band_db_rel: Dict[str, float],
    post_band_db_rel: Dict[str, float],
    target_band_db_rel: Dict[str, float],
    pre_band_db_abs: Dict[str, float],
    post_band_db_abs: Dict[str, float],
    target_band_db_abs: Dict[str, float],
    pre_error_rms: float,
    post_error_rms: float,
    eq_gains_db: Dict[str, float],
    max_tonal_error_db: float,
    max_eq_change_db: float,
) -> None:
    metrics_path = temp_dir / "tonal_metrics_S7_MIXBUS_TONAL_BALANCE.json"
    data = {
        "contract_id": contract_id,
        "style_preset": style_preset,
        "max_tonal_balance_error_db": max_tonal_error_db,
        "max_eq_change_db_per_band_per_pass": max_eq_change_db,
        "pre": {
            "band_db": pre_band_db_rel,          # REL (shape)
            "band_db_abs": pre_band_db_abs,      # ABS (diag)
            "error_rms_db": pre_error_rms,
        },
        "post": {
            "band_db": post_band_db_rel,         # REL (shape)
            "band_db_abs": post_band_db_abs,     # ABS (diag)
            "error_rms_db": post_error_rms,
        },
        "target_band_db": target_band_db_rel,    # REL (shape)
        "target_band_db_abs": target_band_db_abs,
        "eq_gains_db": eq_gains_db,
    }

    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.logger.info(f"[S7_MIXBUS_TONAL_BALANCE] Métricas guardadas en: {metrics_path}")


# ---------------------------------------------------------------------
# Stage principal
# ---------------------------------------------------------------------

def _smooth_gains(bands: List[Dict[str, Any]], gains: Dict[str, float]) -> Dict[str, float]:
    """
    Suavizado 3-tap por orden de bandas (evita correcciones serrucho).
    """
    ids = [b.get("id") for b in bands if b.get("id") is not None]
    out: Dict[str, float] = dict(gains)

    for i, bid in enumerate(ids):
        g0 = float(gains.get(bid, 0.0))
        g_prev = float(gains.get(ids[i - 1], g0)) if i > 0 else g0
        g_next = float(gains.get(ids[i + 1], g0)) if i < (len(ids) - 1) else g0
        out[bid] = float((g_prev + 2.0 * g0 + g_next) / 4.0)

    return out


def _detect_global_gain_like(gains: Dict[str, float], min_bands: int = 3) -> Tuple[bool, float, float, int]:
    """
    Detecta el patrón "todas las bandas casi igual" => trim global.
    """
    vals = [float(v) for v in gains.values() if abs(float(v)) >= 0.10]
    n = len(vals)
    if n < min_bands:
        return False, 0.0, 0.0, n

    mean = sum(vals) / float(n)
    var = sum((v - mean) ** 2 for v in vals) / float(n)
    std = var ** 0.5

    # Si casi no hay varianza pero hay media apreciable -> es un global gain
    is_global = (std <= 0.12) and (abs(mean) >= 0.25)
    return is_global, float(mean), float(std), n


def process(context: PipelineContext, *args) -> bool:
    contract_id = context.stage_id
    temp_dir = context.get_stage_dir()

    # 1) Cargar análisis
    try:
        analysis = load_analysis_with_context(context)
    except FileNotFoundError:
        analysis = load_analysis(contract_id)

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}
    session: Dict[str, Any] = analysis.get("session", {}) or {}

    style_preset = analysis.get("style_preset", "default")
    tonal_info: Dict[str, Any] = session.get("tonal_bands", {}) or {}

    # Umbrales
    max_tonal_error_db = float(metrics.get("max_tonal_balance_error_db", 3.0))
    max_eq_change_db = float(limits.get("max_eq_change_db_per_band_per_pass", 1.5))

    # Parámetros de control (nuevos defaults seguros)
    eq_k = float(metrics.get("eq_proportional_factor", 0.75))  # <1 para evitar overshoot
    do_smooth = bool(metrics.get("smooth_eq_gains", True))
    rollback_if_worse = bool(metrics.get("rollback_if_worse", True))
    worsen_margin_db = float(metrics.get("worsen_margin_db", 0.05))  # si empeora más que esto, rollback
    min_gain_db = float(metrics.get("min_gain_db", 0.10))

    full_song_path = temp_dir / "full_song.wav"
    if not full_song_path.exists():
        logger.logger.info(f"[S7_MIXBUS_TONAL_BALANCE] No existe {full_song_path}; no se puede aplicar EQ.")
        return True

    # 2) Obtener medición PRE (REL preferente; fallback a ABS->REL)
    pre_band_rel = tonal_info.get("current_band_db", {}) or {}
    tgt_band_rel = tonal_info.get("target_band_db", {}) or {}

    pre_band_abs = tonal_info.get("current_band_db_abs", {}) or {}
    tgt_band_abs = tonal_info.get("target_band_db_abs", {}) or {}

    if not tgt_band_abs:
        tgt_band_abs = get_style_tonal_profile(style_preset) or {}

    if not pre_band_abs:
        # Si análisis no guardó ABS, medimos aquí (fallback)
        y0, sr0 = sf.read(full_song_path, always_2d=False)
        y0 = np.asarray(y0, dtype=np.float32)
        pre_band_abs = compute_band_energies(y0, sr0)

    # Si REL está vacío o lleno de -inf, reconstruimos
    def _looks_empty_rel(d: Dict[str, float]) -> bool:
        return (not d) or all((v == float("-inf")) for v in d.values())

    if _looks_empty_rel(pre_band_rel):
        pre_band_rel, _ = normalize_bands_db(pre_band_abs)
    if _looks_empty_rel(tgt_band_rel):
        tgt_band_rel, _ = normalize_bands_db(tgt_band_abs)

    pre_err_by_band, pre_error_rms = compute_error_by_band_rel(pre_band_rel, tgt_band_rel)

    # 3) Idempotencia
    MARGIN_RMS = 0.25
    if pre_error_rms <= max_tonal_error_db + MARGIN_RMS:
        logger.logger.info(
            f"[S7_MIXBUS_TONAL_BALANCE] error_RMS_REL={pre_error_rms:.2f} dB "
            f"<= umbral {max_tonal_error_db:.2f} dB (+{MARGIN_RMS:.2f}); no-op."
        )
        # Guardar métricas mínimas (post == pre)
        _save_tonal_metrics(
            temp_dir=temp_dir,
            contract_id=contract_id,
            style_preset=style_preset,
            pre_band_db_rel=pre_band_rel,
            post_band_db_rel=pre_band_rel,
            target_band_db_rel=tgt_band_rel,
            pre_band_db_abs=pre_band_abs,
            post_band_db_abs=pre_band_abs,
            target_band_db_abs=tgt_band_abs,
            pre_error_rms=pre_error_rms,
            post_error_rms=pre_error_rms,
            eq_gains_db={},
            max_tonal_error_db=max_tonal_error_db,
            max_eq_change_db=max_eq_change_db,
        )
        return True

    # 4) Calcular ganancias por banda (REL)
    bands = get_freq_bands()
    eq_gains_db: Dict[str, float] = {}

    for b in bands:
        bid = b.get("id")
        if not bid:
            continue
        err = float(pre_err_by_band.get(bid, 0.0))
        desired = -eq_k * err  # si current > target => err>0 => desired negativo (recorta esa banda)
        gain = max(-max_eq_change_db, min(max_eq_change_db, desired))
        eq_gains_db[str(bid)] = float(gain)

    # Suavizado opcional
    if do_smooth:
        eq_gains_db = _smooth_gains(bands, eq_gains_db)

    # Zero small
    for k in list(eq_gains_db.keys()):
        if abs(float(eq_gains_db[k])) < min_gain_db:
            eq_gains_db[k] = 0.0

    # Detectar patrón de “trim global”
    is_global, mean_g, std_g, n_sig = _detect_global_gain_like(eq_gains_db, min_bands=3)
    if is_global:
        logger.logger.info(
            f"[S7_MIXBUS_TONAL_BALANCE] Detectado patrón de ganancia global (mean={mean_g:+.2f} dB, std={std_g:.2f}, bands={n_sig}). "
            "Este stage no debe hacer atenuación global → no-op."
        )
        eq_gains_db = {k: 0.0 for k in eq_gains_db.keys()}

    # Si quedó todo a 0, no-op
    if all(abs(float(v)) < 1e-6 for v in eq_gains_db.values()):
        logger.logger.info("[S7_MIXBUS_TONAL_BALANCE] EQ resultante ~0 dB en todas las bandas → no-op.")
        _save_tonal_metrics(
            temp_dir=temp_dir,
            contract_id=contract_id,
            style_preset=style_preset,
            pre_band_db_rel=pre_band_rel,
            post_band_db_rel=pre_band_rel,
            target_band_db_rel=tgt_band_rel,
            pre_band_db_abs=pre_band_abs,
            post_band_db_abs=pre_band_abs,
            target_band_db_abs=tgt_band_abs,
            pre_error_rms=pre_error_rms,
            post_error_rms=pre_error_rms,
            eq_gains_db={},
            max_tonal_error_db=max_tonal_error_db,
            max_eq_change_db=max_eq_change_db,
        )
        return True

    logger.logger.info("[S7_MIXBUS_TONAL_BALANCE] Ganancias de EQ por banda (dB):")
    for b in bands:
        bid = b.get("id")
        if not bid:
            continue
        g = float(eq_gains_db.get(str(bid), 0.0))
        if abs(g) >= min_gain_db:
            logger.logger.info(f"  - {bid}: {g:+.2f} dB")

    # 5) Aplicar EQ
    y, sr = sf.read(full_song_path, always_2d=False)
    y = np.asarray(y, dtype=np.float32)
    y_before = y.copy()

    y_eq = _apply_multiband_eq_pedalboard(y, sr, eq_gains_db)
    sf.write(full_song_path, y_eq, sr, subtype="FLOAT")
    logger.logger.info(f"[S7_MIXBUS_TONAL_BALANCE] EQ aplicada sobre {full_song_path.name}.")

    # 6) Re-medición post (ABS->REL) y rollback si empeora
    post_band_abs = compute_band_energies(y_eq, sr)
    post_band_rel, _ = normalize_bands_db(post_band_abs)
    _post_err_by_band, post_error_rms = compute_error_by_band_rel(post_band_rel, tgt_band_rel)

    logger.logger.info(
        f"[S7_MIXBUS_TONAL_BALANCE] error_RMS_REL pre={pre_error_rms:.2f} dB, post={post_error_rms:.2f} dB."
    )

    if rollback_if_worse and (post_error_rms > pre_error_rms + worsen_margin_db):
        logger.logger.info(
            f"[S7_MIXBUS_TONAL_BALANCE] Rollback: el error empeoró (+{post_error_rms - pre_error_rms:.2f} dB). "
            "Se revierte full_song.wav y se anula EQ."
        )
        sf.write(full_song_path, y_before, sr, subtype="FLOAT")

        # Métricas rollback (post == pre)
        _save_tonal_metrics(
            temp_dir=temp_dir,
            contract_id=contract_id,
            style_preset=style_preset,
            pre_band_db_rel=pre_band_rel,
            post_band_db_rel=pre_band_rel,
            target_band_db_rel=tgt_band_rel,
            pre_band_db_abs=pre_band_abs,
            post_band_db_abs=pre_band_abs,
            target_band_db_abs=tgt_band_abs,
            pre_error_rms=pre_error_rms,
            post_error_rms=pre_error_rms,
            eq_gains_db={},
            max_tonal_error_db=max_tonal_error_db,
            max_eq_change_db=max_eq_change_db,
        )
        return True

    # 7) Guardar métricas finales
    _save_tonal_metrics(
        temp_dir=temp_dir,
        contract_id=contract_id,
        style_preset=style_preset,
        pre_band_db_rel=pre_band_rel,
        post_band_db_rel=post_band_rel,
        target_band_db_rel=tgt_band_rel,
        pre_band_db_abs=pre_band_abs,
        post_band_db_abs=post_band_abs,
        target_band_db_abs=tgt_band_abs,
        pre_error_rms=pre_error_rms,
        post_error_rms=post_error_rms,
        eq_gains_db=eq_gains_db,
        max_tonal_error_db=max_tonal_error_db,
        max_eq_change_db=max_eq_change_db,
    )
    return True


def main() -> None:
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S7_MIXBUS_TONAL_BALANCE.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]
    temp_dir = get_temp_dir(contract_id, create=False)
    temp_root = temp_dir.parent
    job_id = temp_root.name

    if PipelineContext:
        ctx = PipelineContext(stage_id=contract_id, job_id=job_id, temp_root=temp_root)
        process(ctx)
    else:
        logger.logger.info("Error: PipelineContext no disponible en legacy main wrapper")
        sys.exit(1)


if __name__ == "__main__":
    main()
