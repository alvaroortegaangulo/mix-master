# C:\mix-master\backend\src\stages\S4_STEM_RESONANCE_CONTROL.py

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

from pedalboard import Pedalboard, PeakFilter  # noqa: E402

from utils.analysis_utils import get_temp_dir, sf_read_limited  # noqa: E402
from utils.resonance_utils import compute_magnitude_spectrum  # noqa: E402


# -------------------------------------------------------------------
# Load analysis
# -------------------------------------------------------------------

def load_analysis(contract_id: str) -> Dict[str, Any]:
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"
    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")
    with analysis_path.open("r", encoding="utf-8") as f:
        return json.load(f)


# -------------------------------------------------------------------
# Detector consistente con análisis (para métricas pre/post)
# -------------------------------------------------------------------

def _moving_median(x: np.ndarray, win: int) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    if win < 3:
        return x.copy()
    if win % 2 == 0:
        win += 1
    pad = win // 2
    xpad = np.pad(x, (pad, pad), mode="reflect")
    try:
        from numpy.lib.stride_tricks import sliding_window_view  # type: ignore
        w = sliding_window_view(xpad, win)
        return np.median(w, axis=-1).astype(np.float32)
    except Exception:
        k = np.ones(win, dtype=np.float32) / float(win)
        return np.convolve(xpad, k, mode="valid").astype(np.float32)


def _detect_resonances_local(
    y_mono: np.ndarray,
    sr: int,
    fmin: float,
    fmax: float,
    local_window_hz: float,
    threshold_db: float,
    max_resonances: int,
) -> List[Dict[str, Any]]:
    freqs, mag_lin = compute_magnitude_spectrum(np.asarray(y_mono, dtype=np.float32), int(sr))
    freqs = np.asarray(freqs, dtype=np.float32)
    mag_lin = np.asarray(mag_lin, dtype=np.float32)
    if freqs.size == 0 or mag_lin.size == 0:
        return []

    mask = (freqs >= float(fmin)) & (freqs <= float(fmax))
    if not np.any(mask):
        return []

    fb = freqs[mask]
    mb = mag_lin[mask]

    eps = 1e-12
    mag_db = 20.0 * np.log10(np.maximum(mb, eps))

    df = float(np.median(np.diff(fb))) if fb.size > 2 else 1.0
    df = max(df, 1e-6)
    win_bins = int(round(float(local_window_hz) / df))
    win_bins = max(11, win_bins)
    if win_bins % 2 == 0:
        win_bins += 1

    baseline_db = _moving_median(mag_db, win_bins)
    residual_db = mag_db - baseline_db

    edge_guard_hz = 0.5 * float(local_window_hz)
    valid_edge = (fb >= (float(fmin) + edge_guard_hz)) & (fb <= (float(fmax) - edge_guard_hz))

    r = residual_db
    cand = np.zeros_like(r, dtype=bool)
    if r.size >= 3:
        cand[1:-1] = (r[1:-1] > r[:-2]) & (r[1:-1] >= r[2:]) & (r[1:-1] >= float(threshold_db))
    cand &= valid_edge

    idxs = np.where(cand)[0]
    if idxs.size == 0:
        return []

    min_ratio = 2.0 ** (1.0 / 6.0)
    min_spacing_hz = max(30.0, 0.25 * float(local_window_hz))

    idxs = sorted(idxs.tolist(), key=lambda i: float(r[i]), reverse=True)

    sel: List[int] = []
    sel_f: List[float] = []

    for i in idxs:
        if len(sel) >= int(max_resonances):
            break
        fi = float(fb[i])
        if any(abs(fi - f0) < min_spacing_hz for f0 in sel_f):
            continue
        if any((max(fi, f0) / max(min(fi, f0), 1e-6)) < min_ratio for f0 in sel_f):
            continue
        sel.append(i)
        sel_f.append(fi)

    out: List[Dict[str, Any]] = []
    for i in sel:
        fi = float(fb[i])
        prom = float(r[i])
        peak_db = float(mag_db[i])
        base_db = float(baseline_db[i])

        target = prom - 3.0
        left = i
        while left > 0 and float(r[left]) > target:
            left -= 1
        right = i
        while right < (r.size - 1) and float(r[right]) > target:
            right += 1

        bw = float(fb[right] - fb[left]) if right > left else float(df * 2.0)
        bw = max(bw, float(df * 2.0))
        q = float(np.clip(fi / bw if bw > 0 else 8.0, 2.0, 14.0))

        out.append(
            {
                "freq_hz": fi,
                "gain_above_local_db": prom,
                "peak_db": peak_db,
                "baseline_db": base_db,
                "bandwidth_hz": bw,
                "q_suggested": q,
            }
        )

    out.sort(key=lambda d: float(d.get("freq_hz", 0.0)))
    return out


def _to_mono(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    if x.ndim == 2 and x.shape[1] >= 1:
        return np.mean(x, axis=1).astype(np.float32)
    return x.astype(np.float32)


# -------------------------------------------------------------------
# Filter design heuristics
# -------------------------------------------------------------------

def _is_low_end_instrument(inst: str | None) -> bool:
    s = (inst or "").lower()
    return any(k in s for k in ("kick", "bass", "sub", "808", "lowtom", "floor tom"))


def _cut_depth_db(excess_db: float, max_cuts_db: float, freq_hz: float, inst: str | None) -> float:
    """
    Evitar '8 dB always'. Curva suave:
      cut ~= 0.6*excess + 0.5, cap a max_cuts_db
    Protección low-mids: 200–350 Hz cap 4 dB salvo low-end.
    """
    excess_db = float(max(0.0, excess_db))
    if excess_db <= 0.0:
        return 0.0

    cut = 0.6 * excess_db + 0.5
    cut = float(min(cut, float(max_cuts_db)))

    f = float(freq_hz)
    if 200.0 <= f <= 350.0 and not _is_low_end_instrument(inst):
        cut = min(cut, 4.0)

    # micro-cuts no
    if cut < 0.4:
        return 0.0

    return float(cut)


def _q_for_resonance(res: Dict[str, Any], inst: str | None) -> float:
    """
    Usar q_suggested si existe; si no, fallback razonable.
    """
    try:
        q = float(res.get("q_suggested", 0.0))
        if 1.0 <= q <= 20.0:
            return float(np.clip(q, 2.0, 14.0))
    except Exception:
        pass

    f = float(res.get("freq_hz", 0.0) or 0.0)
    s = (inst or "").lower()

    if _is_low_end_instrument(s):
        return 3.5 if f < 250.0 else 5.0
    if "vocal" in s or "voice" in s:
        return 4.5 if f < 300.0 else 7.0
    if "guitar" in s:
        return 6.0 if f < 400.0 else 8.0
    return 6.0


def _build_notches(
    resonances: List[Dict[str, Any]],
    threshold_db: float,
    max_cuts_db: float,
    max_filters: int,
    inst: str | None,
) -> List[Dict[str, float]]:
    """
    Construye notches priorizando prominencia.
    Espaciado: 1/6 octava para evitar machacar low-mids.
    """
    if not resonances:
        return []

    thr = float(threshold_db)

    # ordenar por prominencia desc
    rs = sorted(resonances, key=lambda r: float(r.get("gain_above_local_db", 0.0)), reverse=True)

    min_ratio = 2.0 ** (1.0 / 6.0)
    used: List[float] = []
    out: List[Dict[str, float]] = []

    for r in rs:
        if len(out) >= int(max_filters):
            break

        try:
            f = float(r.get("freq_hz", 0.0))
            prom = float(r.get("gain_above_local_db", 0.0))
        except Exception:
            continue

        if f <= 0.0:
            continue

        excess = prom - thr
        cut = _cut_depth_db(excess, max_cuts_db, f, inst)
        if cut <= 0.0:
            continue

        # spacing 1/6 octave
        if any((max(f, f0) / max(min(f, f0), 1e-6)) < min_ratio for f0 in used):
            continue

        q = _q_for_resonance(r, inst)

        out.append(
            {
                "freq_hz": float(f),
                "cut_db": float(cut),
                "q": float(q),
                "prominence_db": float(prom),
            }
        )
        used.append(float(f))

    # ordenar por frecuencia para logging
    out.sort(key=lambda d: float(d["freq_hz"]))
    return out


# -------------------------------------------------------------------
# Stem processing
# -------------------------------------------------------------------

def _apply_notches_to_file(path: Path, notches: List[Dict[str, float]]) -> bool:
    if not notches:
        return False
    try:
        audio, sr = sf.read(path, always_2d=True)
        x = np.asarray(audio, dtype=np.float32)
        if x.size == 0:
            return False

        plugins = []
        for n in notches:
            f = float(n["freq_hz"])
            cut = float(n["cut_db"])
            q = float(n["q"])
            if f <= 0.0 or cut <= 0.0:
                continue
            plugins.append(PeakFilter(cutoff_frequency_hz=f, gain_db=-cut, q=q))

        if not plugins:
            return False

        board = Pedalboard(plugins)
        y = board(x, int(sr))
        y = np.asarray(y, dtype=np.float32)
        y = np.clip(y, -1.5, 1.5)

        sf.write(path, y, int(sr), subtype="FLOAT")
        return True
    except Exception as e:
        logger.logger.info(f"[S4_STEM_RESONANCE_CONTROL] Error procesando {path.name}: {e}")
        return False


def _worst_prominence(res: List[Dict[str, Any]]) -> float:
    w = 0.0
    for r in (res or []):
        try:
            w = max(w, float(r.get("gain_above_local_db", 0.0)))
        except Exception:
            pass
    return float(w)


def _save_metrics(
    temp_dir: Path,
    contract_id: str,
    metrics: Dict[str, Any],
    limits: Dict[str, Any],
    per_stem: List[Dict[str, Any]],
) -> None:
    out = temp_dir / "resonance_metrics_S4_STEM_RESONANCE_CONTROL.json"
    payload = {
        "contract_id": contract_id,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "stems": per_stem,
    }
    with out.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    logger.logger.info(f"[S4_STEM_RESONANCE_CONTROL] Métricas guardadas en: {out}")


def main() -> None:
    """
    Stage S4_STEM_RESONANCE_CONTROL:
      - Lee analysis_S4_STEM_RESONANCE_CONTROL.json.
      - Para cada stem: analiza pre -> diseña notches -> aplica -> analiza post.
      - Guarda resonance_metrics_S4_STEM_RESONANCE_CONTROL.json (pre/post real).
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S4_STEM_RESONANCE_CONTROL.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]

    analysis = load_analysis(contract_id)
    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}
    stems: List[Dict[str, Any]] = analysis.get("stems", []) or []
    session: Dict[str, Any] = analysis.get("session", {}) or {}

    threshold_db = float(metrics.get("max_resonance_peak_db_above_local", session.get("max_resonance_peak_db_above_local", 12.0)))
    max_cuts_db = float(limits.get("max_resonant_cuts_db", session.get("max_resonant_cuts_db", 8.0)))
    max_filters = int(limits.get("max_resonant_filters_per_band", session.get("max_resonant_filters_per_band", 3)))

    fmin = float(session.get("band_fmin_hz", metrics.get("band_fmin_hz", 80.0)))
    fmax = float(session.get("band_fmax_hz", metrics.get("band_fmax_hz", 12000.0)))
    local_window_hz = float(session.get("local_window_hz", metrics.get("local_window_hz", 220.0)))

    temp_dir = get_temp_dir(contract_id, create=False)

    per_stem_metrics: List[Dict[str, Any]] = []

    stems_touched = 0
    total_notches = 0

    for st in stems:
        fname = st.get("file_name")
        fpath = st.get("file_path")
        inst = st.get("instrument_profile") or "Other"

        if not fname or not fpath:
            continue

        path = Path(fpath)
        if not path.exists():
            continue
        if path.name.lower() == "full_song.wav":
            continue

        # Pre analysis (authoritative)
        y_pre, sr = sf_read_limited(path, always_2d=True)
        y_pre_mono = _to_mono(y_pre)
        res_pre = _detect_resonances_local(
            y_mono=y_pre_mono,
            sr=int(sr),
            fmin=fmin,
            fmax=fmax,
            local_window_hz=local_window_hz,
            threshold_db=threshold_db,
            max_resonances=max_filters,
        )
        worst_pre = _worst_prominence(res_pre)

        # Notch plan
        notches = _build_notches(
            resonances=res_pre,
            threshold_db=threshold_db,
            max_cuts_db=max_cuts_db,
            max_filters=max_filters,
            inst=inst,
        )

        applied = _apply_notches_to_file(path, notches)
        if applied:
            stems_touched += 1
            total_notches += len(notches)

        # Post analysis
        y_post, sr2 = sf_read_limited(path, always_2d=True)
        y_post_mono = _to_mono(y_post)
        res_post = _detect_resonances_local(
            y_mono=y_post_mono,
            sr=int(sr2),
            fmin=fmin,
            fmax=fmax,
            local_window_hz=local_window_hz,
            threshold_db=threshold_db,
            max_resonances=max_filters,
        )
        worst_post = _worst_prominence(res_post)

        if notches:
            notch_str = ", ".join([f"{n['freq_hz']:.0f}Hz/-{n['cut_db']:.1f}dB(Q={n['q']:.1f})" for n in notches])
        else:
            notch_str = "none"

        logger.logger.info(
            f"[S4_STEM_RESONANCE_CONTROL] {fname}: worst_pre={worst_pre:.2f} dB, "
            f"worst_post={worst_post:.2f} dB | notches={notch_str}"
        )

        per_stem_metrics.append(
            {
                "file_name": fname,
                "instrument_profile": inst,
                "samplerate_hz": int(sr2),
                "pre": {
                    "worst_gain_above_local_db": float(worst_pre),
                    "resonances": res_pre,
                },
                "post": {
                    "worst_gain_above_local_db": float(worst_post),
                    "resonances": res_post,
                },
                "applied_notches": notches,
            }
        )

    _save_metrics(temp_dir, contract_id, metrics, limits, per_stem_metrics)

    logger.logger.info(
        f"[S4_STEM_RESONANCE_CONTROL] Stage completado. stems procesados={stems_touched}, "
        f"notches totales={total_notches}."
    )


if __name__ == "__main__":
    main()
