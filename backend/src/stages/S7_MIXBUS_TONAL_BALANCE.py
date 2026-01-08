# C:\mix-master\backend\src\stages\S7_MIXBUS_TONAL_BALANCE.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
S7_MIXBUS_TONAL_BALANCE (iterativo, con quality gates, sin parar pipeline)
-----------------------------------------------------------------------
Objetivo:
- Analizar el mixbus (full_song.wav) y estimar error de balance tonal por bandas.
- Aplicar corrección EQ iterativa por bandas hacia el target del estilo, con límites.
- Guardar métricas y report (analysis_*.json + tonal_metrics_*.json + tonal_interactive_*.json).
- NO detener el pipeline nunca: incluso HARD_FAIL/WARNING => return True, pero reflejado en logs/JSON.

Requisitos implementados:
- FIX logger: no dependemos de get_logger; fallback a logger singleton o logging estándar.
- Loop N passes (default 3), max 1.5 dB/banda/pass, max 4.5 dB/banda total.
- Low-band (20–120 Hz) max 1.0 dB/banda/pass (por defecto).
- Convergencia:
  - STOP si error_RMS_REL <= 3.0 dB
  - CONTINUE si mejora >= 0.5 dB y aún no cumple
  - BREAK + WARNING si mejora < 0.2 dB en 2 passes consecutivos
- Seguridad: auto-trim si peak / true-peak estimado suben demasiado.

Notas:
- Se apoya en src.utils.tonal_balance_utils.* (bandas, perfiles, energías).
- No cambia el funcionamiento global del pipeline; sólo enriquece S7.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List, Union

import numpy as np  # noqa: E402
import scipy.signal as spsig  # noqa: E402
import soundfile as sf  # noqa: E402

from pedalboard import Pedalboard, LowShelfFilter, PeakFilter, HighShelfFilter  # noqa: E402

# ---------------------------------------------------------------------
# sys.path guard (evita problemas al importar en runtime por loader)
# ---------------------------------------------------------------------
THIS_DIR = Path(__file__).resolve().parent          # .../src/stages
SRC_DIR = THIS_DIR.parent                           # .../src
PROJECT_ROOT = SRC_DIR.parent                       # .../
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# ---------------------------------------------------------------------
# Logger robusto (evita ImportError por get_logger inexistente)
# ---------------------------------------------------------------------
def _get_logger_container(name: str):
    """
    Devuelve un objeto "logger_container" que idealmente tenga .logger (compat con tu código),
    pero si no existe, devuelve un logging.Logger directo.
    """
    # 1) Intento "nuevo": src.utils.logger.get_logger
    try:
        from src.utils.logger import get_logger as _get_logger  # type: ignore
        return _get_logger(name)
    except Exception:
        pass

    # 2) Intento "legacy": utils.logger.logger (singleton con .logger)
    try:
        from utils.logger import logger as _logger_singleton  # type: ignore
        return _logger_singleton
    except Exception:
        pass

    # 3) Fallback: logging estándar (con .logger wrapper para compat)
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    class _Wrapper:
        def __init__(self, n: str):
            self.logger = logging.getLogger(n)

    return _Wrapper(name)


LOGGER_CONTAINER = _get_logger_container("S7_MIXBUS_TONAL_BALANCE")


def _log():
    """Devuelve un logging.Logger real, sea cual sea el contenedor."""
    return LOGGER_CONTAINER.logger if hasattr(LOGGER_CONTAINER, "logger") else LOGGER_CONTAINER


# ---------------------------------------------------------------------
# Imports utils tonal
# ---------------------------------------------------------------------
from src.utils.tonal_balance_utils import (  # noqa: E402
    compute_band_energies,
    normalize_band_energies,
    get_style_tonal_profile,
    get_freq_bands,
)

# ---------------------------------------------------------------------
# Defaults / tuning (conservadores)
# ---------------------------------------------------------------------
DEFAULT_MAX_TONAL_ERROR_DB = 3.0

DEFAULT_PASSES_MAX = 3
DEFAULT_MAX_EQ_CHANGE_DB_PER_PASS = 1.5
DEFAULT_MAX_EQ_CHANGE_DB_TOTAL = 4.5
DEFAULT_LOW_BAND_MAX_EQ_CHANGE_DB_PER_PASS = 1.0

DEFAULT_MIN_GAIN_DB = 0.10
DEFAULT_SMOOTH_EQ = True

# Gates (según tu spec)
DEFAULT_GATE_IDEAL_DB = 3.0
DEFAULT_GATE_OK_DB = 6.0
DEFAULT_GATE_HARDFAIL_DB = 10.0

# Convergencia
DEFAULT_MIN_IMPROVEMENT_CONTINUE_DB = 0.5
DEFAULT_MIN_IMPROVEMENT_STALL_DB = 0.2
DEFAULT_STALL_CONSEC_PASSES = 2

# Seguridad picos
DEFAULT_SAFETY_PEAK_MAX_DBFS = -1.0   # sample peak
DEFAULT_SAFETY_TP_MAX_DBTP = -1.0     # true-peak estimado (OS4x)
DEFAULT_AUTOTRIM_STEP_DB = 0.75       # entre 0.5 y 1.0 dB


# ---------------------------------------------------------------------
# Helpers dB
# ---------------------------------------------------------------------
def _linear_to_db(x: float) -> float:
    return 20.0 * np.log10(max(1e-12, float(x)))


def _db_to_linear(db: float) -> float:
    return float(10.0 ** (float(db) / 20.0))


def _safe_float(x: Any, default: float) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


# ---------------------------------------------------------------------
# Error relativo
# ---------------------------------------------------------------------
def _compute_error_rel(
    band_rel_db: Dict[str, float],
    target_rel_db: Dict[str, float],
) -> Tuple[float, Dict[str, float]]:
    """
    err = current_rel - target_rel
    RMS sobre intersección de keys finitas.
    """
    keys = sorted(set(band_rel_db.keys()) & set(target_rel_db.keys()))
    if not keys:
        return 0.0, {}

    errs: List[float] = []
    err_by_band: Dict[str, float] = {}
    for k in keys:
        c = band_rel_db.get(k, float("-inf"))
        t = target_rel_db.get(k, float("-inf"))
        try:
            cf = float(c)
            tf = float(t)
        except Exception:
            continue
        if not np.isfinite(cf) or not np.isfinite(tf):
            continue
        e = float(cf - tf)
        err_by_band[k] = e
        errs.append(e)

    err_rms = float(np.sqrt(np.mean(np.square(errs)))) if errs else 0.0
    return err_rms, err_by_band


# ---------------------------------------------------------------------
# Band helpers / caps
# ---------------------------------------------------------------------
def _band_is_low_20_120(band: Dict[str, Any]) -> bool:
    """
    Determina si una banda cae en 20–120 Hz (para cap más estricto).
    Funciona con:
      - band["fmin_hz"], band["fmax_hz"] si existen
      - o fallback por id (sub/low)
    """
    bid = str(band.get("id", "")).lower()
    if bid in {"sub", "low"}:
        return True

    fmin = band.get("fmin_hz", None)
    fmax = band.get("fmax_hz", None)
    center = band.get("center_hz", None)
    try:
        if fmax is not None and float(fmax) <= 120.0:
            return True
        if center is not None and float(center) <= 120.0:
            return True
        if fmin is not None and fmax is not None:
            # si el rango entra significativamente en 20–120
            return float(fmin) < 120.0 and float(fmax) > 20.0 and float(fmax) <= 180.0
    except Exception:
        pass

    return False


def _band_center_hz_fallback(band_id: str) -> float:
    """
    Centro aproximado para reporting si no viene en get_freq_bands().
    Debe coincidir razonablemente con _build_eq_plugins().
    """
    bid = band_id.lower()
    mapping = {
        "sub": 60.0,
        "low": 120.0,
        "low_mid": 350.0,
        "mid": 1000.0,
        "high_mid": 2500.0,
        "presence": 4500.0,
        "air": 10000.0,
        "ultra_air": 14000.0,
    }
    return float(mapping.get(bid, 1000.0))


# ---------------------------------------------------------------------
# De-harsh / edge ratio (se mantiene tu lógica, pero compatible con loop)
# ---------------------------------------------------------------------
def _band_rms_db_welch(
    y: np.ndarray,
    sr: int,
    fmin_hz: float,
    fmax_hz: float,
    nperseg: int = 8192,
    noverlap: int = 4096,
) -> float:
    if y.size == 0:
        return -120.0
    y = np.asarray(y, dtype=np.float32)
    y = y - float(np.mean(y))  # remove DC

    nper = min(int(nperseg), max(2048, int(y.size)))
    nov = min(int(noverlap), max(1024, int(nper // 2)))

    freqs, pxx = spsig.welch(y, fs=int(sr), nperseg=nper, noverlap=nov, scaling="spectrum")
    mask = (freqs >= float(fmin_hz)) & (freqs < float(fmax_hz))
    if not np.any(mask):
        return -120.0

    power = float(np.mean(pxx[mask]))
    rms = float(np.sqrt(max(power, 1e-20)))
    return _linear_to_db(rms)


def _compute_edge_ratio_db(
    y: np.ndarray,
    sr: int,
    edge_band_hz: Tuple[float, float] = (5000.0, 10000.0),
    ref_band_hz: Tuple[float, float] = (1000.0, 4000.0),
) -> float:
    edge_db = _band_rms_db_welch(y, sr, edge_band_hz[0], edge_band_hz[1])
    ref_db = _band_rms_db_welch(y, sr, ref_band_hz[0], ref_band_hz[1])
    return float(edge_db - ref_db)


# ---------------------------------------------------------------------
# Pedalboard EQ (por banda)
# ---------------------------------------------------------------------
def _build_eq_plugins(eq_gains_db: Dict[str, float]) -> List[Any]:
    """
    Mapeo (aprox) a filtros:
    sub        -> LowShelf 60 Hz
    low        -> Peak 120 Hz
    low_mid    -> Peak 350 Hz
    mid        -> Peak 1 kHz
    high_mid   -> Peak 2.5 kHz
    presence   -> Peak 4.5 kHz
    air        -> HighShelf 10 kHz
    ultra_air  -> HighShelf 14 kHz
    """
    if not eq_gains_db:
        return []

    band_to_filter = {
        "sub": lambda g: LowShelfFilter(cutoff_frequency_hz=60, gain_db=g, q=0.7),
        "low": lambda g: PeakFilter(cutoff_frequency_hz=120, q=0.9, gain_db=g),
        "low_mid": lambda g: PeakFilter(cutoff_frequency_hz=350, q=1.0, gain_db=g),
        "mid": lambda g: PeakFilter(cutoff_frequency_hz=1000, q=1.0, gain_db=g),
        "high_mid": lambda g: PeakFilter(cutoff_frequency_hz=2500, q=1.0, gain_db=g),
        "presence": lambda g: PeakFilter(cutoff_frequency_hz=4500, q=0.9, gain_db=g),
        "air": lambda g: HighShelfFilter(cutoff_frequency_hz=10000, gain_db=g, q=0.7),
        "ultra_air": lambda g: HighShelfFilter(cutoff_frequency_hz=14000, gain_db=g, q=0.7),
    }

    plugins: List[Any] = []
    for band in get_freq_bands():
        bid = str(band["id"])
        g = float(eq_gains_db.get(bid, 0.0))
        if abs(g) < 1e-3:
            continue
        fn = band_to_filter.get(bid)
        if fn is not None:
            plugins.append(fn(g))

    return plugins


def _apply_eq_pedalboard(
    audio: np.ndarray,
    sr: int,
    eq_gains_db: Dict[str, float],
    *,
    extra_plugins: Optional[List[Any]] = None,
) -> np.ndarray:
    x = np.asarray(audio, dtype=np.float32)
    if x.size == 0 or sr <= 0:
        return x

    plugins = _build_eq_plugins(eq_gains_db)
    if extra_plugins:
        plugins.extend(list(extra_plugins))

    if not plugins:
        return x

    board = Pedalboard(plugins)
    y = board(x, int(sr))
    return np.asarray(y, dtype=np.float32)


# ---------------------------------------------------------------------
# Seguridad: peak + true-peak aproximado
# ---------------------------------------------------------------------
def _sample_peak_dbfs(y: np.ndarray) -> float:
    if y.size == 0:
        return -120.0
    peak = float(np.max(np.abs(y)))
    return _linear_to_db(peak)


def _true_peak_est_dbtp_os4x(y: np.ndarray, sr: int) -> float:
    """
    Estimación rápida de true peak con oversampling 4x (resample_poly).
    No pretende ser ITU-R BS.1770 completo, pero sirve como guardrail.
    """
    if y.size == 0:
        return -120.0
    try:
        y = np.asarray(y, dtype=np.float32)
        up = 4
        y_up = spsig.resample_poly(y, up=up, down=1)
        peak = float(np.max(np.abs(y_up)))
        return _linear_to_db(peak)
    except Exception:
        # Fallback: sample peak
        return _sample_peak_dbfs(y)


def _apply_autotrim_if_needed(
    y: np.ndarray,
    sr: int,
    *,
    safety_peak_max_dbfs: float,
    safety_tp_max_dbtp: float,
    step_db: float,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Si peak o TP estimado exceden límites, aplica trim en pasos (0.5–1.0 dB típico).
    Devuelve y ajustado + métricas de trim.
    """
    m: Dict[str, Any] = {
        "autotrim_applied_db": 0.0,
        "peak_dbfs_pre": _sample_peak_dbfs(y),
        "tp_est_db_pre": _true_peak_est_dbtp_os4x(y, sr),
        "peak_dbfs_post": None,
        "tp_est_db_post": None,
    }

    peak_pre = float(m["peak_dbfs_pre"])
    tp_pre = float(m["tp_est_db_pre"])

    # ¿Excede?
    exceed_peak = peak_pre > float(safety_peak_max_dbfs) + 1e-6
    exceed_tp = tp_pre > float(safety_tp_max_dbtp) + 1e-6

    if not (exceed_peak or exceed_tp):
        m["peak_dbfs_post"] = peak_pre
        m["tp_est_db_post"] = tp_pre
        return y, m

    # Calcula reducción mínima necesaria (en dB), y aplica en pasos.
    need_reduce_db = 0.0
    if exceed_peak:
        need_reduce_db = max(need_reduce_db, peak_pre - float(safety_peak_max_dbfs))
    if exceed_tp:
        need_reduce_db = max(need_reduce_db, tp_pre - float(safety_tp_max_dbtp))

    # Pasos: al menos 1 paso; step_db ~0.75 por defecto
    steps = int(np.ceil(need_reduce_db / max(1e-6, float(step_db))))
    applied_db = float(min(need_reduce_db, steps * float(step_db)))

    gain = _db_to_linear(-applied_db)
    y2 = np.asarray(y, dtype=np.float32) * float(gain)

    m["autotrim_applied_db"] = applied_db
    m["peak_dbfs_post"] = _sample_peak_dbfs(y2)
    m["tp_est_db_post"] = _true_peak_est_dbtp_os4x(y2, sr)
    return y2, m


# ---------------------------------------------------------------------
# Suavizado de deltas (por vecinos)
# ---------------------------------------------------------------------
def _smooth_by_neighbors(values: Dict[str, float], bands_order: List[str]) -> Dict[str, float]:
    if not values:
        return values
    out = dict(values)
    for i, bid in enumerate(bands_order):
        neigh = [float(values.get(bid, 0.0))]
        if i > 0:
            neigh.append(float(values.get(bands_order[i - 1], 0.0)))
        if i < len(bands_order) - 1:
            neigh.append(float(values.get(bands_order[i + 1], 0.0)))
        out[bid] = float(np.mean(neigh))
    return out


# ---------------------------------------------------------------------
# JSON writers (compat + enriquecido)
# ---------------------------------------------------------------------
def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _write_interactive_comparison(
    temp_dir: Path,
    contract_id: str,
    pre_band_rel_db: Dict[str, float],
    post_band_rel_db: Dict[str, float],
    target_rel_db: Dict[str, float],
    cumulative_eq_db: Dict[str, float],
) -> None:
    out = {
        "contract_id": contract_id,
        "bands": [b["id"] for b in get_freq_bands()],
        "pre_rel_db": pre_band_rel_db,
        "post_rel_db": post_band_rel_db,
        "target_rel_db": target_rel_db,
        "cumulative_eq_gains_db": cumulative_eq_db,
    }
    _write_json(temp_dir / f"tonal_interactive_{contract_id}.json", out)


def _status_from_error(final_err: float, pre_err: float, target_db: float) -> str:
    # NOOP si ya cumplía al inicio
    if pre_err <= target_db + 1e-9:
        return "NOOP"
    if final_err <= DEFAULT_GATE_IDEAL_DB + 1e-9:
        return "OK"  # "IDEAL" lo marcamos en report, pero mantenemos conjunto pedido si quieres
    if final_err <= DEFAULT_GATE_OK_DB + 1e-9:
        return "OK"
    if final_err > DEFAULT_GATE_HARDFAIL_DB + 1e-9:
        return "HARD_FAIL"
    return "WARNING"


def _severity_gate(final_err: float, pre_err: float) -> str:
    # Implementa tu spec exacto:
    # - HARD_FAIL si tras N passes error_RMS_REL > 10
    # - WARNING si > 6
    # - OK si <= 6 (IDEAL si <=3)
    # - NOOP si pre <= 3
    if pre_err <= DEFAULT_GATE_IDEAL_DB + 1e-9:
        return "NOOP"
    if final_err <= DEFAULT_GATE_IDEAL_DB + 1e-9:
        return "OK"  # ideal dentro de OK (se reporta aparte)
    if final_err <= DEFAULT_GATE_OK_DB + 1e-9:
        return "OK"
    if final_err > DEFAULT_GATE_HARDFAIL_DB + 1e-9:
        return "HARD_FAIL"
    return "WARNING"


def _top_band_changes(cumulative_eq_db: Dict[str, float], top_n: int = 5) -> List[Dict[str, Any]]:
    bands = get_freq_bands()
    meta = {str(b["id"]): b for b in bands}

    items = []
    for bid, g in cumulative_eq_db.items():
        g = float(g)
        if abs(g) < 1e-6:
            continue
        b = meta.get(bid, {})
        center = b.get("center_hz", None)
        if center is None:
            # intenta construir desde fmin/fmax
            try:
                fmin = float(b.get("fmin_hz"))
                fmax = float(b.get("fmax_hz"))
                center = float(np.sqrt(fmin * fmax))
            except Exception:
                center = _band_center_hz_fallback(bid)

        items.append({"band_id": bid, "center_hz": float(center), "gain_db": float(g)})

    items.sort(key=lambda d: abs(float(d["gain_db"])), reverse=True)
    return items[: int(top_n)]


# ---------------------------------------------------------------------
# Main stage
# ---------------------------------------------------------------------
def process(contract_id: str) -> bool:
    """
    Lee contrato {temp_dir}/{contract_id}.json, procesa full_song.wav y escribe:
    - full_song_tonal.wav
    - analysis_{contract_id}.json
    - tonal_metrics_{contract_id}.json
    - tonal_interactive_{contract_id}.json

    IMPORTANTE: nunca devuelve False para no detener pipeline.
    """
    log = _log()

    try:
        # Temp dir root configurable, fallback a /tmp
        temp_root = Path(os.environ.get("MIXMASTER_TEMP_ROOT", "/tmp"))
        temp_dir = temp_root / contract_id
        contract_path = temp_dir / f"{contract_id}.json"

        if not contract_path.exists():
            log.error("[S7_MIXBUS_TONAL_BALANCE] No existe contrato: %s", contract_path)
            # No paramos pipeline
            return True

        with contract_path.open("r", encoding="utf-8") as f:
            contract = json.load(f)

        analysis = contract.get("analysis", {}) or {}
        metrics = contract.get("metrics", {}) or {}
        limits = contract.get("limits", {}) or {}

        # style preset
        style_preset_raw = str(analysis.get("style_preset", "balanced"))
        style_preset = style_preset_raw

        # Alias razonables sin tocar utils:
        if style_preset.lower() in {"unknown", "balanced", "default"}:
            style_preset = "neutral"

        # Loop config (defaults + override por contrato)
        passes_max = int(metrics.get("passes_max", DEFAULT_PASSES_MAX))
        passes_max = max(1, min(passes_max, 8))

        max_eq_change_db_per_pass = float(
            limits.get("max_eq_change_db_per_band_per_pass", metrics.get("max_eq_change_db_per_band_per_pass", DEFAULT_MAX_EQ_CHANGE_DB_PER_PASS))
        )
        max_eq_change_db_total = float(
            limits.get("max_eq_change_db_per_band_total", metrics.get("max_eq_change_db_per_band_total", DEFAULT_MAX_EQ_CHANGE_DB_TOTAL))
        )
        lowband_max_eq_change_db_per_pass = float(
            limits.get("lowband_max_eq_change_db_per_pass", metrics.get("lowband_max_eq_change_db_per_pass", DEFAULT_LOW_BAND_MAX_EQ_CHANGE_DB_PER_PASS))
        )

        max_tonal_error_db = float(metrics.get("max_tonal_balance_error_db", DEFAULT_MAX_TONAL_ERROR_DB))
        target_err_db = float(metrics.get("target_tonal_error_rms_rel_db", DEFAULT_GATE_IDEAL_DB))

        min_gain_db = float(metrics.get("min_gain_db", DEFAULT_MIN_GAIN_DB))
        smooth_eq = bool(metrics.get("smooth_eq", DEFAULT_SMOOTH_EQ))

        min_improve_continue_db = float(metrics.get("min_improvement_continue_db", DEFAULT_MIN_IMPROVEMENT_CONTINUE_DB))
        min_improve_stall_db = float(metrics.get("min_improvement_stall_db", DEFAULT_MIN_IMPROVEMENT_STALL_DB))
        stall_consec_passes = int(metrics.get("stall_consecutive_passes", DEFAULT_STALL_CONSEC_PASSES))

        # Seguridad
        safety_peak_max_dbfs = float(metrics.get("safety_peak_max_dbfs", DEFAULT_SAFETY_PEAK_MAX_DBFS))
        safety_tp_max_dbtp = float(metrics.get("safety_true_peak_max_dbtp", DEFAULT_SAFETY_TP_MAX_DBTP))
        autotrim_step_db = float(metrics.get("autotrim_step_db", DEFAULT_AUTOTRIM_STEP_DB))

        # Ruta de audio
        full_song_path = temp_dir / "full_song.wav"
        if not full_song_path.exists():
            p = analysis.get("mixbus_path")
            if p:
                full_song_path = Path(p)

        if not full_song_path.exists():
            log.warning("[S7_MIXBUS_TONAL_BALANCE] No existe full_song.wav: %s (no-op)", full_song_path)
            # No-op tolerante
            out = {
                "contract_id": contract_id,
                "stage_id": contract.get("stage_id", "S7_MIXBUS_TONAL_BALANCE"),
                "style_preset": style_preset_raw,
                "profile_used": None,
                "status_severity": "NOOP",
                "reason": "missing_full_song",
            }
            _write_json(temp_dir / f"analysis_{contract_id}.json", out)
            return True

        # Leer audio
        y, sr = sf.read(full_song_path, always_2d=False)
        y = np.asarray(y, dtype=np.float32)
        if y.ndim > 1:
            y = np.mean(y, axis=1)
        sr = int(sr)

        # Perfil target relativo (si no existe, fallback a neutral)
        target_rel = get_style_tonal_profile(style_preset)
        profile_used = style_preset
        if not isinstance(target_rel, dict) or not target_rel:
            target_rel = get_style_tonal_profile("neutral") or {}
            profile_used = "neutral"

        # Bandas
        freq_bands = get_freq_bands()
        band_ids = [str(b["id"]) for b in freq_bands]

        # Métricas PRE
        pre_band_abs = compute_band_energies(y, sr)
        pre_band_rel = normalize_band_energies(pre_band_abs)
        pre_err_rms_rel, pre_err_by_band_rel = _compute_error_rel(pre_band_rel, target_rel)

        log.info(
            "[S7_MIXBUS_TONAL_BALANCE] PRE: style=%s(profile_used=%s) err_RMS_REL=%.2f dB | peak=%.2f dBFS | tp_est=%.2f dBTP",
            style_preset_raw, profile_used, pre_err_rms_rel, _sample_peak_dbfs(y), _true_peak_est_dbtp_os4x(y, sr)
        )

        # NOOP si ya cumple
        if pre_err_rms_rel <= target_err_db + 1e-9:
            status = "NOOP"
            analysis_out = {
                "contract_id": contract_id,
                "stage_id": contract.get("stage_id", "S7_MIXBUS_TONAL_BALANCE"),
                "style_preset": style_preset_raw,
                "profile_used": profile_used,
                "passes_used": 0,
                "status_severity": status,
                "ideal_met": True,
                "error_rms_rel_db_pre": float(pre_err_rms_rel),
                "error_rms_rel_db_post": float(pre_err_rms_rel),
                "improvement_db": 0.0,
                "band_errors_rel_db_pre": pre_err_by_band_rel,
                "band_errors_rel_db_post": pre_err_by_band_rel,
                "applied_curve": [],
                "max_correction_db": 0.0,
            }
            _write_json(temp_dir / f"analysis_{contract_id}.json", analysis_out)
            _write_interactive_comparison(
                temp_dir=temp_dir,
                contract_id=contract_id,
                pre_band_rel_db=pre_band_rel,
                post_band_rel_db=pre_band_rel,
                target_rel_db=target_rel,
                cumulative_eq_db={},
            )
            return True

        # -----------------------------------------------------------------
        # (Opcional) De-harsh guard (se mantiene tu idea, aplicada siempre igual)
        # -----------------------------------------------------------------
        deharsh_enable = bool(metrics.get("deharsh_enable", True))
        deharsh_edge_ratio_threshold_db = float(metrics.get("deharsh_edge_ratio_threshold_db", -14.0))
        deharsh_max_cut_db = float(metrics.get("deharsh_max_cut_db", 2.5))
        deharsh_sensitivity = float(metrics.get("deharsh_sensitivity", 0.75))
        deharsh_fc_hz = float(metrics.get("deharsh_fc_hz", 6500.0))
        deharsh_q = float(metrics.get("deharsh_q", 0.9))

        # Caps de boosts en HF (evitar estridencia)
        boost_cap_high_mid_db = float(metrics.get("boost_cap_high_mid_db", 0.75))
        boost_cap_presence_db = float(metrics.get("boost_cap_presence_db", 0.50))
        boost_cap_air_db = float(metrics.get("boost_cap_air_db", 0.35))
        boost_cap_ultra_air_db = float(metrics.get("boost_cap_ultra_air_db", 0.25))

        edge_ratio_db_pre = float("nan")
        try:
            edge_ratio_db_pre = _compute_edge_ratio_db(y, sr)
        except Exception:
            pass

        deharsh_cut_db = 0.0
        if (
            deharsh_enable
            and np.isfinite(edge_ratio_db_pre)
            and edge_ratio_db_pre > deharsh_edge_ratio_threshold_db
        ):
            excess = float(edge_ratio_db_pre - deharsh_edge_ratio_threshold_db)
            deharsh_cut_db = min(deharsh_max_cut_db, max(0.0, excess * deharsh_sensitivity))
            # Si deharsh está activo, no permitimos boosts en bandas altas
            boost_cap_high_mid_db = min(boost_cap_high_mid_db, 0.0)
            boost_cap_presence_db = min(boost_cap_presence_db, 0.0)
            boost_cap_air_db = min(boost_cap_air_db, 0.0)
            boost_cap_ultra_air_db = min(boost_cap_ultra_air_db, 0.0)

        if np.isfinite(edge_ratio_db_pre):
            log.info(
                "[S7_MIXBUS_TONAL_BALANCE] De-harsh: edge_ratio_pre=%+.2f dB (thr=%+.2f) cut=%.2f dB",
                edge_ratio_db_pre, deharsh_edge_ratio_threshold_db, deharsh_cut_db
            )
        else:
            log.info("[S7_MIXBUS_TONAL_BALANCE] De-harsh: edge_ratio_pre=nan (skip)")

        extra_plugins_static: List[Any] = []
        if deharsh_cut_db > 0.0:
            extra_plugins_static.append(
                PeakFilter(
                    cutoff_frequency_hz=float(deharsh_fc_hz),
                    q=float(deharsh_q),
                    gain_db=float(-deharsh_cut_db),
                )
            )

        boost_caps = {
            "high_mid": float(boost_cap_high_mid_db),
            "presence": float(boost_cap_presence_db),
            "air": float(boost_cap_air_db),
            "ultra_air": float(boost_cap_ultra_air_db),
        }

        # -----------------------------------------------------------------
        # Loop iterativo
        # -----------------------------------------------------------------
        cumulative_eq: Dict[str, float] = {bid: 0.0 for bid in band_ids}
        y_work = np.asarray(y, dtype=np.float32)

        best_err = float(pre_err_rms_rel)
        best_y = np.asarray(y_work, dtype=np.float32)
        best_cum = dict(cumulative_eq)

        passes_used = 0
        consecutive_stall = 0
        stop_reason = "max_passes"

        prev_err = float(pre_err_rms_rel)

        # Para reporting
        per_pass_history: List[Dict[str, Any]] = []

        for p in range(1, passes_max + 1):
            passes_used = p

            # Medición current
            band_abs = compute_band_energies(y_work, sr)
            band_rel = normalize_band_energies(band_abs)
            err_rms, err_by_band = _compute_error_rel(band_rel, target_rel)

            # Curva deseada: g_desired = -err (si current>target, recorta; si current<target, realza)
            # Limitamos por max_tonal_error_db (evitar correcciones por medición extrema)
            desired: Dict[str, float] = {}
            for b in freq_bands:
                bid = str(b["id"])
                e = float(err_by_band.get(bid, 0.0))
                e = float(np.clip(e, -max_tonal_error_db, max_tonal_error_db))
                g = float(-e)

                # Boost caps HF
                if bid in boost_caps and g > 0.0:
                    g = float(min(g, boost_caps[bid]))

                desired[bid] = float(g)

            # Delta por pass = clamp(desired - cumulative, cap_pass) y clamp total
            deltas: Dict[str, float] = {}
            for b in freq_bands:
                bid = str(b["id"])
                target_g = float(desired.get(bid, 0.0))
                cur_g = float(cumulative_eq.get(bid, 0.0))
                raw_delta = float(target_g - cur_g)

                # cap por pass (low-band más estricto)
                cap_pass = lowband_max_eq_change_db_per_pass if _band_is_low_20_120(b) else max_eq_change_db_per_pass
                raw_delta = float(np.clip(raw_delta, -cap_pass, cap_pass))

                # cap total (acumulado)
                new_g = float(np.clip(cur_g + raw_delta, -max_eq_change_db_total, max_eq_change_db_total))
                delta = float(new_g - cur_g)

                deltas[bid] = delta

            # Suavizado opcional (en deltas)
            if smooth_eq:
                deltas = _smooth_by_neighbors(deltas, band_ids)

            # Eliminar deltas muy pequeños
            deltas = {k: float(v) for k, v in deltas.items() if abs(float(v)) >= float(min_gain_db)}

            # Si no hay nada que aplicar, salimos con WARNING (no converge / no actionable)
            if not deltas and deharsh_cut_db <= 0.0:
                stop_reason = "no_actionable_deltas"
                log.warning("[S7_MIXBUS_TONAL_BALANCE] Pass %d: no hay deltas aplicables (min_gain=%.2f).", p, min_gain_db)
                break

            # Aplica EQ del pass (solo deltas), pero acumulando en state
            # (Pedalboard encadena filtros; por eso aplicamos deltas directamente en audio actual)
            y_next = _apply_eq_pedalboard(y_work, sr, deltas, extra_plugins=extra_plugins_static)

            # Seguridad picos: autotrim si excede
            y_next, trim_metrics = _apply_autotrim_if_needed(
                y_next,
                sr,
                safety_peak_max_dbfs=safety_peak_max_dbfs,
                safety_tp_max_dbtp=safety_tp_max_dbtp,
                step_db=autotrim_step_db,
            )

            # Actualiza acumulado (solo lo que realmente aplicamos)
            for bid, d in deltas.items():
                cumulative_eq[bid] = float(cumulative_eq.get(bid, 0.0) + float(d))

            # Mide post-pass
            band_abs_post = compute_band_energies(y_next, sr)
            band_rel_post = normalize_band_energies(band_abs_post)
            err_rms_post, _ = _compute_error_rel(band_rel_post, target_rel)

            improvement = float(prev_err - err_rms_post)

            per_pass_history.append({
                "pass": p,
                "err_rms_rel_db_pre_pass": float(prev_err),
                "err_rms_rel_db_post_pass": float(err_rms_post),
                "improvement_db": float(improvement),
                "deltas_db": deltas,
                "autotrim": trim_metrics,
            })

            log.info(
                "[S7_MIXBUS_TONAL_BALANCE] Pass %d/%d: err %.2f -> %.2f (impr=%.2f dB) | max|delta|=%.2f dB | autotrim=%.2f dB",
                p, passes_max, prev_err, err_rms_post, improvement,
                float(max([abs(v) for v in deltas.values()] + [0.0])),
                float(trim_metrics.get("autotrim_applied_db", 0.0)),
            )

            # Actualiza best
            if err_rms_post < best_err - 1e-9:
                best_err = float(err_rms_post)
                best_y = np.asarray(y_next, dtype=np.float32)
                best_cum = dict(cumulative_eq)

            # Stop conditions
            if err_rms_post <= target_err_db + 1e-9:
                stop_reason = "target_met"
                y_work = y_next
                prev_err = float(err_rms_post)
                break

            # Stall tracking
            if improvement < min_improve_stall_db:
                consecutive_stall += 1
            else:
                consecutive_stall = 0

            if consecutive_stall >= stall_consec_passes:
                stop_reason = "stall_warning"
                log.warning(
                    "[S7_MIXBUS_TONAL_BALANCE] BREAK por stall: improvement < %.2f dB en %d passes consecutivos.",
                    min_improve_stall_db, stall_consec_passes
                )
                y_work = y_next
                prev_err = float(err_rms_post)
                break

            # Continue policy
            if improvement >= min_improve_continue_db:
                y_work = y_next
                prev_err = float(err_rms_post)
                continue

            # Si no mejora lo suficiente para "continue", aún así seguimos hasta N (pero sin resetear stall)
            y_work = y_next
            prev_err = float(err_rms_post)

        # Use best result (protege contra overshoot o regresión en el último pass)
        y_final = np.asarray(best_y, dtype=np.float32)
        cumulative_final = dict(best_cum)

        # Métricas POST finales
        post_band_abs = compute_band_energies(y_final, sr)
        post_band_rel = normalize_band_energies(post_band_abs)
        post_err_rms_rel, post_err_by_band_rel = _compute_error_rel(post_band_rel, target_rel)

        improvement_total = float(pre_err_rms_rel - post_err_rms_rel)

        # Severity gates (sin detener pipeline)
        status_severity = _severity_gate(post_err_rms_rel, pre_err_rms_rel)
        ideal_met = bool(post_err_rms_rel <= DEFAULT_GATE_IDEAL_DB + 1e-9)
        ok_met = bool(post_err_rms_rel <= DEFAULT_GATE_OK_DB + 1e-9)
        hard_fail = bool(post_err_rms_rel > DEFAULT_GATE_HARDFAIL_DB + 1e-9)

        max_correction_db = float(max([abs(v) for v in cumulative_final.values()] + [0.0]))

        # Curva aplicada (para reporte/front)
        applied_curve = []
        for bid, g in cumulative_final.items():
            if abs(float(g)) < 1e-6:
                continue
            applied_curve.append({
                "band_id": bid,
                "band_center_hz": _band_center_hz_fallback(bid),
                "gain_db": float(g),
            })

        # Escribe WAV resultado
        out_path = temp_dir / "full_song_tonal.wav"
        sf.write(out_path, y_final, sr)

        # JSON "analysis_*" enriquecido (mantiene filosofía del otro S7 análisis)
        analysis_out: Dict[str, Any] = {
            "contract_id": contract_id,
            "stage_id": contract.get("stage_id", "S7_MIXBUS_TONAL_BALANCE"),
            "style_preset": style_preset_raw,
            "profile_used": profile_used,
            "passes_used": int(passes_used),
            "stop_reason": stop_reason,
            "status_severity": status_severity,  # {NOOP, OK, WARNING, HARD_FAIL}
            "ideal_met": ideal_met,
            "ok_met": ok_met,
            "hard_fail": hard_fail,
            "error_rms_rel_db_pre": float(pre_err_rms_rel),
            "error_rms_rel_db_post": float(post_err_rms_rel),
            "improvement_db": float(improvement_total),
            "band_errors_rel_db_pre": pre_err_by_band_rel,
            "band_errors_rel_db_post": post_err_by_band_rel,
            "max_correction_db": float(max_correction_db),
            "applied_curve": _top_band_changes(cumulative_final, top_n=9999),  # lista completa con center_hz
            "top_5_changes": _top_band_changes(cumulative_final, top_n=5),
            "limits": {
                "passes_max": int(passes_max),
                "max_eq_change_db_per_band_per_pass": float(max_eq_change_db_per_pass),
                "max_eq_change_db_per_band_total": float(max_eq_change_db_total),
                "lowband_max_eq_change_db_per_pass": float(lowband_max_eq_change_db_per_pass),
            },
            "convergence": {
                "target_error_rms_rel_db": float(target_err_db),
                "min_improvement_continue_db": float(min_improve_continue_db),
                "min_improvement_stall_db": float(min_improve_stall_db),
                "stall_consecutive_passes": int(stall_consec_passes),
            },
            "safety": {
                "safety_peak_max_dbfs": float(safety_peak_max_dbfs),
                "safety_true_peak_max_dbtp": float(safety_tp_max_dbtp),
                "autotrim_step_db": float(autotrim_step_db),
                "peak_dbfs_post": float(_sample_peak_dbfs(y_final)),
                "tp_est_db_post": float(_true_peak_est_dbtp_os4x(y_final, sr)),
            },
            "deharsh": {
                "edge_ratio_db_pre": float(edge_ratio_db_pre) if np.isfinite(edge_ratio_db_pre) else None,
                "deharsh_cut_db": float(deharsh_cut_db),
                "boost_caps_db": boost_caps,
            },
            "per_pass": per_pass_history,
            "outputs": {
                "full_song_tonal_wav": str(out_path),
                "analysis_json": str(temp_dir / f"analysis_{contract_id}.json"),
                "tonal_metrics_json": str(temp_dir / f"tonal_metrics_{contract_id}.json"),
                "tonal_interactive_json": str(temp_dir / f"tonal_interactive_{contract_id}.json"),
            },
        }

        _write_json(temp_dir / f"analysis_{contract_id}.json", analysis_out)

        # tonal_metrics_{cid}.json (compat con tu front/uso actual)
        tonal_metrics = {
            "pre": {
                "band_db_abs": pre_band_abs,
                "band_db_rel": pre_band_rel,
                "error_rms_rel_db": float(pre_err_rms_rel),
                "error_by_band_rel_db": pre_err_by_band_rel,
            },
            "target_rel_db": target_rel,
            "post": {
                "band_db_abs": post_band_abs,
                "band_db_rel": post_band_rel,
                "error_rms_rel_db": float(post_err_rms_rel),
                "error_by_band_rel_db": post_err_by_band_rel,
            },
            "cumulative_eq_gains_db": cumulative_final,
            "status_severity": status_severity,
            "passes_used": int(passes_used),
            "improvement_db": float(improvement_total),
            "profile_used": profile_used,
            "stop_reason": stop_reason,
        }
        _write_json(temp_dir / f"tonal_metrics_{contract_id}.json", tonal_metrics)

        # JSON interactivo
        _write_interactive_comparison(
            temp_dir=temp_dir,
            contract_id=contract_id,
            pre_band_rel_db=pre_band_rel,
            post_band_rel_db=post_band_rel,
            target_rel_db=target_rel,
            cumulative_eq_db=cumulative_final,
        )

        # Log final conciso (reporte)
        top5 = analysis_out["top_5_changes"]
        top5_str = ", ".join([f'{t["band_id"]}@{t["center_hz"]:.0f}Hz {t["gain_db"]:+.2f}dB' for t in top5]) if top5 else "none"

        ideal_tag = "IDEAL" if ideal_met else ("OK" if ok_met else status_severity)

        log.info(
            "[S7_MIXBUS_TONAL_BALANCE] DONE: %s | passes=%d | err %.2f -> %.2f (impr=%.2f) | top5: %s",
            ideal_tag, passes_used, pre_err_rms_rel, post_err_rms_rel, improvement_total, top5_str
        )

        # HARD_FAIL se reporta, pero no paramos pipeline
        if hard_fail:
            log.error(
                "[S7_MIXBUS_TONAL_BALANCE] HARD_FAIL (sin detener pipeline): error_RMS_REL=%.2f dB > %.2f dB",
                post_err_rms_rel, DEFAULT_GATE_HARDFAIL_DB
            )
        elif status_severity == "WARNING":
            log.warning(
                "[S7_MIXBUS_TONAL_BALANCE] WARNING: error_RMS_REL=%.2f dB > %.2f dB",
                post_err_rms_rel, DEFAULT_GATE_OK_DB
            )

        return True

    except Exception as e:
        # Nunca devolvemos False
        _log().exception("[S7_MIXBUS_TONAL_BALANCE] Exception tolerada (pipeline sigue): %s", e)
        # Intento de escribir un analysis minimal para que el summary lo refleje
        try:
            temp_root = Path(os.environ.get("MIXMASTER_TEMP_ROOT", "/tmp"))
            temp_dir = temp_root / contract_id
            _write_json(
                temp_dir / f"analysis_{contract_id}.json",
                {
                    "contract_id": contract_id,
                    "stage_id": "S7_MIXBUS_TONAL_BALANCE",
                    "status_severity": "HARD_FAIL",
                    "error": str(e),
                },
            )
        except Exception:
            pass
        return True


if __name__ == "__main__":
    cid = sys.argv[1] if len(sys.argv) > 1 else "S7_MIXBUS_TONAL_BALANCE"
    ok = process(cid)
    sys.exit(0 if ok else 0)  # nunca “falla” a nivel proceso para no romper orquestación
