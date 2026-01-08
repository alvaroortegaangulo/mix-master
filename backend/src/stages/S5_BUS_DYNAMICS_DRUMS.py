# C:\mix-master\backend\src\stages\S5_BUS_DYNAMICS_DRUMS.py
from __future__ import annotations

from utils.logger import logger
import sys
import os
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

from utils.analysis_utils import get_temp_dir
from utils.dynamics_utils import (  # noqa: E402
    compress_peak_detector,
    compute_crest_factor_db,
)


def load_analysis(contract_id: str) -> Dict[str, Any]:
    """Carga el JSON de análisis generado por analysis\\S5_BUS_DYNAMICS_DRUMS.py."""
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"
    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")
    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def _compute_bus_threshold(
    pre_rms_db: float,
    pre_peak_db: float,
    crest_db: float,
    crest_max_target: float,
    max_avg_gr_db: float,
    ratio: float,
) -> float | None:
    """
    Calcula un umbral de compresión para el bus de Drums si el crest factor es demasiado alto.

    Política:
      - Si crest_db <= crest_max_target + margen -> None (no compresión).
      - Si crest_db > crest_max_target:
          * Permitimos una GR media objetivo ~ max_avg_gr_db.
          * Usamos una GR máxima teórica algo superior para calcular el umbral.
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

    max_peak_gr_db = max_avg_gr_db + 1.0
    over_max_target = max_peak_gr_db / k
    threshold_from_peak = pre_peak_db - over_max_target

    if pre_rms_db != float("-inf"):
        min_threshold = pre_rms_db + 2.0
        threshold_db = max(threshold_from_peak, min_threshold)
    else:
        threshold_db = threshold_from_peak

    return float(threshold_db)


def _read_mono_limited(path: Path, max_seconds: float = 90.0) -> tuple[np.ndarray | None, int | None, str | None]:
    """Lectura limitada y mono para estimación BPM en stage (evita cargar el tema entero)."""
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
    """Energía + autocorrelación FFT (ligero)."""
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


def _tempo_synced_release_ms_for_drums(bpm: float, style_preset: str) -> float:
    """
    Bus Drums: release más rápido para mantener pegada/punch, pero tempo-synced.
    Subdivisión por BPM:
      - >=150: 1/16 (0.25 beat)
      - 110..149: 1/8 (0.5 beat)
      - <110: dotted 1/8 (0.75 beat)
    Clamps: 40..250 ms
    """
    beat_ms = 60000.0 / max(bpm, 1e-6)
    if bpm >= 150.0:
        beats = 0.25
    elif bpm >= 110.0:
        beats = 0.5
    else:
        beats = 0.75

    sp = (style_preset or "").lower()
    style_mul = 1.0
    if any(k in sp for k in ("ballad", "ambient", "cinematic", "slow")):
        style_mul *= 1.15
    if any(k in sp for k in ("edm", "dnb", "drum", "trap", "rap", "fast")):
        style_mul *= 0.9

    rel = beat_ms * beats * style_mul
    rel = float(min(max(rel, 40.0), 250.0))
    return rel


def _load_drum_stem_worker(args: Tuple[str, str]) -> Tuple[str, str, np.ndarray | None, int | None, str | None]:
    """
    Lee un stem de Drums desde disco y lo devuelve como matriz (N, C) float32.
    args:
      - fname: nombre de archivo
      - path_str: ruta completa al wav

    return: (fname, path_str, data_2d_or_none, sr_or_none, error_msg_or_none)
    """
    fname, path_str = args
    try:
        data, sr = sf.read(path_str, always_2d=False)
        if not isinstance(data, np.ndarray):
            data = np.asarray(data, dtype=np.float32)
        else:
            data = data.astype(np.float32)
        if data.ndim == 1:
            data = data.reshape(-1, 1)  # mono -> (N, 1)
        if data.size == 0:
            return fname, path_str, None, None, "archivo vacío"
        return fname, path_str, data, int(sr), None
    except Exception as e:
        return fname, path_str, None, None, str(e)


def main() -> None:
    """
    Stage S5_BUS_DYNAMICS_DRUMS:
      - Lee analysis_S5_BUS_DYNAMICS_DRUMS.json.
      - Agrupa stems de familia 'Drums' como un bus multicanal.
      - Calcula crest factor pre del bus.
      - Si el crest es mayor que el target, aplica compresión de glue (misma envolvente para todas las pistas del bus).
      - Release tempo-synced al BPM (si BPM fiable), para "groove".
      - Reescribe los stems de Drums procesados.
      - Guarda métricas de bus (pre/post crest, GR media/máx).
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S5_BUS_DYNAMICS_DRUMS.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S5_BUS_DYNAMICS_DRUMS"
    analysis = load_analysis(contract_id)

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}
    session: Dict[str, Any] = analysis.get("session", {}) or {}
    stems: List[Dict[str, Any]] = analysis.get("stems", []) or []

    target_family = str(session.get("target_family", metrics.get("target_family", "Drums")))
    crest_min = float(metrics.get("target_crest_factor_db_min", 6.0))
    crest_max = float(metrics.get("target_crest_factor_db_max", 10.0))
    max_avg_gr = float(limits.get("max_average_gain_reduction_db", 3.0))

    temp_dir = get_temp_dir(contract_id, create=False)

    # Parámetros de compresión típicos de bus de drums
    RATIO = 3.0
    ATTACK_MS = 10.0
    RELEASE_MS_DEFAULT = 150.0
    MAKEUP_DB = 0.0  # sin maquillaje en este stage

    style_preset = str(analysis.get("style_preset", session.get("style_preset", "")) or "")

    bpm, bpm_conf, bpm_source = _get_bpm_from_analysis_or_audio(analysis, temp_dir)

    # Activación tempo-sync solo si parece fiable
    tempo_sync_enabled = (bpm is not None and bpm_conf >= 0.15)
    if tempo_sync_enabled:
        RELEASE_MS = _tempo_synced_release_ms_for_drums(float(bpm), style_preset)
        logger.logger.info(
            f"[S5_BUS_DYNAMICS_DRUMS] Tempo-sync ON: bpm={bpm:.2f} (conf={bpm_conf:.2f}, source={bpm_source}), "
            f"release_ms={RELEASE_MS:.1f}."
        )
    else:
        RELEASE_MS = RELEASE_MS_DEFAULT
        if bpm is not None:
            logger.logger.info(
                f"[S5_BUS_DYNAMICS_DRUMS] Tempo-sync OFF (conf baja): bpm={bpm:.2f} conf={bpm_conf:.2f}; "
                f"release_ms default={RELEASE_MS:.1f}."
            )
        else:
            logger.logger.info(
                f"[S5_BUS_DYNAMICS_DRUMS] Tempo-sync OFF (sin bpm); release_ms default={RELEASE_MS:.1f}."
            )

    # 1) Identificar stems de familia Drums
    drum_stems: List[Dict[str, Any]] = [
        s for s in stems if s.get("is_target_family", False) or s.get("family") == target_family
    ]
    if not drum_stems:
        logger.logger.info(
            f"[S5_BUS_DYNAMICS_DRUMS] No hay stems de familia {target_family}; "
            f"no se aplica compresión de bus."
        )
        return

    load_tasks: List[Tuple[str, str]] = []
    for s in drum_stems:
        fname = s.get("file_name")
        if not fname:
            continue
        path = temp_dir / fname
        if not path.exists():
            continue
        load_tasks.append((fname, str(path)))

    if not load_tasks:
        logger.logger.info(
            f"[S5_BUS_DYNAMICS_DRUMS] No hay archivos válidos para familia {target_family}; "
            f"no se aplica compresión."
        )
        return

    buffers: List[np.ndarray] = []
    files_info: List[Dict[str, Any]] = []
    sr_ref: int | None = None
    max_len = 0
    total_channels = 0

    # 3) Leer stems de Drums en serie
    for fname, path_str, data, sr, err in map(_load_drum_stem_worker, load_tasks):
        if err is not None or data is None or sr is None:
            logger.logger.info(f"[S5_BUS_DYNAMICS_DRUMS] Aviso: no se puede leer '{fname}': {err}.")
            continue

        if sr_ref is None:
            sr_ref = sr
        elif sr != sr_ref:
            logger.logger.info(
                f"[S5_BUS_DYNAMICS_DRUMS] Aviso: samplerate inconsistente en {fname} "
                f"(sr={sr}, ref={sr_ref}); se omite de la compresión de bus."
            )
            continue

        n, c = data.shape
        buffers.append(data)
        files_info.append({"file_name": fname, "path": Path(path_str), "channels": c, "length": n})
        max_len = max(max_len, n)
        total_channels += c

    if not buffers or max_len == 0 or sr_ref is None:
        logger.logger.info(
            f"[S5_BUS_DYNAMICS_DRUMS] No hay buffers válidos para bus {target_family}; "
            f"no se aplica compresión."
        )
        return

    # 4) Construir matriz (N, C_total) del bus
    bus_data = np.zeros((max_len, total_channels), dtype=np.float32)
    ch_start = 0
    for buf, info in zip(buffers, files_info):
        n, c = buf.shape
        bus_data[:n, ch_start : ch_start + c] = buf
        info["ch_start"] = ch_start
        info["ch_end"] = ch_start + c
        ch_start += c

    # 5) Crest factor pre del bus (mezclado a mono)
    bus_mono_pre = np.mean(bus_data, axis=1)
    pre_rms_db, pre_peak_db, pre_crest_db = compute_crest_factor_db(bus_mono_pre)
    logger.logger.info(
        f"[S5_BUS_DYNAMICS_DRUMS] Bus {target_family} PRE: "
        f"RMS={pre_rms_db:.2f} dBFS, peak={pre_peak_db:.2f} dBFS, "
        f"crest={pre_crest_db:.2f} dB."
    )

    # 6) Decidir si necesitamos compresión
    threshold_db = _compute_bus_threshold(
        pre_rms_db=pre_rms_db,
        pre_peak_db=pre_peak_db,
        crest_db=pre_crest_db,
        crest_max_target=crest_max,
        max_avg_gr_db=max_avg_gr,
        ratio=RATIO,
    )

    if threshold_db is None:
        logger.logger.info(
            f"[S5_BUS_DYNAMICS_DRUMS] Crest={pre_crest_db:.2f} dB ya dentro de rango "
            f"o cercano a target; no se aplica compresión de bus."
        )
        post_rms_db, post_peak_db, post_crest_db = pre_rms_db, pre_peak_db, pre_crest_db
        avg_gr_db = 0.0
        max_gr_db = 0.0
        y_out = bus_data
    else:
        # 7) Aplicar compresión al bus multicanal
        y_out, avg_gr_db, max_gr_db = compress_peak_detector(
            bus_data,
            sr_ref,
            threshold_db=threshold_db,
            ratio=RATIO,
            attack_ms=ATTACK_MS,
            release_ms=RELEASE_MS,
            makeup_gain_db=MAKEUP_DB,
        )

        # 8) Recalcular crest factor post
        bus_mono_post = np.mean(y_out, axis=1)
        post_rms_db, post_peak_db, post_crest_db = compute_crest_factor_db(bus_mono_post)
        logger.logger.info(
            f"[S5_BUS_DYNAMICS_DRUMS] Bus {target_family} POST: "
            f"RMS={post_rms_db:.2f} dBFS, peak={post_peak_db:.2f} dBFS, "
            f"crest={post_crest_db:.2f} dB, "
            f"avg_GR={avg_gr_db:.2f} dB, max_GR={max_gr_db:.2f} dB."
        )

    # 9) Volcar cada stem comprimido de vuelta a su archivo (secuencial)
    if y_out is not None:
        for info in files_info:
            fname = info["file_name"]
            path = info["path"]
            ch_start = info["ch_start"]
            ch_end = info["ch_end"]
            length = info["length"]
            c = info["channels"]

            stem_data_out = y_out[:length, ch_start:ch_end]
            if c == 1:
                stem_data_out = stem_data_out.reshape(-1)

            sf.write(path, stem_data_out, sr_ref)
            logger.logger.info(f"[S5_BUS_DYNAMICS_DRUMS] {fname}: reescrito con compresión de bus aplicada.")

    # 10) Guardar métricas de bus para el futuro check
    metrics_path = temp_dir / "bus_dynamics_metrics_S5_BUS_DYNAMICS_DRUMS.json"
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "contract_id": contract_id,
                "target_family": target_family,
                "target_crest_factor_min_db": crest_min,
                "target_crest_factor_max_db": crest_max,
                "max_average_gain_reduction_db": max_avg_gr,
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
                "release_ms_default": RELEASE_MS_DEFAULT,
                "tempo_sync_enabled": tempo_sync_enabled,
                "bpm": bpm,
                "bpm_confidence": bpm_conf,
                "bpm_source": bpm_source,
                "makeup_gain_db": MAKEUP_DB,
                "num_drum_stems": len(drum_stems),
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    logger.logger.info(
        f"[S5_BUS_DYNAMICS_DRUMS] Stage completado para familia {target_family}. "
        f"Métricas guardadas en: {metrics_path}"
    )


if __name__ == "__main__":
    main()
