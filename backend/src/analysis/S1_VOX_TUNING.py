from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple
import os
from concurrent.futures import ProcessPoolExecutor

# --- hack para poder importar utils cuando se ejecuta como script suelto ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
import librosa  # noqa: E402

from utils.analysis_utils import (  # noqa: E402
    load_contract,
    get_temp_dir,
    PROJECT_ROOT,
)
from utils.session_utils import (  # noqa: E402
    load_session_config,
)
from utils.vocal_utils import is_vocal_profile  # noqa: E402
from utils.pitch_utils import estimate_pitch_deviation  # noqa: E402


def analyze_stem(args: Tuple[Path, str, bool]) -> Dict[str, Any]:
    """
    Worker para ProcessPoolExecutor.

    Recibe:
      - stem_path: ruta al .wav
      - instrument_profile: etiqueta de instrumento desde instrument_by_file
      - is_vocal: si el perfil se considera vocal (is_vocal_profile)

    Solo si es vocal se carga el audio y se estima la desviación de afinación.
    Devuelve un dict con el mismo formato que en la versión secuencial.
    """
    stem_path, instrument_profile, is_vocal = args
    file_name = stem_path.name

    max_abs_dev_cents = None
    median_dev_cents = None
    recommended_shift_semitones = 0.0

    if is_vocal:
        # Cargar audio (mono)
        y, sr = sf.read(stem_path, always_2d=False)
        if isinstance(y, np.ndarray) and y.ndim > 1:
            y_mono = np.mean(y, axis=1).astype(np.float32)
        else:
            y_mono = np.asarray(y, dtype=np.float32)

        pitch_stats = estimate_pitch_deviation(y_mono, sr)
        max_abs_dev_cents = pitch_stats["max_abs_deviation_cents"]
        median_dev_cents = pitch_stats["median_deviation_cents"]
        recommended_shift_semitones = pitch_stats["recommended_global_shift_semitones"]

    return {
        "file_name": file_name,
        "file_path": str(stem_path),
        "instrument_profile": instrument_profile,
        "is_vocal_stem": is_vocal,
        "estimated_pitch_deviation_cents_max": max_abs_dev_cents,
        "estimated_pitch_deviation_cents_median": median_dev_cents,
        "recommended_global_shift_semitones": recommended_shift_semitones,
    }


def main() -> None:
    """
    Análisis para el contrato S1_VOX_TUNING.

    Uso esperado desde stage.py:
        python analysis/S1_VOX_TUNING.py S1_VOX_TUNING
    """
    if len(sys.argv) < 2:
        print("Uso: python S1_VOX_TUNING.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S1_VOX_TUNING"

    # 1) Cargar contrato
    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    # 2) Directorio temp/<contract_id> y session_config
    temp_dir = get_temp_dir(contract_id, create=True)

    cfg = load_session_config(contract_id)
    style_preset = cfg["style_preset"]
    instrument_by_file = cfg["instrument_by_file"]

    # 2b) Leer análisis previo de S1_KEY_DETECTION (si existe) para traer la escala
    key_root_pc = None
    key_mode = None
    key_name = None
    scale_pcs = None

    key_analysis_path = PROJECT_ROOT / "temp" / "S1_KEY_DETECTION" / "analysis_S1_KEY_DETECTION.json"
    if key_analysis_path.exists():
        with key_analysis_path.open("r", encoding="utf-8") as f:
            key_data = json.load(f)
        key_session = key_data.get("session", {})
        key_root_pc = key_session.get("key_root_pc")
        key_mode = key_session.get("key_mode")
        key_name = key_session.get("key_name")
        scale_pcs = key_session.get("scale_pitch_classes")

    # 3) Listar stems (.wav) en temp/<contract_id>, excluyendo full_song.wav
    stem_files: List[Path] = sorted(
        p for p in temp_dir.glob("*.wav")
        if p.name.lower() != "full_song.wav"
    )

    # Preparar tareas para el pool: (stem_path, instrument_profile, is_vocal)
    stem_tasks: List[Tuple[Path, str, bool]] = []
    for stem_path in stem_files:
        file_name = stem_path.name
        instrument_profile = instrument_by_file.get(file_name, "Other")
        is_vocal = is_vocal_profile(instrument_profile)
        stem_tasks.append((stem_path, instrument_profile, is_vocal))

    # --- Análisis paralelo ---
    if stem_tasks:
        max_workers = min(4, os.cpu_count() or 1)
        with ProcessPoolExecutor(max_workers=max_workers) as ex:
            results = list(ex.map(analyze_stem, stem_tasks))
    else:
        results = []

    stems_analysis: List[Dict[str, Any]] = list(results)
    vocal_count = sum(1 for s in stems_analysis if s["is_vocal_stem"])

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
            # info de tonalidad/escala importada de S1_KEY_DETECTION
            "key_root_pc": key_root_pc,
            "key_mode": key_mode,
            "key_name": key_name,
            "scale_pitch_classes": scale_pcs,
        },
        "stems": stems_analysis,
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    print(
        f"[S1_VOX_TUNING] Análisis completado. "
        f"{vocal_count} stems vocales detectados de {len(stems_analysis)}. "
        f"JSON guardado en: {output_path}"
    )


if __name__ == "__main__":
    main()
