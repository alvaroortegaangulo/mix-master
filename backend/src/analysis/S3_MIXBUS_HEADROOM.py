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
import soundfile as sf  # noqa: E402

from utils.analysis_utils import (  # noqa: E402
    load_contract,
    get_temp_dir,
    sf_read_limited,
)
from utils.session_utils import load_session_config  # noqa: E402

try:
    from utils.loudness_utils import (  # type: ignore  # noqa: E402
        measure_integrated_lufs,
        measure_true_peak_dbtp,
        measure_sample_peak_dbfs,
    )
except Exception:  # pragma: no cover
    measure_integrated_lufs = None  # type: ignore
    measure_true_peak_dbtp = None  # type: ignore
    measure_sample_peak_dbfs = None  # type: ignore


def _dbfs_from_peak(peak_lin: float) -> float:
    if peak_lin <= 0.0:
        return float("-inf")
    return float(20.0 * np.log10(float(peak_lin)))


def _mixbus_sample_peak_stream(stem_files: List[Path], block_size: int = 65536) -> Tuple[float, int | None]:
    """
    Mide el pico REAL (sample-peak) del sumatorio de stems, SIN normalizar.
    Streaming para evitar cargar todo en RAM.

    Devuelve: (mix_peak_dbfs, sr_ref)
    """
    if not stem_files:
        return float("-inf"), None

    files: List[sf.SoundFile] = []
    try:
        for p in stem_files:
            files.append(sf.SoundFile(str(p), mode="r"))

        sr_ref = int(files[0].samplerate)
        ch_ref = int(files[0].channels)

        peak_lin = 0.0
        done = [False] * len(files)

        while not all(done):
            mix_block = None

            for i, f in enumerate(files):
                if done[i]:
                    continue

                x = f.read(block_size, dtype="float32", always_2d=True)
                if x.size == 0:
                    done[i] = True
                    continue

                # Alinear canales a ch_ref (conservador)
                if x.shape[1] != ch_ref:
                    if x.shape[1] == 1 and ch_ref == 2:
                        x = np.repeat(x, 2, axis=1)
                    elif x.shape[1] == 2 and ch_ref == 1:
                        x = np.mean(x, axis=1, keepdims=True)
                    else:
                        x = np.mean(x, axis=1, keepdims=True)
                        if ch_ref == 2:
                            x = np.repeat(x, 2, axis=1)

                if mix_block is None:
                    mix_block = x.astype(np.float32, copy=False)
                else:
                    n = min(mix_block.shape[0], x.shape[0])
                    mix_block[:n, :] += x[:n, :]

            if mix_block is None:
                break

            blk_peak = float(np.max(np.abs(mix_block))) if mix_block.size else 0.0
            if blk_peak > peak_lin:
                peak_lin = blk_peak

        return _dbfs_from_peak(peak_lin), sr_ref

    finally:
        for f in files:
            try:
                f.close()
            except Exception:
                pass


def _mix_to_array_in_memory(stem_files: List[Path], sr_hint: int | None) -> Tuple[np.ndarray, int, int]:
    """
    Mezcla sumando stems SIN normalizar ni mezclar a mono.
    Devuelve (array, sr, ch_ref) donde array tiene forma (n, ch_ref).
    """
    if not stem_files:
        ch_ref = 2
        return np.zeros((1, ch_ref), dtype=np.float32), int(sr_hint or 44100), ch_ref

    ys: List[np.ndarray] = []
    sr_ref: int | None = None
    ch_ref: int | None = None

    for p in stem_files:
        y, sr = sf_read_limited(p, always_2d=True)
        arr = np.asarray(y, dtype=np.float32)
        if sr_ref is None:
            sr_ref = int(sr)
            ch_ref = int(arr.shape[1])
        if ch_ref is None:
            ch_ref = int(arr.shape[1])
        if arr.shape[1] != ch_ref:
            if arr.shape[1] == 1 and ch_ref == 2:
                arr = np.repeat(arr, 2, axis=1)
            elif arr.shape[1] == 2 and ch_ref == 1:
                arr = np.mean(arr, axis=1, keepdims=True)
            else:
                arr = np.mean(arr, axis=1, keepdims=True)
                if ch_ref == 2:
                    arr = np.repeat(arr, 2, axis=1)
        ys.append(arr)

    if not ys:
        ch = int(ch_ref or 2)
        return np.zeros((1, ch), dtype=np.float32), int(sr_ref or sr_hint or 44100), ch

    max_len = max(a.shape[0] for a in ys)
    ch = int(ch_ref or ys[0].shape[1])
    mix = np.zeros((max_len, ch), dtype=np.float32)
    for a in ys:
        n = a.shape[0]
        mix[:n, :] += a

    return mix, int(sr_ref or sr_hint or 44100), ch


def _enforce_true_peak_invariant(sample_peak_dbfs: float, true_peak_dbtp: float, stage_tag: str) -> float:
    """
    Garantiza true_peak >= sample_peak (en lineal). Si se viola, ajusta y loggea.
    """
    if not np.isfinite(sample_peak_dbfs) or not np.isfinite(true_peak_dbtp):
        return true_peak_dbtp

    sample_lin = 10.0 ** (sample_peak_dbfs / 20.0)
    true_lin = 10.0 ** (true_peak_dbtp / 20.0)
    if true_lin + 1e-9 < sample_lin * 0.998:
        logger.logger.info(
            f"[{stage_tag}] Invariante TP>=sample incumplida (sample={sample_peak_dbfs:.2f} dBFS, true={true_peak_dbtp:.2f} dBTP). Ajustando true_peak al sample."
        )
        return float(sample_peak_dbfs)
    return true_peak_dbtp


def main() -> None:
    """
    Análisis para S3_MIXBUS_HEADROOM (sin normalizar).
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S3_MIXBUS_HEADROOM.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]

    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    peak_dbfs_min = float(metrics.get("peak_dbfs_min", -12.0))
    peak_dbfs_max = float(metrics.get("peak_dbfs_max", -6.0))
    lufs_min = float(metrics.get("lufs_integrated_min", -28.0))
    lufs_max = float(metrics.get("lufs_integrated_max", -20.0))

    temp_dir = get_temp_dir(contract_id, create=True)
    cfg = load_session_config(contract_id)
    style_preset = cfg["style_preset"]
    instrument_by_file = cfg["instrument_by_file"]

    stem_files: List[Path] = sorted(
        p for p in temp_dir.glob("*.wav")
        if p.name.lower() != "full_song.wav"
    )

    # 1) pico del sumatorio REAL (sin normalizar)
    mix_sample_peak_dbfs_stream, sr_ref = _mixbus_sample_peak_stream(stem_files)

    # 2) true-peak y LUFS (si están disponibles) usando la misma mezcla
    mix_sample_peak_dbfs = mix_sample_peak_dbfs_stream
    mix_true_peak_dbtp = mix_sample_peak_dbfs_stream
    mix_lufs_integrated = float("-inf")

    if stem_files:
        mix_arr, sr, _ = _mix_to_array_in_memory(stem_files, sr_ref)
        if measure_sample_peak_dbfs is not None:
            mix_sample_peak_dbfs = float(measure_sample_peak_dbfs(mix_arr))
        if measure_true_peak_dbtp is not None:
            mix_true_peak_dbtp = float(measure_true_peak_dbtp(mix_arr, sr))
        mix_true_peak_dbtp = _enforce_true_peak_invariant(
            mix_sample_peak_dbfs, mix_true_peak_dbtp, "S3_MIXBUS_HEADROOM_ANALYSIS"
        )
        if measure_integrated_lufs is not None:
            mix_lufs_integrated = float(measure_integrated_lufs(mix_arr, sr))

    stems_info: List[Dict[str, Any]] = []
    for p in stem_files:
        fname = p.name
        inst = instrument_by_file.get(fname, "Other")
        stems_info.append({"file_name": fname, "file_path": str(p), "instrument_profile": inst})

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
            "mix_sample_peak_dbfs_measured": mix_sample_peak_dbfs,
            "mix_true_peak_dbtp_measured": mix_true_peak_dbtp,
            "mix_true_peak_dbfs_measured": mix_true_peak_dbtp,  # alias legacy
            "mix_lufs_integrated_measured": mix_lufs_integrated,
            "samplerate_hz": sr_ref,
        },
        "stems": stems_info,
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    logger.logger.info(
        f"[S3_MIXBUS_HEADROOM] Análisis OK. "
        f"sample_peak={mix_sample_peak_dbfs:.2f} dBFS, true_peak={mix_true_peak_dbtp:.2f} dBTP, "
        f"LUFS={mix_lufs_integrated:.2f}. JSON: {output_path}"
    )


if __name__ == "__main__":
    main()
