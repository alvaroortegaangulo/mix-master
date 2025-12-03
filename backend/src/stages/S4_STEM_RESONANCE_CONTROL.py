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


def load_analysis(contract_id: str) -> Dict[str, Any]:
    """
    Carga el JSON de análisis generado por analysis\\S4_STEM_RESONANCE_CONTROL.py.
    """
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data


# -------------------------------------------------------------------
# Heurísticas de diseño de filtros
# -------------------------------------------------------------------


def _estimate_q(freq_hz: float, instrument_profile: str | None) -> float:
    """
    Estima un Q razonable según instrumento y frecuencia.
    - Voces: algo más ancho en low-mids, más estrecho en agudos.
    - Kick/Bajo: notches algo más anchos para resonancias “boomy”.
    - Guitarras: notches relativamente estrechos para preservar carácter.
    - Otros: heurística genérica.
    """
    inst = (instrument_profile or "").lower()
    f = float(freq_hz)

    # Voces lead / backing
    if "vocal" in inst or "voice" in inst:
        if f < 300.0:
            return 4.0
        elif f < 3000.0:
            return 6.0
        else:
            return 8.0

    # Bajo
    if "bass" in inst:
        if f < 150.0:
            return 3.5
        elif f < 400.0:
            return 5.0
        else:
            return 6.5

    # Batería / percusión
    if any(k in inst for k in ("kick", "snare", "tom", "perc", "drum")):
        if f < 250.0:
            return 4.0
        elif f < 1000.0:
            return 5.5
        else:
            return 7.0

    # Guitarras
    if "guitar" in inst:
        if f < 400.0:
            return 5.5
        elif f < 3000.0:
            return 7.0
        else:
            return 8.5

    # Resto de instrumentos
    if f < 400.0:
        return 5.0
    elif f < 4000.0:
        return 7.0
    else:
        return 9.0


def _build_notches_for_stem(
    stem: Dict[str, Any],
    max_res_peak_db: float,
    max_cuts_db: float,
    max_filters_per_band: int,
) -> List[Dict[str, float]]:
    """
    A partir de la info de resonancias de un stem, construye la lista de notches
    (freq_hz, cut_db, q, gain_above_local_db_original) ya filtrada y limitada.

    Mejores decisiones:
      - Priorizamos las resonancias más severas.
      - Impedimos poner varios notches casi en la misma frecuencia (min_spacing).
      - Q dinámico según instrumento y frecuencia.
    """
    resonances = stem.get("resonances", []) or []
    if not resonances:
        return []

    inst_profile = stem.get("instrument_profile") or ""

    # Ordenar resonancias por severidad (gain_above_local_db descendente)
    try:
        resonances_sorted = sorted(
            resonances,
            key=lambda r: float(r.get("gain_above_local_db", 0.0)),
            reverse=True,
        )
    except Exception:
        resonances_sorted = resonances

    notches: List[Dict[str, float]] = []
    used_freqs: List[float] = []

    for res in resonances_sorted:
        if len(notches) >= max_filters_per_band:
            break

        try:
            gain_above = float(res.get("gain_above_local_db", 0.0))
            freq_hz = float(res.get("freq_hz", 0.0))
        except (TypeError, ValueError):
            continue

        if freq_hz <= 0.0:
            continue

        # Exceso sobre el umbral permitido
        excess_db = gain_above - max_res_peak_db
        if excess_db <= 0.0:
            # Ya está por debajo del objetivo contractual
            continue

        # Espaciado mínimo entre notches para no machacar la misma zona
        # Escalamos con la frecuencia para ser algo más laxos arriba
        min_spacing_hz = max(30.0, freq_hz * 0.08)  # ~8% de f, mínimo 30 Hz
        if any(abs(freq_hz - f0) < min_spacing_hz for f0 in used_freqs):
            # Ya hemos colocado un notch muy cerca de esta frecuencia
            continue

        # Profundidad de corte limitada por el contrato
        cut_db = min(excess_db, max_cuts_db)
        if cut_db <= 0.0:
            continue

        q = _estimate_q(freq_hz, inst_profile)

        notches.append(
            {
                "freq_hz": freq_hz,
                "cut_db": cut_db,  # positiva = cantidad de corte
                "q": q,
                "gain_above_local_db": gain_above,
            }
        )
        used_freqs.append(freq_hz)

    return notches


# --------------------------------------------------------------------
# --------------------------------------------------------------------


def _process_stem_worker(
    args: Tuple[str, str, List[Dict[str, float]]]
) -> Tuple[str, int]:
    """
    Aplica los cortes de resonancia a un stem concreto usando Pedalboard.

    args:
      - temp_dir_str: carpeta temporal del contrato
      - file_name: nombre del stem
      - notches: lista de dicts con al menos:
          {"freq_hz": float, "cut_db": float, "q": float?, "gain_above_local_db": float?}

    Devuelve:
      (file_name, num_notches_aplicadas)
    """
    temp_dir_str, fname, notches = args

    if not fname or not notches:
        return fname or "", 0

    temp_dir = Path(temp_dir_str)
    path = temp_dir / fname
    if not path.exists():
        return fname, 0

    try:
        # Leer audio con soundfile (forma estable en tu pipeline)
        audio, sr = sf.read(path, always_2d=True)  # (N, C)
        audio = np.asarray(audio, dtype=np.float32)

        if audio.size == 0:
            return fname, 0

        plugins = []
        log_parts: List[str] = []

        for n in notches:
            try:
                freq_hz = float(n["freq_hz"])
                cut_db = float(n["cut_db"])  # cantidad de corte (positiva)
            except (KeyError, TypeError, ValueError):
                continue

            if freq_hz <= 0.0 or cut_db <= 0.0:
                continue

            q = float(n.get("q", 10.0))

            # Para logging aproximado del “antes/después”
            gain_above = n.get("gain_above_local_db")
            if isinstance(gain_above, (int, float)):
                try:
                    gain_above = float(gain_above)
                except (TypeError, ValueError):
                    gain_above = None
            else:
                gain_above = None

            if gain_above is not None:
                residual_est = gain_above - cut_db
                log_parts.append(
                    f"{freq_hz:.0f}Hz/{cut_db:.1f}dB(Q={q:.1f}, "
                    f"{gain_above:.1f}→~{residual_est:.1f}dB)"
                )
            else:
                log_parts.append(f"{freq_hz:.0f}Hz/{cut_db:.1f}dB(Q={q:.1f})")

            plugins.append(
                PeakFilter(
                    cutoff_frequency_hz=freq_hz,
                    gain_db=-cut_db,   # negativo = corte
                    q=q,
                )
            )

        if not plugins:
            return fname, 0

        board = Pedalboard(plugins)

        # Procesar audio
        audio_filt = board(audio, sr)

        # Clamp suave por seguridad
        audio_filt = np.clip(audio_filt, -1.5, 1.5).astype(np.float32)

        # Escribir de vuelta al mismo archivo
        sf.write(path, audio_filt, sr)

        notch_str = ", ".join(log_parts)
        logger.logger.info(
            f"[S4_STEM_RESONANCE_CONTROL] {fname}: aplicadas {len(plugins)} notches "
            f"({notch_str})."
        )

        return fname, len(plugins)

    except Exception as e:
        logger.logger.info(f"[S4_STEM_RESONANCE_CONTROL] Error procesando {fname}: {e}")
        return fname, 0


def main() -> None:
    """
    Stage S4_STEM_RESONANCE_CONTROL:

      - Lee analysis_S4_STEM_RESONANCE_CONTROL.json.
      - Para cada stem, construye notches "musicales" (freq, Q, cut) a partir
        de las resonancias detectadas.
      - Aplica esos notches usando PeakFilter de Pedalboard.
      - Respeta:
          * max_resonance_peak_db_above_local (umbral de "aceptable").
          * max_resonant_cuts_db (corte máx. por resonancia).
          * max_resonant_filters_per_band (máx. resonancias aplicadas por stem).
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S4_STEM_RESONANCE_CONTROL.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S4_STEM_RESONANCE_CONTROL"

    analysis = load_analysis(contract_id)

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}
    stems: List[Dict[str, Any]] = analysis.get("stems", []) or []

    max_res_peak_db = float(metrics.get("max_resonance_peak_db_above_local", 12.0))
    max_cuts_db = float(limits.get("max_resonant_cuts_db", 8.0))
    max_filters_per_band = int(limits.get("max_resonant_filters_per_band", 3))

    temp_dir = get_temp_dir(contract_id, create=False)
    temp_dir_str = str(temp_dir)

    # Preparar tareas solo para stems que tengan notches efectivos
    tasks: List[Tuple[str, str, List[Dict[str, float]]]] = []

    for stem in stems:
        fname = stem.get("file_name")
        if not fname:
            continue

        resonances = stem.get("resonances", []) or []
        if not resonances:
            continue

        notches = _build_notches_for_stem(
            stem=stem,
            max_res_peak_db=max_res_peak_db,
            max_cuts_db=max_cuts_db,
            max_filters_per_band=max_filters_per_band,
        )
        if not notches:
            continue

        tasks.append((temp_dir_str, fname, notches))

    if not tasks:
        logger.logger.info(
            "[S4_STEM_RESONANCE_CONTROL] No hay stems con resonancias a procesar. "
            "Stage completado sin cambios."
        )
        return

    stems_touched = 0
    total_notches_applied = 0

    # Procesado en serie para evitar problemas de estabilidad con pedalboard
    for fname, num_notches in map(_process_stem_worker, tasks):
        if num_notches > 0:
            stems_touched += 1
            total_notches_applied += num_notches

    logger.logger.info(
        f"[S4_STEM_RESONANCE_CONTROL] Stage completado. "
        f"stems procesados={stems_touched}, notches totales={total_notches_applied}."
    )


if __name__ == "__main__":
    main()
