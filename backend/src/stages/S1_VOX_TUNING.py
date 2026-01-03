# C:\mix-master\backend\src\stages\S1_VOX_TUNING.py

from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import os  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from utils.analysis_utils import get_temp_dir  # noqa: E402
from utils.pitch_utils import tune_vocal_time_varying  # noqa: E402


def load_analysis(contract_id: str) -> Dict[str, Any]:
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"
    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")
    with analysis_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _sanitize_scale_pcs(pcs: Any) -> Optional[List[int]]:
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


def apply_vocal_tuning_to_stem(
    stem_info: Dict[str, Any],
    pitch_cents_max_deviation: float | None,
    tuning_strength: float | None,
    max_pitch_shift_semitones: float | None,
    scale_pcs: List[int] | None,
) -> bool:
    """
    Aplica afinación time-varying a un stem vocal.
    Devuelve True si modificó el archivo, False si no-op.
    """
    if not stem_info.get("is_vocal_stem", False):
        return False

    file_path = Path(stem_info["file_path"])
    stem_name = stem_info.get("file_name", file_path.name)

    if tuning_strength is None:
        tuning_strength = 1.0

    try:
        data, sr = sf.read(file_path, always_2d=False)
    except Exception as e:
        logger.logger.info(f"[S1_VOX_TUNING] {stem_name}: no se pudo leer: {e}")
        return False

    if not isinstance(data, np.ndarray):
        data = np.asarray(data, dtype=np.float32)
    else:
        data = data.astype(np.float32)

    if data.size == 0:
        logger.logger.info(f"[S1_VOX_TUNING] {stem_name}: archivo vacío, se omite.")
        return False

    used_scale = scale_pcs if (isinstance(scale_pcs, list) and len(scale_pcs) > 0) else None
    mode_str = "SCALE" if used_scale is not None else "CHROMATIC"

    # Afinar canal por canal si es estéreo (para no colapsar imagen)
    if data.ndim == 2 and data.shape[1] > 1:
        chans = []
        for ch in range(data.shape[1]):
            y_tuned = tune_vocal_time_varying(
                y=data[:, ch],
                sr=sr,
                tuning_strength=float(tuning_strength),
                max_shift_semitones=float(max_pitch_shift_semitones) if max_pitch_shift_semitones is not None else None,
                pitch_cents_max_deviation=float(pitch_cents_max_deviation) if pitch_cents_max_deviation is not None else None,
                allowed_scale_pcs=used_scale,
            )
            chans.append(np.asarray(y_tuned, dtype=np.float32))
        y_out = np.stack(chans, axis=1)
    else:
        y_in = data[:, 0] if (data.ndim == 2 and data.shape[1] == 1) else data
        y_out = tune_vocal_time_varying(
            y=y_in,
            sr=sr,
            tuning_strength=float(tuning_strength),
            max_shift_semitones=float(max_pitch_shift_semitones) if max_pitch_shift_semitones is not None else None,
            pitch_cents_max_deviation=float(pitch_cents_max_deviation) if pitch_cents_max_deviation is not None else None,
            allowed_scale_pcs=used_scale,
        )
        y_out = np.asarray(y_out, dtype=np.float32)
        if data.ndim == 2 and data.shape[1] == 1:
            y_out = y_out.reshape(-1, 1)

    sf.write(file_path, y_out, sr)

    logger.logger.info(
        f"[S1_VOX_TUNING] {stem_name}: tuning aplicado "
        f"(mode={mode_str}, strength={float(tuning_strength):.2f}, "
        f"max_shift={max_pitch_shift_semitones}, scale_pcs={used_scale})."
    )
    return True


def _tune_stem_worker(
    args: Tuple[Dict[str, Any], float | None, float | None, float | None, List[int] | None]
) -> bool:
    stem_info, pitch_cents_max_deviation, tuning_strength, max_pitch_shift_semitones, scale_pcs = args
    return apply_vocal_tuning_to_stem(
        stem_info=stem_info,
        pitch_cents_max_deviation=pitch_cents_max_deviation,
        tuning_strength=tuning_strength,
        max_pitch_shift_semitones=max_pitch_shift_semitones,
        scale_pcs=scale_pcs,
    )


def main() -> None:
    """
    Stage S1_VOX_TUNING:
      - Usa scale_pitch_classes_resolved del análisis.
      - Si no hay escala resuelta: afinación cromática (allowed_scale_pcs=None).
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S1_VOX_TUNING.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]
    analysis = load_analysis(contract_id)

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}
    session: Dict[str, Any] = analysis.get("session", {}) or {}
    stems: List[Dict[str, Any]] = analysis.get("stems", []) or []

    pitch_cents_max_deviation = metrics.get("pitch_cents_max_deviation")
    tuning_strength = metrics.get("tuning_strength_0_1", 1.0)
    max_pitch_shift_semitones = limits.get("max_pitch_shift_semitones")

    # Escala RESUELTA (detectada o inferida) desde el análisis
    scale_pcs = _sanitize_scale_pcs(session.get("scale_pitch_classes_resolved"))
    key_name = session.get("key_name")
    key_mode = session.get("key_mode")

    if scale_pcs is None:
        logger.logger.info(
            f"[S1_VOX_TUNING] Aviso: scale_pitch_classes_resolved=None "
            f"(key={key_name}, mode={key_mode}). Se aplicará afinación cromática (suave)."
        )
    else:
        logger.logger.info(
            f"[S1_VOX_TUNING] Usando escala detectada/resuelta para afinación: "
            f"key={key_name}, mode={key_mode}, pcs={scale_pcs}."
        )

    vocal_stems = [s for s in stems if s.get("is_vocal_stem", False)]
    if not vocal_stems:
        logger.logger.info("[S1_VOX_TUNING] No hay stems vocales; no-op.")
        return

    args_list: List[Tuple[Dict[str, Any], float | None, float | None, float | None, List[int] | None]] = [
        (s, pitch_cents_max_deviation, tuning_strength, max_pitch_shift_semitones, scale_pcs)
        for s in vocal_stems
    ]

    touched = 0
    for ok in map(_tune_stem_worker, args_list):
        if ok:
            touched += 1

    logger.logger.info(f"[S1_VOX_TUNING] Procesados {len(vocal_stems)} stems vocales. Modificados={touched}.")


if __name__ == "__main__":
    main()
