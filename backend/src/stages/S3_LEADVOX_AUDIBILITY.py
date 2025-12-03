# C:\mix-master\backend\src\stages\S3_LEADVOX_AUDIBILITY.py

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

from utils.analysis_utils import get_temp_dir


def load_analysis(contract_id: str) -> Dict[str, Any]:
    """
    Carga el JSON de análisis generado por analysis\\S3_LEADVOX_AUDIBILITY.py.
    """
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def _compute_lead_gain_db(
    session: Dict[str, Any],
    metrics: Dict[str, Any],
    limits: Dict[str, Any],
) -> float:
    """
    Calcula el gain global a aplicar a las pistas de lead vocal.

    offset = LUFS_lead_short_term - LUFS_mix_short_term (media global).

    Queremos que offset esté dentro de [offset_min, offset_max].
    Elegimos como objetivo el centro (que en este contrato es 0 dB).

    Estrategia:
      - Simulamos varias "pasadas virtuales" de hasta max_gain_change_db_per_pass
        cada una, acumulando un gain total que acerque el offset al objetivo
        y lo deje dentro de rango en una sola ejecución del stage.
    """
    offset_min = float(metrics.get("short_term_lufs_offset_vs_mixbus_min_db", -3.0))
    offset_max = float(metrics.get("short_term_lufs_offset_vs_mixbus_max_db", 3.0))

    offset_mean = session.get("global_short_term_offset_mean_db")
    if offset_mean is None:
        # No hay datos útiles de ventanas con voz
        return 0.0

    try:
        offset_mean = float(offset_mean)
    except (TypeError, ValueError):
        return 0.0

    max_gain_step = float(limits.get("max_gain_change_db_per_pass", 2.0))

    # Margen que usa también el check
    MARGIN_DB = 0.5
    target_offset = 0.5 * (offset_min + offset_max)  # en este contrato, 0 dB

    # Simulación de varias pasadas virtuales
    cur_offset = offset_mean
    total_gain = 0.0

    # Igual que en S1_MIXBUS_HEADROOM: hasta 8 pasos razonables
    MAX_STEPS = 8

    for _ in range(MAX_STEPS):
        # ¿Ya estamos dentro del rango (con margen)?
        if offset_min - MARGIN_DB <= cur_offset <= offset_max + MARGIN_DB:
            break

        # Ganancia ideal para ir al centro
        desired_gain = target_offset - cur_offset  # subir/bajar lead

        # Limitar por step máximo
        if desired_gain > max_gain_step:
            step = max_gain_step
        elif desired_gain < -max_gain_step:
            step = -max_gain_step
        else:
            step = desired_gain

        # Evitar micro-ajustes ridículos
        if abs(step) < 0.1:
            break

        # Aplicar paso virtual:
        # si subimos la voz X dB, el offset lead-mix sube también X dB.
        total_gain += step
        cur_offset += step

    # Si el gain total es muy pequeño, lo ignoramos
    if abs(total_gain) < 0.1:
        return 0.0

    return float(total_gain)


# -------------------------------------------------------------------
# -------------------------------------------------------------------
def _apply_gain_to_lead_worker(
    args: Tuple[str, Dict[str, Any], float]
) -> bool:
    """
    Aplica el gain lineal a un stem de lead vocal y sobrescribe el archivo.

    Devuelve True si el stem ha sido procesado, False en caso contrario.
    """
    temp_dir_str, stem, gain_lin = args
    temp_dir = Path(temp_dir_str)

    if not stem.get("is_lead_vocal", False):
        return False

    fname = stem.get("file_name")
    if not fname:
        return False

    path = temp_dir / fname
    if not path.exists():
        return False

    data, sr = sf.read(path, always_2d=False)
    if not isinstance(data, np.ndarray):
        data = np.array(data, dtype=np.float32)
    else:
        data = data.astype(np.float32)

    if data.size == 0:
        return False

    data_out = data * gain_lin
    sf.write(path, data_out, sr)

    print(f"[S3_LEADVOX_AUDIBILITY] {fname}: aplicado gain {20.0 * np.log10(gain_lin):.2f} dB.")

    return True


def main() -> None:
    """
    Stage S3_LEADVOX_AUDIBILITY:

      - Lee analysis_S3_LEADVOX_AUDIBILITY.json.
      - Calcula un gain global en dB para todas las pistas de lead vocal.
      - Aplica ese gain a los stems marcados como is_lead_vocal = True.
    """
    if len(sys.argv) < 2:
        print("Uso: python S3_LEADVOX_AUDIBILITY.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S3_LEADVOX_AUDIBILITY"

    analysis = load_analysis(contract_id)

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}
    session: Dict[str, Any] = analysis.get("session", {}) or {}
    stems: List[Dict[str, Any]] = analysis.get("stems", []) or []

    gain_db = _compute_lead_gain_db(session, metrics, limits)

    if abs(gain_db) < 1e-6:
        print("[S3_LEADVOX_AUDIBILITY] Lead vocal ya dentro de rango (o sin datos); no se aplica gain.")
        return

    gain_lin = float(10.0 ** (gain_db / 20.0))

    temp_dir = get_temp_dir(contract_id, create=False)

    # Filtramos solo stems de lead vocal
    lead_stems: List[Dict[str, Any]] = [
        s for s in stems if s.get("is_lead_vocal", False)
    ]

    if not lead_stems:
        print("[S3_LEADVOX_AUDIBILITY] No se han encontrado stems marcados como lead vocal.")
        return

    args_list: List[Tuple[str, Dict[str, Any], float]] = [
        (str(temp_dir), stem, gain_lin) for stem in lead_stems
    ]

    results = []
    for args in args_list:
        results.append(_apply_gain_to_lead_worker(args))

    processed = sum(1 for r in results if r)

    print(
        f"[S3_LEADVOX_AUDIBILITY] Aplicado gain global de {gain_db:.2f} dB "
        f"a {processed} stems de lead vocal."
    )


if __name__ == "__main__":
    main()
