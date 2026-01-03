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

from utils.analysis_utils import get_temp_dir  # noqa: E402
from utils.resonance_utils import compute_magnitude_spectrum, detect_resonances  # noqa: E402


def load_analysis(contract_id: str) -> Dict[str, Any]:
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"
    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")
    with analysis_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _to_mono(arr: np.ndarray) -> np.ndarray:
    x = np.asarray(arr, dtype=np.float32)
    if x.ndim > 1:
        return np.mean(x, axis=1).astype(np.float32)
    return x.astype(np.float32)


def _detect_on_audio(
    audio: np.ndarray,
    sr: int,
    fmin: float,
    fmax: float,
    threshold_db: float,
    local_window_hz: float,
    max_res: int,
) -> List[Dict[str, Any]]:
    y_mono = _to_mono(audio)
    freqs, mag_lin = compute_magnitude_spectrum(y_mono, int(sr))
    return detect_resonances(
        freqs=freqs,
        mag_lin=mag_lin,
        fmin=float(fmin),
        fmax=float(fmax),
        threshold_db=float(threshold_db),
        local_window_hz=float(local_window_hz),
        max_resonances=int(max_res),
    )


def _worst_gain(res_list: List[Dict[str, Any]]) -> float:
    worst = 0.0
    for r in res_list or []:
        try:
            g = float(r.get("gain_above_local_db", 0.0))
        except (TypeError, ValueError):
            continue
        if g > worst:
            worst = g
    return float(worst)


def _estimate_q(freq_hz: float, instrument_profile: str | None) -> float:
    """
    Q más musical y CLAMPED (evita Q=14).
    """
    inst = (instrument_profile or "").lower()
    f = float(freq_hz)

    # Base por frecuencia (más ancho en low-mids)
    if f < 250.0:
        q = 4.0
    elif f < 800.0:
        q = 6.0
    elif f < 4000.0:
        q = 8.0
    else:
        q = 9.0

    # Ajustes por instrumento
    if "vocal" in inst or "voice" in inst:
        q += 0.5
    if "bass" in inst or "kick" in inst:
        q -= 1.0
    if "guitar" in inst:
        q += 0.5

    # Clamp duro
    q = max(2.5, min(q, 10.0))
    return float(q)


def _choose_notch_from_res(
    res: Dict[str, Any],
    max_res_peak_db: float,
    max_cuts_db: float,
    instrument_profile: str,
) -> Dict[str, float] | None:
    """
    Decide notch (freq, cut, q) a partir de la resonancia más severa.
    Aplica:
      - cut parcial (no 100% del exceso) para evitar sobre-EQ
      - cap extra en 200–350 Hz
    """
    try:
        freq_hz = float(res.get("freq_hz", 0.0))
        gain_above = float(res.get("gain_above_local_db", 0.0))
    except (TypeError, ValueError):
        return None

    if freq_hz <= 0.0:
        return None

    excess = gain_above - float(max_res_peak_db)
    if excess <= 0.0:
        return None

    # Cut parcial: atacamos 70% del exceso, iterativo (puede repetir si hace falta)
    cut_db = 0.70 * excess

    # Cap contractual
    cut_db = min(float(max_cuts_db), float(cut_db))

    # Cap extra para low-mids (evitar adelgazar)
    if 200.0 <= freq_hz <= 350.0:
        cut_db = min(cut_db, 5.0)

    # Evitar micro-notches
    if cut_db < 0.8:
        return None

    q = _estimate_q(freq_hz, instrument_profile)

    return {"freq_hz": float(freq_hz), "cut_db": float(cut_db), "q": float(q), "gain_above_local_db": float(gain_above)}


def _apply_one_notch(audio: np.ndarray, sr: int, freq_hz: float, cut_db: float, q: float) -> np.ndarray:
    board = Pedalboard([PeakFilter(cutoff_frequency_hz=float(freq_hz), gain_db=-float(cut_db), q=float(q))])
    y = board(np.asarray(audio, dtype=np.float32), int(sr))
    return np.asarray(y, dtype=np.float32)


def _process_stem_iterative(
    stem_path: Path,
    instrument_profile: str,
    max_res_peak_db: float,
    max_cuts_db: float,
    max_filters_per_band: int,
    fmin: float,
    fmax: float,
    local_window_hz: float,
) -> Dict[str, Any]:
    """
    Aplica notches de forma iterativa:
      detectar -> aplicar 1 notch -> re-detectar -> ...
    y guarda métricas pre/post alineadas con el detector.
    """
    audio, sr = sf.read(stem_path, always_2d=True)
    audio = np.asarray(audio, dtype=np.float32)
    sr = int(sr)

    pre_res = _detect_on_audio(audio, sr, fmin, fmax, max_res_peak_db, local_window_hz, max_filters_per_band)
    pre_worst = _worst_gain(pre_res)

    applied: List[Dict[str, float]] = []

    # Evitar poner notches pegados
    used_freqs: List[float] = []

    y = audio
    for _ in range(int(max_filters_per_band)):
        cur_res = _detect_on_audio(y, sr, fmin, fmax, max_res_peak_db, local_window_hz, max_filters_per_band)
        if not cur_res:
            break

        # Elegimos la más severa (por gain_above_local_db)
        try:
            cur_res_sorted = sorted(cur_res, key=lambda r: float(r.get("gain_above_local_db", 0.0)), reverse=True)
        except Exception:
            cur_res_sorted = cur_res

        chosen = None
        for r in cur_res_sorted:
            notch = _choose_notch_from_res(r, max_res_peak_db, max_cuts_db, instrument_profile)
            if notch is None:
                continue

            f0 = float(notch["freq_hz"])
            min_spacing = max(25.0, f0 * 0.06)  # ~6% ó 25 Hz
            if any(abs(f0 - fu) < min_spacing for fu in used_freqs):
                continue

            chosen = notch
            break

        if chosen is None:
            break

        y = _apply_one_notch(y, sr, chosen["freq_hz"], chosen["cut_db"], chosen["q"])
        used_freqs.append(float(chosen["freq_hz"]))
        applied.append(chosen)

        # Early stop si ya bajamos lo suficiente (evita “seguir cortando por deporte”)
        post_res_tmp = _detect_on_audio(y, sr, fmin, fmax, max_res_peak_db, local_window_hz, max_filters_per_band)
        post_worst_tmp = _worst_gain(post_res_tmp)
        if post_worst_tmp <= max_res_peak_db + 1.0:
            break

    # Clamp suave y escritura FLOAT
    y = np.clip(y, -1.5, 1.5).astype(np.float32)
    sf.write(stem_path, y, sr, subtype="FLOAT")

    post_res = _detect_on_audio(y, sr, fmin, fmax, max_res_peak_db, local_window_hz, max_filters_per_band)
    post_worst = _worst_gain(post_res)

    return {
        "file_name": stem_path.name,
        "file_path": str(stem_path),
        "instrument_profile": instrument_profile,
        "samplerate_hz": sr,
        "pre": {"worst_resonance_db": float(pre_worst), "resonances": pre_res},
        "post": {"worst_resonance_db": float(post_worst), "resonances": post_res},
        "applied_notches": applied,
        "total_cut_db_sum": float(sum(float(n.get("cut_db", 0.0)) for n in applied)),
        "num_notches_applied": int(len(applied)),
    }


def _save_metrics(temp_dir: Path, contract_id: str, data: Dict[str, Any]) -> Path:
    p = temp_dir / "resonance_metrics_S4_STEM_RESONANCE_CONTROL.json"
    with p.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.logger.info(f"[S4_STEM_RESONANCE_CONTROL] Métricas guardadas en: {p}")
    return p


def main() -> None:
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S4_STEM_RESONANCE_CONTROL.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]
    analysis = load_analysis(contract_id)

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}
    stems: List[Dict[str, Any]] = analysis.get("stems", []) or []
    session: Dict[str, Any] = analysis.get("session", {}) or {}

    max_res_peak_db = float(metrics.get("max_resonance_peak_db_above_local", 12.0))
    max_cuts_db = float(limits.get("max_resonant_cuts_db", 8.0))
    max_filters_per_band = int(limits.get("max_resonant_filters_per_band", 3))

    fmin = float(session.get("res_band_fmin_hz", metrics.get("res_band_fmin_hz", 200.0)))
    fmax = float(session.get("res_band_fmax_hz", metrics.get("res_band_fmax_hz", 12000.0)))
    local_window_hz = float(session.get("res_local_window_hz", metrics.get("res_local_window_hz", 200.0)))

    temp_dir = get_temp_dir(contract_id, create=False)

    # Procesamos solo stems existentes y no full_song.wav
    stem_paths = []
    for s in stems:
        fp = s.get("file_path")
        if not fp:
            continue
        p = Path(fp)
        if p.name.lower() == "full_song.wav":
            continue
        if p.exists():
            stem_paths.append((p, s.get("instrument_profile", "Other")))

    if not stem_paths:
        logger.logger.info("[S4_STEM_RESONANCE_CONTROL] No hay stems válidos a procesar. No-op.")
        _save_metrics(temp_dir, contract_id, {"contract_id": contract_id, "stems": [], "summary": {"stems_processed": 0}})
        return

    per_stem: List[Dict[str, Any]] = []
    for p, inst in stem_paths:
        r = _process_stem_iterative(
            stem_path=p,
            instrument_profile=str(inst or "Other"),
            max_res_peak_db=max_res_peak_db,
            max_cuts_db=max_cuts_db,
            max_filters_per_band=max_filters_per_band,
            fmin=fmin,
            fmax=fmax,
            local_window_hz=local_window_hz,
        )
        per_stem.append(r)

        logger.logger.info(
            f"[S4_STEM_RESONANCE_CONTROL] {p.name}: notches={r['num_notches_applied']}, "
            f"worst_pre={r['pre']['worst_resonance_db']:.2f} dB, "
            f"worst_post={r['post']['worst_resonance_db']:.2f} dB."
        )

    worst_pre_global = max((float(s["pre"]["worst_resonance_db"]) for s in per_stem), default=0.0)
    worst_post_global = max((float(s["post"]["worst_resonance_db"]) for s in per_stem), default=0.0)

    metrics_out = {
        "contract_id": contract_id,
        "params": {
            "max_resonance_peak_db_above_local": max_res_peak_db,
            "max_resonant_cuts_db": max_cuts_db,
            "max_resonant_filters_per_band": max_filters_per_band,
            "fmin_hz": fmin,
            "fmax_hz": fmax,
            "local_window_hz": local_window_hz,
            "q_clamp": [2.5, 10.0],
            "lowmid_extra_cap_db": 5.0,
        },
        "summary": {
            "stems_processed": int(len(per_stem)),
            "worst_pre_db": float(worst_pre_global),
            "worst_post_db": float(worst_post_global),
            "improvement_db": float(worst_pre_global - worst_post_global),
        },
        "stems": per_stem,
    }

    _save_metrics(temp_dir, contract_id, metrics_out)

    logger.logger.info(
        f"[S4_STEM_RESONANCE_CONTROL] Stage completado. worst_pre={worst_pre_global:.2f} dB, "
        f"worst_post={worst_post_global:.2f} dB."
    )


if __name__ == "__main__":
    main()
