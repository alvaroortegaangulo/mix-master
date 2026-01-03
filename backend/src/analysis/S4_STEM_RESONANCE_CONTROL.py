# C:\mix-master\backend\src\analysis\S4_STEM_RESONANCE_CONTROL.py

from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

# --- hack para importar utils ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import numpy as np  # noqa: E402

from utils.analysis_utils import (  # noqa: E402
    load_contract,
    get_temp_dir,
    sf_read_limited,
)
from utils.session_utils import load_session_config  # noqa: E402
from utils.resonance_utils import compute_magnitude_spectrum  # noqa: E402


# ---------------------------------------------------------------------
# Robust resonance detection (local-prominence on smoothed baseline)
# ---------------------------------------------------------------------

def _moving_median(x: np.ndarray, win: int) -> np.ndarray:
    """
    Running median (robust baseline).
    Uses sliding_window_view if available; fallback to moving average.
    """
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
        med = np.median(w, axis=-1).astype(np.float32)
        return med
    except Exception:
        # Fallback: moving average (less robust but safe)
        k = np.ones(win, dtype=np.float32) / float(win)
        avg = np.convolve(xpad, k, mode="valid").astype(np.float32)
        return avg


def _find_peaks_local_prominence(
    freqs: np.ndarray,
    mag_lin: np.ndarray,
    fmin: float,
    fmax: float,
    local_window_hz: float,
    threshold_db: float,
    max_resonances: int,
) -> List[Dict[str, Any]]:
    """
    Detecta resonancias como picos de prominencia local:
      residual_db = mag_db - baseline_db
    y extrae:
      - freq_hz
      - gain_above_local_db (prominencia)
      - peak_db
      - baseline_db
      - bandwidth_hz (aprox -3 dB)
      - q_suggested
    """
    freqs = np.asarray(freqs, dtype=np.float32)
    mag_lin = np.asarray(mag_lin, dtype=np.float32)

    if freqs.size == 0 or mag_lin.size == 0:
        return []

    # Selección de banda
    fmin = float(fmin)
    fmax = float(fmax)
    if fmax <= fmin:
        return []

    band_mask = (freqs >= fmin) & (freqs <= fmax)
    if not np.any(band_mask):
        return []

    fb = freqs[band_mask]
    mb = mag_lin[band_mask]

    # Evitar -inf
    eps = 1e-12
    mag_db = 20.0 * np.log10(np.maximum(mb, eps))

    # Parámetros de ventana en bins
    df = float(np.median(np.diff(fb))) if fb.size > 2 else 1.0
    df = max(df, 1e-6)

    win_bins = int(round(float(local_window_hz) / df))
    win_bins = max(11, win_bins)  # baseline razonablemente suave
    if win_bins % 2 == 0:
        win_bins += 1

    baseline_db = _moving_median(mag_db, win_bins)
    residual_db = mag_db - baseline_db

    # Guard band para evitar sesgo en bordes (muy importante)
    edge_guard_hz = 0.5 * float(local_window_hz)
    valid_edge = (fb >= (fmin + edge_guard_hz)) & (fb <= (fmax - edge_guard_hz))

    # Candidatos a pico: máximo local + umbral
    r = residual_db
    cand = np.zeros_like(r, dtype=bool)
    if r.size >= 3:
        cand[1:-1] = (r[1:-1] > r[:-2]) & (r[1:-1] >= r[2:]) & (r[1:-1] >= float(threshold_db))
    cand &= valid_edge

    idxs = np.where(cand)[0]
    if idxs.size == 0:
        return []

    # Separación mínima entre picos: ~1/6 octave o edge_guard, lo que sea mayor
    min_ratio = 2.0 ** (1.0 / 6.0)  # 1/6 de octava
    min_spacing_hz = max(30.0, 0.25 * float(local_window_hz))

    # Ordenar por prominencia (desc)
    idxs = sorted(idxs.tolist(), key=lambda i: float(r[i]), reverse=True)

    selected: List[int] = []
    selected_freqs: List[float] = []

    for i in idxs:
        if len(selected) >= int(max_resonances):
            break
        fi = float(fb[i])

        # spacing absoluto
        if any(abs(fi - f0) < min_spacing_hz for f0 in selected_freqs):
            continue
        # spacing relativo (octavas)
        if any((max(fi, f0) / max(min(fi, f0), 1e-6)) < min_ratio for f0 in selected_freqs):
            continue

        selected.append(i)
        selected_freqs.append(fi)

    results: List[Dict[str, Any]] = []
    for i in selected:
        fi = float(fb[i])
        prom = float(r[i])
        peak_db = float(mag_db[i])
        base_db = float(baseline_db[i])

        # Bandwidth aprox (-3 dB sobre la prominencia)
        target = prom - 3.0
        left = i
        while left > 0 and float(r[left]) > target:
            left -= 1
        right = i
        while right < (r.size - 1) and float(r[right]) > target:
            right += 1

        bw = float(fb[right] - fb[left]) if right > left else float(df * 2.0)
        bw = max(bw, float(df * 2.0))

        q = float(fi / bw) if bw > 0 else 8.0
        q = float(np.clip(q, 2.0, 14.0))

        results.append(
            {
                "freq_hz": fi,
                "gain_above_local_db": prom,
                "peak_db": peak_db,
                "baseline_db": base_db,
                "bandwidth_hz": bw,
                "q_suggested": q,
            }
        )

    # Orden final por frecuencia (más legible)
    results.sort(key=lambda d: float(d.get("freq_hz", 0.0)))
    return results


def _to_mono(y: np.ndarray) -> np.ndarray:
    y = np.asarray(y, dtype=np.float32)
    if y.ndim == 2 and y.shape[1] >= 1:
        return np.mean(y, axis=1).astype(np.float32)
    return y.astype(np.float32)


def _analyze_stem(
    args: Tuple[Path, str, float, float, float, float, float, int]
) -> Dict[str, Any]:
    (
        stem_path,
        inst_prof,
        max_res_peak_db,
        max_cuts_db,
        fmin,
        fmax,
        local_window_hz,
        max_filters_per_band,
    ) = args

    fname = stem_path.name

    try:
        y, sr = sf_read_limited(stem_path, always_2d=True)
    except Exception as e:
        logger.logger.info(f"[S4_STEM_RESONANCE_CONTROL] Aviso: no se puede leer '{fname}': {e}.")
        return {
            "file_name": fname,
            "file_path": str(stem_path),
            "instrument_profile": inst_prof,
            "samplerate_hz": None,
            "resonances": [],
            "num_resonances_detected": 0,
        }

    y_mono = _to_mono(y)

    # Magnitude spectrum (utils)
    freqs, mag_lin = compute_magnitude_spectrum(y_mono, int(sr))

    resonances = _find_peaks_local_prominence(
        freqs=freqs,
        mag_lin=mag_lin,
        fmin=float(fmin),
        fmax=float(fmax),
        local_window_hz=float(local_window_hz),
        threshold_db=float(max_res_peak_db),
        max_resonances=int(max_filters_per_band),
    )

    return {
        "file_name": fname,
        "file_path": str(stem_path),
        "instrument_profile": inst_prof,
        "samplerate_hz": int(sr),
        "resonances": resonances,
        "num_resonances_detected": int(len(resonances)),
    }


def main() -> None:
    """
    Análisis para el contrato S4_STEM_RESONANCE_CONTROL.
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S4_STEM_RESONANCE_CONTROL.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]

    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    max_res_peak_db = float(metrics.get("max_resonance_peak_db_above_local", 12.0))
    max_cuts_db = float(limits.get("max_resonant_cuts_db", 8.0))
    max_filters_per_band = int(limits.get("max_resonant_filters_per_band", 3))

    # Banda: bajar fmin para evitar “borde 200 Hz” y permitir detectar booms reales
    BAND_FMIN = float(metrics.get("band_fmin_hz", 80.0))
    BAND_FMAX = float(metrics.get("band_fmax_hz", 12000.0))
    LOCAL_WINDOW_HZ = float(metrics.get("local_window_hz", 220.0))

    temp_dir = get_temp_dir(contract_id, create=True)
    cfg = load_session_config(contract_id)
    style_preset = cfg["style_preset"]
    instrument_by_file = cfg["instrument_by_file"]

    stem_files: List[Path] = sorted(
        p for p in temp_dir.glob("*.wav")
        if p.name.lower() != "full_song.wav"
    )

    tasks: List[Tuple[Path, str, float, float, float, float, float, int]] = []
    for p in stem_files:
        inst_prof = instrument_by_file.get(p.name, "Other")
        tasks.append(
            (
                p,
                inst_prof,
                max_res_peak_db,
                max_cuts_db,
                BAND_FMIN,
                BAND_FMAX,
                LOCAL_WINDOW_HZ,
                max_filters_per_band,
            )
        )

    stems_analysis = list(map(_analyze_stem, tasks)) if tasks else []

    total_resonances = 0
    worst = 0.0
    for st in stems_analysis:
        n = int(st.get("num_resonances_detected", 0) or 0)
        total_resonances += n
        for r in (st.get("resonances", []) or []):
            try:
                worst = max(worst, float(r.get("gain_above_local_db", 0.0)))
            except Exception:
                pass

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "max_resonance_peak_db_above_local": max_res_peak_db,
            "max_resonant_cuts_db": max_cuts_db,
            "max_resonant_filters_per_band": max_filters_per_band,
            "band_fmin_hz": BAND_FMIN,
            "band_fmax_hz": BAND_FMAX,
            "local_window_hz": LOCAL_WINDOW_HZ,
            "total_resonances_detected": total_resonances,
            "worst_gain_above_local_db": float(worst),
        },
        "stems": stems_analysis,
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    logger.logger.info(
        f"[S4_STEM_RESONANCE_CONTROL] Análisis completado para {len(stems_analysis)} stems. "
        f"Resonancias totales={total_resonances}, worst={worst:.2f} dB. JSON: {output_path}"
    )


if __name__ == "__main__":
    main()
