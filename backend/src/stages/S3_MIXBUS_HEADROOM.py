# C:\mix-master\backend\src\stages\S3_MIXBUS_HEADROOM.py

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


def load_analysis(contract_id: str) -> Dict[str, Any]:
    """
    Carga el JSON de análisis generado por analysis\\S3_MIXBUS_HEADROOM.py.
    """
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def _compute_global_gain_db(
    session: Dict[str, Any],
    metrics: Dict[str, Any],
    limits: Dict[str, Any],
) -> float:
    """
    Decide el gain global en dB a aplicar a todos los stems del stage:

      - Si ya estamos dentro de los rangos de peak y LUFS -> 0 dB (idempotente).
      - Si no:
          * Movemos LUFS hacia el centro del rango.
          * Ajustamos gain para no violar peak_dbfs_max.
          * Limitamos a max_gain_change_db_per_pass.
          * Ignoramos cambios muy pequeños (< 0.1 dB).
    """
    peak_min = float(metrics.get("peak_dbfs_min", -12.0))
    peak_max = float(metrics.get("peak_dbfs_max", -6.0))
    lufs_min = float(metrics.get("lufs_integrated_min", -28.0))
    lufs_max = float(metrics.get("lufs_integrated_max", -20.0))

    mix_peak = float(session.get("mix_peak_dbfs_measured", float("-inf")))
    mix_lufs = float(session.get("mix_lufs_integrated_measured", float("-inf")))

    max_gain_step = float(limits.get("max_gain_change_db_per_pass", 3.0))

    # ¿ya estamos dentro de rango?
    if (peak_min <= mix_peak <= peak_max) and (lufs_min <= mix_lufs <= lufs_max):
        return 0.0

    # Objetivos "centrales"
    target_peak = 0.5 * (peak_min + peak_max)
    target_lufs = 0.5 * (lufs_min + lufs_max)

    # Ajuste por LUFS como base
    gain_db = target_lufs - mix_lufs

    # Evitar pasarnos de peak_max
    predicted_peak = mix_peak + gain_db
    if predicted_peak > peak_max:
        # Reducimos gain hasta justo peak_max
        gain_db += (peak_max - predicted_peak)
        predicted_peak = mix_peak + gain_db

    # (Opcional) si quedamos por debajo de peak_min, podríamos subir algo,
    # pero para mantenerlo simple, lo dejamos tal cual.

    # Limitar al máximo cambio por pasada
    if gain_db > max_gain_step:
        gain_db = max_gain_step
    elif gain_db < -max_gain_step:
        gain_db = -max_gain_step

    # Ignorar microcambios
    if abs(gain_db) < 0.1:
        gain_db = 0.0

    return float(gain_db)


# --------------------------------------------------------------------
# --------------------------------------------------------------------

def _apply_gain_to_stem_worker(args: Tuple[str, str, float]) -> Tuple[str, bool]:
    """
    Worker que aplica el gain global a un stem concreto.

    args:
      - contract_id
      - file_name
      - gain_db
    """
    contract_id, fname, gain_db = args

    if not fname:
        return fname, False

    temp_dir = get_temp_dir(contract_id, create=False)
    path = temp_dir / fname

    if not path.exists():
        return fname, False

    try:
        data, sr = sf.read(path, always_2d=False)

        if not isinstance(data, np.ndarray):
            data = np.array(data, dtype=np.float32)
        else:
            data = data.astype(np.float32)

        if data.size == 0:
            return fname, False

        scale = float(10.0 ** (gain_db / 20.0))
        data_out = data * scale

        sf.write(path, data_out, sr)

        logger.logger.info(
            f"[S3_MIXBUS_HEADROOM] {fname}: aplicado gain global de {gain_db:.2f} dB."
        )
        return fname, True
    except Exception as e:
        logger.logger.info(f"[S3_MIXBUS_HEADROOM] Error procesando {fname}: {e}")
        return fname, False


def main() -> None:
    """
    Stage S3_MIXBUS_HEADROOM:

      - Lee analysis_S3_MIXBUS_HEADROOM.json.
      - Calcula un gain global en dB.
      - Aplica ese gain a todos los stems del stage (no a full_song.wav),
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S3_MIXBUS_HEADROOM.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S3_MIXBUS_HEADROOM"

    analysis = load_analysis(contract_id)

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {})
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {})
    session: Dict[str, Any] = analysis.get("session", {})
    stems: List[Dict[str, Any]] = analysis.get("stems", [])

    gain_db = _compute_global_gain_db(session, metrics, limits)

    if abs(gain_db) < 1e-6:
        logger.logger.info("[S3_MIXBUS_HEADROOM] Mezcla ya dentro de rango; no se aplica cambio de gain.")
        return

    # Preparar lista de tareas para los stems válidos (excluyendo full_song.wav)
    tasks: List[Tuple[str, str, float]] = []
    for stem_info in stems:
        fname = stem_info.get("file_name")
        if not fname:
            continue
        if fname.lower() == "full_song.wav":
            continue
        tasks.append((contract_id, fname, gain_db))

    if not tasks:
        logger.logger.info("[S3_MIXBUS_HEADROOM] No hay stems a los que aplicar gain.")
        return

    processed = 0

    for fname, ok in map(_apply_gain_to_stem_worker, tasks):
        if ok:
            processed += 1

    logger.logger.info(
        f"[S3_MIXBUS_HEADROOM] Aplicado gain global de {gain_db:.2f} dB "
        f"a {processed} stems."
    )


if __name__ == "__main__":
    main()
