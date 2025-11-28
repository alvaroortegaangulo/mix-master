# C:\mix-master\backend\src\stages\S5_STEM_DYNAMICS_GENERIC.py

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

from utils.analysis_utils import PROJECT_ROOT  # noqa: E402
from utils.dynamics_utils import (  # noqa: E402
    compress_peak_detector,
    compute_crest_factor_db,
)


def load_analysis(contract_id: str) -> Dict[str, Any]:
    """
    Carga el JSON de análisis generado por analysis\\S5_STEM_DYNAMICS_GENERIC.py.
    """
    temp_dir = PROJECT_ROOT / "temp" / contract_id
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def _compute_threshold_for_stem(
    pre_rms_db: float,
    pre_peak_db: float,
    max_peak_gr_db: float,
    ratio: float,
) -> float:
    """
    Calcula un umbral de compresión para garantizar que la reducción máxima
    no supere aproximadamente max_peak_gr_db, con ratio dado.

    GR_max ≈ (peak_db - threshold_db) * (1 - 1/ratio)

    => threshold_db ≈ peak_db - GR_max / (1 - 1/ratio)

    Además, se fuerza a que no baje por debajo de (pre_rms_db + 2 dB)
    para evitar sobrecomprimir de forma generalizada.
    """
    inv_ratio = 1.0 / float(max(ratio, 1.0))
    k = 1.0 - inv_ratio  # factor para GR

    if k <= 0.0:
        return pre_peak_db  # sin compresión

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
# Worker para ProcessPoolExecutor: comprime y reescribe un stem
# ----------------------------------------------------------------------

def _compress_stem_worker(
    args: Tuple[
        str,   # fname
        str,   # path_str
        float, # threshold_db
        float, # pre_rms_db
        float, # pre_peak_db
        float, # pre_crest_db
        float, # RATIO
        float, # ATTACK_MS
        float, # RELEASE_MS
        float, # MAKEUP_DB
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
        print(f"[S5_STEM_DYNAMICS_GENERIC] {fname}: error al leer el archivo: {e}")
        return None

    if not isinstance(data, np.ndarray):
        data = np.array(data, dtype=np.float32)
    else:
        data = data.astype(np.float32)

    if data.size == 0:
        print(f"[S5_STEM_DYNAMICS_GENERIC] {fname}: archivo vacío; se omite.")
        return None

    # Aplicar compresión
    y_out, avg_gr_db, max_gr_db = compress_peak_detector(
        data,
        sr,
        threshold_db=threshold_db,
        ratio=RATIO,
        attack_ms=ATTACK_MS,
        release_ms=RELEASE_MS,
        makeup_gain_db=MAKEUP_DB,
    )

    # Métricas post-compresión (crest factor nuevo)
    post_rms_db, post_peak_db, post_crest_db = compute_crest_factor_db(y_out)

    # Guardar audio procesado
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
    }


def main() -> None:
    """
    Stage S5_STEM_DYNAMICS_GENERIC:

      - Lee analysis_S5_STEM_DYNAMICS_GENERIC.json.
      - Para cada stem:
          * Calcula un umbral de compresión en función de RMS/peak.
          * Aplica un compresor genérico (ratio moderado).
          * Registra métricas de GR y crest factor antes/después.
      - Usa ProcessPoolExecutor para procesar los stems en paralelo.
    """
    if len(sys.argv) < 2:
        print("Uso: python S5_STEM_DYNAMICS_GENERIC.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S5_STEM_DYNAMICS_GENERIC"

    analysis = load_analysis(contract_id)

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}
    stems: List[Dict[str, Any]] = analysis.get("stems", []) or []

    max_avg_gr = float(metrics.get("max_average_gain_reduction_db", 4.0))
    max_peak_gr = float(metrics.get("max_peak_gain_reduction_db", 6.0))

    max_attack_ms = float(limits.get("max_attack_ms", 50.0))
    min_attack_ms = float(limits.get("min_attack_ms", 1.0))
    max_release_ms = float(limits.get("max_release_ms", 600.0))
    min_release_ms = float(limits.get("min_release_ms", 20.0))

    # Parámetros globales razonables (ajustables por estilo más adelante)
    RATIO = 4.0
    ATTACK_MS = 10.0
    RELEASE_MS = 120.0
    MAKEUP_DB = 0.0  # en este stage NO compensamos, solo control de rango

    # Clamping a los límites del contrato
    ATTACK_MS = min(max(ATTACK_MS, min_attack_ms), max_attack_ms)
    RELEASE_MS = min(max(RELEASE_MS, min_release_ms), max_release_ms)

    temp_dir = PROJECT_ROOT / "temp" / contract_id

    # ------------------------------------------------------------------
    # 1) Preparar tareas para ProcessPoolExecutor
    # ------------------------------------------------------------------
    tasks: List[Tuple[str, str, float, float, float, float, float, float, float, float]] = []

    for stem in stems:
        fname = stem.get("file_name")
        if not fname:
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
                f"[S5_STEM_DYNAMICS_GENERIC] {fname}: métricas previas inválidas; "
                f"se omite compresión."
            )
            continue

        # Si la pista es muy baja de nivel, no hacemos nada
        if pre_peak_db <= -60.0:
            continue

        threshold_db = _compute_threshold_for_stem(
            pre_rms_db=pre_rms_db,
            pre_peak_db=pre_peak_db,
            max_peak_gr_db=max_peak_gr,
            ratio=RATIO,
        )

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

    stems_processed = 0
    metrics_records: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # 2) Ejecutar compresión en paralelo
    # ------------------------------------------------------------------
    if tasks:
        max_workers = min(4, os.cpu_count() or 1)
        with ProcessPoolExecutor(max_workers=max_workers) as ex:
            for result in ex.map(_compress_stem_worker, tasks):
                if result is None:
                    continue

                fname = result["file_name"]
                threshold_db = result["threshold_db"]
                avg_gr_db = result["avg_gain_reduction_db"]
                max_gr_db = result["max_gain_reduction_db"]
                pre_crest_db = result["pre_crest_db"]
                post_crest_db = result["post_crest_db"]

                print(
                    f"[S5_STEM_DYNAMICS_GENERIC] {fname}: threshold={threshold_db:.2f} dBFS, "
                    f"avg_GR={avg_gr_db:.2f} dB, max_GR={max_gr_db:.2f} dB, "
                    f"crest_pre={pre_crest_db:.2f} dB, crest_post={post_crest_db:.2f} dB."
                )

                metrics_records.append(result)
                stems_processed += 1
    else:
        print(
            "[S5_STEM_DYNAMICS_GENERIC] No hay stems válidos que requieran compresión."
        )

    # ------------------------------------------------------------------
    # 3) Guardar métricas de dinámica en un JSON auxiliar para el check
    # ------------------------------------------------------------------
    metrics_path = temp_dir / "dynamics_metrics_S5_STEM_DYNAMICS_GENERIC.json"
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "contract_id": contract_id,
                "max_average_gain_reduction_db": max_avg_gr,
                "max_peak_gain_reduction_db": max_peak_gr,
                "records": metrics_records,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(
        f"[S5_STEM_DYNAMICS_GENERIC] Stage completado. Stems procesados={stems_processed}. "
        f"Métricas guardadas en: {metrics_path}"
    )


if __name__ == "__main__":
    main()
