# C:\mix-master\backend\src\stages\S5_LEADVOX_DYNAMICS.py
from __future__ import annotations

from utils.logger import logger
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import json
import numpy as np
import soundfile as sf

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.analysis_utils import get_temp_dir  # noqa: E402
from utils.dynamics_utils import (  # noqa: E402
    compress_peak_detector,
    compute_crest_factor_db,
)

EPS = 1e-12


def load_analysis(contract_id: str) -> Dict[str, Any]:
    """Carga el JSON de análisis generado por analysis\\S5_LEADVOX_DYNAMICS.py."""
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"
    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")
    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def _db_to_lin(db: float) -> float:
    return float(10.0 ** (float(db) / 20.0))


def _lin_to_db(x: float) -> float:
    return float(20.0 * np.log10(max(float(x), EPS)))


def _to_mono(y: np.ndarray) -> np.ndarray:
    if y.ndim == 1:
        return y.astype(np.float32)
    return np.mean(y, axis=1).astype(np.float32)


def _read_mono_limited(path: Path, max_seconds: float = 90.0) -> tuple[np.ndarray | None, int | None, str | None]:
    try:
        with sf.SoundFile(str(path)) as f:
            sr = int(f.samplerate)
            max_frames = int(max_seconds * sr)
            frames = min(max_frames, len(f))
            y = f.read(frames=frames, dtype="float32", always_2d=True)
        if y is None:
            return None, None, "lectura None"
        if not isinstance(y, np.ndarray):
            y = np.asarray(y, dtype=np.float32)
        if y.size == 0:
            return None, None, "archivo vacío"
        y_m = _to_mono(y)
        return y_m.astype(np.float32), sr, None
    except Exception as e:
        return None, None, str(e)


def _estimate_bpm_from_audio(
    y: np.ndarray, sr: int, bpm_min: float = 60.0, bpm_max: float = 200.0
) -> tuple[float | None, float]:
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
    Release musical (fast comp) sincronizado.
    Clamps: 60..320 ms
    """
    beat_ms = 60000.0 / max(bpm, 1e-6)

    if bpm >= 140.0:
        beats = 0.45
    elif bpm >= 90.0:
        beats = 0.75
    else:
        beats = 1.10

    sp = (style_preset or "").lower()
    style_mul = 1.0
    if any(k in sp for k in ("ballad", "ambient", "cinematic", "slow")):
        style_mul *= 1.12
    if any(k in sp for k in ("rap", "trap", "edm", "fast")):
        style_mul *= 0.92

    rel = beat_ms * beats * style_mul
    rel = float(min(max(rel, 60.0), 320.0))
    return rel


def _tempo_synced_attack_ms_for_vocal(bpm: float) -> float:
    """
    Ataque conservador (fast comp): ~0.8% de beat, clamp 2.5..7 ms.
    """
    beat_ms = 60000.0 / max(bpm, 1e-6)
    atk = beat_ms * 0.008
    return float(min(max(atk, 2.5), 7.0))


# -----------------------------
# De-esser (FFT, overlap-add)
# -----------------------------
def _apply_deesser_fft(
    y: np.ndarray,
    sr: int,
    ratio_thr_db: float = -3.0,
    max_deess_db: float = 6.0,
    slope: float = 0.8,
    band_lo_hz: float = 5000.0,
    band_hi_hz: float = 10000.0,
    mid_lo_hz: float = 1000.0,
    mid_hi_hz: float = 5000.0,
    frame: int = 2048,
    hop: int = 512,
) -> tuple[np.ndarray, Dict[str, float]]:
    """
    De-esser condicional: atenúa bins 5-10k cuando (E_hi/E_mid) supera un umbral.
    Procesa por canal, overlap-add.
    Devuelve (y_out, stats).
    """
    if y.size == 0 or sr <= 0:
        return y, {"enabled": 0.0, "avg_deess_db": 0.0, "max_deess_db": 0.0}

    if y.ndim == 1:
        y2d = y[:, None]
    else:
        y2d = y

    n, ch = y2d.shape
    if n < frame + hop:
        return y, {"enabled": 0.0, "avg_deess_db": 0.0, "max_deess_db": 0.0}

    win = np.hanning(frame).astype(np.float32)
    win_norm = float(np.sum(win**2) / max(hop, 1))

    freqs = np.fft.rfftfreq(frame, d=1.0 / float(sr)).astype(np.float32)
    hi_mask = (freqs >= band_lo_hz) & (freqs < band_hi_hz)
    mid_mask = (freqs >= mid_lo_hz) & (freqs < mid_hi_hz)

    y_out = np.zeros_like(y2d, dtype=np.float32)
    ola_norm = np.zeros((n,), dtype=np.float32)

    deess_vals: List[float] = []

    # Procesamiento por chunks de frames para memoria controlada
    n_frames = 1 + (n - frame) // hop
    for k in range(n_frames):
        i0 = k * hop
        seg = y2d[i0 : i0 + frame, :]  # (frame, ch)
        segw = seg * win[:, None]

        # rfft por canal
        X = np.fft.rfft(segw, axis=0)  # (bins, ch)
        mag2 = (np.abs(X) ** 2).astype(np.float64)

        e_hi = np.sum(mag2[hi_mask, :], axis=0) + EPS
        e_mid = np.sum(mag2[mid_mask, :], axis=0) + EPS
        ratio_db = 10.0 * np.log10(e_hi / e_mid)  # (ch,)

        # GR por canal
        over = ratio_db - float(ratio_thr_db)
        gr_db = np.clip(over * float(slope), 0.0, float(max_deess_db)).astype(np.float32)

        # Atenuación en hi band
        att = (10.0 ** (-gr_db / 20.0)).astype(np.float32)  # (ch,)
        if np.any(gr_db > 0.0):
            deess_vals.extend([float(v) for v in gr_db])

        # aplica por bins: sólo banda hi
        X2 = X.copy()
        if np.any(hi_mask):
            X2[hi_mask, :] *= att[None, :]

        x_time = np.fft.irfft(X2, n=frame, axis=0).astype(np.float32)

        y_out[i0 : i0 + frame, :] += x_time * win[:, None]
        ola_norm[i0 : i0 + frame] += (win.astype(np.float32) ** 2)

    # Normalización OLA
    norm = np.maximum(ola_norm, EPS)[:, None]
    y_out = (y_out / norm).astype(np.float32)

    if y.ndim == 1:
        y_out_final = y_out[:, 0]
    else:
        y_out_final = y_out

    if deess_vals:
        arr = np.array(deess_vals, dtype=np.float32)
        stats = {
            "enabled": 1.0,
            "avg_deess_db": float(np.mean(arr)),
            "max_deess_db": float(np.max(arr)),
            "ratio_thr_db": float(ratio_thr_db),
            "max_deess_limit_db": float(max_deess_db),
            "slope": float(slope),
        }
    else:
        stats = {
            "enabled": 0.0,
            "avg_deess_db": 0.0,
            "max_deess_db": 0.0,
            "ratio_thr_db": float(ratio_thr_db),
            "max_deess_limit_db": float(max_deess_db),
            "slope": float(slope),
        }

    return y_out_final.astype(np.float32), stats


# -----------------------------
# Nivelador lento (RMS detector)
# -----------------------------
def _compress_leveler_rms(
    y: np.ndarray,
    sr: int,
    threshold_db: float,
    ratio: float,
    attack_ms: float,
    release_ms: float,
    gate_dbfs: float = -55.0,
    makeup_db: float = 0.0,
) -> tuple[np.ndarray, float, float]:
    """
    Compresor 'leveler' simple:
      - detector RMS por frames (10ms)
      - suavizado de GR con ataque/release
      - ganancia por frame repetida a muestras
    Devuelve (y_out, avg_gr_db, max_gr_db) medidos en frames.
    """
    if y.size == 0 or sr <= 0:
        return y, 0.0, 0.0

    if y.ndim == 1:
        y2d = y[:, None]
    else:
        y2d = y

    n = y2d.shape[0]
    det_hop = max(int(round(0.01 * sr)), 1)  # 10ms
    det_win = det_hop

    if n < det_win:
        return y, 0.0, 0.0

    # detector sobre mono
    mono = _to_mono(y2d)
    mono2 = (mono * mono).astype(np.float64)
    c = np.concatenate([np.zeros((1,), dtype=np.float64), np.cumsum(mono2, dtype=np.float64)])

    starts = np.arange(0, n - det_win + 1, det_hop, dtype=np.int64)
    sums = c[starts + det_win] - c[starts]
    rms = np.sqrt(sums / float(det_win) + EPS).astype(np.float32)
    level_db = (20.0 * np.log10(np.maximum(rms, EPS))).astype(np.float32)

    # GR target por frame
    inv_ratio = 1.0 / max(float(ratio), 1.0)
    k = 1.0 - inv_ratio
    over_db = (level_db - float(threshold_db)).astype(np.float32)
    gr_t = np.maximum(over_db * float(k), 0.0).astype(np.float32)

    # gate: si muy bajo, no comprimir
    gr_t = np.where(level_db > float(gate_dbfs), gr_t, 0.0).astype(np.float32)

    # suavizado ataque/release sobre frames
    dt = float(det_hop) / float(sr)
    a_att = float(np.exp(-dt / max(float(attack_ms) / 1000.0, 1e-6)))
    a_rel = float(np.exp(-dt / max(float(release_ms) / 1000.0, 1e-6)))

    gr_s = np.zeros_like(gr_t, dtype=np.float32)
    g = 0.0
    for i in range(gr_t.size):
        tgt = float(gr_t[i])
        if tgt > g:
            g = a_att * g + (1.0 - a_att) * tgt
        else:
            g = a_rel * g + (1.0 - a_rel) * tgt
        gr_s[i] = g

    # ganancia lineal por frame -> por muestra
    gain = (10.0 ** (-gr_s / 20.0)).astype(np.float32)
    gain_samples = np.repeat(gain, det_hop).astype(np.float32)
    if gain_samples.size < n:
        gain_samples = np.pad(gain_samples, (0, n - gain_samples.size), mode="edge")
    gain_samples = gain_samples[:n]

    y_out = (y2d * gain_samples[:, None]).astype(np.float32)

    if makeup_db != 0.0:
        y_out *= _db_to_lin(makeup_db)

    avg_gr = float(np.mean(gr_s)) if gr_s.size else 0.0
    max_gr = float(np.max(gr_s)) if gr_s.size else 0.0

    if y.ndim == 1:
        return y_out[:, 0], avg_gr, max_gr
    return y_out, avg_gr, max_gr


def _compute_fast_comp_threshold_from_peak_limit(
    pre_peak_db: float,
    ratio: float,
    max_peak_gr_db: float,
) -> float:
    """
    Umbral teórico para limitar GR de picos:
      over = pre_peak - threshold
      GR = over * (1 - 1/ratio) <= max_peak_gr
      => threshold >= pre_peak - max_peak_gr / (1 - 1/ratio)
    """
    r = max(float(ratio), 1.0)
    k = 1.0 - 1.0 / r
    if k <= 0.0:
        return float(pre_peak_db)
    over_allow = float(max_peak_gr_db) / k
    return float(pre_peak_db - over_allow)


def _compress_lead_stem_worker(
    args: Tuple[
        str,  # fname
        str,  # path_str
        float,  # pre_gain_db
        bool,  # deesser_enable
        float,  # deess_thr_db
        float,  # deess_max_db
        float,  # deess_slope
        # leveler params
        float,  # leveler_threshold_db
        float,  # leveler_ratio
        float,  # leveler_attack_ms
        float,  # leveler_release_ms
        float,  # leveler_max_avg_gr_db (soft constraint via threshold adaption)
        float,  # leveler_max_max_gr_db
        # fast comp params
        bool,   # fast_enable
        float,  # fast_ratio
        float,  # fast_attack_ms
        float,  # fast_release_ms
        float,  # fast_max_peak_gr_db
    ]
) -> Optional[Dict[str, Any]]:
    (
        fname,
        path_str,
        pre_gain_db,
        deesser_enable,
        deess_thr_db,
        deess_max_db,
        deess_slope,
        leveler_threshold_db,
        leveler_ratio,
        leveler_attack_ms,
        leveler_release_ms,
        leveler_max_avg_gr_db,
        leveler_max_max_gr_db,
        fast_enable,
        fast_ratio,
        fast_attack_ms,
        fast_release_ms,
        fast_max_peak_gr_db,
    ) = args

    path = Path(path_str)

    try:
        data, sr = sf.read(path, always_2d=True)
    except Exception as e:
        logger.logger.info(f"[S5_LEADVOX_DYNAMICS] {fname}: error al leer el archivo: {e}")
        return None

    if not isinstance(data, np.ndarray):
        data = np.asarray(data, dtype=np.float32)
    else:
        data = data.astype(np.float32)

    if data.size == 0:
        logger.logger.info(f"[S5_LEADVOX_DYNAMICS] {fname}: archivo vacío; se omite.")
        return None

    pre_rms_db, pre_peak_db, pre_crest_db = compute_crest_factor_db(_to_mono(data))

    # 0) pre-gain (alineación p50 rel BED)
    if float(pre_gain_db) != 0.0:
        data = (data * _db_to_lin(pre_gain_db)).astype(np.float32)

    # 1) de-esser condicional (antes de compresión)
    deess_stats = {"enabled": 0.0, "avg_deess_db": 0.0, "max_deess_db": 0.0}
    if bool(deesser_enable):
        data, deess_stats = _apply_deesser_fft(
            data,
            int(sr),
            ratio_thr_db=float(deess_thr_db),
            max_deess_db=float(deess_max_db),
            slope=float(deess_slope),
        )

    # 2) Leveler lento (consistencia short-term)
    #    Ajuste de threshold si excede límites de GR (hasta 3 iteraciones)
    leveler_avg_gr = 0.0
    leveler_max_gr = 0.0
    lvl_thr = float(leveler_threshold_db)
    y_lvl = data

    for _ in range(3):
        y_tmp, avg_gr, max_gr = _compress_leveler_rms(
            y_lvl,
            int(sr),
            threshold_db=lvl_thr,
            ratio=float(leveler_ratio),
            attack_ms=float(leveler_attack_ms),
            release_ms=float(leveler_release_ms),
            gate_dbfs=-55.0,
            makeup_db=0.0,
        )
        leveler_avg_gr = float(avg_gr)
        leveler_max_gr = float(max_gr)

        # si excede límites, sube threshold para relajar
        if leveler_max_gr > float(leveler_max_max_gr_db) + 0.3:
            lvl_thr += (leveler_max_gr - float(leveler_max_max_gr_db)) * 0.8
            continue
        if leveler_avg_gr > float(leveler_max_avg_gr_db) + 0.3:
            lvl_thr += (leveler_avg_gr - float(leveler_max_avg_gr_db)) * 0.9
            continue

        y_lvl = y_tmp
        break

    data2 = y_lvl

    # 3) Fast comp (consonantes/picos)
    fast_avg_gr = 0.0
    fast_max_gr = 0.0
    fast_thr = None

    if bool(fast_enable):
        # threshold teórico para limitar max GR de picos
        fast_thr = _compute_fast_comp_threshold_from_peak_limit(
            pre_peak_db=float(pre_peak_db) + float(pre_gain_db),
            ratio=float(fast_ratio),
            max_peak_gr_db=float(fast_max_peak_gr_db),
        )

        y_out, fast_avg_gr, fast_max_gr = compress_peak_detector(
            data2,
            int(sr),
            threshold_db=float(fast_thr),
            ratio=float(fast_ratio),
            attack_ms=float(fast_attack_ms),
            release_ms=float(fast_release_ms),
            makeup_gain_db=0.0,
        )
    else:
        y_out = data2

    post_rms_db, post_peak_db, post_crest_db = compute_crest_factor_db(_to_mono(y_out))

    sf.write(path, y_out.astype(np.float32), int(sr))

    return {
        "file_name": fname,
        "samplerate_hz": int(sr),
        "pre_rms_dbfs": float(pre_rms_db),
        "pre_peak_dbfs": float(pre_peak_db),
        "pre_crest_db": float(pre_crest_db),
        "post_rms_dbfs": float(post_rms_db),
        "post_peak_dbfs": float(post_peak_db),
        "post_crest_db": float(post_crest_db),
        "pre_gain_db_applied": float(pre_gain_db),
        "deesser": deess_stats,
        "leveler": {
            "threshold_db": float(lvl_thr),
            "ratio": float(leveler_ratio),
            "attack_ms": float(leveler_attack_ms),
            "release_ms": float(leveler_release_ms),
            "avg_gr_db": float(leveler_avg_gr),
            "max_gr_db": float(leveler_max_gr),
            "max_avg_gr_limit_db": float(leveler_max_avg_gr_db),
            "max_max_gr_limit_db": float(leveler_max_max_gr_db),
        },
        "fast_comp": {
            "enabled": bool(fast_enable),
            "threshold_db": float(fast_thr) if fast_thr is not None else None,
            "ratio": float(fast_ratio),
            "attack_ms": float(fast_attack_ms),
            "release_ms": float(fast_release_ms),
            "avg_gr_db": float(fast_avg_gr),
            "max_gr_db": float(fast_max_gr),
            "max_peak_gr_limit_db": float(fast_max_peak_gr_db),
        },
    }


def main() -> None:
    """
    Stage S5_LEADVOX_DYNAMICS (mejorado):
      - Alinea vocal con BED por short-term (p50) aplicando pre-gain limitado por pass.
      - De-esser condicional (ratio 5–10k vs 1–5k).
      - Compresión en 2 etapas: leveler lento + fast comp de picos/consonantes.
      - Tempo-sync para attack/release del fast comp si BPM fiable.
      - Guarda métricas completas.
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S5_LEADVOX_DYNAMICS.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]
    analysis = load_analysis(contract_id)

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}
    session: Dict[str, Any] = analysis.get("session", {}) or {}
    stems: List[Dict[str, Any]] = analysis.get("stems", []) or []

    crest_min = float(metrics.get("target_crest_factor_db_min", 6.0))
    crest_max = float(metrics.get("target_crest_factor_db_max", 12.0))
    max_avg_gr = float(metrics.get("max_average_gain_reduction_db", 6.0))
    max_auto_change = float(limits.get("max_vocal_automation_change_db_per_pass", 3.0))

    # Targets política vocal vs BED
    target_rel_p50_db = float(session.get("targets_rel_to_bed", {}).get("p50_db", metrics.get("target_vocal_rel_to_bed_p50_db", 1.0)))
    target_rel_p95_db = float(session.get("targets_rel_to_bed", {}).get("p95_db", metrics.get("target_vocal_rel_to_bed_p95_db", 3.0)))

    lead_profile_id = session.get("lead_profile_id", "Lead_Vocal_Melodic")
    temp_dir = get_temp_dir(contract_id, create=False)
    style_preset = str(analysis.get("style_preset", session.get("style_preset", "")) or "")

    bpm, bpm_conf, bpm_source = _get_bpm_from_analysis_or_audio(analysis, temp_dir)
    tempo_sync_enabled = (bpm is not None and float(bpm_conf) >= 0.15)

    # Fast comp params
    FAST_RATIO = float(metrics.get("leadvox_fast_ratio", 4.0))
    FAST_ATTACK_MS_DEFAULT = float(metrics.get("leadvox_fast_attack_ms", 5.0))
    FAST_RELEASE_MS_DEFAULT = float(metrics.get("leadvox_fast_release_ms", 110.0))
    FAST_MAX_PEAK_GR_DB = float(metrics.get("leadvox_fast_max_peak_gr_db", 8.0))

    if tempo_sync_enabled:
        FAST_RELEASE_MS = _tempo_synced_release_ms_for_vocal(float(bpm), style_preset)
        FAST_ATTACK_MS = _tempo_synced_attack_ms_for_vocal(float(bpm))
        logger.logger.info(
            f"[S5_LEADVOX_DYNAMICS] Tempo-sync ON: bpm={bpm:.2f} (conf={bpm_conf:.2f}, source={bpm_source}), "
            f"fast_attack_ms={FAST_ATTACK_MS:.1f}, fast_release_ms={FAST_RELEASE_MS:.1f}."
        )
    else:
        FAST_RELEASE_MS = FAST_RELEASE_MS_DEFAULT
        FAST_ATTACK_MS = FAST_ATTACK_MS_DEFAULT
        logger.logger.info(
            f"[S5_LEADVOX_DYNAMICS] Tempo-sync OFF; fast_attack_ms={FAST_ATTACK_MS:.1f}, fast_release_ms={FAST_RELEASE_MS:.1f}."
        )

    # Leveler params (consistencia)
    LVL_RATIO = float(metrics.get("leadvox_leveler_ratio", 2.0))
    LVL_ATTACK_MS = float(metrics.get("leadvox_leveler_attack_ms", 35.0))
    LVL_RELEASE_MS = float(metrics.get("leadvox_leveler_release_ms", 260.0))
    LVL_MAX_AVG_GR_DB = float(metrics.get("leadvox_leveler_max_avg_gr_db", 4.0))
    LVL_MAX_MAX_GR_DB = float(metrics.get("leadvox_leveler_max_max_gr_db", 8.0))

    # De-esser params
    DEESS_THR_DB = float(metrics.get("deesser_ratio_hi_over_mid_threshold_db", -3.0))
    DEESS_MAX_DB = float(metrics.get("deesser_max_deess_db", 6.0))
    DEESS_SLOPE = float(metrics.get("deesser_slope", 0.8))

    # ------------------------------------------------------------------
    # 1) Preparar tareas para stems lead vocal
    # ------------------------------------------------------------------
    tasks: List[Tuple[str, str, float, bool, float, float, float, float, float, float, float, float, float, bool, float, float, float, float]] = []

    for stem in stems:
        fname = stem.get("file_name")
        if not fname:
            continue
        if not stem.get("is_lead_vocal", False):
            continue

        path = temp_dir / fname
        if not path.exists():
            continue

        pre_peak_db = stem.get("pre_peak_dbfs")
        pre_crest_db = stem.get("pre_crest_factor_db")

        try:
            pre_peak_db = float(pre_peak_db)
            pre_crest_db = float(pre_crest_db)
        except (TypeError, ValueError):
            logger.logger.info(f"[S5_LEADVOX_DYNAMICS] {fname}: métricas previas inválidas; se omite.")
            continue

        # Pre-gain recomendado desde análisis (alineación p50 rel BED), clamp redundante por seguridad
        pre_gain_db = float(stem.get("recommended_pre_gain_db", 0.0))
        pre_gain_db = float(np.clip(pre_gain_db, -max_auto_change, max_auto_change))

        # De-esser condicional (de análisis) con fallback por métrica
        deesser_enable = bool(stem.get("deesser_recommended_enabled", False))
        sib_p95 = stem.get("vocal_sibilance_ratio_hi5_10k_over_mid1_5k_p95_db")
        try:
            if sib_p95 is not None and float(sib_p95) == float(sib_p95):
                deesser_enable = deesser_enable or (float(sib_p95) > float(DEESS_THR_DB) + 1.0)
        except (TypeError, ValueError):
            pass

        # Decide fast comp:
        #   - Si crest alto (picos consonánticos) o si el objetivo p95 rel BED requiere control de picos.
        rel_p95 = stem.get("vocal_rel_to_bed_p95_db")
        need_fast = False
        try:
            if float(pre_crest_db) > float(crest_max) + 0.5:
                need_fast = True
        except Exception:
            pass
        try:
            if rel_p95 is not None and float(rel_p95) == float(rel_p95):
                # si la vocal está baja en p95 rel, en realidad fast comp no ayuda;
                # fast comp es para controlar picos, así que lo activamos si está alta o inestable:
                if float(rel_p95) > float(target_rel_p95_db) + 1.0:
                    need_fast = True
        except Exception:
            pass

        # Threshold leveler:
        #   - Si tenemos bed_p50, target vocal p50 = bed_p50 + target_rel_p50
        #   - sino: usa pre_rms-3 dB como punto conservador
        bed_p50 = session.get("bed_short_term_p50_dbfs")
        pre_rms_db = stem.get("pre_rms_dbfs")
        try:
            if bed_p50 is not None and float(bed_p50) == float(bed_p50):
                target_vocal_p50 = float(bed_p50) + float(target_rel_p50_db)
                leveler_threshold_db = float(target_vocal_p50 - 2.0)
            else:
                leveler_threshold_db = float(pre_rms_db) - 3.0 if pre_rms_db is not None else -24.0
        except Exception:
            leveler_threshold_db = -24.0

        # Safety: si el stem es muy bajo, no metas procesamiento agresivo
        if pre_peak_db <= -60.0:
            logger.logger.info(
                f"[S5_LEADVOX_DYNAMICS] {fname}: nivel muy bajo (peak={pre_peak_db:.1f} dBFS); se omite."
            )
            continue

        tasks.append(
            (
                fname,
                str(path),
                float(pre_gain_db),
                bool(deesser_enable),
                float(DEESS_THR_DB),
                float(DEESS_MAX_DB),
                float(DEESS_SLOPE),
                float(leveler_threshold_db),
                float(LVL_RATIO),
                float(LVL_ATTACK_MS),
                float(LVL_RELEASE_MS),
                float(LVL_MAX_AVG_GR_DB),
                float(LVL_MAX_MAX_GR_DB),
                bool(need_fast),
                float(FAST_RATIO),
                float(FAST_ATTACK_MS),
                float(FAST_RELEASE_MS),
                float(FAST_MAX_PEAK_GR_DB),
            )
        )

    # ------------------------------------------------------------------
    # 2) Ejecutar en serie
    # ------------------------------------------------------------------
    metrics_records: List[Dict[str, Any]] = []
    processed = 0

    if not tasks:
        logger.logger.info("[S5_LEADVOX_DYNAMICS] No hay stems lead válidos para procesar.")
    else:
        for result in map(_compress_lead_stem_worker, tasks):
            if result is None:
                continue

            fname = result["file_name"]
            lvl = result["leveler"]
            fcmp = result["fast_comp"]
            deess = result["deesser"]

            logger.logger.info(
                f"[S5_LEADVOX_DYNAMICS] {fname}: pre_gain={result['pre_gain_db_applied']:.2f} dB, "
                f"deess_en={bool(deess.get('enabled', 0.0))}, deess_max={float(deess.get('max_deess_db', 0.0)):.2f} dB, "
                f"lvl_avgGR={float(lvl.get('avg_gr_db', 0.0)):.2f} dB, lvl_maxGR={float(lvl.get('max_gr_db', 0.0)):.2f} dB, "
                f"fast_en={bool(fcmp.get('enabled', False))}, fast_maxGR={float(fcmp.get('max_gr_db', 0.0)):.2f} dB, "
                f"crest_pre={result['pre_crest_db']:.2f} dB, crest_post={result['post_crest_db']:.2f} dB."
            )

            rec = dict(result)
            rec["max_vocal_automation_change_db_per_pass"] = max_auto_change
            rec["tempo_sync_enabled"] = bool(tempo_sync_enabled)
            rec["bpm"] = bpm
            rec["bpm_confidence"] = bpm_conf
            rec["bpm_source"] = bpm_source
            rec["targets_rel_to_bed"] = {"p50_db": target_rel_p50_db, "p95_db": target_rel_p95_db}
            rec["lead_profile_id"] = lead_profile_id
            metrics_records.append(rec)
            processed += 1

    # ------------------------------------------------------------------
    # 3) Guardar métricas
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
                "tempo_sync_enabled": bool(tempo_sync_enabled),
                "bpm": bpm,
                "bpm_confidence": bpm_conf,
                "bpm_source": bpm_source,
                "targets_rel_to_bed": {"p50_db": target_rel_p50_db, "p95_db": target_rel_p95_db},
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
