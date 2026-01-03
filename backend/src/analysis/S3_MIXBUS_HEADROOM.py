# C:\mix-master\backend\src\analysis\S3_MIXBUS_HEADROOM.py

from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

# --- hack para importar utils cuando se ejecuta como script suelto ---
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
from utils.loudness_utils import (  # noqa: E402
    measure_integrated_lufs,
    measure_true_peak_dbfs,
)


def _load_stem_audio(stem_path: Path) -> Tuple[np.ndarray, int]:
    """
    Lee un stem y lo devuelve como float32, siempre 2D: (N, C).
    """
    y, sr = sf_read_limited(stem_path, always_2d=True)
    y = np.asarray(y, dtype=np.float32)
    if y.ndim == 1:
        y = y[:, None]
    return y, int(sr)


def _mix_stems_sum(stem_files: List[Path]) -> Tuple[np.ndarray, int]:
    """
    Suma UNITY de todos los stems (sin normalizar) para medir headroom real.

    Devuelve (mix, sr) con mix como (N, C).
    """
    if not stem_files:
        return np.zeros((1, 1), dtype=np.float32), 44100

    data_list: List[np.ndarray] = []
    sr_ref: int | None = None
    ch_ref: int | None = None

    for p in stem_files:
        y, sr = _load_stem_audio(p)
        if y.size == 0:
            continue
        if sr_ref is None:
            sr_ref = sr
        if ch_ref is None:
            ch_ref = y.shape[1]

        # Si algún stem viene mono y otros stereo, lo adaptamos (no debería pasar si S0 hizo su trabajo)
        if y.shape[1] != ch_ref:
            if y.shape[1] == 1 and ch_ref == 2:
                y = np.repeat(y, 2, axis=1)
            elif y.shape[1] == 2 and ch_ref == 1:
                y = np.mean(y, axis=1, keepdims=True)
            else:
                # Caso raro: forzamos a mínimo común (fallback seguro)
                min_ch = min(int(y.shape[1]), int(ch_ref))
                y = y[:, :min_ch]
                ch_ref = min_ch

        data_list.append(y)

    if not data_list:
        return np.zeros((1, 1), dtype=np.float32), (sr_ref or 44100)

    max_len = max(d.shape[0] for d in data_list)
    mix = np.zeros((max_len, int(ch_ref)), dtype=np.float32)

    for d in data_list:
        n = d.shape[0]
        mix[:n, :] += d

    return mix, (sr_ref or 44100)


def _true_peak_dbfs_multichannel(mix: np.ndarray, sr: int) -> float:
    """
    True peak como máximo entre canales, usando tu util measure_true_peak_dbfs (1D).
    """
    x = np.asarray(mix, dtype=np.float32)
    if x.ndim == 1:
        return float(measure_true_peak_dbfs(x, sr))
    if x.ndim == 2 and x.shape[1] >= 1:
        peaks = [float(measure_true_peak_dbfs(x[:, ch], sr)) for ch in range(x.shape[1])]
        return float(max(peaks)) if peaks else float("-inf")
    return float("-inf")


def _sample_peak_dbfs_multichannel(mix: np.ndarray) -> float:
    """
    Peak de sample (no true peak) para diagnóstico rápido.
    """
    x = np.asarray(mix, dtype=np.float32)
    if x.size == 0:
        return float("-inf")
    peak = float(np.max(np.abs(x)))
    if peak <= 0.0:
        return float("-inf")
    return float(20.0 * np.log10(peak))


def main() -> None:
    """
    Análisis para el contrato S3_MIXBUS_HEADROOM.

    Uso esperado desde stage.py:
        python analysis/S3_MIXBUS_HEADROOM.py S3_MIXBUS_HEADROOM
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S3_MIXBUS_HEADROOM.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]

    # 1) Cargar contrato
    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    peak_dbfs_min = float(metrics.get("peak_dbfs_min", -12.0))
    peak_dbfs_max = float(metrics.get("peak_dbfs_max", -6.0))
    lufs_min = float(metrics.get("lufs_integrated_min", -28.0))
    lufs_max = float(metrics.get("lufs_integrated_max", -20.0))

    # 2) Directorio temp/<contract_id> y session_config
    temp_dir = get_temp_dir(contract_id, create=True)

    cfg = load_session_config(contract_id)
    style_preset = cfg["style_preset"]
    instrument_by_file = cfg["instrument_by_file"]

    # 3) Listar stems (.wav) excluyendo full_song.wav
    stem_files: List[Path] = sorted(
        p for p in temp_dir.glob("*.wav")
        if p.name.lower() != "full_song.wav"
    )

    # 4) Mezcla UNITY (sin normalizar) para medir headroom real
    mix, sr = _mix_stems_sum(stem_files)

    if mix.size == 0:
        mix_peak_dbfs = float("-inf")
        mix_lufs_integrated = float("-inf")
        mix_sample_peak_dbfs = float("-inf")
    else:
        mix_peak_dbfs = _true_peak_dbfs_multichannel(mix, sr)
        mix_sample_peak_dbfs = _sample_peak_dbfs_multichannel(mix)

        # Para LUFS: downmix a mono (media) para estabilidad
        mix_mono = np.mean(mix, axis=1).astype(np.float32) if mix.ndim == 2 else mix.astype(np.float32)
        mix_lufs_integrated = float(measure_integrated_lufs(mix_mono, sr))

    # 5) Estructura de stems
    stems_info: List[Dict[str, Any]] = []
    for p in stem_files:
        fname = p.name
        inst = instrument_by_file.get(fname, "Other")
        stems_info.append(
            {
                "file_name": fname,
                "file_path": str(p),
                "instrument_profile": inst,
            }
        )

    # 6) JSON análisis
    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "peak_dbfs_min_target": peak_dbfs_min,
            "peak_dbfs_max_target": peak_dbfs_max,
            "lufs_integrated_min_target": lufs_min,
            "lufs_integrated_max_target": lufs_max,
            "mix_peak_dbfs_measured": mix_peak_dbfs,
            "mix_sample_peak_dbfs_measured": mix_sample_peak_dbfs,
            "mix_lufs_integrated_measured": mix_lufs_integrated,
            "num_stems": len(stem_files),
            "samplerate_hz": sr,
        },
        "stems": stems_info,
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    logger.logger.info(
        f"[S3_MIXBUS_HEADROOM] Análisis completado. "
        f"true_peak={mix_peak_dbfs:.2f} dBFS, sample_peak={mix_sample_peak_dbfs:.2f} dBFS, "
        f"LUFS={mix_lufs_integrated:.2f}. JSON: {output_path}"
    )


if __name__ == "__main__":
    main()
