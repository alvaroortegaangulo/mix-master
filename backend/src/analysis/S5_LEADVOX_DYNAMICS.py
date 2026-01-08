# C:\mix-master\backend\src\analysis\S5_LEADVOX_DYNAMICS.py
from __future__ import annotations

from utils.logger import logger
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import json
import numpy as np
import soundfile as sf

# --- hack para importar utils ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.analysis_utils import (  # noqa: E402
    load_contract,
    get_temp_dir,
    sf_read_limited,
)
from utils.session_utils import load_session_config  # noqa: E402
from utils.dynamics_utils import compute_crest_factor_db  # noqa: E402


# -----------------------------
# Helpers numéricos / audio
# -----------------------------
EPS = 1e-12


def _db(x: float) -> float:
    return float(20.0 * np.log10(max(float(x), EPS)))


def _rms_dbfs(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=np.float32)
    if x.size == 0:
        return float("-inf")
    rms = float(np.sqrt(np.mean(x * x) + EPS))
    return _db(rms)


def _read_audio_limited(
    path: Path,
    max_seconds: float = 600.0,
    always_2d: bool = True,
) -> tuple[np.ndarray | None, int | None, str | None]:
    """
    Lee audio limitado en duración para análisis de métricas.
    Devuelve (y, sr, err).
      - y en float32, shape (n, ch) si always_2d=True; si no, puede ser 1D.
    """
    try:
        with sf.SoundFile(str(path)) as f:
            sr = int(f.samplerate)
            max_frames = int(max_seconds * sr)
            frames = min(max_frames, len(f))
            y = f.read(frames=frames, dtype="float32", always_2d=always_2d)
        if y is None:
            return None, None, "lectura None"
        if not isinstance(y, np.ndarray):
            y = np.asarray(y, dtype=np.float32)
        if y.size == 0:
            return None, None, "archivo vacío"
        return y.astype(np.float32), sr, None
    except Exception as e:
        return None, None, str(e)


def _to_mono(y: np.ndarray) -> np.ndarray:
    if y.ndim == 1:
        return y.astype(np.float32)
    return np.mean(y, axis=1).astype(np.float32)


def _short_term_rms_db_series(
    y_mono: np.ndarray,
    sr: int,
    win_s: float = 3.0,
    hop_s: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Serie short-term (ventana tipo EBU, 3s, hop 1s) usando RMS dBFS (aprox. ST loudness).
    Devuelve (t_centers_s, st_rms_db).
    """
    y = np.asarray(y_mono, dtype=np.float32)
    if y.size == 0:
        return np.zeros((0,), dtype=np.float32), np.zeros((0,), dtype=np.float32)

    win = max(int(round(win_s * sr)), 1)
    hop = max(int(round(hop_s * sr)), 1)

    if y.size < win:
        t = np.array([0.0], dtype=np.float32)
        return t, np.array([_rms_dbfs(y)], dtype=np.float32)

    y2 = (y * y).astype(np.float64)
    c = np.concatenate([np.zeros((1,), dtype=np.float64), np.cumsum(y2, dtype=np.float64)])

    starts = np.arange(0, y.size - win + 1, hop, dtype=np.int64)
    sums = c[starts + win] - c[starts]
    rms = np.sqrt(sums / float(win) + EPS).astype(np.float32)
    dbs = (20.0 * np.log10(np.maximum(rms, EPS))).astype(np.float32)

    t_centers = (starts.astype(np.float32) + 0.5 * float(win)) / float(sr)
    return t_centers.astype(np.float32), dbs


def _vad_mask_from_short_term(
    st_db: np.ndarray,
    floor_offset_db: float = 10.0,
    min_gate_dbfs: float = -55.0,
) -> np.ndarray:
    """
    Máscara de actividad vocal sobre la serie short-term.
    Regla robusta:
      gate = max(min_gate_dbfs, p10(st_db) + floor_offset_db)
      active = st_db > gate
    """
    if st_db.size == 0:
        return np.zeros((0,), dtype=bool)
    p10 = float(np.percentile(st_db, 10.0))
    gate = max(min_gate_dbfs, p10 + float(floor_offset_db))
    return (st_db > gate)


def _segments_from_mask(
    t_s: np.ndarray,
    mask: np.ndarray,
    min_len_s: float = 6.0,
    gap_merge_s: float = 2.0,
) -> List[Dict[str, float]]:
    """
    Convierte una máscara booleana (por frames ST) a segmentos [t_start, t_end].
    - Fusiona gaps pequeños.
    - Descarta segmentos muy cortos.
    """
    segs: List[Dict[str, float]] = []
    if mask.size == 0 or t_s.size != mask.size:
        return segs

    idx = np.where(mask)[0]
    if idx.size == 0:
        return segs

    # Estima hop a partir de tiempos (asume casi uniforme)
    hop_s = float(np.median(np.diff(t_s))) if t_s.size > 1 else 1.0
    max_gap_frames = int(round(gap_merge_s / max(hop_s, 1e-6)))

    start = int(idx[0])
    prev = int(idx[0])

    for i in idx[1:]:
        i = int(i)
        if i <= prev + max_gap_frames:
            prev = i
            continue
        # cerrar segmento
        t0 = float(t_s[start])
        t1 = float(t_s[prev] + hop_s)
        if (t1 - t0) >= min_len_s:
            segs.append({"t_start_s": t0, "t_end_s": t1})
        start = i
        prev = i

    t0 = float(t_s[start])
    t1 = float(t_s[prev] + hop_s)
    if (t1 - t0) >= min_len_s:
        segs.append({"t_start_s": t0, "t_end_s": t1})

    return segs


def _band_energy_ratio_db_p95(
    y_mono: np.ndarray,
    sr: int,
    band_hi: tuple[float, float] = (5000.0, 10000.0),
    band_mid: tuple[float, float] = (1000.0, 5000.0),
    frame: int = 2048,
    hop: int = 512,
    max_seconds: float = 120.0,
) -> Dict[str, float]:
    """
    Calcula ratio energético (dB) entre band_hi y band_mid en STFT,
    y devuelve p50/p95 (robusto) en dB.
    Procesa sólo hasta max_seconds para coste controlado (en análisis).
    """
    y = np.asarray(y_mono, dtype=np.float32)
    if y.size == 0 or sr <= 0:
        return {"p50_db": float("nan"), "p95_db": float("nan")}

    max_n = int(min(y.size, int(max_seconds * sr)))
    y = y[:max_n]

    if y.size < frame:
        return {"p50_db": float("nan"), "p95_db": float("nan")}

    win = np.hanning(frame).astype(np.float32)
    freqs = np.fft.rfftfreq(frame, d=1.0 / float(sr)).astype(np.float32)

    hi_mask = (freqs >= band_hi[0]) & (freqs < band_hi[1])
    mid_mask = (freqs >= band_mid[0]) & (freqs < band_mid[1])

    ratios: List[float] = []
    n_frames = 1 + (y.size - frame) // hop

    for k in range(n_frames):
        i0 = k * hop
        x = y[i0 : i0 + frame]
        X = np.fft.rfft(x * win)
        mag2 = (np.abs(X) ** 2).astype(np.float64)
        e_hi = float(np.sum(mag2[hi_mask]) + EPS)
        e_mid = float(np.sum(mag2[mid_mask]) + EPS)
        r_db = float(10.0 * np.log10(e_hi / e_mid))
        ratios.append(r_db)

    if not ratios:
        return {"p50_db": float("nan"), "p95_db": float("nan")}

    arr = np.array(ratios, dtype=np.float32)
    return {
        "p50_db": float(np.percentile(arr, 50.0)),
        "p95_db": float(np.percentile(arr, 95.0)),
    }


def _is_lead_vocal_profile(inst: str | None, lead_id: str) -> bool:
    """
    Determina si un instrument_profile se considera 'lead vocal' para este contrato.
    Regla mínima:
      - Igual al instrument_id del contrato, o
      - Empieza por 'Lead_Vocal'.
    """
    if not inst:
        return False
    if inst == lead_id:
        return True
    if inst.startswith("Lead_Vocal"):
        return True
    return False


def _is_any_vocal_profile(inst: str | None) -> bool:
    """
    Heurística para excluir voces del BED.
    """
    if not inst:
        return False
    s = inst.lower()
    if "vocal" in s or "vox" in s:
        return True
    return False


def _analyze_stem(args: Tuple[Path, str, bool]) -> Dict[str, Any]:
    """
    Recibe:
      - stem_path
      - instrument_profile
      - is_lead
    Devuelve dict con métricas pre y (si es lead) métricas musicales adicionales.
    """
    stem_path, inst_prof, is_lead = args
    fname = stem_path.name

    try:
        y, sr = sf_read_limited(stem_path, always_2d=False)
    except Exception as e:
        return {
            "file_name": fname,
            "file_path": str(stem_path),
            "instrument_profile": inst_prof,
            "is_lead_vocal": is_lead,
            "samplerate_hz": None,
            "pre_rms_dbfs": None,
            "pre_peak_dbfs": None,
            "pre_crest_factor_db": None,
            "error": f"[S5_LEADVOX_DYNAMICS] Aviso: no se puede leer '{fname}': {e}.",
        }

    rms_db, peak_db, crest_db = compute_crest_factor_db(y)
    return {
        "file_name": fname,
        "file_path": str(stem_path),
        "instrument_profile": inst_prof,
        "is_lead_vocal": is_lead,
        "samplerate_hz": int(sr) if sr is not None else None,
        "pre_rms_dbfs": rms_db,
        "pre_peak_dbfs": peak_db,
        "pre_crest_factor_db": crest_db,
        "error": None,
    }


def _read_mono_limited(path: Path, max_seconds: float = 90.0) -> tuple[np.ndarray | None, int | None, str | None]:
    """Lectura limitada y mono para estimación de BPM."""
    y, sr, err = _read_audio_limited(path, max_seconds=max_seconds, always_2d=True)
    if err is not None or y is None or sr is None:
        return None, None, err
    return _to_mono(y), sr, None


def _estimate_bpm_from_audio(
    y: np.ndarray, sr: int, bpm_min: float = 60.0, bpm_max: float = 200.0
) -> tuple[float | None, float]:
    """Idéntico criterio que en drums: energía + autocorrelación FFT."""
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


def _build_bed_mix_limited(
    temp_dir: Path,
    stems_analysis: List[Dict[str, Any]],
    max_seconds: float = 600.0,
) -> tuple[np.ndarray | None, int | None, str]:
    """
    BED = suma de stems NO vocales (excluye Lead Vocal y cualquier Vocal/Vox).
    Devuelve (bed_mono, sr, reason).
    """
    bed: Optional[np.ndarray] = None
    sr0: Optional[int] = None
    used = 0

    for st in stems_analysis:
        fname = st.get("file_name")
        inst = st.get("instrument_profile")
        if not fname or not inst:
            continue
        if _is_any_vocal_profile(inst):
            continue
        path = temp_dir / fname
        if not path.exists():
            continue

        y, sr, err = _read_audio_limited(path, max_seconds=max_seconds, always_2d=True)
        if err is not None or y is None or sr is None:
            continue

        y_mono = _to_mono(y)

        if sr0 is None:
            sr0 = int(sr)
            bed = y_mono.astype(np.float32)
            used += 1
        else:
            if int(sr) != int(sr0):
                continue
            if bed is None:
                bed = y_mono.astype(np.float32)
                used += 1
                continue
            n = min(bed.size, y_mono.size)
            bed = bed[:n] + y_mono[:n]
            used += 1

    if bed is None or sr0 is None or used == 0:
        return None, None, "no_bed_stems"
    return bed.astype(np.float32), int(sr0), f"sum_{used}_stems"


def main() -> None:
    """
    Análisis para el contrato S5_LEADVOX_DYNAMICS.
    Uso desde stage.py: python analysis/S5_LEADVOX_DYNAMICS.py S5_LEADVOX_DYNAMICS
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S5_LEADVOX_DYNAMICS.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]

    # 1) Cargar contrato
    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    # Targets de crest (se mantiene, pero ya no es el único driver)
    crest_min = float(metrics.get("target_crest_factor_db_min", 6.0))
    crest_max = float(metrics.get("target_crest_factor_db_max", 12.0))
    max_avg_gr = float(metrics.get("max_average_gain_reduction_db", 6.0))
    max_auto_change = float(limits.get("max_vocal_automation_change_db_per_pass", 3.0))

    # Política recomendada (defaults)
    target_rel_p50_db = float(metrics.get("target_vocal_rel_to_bed_p50_db", 1.0))
    target_rel_p95_db = float(metrics.get("target_vocal_rel_to_bed_p95_db", 3.0))
    st_win_s = float(metrics.get("short_term_window_s", 3.0))
    st_hop_s = float(metrics.get("short_term_hop_s", 1.0))
    analysis_max_seconds = float(metrics.get("analysis_max_seconds", 600.0))

    # De-esser condicional
    deess_thr_db = float(metrics.get("deesser_ratio_hi_over_mid_threshold_db", -3.0))
    deess_enable_margin_db = float(metrics.get("deesser_enable_margin_db", 1.0))

    # 2) Directorio temp/<contract_id> y session_config
    temp_dir = get_temp_dir(contract_id, create=True)
    cfg = load_session_config(contract_id)
    style_preset = cfg.get("style_preset", "")
    instrument_by_file = cfg.get("instrument_by_file", {}) or {}

    lead_profile_id = contract.get("instrument_id", "Lead_Vocal_Melodic")

    bpm, bpm_conf, bpm_source = _get_bpm(cfg, temp_dir)
    if bpm is not None:
        logger.logger.info(
            f"[S5_LEADVOX_DYNAMICS] BPM detectado={bpm:.2f} (conf={bpm_conf:.2f}, source={bpm_source})."
        )
    else:
        logger.logger.info("[S5_LEADVOX_DYNAMICS] BPM no disponible (tempo-sync downstream puede quedar inactivo).")

    # 3) Listar stems (.wav) (excluyendo full_song.wav)
    stem_files: List[Path] = sorted(p for p in temp_dir.glob("*.wav") if p.name.lower() != "full_song.wav")

    # 4) Preparar tareas para análisis (serie)
    tasks: List[Tuple[Path, str, bool]] = []
    for p in stem_files:
        fname = p.name
        inst_prof = instrument_by_file.get(fname, "Other")
        is_lead = _is_lead_vocal_profile(inst_prof, lead_profile_id)
        tasks.append((p, inst_prof, is_lead))

    # 5) Ejecutar análisis base (crest/rms/peak)
    stems_analysis: List[Dict[str, Any]] = [_analyze_stem(t) for t in tasks] if tasks else []

    # 6) Construir BED (para targets relativos)
    bed_mono, bed_sr, bed_reason = _build_bed_mix_limited(
        temp_dir=temp_dir, stems_analysis=stems_analysis, max_seconds=analysis_max_seconds
    )
    if bed_mono is not None and bed_sr is not None:
        bed_t, bed_st_db = _short_term_rms_db_series(bed_mono, bed_sr, win_s=st_win_s, hop_s=st_hop_s)
        bed_st_p50 = float(np.percentile(bed_st_db, 50.0)) if bed_st_db.size else float("nan")
        logger.logger.info(
            f"[S5_LEADVOX_DYNAMICS] BED construido ({bed_reason}) sr={bed_sr}Hz, "
            f"ST_p50={bed_st_p50:.2f} dBFS."
        )
    else:
        bed_t = np.zeros((0,), dtype=np.float32)
        bed_st_db = np.zeros((0,), dtype=np.float32)
        bed_st_p50 = float("nan")
        logger.logger.info("[S5_LEADVOX_DYNAMICS] BED no disponible (targets relativos quedarán sin evaluar).")

    # 7) Métricas musicales por lead vocal: ST relativo, secciones, sibilancia
    n_lead = 0
    for st in stems_analysis:
        err = st.get("error")
        if err is not None:
            logger.logger.info(err)
            continue

        fname = st.get("file_name")
        is_lead = bool(st.get("is_lead_vocal", False))
        inst_prof = st.get("instrument_profile")

        rms_db = st.get("pre_rms_dbfs")
        peak_db = st.get("pre_peak_dbfs")
        crest_db = st.get("pre_crest_factor_db")

        if is_lead:
            n_lead += 1

        if rms_db is not None and peak_db is not None and crest_db is not None:
            if is_lead:
                logger.logger.info(
                    f"[S5_LEADVOX_DYNAMICS] LEAD {fname}: "
                    f"RMS={float(rms_db):.2f} dBFS, peak={float(peak_db):.2f} dBFS, crest={float(crest_db):.2f} dB."
                )
            else:
                logger.logger.info(
                    f"[S5_LEADVOX_DYNAMICS] {fname}: "
                    f"RMS={float(rms_db):.2f} dBFS, peak={float(peak_db):.2f} dBFS, crest={float(crest_db):.2f} dB."
                )

        # métricas avanzadas sólo para lead
        if not is_lead or not fname:
            continue

        path = temp_dir / fname
        y, sr, err2 = _read_audio_limited(path, max_seconds=analysis_max_seconds, always_2d=True)
        if err2 is not None or y is None or sr is None:
            st["vocal_metrics_error"] = f"no_read_for_advanced_metrics: {err2}"
            continue

        y_mono = _to_mono(y)

        # Short-term vocal
        vt, v_st_db = _short_term_rms_db_series(y_mono, int(sr), win_s=st_win_s, hop_s=st_hop_s)
        v_mask = _vad_mask_from_short_term(v_st_db, floor_offset_db=10.0, min_gate_dbfs=-55.0)

        st["vocal_short_term_window_s"] = st_win_s
        st["vocal_short_term_hop_s"] = st_hop_s
        st["vocal_short_term_active_ratio"] = float(np.mean(v_mask.astype(np.float32))) if v_mask.size else 0.0

        # BED relativo si es posible (mismo sr y longitudes razonables)
        rel_p50 = float("nan")
        rel_p95 = float("nan")
        rel_sections: List[Dict[str, Any]] = []
        recommended_pre_gain_db = 0.0

        if bed_mono is not None and bed_sr is not None and int(bed_sr) == int(sr) and bed_st_db.size and v_st_db.size:
            n = min(bed_st_db.size, v_st_db.size)
            rel = (v_st_db[:n] - bed_st_db[:n]).astype(np.float32)

            active = v_mask[:n]
            rel_active = rel[active] if np.any(active) else rel

            if rel_active.size:
                rel_p50 = float(np.percentile(rel_active, 50.0))
                rel_p95 = float(np.percentile(rel_active, 95.0))

                # Secciones (agrupadas por actividad vocal)
                segs = _segments_from_mask(vt[:n], active, min_len_s=6.0, gap_merge_s=2.0)
                for seg in segs:
                    t0 = float(seg["t_start_s"])
                    t1 = float(seg["t_end_s"])
                    # índices aproximados por tiempo
                    idx0 = int(np.searchsorted(vt[:n], t0, side="left"))
                    idx1 = int(np.searchsorted(vt[:n], t1, side="right"))
                    idx0 = max(0, min(idx0, n))
                    idx1 = max(0, min(idx1, n))
                    rseg = rel[idx0:idx1]
                    aseg = active[idx0:idx1]
                    ruse = rseg[aseg] if np.any(aseg) else rseg
                    if ruse.size:
                        rel_sections.append(
                            {
                                "t_start_s": t0,
                                "t_end_s": t1,
                                "rel_p50_db": float(np.percentile(ruse, 50.0)),
                                "rel_p95_db": float(np.percentile(ruse, 95.0)),
                            }
                        )

                # Pre-gain recomendado para alinear p50 (clamp por límites)
                delta = float(target_rel_p50_db - rel_p50)
                recommended_pre_gain_db = float(np.clip(delta, -max_auto_change, max_auto_change))

        st["vocal_rel_to_bed_p50_db"] = rel_p50
        st["vocal_rel_to_bed_p95_db"] = rel_p95
        st["vocal_rel_to_bed_sections"] = rel_sections
        st["recommended_pre_gain_db"] = float(recommended_pre_gain_db)
        st["targets_rel_to_bed"] = {"p50_db": target_rel_p50_db, "p95_db": target_rel_p95_db}

        # Sibilancia (ratio 5-10k / 1-5k)
        sib = _band_energy_ratio_db_p95(
            y_mono=y_mono,
            sr=int(sr),
            band_hi=(5000.0, 10000.0),
            band_mid=(1000.0, 5000.0),
            frame=2048,
            hop=512,
            max_seconds=min(120.0, analysis_max_seconds),
        )
        st["vocal_sibilance_ratio_hi5_10k_over_mid1_5k_p50_db"] = float(sib["p50_db"])
        st["vocal_sibilance_ratio_hi5_10k_over_mid1_5k_p95_db"] = float(sib["p95_db"])

        # De-esser recomendado (condicional)
        deesser_enabled = False
        if sib["p95_db"] == sib["p95_db"]:  # not NaN
            deesser_enabled = bool(float(sib["p95_db"]) > (deess_thr_db + deess_enable_margin_db))
        st["deesser_threshold_db"] = deess_thr_db
        st["deesser_enable_margin_db"] = deess_enable_margin_db
        st["deesser_recommended_enabled"] = bool(deesser_enabled)

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "target_crest_factor_min_db": crest_min,
            "target_crest_factor_max_db": crest_max,
            "max_average_gain_reduction_db": max_avg_gr,
            "max_vocal_automation_change_db_per_pass": max_auto_change,
            "lead_profile_id": lead_profile_id,
            "num_lead_vocal_stems": n_lead,
            "bpm": bpm,
            "bpm_confidence": bpm_conf,
            "bpm_source": bpm_source,
            "bed_available": bool(bed_mono is not None and bed_sr is not None),
            "bed_build_reason": bed_reason,
            "bed_short_term_p50_dbfs": float(bed_st_p50),
            "short_term_window_s": st_win_s,
            "short_term_hop_s": st_hop_s,
            "analysis_max_seconds": analysis_max_seconds,
            "targets_rel_to_bed": {"p50_db": target_rel_p50_db, "p95_db": target_rel_p95_db},
        },
        "stems": stems_analysis,
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    logger.logger.info(
        f"[S5_LEADVOX_DYNAMICS] Análisis completado para {len(stems_analysis)} stems "
        f"(lead_vocals={n_lead}). JSON: {output_path}"
    )


if __name__ == "__main__":
    main()
