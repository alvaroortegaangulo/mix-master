# C:\mix-master\backend\src\analysis\S2_GROUP_PHASE_DRUMS.py

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
import soundfile as sf  # noqa: E402

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
    Idealmente esto saldría de profiles.json, pero lo dejamos
    aquí para mantener el script operativo.
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

    # otras familias se podrían añadir aquí (Bass, Guitars, etc.)
    return False


def _normalize_audio(x: np.ndarray) -> np.ndarray:
    """Normaliza a pico 1.0 si es posible, sin modificar el array original."""
    if x.size == 0:
        return x
    peak = float(np.max(np.abs(x)))
    if peak > 0.0:
        return x / peak
    return x


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
    ]
) -> Tuple[int, Dict[str, Any]]:
    """

    Recibe:
      - idx: índice del stem en stems_info_raw / stem_files
      - base_info: dict con info básica (file_name, file_path, instrument_profile, in_family)
      - stem_path: ruta al .wav candidato
      - ref_mono: array mono de la referencia
      - ref_sr: samplerate de la referencia
      - max_time_shift_ms: límite de desplazamiento en ms
      - band_fmin / band_fmax: banda de frecuencia para la correlación
      - allow_polarity_flip: si se evalúa o no la inversión de polaridad

    Devuelve:
      (idx, info_actualizada)
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
    ) = args

    info = dict(base_info)

    cand_data, cand_sr = sf_read_limited(stem_path, always_2d=False)
    if cand_sr != ref_sr:
        # En teoría no debería pasar tras S0_SESSION_FORMAT
        logger.logger.info(
            f"[S2_GROUP_PHASE_DRUMS] Advertencia: samplerate distinto en {stem_path.name} "
            f"({cand_sr} vs {ref_sr}), se trunca al menor."
        )

    if isinstance(cand_data, np.ndarray) and cand_data.ndim > 1:
        cand_mono = np.mean(cand_data, axis=1).astype(np.float32)
    else:
        cand_mono = np.asarray(cand_data, dtype=np.float32)

    # Copias locales para normalizar sin tocar ref_mono original
    ref_local = np.asarray(ref_mono, dtype=np.float32)
    cand_local = cand_mono

    ref_norm = _normalize_audio(ref_local)
    cand_norm = _normalize_audio(cand_local)

    sr = ref_sr

    # Opción 1: sin invertir polaridad
    res_norm = estimate_best_lag_and_corr(
        ref=ref_norm,
        cand=cand_norm,
        sr=sr,
        max_time_shift_ms=max_time_shift_ms,
        fmin=band_fmin,
        fmax=band_fmax,
    )
    corr_norm = res_norm["correlation"]

    # Opción 2: invertir polaridad
    if allow_polarity_flip:
        res_flip = estimate_best_lag_and_corr(
            ref=ref_norm,
            cand=-cand_norm,
            sr=sr,
            max_time_shift_ms=max_time_shift_ms,
            fmin=band_fmin,
            fmax=band_fmax,
        )
        corr_flip = res_flip["correlation"]
    else:
        res_flip = None
        corr_flip = -999.0

    if corr_flip > corr_norm:
        best = res_flip
        use_flip = True
    else:
        best = res_norm
        use_flip = False

    info.update(
        {
            "is_reference": False,
            "lag_samples": best["lag_samples"],
            "lag_ms": best["lag_ms"],
            "correlation_band_100_500": best["correlation"],
            "use_polarity_flip": use_flip,
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
        # Aun así generamos un JSON vacío
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
        # Aun así generamos JSON
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

    # Preparamos estructura de salida preservando orden
    stems_analysis: List[Dict[str, Any] | None] = [None] * len(stems_info_raw)

    # 5) Rellenar casos triviales (no familia + referencia)
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
                }
            )
            stems_analysis[idx] = info

    # 6) Preparar tareas para stems de drums que NO son referencia
    tasks: List[Tuple[int, Dict[str, Any], Path, np.ndarray, int, float, float, float, bool]] = []

    for idx, base_info in enumerate(stems_info_raw):
        in_family = base_info["in_family"]
        if not in_family:
            continue
        if idx == ref_idx:
            continue  # ya tratado como referencia

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
            )
        )

    # 7) Ejecutar análisis para candidatos de drums en serie
    if tasks:
        for idx_res, info_res in map(_analyze_drum_stem, tasks):
            stems_analysis[idx_res] = info_res

    # Por seguridad, rellenar cualquier hueco que pudiera quedar (no debería)
    for idx, val in enumerate(stems_analysis):
        if val is None:
            stems_analysis[idx] = dict(stems_info_raw[idx])

    # Cast seguro a List[Dict[str, Any]]
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
