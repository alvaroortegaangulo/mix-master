# C:\mix-master\backend\src\stages\S3_MIXBUS_HEADROOM.py

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
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from utils.analysis_utils import get_temp_dir, sf_read_limited  # noqa: E402
from utils.loudness_utils import measure_integrated_lufs, measure_true_peak_dbfs  # noqa: E402


# ---------------------------
# Load analysis
# ---------------------------

def load_analysis(contract_id: str) -> Dict[str, Any]:
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"
    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")
    with analysis_path.open("r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------
# Mix measurement (same as analysis, but local/authoritative)
# ---------------------------

def _load_stem_audio(path: Path) -> Tuple[np.ndarray, int]:
    y, sr = sf_read_limited(path, always_2d=True)
    y = np.asarray(y, dtype=np.float32)
    if y.ndim == 1:
        y = y[:, None]
    return y, int(sr)


def _mix_stems_sum(stem_paths: List[Path]) -> Tuple[np.ndarray, int]:
    if not stem_paths:
        return np.zeros((1, 1), dtype=np.float32), 44100

    data_list: List[np.ndarray] = []
    sr_ref: int | None = None
    ch_ref: int | None = None

    for p in stem_paths:
        y, sr = _load_stem_audio(p)
        if y.size == 0:
            continue

        if sr_ref is None:
            sr_ref = sr
        if ch_ref is None:
            ch_ref = y.shape[1]

        if y.shape[1] != ch_ref:
            if y.shape[1] == 1 and ch_ref == 2:
                y = np.repeat(y, 2, axis=1)
            elif y.shape[1] == 2 and ch_ref == 1:
                y = np.mean(y, axis=1, keepdims=True)
            else:
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
    x = np.asarray(mix, dtype=np.float32)
    if x.ndim == 1:
        return float(measure_true_peak_dbfs(x, sr))
    if x.ndim == 2 and x.shape[1] >= 1:
        peaks = [float(measure_true_peak_dbfs(x[:, ch], sr)) for ch in range(x.shape[1])]
        return float(max(peaks)) if peaks else float("-inf")
    return float("-inf")


def _measure_mix(stem_paths: List[Path]) -> Tuple[float, float, int]:
    """
    Devuelve (true_peak_dbfs, lufs_integrated, sr)
    """
    mix, sr = _mix_stems_sum(stem_paths)
    if mix.size == 0:
        return float("-inf"), float("-inf"), sr

    peak = _true_peak_dbfs_multichannel(mix, sr)

    mix_mono = np.mean(mix, axis=1).astype(np.float32) if mix.ndim == 2 else mix.astype(np.float32)
    lufs = float(measure_integrated_lufs(mix_mono, sr))
    return float(peak), float(lufs), int(sr)


# ---------------------------
# Gain decision (headroom-first)
# ---------------------------

def _compute_gain_step_db(
    mix_peak: float,
    mix_lufs: float,
    metrics: Dict[str, Any],
    limits: Dict[str, Any],
) -> float:
    """
    Headroom-first:
      - Si peak > peak_max -> reduce lo necesario (negativo).
      - Si LUFS > lufs_max -> reduce lo necesario (negativo).
      - Nunca hace boost en este stage (solo recorta si excede límites).
      - Cap por max_gain_change_db_per_pass.
    """
    peak_max = float(metrics.get("peak_dbfs_max", -6.0))
    lufs_max = float(metrics.get("lufs_integrated_max", -20.0))

    # márgenes pequeños para evitar oscilación
    peak_margin = float(metrics.get("peak_margin_db", 0.10))
    lufs_margin = float(metrics.get("lufs_margin_db", 0.10))

    max_step = float(limits.get("max_gain_change_db_per_pass", 3.0))

    need_peak = 0.0
    if mix_peak > peak_max + peak_margin:
        need_peak = peak_max - mix_peak  # negativo

    need_lufs = 0.0
    if mix_lufs > lufs_max + lufs_margin:
        need_lufs = lufs_max - mix_lufs  # negativo

    # Necesidad total (más restrictiva, siempre <= 0)
    gain_needed = min(0.0, need_peak, need_lufs)

    # cap por paso
    if gain_needed < -max_step:
        gain_step = -max_step
    else:
        gain_step = gain_needed

    if abs(gain_step) < 0.05:
        return 0.0

    return float(gain_step)


def _apply_gain_to_file(path: Path, gain_db: float) -> bool:
    try:
        data, sr = sf.read(path, always_2d=False)
        x = np.asarray(data, dtype=np.float32)
        if x.size == 0:
            return False

        scale = float(10.0 ** (gain_db / 20.0))
        y = x * scale

        # Guardar como FLOAT para no truncar/clippear
        sf.write(path, y, int(sr), subtype="FLOAT")
        return True
    except Exception as e:
        logger.logger.info(f"[S3_MIXBUS_HEADROOM] Error aplicando gain a {path.name}: {e}")
        return False


def _save_headroom_metrics(
    temp_dir: Path,
    contract_id: str,
    pre_peak: float,
    pre_lufs: float,
    post_peak: float,
    post_lufs: float,
    total_gain_db: float,
    iterations: int,
    metrics: Dict[str, Any],
    limits: Dict[str, Any],
    sr: int,
) -> None:
    out = temp_dir / "headroom_metrics_S3_MIXBUS_HEADROOM.json"
    payload = {
        "contract_id": contract_id,
        "samplerate_hz": sr,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "pre": {"mix_peak_dbfs": pre_peak, "mix_lufs_integrated": pre_lufs},
        "post": {"mix_peak_dbfs": post_peak, "mix_lufs_integrated": post_lufs},
        "total_gain_db_applied": total_gain_db,
        "iterations": iterations,
    }
    with out.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    logger.logger.info(f"[S3_MIXBUS_HEADROOM] Métricas guardadas en: {out}")


def main() -> None:
    """
    Stage S3_MIXBUS_HEADROOM:

      - Re-mide mix peak/LUFS sin normalización.
      - Aplica gain global NEGATIVO en iteraciones hasta cumplir peak_max / lufs_max,
        respetando max_gain_change_db_per_pass por iteración.
      - Guarda headroom_metrics_S3_MIXBUS_HEADROOM.json (pre/post).
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S3_MIXBUS_HEADROOM.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]

    analysis = load_analysis(contract_id)

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}
    stems: List[Dict[str, Any]] = analysis.get("stems", []) or []

    temp_dir = get_temp_dir(contract_id, create=False)

    # Lista de stems (paths)
    stem_paths: List[Path] = []
    for s in stems:
        fp = s.get("file_path")
        fn = s.get("file_name")
        if fn and str(fn).lower() == "full_song.wav":
            continue
        if fp:
            stem_paths.append(Path(fp))

    # Fallback: si no venían paths (caso raro)
    if not stem_paths:
        stem_paths = sorted(
            p for p in temp_dir.glob("*.wav")
            if p.name.lower() != "full_song.wav"
        )

    if not stem_paths:
        logger.logger.info("[S3_MIXBUS_HEADROOM] No hay stems; no-op.")
        return

    # Targets
    peak_max = float(metrics.get("peak_dbfs_max", -6.0))
    lufs_max = float(metrics.get("lufs_integrated_max", -20.0))

    max_iters = int(metrics.get("max_iterations", 6))

    # Medición pre
    pre_peak, pre_lufs, sr = _measure_mix(stem_paths)
    logger.logger.info(
        f"[S3_MIXBUS_HEADROOM] PRE: true_peak={pre_peak:.2f} dBFS, LUFS={pre_lufs:.2f} "
        f"(targets peak<= {peak_max:.2f}, lufs<= {lufs_max:.2f})"
    )

    total_gain = 0.0
    iterations = 0

    cur_peak, cur_lufs = pre_peak, pre_lufs

    for i in range(max_iters):
        gain_step = _compute_gain_step_db(cur_peak, cur_lufs, metrics, limits)
        if abs(gain_step) < 1e-6:
            break

        # Aplicar a todos los stems
        applied = 0
        for p in stem_paths:
            if _apply_gain_to_file(p, gain_step):
                applied += 1

        total_gain += float(gain_step)
        iterations += 1

        # Re-medición
        cur_peak, cur_lufs, _ = _measure_mix(stem_paths)

        logger.logger.info(
            f"[S3_MIXBUS_HEADROOM] Iter {i+1}/{max_iters}: step={gain_step:.2f} dB "
            f"(total={total_gain:.2f} dB) | stems={applied} | "
            f"POST_iter: true_peak={cur_peak:.2f} dBFS, LUFS={cur_lufs:.2f}"
        )

        # Si ya cumple límites duros, cortamos
        if (cur_peak <= peak_max + 0.10) and (cur_lufs <= lufs_max + 0.10):
            break

    # Métricas finales
    post_peak, post_lufs = cur_peak, cur_lufs
    logger.logger.info(
        f"[S3_MIXBUS_HEADROOM] POST: true_peak={post_peak:.2f} dBFS, LUFS={post_lufs:.2f} "
        f"| total_gain={total_gain:.2f} dB | iterations={iterations}"
    )

    _save_headroom_metrics(
        temp_dir=temp_dir,
        contract_id=contract_id,
        pre_peak=pre_peak,
        pre_lufs=pre_lufs,
        post_peak=post_peak,
        post_lufs=post_lufs,
        total_gain_db=total_gain,
        iterations=iterations,
        metrics=metrics,
        limits=limits,
        sr=sr,
    )


if __name__ == "__main__":
    main()
