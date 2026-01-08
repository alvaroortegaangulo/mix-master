#C:\mix-master\backend\src\analysis\S2_GROUP_PHASE_DRUMS.py

from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple
import os

# --- hack para importar utils ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import numpy as np  # noqa: E402

from utils.analysis_utils import (  # noqa: E402
    load_contract,
    get_temp_dir,
    sf_read_limited,
)
from utils.session_utils import load_session_config  # noqa: E402
from utils.phase_utils import estimate_best_lag_and_corr  # noqa: E402


def _is_in_family(instrument_profile: str | None, target_family: str) -> bool:
    """
    Clasificación mínima de familias.

    Para 'Drums', consideramos varios perfiles relacionados.
    """
    if not instrument_profile:
        return False

    if target_family.lower() == "drums":
        prefixes = (
            "Kick",
            "Snare",
            "Percussion",
            "HiHat",
            "Tom",
            "Overhead",
            "Room",
            "Drums_",
        )
        return instrument_profile.startswith(prefixes)

    return False


def _normalize_audio(x: np.ndarray) -> np.ndarray:
    """Normaliza a pico 1.0 si es posible, sin modificar el array original."""
    if x.size == 0:
        return x
    peak = float(np.max(np.abs(x)))
    if peak > 0.0:
        return x / peak
    return x


def _compute_lag_curve(
    ref_norm: np.ndarray,
    cand_norm: np.ndarray,
    sr: int,
    max_time_shift_ms_curve: float,
    fmin: float,
    fmax: float,
    num_points: int,
    window_sec: float,
    correlation_min: float,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Estima el lag en varios anclajes temporales para detectar deriva.

    Devuelve:
      - lag_curve: lista de dicts con anchor_sample, anchor_sec, lag_samples, lag_ms, correlation, valid
      - summary: dict con drift_range_ms, valid_points, etc.
    """
    ref_norm = np.asarray(ref_norm, dtype=np.float32)
    cand_norm = np.asarray(cand_norm, dtype=np.float32)

    min_len = int(min(ref_norm.shape[0], cand_norm.shape[0]))
    if min_len <= 0 or sr <= 0:
        return [], {
            "enabled": False,
            "reason": "audio vacío o sr inválido",
        }

    dur_sec = float(min_len / sr)

    # Ajustes robustos de ventana
    window_sec = float(window_sec)
    window_sec = max(0.5, min(window_sec, 6.0, max(0.5, dur_sec * 0.25)))
    win_len = int(round(window_sec * sr))
    win_len = max(2048, min(win_len, min_len))

    if num_points < 2:
        num_points = 2

    # Evitar anclajes justo en 0/fin (suele haber silencios/fades)
    anchors = np.linspace(0.1, 0.9, num_points, dtype=np.float64) * dur_sec

    curve: List[Dict[str, Any]] = []
    for t_sec in anchors.tolist():
        center = int(round(t_sec * sr))
        start = int(center - win_len // 2)
        start = max(0, min(start, min_len - win_len))
        end = start + win_len

        ref_seg = ref_norm[start:end]
        cand_seg = cand_norm[start:end]

        try:
            res = estimate_best_lag_and_corr(
                ref=ref_seg,
                cand=cand_seg,
                sr=sr,
                max_time_shift_ms=max_time_shift_ms_curve,
                fmin=fmin,
                fmax=fmax,
            )
            lag_s = float(res["lag_samples"])
            lag_ms = float(res["lag_ms"])
            corr = float(res["correlation"])
        except Exception as e:
            lag_s = 0.0
            lag_ms = 0.0
            corr = float("-inf")
            logger.logger.info(
                f"[S2_GROUP_PHASE_DRUMS] Aviso: fallo al estimar lag_curve en t={t_sec:.2f}s: {e}"
            )

        valid = bool(np.isfinite(corr) and corr >= correlation_min)

        curve.append(
            {
                "anchor_sec": float(start / sr),
                "anchor_sample": int(start),
                "window_sec": float(win_len / sr),
                "lag_samples": float(lag_s),
                "lag_ms": float(lag_ms),
                "correlation": float(corr),
                "valid": bool(valid),
            }
        )

    valid_lags_ms = [p["lag_ms"] for p in curve if p.get("valid", False)]
    valid_count = int(len(valid_lags_ms))

    if valid_count >= 2:
        drift_range_ms = float(max(valid_lags_ms) - min(valid_lags_ms))
        lag_ms_median = float(np.median(np.asarray(valid_lags_ms, dtype=np.float32)))
    elif valid_count == 1:
        drift_range_ms = 0.0
        lag_ms_median = float(valid_lags_ms[0])
    else:
        drift_range_ms = 0.0
        lag_ms_median = 0.0

    summary = {
        "enabled": True,
        "duration_sec_analyzed": float(dur_sec),
        "num_points": int(num_points),
        "window_sec_used": float(win_len / sr),
        "max_time_shift_ms_curve": float(max_time_shift_ms_curve),
        "valid_points": int(valid_count),
        "drift_range_ms": float(drift_range_ms),
        "lag_ms_median": float(lag_ms_median),
    }
    return curve, summary


def _analyze_drum_stem(
    args: Tuple[
        int,
        Dict[str, Any],
        Path,
        np.ndarray,
        int,
        float,
        float,
        float,
        bool,
        float,
        bool,
        int,
        float,
        float,
        float,
    ]
) -> Tuple[int, Dict[str, Any]]:
    """
    Analiza un stem candidato vs referencia:
      - lag global + correlación (y flip de polaridad opcional)
      - curva de lag a lo largo del tiempo para detectar deriva
    """
    (
        idx,
        base_info,
        stem_path,
        ref_mono,
        ref_sr,
        max_time_shift_ms,
        band_fmin,
        band_fmax,
        allow_polarity_flip,
        correlation_min,
        enable_time_varying,
        drift_num_points,
        drift_window_sec,
        max_time_shift_ms_curve,
        drift_min_range_ms,
    ) = args

    info = dict(base_info)

    cand_data, cand_sr = sf_read_limited(stem_path, always_2d=False)
    if cand_sr != ref_sr:
        logger.logger.info(
            f"[S2_GROUP_PHASE_DRUMS] Advertencia: samplerate distinto en {stem_path.name} "
            f"({cand_sr} vs {ref_sr}), se trunca al menor."
        )

    if isinstance(cand_data, np.ndarray) and cand_data.ndim > 1:
        cand_mono = np.mean(cand_data, axis=1).astype(np.float32)
    else:
        cand_mono = np.asarray(cand_data, dtype=np.float32)

    ref_local = np.asarray(ref_mono, dtype=np.float32)
    cand_local = np.asarray(cand_mono, dtype=np.float32)

    # Truncar a longitud común para análisis estable
    min_len = int(min(ref_local.shape[0], cand_local.shape[0]))
    if min_len <= 0:
        info.update(
            {
                "is_reference": False,
                "lag_samples": 0.0,
                "lag_ms": 0.0,
                "correlation_band_100_500": float("-inf"),
                "use_polarity_flip": False,
                "time_varying_recommended": False,
                "drift": {"enabled": False, "reason": "audio vacío"},
                "lag_curve": [],
            }
        )
        return idx, info

    ref_local = ref_local[:min_len]
    cand_local = cand_local[:min_len]

    ref_norm = _normalize_audio(ref_local)
    cand_norm = _normalize_audio(cand_local)

    sr = int(ref_sr)

    # -----------------------
    # 1) Lag global (como antes)
    # -----------------------
    res_norm = estimate_best_lag_and_corr(
        ref=ref_norm,
        cand=cand_norm,
        sr=sr,
        max_time_shift_ms=max_time_shift_ms,
        fmin=band_fmin,
        fmax=band_fmax,
    )
    corr_norm = float(res_norm["correlation"])

    if allow_polarity_flip:
        res_flip = estimate_best_lag_and_corr(
            ref=ref_norm,
            cand=-cand_norm,
            sr=sr,
            max_time_shift_ms=max_time_shift_ms,
            fmin=band_fmin,
            fmax=band_fmax,
        )
        corr_flip = float(res_flip["correlation"])
    else:
        res_flip = None
        corr_flip = float("-inf")

    if corr_flip > corr_norm:
        best = res_flip
        use_flip = True
    else:
        best = res_norm
        use_flip = False

    lag_global_samples = float(best["lag_samples"])
    lag_global_ms = float(best["lag_ms"])
    corr_global = float(best["correlation"])

    # -----------------------
    # 2) Curva de deriva (time-varying)
    # -----------------------
    lag_curve: List[Dict[str, Any]] = []
    drift_summary: Dict[str, Any] = {"enabled": False}

    if enable_time_varying:
        # Importante: la curva debe evaluarse con la misma polaridad que “gana”
        cand_for_curve = (-cand_norm) if use_flip else cand_norm

        lag_curve, drift_summary = _compute_lag_curve(
            ref_norm=ref_norm,
            cand_norm=cand_for_curve,
            sr=sr,
            max_time_shift_ms_curve=max_time_shift_ms_curve,
            fmin=band_fmin,
            fmax=band_fmax,
            num_points=drift_num_points,
            window_sec=drift_window_sec,
            correlation_min=correlation_min,
        )

    drift_range_ms = float(drift_summary.get("drift_range_ms", 0.0)) if drift_summary else 0.0
    valid_points = int(drift_summary.get("valid_points", 0)) if drift_summary else 0

    time_varying_recommended = bool(
        enable_time_varying
        and valid_points >= 2
        and drift_range_ms >= float(drift_min_range_ms)
    )

    info.update(
        {
            "is_reference": False,
            "lag_samples": float(lag_global_samples),
            "lag_ms": float(lag_global_ms),
            "correlation_band_100_500": float(corr_global),
            "use_polarity_flip": bool(use_flip),

            "time_varying_recommended": bool(time_varying_recommended),
            "drift": dict(drift_summary) if drift_summary else {"enabled": False},
            "lag_curve": lag_curve,
        }
    )

    return idx, info


def main() -> None:
    """
    Análisis para el contrato S2_GROUP_PHASE_DRUMS.

    Uso esperado desde stage.py:
        python analysis/S2_GROUP_PHASE_DRUMS.py S2_GROUP_PHASE_DRUMS
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S2_GROUP_PHASE_DRUMS.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S2_GROUP_PHASE_DRUMS"

    # 1) Cargar contrato
    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    target_family = metrics.get("target_family", "Drums")
    correlation_min = float(metrics.get("correlation_min", 0.0))

    max_time_shift_ms = float(limits.get("max_time_shift_ms", 2.0))
    allow_polarity_flip = bool(limits.get("allow_polarity_flip", True))
    ref_instrument_id = contract.get("instrument_id", "Kick")

    # --- NUEVO: parámetros deriva (con defaults seguros) ---
    enable_time_varying = bool(limits.get("enable_time_varying_alignment", True))
    drift_num_points = int(limits.get("drift_num_points", 5))
    drift_window_sec = float(limits.get("drift_window_sec", 2.0))
    max_time_shift_ms_curve = float(limits.get("max_time_shift_ms_curve", max(6.0, max_time_shift_ms * 4.0)))
    drift_min_range_ms = float(limits.get("drift_min_range_ms", 0.25))  # umbral para “merece la pena”

    # 2) Directorio temp/<contract_id> y session_config
    temp_dir = get_temp_dir(contract_id, create=True)

    cfg = load_session_config(contract_id)
    style_preset = cfg["style_preset"]
    instrument_by_file = cfg["instrument_by_file"]

    # 3) Listar stems .wav
    stem_files: List[Path] = sorted(
        p for p in temp_dir.glob("*.wav") if p.name.lower() != "full_song.wav"
    )

    if not stem_files:
        logger.logger.info("[S2_GROUP_PHASE_DRUMS] No se han encontrado stems en temp.")
        session_state = {
            "contract_id": contract_id,
            "stage_id": stage_id,
            "style_preset": style_preset,
            "metrics_from_contract": metrics,
            "limits_from_contract": limits,
            "session": {
                "target_family": target_family,
                "correlation_min": correlation_min,
                "max_time_shift_ms": max_time_shift_ms,
                "allow_polarity_flip": allow_polarity_flip,
                "reference_stem_name": None,

                "enable_time_varying_alignment": enable_time_varying,
                "drift_num_points": drift_num_points,
                "drift_window_sec": drift_window_sec,
                "max_time_shift_ms_curve": max_time_shift_ms_curve,
                "drift_min_range_ms": drift_min_range_ms,
            },
            "stems": [],
        }
        output_path = temp_dir / f"analysis_{contract_id}.json"
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(session_state, f, indent=2, ensure_ascii=False)
        return

    # 4) Clasificar stems por familia y buscar referencia
    stems_info_raw: List[Dict[str, Any]] = []
    drum_indices: List[int] = []

    for idx, p in enumerate(stem_files):
        file_name = p.name
        inst_prof = instrument_by_file.get(file_name, "Other")
        in_family = _is_in_family(inst_prof, target_family)
        stems_info_raw.append(
            {
                "file_name": file_name,
                "file_path": str(p),
                "instrument_profile": inst_prof,
                "in_family": in_family,
            }
        )
        if in_family:
            drum_indices.append(idx)

    if not drum_indices:
        logger.logger.info("[S2_GROUP_PHASE_DRUMS] No hay stems de familia Drums según instrument_profile.")
        session_state = {
            "contract_id": contract_id,
            "stage_id": stage_id,
            "style_preset": style_preset,
            "metrics_from_contract": metrics,
            "limits_from_contract": limits,
            "session": {
                "target_family": target_family,
                "correlation_min": correlation_min,
                "max_time_shift_ms": max_time_shift_ms,
                "allow_polarity_flip": allow_polarity_flip,
                "reference_stem_name": None,

                "enable_time_varying_alignment": enable_time_varying,
                "drift_num_points": drift_num_points,
                "drift_window_sec": drift_window_sec,
                "max_time_shift_ms_curve": max_time_shift_ms_curve,
                "drift_min_range_ms": drift_min_range_ms,
            },
            "stems": stems_info_raw,
        }
        output_path = temp_dir / f"analysis_{contract_id}.json"
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(session_state, f, indent=2, ensure_ascii=False)
        return

    # Referencia: Kick si existe, si no, primer drum stem
    ref_idx = None
    for idx in drum_indices:
        if stems_info_raw[idx]["instrument_profile"] == ref_instrument_id:
            ref_idx = idx
            break
    if ref_idx is None:
        ref_idx = drum_indices[0]

    ref_path = stem_files[ref_idx]
    ref_name = ref_path.name

    ref_data, ref_sr = sf_read_limited(ref_path, always_2d=False)
    if isinstance(ref_data, np.ndarray) and ref_data.ndim > 1:
        ref_mono = np.mean(ref_data, axis=1).astype(np.float32)
    else:
        ref_mono = np.asarray(ref_data, dtype=np.float32)

    BAND_FMIN = 100.0
    BAND_FMAX = 500.0

    stems_analysis: List[Dict[str, Any] | None] = [None] * len(stems_info_raw)

    # 5) Casos triviales (no familia + referencia)
    for idx, base_info in enumerate(stems_info_raw):
        info = dict(base_info)
        in_family = info["in_family"]
        is_ref = (idx == ref_idx) and in_family

        if not in_family:
            info.update(
                {
                    "is_reference": False,
                    "lag_samples": 0.0,
                    "lag_ms": 0.0,
                    "correlation_band_100_500": None,
                    "use_polarity_flip": False,

                    "time_varying_recommended": False,
                    "drift": {"enabled": False},
                    "lag_curve": [],
                }
            )
            stems_analysis[idx] = info
        elif is_ref:
            info.update(
                {
                    "is_reference": True,
                    "lag_samples": 0.0,
                    "lag_ms": 0.0,
                    "correlation_band_100_500": 1.0,
                    "use_polarity_flip": False,

                    "time_varying_recommended": False,
                    "drift": {"enabled": False},
                    "lag_curve": [],
                }
            )
            stems_analysis[idx] = info

    # 6) Tareas de drums que NO son referencia
    tasks: List[
        Tuple[int, Dict[str, Any], Path, np.ndarray, int, float, float, float, bool, float, bool, int, float, float, float]
    ] = []

    for idx, base_info in enumerate(stems_info_raw):
        if not base_info["in_family"]:
            continue
        if idx == ref_idx:
            continue

        stem_path = stem_files[idx]
        tasks.append(
            (
                idx,
                base_info,
                stem_path,
                ref_mono,
                ref_sr,
                max_time_shift_ms,
                BAND_FMIN,
                BAND_FMAX,
                allow_polarity_flip,
                correlation_min,
                enable_time_varying,
                drift_num_points,
                drift_window_sec,
                max_time_shift_ms_curve,
                drift_min_range_ms,
            )
        )

    # 7) Ejecutar análisis en serie
    if tasks:
        for idx_res, info_res in map(_analyze_drum_stem, tasks):
            stems_analysis[idx_res] = info_res

    for idx, val in enumerate(stems_analysis):
        if val is None:
            stems_analysis[idx] = dict(stems_info_raw[idx])

    stems_analysis_final: List[Dict[str, Any]] = [dict(x) for x in stems_analysis]

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "target_family": target_family,
            "correlation_min": correlation_min,
            "max_time_shift_ms": max_time_shift_ms,
            "allow_polarity_flip": allow_polarity_flip,
            "reference_stem_name": ref_name,
            "band_fmin_hz": BAND_FMIN,
            "band_fmax_hz": BAND_FMAX,

            "enable_time_varying_alignment": enable_time_varying,
            "drift_num_points": drift_num_points,
            "drift_window_sec": drift_window_sec,
            "max_time_shift_ms_curve": max_time_shift_ms_curve,
            "drift_min_range_ms": drift_min_range_ms,
        },
        "stems": stems_analysis_final,
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    logger.logger.info(
        f"[S2_GROUP_PHASE_DRUMS] Análisis completado para {len(stems_analysis_final)} stems "
        f"(familia={target_family}, ref={ref_name}). JSON: {output_path}"
    )


if __name__ == "__main__":
    main()
