# C:\mix-master\backend\src\analysis\S1_KEY_DETECTION.py

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Any, List

# --- hack para poder importar utils cuando se ejecuta como script suelto ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import os  # noqa: E402

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
import essentia.standard as es  # noqa: E402

from utils.analysis_utils import (  # noqa: E402
    load_contract,
    get_temp_dir,
    sf_read_limited,
)
from utils.session_utils import (  # noqa: E402
    load_session_config,
)

# Nota: mantenemos solo los nombres de nota para mapear a pitch class
_NOTE_NAMES = [
    "C", "C#", "D", "D#", "E", "F",
    "F#", "G", "G#", "A", "A#", "B",
]


# ---------------------------------------------------------------------------
# Carga de stems y mezcla a mono
# ---------------------------------------------------------------------------

def _load_mono_for_mix(path_str: str) -> tuple[np.ndarray, int]:
    """
    Lee un stem desde disco y lo devuelve como (mono_float32, sr).
    Esta función está pensada para ser ejecutada en procesos separados.
    """
    p = Path(path_str)
    y, sr = sf_read_limited(p, always_2d=False)

    if isinstance(y, np.ndarray) and y.ndim > 1:
        y_mono = np.mean(y, axis=1).astype(np.float32)
    else:
        y_mono = np.asarray(y, dtype=np.float32)

    return y_mono, sr


def _mix_stems_mono(stem_files: List[Path]) -> tuple[np.ndarray, int]:
    """
    Hace un mix sencillo de todos los stems a mono, para análisis de tonalidad.
    Asume que todos tienen mismo samplerate (garantizado por S0_SESSION_FORMAT).
    """
    if not stem_files:
        return np.zeros(1, dtype=np.float32), 44100

    path_strs = [str(p) for p in stem_files]

    # Cargar stems en serie (si quieres paralelizar, aquí pondrías ProcessPool)
    results = list(map(_load_mono_for_mix, path_strs))

    data_list: List[np.ndarray] = []
    sr_ref: int | None = None

    for y_mono, sr in results:
        if sr_ref is None:
            sr_ref = sr
        # Asumimos samplerate consistente; si no lo fuera, aquí se podría
        # introducir un resample a sr_ref.
        data_list.append(y_mono)

    if sr_ref is None:
        # Algo raro ha pasado; devolvemos un buffer vacío
        return np.zeros(1, dtype=np.float32), 44100

    max_len = max(len(y) for y in data_list)
    mix = np.zeros(max_len, dtype=np.float32)

    for y in data_list:
        n = len(y)
        mix[:n] += y

    # Normalizar para evitar saturación y estabilizar la detección de tonalidad
    peak = float(np.max(np.abs(mix))) if mix.size > 0 else 0.0
    if peak > 0.0:
        mix /= peak

    return mix, sr_ref


# ---------------------------------------------------------------------------
# Detección de tonalidad con Essentia
# ---------------------------------------------------------------------------

def _detect_key_from_mix(y: np.ndarray, sr: int) -> Dict[str, Any]:
    """
    Detecta tonalidad (nota + modo mayor/menor) a partir de un mix mono
    usando Essentia (KeyExtractor):

      - Devuelve:
        - key_root_pc (0=C, 1=C#, ... 11=B)
        - key_mode ("major" o "minor")
        - key_name ("C major", "A minor", etc.)
        - confidence (~0-1)
    """
    if y.size == 0:
        return {
            "key_root_pc": None,
            "key_mode": None,
            "key_name": None,
            "confidence": None,
        }

    # Aseguramos float32 1D
    audio = np.asarray(y, dtype=np.float32).flatten()

    # Essentia trabaja por defecto a 44.1 kHz; si tu sesión no está ahí,
    # re-muestreamos para estabilizar resultados.
    target_sr = 44100
    if sr != target_sr:
        resample = es.Resample(
            inputSampleRate=float(sr),
            outputSampleRate=float(target_sr),
        )
        audio = resample(audio)
        sr = target_sr

    # KeyExtractor: en tu versión devuelve (key, scale, strength)
    key_extractor = es.KeyExtractor()
    key_str, scale_str, strength = key_extractor(audio)

    # Normalizar strings
    key_str = str(key_str or "").strip()
    scale_str = str(scale_str or "").strip().lower()

    # Mapear nota a pitch class 0-11
    key_root_pc = None
    if key_str in _NOTE_NAMES:
        key_root_pc = int(_NOTE_NAMES.index(key_str))

    # Asegurarnos de que el modo sea "major"/"minor" o None
    if scale_str not in ("major", "minor"):
        key_mode = None
    else:
        key_mode = scale_str

    if key_root_pc is not None and key_mode is not None:
        key_name = f"{_NOTE_NAMES[key_root_pc]} {key_mode}"
    else:
        key_name = None

    # Confianza: usamos strength de Essentia, clamp 0-1 por seguridad
    if strength is None:
        confidence = None
    else:
        confidence = float(strength)
        if confidence < 0.0:
            confidence = 0.0
        if confidence > 1.0:
            confidence = 1.0

    return {
        "key_root_pc": key_root_pc,
        "key_mode": key_mode,
        "key_name": key_name,
        "confidence": confidence,
    }


def _build_scale_degrees_midi(key_root_pc: int, key_mode: str) -> List[int]:
    """
    Devuelve la escala en pitch classes (0-11) relativa a C=0.

    Mayor: 0,2,4,5,7,9,11
    Menor: 0,2,3,5,7,8,10
    """
    if key_mode == "minor":
        pattern = [0, 2, 3, 5, 7, 8, 10]
    else:
        pattern = [0, 2, 4, 5, 7, 9, 11]

    pcs = [int((key_root_pc + step) % 12) for step in pattern]
    return pcs


def main() -> None:
    """
    Análisis para el contrato S1_KEY_DETECTION.

    Uso esperado desde stage.py:
        python analysis/S1_KEY_DETECTION.py S1_KEY_DETECTION
    """
    if len(sys.argv) < 2:
        print("Uso: python S1_KEY_DETECTION.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S1_KEY_DETECTION"

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

    # 3) Listar stems (.wav) en temp/<contract_id>, excluyendo full_song.wav
    stem_files: List[Path] = sorted(
        p for p in temp_dir.glob("*.wav")
        if p.name.lower() != "full_song.wav"
    )

    # 4) Mix de stems para análisis de tonalidad
    mix_mono, sr = _mix_stems_mono(stem_files)
    key_info = _detect_key_from_mix(mix_mono, sr)

    key_root_pc = key_info["key_root_pc"]
    key_mode = key_info["key_mode"]
    scale_pcs = (
        _build_scale_degrees_midi(key_root_pc, key_mode)
        if key_root_pc is not None and key_mode is not None
        else None
    )

    # 5) Construir JSON de salida
    stems_info: List[Dict[str, Any]] = []
    for stem_path in stem_files:
        file_name = stem_path.name
        inst_profile = instrument_by_file.get(file_name, "Other")
        stems_info.append(
            {
                "file_name": file_name,
                "file_path": str(stem_path),
                "instrument_profile": inst_profile,
            }
        )

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "key_root_pc": key_root_pc,
            "key_mode": key_mode,
            "key_name": key_info["key_name"],
            "key_detection_confidence": key_info["confidence"],
            "scale_pitch_classes": scale_pcs,  # 0-11, C=0
        },
        "stems": stems_info,
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    print(
        f"[S1_KEY_DETECTION] Análisis completado. "
        f"Tonalidad detectada: {key_info['key_name']} "
        f"(conf={key_info['confidence']:.2f}). JSON: {output_path}"
    )


if __name__ == "__main__":
    main()
