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

import json  # noqa: E402
import numpy as np  # noqa: E402

from utils.analysis_utils import get_temp_dir  # noqa: E402
from utils.dynamics_utils import compute_crest_factor_db  # noqa: E402

# Pedalboard
from pedalboard import Pedalboard, Compressor  # noqa: E402
from pedalboard.io import AudioFile  # noqa: E402


def load_analysis(contract_id: str) -> Dict[str, Any]:
    """
    Carga el JSON de análisis generado por analysis\\S5_STEM_DYNAMICS_GENERIC.py.
    """
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
      - Aplica compresión con Pedalboard.
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
        # Leer audio con Pedalboard (forma: (channels, samples))
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

    # Normalizar forma para compresor:
    # - Pedalboard espera (channels, samples)
    # - Para métricas compatibles con utilidades existentes,
    #   preservamos una versión "data" similar a soundfile: (samples,) o (samples, channels)
    if audio.ndim == 1:
        # Mono
        audio_for_board = audio.reshape(1, -1)  # (1, samples)
        data_in = audio.copy()                  # (samples,)
    elif audio.ndim == 2:
        # (channels, samples)
        audio_for_board = audio
        data_in = audio.T.copy()               # (samples, channels)
    else:
        print(
            f"[S5_STEM_DYNAMICS_GENERIC] {fname}: formato de audio no soportado "
            f"con ndim={audio.ndim}; se omite."
        )
        return None

    # ------------------------------------------------------------------
    # Compresor genérico con Pedalboard
    # ------------------------------------------------------------------
    board = Pedalboard(
        [
            Compressor(
                threshold_db=float(threshold_db),
                ratio=float(RATIO),
                attack_ms=float(ATTACK_MS),
                release_ms=float(RELEASE_MS),
                makeup_gain_db=float(MAKEUP_DB),
            )
        ]
    )

    try:
        processed = board(audio_for_board, samplerate)  # (channels, samples)
    except Exception as e:
        print(f"[S5_STEM_DYNAMICS_GENERIC] {fname}: error en compresor: {e}")
        return None

    if not isinstance(processed, np.ndarray):
        processed = np.array(processed, dtype=np.float32)
    else:
        processed = processed.astype(np.float32)

    # Normalizar salida a la misma convención que data_in para métricas
    if processed.ndim == 1:
        data_out = processed.copy()  # (samples,)
    elif processed.ndim == 2:
        data_out = processed.T.copy()  # (samples, channels)
    else:
        print(
            f"[S5_STEM_DYNAMICS_GENERIC] {fname}: salida del compresor no soportada "
            f"con ndim={processed.ndim}; se omite."
        )
        return None

    # ------------------------------------------------------------------
    # Cálculo de ganancia de reducción media y máxima
    # ------------------------------------------------------------------
    eps = 1e-12

    # Trabajamos en forma (channels, samples) para GR por muestra
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

    # GR por muestra (dB): típicamente <= 0 (reducción)
    gr_db = 20.0 * np.log10(out_abs / in_abs)

    # Consideramos solo reducción (valores <= 0); ignoramos posibles zonas con out > in
    gr_db_clipped = np.minimum(gr_db, 0.0)

    # Ganancia de reducción media y máxima como magnitudes positivas
    avg_gr_db = float(-np.mean(gr_db_clipped))  # media de reducción
    max_gr_db = float(-np.min(gr_db_clipped))   # máxima reducción

    # ------------------------------------------------------------------
    # Métricas post-compresión (crest factor nuevo)
    # ------------------------------------------------------------------
    post_rms_db, post_peak_db, post_crest_db = compute_crest_factor_db(data_out)

    # Guardar audio procesado sobre el archivo original
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


def main() -> None:
    """
    Stage S5_STEM_DYNAMICS_GENERIC:

      - Lee analysis_S5_STEM_DYNAMICS_GENERIC.json.
      - Para cada stem:
          * Calcula un umbral de compresión en función de RMS/peak.
          * Aplica un compresor genérico (ratio moderado) con Pedalboard.
          * Registra métricas de GR y crest factor antes/después.
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

    temp_dir = get_temp_dir(contract_id, create=False)

    # ------------------------------------------------------------------
    # Preparar tareas
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
    # Ejecutar compresión en serie
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Guardar métricas de dinámica en un JSON auxiliar para el check
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
