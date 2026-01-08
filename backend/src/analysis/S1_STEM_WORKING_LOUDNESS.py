# C:\mix-master\backend\src\analysis\S1_STEM_WORKING_LOUDNESS
from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

# --- hack para importar utils ---
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
from utils.profiles_utils import get_instrument_profile  # noqa: E402

try:
    # Si existe, úsalo (mismo medidor que etapas posteriores)
    from utils.loudness_utils import (  # type: ignore  # noqa: E402
        measure_integrated_lufs,
        measure_true_peak_dbtp,
        measure_sample_peak_dbfs,
    )
except Exception:  # pragma: no cover
    measure_integrated_lufs = None  # type: ignore
    measure_true_peak_dbtp = None  # type: ignore
    measure_sample_peak_dbfs = None  # type: ignore


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def _db_from_peak_lin(peak_lin: float) -> float:
    if peak_lin <= 0.0:
        return float("-inf")
    return float(20.0 * np.log10(float(peak_lin)))


def _align_channels(x: np.ndarray, ch_ref: int) -> np.ndarray:
    """
    Alinea canales de forma conservadora para suma.
    """
    x = np.asarray(x, dtype=np.float32)
    if x.ndim == 1:
        x = x[:, None]
    ch = int(x.shape[1])

    if ch == ch_ref:
        return x

    if ch == 1 and ch_ref == 2:
        return np.repeat(x, 2, axis=1)
    if ch == 2 and ch_ref == 1:
        return np.mean(x, axis=1, keepdims=True)

    # raro -> mono y expand si hace falta
    x = np.mean(x, axis=1, keepdims=True)
    if ch_ref == 2:
        x = np.repeat(x, 2, axis=1)
    return x


def _mixbus_sample_peak_stream(
    stem_paths: List[Path],
    block_size: int = 65536,
) -> Tuple[float, int | None]:
    """
    Sample-peak del sumatorio (sin normalizar), streaming (robusto en RAM).
    Devuelve (mix_peak_dbfs, sr_ref).
    """
    if not stem_paths:
        return float("-inf"), None

    files: List[sf.SoundFile] = []
    try:
        for p in stem_paths:
            files.append(sf.SoundFile(str(p), mode="r"))

        sr_ref = int(files[0].samplerate)
        ch_ref = int(files[0].channels)

        for f in files[1:]:
            if int(f.samplerate) != sr_ref:
                logger.logger.info(
                    f"[S1_STEM_WORKING_LOUDNESS] WARN: samplerate distinto en {getattr(f, 'name', '')}."
                )

        peak_lin = 0.0
        done = [False] * len(files)

        while not all(done):
            mix_block: Optional[np.ndarray] = None

            for i, f in enumerate(files):
                if done[i]:
                    continue

                x = f.read(block_size, dtype="float32", always_2d=True)
                if x.size == 0:
                    done[i] = True
                    continue

                x = _align_channels(x, ch_ref)

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

        return _db_from_peak_lin(peak_lin), sr_ref

    finally:
        for f in files:
            try:
                f.close()
            except Exception:
                pass


def _mixbus_true_peak_sum_limited(stem_paths: List[Path]) -> Tuple[float, int | None]:
    """
    True Peak (dBTP) del sumatorio (sin normalizar).
    Estrategia: carga limitada (sf_read_limited) y suma en memoria.
    Si no hay medidor de TP, cae a sample peak.
    """
    if not stem_paths:
        return float("-inf"), None

    # Si no hay TP util, no prometemos dBTP: devolvemos sample-peak como fallback
    tp_available = measure_true_peak_dbtp is not None

    y_sum: Optional[np.ndarray] = None
    sr_ref: Optional[int] = None
    ch_ref: Optional[int] = None

    for p in stem_paths:
        try:
            y, sr = sf_read_limited(p, always_2d=True)
        except Exception as e:
            logger.logger.info(f"[S1_STEM_WORKING_LOUDNESS] WARN: no se pudo leer {p.name}: {e}")
            continue

        x = np.asarray(y, dtype=np.float32)
        if sr_ref is None:
            sr_ref = int(sr)
            ch_ref = int(x.shape[1]) if x.ndim == 2 else 1
        else:
            if int(sr) != int(sr_ref):
                logger.logger.info(
                    f"[S1_STEM_WORKING_LOUDNESS] WARN: sr distinto en {p.name} ({sr} vs {sr_ref}); suma sin resample."
                )

        x = _align_channels(x, int(ch_ref or 2))

        if y_sum is None:
            y_sum = x
        else:
            # padding a max_len
            max_len = max(int(y_sum.shape[0]), int(x.shape[0]))
            if y_sum.shape[0] < max_len:
                pad = np.zeros((max_len - y_sum.shape[0], y_sum.shape[1]), dtype=np.float32)
                y_sum = np.vstack([y_sum, pad])
            if x.shape[0] < max_len:
                pad = np.zeros((max_len - x.shape[0], x.shape[1]), dtype=np.float32)
                x = np.vstack([x, pad])
            y_sum = (y_sum + x).astype(np.float32)

    if y_sum is None or sr_ref is None:
        return float("-inf"), sr_ref

    if tp_available:
        try:
            # max entre canales implícito en el medidor (si lo hace),
            # si no, tu util igualmente debería manejar 2D.
            tp = float(measure_true_peak_dbtp(y_sum, int(sr_ref)))
            return tp, int(sr_ref)
        except Exception as e:
            logger.logger.info(f"[S1_STEM_WORKING_LOUDNESS] WARN: TP mixbus falló, fallback a sample peak: {e}")

    # fallback: sample peak dBFS (no es dBTP)
    pk = float(np.max(np.abs(y_sum))) if y_sum.size else 0.0
    return _db_from_peak_lin(pk), int(sr_ref)


def _analyze_stem(args: Tuple[Path, str, str]) -> Dict[str, Any]:
    """
    Analiza un stem:
      - LUFS integrados
      - true peak (dBTP)
      - sample peak (dBFS)
      - crest_db = true_peak - lufs
      - family + work_loudness_lufs_range (trazabilidad)
    """
    stem_path, requested_profile, resolved_profile = args
    fname = stem_path.name

    try:
        y, sr = sf_read_limited(stem_path, always_2d=True)
    except Exception as e:
        return {
            "file_name": fname,
            "file_path": str(stem_path),
            "instrument_profile_requested": requested_profile,
            "instrument_profile_resolved": resolved_profile,
            "family": None,
            "work_loudness_lufs_range": None,
            "samplerate_hz": None,
            "integrated_lufs": float("-inf"),
            "true_peak_dbtp": float("-inf"),
            "sample_peak_dbfs": float("-inf"),
            "crest_db": float("inf"),
            "error": str(e),
        }

    arr = np.asarray(y, dtype=np.float32)
    mono = np.mean(arr, axis=1).astype(np.float32) if arr.ndim > 1 else arr

    # Perfil (para trazabilidad)
    family = None
    work_range = None
    try:
        prof = get_instrument_profile(resolved_profile)
        family = prof.get("family")
        work_range = prof.get("work_loudness_lufs_range")
    except Exception:
        pass

    # LUFS
    if measure_integrated_lufs is not None:
        lufs = float(measure_integrated_lufs(arr, int(sr)))
    else:
        eps = 1e-12
        rms = float(np.sqrt(np.mean(mono**2)) + eps)
        lufs = float(20.0 * np.log10(rms) - 23.0)  # aproximación grosera

    # True Peak
    if measure_true_peak_dbtp is not None:
        try:
            tp = float(measure_true_peak_dbtp(arr, int(sr)))
        except Exception:
            tp = _db_from_peak_lin(float(np.max(np.abs(arr))) if arr.size else 0.0)
    else:
        tp = _db_from_peak_lin(float(np.max(np.abs(arr))) if arr.size else 0.0)

    # Sample peak
    if measure_sample_peak_dbfs is not None:
        try:
            sample_peak_dbfs = float(measure_sample_peak_dbfs(arr))
        except Exception:
            sample_peak_dbfs = _db_from_peak_lin(float(np.max(np.abs(arr))) if arr.size else 0.0)
    else:
        sample_peak_dbfs = _db_from_peak_lin(float(np.max(np.abs(arr))) if arr.size else 0.0)

    crest = float(tp - lufs) if (lufs != float("-inf") and tp != float("-inf")) else float("inf")

    return {
        "file_name": fname,
        "file_path": str(stem_path),
        "instrument_profile_requested": requested_profile,
        "instrument_profile_resolved": resolved_profile,
        "family": family,
        "work_loudness_lufs_range": work_range,
        "samplerate_hz": int(sr),
        "integrated_lufs": lufs,
        "true_peak_dbtp": tp,
        "true_peak_dbfs": tp,  # alias legacy
        "sample_peak_dbfs": sample_peak_dbfs,
        "crest_db": crest,
        "error": None,
    }


def main() -> None:
    """
    Analysis S1_STEM_WORKING_LOUDNESS:
      - analiza LUFS/TP por stem
      - mide sample-peak del mixbus por suma streaming (legacy/diagnóstico)
      - mide TRUE PEAK del mixbus por suma limitada (dBTP) -> métrica primaria
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S1_STEM_WORKING_LOUDNESS.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]

    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {}) or {}
    limits: Dict[str, Any] = contract.get("limits", {}) or {}
    stage_id: str | None = contract.get("stage_id")

    # Targets recomendados (TP) para headroom real de oversampling
    mixbus_true_peak_target_min_dbtp = float(metrics.get("mixbus_true_peak_target_min_dbtp", -8.0))
    mixbus_true_peak_target_max_dbtp = float(metrics.get("mixbus_true_peak_target_max_dbtp", -6.0))

    # Per-stem ceiling (TP) para evitar stems descontrolados (conservador)
    true_peak_per_stem_target_max_dbtp = float(
        metrics.get("true_peak_per_stem_target_max_dbtp", metrics.get("true_peak_per_stem_target_max_dbfs", -6.0))
    )

    # Legacy: target sample-peak (si existía)
    mixbus_peak_target_max_dbfs = float(metrics.get("mixbus_peak_target_max_dbfs", -6.0))

    # temp y cfg
    temp_dir = get_temp_dir(contract_id, create=True)
    cfg = load_session_config(contract_id)
    style_preset = cfg.get("style_preset", "balanced")
    instrument_by_file = cfg.get("instrument_by_file", {})

    stem_files: List[Path] = sorted(
        p for p in temp_dir.glob("*.wav") if p.name.lower() != "full_song.wav"
    )

    # Resolver perfiles
    tasks: List[Tuple[Path, str, str]] = []
    for p in stem_files:
        req = instrument_by_file.get(p.name, "Other")
        resolved = "Other"
        try:
            if isinstance(req, str) and req.lower().strip() == "auto":
                resolved = "Other"
            else:
                resolved = str(req)
        except Exception:
            resolved = "Other"

        try:
            prof = get_instrument_profile(resolved)
            resolved = str(prof.get("id", resolved))
        except Exception:
            pass

        tasks.append((p, str(req), resolved))

    stems_analysis = list(map(_analyze_stem, tasks)) if tasks else []

    # Mixbus peaks
    mix_peak_dbfs_stream, sr_ref_stream = _mixbus_sample_peak_stream(stem_files)
    mix_tp_dbtp_sum, sr_ref_tp = _mixbus_true_peak_sum_limited(stem_files)

    # Prefer SR del TP si está disponible
    sr_ref = sr_ref_tp if sr_ref_tp is not None else sr_ref_stream

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "samplerate_hz": sr_ref,

            # NUEVO: primario
            "mixbus_true_peak_dbtp_measured": mix_tp_dbtp_sum,
            "mixbus_true_peak_target_min_dbtp": mixbus_true_peak_target_min_dbtp,
            "mixbus_true_peak_target_max_dbtp": mixbus_true_peak_target_max_dbtp,

            # NUEVO: per-stem
            "true_peak_per_stem_target_max_dbtp": true_peak_per_stem_target_max_dbtp,

            # Legacy / diagnóstico
            "mixbus_peak_dbfs_measured": mix_peak_dbfs_stream,
            "mixbus_peak_target_max_dbfs": mixbus_peak_target_max_dbfs,
        },
        "stems": stems_analysis,
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    logger.logger.info(
        f"[S1_STEM_WORKING_LOUDNESS] Analysis OK. mixbus_TP={mix_tp_dbtp_sum:.2f} dBTP "
        f"(target {mixbus_true_peak_target_min_dbtp:.2f}..{mixbus_true_peak_target_max_dbtp:.2f}), "
        f"mixbus_sample_peak={mix_peak_dbfs_stream:.2f} dBFS. JSON: {output_path}"
    )


if __name__ == "__main__":
    main()
