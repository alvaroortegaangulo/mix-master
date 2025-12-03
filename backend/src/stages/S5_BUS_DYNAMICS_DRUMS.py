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
    """
    Carga el JSON de análisis generado por analysis\\S5_BUS_DYNAMICS_DRUMS.py.
    """
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

    # Lógica similar a S5_STEM_DYNAMICS_GENERIC / leadvox
    inv_ratio = 1.0 / float(max(ratio, 1.0))
    k = 1.0 - inv_ratio
    if k <= 0.0:
        return None

    # Dejamos que la GR máxima teórica sea algo superior a la media objetivo
    max_peak_gr_db = max_avg_gr_db + 1.0
    over_max_target = max_peak_gr_db / k
    threshold_from_peak = pre_peak_db - over_max_target

    # Umbral mínimo: RMS + 2 dB para no aplastar demasiado
    if pre_rms_db != float("-inf"):
        min_threshold = pre_rms_db + 2.0
        threshold_db = max(threshold_from_peak, min_threshold)
    else:
        threshold_db = threshold_from_peak

    return float(threshold_db)


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------

def _load_drum_stem_worker(args: Tuple[str, str]) -> Tuple[str, str, np.ndarray | None, int | None, str | None]:
    """
    Lee un stem de Drums desde disco y lo devuelve como matriz (N, C) float32.

    args:
      - fname: nombre de archivo
      - path_str: ruta completa al wav

    return:
      (fname, path_str, data_2d_or_none, sr_or_none, error_msg_or_none)
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

        return fname, path_str, data, sr, None
    except Exception as e:
        return fname, path_str, None, None, str(e)


def main() -> None:
    """
    Stage S5_BUS_DYNAMICS_DRUMS:

      - Lee analysis_S5_BUS_DYNAMICS_DRUMS.json.
      - Agrupa stems de familia 'Drums' como un bus multicanal.
      - Calcula crest factor pre del bus.
      - Si el crest es mayor que el target, aplica compresión de glue
        (misma envolvente para todas las pistas del bus).
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
    RELEASE_MS = 150.0
    MAKEUP_DB = 0.0  # sin maquillaje en este stage

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
        files_info.append(
            {
                "file_name": fname,
                "path": Path(path_str),
                "channels": c,
                "length": n,
            }
        )
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
        # Aún así guardamos métricas “sin compresión”
        post_rms_db, post_peak_db, post_crest_db = pre_rms_db, pre_peak_db, pre_crest_db
        avg_gr_db = 0.0
        max_gr_db = 0.0
    else:
        # 7) Aplicar compresión al bus multicanal (misma envolvente para todas las pistas)
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
            logger.logger.info(
                f"[S5_BUS_DYNAMICS_DRUMS] {fname}: reescrito con compresión de bus aplicada."
            )

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
