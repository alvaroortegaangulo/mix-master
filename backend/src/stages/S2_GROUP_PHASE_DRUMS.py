# C:\mix-master\backend\src\stages\S2_GROUP_PHASE_DRUMS.py

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import os  # noqa: E402

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from utils.analysis_utils import get_temp_dir  # noqa: E402
from utils.phase_utils import (  # noqa: E402
    apply_time_shift_samples,
    estimate_best_lag_and_corr,
)


def load_analysis(contract_id: str) -> Dict[str, Any]:
    """
    Carga el JSON de análisis generado por analysis\\S2_GROUP_PHASE_DRUMS.py.
    """
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def _normalize_audio(x: np.ndarray) -> np.ndarray:
    """Normaliza a pico 1.0 si es posible, sin modificar el array original."""
    if x.size == 0:
        return x
    peak = float(np.max(np.abs(x)))
    if peak > 0.0:
        return x / peak
    return x


# -------------------------------------------------------------------
# -------------------------------------------------------------------
def _process_stem_worker(
    args: Tuple[
        str,                 # temp_dir_str
        Dict[str, Any],      # stem_info
        float,               # min_shift_ms
        str,                 # reference_name
        float,               # max_time_shift_ms
        float,               # band_fmin
        float,               # band_fmax
        bool,                # allow_polarity_flip
    ]
) -> bool:
    """
    Worker que:
      - Vuelve a estimar lag/polaridad entre ref y stem usando estimate_best_lag_and_corr.
      - Prueba shift = +lag_samples y shift = -lag_samples.
      - Se queda con el que deja el lag residual más cercano a 0 ms.
      - Aplica shift + flip (si procede) al audio completo y sobrescribe el .wav.

    Devuelve True si el stem ha sido procesado, False en caso contrario.
    """
    (
        temp_dir_str,
        stem_info,
        min_shift_ms,
        reference_name,
        max_time_shift_ms,
        band_fmin,
        band_fmax,
        allow_polarity_flip,
    ) = args

    temp_dir = Path(temp_dir_str)

    if not stem_info.get("in_family", False):
        return False
    if stem_info.get("is_reference", False):
        return False

    file_name = stem_info.get("file_name")
    if not file_name:
        return False

    file_path = temp_dir / file_name
    ref_path = temp_dir / str(reference_name or "")

    if not ref_path.exists():
        print(
            f"[S2_GROUP_PHASE_DRUMS] Referencia {reference_name!r} no existe en {temp_dir}; "
            f"no se procesa {file_name}."
        )
        return False

    if not file_path.exists():
        print(
            f"[S2_GROUP_PHASE_DRUMS] Stem {file_name!r} no existe en {temp_dir}; se omite."
        )
        return False

    # ------------------------------------------------------------------
    # 1) Cargar referencia y candidato, convertir a mono y normalizar
    # ------------------------------------------------------------------
    try:
        ref_data, ref_sr = sf.read(ref_path, always_2d=False)
    except Exception as e:
        print(f"[S2_GROUP_PHASE_DRUMS] Error leyendo referencia {reference_name}: {e}")
        return False

    try:
        cand_data_full, cand_sr = sf.read(file_path, always_2d=False)
    except Exception as e:
        print(f"[S2_GROUP_PHASE_DRUMS] Error leyendo stem {file_name}: {e}")
        return False

    if isinstance(ref_data, np.ndarray) and ref_data.ndim > 1:
        ref_mono = np.mean(ref_data, axis=1).astype(np.float32)
    else:
        ref_mono = np.asarray(ref_data, dtype=np.float32)

    if isinstance(cand_data_full, np.ndarray) and cand_data_full.ndim > 1:
        cand_mono = np.mean(cand_data_full, axis=1).astype(np.float32)
    else:
        cand_mono = np.asarray(cand_data_full, dtype=np.float32)

    if ref_mono.size == 0 or cand_mono.size == 0:
        print(f"[S2_GROUP_PHASE_DRUMS] {file_name}: audio vacío; se omite.")
        return False

    # Usamos samplerate de la referencia (como en el análisis)
    sr = int(ref_sr)

    ref_norm = _normalize_audio(ref_mono)
    cand_norm = _normalize_audio(cand_mono)

    # ------------------------------------------------------------------
    # 2) Estimar lag inicial y posible flip (idéntico al análisis)
    # ------------------------------------------------------------------
    res_norm = estimate_best_lag_and_corr(
        ref=ref_norm,
        cand=cand_norm,
        sr=sr,
        max_time_shift_ms=max_time_shift_ms,
        fmin=band_fmin,
        fmax=band_fmax,
    )
    corr_norm = float(res_norm["correlation"])

    if allow_polarity_flip:
        res_flip = estimate_best_lag_and_corr(
            ref=ref_norm,
            cand=-cand_norm,
            sr=sr,
            max_time_shift_ms=max_time_shift_ms,
            fmin=band_fmin,
            fmax=band_fmax,
        )
        corr_flip = float(res_flip["correlation"])
    else:
        res_flip = None
        corr_flip = -999.0

    if corr_flip > corr_norm:
        base = res_flip
        use_flip = True
    else:
        base = res_norm
        use_flip = False

    base_lag_samples = float(base["lag_samples"])
    base_lag_ms = float(base["lag_ms"])

    # Si ya está casi alineado y no hay flip, no tocamos
    if abs(base_lag_ms) < min_shift_ms and not use_flip:
        return False

    # ------------------------------------------------------------------
    # 3) Probar shift = +lag_samples y shift = -lag_samples
    #    y quedarnos con el que deje menor lag residual.
    # ------------------------------------------------------------------
    candidates: List[Dict[str, Any]] = []
    data_orig = np.asarray(cand_data_full, dtype=np.float32)

    for sign in (+1, -1):
        shift_samples = sign * int(round(base_lag_samples))

        # Evitar repetir el caso shift=0 dos veces
        if shift_samples == 0 and sign == -1:
            continue

        # Aplicar shift al audio completo (todas las capas/canales)
        shifted = apply_time_shift_samples(data_orig, shift_samples)

        if use_flip:
            shifted = -shifted

        # Para medir residual, volvemos a mono + normalizamos
        if isinstance(shifted, np.ndarray) and shifted.ndim > 1:
            shifted_mono = np.mean(shifted, axis=1).astype(np.float32)
        else:
            shifted_mono = np.asarray(shifted, dtype=np.float32)

        shifted_norm = _normalize_audio(shifted_mono)

        res_resid = estimate_best_lag_and_corr(
            ref=ref_norm,
            cand=shifted_norm,
            sr=sr,
            max_time_shift_ms=max_time_shift_ms,
            fmin=band_fmin,
            fmax=band_fmax,
        )
        resid_lag_ms = float(res_resid["lag_ms"])

        candidates.append(
            {
                "shift_samples": shift_samples,
                "residual_lag_ms": resid_lag_ms,
                "audio": shifted,
            }
        )

    if not candidates:
        return False

    # Elegimos el candidato con |lag_residual| más pequeño
    best = min(candidates, key=lambda c: abs(c["residual_lag_ms"]))
    best_shift = int(best["shift_samples"])
    best_resid_ms = float(best["residual_lag_ms"])
    best_audio = np.asarray(best["audio"], dtype=np.float32)

    # ------------------------------------------------------------------
    # 4) Si la mejora es mínima y el lag residual ya es casi 0, podríamos
    #    omitir escribir, pero escribir es seguro e idempotente.
    # ------------------------------------------------------------------
    try:
        sf.write(file_path, best_audio, sr)
    except Exception as e:
        print(f"[S2_GROUP_PHASE_DRUMS] Error escribiendo {file_name}: {e}")
        return False

    print(
        f"[S2_GROUP_PHASE_DRUMS] {file_name}: lag_inicial={base_lag_ms:.3f} ms, "
        f"shift_aplicado={best_shift} samples, lag_residual≈{best_resid_ms:.3f} ms, "
        f"flip={use_flip}"
    )

    return True


def main() -> None:
    """
    Stage S2_GROUP_PHASE_DRUMS:
      - Lee analysis_S2_GROUP_PHASE_DRUMS.json.
      - Vuelve a estimar lag/polaridad respecto a la referencia usando estimate_best_lag_and_corr.
      - Aplica el shift (y flip si procede) que deje el lag residual más cercano a 0 ms.
      - Sobrescribe los archivos .wav correspondientes.
    """
    if len(sys.argv) < 2:
        print("Uso: python S2_GROUP_PHASE_DRUMS.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S2_GROUP_PHASE_DRUMS"

    analysis = load_analysis(contract_id)

    session: Dict[str, Any] = analysis.get("session", {}) or {}
    stems: List[Dict[str, Any]] = analysis.get("stems", []) or []

    # Parámetros desde el análisis
    max_time_shift_ms = float(session.get("max_time_shift_ms", 2.0))
    reference_name = session.get("reference_stem_name")
    band_fmin = float(session.get("band_fmin_hz", 100.0))
    band_fmax = float(session.get("band_fmax_hz", 500.0))
    allow_polarity_flip = bool(session.get("allow_polarity_flip", True))

    # Umbral mínimo para no mover si ya está prácticamente alineado
    MIN_SHIFT_MS = 0.1

    temp_dir = get_temp_dir(contract_id, create=False)

    if not reference_name:
        print(
            "[S2_GROUP_PHASE_DRUMS] reference_stem_name no definido en session; "
            "stage actúa como no-op."
        )
        return

    # Stems candidatos: familia Drums y no referencia
    candidate_stems: List[Dict[str, Any]] = [
        s
        for s in stems
        if s.get("in_family", False) and not s.get("is_reference", False)
    ]

    if not candidate_stems:
        print(
            f"[S2_GROUP_PHASE_DRUMS] No hay stems de familia Drums (o solo referencia); "
            f"Stage completado sin cambios."
        )
        return

    processed = 0
    args_list: List[
        Tuple[str, Dict[str, Any], float, str, float, float, float, bool]
    ] = [
        (
            str(temp_dir),
            stem_info,
            MIN_SHIFT_MS,
            str(reference_name),
            max_time_shift_ms,
            band_fmin,
            band_fmax,
            allow_polarity_flip,
        )
        for stem_info in candidate_stems
    ]

    results: List[bool] = []
    for args in args_list:
        results.append(_process_stem_worker(args))

    processed = sum(1 for r in results if r)

    print(
        f"[S2_GROUP_PHASE_DRUMS] Stage completado. "
        f"Referencia={reference_name}, stems procesados={processed}."
    )


if __name__ == "__main__":
    main()
