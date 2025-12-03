# C:\mix-master\backend\src\stages\S5_STEM_DYNAMICS_GENERIC.py

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from stages.pipeline_context import PipelineContext

import json  # noqa: E402
import numpy as np  # noqa: E402

from utils.analysis_utils import get_temp_dir  # noqa: E402
from utils.dynamics_utils import compute_crest_factor_db  # noqa: E402

from pedalboard import Pedalboard, Compressor  # noqa: E402
from pedalboard.io import AudioFile  # noqa: E402


def load_analysis(contract_id: str) -> Dict[str, Any]:
    temp_dir = get_temp_dir(contract_id, create=False)
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
    inv_ratio = 1.0 / float(max(ratio, 1.0))
    k = 1.0 - inv_ratio

    if k <= 0.0:
        return pre_peak_db

    over_max_target = max_peak_gr_db / k
    threshold_from_peak = pre_peak_db - over_max_target

    if pre_rms_db != float("-inf"):
        min_threshold = pre_rms_db + 2.0
        threshold_db = max(threshold_from_peak, min_threshold)
    else:
        threshold_db = threshold_from_peak

    return float(threshold_db)


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
        float, # MAKEUP_DB (no se usa en Pedalboard, se mantiene por compatibilidad)
    ]
) -> Optional[Dict[str, Any]]:
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
        MAKEUP_DB,  # no lo usamos, en este stage ya era 0.0
    ) = args

    path = Path(path_str)

    try:
        with AudioFile(str(path)) as f:
            audio = f.read(f.frames)
            samplerate = f.samplerate
    except Exception as e:
        print(f"[S5_STEM_DYNAMICS_GENERIC] {fname}: error al leer el archivo: {e}")
        return None

    if not isinstance(audio, np.ndarray):
        audio = np.array(audio, dtype=np.float32)
    else:
        audio = audio.astype(np.float32)

    if audio.size == 0:
        print(f"[S5_STEM_DYNAMICS_GENERIC] {fname}: archivo vacío; se omite.")
        return None

    # Normalizar forma para el compresor
    if audio.ndim == 1:
        audio_for_board = audio.reshape(1, -1)  # (1, samples)
        data_in = audio.copy()                  # (samples,)
    elif audio.ndim == 2:
        audio_for_board = audio                 # (channels, samples)
        data_in = audio.T.copy()                # (samples, channels)
    else:
        print(
            f"[S5_STEM_DYNAMICS_GENERIC] {fname}: formato de audio no soportado "
            f"con ndim={audio.ndim}; se omite."
        )
        return None

    # Compresor Pedalboard (sin makeup_gain_db: en este stage ya era 0.0)
    board = Pedalboard(
        [
            Compressor(
                threshold_db=float(threshold_db),
                ratio=float(RATIO),
                attack_ms=float(ATTACK_MS),
                release_ms=float(RELEASE_MS),
            )
        ]
    )

    try:
        processed = board(audio_for_board, samplerate)
    except Exception as e:
        print(f"[S5_STEM_DYNAMICS_GENERIC] {fname}: error en compresor: {e}")
        return None

    if not isinstance(processed, np.ndarray):
        processed = np.array(processed, dtype=np.float32)
    else:
        processed = processed.astype(np.float32)

    if processed.ndim == 1:
        data_out = processed.copy()
    elif processed.ndim == 2:
        data_out = processed.T.copy()
    else:
        print(
            f"[S5_STEM_DYNAMICS_GENERIC] {fname}: salida del compresor no soportada "
            f"con ndim={processed.ndim}; se omite."
        )
        return None

    # Ganancia de reducción media y máxima (en función de |in| vs |out|)
    eps = 1e-12

    if audio_for_board.ndim == 1:
        in_cs = audio_for_board.reshape(1, -1)
    else:
        in_cs = audio_for_board

    if processed.ndim == 1:
        out_cs = processed.reshape(1, -1)
    else:
        out_cs = processed

    in_abs = np.abs(in_cs).astype(np.float32) + eps
    out_abs = np.abs(out_cs).astype(np.float32) + eps

    gr_db = 20.0 * np.log10(out_abs / in_abs)
    gr_db_clipped = np.minimum(gr_db, 0.0)  # solo reducción

    avg_gr_db = float(-np.mean(gr_db_clipped))
    max_gr_db = float(-np.min(gr_db_clipped))

    # Métricas post-compresión
    post_rms_db, post_peak_db, post_crest_db = compute_crest_factor_db(data_out)

    # Guardar audio procesado
    with AudioFile(
        str(path),
        "w",
        samplerate=samplerate,
        num_channels=out_cs.shape[0],
    ) as f:
        f.write(processed)

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


def process(context: PipelineContext) -> None:

    contract_id = context.contract_id

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

    RATIO = 4.0
    ATTACK_MS = 10.0
    RELEASE_MS = 120.0
    MAKEUP_DB = 0.0  # mantenemos por si en el futuro quieres usarlo

    ATTACK_MS = min(max(ATTACK_MS, min_attack_ms), max_attack_ms)
    RELEASE_MS = min(max(RELEASE_MS, min_release_ms), max_release_ms)

    temp_dir = get_temp_dir(contract_id, create=False)

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

    if tasks:
        for result in map(_compress_stem_worker, tasks):
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
    if len(sys.argv) < 2:
        print(f"Uso: python {Path(__file__).name} <CONTRACT_ID>")
        sys.exit(1)

    from dataclasses import dataclass
    @dataclass
    class _MockContext:
        contract_id: str
        next_contract_id: str | None = None

    process(_MockContext(contract_id=sys.argv[1]))
