# C:\mix-master\backend\src\analysis\S1_STEM_WORKING_LOUDNESS.py

import sys
from pathlib import Path
from typing import Dict, Any, List

# --- hack para poder importar utils cuando se ejecuta como script ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import os  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from utils.analysis_utils import (  # noqa: E402
    load_contract,
    get_temp_dir,
    load_audio_mono,
    compute_peak_dbfs,
    compute_integrated_loudness_lufs,
)
from utils.session_utils import (  # noqa: E402
    load_session_config,
    infer_bus_target,
)


def analyze_stem(stem_path: Path) -> Dict[str, Any]:
    """
    Analiza loudness de trabajo por stem:
      - LUFS integrado
      - true peak aprox. en dBFS
      - samplerate
    """
    mono, sr = load_audio_mono(stem_path)

    integrated_lufs = compute_integrated_loudness_lufs(mono, sr)
    true_peak_dbfs = compute_peak_dbfs(mono)

    return {
        "file_name": stem_path.name,
        "file_path": str(stem_path),
        "samplerate_hz": sr,
        "integrated_lufs": integrated_lufs,
        "true_peak_dbfs": true_peak_dbfs,
    }


def compute_mixbus_peak_dbfs(stem_paths: List[Path]) -> float:
    """
    Calcula el pico del mix preliminar (suma unity de todos los stems).
    Asume que todos los stems tienen mismo samplerate y nº de canales
    (esto debería estar garantizado por S0_SESSION_FORMAT).
    """
    if not stem_paths:
        return float("-inf")

    data_list = []
    sr_ref = None
    ch_ref = None

    for p in stem_paths:
        data, sr = sf.read(p, always_2d=True)  # (n_samples, n_channels)
        data = data.astype(np.float32)

        if sr_ref is None:
            sr_ref = sr
            ch_ref = data.shape[1]
        # Para simplificar, asumimos que el resto coincide; si no, sería
        # el momento de añadir checks o resample.

        data_list.append(data)

    max_len = max(d.shape[0] for d in data_list)
    mix = np.zeros((max_len, ch_ref), dtype=np.float32)

    for d in data_list:
        n = d.shape[0]
        mix[:n, :] += d

    peak = float(np.max(np.abs(mix)))
    if peak <= 0.0:
        return float("-inf")

    return float(20.0 * np.log10(peak))


def main() -> None:
    """
    Análisis para el contrato S1_STEM_WORKING_LOUDNESS.

    Uso esperado desde stage.py:
        python analysis/S1_STEM_WORKING_LOUDNESS.py S1_STEM_WORKING_LOUDNESS
    """
    if len(sys.argv) < 2:
        print("Uso: python S1_STEM_WORKING_LOUDNESS.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S1_STEM_WORKING_LOUDNESS"

    # 1) Cargar contrato y directorio temp/<contract_id>
    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    temp_dir = get_temp_dir(contract_id, create=True)

    # 2) Cargar config de sesión (instrument_profile y style_preset)
    cfg = load_session_config(contract_id)
    style_preset = cfg["style_preset"]
    instrument_by_file = cfg["instrument_by_file"]

    # 3) Analizar stems
    stem_files: List[Path] = sorted(
        p for p in temp_dir.glob("*.wav")
        if p.name.lower() != "full_song.wav"
    )

    stems_analysis: List[Dict[str, Any]] = []
    lufs_values: List[float] = []
    true_peaks_values: List[float] = []

    if stem_files:
        # --- aquí paralelizamos el análisis por stem ---
        max_workers = min(4, os.cpu_count() or 1)
        with ProcessPoolExecutor(max_workers=max_workers) as ex:
            # ex.map devuelve en el mismo orden que stem_files
            results = list(ex.map(analyze_stem, stem_files))
    else:
        results = []

    for stem_info in results:
        file_name = stem_info["file_name"]
        requested_profile = instrument_by_file.get(file_name, "Other")

        if str(requested_profile).lower() == "auto":
            resolved_profile = "Other"
        else:
            resolved_profile = requested_profile

        bus_target = infer_bus_target(resolved_profile)

        stem_info["instrument_profile_requested"] = requested_profile
        stem_info["instrument_profile_resolved"] = resolved_profile
        stem_info["bus_target"] = bus_target

        stems_analysis.append(stem_info)

        lufs_values.append(stem_info["integrated_lufs"])
        true_peaks_values.append(stem_info["true_peak_dbfs"])

    # 4) Calcular pico del mix preliminar (suma unity)
    mixbus_peak_dbfs_measured = compute_mixbus_peak_dbfs(stem_files)

    # 5) Construir estado de sesión con métricas agregadas
    if true_peaks_values:
        max_true_peak_dbfs = float(max(true_peaks_values))
    else:
        max_true_peak_dbfs = float("-inf")

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            # Targets típicos que el check podría validar:
            # - true_peak_per_stem <= -3 dBTP
            # - mixbus_peak <= -6 dBFS
            "true_peak_per_stem_target_max_dbtp": -3.0,
            "mixbus_peak_target_max_dbfs": -6.0,
            # Medidas reales:
            "max_true_peak_dbfs_measured": max_true_peak_dbfs,
            "mixbus_peak_dbfs_measured": mixbus_peak_dbfs_measured,
        },
        "stems": stems_analysis,
    }

    # 6) Guardar JSON de análisis
    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    print(
        f"[S1_STEM_WORKING_LOUDNESS] Análisis completado. "
        f"JSON guardado en: {output_path} (stems={len(stems_analysis)})"
    )


if __name__ == "__main__":
    main()
