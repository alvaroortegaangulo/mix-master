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

from utils.analysis_utils import get_temp_dir  # noqa: E402

try:
    from utils.loudness_utils import (  # type: ignore  # noqa: E402
        measure_integrated_lufs,
        measure_true_peak_dbtp,
    )
except Exception:  # pragma: no cover
    measure_integrated_lufs = None  # type: ignore
    measure_true_peak_dbtp = None  # type: ignore


def load_analysis(contract_id: str) -> Dict[str, Any]:
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"
    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")
    with analysis_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _dbfs_from_peak(peak_lin: float) -> float:
    if peak_lin <= 0.0:
        return float("-inf")
    return float(20.0 * np.log10(float(peak_lin)))


def _mixbus_sample_peak_stream(stem_files: List[Path], block_size: int = 65536) -> float:
    """
    Pico sample-peak del sumatorio, sin normalizar.
    """
    if not stem_files:
        return float("-inf")

    files: List[sf.SoundFile] = []
    try:
        for p in stem_files:
            files.append(sf.SoundFile(str(p), mode="r"))

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

        return _dbfs_from_peak(peak_lin)

    finally:
        for f in files:
            try:
                f.close()
            except Exception:
                pass


def _apply_gain_inplace(path: Path, gain_db: float) -> bool:
    """
    Aplica ganancia y reescribe el stem en FLOAT para evitar clips por PCM.
    """
    try:
        x, sr = sf.read(path, always_2d=True)
        arr = np.asarray(x, dtype=np.float32)
        if arr.size == 0:
            return False

        g_lin = float(10.0 ** (float(gain_db) / 20.0))
        y = (arr * g_lin).astype(np.float32)

        sf.write(path, y, int(sr), subtype="FLOAT")
        return True
    except Exception as e:
        logger.logger.info(f"[S3_MIXBUS_HEADROOM] Error aplicando gain a {path.name}: {e}")
        return False


def main() -> None:
    """
    Stage S3_MIXBUS_HEADROOM (corregido):
      - SOLO garantiza headroom por pico (peak_dbfs_max).
      - NO persigue LUFS al centro (evita hundir la mezcla).
      - Métricas pre/post guardadas en headroom_metrics_S3_MIXBUS_HEADROOM.json.
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S3_MIXBUS_HEADROOM.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]
    analysis = load_analysis(contract_id)

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}
    session: Dict[str, Any] = analysis.get("session", {}) or {}
    stems: List[Dict[str, Any]] = analysis.get("stems", []) or []

    peak_max = float(metrics.get("peak_dbfs_max", session.get("peak_dbfs_max_target", -6.0)))
    lufs_min = float(metrics.get("lufs_integrated_min", session.get("lufs_integrated_min_target", -28.0)))
    lufs_max = float(metrics.get("lufs_integrated_max", session.get("lufs_integrated_max_target", -20.0)))

    max_gain_step = float(limits.get("max_gain_change_db_per_pass", 3.0))
    MIN_STEP_DB = float(metrics.get("min_gain_step_db", 0.1))

    # Preferimos true-peak si está medido; si no, sample-peak
    pre_true_peak = session.get("mix_true_peak_dbtp_measured", session.get("mix_true_peak_dbfs_measured", float("-inf")))
    pre_sample_peak = session.get("mix_sample_peak_dbfs_measured", float("-inf"))
    pre_lufs = session.get("mix_lufs_integrated_measured", float("-inf"))

    pre_true_peak = float(pre_true_peak) if pre_true_peak is not None else float("-inf")
    pre_sample_peak = float(pre_sample_peak) if pre_sample_peak is not None else float("-inf")
    pre_lufs = float(pre_lufs) if pre_lufs is not None else float("-inf")

    pre_peak = pre_true_peak if np.isfinite(pre_true_peak) else pre_sample_peak
    peak_metric_used = "true_peak_dbtp" if np.isfinite(pre_true_peak) else "sample_peak_dbfs"

    temp_dir = get_temp_dir(contract_id, create=False)
    stem_paths: List[Path] = sorted(
        p for p in temp_dir.glob("*.wav") if p.name.lower() != "full_song.wav"
    )

    # 1) Ganancia: SOLO si peak excede el techo
    gain_db = 0.0
    if pre_peak != float("-inf") and pre_peak > peak_max:
        needed = float(peak_max - pre_peak)  # negativo
        if needed < -abs(max_gain_step):
            needed = -abs(max_gain_step)
        gain_db = float(needed)

    if abs(gain_db) < MIN_STEP_DB:
        gain_db = 0.0

    if gain_db == 0.0:
        # Guardar métricas no-op para QC
        metrics_path = temp_dir / "headroom_metrics_S3_MIXBUS_HEADROOM.json"
        with metrics_path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "contract_id": contract_id,
                    "gain_db_applied": 0.0,
                    "pre": {
                        "sample_peak_dbfs": pre_sample_peak,
                        "true_peak_dbtp": pre_true_peak,
                        "lufs": pre_lufs,
                    },
                    "post": {
                        "sample_peak_dbfs": pre_sample_peak,
                        "true_peak_dbtp": pre_true_peak,
                        "lufs": pre_lufs,
                    },
                    "targets": {"peak_dbfs_max": peak_max, "lufs_min": lufs_min, "lufs_max": lufs_max},
                    "peak_metric_used": peak_metric_used,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

        logger.logger.info(
            f"[S3_MIXBUS_HEADROOM] No-op. {peak_metric_used}_pre={pre_peak:.2f} "
            f"(sample={pre_sample_peak:.2f} dBFS, true={pre_true_peak:.2f} dBTP) <= {peak_max:.2f}. "
            f"LUFS_pre={pre_lufs:.2f}. Métricas: {metrics_path}"
        )
        return

    # 2) Aplicar ganancia a todos los stems
    touched = 0
    for p in stem_paths:
        ok = _apply_gain_inplace(p, gain_db)
        if ok:
            touched += 1

    # 3) Re-medir pico real post (sample-peak de sumatorio) y true-peak opcional
    post_sample_peak = _mixbus_sample_peak_stream(stem_paths)
    post_true_peak = post_sample_peak

    # LUFS post (si hay medidor). Si no, heredamos el pre como “unknown”.
    post_lufs = pre_lufs
    sr_ref = None
    if stem_paths and (measure_integrated_lufs is not None or measure_true_peak_dbtp is not None):
        # Mezcla rápida en memoria para LUFS/TP (solo si tu pipeline lo tolera)
        ys = []
        for p in stem_paths:
            y, sr = sf.read(p, always_2d=False)
            arr = np.asarray(y, dtype=np.float32)
            if arr.ndim > 1:
                arr = np.mean(arr, axis=1).astype(np.float32)
            if sr_ref is None:
                sr_ref = int(sr)
            ys.append(arr)

        if ys and sr_ref is not None:
            max_len = max(len(a) for a in ys)
            mix = np.zeros(max_len, dtype=np.float32)
            for a in ys:
                mix[: len(a)] += a
            if measure_integrated_lufs is not None:
                post_lufs = float(measure_integrated_lufs(mix, int(sr_ref)))
            if measure_true_peak_dbtp is not None:
                post_true_peak = float(measure_true_peak_dbtp(mix, int(sr_ref)))

    # 4) Guardar métricas pre/post para QC
    metrics_path = temp_dir / "headroom_metrics_S3_MIXBUS_HEADROOM.json"
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "contract_id": contract_id,
                "gain_db_applied": float(gain_db),
                "pre": {
                    "sample_peak_dbfs": float(pre_sample_peak),
                    "true_peak_dbtp": float(pre_true_peak),
                    "lufs": float(pre_lufs),
                },
                "post": {
                    "sample_peak_dbfs": float(post_sample_peak),
                    "true_peak_dbtp": float(post_true_peak),
                    "lufs": float(post_lufs),
                },
                "targets": {"peak_dbfs_max": float(peak_max), "lufs_min": float(lufs_min), "lufs_max": float(lufs_max)},
                "peak_metric_used": peak_metric_used,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    logger.logger.info(
        f"[S3_MIXBUS_HEADROOM] Aplicado gain global {gain_db:+.2f} dB a {touched} stems. "
        f"{peak_metric_used}_pre={pre_peak:.2f} -> sample_post={post_sample_peak:.2f} dBFS, "
        f"true_post={post_true_peak:.2f} dBTP (max={peak_max:.2f}). "
        f"LUFS_pre={pre_lufs:.2f} -> LUFS_post={post_lufs:.2f}. Métricas: {metrics_path}"
    )


if __name__ == "__main__":
    main()
