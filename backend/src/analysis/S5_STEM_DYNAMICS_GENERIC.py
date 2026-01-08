# C:\mix-master\backend\src\analysis\S5_STEM_DYNAMICS_GENERIC.py
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
from utils.dynamics_utils import compute_crest_factor_db  # noqa: E402


def _analyze_stem(args: Tuple[Path, str]) -> Dict[str, Any]:
    """
    Recibe:
      - stem_path: ruta al .wav
      - inst_prof: instrument_profile
    Devuelve un dict de análisis por stem con la misma estructura que en la versión secuencial,
    añadiendo 'error' para que el proceso principal imprima los avisos.
    """
    stem_path, inst_prof = args
    fname = stem_path.name
    try:
        y, sr = sf_read_limited(stem_path, always_2d=False)
    except Exception as e:
        return {
            "file_name": fname,
            "file_path": str(stem_path),
            "instrument_profile": inst_prof,
            "samplerate_hz": None,
            "pre_rms_dbfs": None,
            "pre_peak_dbfs": None,
            "pre_crest_factor_db": None,
            "error": f"[S5_STEM_DYNAMICS_GENERIC] Aviso: no se puede leer '{fname}': {e}.",
        }

    rms_db, peak_db, crest_db = compute_crest_factor_db(y)
    return {
        "file_name": fname,
        "file_path": str(stem_path),
        "instrument_profile": inst_prof,
        "samplerate_hz": sr,
        "pre_rms_dbfs": rms_db,
        "pre_peak_dbfs": peak_db,
        "pre_crest_factor_db": crest_db,
        "error": None,
    }


def _read_mono_limited(path: Path, max_seconds: float = 90.0) -> tuple[np.ndarray | None, int | None, str | None]:
    try:
        with sf.SoundFile(str(path)) as f:
            sr = int(f.samplerate)
            max_frames = int(max_seconds * sr)
            frames = min(max_frames, len(f))
            y = f.read(frames=frames, dtype="float32", always_2d=False)
        if y is None:
            return None, None, "lectura None"
        if not isinstance(y, np.ndarray):
            y = np.asarray(y, dtype=np.float32)
        if y.size == 0:
            return None, None, "archivo vacío"
        if y.ndim > 1:
            y = np.mean(y, axis=1).astype(np.float32)
        return y.astype(np.float32), sr, None
    except Exception as e:
        return None, None, str(e)


def _estimate_bpm_from_audio(y: np.ndarray, sr: int, bpm_min: float = 60.0, bpm_max: float = 200.0) -> tuple[float | None, float]:
    if y is None or sr is None:
        return None, 0.0
    if y.size < sr * 5:
        return None, 0.0

    y = y.astype(np.float32)
    y = y - float(np.mean(y))

    frame = 2048
    hop = 512
    n = int((len(y) - frame) / hop) + 1
    if n < 256:
        return None, 0.0

    idx = np.arange(frame, dtype=np.int32)[None, :] + (np.arange(n, dtype=np.int32) * hop)[:, None]
    frames = y[idx]
    rms = np.sqrt(np.mean(frames * frames, axis=1) + 1e-12).astype(np.float32)

    env = np.diff(rms, prepend=rms[:1])
    env = np.maximum(env, 0.0)

    k = 5
    if env.size > k:
        env = np.convolve(env, np.ones(k, dtype=np.float32) / k, mode="same")

    env = env - float(np.mean(env))
    std = float(np.std(env) + 1e-12)
    env = (env / std).astype(np.float32)

    fe = sr / float(hop)

    m = int(env.size)
    nfft = 1 << ((2 * m - 1).bit_length())
    F = np.fft.rfft(env, n=nfft)
    ac = np.fft.irfft(F * np.conj(F), n=nfft)[:m].real
    ac[0] = 0.0

    lag_min = int(round((60.0 * fe) / bpm_max))
    lag_max = int(round((60.0 * fe) / bpm_min))
    if lag_max <= lag_min + 2 or lag_max >= ac.size:
        return None, 0.0

    window = ac[lag_min : lag_max + 1]
    peak_i = int(np.argmax(window))
    peak_lag = lag_min + peak_i
    bpm0 = 60.0 * fe / float(peak_lag)

    candidates: List[tuple[float, float]] = []
    for mult in (0.5, 1.0, 2.0):
        bpm_c = bpm0 * mult
        if bpm_c < bpm_min or bpm_c > bpm_max:
            continue
        lag_c = int(round((60.0 * fe) / bpm_c))
        if lag_c <= 1 or lag_c >= ac.size:
            continue
        candidates.append((bpm_c, float(ac[lag_c])))

    if not candidates:
        return None, 0.0

    bpm_best, score_best = max(candidates, key=lambda t: t[1])
    med = float(np.median(window) + 1e-12)
    conf = float(np.clip((score_best / med - 1.0) / 10.0, 0.0, 1.0))
    return float(bpm_best), conf


def _get_bpm(cfg: Dict[str, Any], temp_dir: Path) -> tuple[float | None, float, str]:
    for k in ("bpm", "tempo_bpm", "bpm_estimate", "tempo"):
        v = cfg.get(k)
        try:
            if v is not None:
                bpm = float(v)
                if 40.0 <= bpm <= 260.0:
                    return bpm, 1.0, "session_config"
        except (TypeError, ValueError):
            pass

    full_song = temp_dir / "full_song.wav"
    if full_song.exists():
        y, sr, err = _read_mono_limited(full_song, max_seconds=90.0)
        if err is None and y is not None and sr is not None:
            bpm, conf = _estimate_bpm_from_audio(y, sr)
            if bpm is not None:
                return bpm, conf, "estimated_full_song"

    return None, 0.0, "none"


def main() -> None:
    """
    Análisis para el contrato S5_STEM_DYNAMICS_GENERIC.
    Uso desde stage.py: python analysis/S5_STEM_DYNAMICS_GENERIC.py S5_STEM_DYNAMICS_GENERIC
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S5_STEM_DYNAMICS_GENERIC.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S5_STEM_DYNAMICS_GENERIC"

    # 1) Cargar contrato
    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    max_avg_gr = float(metrics.get("max_average_gain_reduction_db", 4.0))
    max_peak_gr = float(metrics.get("max_peak_gain_reduction_db", 6.0))

    # 2) Directorio temp/<contract_id> y session_config
    temp_dir = get_temp_dir(contract_id, create=True)
    cfg = load_session_config(contract_id)
    style_preset = cfg["style_preset"]
    instrument_by_file = cfg["instrument_by_file"]

    bpm, bpm_conf, bpm_source = _get_bpm(cfg, temp_dir)
    if bpm is not None:
        logger.logger.info(
            f"[S5_STEM_DYNAMICS_GENERIC] BPM detectado={bpm:.2f} (conf={bpm_conf:.2f}, source={bpm_source})."
        )
    else:
        logger.logger.info("[S5_STEM_DYNAMICS_GENERIC] BPM no disponible (tempo-sync downstream puede quedar inactivo).")

    # 3) Listar stems (.wav) de este stage (excluimos full_song.wav)
    stem_files: List[Path] = sorted(
        p for p in temp_dir.glob("*.wav") if p.name.lower() != "full_song.wav"
    )

    # 4) Preparar tareas para análisis (serie)
    tasks: List[Tuple[Path, str]] = []
    for p in stem_files:
        fname = p.name
        inst_prof = instrument_by_file.get(fname, "Other")
        tasks.append((p, inst_prof))

    # 5) Ejecutar análisis en serie
    results: List[Dict[str, Any]] = [_analyze_stem(t) for t in tasks] if tasks else []

    stems_analysis: List[Dict[str, Any]] = []

    # 6) Logging y construcción de lista de stems
    for stem_entry in results:
        stems_analysis.append(stem_entry)
        fname = stem_entry["file_name"]
        err = stem_entry.get("error")
        if err is not None:
            logger.logger.info(err)
            continue

        rms_db = stem_entry["pre_rms_dbfs"]
        peak_db = stem_entry["pre_peak_dbfs"]
        crest_db = stem_entry["pre_crest_factor_db"]
        if rms_db is None or peak_db is None or crest_db is None:
            continue

        logger.logger.info(
            f"[S5_STEM_DYNAMICS_GENERIC] {fname}: "
            f"RMS={rms_db:.2f} dBFS, peak={peak_db:.2f} dBFS, crest={crest_db:.2f} dB."
        )

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "max_average_gain_reduction_db": max_avg_gr,
            "max_peak_gain_reduction_db": max_peak_gr,
            "bpm": bpm,
            "bpm_confidence": bpm_conf,
            "bpm_source": bpm_source,
        },
        "stems": stems_analysis,
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    logger.logger.info(
        f"[S5_STEM_DYNAMICS_GENERIC] Análisis completado para {len(stems_analysis)} stems. "
        f"JSON: {output_path}"
    )


if __name__ == "__main__":
    main()
