# C:\mix-master\backend\src\analysis\S1_VOX_TUNING.py

from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import os

# --- hack para poder importar utils cuando se ejecuta como script suelto ---
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
from utils.vocal_utils import is_vocal_profile  # noqa: E402
from utils.pitch_utils import estimate_pitch_deviation  # noqa: E402


def _sanitize_scale_pcs(pcs: Any) -> Optional[List[int]]:
    """
    Normaliza pitch classes:
      - lista de ints en [0..11]
      - unique + sorted
    """
    if not isinstance(pcs, list) or not pcs:
        return None
    out: List[int] = []
    for v in pcs:
        try:
            i = int(v)
        except (TypeError, ValueError):
            continue
        i = i % 12
        if i not in out:
            out.append(i)
    out.sort()
    return out if out else None


def _infer_scale_pcs_from_root_mode(root_pc: Any, mode: Any) -> Optional[List[int]]:
    """
    Fallback si S1_KEY_DETECTION no trae scale_pitch_classes pero sí root+mode.
    Soporta major/minor (natural minor).
    """
    try:
        r = int(root_pc) % 12
    except (TypeError, ValueError):
        return None

    m = str(mode or "").strip().lower()
    if m in ("major", "ionian"):
        intervals = [0, 2, 4, 5, 7, 9, 11]
    elif m in ("minor", "aeolian"):
        intervals = [0, 2, 3, 5, 7, 8, 10]
    else:
        return None

    pcs = sorted({(r + it) % 12 for it in intervals})
    return pcs if pcs else None


def _load_key_detection_from_job_root(job_root: Path) -> Dict[str, Any]:
    """
    Lee /temp/<job_id>/S1_KEY_DETECTION/analysis_S1_KEY_DETECTION.json si existe.
    Devuelve dict con campos:
      key_root_pc, key_mode, key_name, scale_pitch_classes_detected, key_source_path
    """
    out: Dict[str, Any] = {
        "key_root_pc": None,
        "key_mode": None,
        "key_name": None,
        "scale_pitch_classes_detected": None,
        "key_source_path": None,
    }

    key_path = job_root / "S1_KEY_DETECTION" / "analysis_S1_KEY_DETECTION.json"
    if not key_path.exists():
        return out

    try:
        with key_path.open("r", encoding="utf-8") as f:
            key_data = json.load(f)
    except Exception as e:
        logger.logger.info(f"[S1_VOX_TUNING] Aviso: no se pudo leer key detection en {key_path}: {e}")
        return out

    session = key_data.get("session", {}) or {}
    out["key_root_pc"] = session.get("key_root_pc")
    out["key_mode"] = session.get("key_mode")
    out["key_name"] = session.get("key_name")
    out["scale_pitch_classes_detected"] = session.get("scale_pitch_classes") or session.get("scale_pitch_classes_detected") or session.get("scale_pitch_classes")
    out["key_source_path"] = str(key_path)
    return out


def analyze_stem(args: Tuple[Path, str, bool]) -> Dict[str, Any]:
    """
    Analiza SOLO stems vocales: estima desviación de afinación.
    """
    stem_path, instrument_profile, is_vocal = args
    file_name = stem_path.name

    max_abs_dev_cents = None
    median_dev_cents = None
    recommended_shift_semitones = 0.0

    if is_vocal:
        y, sr = sf_read_limited(stem_path, always_2d=False)
        if isinstance(y, np.ndarray) and y.ndim > 1:
            y_mono = np.mean(y, axis=1).astype(np.float32)
        else:
            y_mono = np.asarray(y, dtype=np.float32)

        pitch_stats = estimate_pitch_deviation(y_mono, sr)
        max_abs_dev_cents = pitch_stats.get("max_abs_deviation_cents")
        median_dev_cents = pitch_stats.get("median_deviation_cents")
        recommended_shift_semitones = pitch_stats.get("recommended_global_shift_semitones", 0.0)

    return {
        "file_name": file_name,
        "file_path": str(stem_path),
        "instrument_profile": instrument_profile,
        "is_vocal_stem": bool(is_vocal),
        "estimated_pitch_deviation_cents_max": max_abs_dev_cents,
        "estimated_pitch_deviation_cents_median": median_dev_cents,
        "recommended_global_shift_semitones": recommended_shift_semitones,
    }


def main() -> None:
    """
    Análisis para S1_VOX_TUNING.

    IMPORTANT: la key/scale se lee desde el MISMO job_root del pipeline:
      /temp/<job_id>/S1_KEY_DETECTION/analysis_S1_KEY_DETECTION.json
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S1_VOX_TUNING.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]

    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    temp_dir = get_temp_dir(contract_id, create=True)
    job_root = temp_dir.parent  # .../temp/<job_id>

    cfg = load_session_config(contract_id)
    style_preset = cfg["style_preset"]
    instrument_by_file = cfg["instrument_by_file"]

    # --- cargar key detection desde job_root ---
    kd = _load_key_detection_from_job_root(job_root)
    key_root_pc = kd.get("key_root_pc")
    key_mode = kd.get("key_mode")
    key_name = kd.get("key_name")
    scale_detected = _sanitize_scale_pcs(kd.get("scale_pitch_classes_detected"))

    # Resolver escala definitiva (prioridad: detectada; fallback: inferida)
    scale_resolved = scale_detected
    scale_inferred = False
    if scale_resolved is None:
        inferred = _infer_scale_pcs_from_root_mode(key_root_pc, key_mode)
        if inferred is not None:
            scale_resolved = inferred
            scale_inferred = True

    # Listar stems
    stem_files: List[Path] = sorted(
        p for p in temp_dir.glob("*.wav")
        if p.name.lower() != "full_song.wav"
    )

    stem_tasks: List[Tuple[Path, str, bool]] = []
    for stem_path in stem_files:
        fname = stem_path.name
        inst = instrument_by_file.get(fname, "Other")
        is_vocal = is_vocal_profile(inst)
        stem_tasks.append((stem_path, inst, is_vocal))

    if stem_tasks:
        results = list(map(analyze_stem, stem_tasks))
    else:
        results = []

    stems_analysis: List[Dict[str, Any]] = list(results)
    vocal_count = sum(1 for s in stems_analysis if s.get("is_vocal_stem"))

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "pitch_cents_max_deviation_target": metrics.get("pitch_cents_max_deviation"),
            "tuning_strength_0_1_target": metrics.get("tuning_strength_0_1"),
            "max_pitch_shift_semitones_limit": limits.get("max_pitch_shift_semitones"),
            "vocal_stems_count": vocal_count,
            "total_stems_count": len(stems_analysis),
            # info tonalidad
            "key_root_pc": key_root_pc,
            "key_mode": key_mode,
            "key_name": key_name,
            "key_source_path": kd.get("key_source_path"),
            "scale_pitch_classes_detected": scale_detected,
            "scale_pitch_classes_resolved": scale_resolved,
            "scale_was_inferred": bool(scale_inferred),
        },
        "stems": stems_analysis,
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    logger.logger.info(
        f"[S1_VOX_TUNING] Análisis completado. vocals={vocal_count}/{len(stems_analysis)}. "
        f"key={key_name} mode={key_mode} scale_resolved={scale_resolved}. "
        f"JSON: {output_path}"
    )


if __name__ == "__main__":
    main()
