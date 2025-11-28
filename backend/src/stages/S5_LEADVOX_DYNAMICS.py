# C:\mix-master\backend\src\stages\S5_LEADVOX_DYNAMICS.py

from __future__ import annotations

import sys
import os
from concurrent.futures import ProcessPoolExecutor
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
    """
    Carga el JSON de análisis generado por analysis\\S5_LEADVOX_DYNAMICS.py.
    """
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
          * Usamos fórmula similar a S5_STEM_DYNAMICS_GENERIC para garantizar
            un techo de GR razonable, pero sin intentar clavar crest exacto.

    Si devuelve None, el stage no aplicará compresión a ese stem.
    """
    MARGIN_DB = 0.5

    if crest_db == float("inf") or crest_db != crest_db:  # NaN
        return None

    if crest_db <= crest_max_target + MARGIN_DB:
        return None

    # Misma idea que en genérico: limitar reducción máxima teórica
    inv_ratio = 1.0 / float(max(ratio, 1.0))
    k = 1.0 - inv_ratio  # factor de GR

    if k <= 0.0:
        return None

    # Permitimos que la GR máxima teórica sea algo mayor que la media objetivo
    max_peak_gr_db = max_avg_gr_db + 2.0
    over_max_target = max_peak_gr_db / k
    threshold_from_peak = pre_peak_db - over_max_target

    # Umbral mínimo: RMS + 2 dB (solo cazar picos)
    if pre_rms_db != float("-inf"):
        min_threshold = pre_rms_db + 2.0
        threshold_db = max(threshold_from_peak, min_threshold)
    else:
        threshold_db = threshold_from_peak

    return float(threshold_db)


# ----------------------------------------------------------------------
# Worker para ProcessPoolExecutor: comprime y reescribe un stem de lead
# ----------------------------------------------------------------------

def _compress_lead_stem_worker(
    args: Tuple[
        str,          # fname
        str,          # path_str
        float,        # threshold_db
        float,        # pre_rms_db
        float,        # pre_peak_db
        float,        # pre_crest_db
        float,        # RATIO
        float,        # ATTACK_MS
        float,        # RELEASE_MS
        float,        # MAKEUP_DB
    ]
) -> Optional[Dict[str, Any]]:
    """
    Worker que:
      - Lee el archivo de audio.
      - Aplica compresión peak detector.
      - Reescribe el archivo.
      - Devuelve métricas post-compresión para el registro.

    Si hay error o el archivo está vacío, devuelve None.
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
        print(f"[S5_LEADVOX_DYNAMICS] {fname}: error al leer el archivo: {e}")
        return None

    if not isinstance(data, np.ndarray):
        data = np.array(data, dtype=np.float32)
    else:
        data = data.astype(np.float32)

    if data.size == 0:
        print(f"[S5_LEADVOX_DYNAMICS] {fname}: archivo vacío; se omite.")
        return None

    # Aplicar compresor
    y_out, avg_gr_db, max_gr_db = compress_peak_detector(
        data,
        sr,
        threshold_db=threshold_db,
        ratio=RATIO,
        attack_ms=ATTACK_MS,
        release_ms=RELEASE_MS,
        makeup_gain_db=MAKEUP_DB,
    )

    post_rms_db, post_peak_db, post_crest_db = compute_crest_factor_db(y_out)

    # Guardar audio
    sf.write(path, y_out, sr)

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
      - Si el crest factor es mayor que el target, aplica compresión moderada
        para recortar picos sin matar demasiado la vida.
      - Guarda métricas de GR y crest factor antes/después.
      - Usa ProcessPoolExecutor para procesar en paralelo los stems de lead.
    """
    if len(sys.argv) < 2:
        print("Uso: python S5_LEADVOX_DYNAMICS.py <CONTRACT_ID>")
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

    # Parámetros de compresión típicos de voz
    RATIO = 3.0
    ATTACK_MS = 5.0
    RELEASE_MS = 100.0
    MAKEUP_DB = 0.0  # de momento no hacemos maquillaje (automatización global = 0 dB)

    temp_dir = get_temp_dir(contract_id, create=False)

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
            print(
                f"[S5_LEADVOX_DYNAMICS] {fname}: métricas previas inválidas; "
                f"se omite compresión."
            )
            continue

        # Si la pista es muy baja, no tiene sentido comprimir
        if pre_peak_db <= -60.0:
            print(
                f"[S5_LEADVOX_DYNAMICS] {fname}: nivel muy bajo (peak={pre_peak_db:.1f} dBFS); "
                f"no se aplica compresión."
            )
            continue

        # Si el crest ya está dentro de rango razonable, no tocamos
        if crest_min <= pre_crest_db <= crest_max:
            print(
                f"[S5_LEADVOX_DYNAMICS] {fname}: crest={pre_crest_db:.2f} dB ya en rango "
                f"[{crest_min:.1f}, {crest_max:.1f}] dB; no se aplica compresión."
            )
            continue

        # Si el crest es bajo (< min), no hacemos expansión
        if pre_crest_db < crest_min:
            print(
                f"[S5_LEADVOX_DYNAMICS] {fname}: crest={pre_crest_db:.2f} dB < min "
                f"{crest_min:.1f} dB; no se comprime (no expansión)."
            )
            continue

        # Si crest > max: intentamos recortar picos
        threshold_db = _compute_vocal_threshold(
            pre_rms_db=pre_rms_db,
            pre_peak_db=pre_peak_db,
            crest_db=pre_crest_db,
            crest_max_target=crest_max,
            max_avg_gr_db=max_avg_gr,
            ratio=RATIO,
        )

        if threshold_db is None:
            print(
                f"[S5_LEADVOX_DYNAMICS] {fname}: no se determina umbral de compresión; "
                f"no se aplica compresión."
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
    # 2) Ejecutar compresión en paralelo
    # ------------------------------------------------------------------
    metrics_records: List[Dict[str, Any]] = []
    processed = 0

    if tasks:
        max_workers = min(4, os.cpu_count() or 1)
        with ProcessPoolExecutor(max_workers=max_workers) as ex:
            for result in ex.map(_compress_lead_stem_worker, tasks):
                if result is None:
                    continue

                fname = result["file_name"]
                threshold_db = result["threshold_db"]
                avg_gr_db = result["avg_gain_reduction_db"]
                max_gr_db = result["max_gain_reduction_db"]
                pre_crest_db = result["pre_crest_db"]
                post_crest_db = result["post_crest_db"]

                print(
                    f"[S5_LEADVOX_DYNAMICS] {fname}: threshold={threshold_db:.2f} dBFS, "
                    f"avg_GR={avg_gr_db:.2f} dB, max_GR={max_gr_db:.2f} dB, "
                    f"crest_pre={pre_crest_db:.2f} dB, crest_post={post_crest_db:.2f} dB."
                )

                # Añadir a métricas (sin modificar estructura original)
                record = dict(result)
                # Añadimos también el límite de automatización para mantener info de contrato
                record["max_vocal_automation_change_db_per_pass"] = max_auto_change
                metrics_records.append(record)
                processed += 1
    else:
        print(
            "[S5_LEADVOX_DYNAMICS] No hay stems de lead que requieran compresión "
            "(o no hay stems válidos)."
        )

    # ------------------------------------------------------------------
    # 3) Guardar métricas de dinámica para el futuro check
    # ------------------------------------------------------------------
    temp_dir = get_temp_dir(contract_id, create=False)
    metrics_path = temp_dir / "leadvox_dynamics_metrics_S5_LEADVOX_DYNAMICS.json"
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "contract_id": contract_id,
                "target_crest_factor_min_db": crest_min,
                "target_crest_factor_max_db": crest_max,
                "max_average_gain_reduction_db": max_avg_gr,
                "max_vocal_automation_change_db_per_pass": max_auto_change,
                "records": metrics_records,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(
        f"[S5_LEADVOX_DYNAMICS] Stage completado. Stems lead procesados={processed}. "
        f"Métricas guardadas en: {metrics_path}"
    )


if __name__ == "__main__":
    main()
