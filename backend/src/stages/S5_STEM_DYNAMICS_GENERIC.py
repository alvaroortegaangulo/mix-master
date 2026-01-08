# C:\mix-master\backend\src\stages\S5_STEM_DYNAMICS_GENERIC.py
from __future__ import annotations

from utils.logger import logger
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from utils.analysis_utils import get_temp_dir  # noqa: E402
from utils.dynamics_utils import compute_crest_factor_db  # noqa: E402
from pedalboard import Pedalboard, Compressor  # noqa: E402
from pedalboard.io import AudioFile  # noqa: E402


def load_analysis(contract_id: str) -> Dict[str, Any]:
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"
    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")
    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def _compute_threshold_for_stem(
    pre_rms_db: float,
    pre_peak_db: float,
    max_peak_gr_db: float,
    ratio: float,
) -> float:
    inv_ratio = 1.0 / float(max(ratio, 1.0))
    k = 1.0 - inv_ratio
    if k <= 0.0:
        return pre_peak_db

    over_max_target = max_peak_gr_db / k
    threshold_from_peak = pre_peak_db - over_max_target

    if pre_rms_db != float("-inf"):
        min_threshold = pre_rms_db + 2.0
        threshold_db = max(threshold_from_peak, min_threshold)
    else:
        threshold_db = threshold_from_peak

    return float(threshold_db)


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


def _get_bpm_from_analysis_or_audio(analysis: Dict[str, Any], temp_dir: Path) -> tuple[float | None, float, str]:
    session = analysis.get("session", {}) or {}
    bpm = session.get("bpm")
    conf = session.get("bpm_confidence", 0.0)
    source = session.get("bpm_source", "none")

    try:
        if bpm is not None:
            bpmf = float(bpm)
            if 40.0 <= bpmf <= 260.0:
                return bpmf, float(conf), str(source)
    except (TypeError, ValueError):
        pass

    full_song = temp_dir / "full_song.wav"
    if full_song.exists():
        y, sr, err = _read_mono_limited(full_song, max_seconds=90.0)
        if err is None and y is not None and sr is not None:
            bpm2, conf2 = _estimate_bpm_from_audio(y, sr)
            if bpm2 is not None:
                return bpm2, conf2, "estimated_full_song_stage"

    return None, 0.0, "none"


def _tempo_synced_release_ms_generic(bpm: float, style_preset: str, min_ms: float, max_ms: float) -> float:
    """
    Genérico: un release musical que no rompa el rango de tu contrato.
    Subdivisión por BPM:
      - >=150: 1/16 (0.25 beat)
      - 100..149: 1/8 (0.5 beat)
      - <100: 1/4 (1.0 beat)
    Luego clamp a [min_ms, max_ms] (desde limits).
    """
    beat_ms = 60000.0 / max(bpm, 1e-6)
    if bpm >= 150.0:
        beats = 0.25
    elif bpm >= 100.0:
        beats = 0.5
    else:
        beats = 1.0

    sp = (style_preset or "").lower()
    style_mul = 1.0
    if any(k in sp for k in ("ballad", "ambient", "cinematic", "slow")):
        style_mul *= 1.10
    if any(k in sp for k in ("edm", "rap", "trap", "fast", "dnb")):
        style_mul *= 0.92

    rel = beat_ms * beats * style_mul
    rel = float(min(max(rel, min_ms), max_ms))
    return rel


def _compress_stem_worker(
    args: Tuple[
        str,  # fname
        str,  # path_str
        float,  # threshold_db
        float,  # pre_rms_db
        float,  # pre_peak_db
        float,  # pre_crest_db
        float,  # RATIO
        float,  # ATTACK_MS
        float,  # RELEASE_MS
        float,  # MAKEUP_DB (no se usa en Pedalboard)
    ]
) -> Optional[Dict[str, Any]]:
    (
        fname,
        path_str,
        threshold_db,
        pre_rms_db,
        pre_peak_db,
        pre_crest_db,
        RATIO,
        ATTACK_MS,
        RELEASE_MS,
        MAKEUP_DB,  # no lo usamos
    ) = args

    path = Path(path_str)
    try:
        with AudioFile(str(path)) as f:
            audio = f.read(f.frames)
            samplerate = f.samplerate
    except Exception as e:
        logger.logger.info(f"[S5_STEM_DYNAMICS_GENERIC] {fname}: error al leer el archivo: {e}")
        return None

    if not isinstance(audio, np.ndarray):
        audio = np.array(audio, dtype=np.float32)
    else:
        audio = audio.astype(np.float32)

    if audio.size == 0:
        logger.logger.info(f"[S5_STEM_DYNAMICS_GENERIC] {fname}: archivo vacío; se omite.")
        return None

    # Normalizar forma para el compresor
    if audio.ndim == 1:
        audio_for_board = audio.reshape(1, -1)  # (1, samples)
        data_in = audio.copy()  # (samples,)
    elif audio.ndim == 2:
        audio_for_board = audio  # (channels, samples)
        data_in = audio.T.copy()  # (samples, channels)
    else:
        logger.logger.info(
            f"[S5_STEM_DYNAMICS_GENERIC] {fname}: formato de audio no soportado con ndim={audio.ndim}; se omite."
        )
        return None

    board = Pedalboard(
        [
            Compressor(
                threshold_db=float(threshold_db),
                ratio=float(RATIO),
                attack_ms=float(ATTACK_MS),
                release_ms=float(RELEASE_MS),
            )
        ]
    )

    try:
        processed = board(audio_for_board, samplerate)
    except Exception as e:
        logger.logger.info(f"[S5_STEM_DYNAMICS_GENERIC] {fname}: error en compresor: {e}")
        return None

    if not isinstance(processed, np.ndarray):
        processed = np.array(processed, dtype=np.float32)
    else:
        processed = processed.astype(np.float32)

    if processed.ndim == 1:
        data_out = processed.copy()
    elif processed.ndim == 2:
        data_out = processed.T.copy()
    else:
        logger.logger.info(
            f"[S5_STEM_DYNAMICS_GENERIC] {fname}: salida del compresor no soportada con ndim={processed.ndim}; se omite."
        )
        return None

    # Ganancia de reducción media y máxima
    eps = 1e-12
    if audio_for_board.ndim == 1:
        in_cs = audio_for_board.reshape(1, -1)
    else:
        in_cs = audio_for_board
    if processed.ndim == 1:
        out_cs = processed.reshape(1, -1)
    else:
        out_cs = processed

    in_abs = np.abs(in_cs).astype(np.float32) + eps
    out_abs = np.abs(out_cs).astype(np.float32) + eps
    gr_db = 20.0 * np.log10(out_abs / in_abs)
    gr_db_clipped = np.minimum(gr_db, 0.0)
    avg_gr_db = float(-np.mean(gr_db_clipped))
    max_gr_db = float(-np.min(gr_db_clipped))

    post_rms_db, post_peak_db, post_crest_db = compute_crest_factor_db(data_out)

    with AudioFile(
        str(path),
        "w",
        samplerate=samplerate,
        num_channels=out_cs.shape[0],
    ) as f:
        f.write(processed)

    return {
        "file_name": fname,
        "pre_rms_dbfs": pre_rms_db,
        "pre_peak_dbfs": pre_peak_db,
        "pre_crest_db": pre_crest_db,
        "post_rms_dbfs": post_rms_db,
        "post_peak_dbfs": post_peak_db,
        "post_crest_db": post_crest_db,
        "avg_gain_reduction_db": avg_gr_db,
        "max_gain_reduction_db": max_gr_db,
        "threshold_db": threshold_db,
        "ratio": RATIO,
        "attack_ms": ATTACK_MS,
        "release_ms": RELEASE_MS,
    }


def main() -> None:
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S5_STEM_DYNAMICS_GENERIC.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]
    analysis = load_analysis(contract_id)

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}
    stems: List[Dict[str, Any]] = analysis.get("stems", []) or []
    session: Dict[str, Any] = analysis.get("session", {}) or {}

    max_avg_gr = float(metrics.get("max_average_gain_reduction_db", 4.0))
    max_peak_gr = float(metrics.get("max_peak_gain_reduction_db", 6.0))

    max_attack_ms = float(limits.get("max_attack_ms", 50.0))
    min_attack_ms = float(limits.get("min_attack_ms", 1.0))
    max_release_ms = float(limits.get("max_release_ms", 600.0))
    min_release_ms = float(limits.get("min_release_ms", 20.0))

    RATIO = 4.0
    ATTACK_MS_DEFAULT = 10.0
    RELEASE_MS_DEFAULT = 120.0
    MAKEUP_DB = 0.0  # compat

    ATTACK_MS = float(min(max(ATTACK_MS_DEFAULT, min_attack_ms), max_attack_ms))
    RELEASE_MS = float(min(max(RELEASE_MS_DEFAULT, min_release_ms), max_release_ms))

    temp_dir = get_temp_dir(contract_id, create=False)

    style_preset = str(analysis.get("style_preset", session.get("style_preset", "")) or "")
    bpm, bpm_conf, bpm_source = _get_bpm_from_analysis_or_audio(analysis, temp_dir)
    tempo_sync_enabled = (bpm is not None and bpm_conf >= 0.15)

    if tempo_sync_enabled:
        RELEASE_MS = _tempo_synced_release_ms_generic(
            float(bpm),
            style_preset,
            min_ms=float(min_release_ms),
            max_ms=float(max_release_ms),
        )
        logger.logger.info(
            f"[S5_STEM_DYNAMICS_GENERIC] Tempo-sync ON: bpm={bpm:.2f} (conf={bpm_conf:.2f}, source={bpm_source}), "
            f"release_ms={RELEASE_MS:.1f} (clamp {min_release_ms:.0f}..{max_release_ms:.0f})."
        )
    else:
        logger.logger.info(
            f"[S5_STEM_DYNAMICS_GENERIC] Tempo-sync OFF; release_ms={RELEASE_MS:.1f} (default/clamp)."
        )

    tasks: List[Tuple[str, str, float, float, float, float, float, float, float, float]] = []

    for stem in stems:
        fname = stem.get("file_name")
        if not fname:
            continue
        path = temp_dir / fname
        if not path.exists():
            continue

        pre_rms_db = stem.get("pre_rms_dbfs")
        pre_peak_db = stem.get("pre_peak_dbfs")
        pre_crest_db = stem.get("pre_crest_factor_db")

        try:
            pre_rms_db = float(pre_rms_db)
            pre_peak_db = float(pre_peak_db)
            pre_crest_db = float(pre_crest_db)
        except (TypeError, ValueError):
            logger.logger.info(
                f"[S5_STEM_DYNAMICS_GENERIC] {fname}: métricas previas inválidas; se omite compresión."
            )
            continue

        if pre_peak_db <= -60.0:
            continue

        threshold_db = _compute_threshold_for_stem(
            pre_rms_db=pre_rms_db,
            pre_peak_db=pre_peak_db,
            max_peak_gr_db=max_peak_gr,
            ratio=RATIO,
        )

        tasks.append(
            (
                fname,
                str(path),
                float(threshold_db),
                float(pre_rms_db),
                float(pre_peak_db),
                float(pre_crest_db),
                RATIO,
                ATTACK_MS,
                RELEASE_MS,
                MAKEUP_DB,
            )
        )

    stems_processed = 0
    metrics_records: List[Dict[str, Any]] = []

    if tasks:
        for result in map(_compress_stem_worker, tasks):
            if result is None:
                continue
            fname = result["file_name"]
            threshold_db = result["threshold_db"]
            avg_gr_db = result["avg_gain_reduction_db"]
            max_gr_db = result["max_gain_reduction_db"]
            pre_crest_db = result["pre_crest_db"]
            post_crest_db = result["post_crest_db"]

            logger.logger.info(
                f"[S5_STEM_DYNAMICS_GENERIC] {fname}: threshold={threshold_db:.2f} dBFS, "
                f"avg_GR={avg_gr_db:.2f} dB, max_GR={max_gr_db:.2f} dB, "
                f"crest_pre={pre_crest_db:.2f} dB, crest_post={post_crest_db:.2f} dB."
            )

            rec = dict(result)
            rec["tempo_sync_enabled"] = tempo_sync_enabled
            rec["bpm"] = bpm
            rec["bpm_confidence"] = bpm_conf
            rec["bpm_source"] = bpm_source
            rec["release_ms_default"] = RELEASE_MS_DEFAULT

            metrics_records.append(rec)
            stems_processed += 1
    else:
        logger.logger.info("[S5_STEM_DYNAMICS_GENERIC] No hay stems válidos que requieran compresión.")

    metrics_path = temp_dir / "dynamics_metrics_S5_STEM_DYNAMICS_GENERIC.json"
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "contract_id": contract_id,
                "max_average_gain_reduction_db": max_avg_gr,
                "max_peak_gain_reduction_db": max_peak_gr,
                "tempo_sync_enabled": tempo_sync_enabled,
                "bpm": bpm,
                "bpm_confidence": bpm_conf,
                "bpm_source": bpm_source,
                "records": metrics_records,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    logger.logger.info(
        f"[S5_STEM_DYNAMICS_GENERIC] Stage completado. Stems procesados={stems_processed}. "
        f"Métricas guardadas en: {metrics_path}"
    )


if __name__ == "__main__":
    main()
