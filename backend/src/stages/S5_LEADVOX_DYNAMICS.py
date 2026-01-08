# C:\mix-master\backend\src\stages\S5_LEADVOX_DYNAMICS.py
from __future__ import annotations

from utils.logger import logger
import sys
import os
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

from utils.analysis_utils import get_temp_dir
from utils.dynamics_utils import (  # noqa: E402
    compress_peak_detector,
    compute_crest_factor_db,
)


def load_analysis(contract_id: str) -> Dict[str, Any]:
    """Carga el JSON de análisis generado por analysis\\S5_LEADVOX_DYNAMICS.py."""
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"
    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")
    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def _compute_vocal_threshold(
    pre_rms_db: float,
    pre_peak_db: float,
    crest_db: float,
    crest_max_target: float,
    max_avg_gr_db: float,
    ratio: float,
) -> float | None:
    """
    Calcula un umbral de compresión para lead vocal si el crest factor es demasiado alto.

    Regla:
      - Si crest_db <= crest_max_target + margen -> None (no compresión).
      - Si crest_db > crest_max_target:
          * Se permite como máximo max_avg_gr_db de GR media (aprox.).
          * Fórmula similar a S5_STEM_DYNAMICS_GENERIC para limitar GR.
    """
    MARGIN_DB = 0.5
    if crest_db == float("inf") or crest_db != crest_db:  # NaN
        return None

    if crest_db <= crest_max_target + MARGIN_DB:
        return None

    inv_ratio = 1.0 / float(max(ratio, 1.0))
    k = 1.0 - inv_ratio
    if k <= 0.0:
        return None

    max_peak_gr_db = max_avg_gr_db + 2.0
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


def _tempo_synced_release_ms_for_vocal(bpm: float, style_preset: str) -> float:
    """
    Lead Vocal: release que "respira" con BPM sin irse a valores absurdos.
    Subdivisión por BPM:
      - >=140: 1/8 (0.5 beat)  -> evita distorsión/pumping en rap rápido
      - 90..139: 1/4 (1.0 beat)-> musical por defecto
      - <90: dotted 1/4 (1.5 beat)-> balada, colas más naturales
    Clamps: 60..350 ms
    """
    beat_ms = 60000.0 / max(bpm, 1e-6)

    if bpm >= 140.0:
        beats = 0.5
    elif bpm >= 90.0:
        beats = 1.0
    else:
        beats = 1.5

    sp = (style_preset or "").lower()
    style_mul = 1.0
    if any(k in sp for k in ("ballad", "ambient", "cinematic", "slow")):
        style_mul *= 1.15
    if any(k in sp for k in ("rap", "trap", "edm", "fast")):
        style_mul *= 0.92

    rel = beat_ms * beats * style_mul
    rel = float(min(max(rel, 60.0), 350.0))
    return rel


def _tempo_synced_attack_ms_for_vocal(bpm: float) -> float:
    """
    Ajuste MUY conservador: ataquear ~1% de beat, clamp 3..8 ms.
    Mantiene el carácter del valor fijo (5 ms) pero se adapta ligeramente.
    """
    beat_ms = 60000.0 / max(bpm, 1e-6)
    atk = beat_ms * 0.01
    return float(min(max(atk, 3.0), 8.0))


def _compress_lead_stem_worker(
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
        float,  # MAKEUP_DB
    ]
) -> Optional[Dict[str, Any]]:
    """
    Worker que:
      - Lee el archivo de audio.
      - Aplica compresión peak detector.
      - Reescribe el archivo.
      - Devuelve métricas post-compresión para el registro.
    """
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
        MAKEUP_DB,
    ) = args

    path = Path(path_str)

    try:
        data, sr = sf.read(path, always_2d=False)
    except Exception as e:
        logger.logger.info(f"[S5_LEADVOX_DYNAMICS] {fname}: error al leer el archivo: {e}")
        return None

    if not isinstance(data, np.ndarray):
        data = np.array(data, dtype=np.float32)
    else:
        data = data.astype(np.float32)

    if data.size == 0:
        logger.logger.info(f"[S5_LEADVOX_DYNAMICS] {fname}: archivo vacío; se omite.")
        return None

    y_out, avg_gr_db, max_gr_db = compress_peak_detector(
        data,
        int(sr),
        threshold_db=threshold_db,
        ratio=RATIO,
        attack_ms=ATTACK_MS,
        release_ms=RELEASE_MS,
        makeup_gain_db=MAKEUP_DB,
    )

    post_rms_db, post_peak_db, post_crest_db = compute_crest_factor_db(y_out)

    sf.write(path, y_out, int(sr))

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
        "makeup_gain_db": MAKEUP_DB,
    }


def main() -> None:
    """
    Stage S5_LEADVOX_DYNAMICS:
      - Lee analysis_S5_LEADVOX_DYNAMICS.json.
      - Sólo procesa stems marcados como lead vocal.
      - Si crest > target, compresión moderada recortapicos.
      - Release tempo-synced (si BPM fiable) para “respirar” con la música.
      - Guarda métricas de GR y crest factor antes/después.
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S5_LEADVOX_DYNAMICS.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S5_LEADVOX_DYNAMICS"
    analysis = load_analysis(contract_id)

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}
    session: Dict[str, Any] = analysis.get("session", {}) or {}
    stems: List[Dict[str, Any]] = analysis.get("stems", []) or []

    crest_min = float(metrics.get("target_crest_factor_db_min", 6.0))
    crest_max = float(metrics.get("target_crest_factor_db_max", 12.0))
    max_avg_gr = float(metrics.get("max_average_gain_reduction_db", 6.0))
    max_auto_change = float(limits.get("max_vocal_automation_change_db_per_pass", 3.0))
    lead_profile_id = session.get("lead_profile_id", "Lead_Vocal_Melodic")

    # Parámetros base
    RATIO = 3.0
    ATTACK_MS_DEFAULT = 5.0
    RELEASE_MS_DEFAULT = 100.0
    MAKEUP_DB = 0.0

    temp_dir = get_temp_dir(contract_id, create=False)

    style_preset = str(analysis.get("style_preset", session.get("style_preset", "")) or "")

    bpm, bpm_conf, bpm_source = _get_bpm_from_analysis_or_audio(analysis, temp_dir)
    tempo_sync_enabled = (bpm is not None and bpm_conf >= 0.15)

    if tempo_sync_enabled:
        RELEASE_MS = _tempo_synced_release_ms_for_vocal(float(bpm), style_preset)
        # attack conservador (muy cercano a 5ms)
        ATTACK_MS = _tempo_synced_attack_ms_for_vocal(float(bpm))
        logger.logger.info(
            f"[S5_LEADVOX_DYNAMICS] Tempo-sync ON: bpm={bpm:.2f} (conf={bpm_conf:.2f}, source={bpm_source}), "
            f"attack_ms={ATTACK_MS:.1f}, release_ms={RELEASE_MS:.1f}."
        )
    else:
        RELEASE_MS = RELEASE_MS_DEFAULT
        ATTACK_MS = ATTACK_MS_DEFAULT
        if bpm is not None:
            logger.logger.info(
                f"[S5_LEADVOX_DYNAMICS] Tempo-sync OFF (conf baja): bpm={bpm:.2f} conf={bpm_conf:.2f}; "
                f"attack_ms={ATTACK_MS:.1f}, release_ms default={RELEASE_MS:.1f}."
            )
        else:
            logger.logger.info(
                f"[S5_LEADVOX_DYNAMICS] Tempo-sync OFF (sin bpm); "
                f"attack_ms={ATTACK_MS:.1f}, release_ms default={RELEASE_MS:.1f}."
            )

    # ------------------------------------------------------------------
    # 1) Preparar tareas para stems de lead vocal que realmente necesiten compresión
    # ------------------------------------------------------------------
    tasks: List[Tuple[str, str, float, float, float, float, float, float, float, float]] = []

    for stem in stems:
        fname = stem.get("file_name")
        if not fname:
            continue
        if not stem.get("is_lead_vocal", False):
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
                f"[S5_LEADVOX_DYNAMICS] {fname}: métricas previas inválidas; se omite compresión."
            )
            continue

        if pre_peak_db <= -60.0:
            logger.logger.info(
                f"[S5_LEADVOX_DYNAMICS] {fname}: nivel muy bajo (peak={pre_peak_db:.1f} dBFS); "
                f"no se aplica compresión."
            )
            continue

        if crest_min <= pre_crest_db <= crest_max:
            logger.logger.info(
                f"[S5_LEADVOX_DYNAMICS] {fname}: crest={pre_crest_db:.2f} dB ya en rango "
                f"[{crest_min:.1f}, {crest_max:.1f}] dB; no se aplica compresión."
            )
            continue

        if pre_crest_db < crest_min:
            logger.logger.info(
                f"[S5_LEADVOX_DYNAMICS] {fname}: crest={pre_crest_db:.2f} dB < min "
                f"{crest_min:.1f} dB; no se comprime (no expansión)."
            )
            continue

        threshold_db = _compute_vocal_threshold(
            pre_rms_db=pre_rms_db,
            pre_peak_db=pre_peak_db,
            crest_db=pre_crest_db,
            crest_max_target=crest_max,
            max_avg_gr_db=max_avg_gr,
            ratio=RATIO,
        )
        if threshold_db is None:
            logger.logger.info(
                f"[S5_LEADVOX_DYNAMICS] {fname}: no se determina umbral de compresión; no se aplica compresión."
            )
            continue

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

    # ------------------------------------------------------------------
    # 2) Ejecutar compresión en serie
    # ------------------------------------------------------------------
    metrics_records: List[Dict[str, Any]] = []
    processed = 0

    if tasks:
        for result in map(_compress_lead_stem_worker, tasks):
            if result is None:
                continue

            fname = result["file_name"]
            threshold_db = result["threshold_db"]
            avg_gr_db = result["avg_gain_reduction_db"]
            max_gr_db = result["max_gain_reduction_db"]
            pre_crest_db = result["pre_crest_db"]
            post_crest_db = result["post_crest_db"]

            logger.logger.info(
                f"[S5_LEADVOX_DYNAMICS] {fname}: threshold={threshold_db:.2f} dBFS, "
                f"avg_GR={avg_gr_db:.2f} dB, max_GR={max_gr_db:.2f} dB, "
                f"crest_pre={pre_crest_db:.2f} dB, crest_post={post_crest_db:.2f} dB."
            )

            record = dict(result)
            record["max_vocal_automation_change_db_per_pass"] = max_auto_change
            record["tempo_sync_enabled"] = tempo_sync_enabled
            record["bpm"] = bpm
            record["bpm_confidence"] = bpm_conf
            record["bpm_source"] = bpm_source
            record["attack_ms_default"] = ATTACK_MS_DEFAULT
            record["release_ms_default"] = RELEASE_MS_DEFAULT

            metrics_records.append(record)
            processed += 1
    else:
        logger.logger.info(
            "[S5_LEADVOX_DYNAMICS] No hay stems de lead que requieran compresión (o no hay stems válidos)."
        )

    # ------------------------------------------------------------------
    # 3) Guardar métricas de dinámica para el futuro check
    # ------------------------------------------------------------------
    metrics_path = temp_dir / "leadvox_dynamics_metrics_S5_LEADVOX_DYNAMICS.json"
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "contract_id": contract_id,
                "target_crest_factor_min_db": crest_min,
                "target_crest_factor_max_db": crest_max,
                "max_average_gain_reduction_db": max_avg_gr,
                "max_vocal_automation_change_db_per_pass": max_auto_change,
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
        f"[S5_LEADVOX_DYNAMICS] Stage completado. Stems lead procesados={processed}. "
        f"Métricas guardadas en: {metrics_path}"
    )


if __name__ == "__main__":
    main()
