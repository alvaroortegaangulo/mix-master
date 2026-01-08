# C:\mix-master\backend\src\stages\S7_MIXBUS_TONAL_BALANCE.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
S7_MIXBUS_TONAL_BALANCE
-----------------------
Objetivo:
- Analizar el mixbus (full_song.wav) y estimar un error de balance tonal por bandas.
- Aplicar correcciones EQ suaves (por banda) para acercar el perfil al target del estilo.
- Guardar métricas y generar un full_song_tonal.wav.

Notas:
- El stage trabaja con perfiles por estilo desde utils/tonal_balance_utils.py
- Se usa Pedalboard para aplicar EQ.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

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

from src.utils.logger import get_logger  # noqa: E402
from src.utils.tonal_balance_utils import (  # noqa: E402
    compute_band_energies,
    normalize_band_energies,
    get_style_tonal_profile,
    get_freq_bands,
)

logger = get_logger("S7_MIXBUS_TONAL_BALANCE")

DEFAULT_MAX_TONAL_ERROR_DB = 3.0
DEFAULT_MAX_EQ_CHANGE_DB = 1.5


# ---------------------------------------------------------------------
# Helpers dB
# ---------------------------------------------------------------------
def linear_to_db(x: float) -> float:
    return 20.0 * np.log10(max(1e-12, float(x)))


def db_to_linear(db: float) -> float:
    return float(10.0 ** (float(db) / 20.0))


# ---------------------------------------------------------------------
# Error (relativo y absoluto alineado)
# ---------------------------------------------------------------------
def compute_error_rel(
    band_rel_db: Dict[str, float], target_rel_db: Dict[str, float]
) -> Tuple[float, Dict[str, float]]:
    """
    Error por banda en espacio relativo (ya normalizado por media).
    err = band_rel_db - target_rel_db

    Devuelve:
    - RMS del error
    - dict error por banda
    """
    keys = sorted(set(band_rel_db.keys()) & set(target_rel_db.keys()))
    if not keys:
        return 0.0, {}

    errs: List[float] = []
    err_by_band: Dict[str, float] = {}
    for k in keys:
        e = float(band_rel_db[k] - target_rel_db[k])
        err_by_band[k] = e
        errs.append(e)

    err_rms = float(np.sqrt(np.mean(np.square(errs)))) if errs else 0.0
    return err_rms, err_by_band


def compute_error_aligned_abs(
    band_abs_db: Dict[str, float], target_rel_db: Dict[str, float]
) -> Tuple[float, Dict[str, float], float]:
    """
    A partir de energías absolutas (dB) del audio y un target relativo,
    calcula un target absoluto alineado con el audio (offset global) y
    devuelve RMS del error absoluto alineado.

    target_abs_db[k] = target_rel_db[k] + global_offset_db

    global_offset_db se elige para minimizar el error (media de (band_abs_db - target_rel_db)).
    """
    keys = sorted(set(band_abs_db.keys()) & set(target_rel_db.keys()))
    if not keys:
        return 0.0, {}, 0.0

    diffs = [float(band_abs_db[k] - target_rel_db[k]) for k in keys]
    global_offset_db = float(np.mean(diffs))

    err_by_band: Dict[str, float] = {}
    errs: List[float] = []
    for k in keys:
        target_abs = float(target_rel_db[k] + global_offset_db)
        e = float(band_abs_db[k] - target_abs)
        err_by_band[k] = e
        errs.append(e)

    err_rms = float(np.sqrt(np.mean(np.square(errs)))) if errs else 0.0
    return err_rms, err_by_band, global_offset_db


def _band_rms_db_welch(
    y: np.ndarray,
    sr: int,
    fmin_hz: float,
    fmax_hz: float,
    nperseg: int = 8192,
    noverlap: int = 4096,
) -> float:
    """Band RMS en dB usando Welch PSD (estable y con ventana)."""
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
    return linear_to_db(rms)


def compute_edge_ratio_db(
    y: np.ndarray,
    sr: int,
    edge_band_hz: Tuple[float, float] = (5000.0, 10000.0),
    ref_band_hz: Tuple[float, float] = (1000.0, 4000.0),
) -> float:
    """
    Proxy simple de estridencia/edge:
    edge_ratio_db = RMS(5–10k) - RMS(1–4k)

    Menos negativo => más brillante/edgy.
    """
    edge_db = _band_rms_db_welch(y, sr, edge_band_hz[0], edge_band_hz[1])
    ref_db = _band_rms_db_welch(y, sr, ref_band_hz[0], ref_band_hz[1])
    return float(edge_db - ref_db)


# ---------------------------------------------------------------------
# Pedalboard EQ (por banda)
# ---------------------------------------------------------------------
def _build_eq_plugins(eq_gains_db: Dict[str, float]) -> List[Any]:
    """
    Construye plugins por banda.
    Bandas definidas en tonal_balance_utils.get_freq_bands()

    Mapeo (aprox):
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
        bid = band["id"]
        g = float(eq_gains_db.get(bid, 0.0))
        if abs(g) < 1e-3:
            continue
        fn = band_to_filter.get(bid)
        if fn is not None:
            plugins.append(fn(g))

    return plugins


def _apply_multiband_eq_pedalboard(
    audio: np.ndarray,
    sr: int,
    eq_gains_db: Dict[str, float],
    *,
    extra_plugins: Optional[List[Any]] = None,
) -> np.ndarray:
    x = np.asarray(audio, dtype=np.float32)
    if x.size == 0 or sr <= 0:
        return x
    if (not eq_gains_db) or all(abs(float(v)) < 1e-3 for v in eq_gains_db.values()):
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
# Métricas
# ---------------------------------------------------------------------
def _save_tonal_metrics(
    temp_dir: Path,
    contract_id: str,
    pre_band_abs_db: Dict[str, float],
    pre_band_rel_db: Dict[str, float],
    target_rel_db: Dict[str, float],
    pre_error_rms_rel: float,
    pre_err_by_band_rel: Dict[str, float],
    pre_error_rms_abs: float,
    pre_err_by_band_abs: Dict[str, float],
    pre_global_offset_db: float,
    eq_gains_db: Dict[str, float],
    post_band_abs_db: Dict[str, float],
    post_band_rel_db: Dict[str, float],
    post_error_rms_rel: float,
    post_err_by_band_rel: Dict[str, float],
    post_error_rms_abs: float,
    post_err_by_band_abs: Dict[str, float],
    post_global_offset_db: float,
    extra_metrics: Optional[Dict[str, Any]] = None,
) -> None:
    data: Dict[str, Any] = {
        "pre": {
            "band_db_abs": pre_band_abs_db,
            "band_db_rel": pre_band_rel_db,
            "error_rms_rel_db": float(pre_error_rms_rel),
            "error_by_band_rel_db": pre_err_by_band_rel,
            "error_rms_abs_aligned_db": float(pre_error_rms_abs),
            "error_by_band_abs_aligned_db": pre_err_by_band_abs,
            "global_offset_abs_db": float(pre_global_offset_db),
        },
        "target_rel_db": target_rel_db,
        "eq_gains_db": eq_gains_db,
        "post": {
            "band_db_abs": post_band_abs_db,
            "band_db_rel": post_band_rel_db,
            "error_rms_rel_db": float(post_error_rms_rel),
            "error_by_band_rel_db": post_err_by_band_rel,
            "error_rms_abs_aligned_db": float(post_error_rms_abs),
            "error_by_band_abs_aligned_db": post_err_by_band_abs,
            "global_offset_abs_db": float(post_global_offset_db),
        },
    }

    if extra_metrics:
        data.update(extra_metrics)

    metrics_path = temp_dir / f"tonal_metrics_{contract_id}.json"
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------
# Interactivo (comparación pre/post)
# ---------------------------------------------------------------------
def _write_interactive_comparison(
    temp_dir: Path,
    contract_id: str,
    pre_band_rel_db: Dict[str, float],
    post_band_rel_db: Dict[str, float],
    target_rel_db: Dict[str, float],
    eq_gains_db: Dict[str, float],
) -> None:
    """
    Escribe un JSON simple para que el front pueda graficar barras.
    """
    out = {
        "contract_id": contract_id,
        "bands": [b["id"] for b in get_freq_bands()],
        "pre_rel_db": pre_band_rel_db,
        "post_rel_db": post_band_rel_db,
        "target_rel_db": target_rel_db,
        "eq_gains_db": eq_gains_db,
    }

    path_out = temp_dir / f"tonal_interactive_{contract_id}.json"
    with path_out.open("w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------
def process(contract_id: str) -> bool:
    """
    Lee contrato {temp_dir}/{contract_id}.json, procesa full_song.wav y escribe:
    - full_song_tonal.wav
    - tonal_metrics_{contract_id}.json
    - tonal_interactive_{contract_id}.json
    """
    try:
        # Temp dir root configurable, fallback a /tmp
        temp_root = Path(os.environ.get("MIXMASTER_TEMP_ROOT", "/tmp"))
        temp_dir = temp_root / contract_id
        contract_path = temp_dir / f"{contract_id}.json"

        if not contract_path.exists():
            logger.logger.error("No existe contrato: %s", contract_path)
            return False

        with contract_path.open("r", encoding="utf-8") as f:
            contract = json.load(f)

        analysis = contract.get("analysis", {}) or {}
        metrics = contract.get("metrics", {}) or {}
        style_preset = analysis.get("style_preset", "balanced")

        full_song_path = temp_dir / "full_song.wav"
        if not full_song_path.exists():
            p = analysis.get("mixbus_path")
            if p:
                full_song_path = Path(p)

        if not full_song_path.exists():
            logger.logger.error("No existe full_song.wav para S7: %s", full_song_path)
            return True  # no-op tolerante

        # ---------------------------------------------------------------------
        # De-harsh / anti-stridency guard (conservative; only acts when needed)
        # ---------------------------------------------------------------------
        deharsh_enable = bool(metrics.get("deharsh_enable", True))
        deharsh_edge_ratio_threshold_db = float(metrics.get("deharsh_edge_ratio_threshold_db", -14.0))
        deharsh_max_cut_db = float(metrics.get("deharsh_max_cut_db", 2.5))
        deharsh_sensitivity = float(metrics.get("deharsh_sensitivity", 0.75))
        deharsh_fc_hz = float(metrics.get("deharsh_fc_hz", 6500.0))
        deharsh_q = float(metrics.get("deharsh_q", 0.9))

        # Positive boost caps (avoid adding stridency). Defaults are intentionally conservative.
        boost_cap_high_mid_db = float(metrics.get("boost_cap_high_mid_db", 0.75))
        boost_cap_presence_db = float(metrics.get("boost_cap_presence_db", 0.50))
        boost_cap_air_db = float(metrics.get("boost_cap_air_db", 0.35))
        boost_cap_ultra_air_db = float(metrics.get("boost_cap_ultra_air_db", 0.25))

        # Compute edge ratio (5–10 kHz vs 1–4 kHz). Less negative => brighter/edgier.
        try:
            y_edge, sr_edge = sf.read(full_song_path, always_2d=False)
            y_edge = np.asarray(y_edge, dtype=np.float32)
            if y_edge.ndim > 1:
                y_edge = np.mean(y_edge, axis=1)
            edge_ratio_db_pre = compute_edge_ratio_db(y_edge, int(sr_edge))
        except Exception:
            edge_ratio_db_pre = float("nan")

        deharsh_cut_db = 0.0
        if (
            deharsh_enable
            and np.isfinite(edge_ratio_db_pre)
            and edge_ratio_db_pre > deharsh_edge_ratio_threshold_db
        ):
            excess = float(edge_ratio_db_pre - deharsh_edge_ratio_threshold_db)
            deharsh_cut_db = min(deharsh_max_cut_db, max(0.0, excess * deharsh_sensitivity))

            # When de-harsh is active, disallow additional positive boosts in the upper bands.
            boost_cap_high_mid_db = min(boost_cap_high_mid_db, 0.0)
            boost_cap_presence_db = min(boost_cap_presence_db, 0.0)
            boost_cap_air_db = min(boost_cap_air_db, 0.0)
            boost_cap_ultra_air_db = min(boost_cap_ultra_air_db, 0.0)

        logger.logger.info(
            "[S7_MIXBUS_TONAL_BALANCE] De-harsh: edge_ratio_pre=%s dB (threshold %+.2f) cut=%0.2f dB | "
            "boost_caps high_mid=%+.2f presence=%+.2f air=%+.2f ultra_air=%+.2f",
            "nan" if not np.isfinite(edge_ratio_db_pre) else f"{edge_ratio_db_pre:+.2f}",
            deharsh_edge_ratio_threshold_db,
            deharsh_cut_db,
            boost_cap_high_mid_db,
            boost_cap_presence_db,
            boost_cap_air_db,
            boost_cap_ultra_air_db,
        )

        # 2) Obtener medición PRE (band energies)
        tonal_info = analysis.get("tonal_balance", {}) or {}
        pre_band_abs = tonal_info.get("band_energies_db", None)
        sr = int(tonal_info.get("sr", 44100))

        if not pre_band_abs:
            y0, sr0 = sf.read(full_song_path, always_2d=False)
            y0 = np.asarray(y0, dtype=np.float32)
            if y0.ndim > 1:
                y0 = np.mean(y0, axis=1)
            sr = int(sr0)
            pre_band_abs = compute_band_energies(y0, sr)

        pre_band_rel = normalize_band_energies(pre_band_abs)

        # 3) Target tonal profile por estilo
        target_rel = get_style_tonal_profile(style_preset)

        # 3.1) Error relativo
        pre_err_rms_rel, pre_err_by_band_rel = compute_error_rel(pre_band_rel, target_rel)

        # 3.2) Error absoluto alineado (para diagnóstico)
        pre_err_rms_abs, pre_err_by_band_abs, pre_global_offset_db = compute_error_aligned_abs(
            pre_band_abs, target_rel
        )

        logger.logger.info(
            "[S7_MIXBUS_TONAL_BALANCE] PRE error RMS REL=%0.2f dB | RMS ABS(aligned)=%0.2f dB | global_offset_abs=%+.2f dB",
            pre_err_rms_rel,
            pre_err_rms_abs,
            pre_global_offset_db,
        )

        # 4) Construir EQ gains (por banda) a partir del error relativo
        max_err = float(metrics.get("max_tonal_balance_error_db", DEFAULT_MAX_TONAL_ERROR_DB))
        max_eq_change_db = float(metrics.get("max_eq_change_db_per_band", DEFAULT_MAX_EQ_CHANGE_DB))
        max_tonal_error_db = float(metrics.get("max_tonal_error_db", max_err))
        min_gain = float(metrics.get("min_gain_db", 0.10))
        smooth = bool(metrics.get("smooth_eq", True))

        eq_gains_db: Dict[str, float] = {}
        for band in get_freq_bands():
            bid = band["id"]
            e = float(pre_err_by_band_rel.get(bid, 0.0))
            e = float(np.clip(e, -max_tonal_error_db, max_tonal_error_db))

            # Si el audio está por encima del target (e>0), recortar; si está por debajo (e<0), realzar.
            g = float(np.clip(-e, -max_eq_change_db, max_eq_change_db))
            eq_gains_db[bid] = g

        # 4.3) Suavizado opcional (promediar con vecinos)
        if smooth:
            bands = [b["id"] for b in get_freq_bands()]
            smoothed = dict(eq_gains_db)
            for i, bid in enumerate(bands):
                neigh = [eq_gains_db[bid]]
                if i > 0:
                    neigh.append(eq_gains_db[bands[i - 1]])
                if i < len(bands) - 1:
                    neigh.append(eq_gains_db[bands[i + 1]])
                smoothed[bid] = float(np.mean(neigh))
            eq_gains_db = smoothed

        # eliminar ganancias muy pequeñas
        eq_gains_db = {k: float(v) for k, v in eq_gains_db.items() if abs(float(v)) >= float(min_gain)}

        # “global trim” detection: si casi todas las bandas están igual, es probablemente un offset global -> no aplicar
        if len(eq_gains_db) >= 3:
            vals = list(eq_gains_db.values())
            mean_g = float(np.mean(vals))
            std_g = float(np.std(vals))
            if abs(mean_g) >= 0.25 and std_g <= 0.12:
                logger.logger.warning(
                    "[S7_MIXBUS_TONAL_BALANCE] Detectado patrón de 'global trim' (mean=%+.2f std=%0.2f). No aplico EQ.",
                    mean_g,
                    std_g,
                )
                eq_gains_db = {}

        # Si hay bass boost incoherente: si sub/low piden boost pero low_mid/mid piden cortes grandes, atenuar bass boost.
        if eq_gains_db:
            bass_boost = float(eq_gains_db.get("sub", 0.0) + eq_gains_db.get("low", 0.0))
            mids_cut = float(min(eq_gains_db.get("low_mid", 0.0), eq_gains_db.get("mid", 0.0)))
            if bass_boost > 0.50 and mids_cut < -0.80:
                logger.logger.warning(
                    "[S7_MIXBUS_TONAL_BALANCE] Incoherencia: bass_boost=%0.2f, mids_cut=%0.2f. Atenúo boosts de sub/low.",
                    bass_boost,
                    mids_cut,
                )
                if "sub" in eq_gains_db:
                    eq_gains_db["sub"] *= 0.5
                if "low" in eq_gains_db:
                    eq_gains_db["low"] *= 0.5

        # High-frequency boost governor (prevents adding stridency even if target requests it).
        boost_caps = {
            "high_mid": float(boost_cap_high_mid_db),
            "presence": float(boost_cap_presence_db),
            "air": float(boost_cap_air_db),
            "ultra_air": float(boost_cap_ultra_air_db),
        }
        for b, cap in boost_caps.items():
            if b in eq_gains_db and float(eq_gains_db[b]) > 0.0:
                eq_gains_db[b] = float(min(float(eq_gains_db[b]), float(cap)))

        extra_metrics_common = {
            "edge_ratio_db_pre": float(edge_ratio_db_pre) if np.isfinite(edge_ratio_db_pre) else None,
            "deharsh_cut_db": float(deharsh_cut_db),
            "boost_caps_db": {
                "high_mid": float(boost_cap_high_mid_db),
                "presence": float(boost_cap_presence_db),
                "air": float(boost_cap_air_db),
                "ultra_air": float(boost_cap_ultra_air_db),
            },
        }

        # Si quedó todo a 0, no-op
        if not eq_gains_db and not (deharsh_cut_db > 0.0):
            logger.logger.info("[S7_MIXBUS_TONAL_BALANCE] No-op. No se aplica EQ.")
            _save_tonal_metrics(
                temp_dir=temp_dir,
                contract_id=contract_id,
                pre_band_abs_db=pre_band_abs,
                pre_band_rel_db=pre_band_rel,
                target_rel_db=target_rel,
                pre_error_rms_rel=pre_err_rms_rel,
                pre_err_by_band_rel=pre_err_by_band_rel,
                pre_error_rms_abs=pre_err_rms_abs,
                pre_err_by_band_abs=pre_err_by_band_abs,
                pre_global_offset_db=pre_global_offset_db,
                eq_gains_db={},
                post_band_abs_db=pre_band_abs,
                post_band_rel_db=pre_band_rel,
                post_error_rms_rel=pre_err_rms_rel,
                post_err_by_band_rel=pre_err_by_band_rel,
                post_error_rms_abs=pre_err_rms_abs,
                post_err_by_band_abs=pre_err_by_band_abs,
                post_global_offset_db=pre_global_offset_db,
                extra_metrics=extra_metrics_common,
            )

            _write_interactive_comparison(
                temp_dir=temp_dir,
                contract_id=contract_id,
                pre_band_rel_db=pre_band_rel,
                post_band_rel_db=pre_band_rel,
                target_rel_db=target_rel,
                eq_gains_db={},
            )
            return True

        logger.logger.info("[S7_MIXBUS_TONAL_BALANCE] EQ gains (dB): %s", eq_gains_db)

        # 5) Aplicar EQ sobre audio y escribir WAV
        y, sr = sf.read(full_song_path, always_2d=False)
        y = np.asarray(y, dtype=np.float32)
        if y.ndim > 1:
            y = np.mean(y, axis=1)
        sr = int(sr)

        extra_plugins: List[Any] = []
        if deharsh_cut_db > 0.0:
            extra_plugins.append(
                PeakFilter(
                    cutoff_frequency_hz=float(deharsh_fc_hz),
                    q=float(deharsh_q),
                    gain_db=float(-deharsh_cut_db),
                )
            )

        y_eq = _apply_multiband_eq_pedalboard(y, sr, eq_gains_db, extra_plugins=extra_plugins)

        out_path = temp_dir / "full_song_tonal.wav"
        sf.write(out_path, y_eq, sr)
        logger.logger.info("[S7_MIXBUS_TONAL_BALANCE] Escrito: %s", out_path)

        # 6) Métricas POST
        post_band_abs = compute_band_energies(y_eq, sr)
        post_band_rel = normalize_band_energies(post_band_abs)

        post_err_rms_rel, post_err_by_band_rel = compute_error_rel(post_band_rel, target_rel)
        post_err_rms_abs, post_err_by_band_abs, post_global_offset_db = compute_error_aligned_abs(
            post_band_abs, target_rel
        )

        logger.logger.info(
            "[S7_MIXBUS_TONAL_BALANCE] POST error RMS REL=%0.2f dB | RMS ABS(aligned)=%0.2f dB | global_offset_abs=%+.2f dB",
            post_err_rms_rel,
            post_err_rms_abs,
            post_global_offset_db,
        )

        # Rollback si empeoró claramente (sólo relativo)
        if post_err_rms_rel > pre_err_rms_rel + 0.25:
            logger.logger.warning(
                "[S7_MIXBUS_TONAL_BALANCE] Rollback: empeoró error rel (pre=%0.2f post=%0.2f).",
                pre_err_rms_rel,
                post_err_rms_rel,
            )
            sf.write(out_path, y, sr)

            # usar PRE como POST en métricas
            post_band_abs = pre_band_abs
            post_band_rel = pre_band_rel
            post_err_rms_rel = pre_err_rms_rel
            post_err_by_band_rel = pre_err_by_band_rel
            post_err_rms_abs = pre_err_rms_abs
            post_err_by_band_abs = pre_err_by_band_abs
            post_global_offset_db = pre_global_offset_db
            eq_gains_db = {}

        _save_tonal_metrics(
            temp_dir=temp_dir,
            contract_id=contract_id,
            pre_band_abs_db=pre_band_abs,
            pre_band_rel_db=pre_band_rel,
            target_rel_db=target_rel,
            pre_error_rms_rel=pre_err_rms_rel,
            pre_err_by_band_rel=pre_err_by_band_rel,
            pre_error_rms_abs=pre_err_rms_abs,
            pre_err_by_band_abs=pre_err_by_band_abs,
            pre_global_offset_db=pre_global_offset_db,
            eq_gains_db=eq_gains_db,
            post_band_abs_db=post_band_abs,
            post_band_rel_db=post_band_rel,
            post_error_rms_rel=post_err_rms_rel,
            post_err_by_band_rel=post_err_by_band_rel,
            post_error_rms_abs=post_err_rms_abs,
            post_err_by_band_abs=post_err_by_band_abs,
            post_global_offset_db=post_global_offset_db,
            extra_metrics=extra_metrics_common,
        )

        _write_interactive_comparison(
            temp_dir=temp_dir,
            contract_id=contract_id,
            pre_band_rel_db=pre_band_rel,
            post_band_rel_db=post_band_rel,
            target_rel_db=target_rel,
            eq_gains_db=eq_gains_db,
        )

        return True

    except Exception as e:
        logger.logger.exception("[S7_MIXBUS_TONAL_BALANCE] Error: %s", e)
        return False


if __name__ == "__main__":
    cid = sys.argv[1] if len(sys.argv) > 1 else "S7_MIXBUS_TONAL_BALANCE"
    ok = process(cid)
    sys.exit(0 if ok else 1)
