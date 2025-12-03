from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import os  # noqa: E402

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from utils.analysis_utils import get_temp_dir
from utils.pitch_utils import tune_vocal_time_varying  # noqa: E402


def load_analysis(contract_id: str) -> Dict[str, Any]:
    """
    Carga el JSON de análisis generado por analysis\\S1_VOX_TUNING.py.
    """
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def apply_vocal_tuning_to_stem(
    stem_info: Dict[str, Any],
    pitch_cents_max_deviation: float | None,
    tuning_strength: float | None,
    max_pitch_shift_semitones: float | None,
    scale_pcs: List[int] | None,
) -> None:
    """
    Aplica afinación time-varying a un stem vocal:

      - Usa librosa.yin para obtener la curva de pitch.
      - Cuantiza a la nota de la escala más cercana (si scale_pcs no es None).
      - Respeta pitch_cents_max_deviation, tuning_strength y max_pitch_shift_semitones.
    """
    if not stem_info.get("is_vocal_stem", False):
        return

    file_path = Path(stem_info["file_path"])
    stem_name = stem_info.get("file_name")

    if tuning_strength is None:
        tuning_strength = 1.0

    data, sr = sf.read(file_path, always_2d=False)

    if not isinstance(data, np.ndarray):
        data = np.array(data, dtype=np.float32)
    else:
        data = data.astype(np.float32)

    if data.size == 0:
        logger.logger.info(f"[S1_VOX_TUNING] {stem_name}: archivo vacío, se omite.")
        return

    y_tuned = tune_vocal_time_varying(
        y=data,
        sr=sr,
        tuning_strength=float(tuning_strength),
        max_shift_semitones=float(max_pitch_shift_semitones)
        if max_pitch_shift_semitones is not None
        else None,
        pitch_cents_max_deviation=float(pitch_cents_max_deviation)
        if pitch_cents_max_deviation is not None
        else None,
        allowed_scale_pcs=scale_pcs,
    )

    sf.write(file_path, y_tuned, sr)

    logger.logger.info(
        f"[S1_VOX_TUNING] {stem_name}: afinación time-varying aplicada "
        f"(tuning_strength={tuning_strength}, max_shift={max_pitch_shift_semitones}, "
        f"scale_pcs={scale_pcs})."
    )


# -------------------------------------------------------------------
# -------------------------------------------------------------------
def _tune_stem_worker(
    args: Tuple[Dict[str, Any], float | None, float | None, float | None, List[int] | None]
) -> None:
    """
    Wrapper para ejecutar la afinación de un stem vocal en un proceso hijo.
    """
    (
        stem_info,
        pitch_cents_max_deviation,
        tuning_strength,
        max_pitch_shift_semitones,
        scale_pcs,
    ) = args

    apply_vocal_tuning_to_stem(
        stem_info=stem_info,
        pitch_cents_max_deviation=pitch_cents_max_deviation,
        tuning_strength=tuning_strength,
        max_pitch_shift_semitones=max_pitch_shift_semitones,
        scale_pcs=scale_pcs,
    )


def main() -> None:
    """
    Stage S1_VOX_TUNING:
      - Lee analysis_S1_VOX_TUNING.json.
      - Aplica afinación nota-a-nota SOLO a stems vocales (según instrument_profile),
        respetando la escala detectada en S1_KEY_DETECTION.
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S1_VOX_TUNING.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S1_VOX_TUNING"

    analysis = load_analysis(contract_id)

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {})
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {})
    session: Dict[str, Any] = analysis.get("session", {})
    stems: List[Dict[str, Any]] = analysis.get("stems", [])

    pitch_cents_max_deviation = metrics.get("pitch_cents_max_deviation")
    tuning_strength = metrics.get("tuning_strength_0_1", 1.0)
    max_pitch_shift_semitones = limits.get("max_pitch_shift_semitones")

    scale_pcs = session.get("scale_pitch_classes")
    # scale_pcs debería ser lista de enteros [0-11] (C=0). Si no, lo dejamos en None.
    if not isinstance(scale_pcs, list) or not scale_pcs:
        scale_pcs = None

    # Filtramos solo los stems vocales para procesarlos en paralelo
    vocal_stems: List[Dict[str, Any]] = [
        s for s in stems if s.get("is_vocal_stem", False)
    ]

    if vocal_stems:
        max_workers = min(4, os.cpu_count() or 1)
        args_list: List[
            Tuple[Dict[str, Any], float | None, float | None, float | None, List[int] | None]
        ] = [
            (
                stem_info,
                pitch_cents_max_deviation,
                tuning_strength,
                max_pitch_shift_semitones,
                scale_pcs,
            )
            for stem_info in vocal_stems
        ]

        for args in args_list:
            _tune_stem_worker(args)

    logger.logger.info(f"[S1_VOX_TUNING] Procesados {len(vocal_stems)} stems vocales.")


if __name__ == "__main__":
    main()
