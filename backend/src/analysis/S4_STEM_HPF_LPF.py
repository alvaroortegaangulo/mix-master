# C:\mix-master\backend\src\analysis\S4_STEM_HPF_LPF.py

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple
import os

# --- hack para importar utils ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from stages.pipeline_context import PipelineContext

import json  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from utils.analysis_utils import (  # noqa: E402
    load_contract,
    get_temp_dir,
    sf_read_limited,
)
from utils.session_utils import load_session_config  # noqa: E402
from utils.profiles_utils import get_hpf_lpf_targets  # noqa: E402


def _analyze_spectrum(
    y: np.ndarray,
    sr: int,
    hpf_target_hz: float | None,
    lpf_target_hz: float | None,
) -> Dict[str, Any]:
    """
    Analiza el contenido espectral de un stem respecto a sus targets HPF/LPF.

    Calcula:
      - total_rms_db: RMS global en dBFS relativos (escala interna).
      - low_rel_db: energía < hpf_target_hz relativa al total (dB).
      - high_rel_db: energía > lpf_target_hz relativa al total (dB).
    """
    if not isinstance(y, np.ndarray):
        y = np.asarray(y, dtype=np.float32)
    else:
        y = y.astype(np.float32)

    if y.ndim > 1:
        y_mono = np.mean(y, axis=1)
    else:
        y_mono = y

    n = y_mono.shape[0]
    if n == 0:
        return {
            "samplerate_hz": sr,
            "total_rms_db": float("-inf"),
            "low_rel_db": None,
            "high_rel_db": None,
        }

    # RMS global
    rms = float(np.sqrt(np.mean(y_mono**2)))
    if rms > 0.0:
        total_rms_db = 20.0 * np.log10(rms)
    else:
        total_rms_db = float("-inf")

    # FFT para distribución de energía
    Y = np.fft.rfft(y_mono)
    magsq = np.abs(Y) ** 2
    freqs = np.fft.rfftfreq(n, d=1.0 / float(sr))

    energy_total = float(np.sum(magsq))
    if energy_total <= 0.0:
        return {
            "samplerate_hz": sr,
            "total_rms_db": total_rms_db,
            "low_rel_db": None,
            "high_rel_db": None,
        }

    nyq = sr / 2.0

    # Definimos bandas en función de los targets
    if hpf_target_hz is None:
        hpf = 20.0
    else:
        hpf = float(hpf_target_hz)
        if hpf < 0.0:
            hpf = 0.0
        if hpf > nyq:
            hpf = nyq

    if lpf_target_hz is None:
        lpf = 20000.0
    else:
        lpf = float(lpf_target_hz)
        if lpf < 0.0:
            lpf = 0.0
        if lpf > nyq:
            lpf = nyq

    # Energía por debajo de HPF (sub-graves que queremos recortar)
    low_mask = freqs < max(20.0, hpf)
    energy_low = float(np.sum(magsq[low_mask]))

    # Energía por encima de LPF (hiss / aire extremo)
    high_mask = freqs > min(lpf, nyq)
    energy_high = float(np.sum(magsq[high_mask]))

    def rel_db(e: float) -> float:
        if e <= 0.0 or energy_total <= 0.0:
            return float("-inf")
        return 10.0 * np.log10(e / energy_total)

    low_rel_db = rel_db(energy_low)
    high_rel_db = rel_db(energy_high)

    return {
        "samplerate_hz": sr,
        "total_rms_db": total_rms_db,
        "low_rel_db": low_rel_db,
        "high_rel_db": high_rel_db,
    }


def _analyze_stem(
    args: Tuple[Path, str, bool]
) -> Dict[str, Any]:
    """

    Recibe:
      - stem_path: ruta al .wav
      - inst_prof: instrument_profile asociado a ese archivo
      - use_profile_ranges: si se usan targets HPF/LPF basados en perfil

    Devuelve el dict de análisis por stem con la misma estructura
    que en la versión secuencial.
    """
    stem_path, inst_prof, use_profile_ranges = args
    fname = stem_path.name

    if use_profile_ranges:
        hpf_target, lpf_target = get_hpf_lpf_targets(inst_prof)
    else:
        # Si no se usan rangos de perfil, dejamos casi fullband
        hpf_target, lpf_target = 20.0, 20000.0

    try:
        y, sr = sf_read_limited(stem_path, always_2d=False)
    except Exception as e:
        print(f"[S4_STEM_HPF_LPF] Aviso: no se puede leer '{fname}': {e}. Se omiten métricas espectrales.")
        return {
            "file_name": fname,
            "file_path": str(stem_path),
            "instrument_profile": inst_prof,
            "hpf_target_hz": hpf_target,
            "lpf_target_hz": lpf_target,
            "samplerate_hz": None,
            "total_rms_db": None,
            "low_rel_db": None,
            "high_rel_db": None,
        }

    spec_metrics = _analyze_spectrum(y, sr, hpf_target, lpf_target)

    return {
        "file_name": fname,
        "file_path": str(stem_path),
        "instrument_profile": inst_prof,
        "hpf_target_hz": hpf_target,
        "lpf_target_hz": lpf_target,
        "samplerate_hz": spec_metrics["samplerate_hz"],
        "total_rms_db": spec_metrics["total_rms_db"],
        "low_rel_db": spec_metrics["low_rel_db"],
        "high_rel_db": spec_metrics["high_rel_db"],
    }


def process(context: PipelineContext) -> None:
    """
    Análisis para el contrato S4_STEM_HPF_LPF.

    Uso desde stage.py:
        python S4_STEM_HPF_LPF.py S4_STEM_HPF_LPF
    """

    contract_id = context.contract_id  # "S4_STEM_HPF_LPF"

    # 1) Cargar contrato
    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    use_profile_ranges = bool(metrics.get("use_instrument_profile_hpf_lpf_ranges", True))
    max_hpf_step = float(limits.get("max_hpf_change_hz_per_pass", 40.0))
    max_lpf_step = float(limits.get("max_lpf_change_hz_per_pass", 4000.0))

    # 2) Directorio temp/<contract_id> y session_config
    temp_dir = get_temp_dir(contract_id, create=True)
    cfg = load_session_config(contract_id)
    style_preset = cfg["style_preset"]
    instrument_by_file = cfg["instrument_by_file"]

    # 3) Listar stems (.wav) de este stage (excluimos full_song.wav)
    stem_files: List[Path] = sorted(
        p for p in temp_dir.glob("*.wav")
        if p.name.lower() != "full_song.wav"
    )

    # 4) Preparar tareas para análisis en serie
    tasks: List[Tuple[Path, str, bool]] = []
    for p in stem_files:
        fname = p.name
        inst_prof = instrument_by_file.get(fname, "Other")
        tasks.append((p, inst_prof, use_profile_ranges))

    stems_analysis: List[Dict[str, Any]] = []
    if tasks:
        stems_analysis = list(map(_analyze_stem, tasks))
    else:
        stems_analysis = []

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "use_instrument_profile_hpf_lpf_ranges": use_profile_ranges,
            "max_hpf_change_hz_per_pass": max_hpf_step,
            "max_lpf_change_hz_per_pass": max_lpf_step,
        },
        "stems": stems_analysis,
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    print(
        f"[S4_STEM_HPF_LPF] Análisis completado para {len(stems_analysis)} stems. "
        f"JSON: {output_path}"
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Uso: python {Path(__file__).name} <CONTRACT_ID>")
        sys.exit(1)

    from dataclasses import dataclass
    @dataclass
    class _MockContext:
        contract_id: str
        next_contract_id: str | None = None

    process(_MockContext(contract_id=sys.argv[1]))
