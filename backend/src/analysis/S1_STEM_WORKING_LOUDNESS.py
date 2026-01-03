from utils.logger import logger
# C:\mix-master\backend\src\analysis\S1_STEM_WORKING_LOUDNESS.py

import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

# --- hack para poder importar utils cuando se ejecuta como script ---
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
    load_audio_mono,
    compute_peak_dbfs,
    compute_integrated_loudness_lufs,
)
from utils.session_utils import (  # noqa: E402
    load_session_config,
    infer_bus_target,
)


def _frame_rms_db(x: np.ndarray, eps: float = 1e-12) -> float:
    rms = float(np.sqrt(np.mean(x * x) + eps))
    return float(20.0 * np.log10(rms + eps))


def extract_active_audio(
    mono: np.ndarray,
    sr: int,
    frame_sec: float = 0.40,
    hop_sec: float = 0.20,
    gate_dbfs: float = -55.0,
    rel_gate_margin_db: float = 25.0,
    min_active_ratio: float = 0.05,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Extrae audio "activo" para que el loudness no quede sesgado por silencios.
    Umbral = max(gate_dbfs, p90_rms_db - rel_gate_margin_db)
    """
    mono = np.asarray(mono, dtype=np.float32)
    n = int(mono.size)

    if n == 0 or sr <= 0:
        return mono, {
            "active_ratio": 0.0,
            "active_seconds": 0.0,
            "threshold_dbfs": gate_dbfs,
            "num_frames": 0,
            "num_active_frames": 0,
            "fallback_full_audio": True,
        }

    frame_len = max(256, int(sr * frame_sec))
    hop_len = max(128, int(sr * hop_sec))

    if n < frame_len:
        return mono, {
            "active_ratio": 1.0,
            "active_seconds": n / float(sr),
            "threshold_dbfs": gate_dbfs,
            "num_frames": 1,
            "num_active_frames": 1,
            "fallback_full_audio": True,
        }

    rms_db_list: List[float] = []
    starts: List[int] = []
    for start in range(0, n - frame_len + 1, hop_len):
        frame = mono[start : start + frame_len]
        rms_db_list.append(_frame_rms_db(frame))
        starts.append(start)

    rms_db = np.asarray(rms_db_list, dtype=np.float32)
    if rms_db.size == 0:
        return mono, {
            "active_ratio": 1.0,
            "active_seconds": n / float(sr),
            "threshold_dbfs": gate_dbfs,
            "num_frames": 0,
            "num_active_frames": 0,
            "fallback_full_audio": True,
        }

    p90 = float(np.percentile(rms_db, 90.0))
    thr = max(float(gate_dbfs), p90 - float(rel_gate_margin_db))

    active_frames = rms_db >= thr
    num_active_frames = int(np.sum(active_frames))
    num_frames = int(active_frames.size)

    mask = np.zeros(n, dtype=bool)
    for is_active, start in zip(active_frames.tolist(), starts):
        if is_active:
            mask[start : start + frame_len] = True

    active_ratio = float(np.mean(mask)) if mask.size > 0 else 0.0
    active_seconds = float(np.sum(mask)) / float(sr)

    if active_ratio < float(min_active_ratio):
        return mono, {
            "active_ratio": active_ratio,
            "active_seconds": active_seconds,
            "threshold_dbfs": thr,
            "num_frames": num_frames,
            "num_active_frames": num_active_frames,
            "fallback_full_audio": True,
        }

    return mono[mask], {
        "active_ratio": active_ratio,
        "active_seconds": active_seconds,
        "threshold_dbfs": thr,
        "num_frames": num_frames,
        "num_active_frames": num_active_frames,
        "fallback_full_audio": False,
    }


def _dbfs_from_amp(amp: float, eps: float = 1e-12) -> float:
    if amp <= 0.0:
        return float("-inf")
    return float(20.0 * np.log10(amp + eps))


def estimate_true_peak_linear_interp(
    y: np.ndarray,
    oversample: int = 4,
) -> float:
    """
    Estimación de true peak por sobremuestreo con interpolación lineal (barata).
    No es brickwall-sinc, pero mejora el sample-peak y es suficiente para logs/guardrails.
    """
    y = np.asarray(y, dtype=np.float32)
    n = int(y.size)
    if n <= 1:
        return float(np.max(np.abs(y))) if n == 1 else 0.0

    x = np.arange(n, dtype=np.float32)
    x_new = np.linspace(0.0, float(n - 1), num=(n - 1) * oversample + 1, dtype=np.float32)
    y_new = np.interp(x_new, x, y).astype(np.float32)
    return float(np.max(np.abs(y_new)))


def compute_mixbus_peak_info(
    stem_paths: List[Path],
    block_frames: int = 262144,
    true_peak_window: int = 4096,
) -> Dict[str, Any]:
    """
    Calcula pico del mix preliminar (suma unity) de forma streaming:
      - sample_peak_dbfs
      - peak_frame_index, peak_channel
      - (opcional) estimación de true-peak en una ventana alrededor del pico
    """
    if not stem_paths:
        return {
            "mixbus_peak_dbfs_measured": float("-inf"),
            "mixbus_peak_linear": 0.0,
            "mixbus_peak_frame": None,
            "mixbus_peak_channel": None,
            "mixbus_true_peak_dbtp_est": float("-inf"),
            "mixbus_true_peak_linear_est": 0.0,
        }

    files: List[sf.SoundFile] = [sf.SoundFile(str(p), mode="r") for p in stem_paths]
    try:
        sr_ref = files[0].samplerate
        ch_ref = files[0].channels
        for f in files[1:]:
            # Si quieres, aquí puedes ser más flexible, pero tu S0_SESSION_FORMAT debería uniformizar esto.
            if f.samplerate != sr_ref or f.channels != ch_ref:
                raise ValueError("Samplerate/channels mismatch en stems; S0_SESSION_FORMAT debería uniformizar.")

        best_amp = 0.0
        best_frame = None
        best_ch = None

        pos = 0
        while True:
            blocks = []
            any_data = False
            for f in files:
                b = f.read(frames=block_frames, dtype="float32", always_2d=True)
                if b.shape[0] > 0:
                    any_data = True
                blocks.append(b)

            if not any_data:
                break

            L = max((b.shape[0] for b in blocks), default=0)
            if L <= 0:
                pos += block_frames
                continue

            mix = np.zeros((L, ch_ref), dtype=np.float32)
            for b in blocks:
                if b.shape[0] == 0:
                    continue
                mix[: b.shape[0], :] += b

            abs_mix = np.abs(mix)
            flat_idx = int(np.argmax(abs_mix))
            local_frame, local_ch = np.unravel_index(flat_idx, abs_mix.shape)
            local_amp = float(abs_mix[local_frame, local_ch])

            if local_amp > best_amp:
                best_amp = local_amp
                best_frame = pos + int(local_frame)
                best_ch = int(local_ch)

            pos += block_frames

        peak_dbfs = _dbfs_from_amp(best_amp)

    finally:
        for f in files:
            try:
                f.close()
            except Exception:
                pass

    # True-peak estimado (ventana alrededor del frame pico)
    true_peak_est = 0.0
    true_peak_db = float("-inf")
    if best_frame is not None and best_ch is not None and best_amp > 0.0:
        start = max(0, int(best_frame) - int(true_peak_window))
        length = int(true_peak_window) * 2 + 1

        # Sumamos ventana de todos los stems en ese canal
        y = np.zeros((length,), dtype=np.float32)
        for p in stem_paths:
            with sf.SoundFile(str(p), mode="r") as f:
                f.seek(start)
                b = f.read(frames=length, dtype="float32", always_2d=True)
                if b.shape[0] == 0:
                    continue
                y[: b.shape[0]] += b[:, best_ch]

        true_peak_est = estimate_true_peak_linear_interp(y, oversample=4)
        true_peak_db = _dbfs_from_amp(true_peak_est)

    return {
        "mixbus_peak_dbfs_measured": float(peak_dbfs),
        "mixbus_peak_linear": float(best_amp),
        "mixbus_peak_frame": best_frame,
        "mixbus_peak_channel": best_ch,
        "mixbus_true_peak_dbtp_est": float(true_peak_db),
        "mixbus_true_peak_linear_est": float(true_peak_est),
    }


def analyze_stem(stem_path: Path) -> Dict[str, Any]:
    mono, sr = load_audio_mono(stem_path)

    integrated_lufs = compute_integrated_loudness_lufs(mono, sr)
    true_peak_dbfs = compute_peak_dbfs(mono)

    active_audio, active_stats = extract_active_audio(mono, sr)
    active_lufs = compute_integrated_loudness_lufs(active_audio, sr) if active_audio.size > 0 else float("-inf")

    return {
        "file_name": stem_path.name,
        "file_path": str(stem_path),
        "samplerate_hz": sr,
        "integrated_lufs": float(integrated_lufs) if integrated_lufs is not None else None,
        "active_lufs": float(active_lufs) if active_lufs is not None else None,
        "true_peak_dbfs": float(true_peak_dbfs) if true_peak_dbfs is not None else None,
        "activity": active_stats,
    }


def main() -> None:
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S1_STEM_WORKING_LOUDNESS.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]

    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    temp_dir = get_temp_dir(contract_id, create=True)

    cfg = load_session_config(contract_id)
    style_preset = cfg["style_preset"]
    instrument_by_file = cfg["instrument_by_file"]

    stem_files: List[Path] = sorted(
        p for p in temp_dir.glob("*.wav")
        if p.name.lower() != "full_song.wav"
    )

    stems_analysis: List[Dict[str, Any]] = []
    true_peaks_values: List[float] = []

    results = [analyze_stem(p) for p in stem_files] if stem_files else []
    for stem_info in results:
        file_name = stem_info["file_name"]
        requested_profile = instrument_by_file.get(file_name, "Other")
        resolved_profile = "Other" if str(requested_profile).lower() == "auto" else requested_profile

        bus_target = infer_bus_target(resolved_profile)

        stem_info["instrument_profile_requested"] = requested_profile
        stem_info["instrument_profile_resolved"] = resolved_profile
        stem_info["bus_target"] = bus_target

        stems_analysis.append(stem_info)

        tp = stem_info.get("true_peak_dbfs")
        if tp is not None and tp != float("-inf"):
            true_peaks_values.append(float(tp))

    mixbus_info = compute_mixbus_peak_info(stem_files)

    max_true_peak_dbfs = float(max(true_peaks_values)) if true_peaks_values else float("-inf")

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "true_peak_per_stem_target_max_dbtp": -3.0,
            "mixbus_peak_target_max_dbfs": -6.0,
            "max_true_peak_dbfs_measured": max_true_peak_dbfs,
            **mixbus_info,
        },
        "stems": stems_analysis,
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    logger.logger.info(
        f"[S1_STEM_WORKING_LOUDNESS] Análisis completado. "
        f"JSON guardado en: {output_path} (stems={len(stems_analysis)})"
    )


if __name__ == "__main__":
    main()
