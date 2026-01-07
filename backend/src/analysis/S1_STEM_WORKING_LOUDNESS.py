# C:\mix-master\backend\src\analysis\S1_STEM_WORKING_LOUDNESS
from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple
import os

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
# Helpers: picos y mixbus sin normalización
# ------------------------------------------------------------

def _dbfs_from_peak(peak_lin: float) -> float:
    if peak_lin <= 0.0:
        return float("-inf")
    return float(20.0 * np.log10(float(peak_lin)))


def _mixbus_peak_stream(
    stem_paths: List[Path],
    block_size: int = 65536,
) -> Tuple[float, int | None]:
    """
    Peak sample-peak real del sumatorio (sin normalizar).
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

        # Validación ligera
        for f in files[1:]:
            if int(f.samplerate) != sr_ref:
                logger.logger.info(
                    f"[S1_STEM_WORKING_LOUDNESS] WARN: samplerate distinto en {getattr(f, 'name', '')}."
                )

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
                        # si es raro, hacemos mono
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


def _analyze_stem(args: Tuple[Path, str, str]) -> Dict[str, Any]:
    """
    Analiza un stem:
      - LUFS integrados (BS.1770 + gating EBU R128 si está disponible)
      - true peak (dBTP, oversampling >=4x)
      - sample peak (dBFS)
      - crest_db = true_peak - lufs (para detectar transitorios)
    """
    stem_path, requested_profile, resolved_profile = args
    fname = stem_path.name

    try:
        y, sr = sf_read_limited(stem_path, always_2d=False)
    except Exception as e:
        return {
            "file_name": fname,
            "file_path": str(stem_path),
            "instrument_profile_requested": requested_profile,
            "instrument_profile_resolved": resolved_profile,
            "samplerate_hz": None,
            "integrated_lufs": float("-inf"),
            "true_peak_dbtp": float("-inf"),
            "sample_peak_dbfs": float("-inf"),
            "crest_db": float("inf"),
            "error": str(e),
        }

    arr = np.asarray(y, dtype=np.float32)
    mono = np.mean(arr, axis=1).astype(np.float32) if arr.ndim > 1 else arr

    if measure_integrated_lufs is not None:
        lufs = float(measure_integrated_lufs(arr, int(sr)))
    else:
        # fallback: RMS->dB (no LUFS real). Mejor que nada.
        eps = 1e-12
        rms = float(np.sqrt(np.mean(mono**2)) + eps)
        lufs = float(20.0 * np.log10(rms) - 23.0)  # aproximación grosera

    if measure_true_peak_dbtp is not None:
        tp = float(measure_true_peak_dbtp(arr, int(sr)))
    else:
        tp = _dbfs_from_peak(float(np.max(np.abs(arr))) if arr.size else 0.0)

    if measure_sample_peak_dbfs is not None:
        sample_peak_dbfs = float(measure_sample_peak_dbfs(arr))
    else:
        sample_peak_dbfs = _dbfs_from_peak(float(np.max(np.abs(arr))) if arr.size else 0.0)

    crest = float(tp - lufs) if (lufs != float("-inf") and tp != float("-inf")) else float("inf")

    return {
        "file_name": fname,
        "file_path": str(stem_path),
        "instrument_profile_requested": requested_profile,
        "instrument_profile_resolved": resolved_profile,
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
      - analiza LUFS/peak por stem
      - mide peak real del mixbus por suma (sin normalizar)
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S1_STEM_WORKING_LOUDNESS.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]

    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    # Targets importantes
    mixbus_peak_target_max_dbfs = float(metrics.get("mixbus_peak_target_max_dbfs", -6.0))
    true_peak_per_stem_target_max_dbfs = float(metrics.get("true_peak_per_stem_target_max_dbfs", -6.0))

    # temp y cfg
    temp_dir = get_temp_dir(contract_id, create=True)
    cfg = load_session_config(contract_id)
    style_preset = cfg["style_preset"]
    instrument_by_file = cfg["instrument_by_file"]

    stem_files: List[Path] = sorted(
        p for p in temp_dir.glob("*.wav") if p.name.lower() != "full_song.wav"
    )

    # Resolver perfiles (auto->por nombre en cfg; luego get_instrument_profile)
    tasks: List[Tuple[Path, str, str]] = []
    for p in stem_files:
        req = instrument_by_file.get(p.name, "Other")
        resolved = req
        try:
            if isinstance(req, str) and req.lower().strip() == "auto":
                resolved = "Other"
            else:
                resolved = str(req)
        except Exception:
            resolved = "Other"

        # Si existe una resolución formal en tus perfiles, úsala (sin forzar cambios)
        try:
            prof = get_instrument_profile(resolved)
            resolved = str(prof.get("id", resolved))
        except Exception:
            pass

        tasks.append((p, str(req), resolved))

    stems_analysis = list(map(_analyze_stem, tasks)) if tasks else []

    # Peak mixbus por suma real (sin normalización)
    mix_peak_dbfs, sr_ref = _mixbus_peak_stream(stem_files)

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "samplerate_hz": sr_ref,
            "mixbus_peak_dbfs_measured": mix_peak_dbfs,
            "mixbus_peak_target_max_dbfs": mixbus_peak_target_max_dbfs,
            "true_peak_per_stem_target_max_dbfs": true_peak_per_stem_target_max_dbfs,
        },
        "stems": stems_analysis,
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    logger.logger.info(
        f"[S1_STEM_WORKING_LOUDNESS] Analysis OK. mixbus_peak={mix_peak_dbfs:.2f} dBFS "
        f"(target<={mixbus_peak_target_max_dbfs:.2f}). JSON: {output_path}"
    )


if __name__ == "__main__":
    main()
