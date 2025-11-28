# C:\mix-master\backend\src\analysis\S11_REPORT_GENERATION.py

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Any, List
import json
import datetime
import os
from concurrent.futures import ProcessPoolExecutor

# --- hack para importar utils ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from utils.analysis_utils import (  # noqa: E402
    load_contract,
    get_temp_dir,
    PROJECT_ROOT,
)
from utils.session_utils import load_session_config  # noqa: E402
from utils.loudness_utils import compute_lufs_and_lra  # noqa: E402
from utils.color_utils import compute_true_peak_dbfs  # noqa: E402


PIPELINE_VERSION = "v1.0.0"

# Orden lógico del pipeline (contract_ids principales)
PIPELINE_CONTRACT_IDS: List[str] = [
    "S0_SESSION_FORMAT",
    "S1_STEM_DC_OFFSET",
    "S1_STEM_WORKING_LOUDNESS",
    "S1_KEY_DETECTION",
    "S1_VOX_TUNING",
    "S2_GROUP_PHASE_DRUMS",
    "S3_MIXBUS_HEADROOM",
    "S3_LEADVOX_AUDIBILITY",
    "S4_STEM_HPF_LPF",
    "S4_STEM_RESONANCE_CONTROL",
    "S5_STEM_DYNAMICS_GENERIC",
    "S5_LEADVOX_DYNAMICS",
    "S5_BUS_DYNAMICS_DRUMS",
    "S6_BUS_REVERB_STYLE",
    "S7_MIXBUS_TONAL_BALANCE",
    "S8_MIXBUS_COLOR_GENERIC",
    "S9_MASTER_GENERIC",
    "S10_MASTER_FINAL_LIMITS",
]

# Pequeña descripción humana por etapa
STAGE_SUMMARY: Dict[str, str] = {
    "S0_SESSION_FORMAT": "Normalización de formato de sesión (samplerate, bit depth, headroom, asignación de buses).",
    "S1_STEM_DC_OFFSET": "Corrección de DC offset por stem.",
    "S1_STEM_WORKING_LOUDNESS": "Normalización de loudness de trabajo por stem según perfil de instrumento.",
    "S1_KEY_DETECTION": "Detección de tonalidad / escala global para la sesión.",
    "S1_VOX_TUNING": "Afinación de voces según escala detectada, respetando límites de pitch y fuerza de afinación.",
    "S2_GROUP_PHASE_DRUMS": "Alineación de fase y polaridad en el grupo de baterías/percusión.",
    "S3_MIXBUS_HEADROOM": "Ajuste de headroom global del mixbus (peak y LUFS de trabajo).",
    "S3_LEADVOX_AUDIBILITY": "Ajuste de nivel estático de la voz principal respecto a la mezcla.",
    "S4_STEM_HPF_LPF": "Aplicación de filtros HPF/LPF por stem según perfil de instrumento.",
    "S4_STEM_RESONANCE_CONTROL": "Control de resonancias por stem mediante cortes estrechos limitados.",
    "S5_STEM_DYNAMICS_GENERIC": "Compresión/puerta genérica por stem para controlar rango dinámico.",
    "S5_LEADVOX_DYNAMICS": "Dinámica específica de voz principal (compresión principal y automatización suave).",
    "S5_BUS_DYNAMICS_DRUMS": "Compresión de bus para el grupo de baterías (pegada y glue).",
    "S6_BUS_REVERB_STYLE": "Asignación de reverbs / espacio según estilo y familia de buses.",
    "S7_MIXBUS_TONAL_BALANCE": "EQ de tono global por bandas para ajustar el balance tonal al estilo.",
    "S8_MIXBUS_COLOR_GENERIC": "Coloración de mixbus (saturación suave y glue).",
    "S9_MASTER_GENERIC": "Mastering (nivel final de loudness, ceiling, ancho M/S moderado).",
    "S10_MASTER_FINAL_LIMITS": "QC final del master (TP, LUFS, L/R, correlación) con micro-ajustes únicamente.",
}


def _build_stage_report_entry(contract_id: str) -> Dict[str, Any]:
    """
    Construye una entrada de reporte para un contract_id concreto,
    usando analysis_<contract_id>.json si existe.
    """
    temp_dir = PROJECT_ROOT / "temp" / contract_id
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    entry: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": None,
        "name": STAGE_SUMMARY.get(contract_id, ""),
        "status": "missing_analysis",
        "key_metrics": {},
    }

    if not analysis_path.exists():
        return entry

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    entry["stage_id"] = data.get("stage_id")
    entry["status"] = "analyzed"
    # Para mantenerlo genérico: guardamos el bloque "session" tal cual.
    entry["key_metrics"] = data.get("session", {})

    return entry


def _compute_crest_and_histogram(
    y: np.ndarray,
    sr: int,
    floor_db: float = -60.0,
    ceil_db: float = 0.0,
    num_bins: int = 30,
) -> Dict[str, Any]:
    """
    Calcula crest factor aproximado y un histograma de niveles (en dB).

    - Crest factor = TP_dBFS - RMS_dBFS del master (mono).
    - Histograma de niveles basado en RMS por frames.
    """
    arr = np.asarray(y, dtype=np.float32)
    if arr.ndim == 2:
        mono = np.mean(arr, axis=1)
    else:
        mono = arr

    # Crest factor
    if mono.size == 0:
        crest_db = 0.0
    else:
        rms = float(np.sqrt(np.mean(mono**2)))
        if rms <= 0.0:
            rms_db = float("-inf")
            crest_db = 0.0
        else:
            rms_db = 20.0 * np.log10(rms)
            # true peak aproximado
            tp_db = compute_true_peak_dbfs(mono, oversample_factor=4)
            crest_db = tp_db - rms_db

    # Histograma: RMS por frames
    frame_len_s = 0.4
    hop_s = 0.2
    frame_len = int(frame_len_s * sr)
    hop_len = int(hop_s * sr)
    levels_db: List[float] = []

    for start in range(0, len(mono), hop_len):
        end = start + frame_len
        if end > len(mono):
            frame = mono[start:len(mono)]
        else:
            frame = mono[start:end]
        if frame.size == 0:
            continue
        rms = float(np.sqrt(np.mean(frame**2)))
        if rms <= 0.0:
            level_db = float("-inf")
        else:
            level_db = 20.0 * np.log10(rms)
        if np.isfinite(level_db):
            levels_db.append(level_db)

    if levels_db:
        levels_arr = np.asarray(levels_db, dtype=np.float32)
        bins = np.linspace(floor_db, ceil_db, num_bins + 1)
        counts, edges = np.histogram(levels_arr, bins=bins)
        histogram = {
            "bin_edges_db": edges.tolist(),
            "counts": counts.tolist(),
        }
    else:
        histogram = {
            "bin_edges_db": [],
            "counts": [],
        }

    return {
        "crest_factor_db": crest_db,
        "level_histogram_db": histogram,
    }


def _crest_hist_worker(path: Path) -> Dict[str, Any]:
    """
    Worker para ProcessPoolExecutor: lee un WAV y calcula crest + histograma.
    Devuelve métricas y posible mensaje de error.
    """
    try:
        y, sr = sf.read(path, always_2d=False)
    except Exception as e:
        return {
            "crest_factor_db": None,
            "level_histogram_db": {"bin_edges_db": [], "counts": []},
            "error": f"[S11_REPORT_GENERATION] Aviso: no se pudo leer {path}: {e}",
        }

    metrics = _compute_crest_and_histogram(y, sr)
    metrics["error"] = None
    return metrics


def main() -> None:
    """
    Análisis para S11_REPORT_GENERATION.

    Genera un objeto 'report' con:
      - pipeline_version, fecha, estilo.
      - resumen por stage con métricas clave (lo que haya en 'session' de cada análisis).
      - métricas finales (LUFS, LRA, TP, correlación, crest, histograma de niveles).
    """
    if len(sys.argv) < 2:
        print("Uso: python S11_REPORT_GENERATION.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S11_REPORT_GENERATION"

    # 1) Cargar contrato
    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    # 2) temp/<contract_id> y session_config (para estilo)
    temp_dir = get_temp_dir(contract_id, create=True)
    cfg = load_session_config(contract_id)
    style_preset = cfg["style_preset"]

    # 3) Construir report.stages recorriendo los contract_ids del pipeline (en paralelo)
    max_workers = min(4, os.cpu_count() or 1)
    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        stages_report: List[Dict[str, Any]] = list(
            ex.map(_build_stage_report_entry, PIPELINE_CONTRACT_IDS)
        )

    # 4) Métricas finales desde QC de S10 + audio final para crest / hist
    qc_contract_id = "S10_MASTER_FINAL_LIMITS"
    qc_dir = PROJECT_ROOT / "temp" / qc_contract_id
    qc_path = qc_dir / "qc_metrics_S10_MASTER_FINAL_LIMITS.json"

    final_tp = float("nan")
    final_lufs = float("nan")
    final_lra = float("nan")
    final_corr = float("nan")
    final_diff_lr = float("nan")

    if qc_path.exists():
        try:
            with qc_path.open("r", encoding="utf-8") as f:
                qc = json.load(f)
            post = qc.get("post", {}) or {}
            final_tp = float(post.get("true_peak_dbtp", float("nan")))
            final_lufs = float(post.get("lufs_integrated", float("nan")))
            final_lra = float(post.get("lra", float("nan")))
            final_corr = float(post.get("correlation", float("nan")))
            final_diff_lr = float(post.get("channel_loudness_diff_db", float("nan")))
        except Exception as e:
            print(f"[S11_REPORT_GENERATION] Aviso: no se pudo leer {qc_path}: {e}")

    # 5) Leer audio final (master) para crest & histograma
    #    Preferimos el full_song de S11; si no existe o falla, usamos el de S10.
    audio_paths = [
        temp_dir / "full_song.wav",
        qc_dir / "full_song.wav",
    ]

    crest_and_hist = {
        "crest_factor_db": None,
        "level_histogram_db": {"bin_edges_db": [], "counts": []},
    }

    for p in audio_paths:
        if not p.exists():
            continue

        with ProcessPoolExecutor(max_workers=max_workers) as ex:
            result = list(ex.map(_crest_hist_worker, [p]))[0]

        if result.get("error"):
            # Logeamos el error y pasamos al siguiente path
            print(result["error"])
            continue

        crest_and_hist = {
            "crest_factor_db": result["crest_factor_db"],
            "level_histogram_db": result["level_histogram_db"],
        }
        break

    final_metrics: Dict[str, Any] = {
        "true_peak_dbtp": final_tp,
        "lufs_integrated": final_lufs,
        "lra": final_lra,
        "correlation": final_corr,
        "channel_loudness_diff_db": final_diff_lr,
        "crest_factor_db": crest_and_hist.get("crest_factor_db"),
        "level_histogram_db": crest_and_hist.get("level_histogram_db"),
    }

    report: Dict[str, Any] = {
        "pipeline_version": PIPELINE_VERSION,
        "generated_at_utc": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "style_preset": style_preset,
        "stages": stages_report,
        "final_metrics": final_metrics,
    }

    # 6) Envolver todo en la estructura de análisis estándar
    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "report": report
        },
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    print(
        f"[S11_REPORT_GENERATION] Análisis completado. Reporte JSON: {output_path}"
    )


if __name__ == "__main__":
    main()
