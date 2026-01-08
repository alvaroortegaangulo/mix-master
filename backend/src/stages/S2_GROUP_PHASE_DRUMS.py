#C:\mix-master\backend\src\stages\S2_GROUP_PHASE_DRUMS.py

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

from utils.analysis_utils import get_temp_dir
from utils.phase_utils import apply_time_shift_samples  # noqa: E402


def load_analysis(contract_id: str) -> Dict[str, Any]:
    """
    Carga el JSON de análisis generado por analysis\\S2_GROUP_PHASE_DRUMS.py.
    """
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        return json.load(f)


# -------------------------------------------------------------------
# Interpolación para retardo variable (Lagrange 4 puntos, vectorizada)
# -------------------------------------------------------------------

def _interp_lagrange4_1d(y: np.ndarray, t: np.ndarray) -> np.ndarray:
    """
    Interpola y(t) para t real (float) usando Lagrange 4 puntos (cúbico),
    vectorizado. Fuera de rango -> 0.
    """
    y = np.asarray(y, dtype=np.float32)
    t = np.asarray(t, dtype=np.float32)

    n = y.shape[0]
    out = np.zeros_like(t, dtype=np.float32)

    if n < 4 or t.size == 0:
        return out

    i = np.floor(t).astype(np.int64)
    f = (t - i.astype(np.float32)).astype(np.float32)

    # válidos donde tenemos i-1, i, i+1, i+2
    valid = (i >= 1) & (i < n - 2) & np.isfinite(t)
    if not np.any(valid):
        return out

    iv = i[valid]
    fv = f[valid]

    y0 = y[iv - 1]
    y1 = y[iv]
    y2 = y[iv + 1]
    y3 = y[iv + 2]

    # Coefs Lagrange 4-tap
    # p(f) = y0 * (-f*(f-1)*(f-2)/6)
    #      + y1 * ((f+1)*(f-1)*(f-2)/2)
    #      + y2 * (-(f+1)*f*(f-2)/2)
    #      + y3 * ((f+1)*f*(f-1)/6)
    f0 = fv
    c0 = (-f0 * (f0 - 1.0) * (f0 - 2.0)) / 6.0
    c1 = ((f0 + 1.0) * (f0 - 1.0) * (f0 - 2.0)) / 2.0
    c2 = (-(f0 + 1.0) * f0 * (f0 - 2.0)) / 2.0
    c3 = ((f0 + 1.0) * f0 * (f0 - 1.0)) / 6.0

    out_valid = (y0 * c0 + y1 * c1 + y2 * c2 + y3 * c3).astype(np.float32)
    out[valid] = out_valid
    return out


def _apply_time_varying_shift(
    data: np.ndarray,
    anchor_samples: np.ndarray,
    anchor_shifts: np.ndarray,
    chunk_size: int = 262144,
) -> np.ndarray:
    """
    Aplica un shift variable en el tiempo:
        y_out[n] = y_in[n - shift(n)]
    donde shift(n) se interpola linealmente entre anclajes.

    data: (N,) o (N,C)
    anchor_samples: posiciones (en samples) donde se define shift
    anchor_shifts: shift en samples (float), mismo tamaño que anchor_samples
    """
    x = np.asarray(data, dtype=np.float32)
    if x.size == 0:
        return x

    if x.ndim == 1:
        x2 = x.reshape(-1, 1)
        mono = True
    else:
        x2 = x
        mono = False

    N = x2.shape[0]
    C = x2.shape[1]

    a_s = np.asarray(anchor_samples, dtype=np.float32)
    a_sh = np.asarray(anchor_shifts, dtype=np.float32)

    # Sanear / ordenar anclajes
    ok = np.isfinite(a_s) & np.isfinite(a_sh)
    a_s = a_s[ok]
    a_sh = a_sh[ok]

    if a_s.size < 2:
        return x.copy()

    order = np.argsort(a_s)
    a_s = a_s[order]
    a_sh = a_sh[order]

    # Extender a bordes para evitar extrapolación rara
    if a_s[0] > 0:
        a_s = np.concatenate([np.array([0.0], dtype=np.float32), a_s])
        a_sh = np.concatenate([np.array([a_sh[0]], dtype=np.float32), a_sh])
    if a_s[-1] < (N - 1):
        a_s = np.concatenate([a_s, np.array([float(N - 1)], dtype=np.float32)])
        a_sh = np.concatenate([a_sh, np.array([a_sh[-1]], dtype=np.float32)])

    y_out = np.zeros_like(x2, dtype=np.float32)

    for start in range(0, N, chunk_size):
        end = min(N, start + chunk_size)
        idx = np.arange(start, end, dtype=np.float32)

        # shift(n) interpolado linealmente entre anclajes
        shift = np.interp(idx, a_s, a_sh).astype(np.float32)

        # índice de lectura en el original
        t = idx - shift  # y_out[n] = y_in[n - shift(n)]

        # Interpolar por canal con Lagrange 4-puntos
        for ch in range(C):
            y_out[start:end, ch] = _interp_lagrange4_1d(x2[:, ch], t)

    if mono:
        return y_out[:, 0].astype(np.float32)
    return y_out.astype(np.float32)


# -------------------------------------------------------------------
# Worker
# -------------------------------------------------------------------

def _process_stem_worker(
    args: Tuple[str, Dict[str, Any], float, float, bool]
) -> bool:
    """
    Aplica alineación de fase/tiempo y posible flip de polaridad a un stem.

    - Si hay deriva recomendada, usa alineación time-varying (retardo variable).
    - Si no, cae a shift estático como antes.
    """
    temp_dir_str, stem_info, min_shift_ms, correlation_min, enable_time_varying = args
    temp_dir = Path(temp_dir_str)

    if not stem_info.get("in_family", False):
        return False
    if stem_info.get("is_reference", False):
        return False

    file_name = stem_info.get("file_name")
    if not file_name:
        return False

    file_path = temp_dir / file_name
    if not file_path.exists():
        return False

    use_flip = bool(stem_info.get("use_polarity_flip", False))

    # Leer audio
    data, sr = sf.read(file_path, always_2d=False)
    data = np.asarray(data, dtype=np.float32)
    if data.size == 0 or sr <= 0:
        return False

    # -----------------------------
    # Decisión: time-varying vs fijo
    # -----------------------------
    lag_curve = stem_info.get("lag_curve", []) or []
    time_varying_reco = bool(stem_info.get("time_varying_recommended", False))
    drift = stem_info.get("drift", {}) or {}
    drift_range_ms = float(drift.get("drift_range_ms", 0.0) or 0.0)
    valid_points = int(drift.get("valid_points", 0) or 0)

    processed_mode = "static"
    y_out: Optional[np.ndarray] = None

    if enable_time_varying and time_varying_reco and valid_points >= 2 and isinstance(lag_curve, list):
        # Filtrar puntos válidos por correlación (defensivo)
        pts = []
        for p in lag_curve:
            try:
                if not p.get("valid", False):
                    continue
                corr = float(p.get("correlation", float("-inf")))
                if not np.isfinite(corr) or corr < correlation_min:
                    continue
                a_s = int(p.get("anchor_sample", 0))
                lag_s = float(p.get("lag_samples", 0.0))
                pts.append((a_s, lag_s, corr))
            except Exception:
                continue

        if len(pts) >= 2:
            pts.sort(key=lambda x: x[0])
            anchor_samples = np.array([p[0] for p in pts], dtype=np.float32)

            # Convención: lag > 0 => candidato retrasado => para corregir shift = -lag
            anchor_shifts = np.array([-p[1] for p in pts], dtype=np.float32)

            # Si el shift es microscópico, no merece la pena
            max_abs_shift_ms = float(np.max(np.abs(anchor_shifts))) * 1000.0 / float(sr)
            if max_abs_shift_ms >= float(min_shift_ms):
                y_out = _apply_time_varying_shift(
                    data=data,
                    anchor_samples=anchor_samples,
                    anchor_shifts=anchor_shifts,
                    chunk_size=262144,
                )
                processed_mode = "time_varying"
            else:
                y_out = None

    if y_out is None:
        # Fallback: tu comportamiento actual (shift global)
        lag_samples = stem_info.get("lag_samples", 0.0)
        lag_ms = stem_info.get("lag_ms", 0.0)

        try:
            lag_ms = float(lag_ms)
            lag_samples = float(lag_samples)
        except (TypeError, ValueError):
            return False

        if abs(lag_ms) < min_shift_ms and not use_flip:
            return False

        shift_samples = -int(round(lag_samples))
        y_out = apply_time_shift_samples(data, shift_samples)
        processed_mode = "static"

    # Flip de polaridad si procede (una sola vez)
    if use_flip:
        y_out = -np.asarray(y_out, dtype=np.float32)

    sf.write(file_path, y_out, sr)

    if processed_mode == "time_varying":
        logger.logger.info(
            f"[S2_GROUP_PHASE_DRUMS] {file_name}: modo=time_varying, "
            f"drift_range≈{drift_range_ms:.3f} ms, "
            f"flip={use_flip}"
        )
    else:
        # log del shift estático
        lag_ms = float(stem_info.get("lag_ms", 0.0) or 0.0)
        lag_samples = float(stem_info.get("lag_samples", 0.0) or 0.0)
        shift_samples = -int(round(lag_samples))
        logger.logger.info(
            f"[S2_GROUP_PHASE_DRUMS] {file_name}: modo=static, "
            f"lag_inicial={lag_ms:.3f} ms, "
            f"shift_aplicado={shift_samples} samples, "
            f"flip={use_flip}"
        )

    return True


def main() -> None:
    """
    Stage S2_GROUP_PHASE_DRUMS:
      - Lee analysis_S2_GROUP_PHASE_DRUMS.json.
      - Aplica alineación de fase/tiempo y posible flip de polaridad
        a los stems de familia Drums (excepto la referencia).
      - Si hay deriva: alineación time-varying (recomendada por el análisis).
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S2_GROUP_PHASE_DRUMS.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]

    analysis = load_analysis(contract_id)

    session: Dict[str, Any] = analysis.get("session", {}) or {}
    stems: List[Dict[str, Any]] = analysis.get("stems", []) or []

    reference_name = session.get("reference_stem_name")

    correlation_min = float(session.get("correlation_min", 0.0))
    enable_time_varying = bool(session.get("enable_time_varying_alignment", True))

    # Umbral mínimo en ms para no mover si ya está prácticamente alineado
    MIN_SHIFT_MS = 0.1

    temp_dir = get_temp_dir(contract_id, create=False)

    candidate_stems: List[Dict[str, Any]] = [
        s
        for s in stems
        if s.get("in_family", False) and not s.get("is_reference", False)
    ]

    processed = 0
    if candidate_stems:
        args_list: List[Tuple[str, Dict[str, Any], float, float, bool]] = [
            (str(temp_dir), stem_info, MIN_SHIFT_MS, correlation_min, enable_time_varying)
            for stem_info in candidate_stems
        ]

        for args in args_list:
            if _process_stem_worker(args):
                processed += 1

    logger.logger.info(
        f"[S2_GROUP_PHASE_DRUMS] Stage completado. "
        f"Referencia={reference_name}, stems procesados={processed}, "
        f"time_varying={'ON' if enable_time_varying else 'OFF'}."
    )


if __name__ == "__main__":
    main()
