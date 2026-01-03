# C:\mix-master\backend\src\analysis\S3_LEADVOX_AUDIBILITY.py

from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple
import os

# --- hack para importar utils cuando se ejecuta como script suelto ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from utils.analysis_utils import (  # noqa: E402
    load_contract,
    get_temp_dir,
    sf_read_limited,
)
from utils.session_utils import load_session_config  # noqa: E402
from utils.loudness_utils import measure_integrated_lufs  # noqa: E402


def _is_lead_vocal_profile(inst: str | None, lead_id: str) -> bool:
    """
    Determina si un instrument_profile se considera 'lead vocal' para este contrato.

    Regla mínima:
      - Igual al instrument_id del contrato (p.ej. 'Lead_Vocal_Melodic'), o
      - Empieza por 'Lead_Vocal'.
    """
    if not inst:
        return False
    if inst == lead_id:
        return True
    if inst.startswith("Lead_Vocal"):
        return True
    return False


def _load_bed_and_mix_signals(
    temp_dir: Path,
    instrument_by_file: Dict[str, str],
    lead_profile_id: str,
    sr_fallback: int = 48000,
) -> tuple[np.ndarray, np.ndarray, int]:
    """
    Devuelve:
      - mix_full_mono: suma de TODOS los stems (sin normalizar)
      - bed_mono: suma de stems EXCLUYENDO lead vocal (sin normalizar)
      - sr
    """
    stem_files = sorted(
        p for p in temp_dir.glob("*.wav")
        if p.name.lower() != "full_song.wav"
    )
    if not stem_files:
        z = np.zeros(1, dtype=np.float32)
        return z, z, sr_fallback

    mix_list: List[np.ndarray] = []
    bed_list: List[np.ndarray] = []
    sr_ref: int | None = None

    for p in stem_files:
        y, sr = sf_read_limited(p, always_2d=False)
        arr = np.asarray(y, dtype=np.float32)
        if arr.ndim > 1:
            arr = np.mean(arr, axis=1).astype(np.float32)

        if arr.size == 0:
            continue

        if sr_ref is None:
            sr_ref = int(sr)

        mix_list.append(arr)

        inst = instrument_by_file.get(p.name, "Other")
        is_lead = _is_lead_vocal_profile(inst, lead_profile_id)
        if not is_lead:
            bed_list.append(arr)

    if sr_ref is None:
        sr_ref = sr_fallback

    def _sum(items: List[np.ndarray]) -> np.ndarray:
        if not items:
            return np.zeros(1, dtype=np.float32)
        max_len = max(len(a) for a in items)
        s = np.zeros(max_len, dtype=np.float32)
        for a in items:
            s[: len(a)] += a
        return s

    mix_full = _sum(mix_list)
    bed = _sum(bed_list)

    # Si no hay bed (solo voz), caemos a mix_full por robustez
    if bed.size == 0 or (bed.size == 1 and float(bed[0]) == 0.0):
        bed = mix_full.copy()

    return mix_full, bed, int(sr_ref)


def _compute_short_term_offsets(
    y_lead: np.ndarray,
    y_ref: np.ndarray,
    sr: int,
    window_sec: float = 3.0,
    hop_sec: float = 1.0,
    rms_threshold_db: float = -40.0,
) -> Dict[str, Any]:
    """
    Calcula offsets de LUFS (por ventanas) entre lead y referencia (bed).

    offset_db = LUFS_lead - LUFS_ref en cada ventana donde:
      - RMS_lead > rms_threshold_db.

    Devuelve dict con:
      - num_windows_total
      - num_windows_used
      - offset_mean_db / median / min / max
    """
    y_lead = np.asarray(y_lead, dtype=np.float32)
    y_ref = np.asarray(y_ref, dtype=np.float32)

    n = min(y_lead.shape[0], y_ref.shape[0])
    if n <= 0:
        return {
            "num_windows_total": 0,
            "num_windows_used": 0,
            "offset_mean_db": None,
            "offset_median_db": None,
            "offset_min_db": None,
            "offset_max_db": None,
        }

    y_lead = y_lead[:n]
    y_ref = y_ref[:n]

    win_samples = int(round(window_sec * sr))
    hop_samples = int(round(hop_sec * sr))

    if win_samples <= 0 or hop_samples <= 0 or n < win_samples:
        return {
            "num_windows_total": 0,
            "num_windows_used": 0,
            "offset_mean_db": None,
            "offset_median_db": None,
            "offset_min_db": None,
            "offset_max_db": None,
        }

    rms_thr_lin = 10.0 ** (rms_threshold_db / 20.0)
    offsets: List[float] = []
    num_total = 0
    num_used = 0

    for start in range(0, n - win_samples + 1, hop_samples):
        end = start + win_samples
        num_total += 1

        seg_lead = y_lead[start:end]
        seg_ref = y_ref[start:end]

        # Actividad vocal básica
        rms_lead = float(np.sqrt(np.mean(seg_lead**2))) if seg_lead.size > 0 else 0.0
        if rms_lead <= rms_thr_lin:
            continue

        lufs_lead = measure_integrated_lufs(seg_lead, sr)
        lufs_ref = measure_integrated_lufs(seg_ref, sr)

        if lufs_lead == float("-inf") or lufs_ref == float("-inf"):
            continue

        offsets.append(float(lufs_lead - lufs_ref))
        num_used += 1

    if not offsets:
        return {
            "num_windows_total": num_total,
            "num_windows_used": num_used,
            "offset_mean_db": None,
            "offset_median_db": None,
            "offset_min_db": None,
            "offset_max_db": None,
        }

    arr = np.array(offsets, dtype=np.float32)

    return {
        "num_windows_total": num_total,
        "num_windows_used": num_used,
        "offset_mean_db": float(np.mean(arr)),
        "offset_median_db": float(np.median(arr)),
        "offset_min_db": float(np.min(arr)),
        "offset_max_db": float(np.max(arr)),
    }


def _analyze_stem(
    args: Tuple[
        Path,
        str,
        bool,
        np.ndarray,
        int,
        float,
        float,
        float,
    ]
) -> Dict[str, Any]:
    """
    Recibe:
      - stem_path: ruta al .wav
      - inst_prof: instrument_profile
      - is_lead: si el perfil se considera lead vocal
      - ref_mono: señal de referencia (BED, sin lead)
      - sr_ref: samplerate de la referencia
      - window_sec / hop_sec / rms_threshold_db: parámetros ST análisis
    """
    (
        stem_path,
        inst_prof,
        is_lead,
        ref_mono,
        sr_ref,
        window_sec,
        hop_sec,
        rms_threshold_db,
    ) = args

    fname = stem_path.name

    stem_entry: Dict[str, Any] = {
        "file_name": fname,
        "file_path": str(stem_path),
        "instrument_profile": inst_prof,
        "is_lead_vocal": is_lead,
        "short_term_offset_mean_db": None,
        "short_term_offset_median_db": None,
        "short_term_offset_min_db": None,
        "short_term_offset_max_db": None,
        "short_term_num_windows_total": 0,
        "short_term_num_windows_used": 0,
        "reference_type": "bed_excluding_lead",
    }

    if not is_lead:
        return stem_entry

    # Cargar stem lead
    y, sr = sf_read_limited(stem_path, always_2d=False)
    y = np.asarray(y, dtype=np.float32)
    if y.ndim > 1:
        y = np.mean(y, axis=1).astype(np.float32)

    if int(sr) != int(sr_ref):
        logger.logger.info(
            f"[S3_LEADVOX_AUDIBILITY] Advertencia: sr distinto en {fname} "
            f"({sr} vs {sr_ref}); se usa longitud mínima común."
        )

    stats = _compute_short_term_offsets(
        y_lead=y,
        y_ref=ref_mono,
        sr=sr_ref,
        window_sec=window_sec,
        hop_sec=hop_sec,
        rms_threshold_db=rms_threshold_db,
    )

    stem_entry.update(
        {
            "short_term_offset_mean_db": stats["offset_mean_db"],
            "short_term_offset_median_db": stats["offset_median_db"],
            "short_term_offset_min_db": stats["offset_min_db"],
            "short_term_offset_max_db": stats["offset_max_db"],
            "short_term_num_windows_total": stats["num_windows_total"],
            "short_term_num_windows_used": stats["num_windows_used"],
        }
    )

    return stem_entry


def main() -> None:
    """
    Análisis para el contrato S3_LEADVOX_AUDIBILITY.

    Uso esperado desde stage.py:
        python analysis/S3_LEADVOX_AUDIBILITY.py S3_LEADVOX_AUDIBILITY
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S3_LEADVOX_AUDIBILITY.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S3_LEADVOX_AUDIBILITY"

    # 1) Cargar contrato
    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {}) or {}
    limits: Dict[str, Any] = contract.get("limits", {}) or {}
    stage_id: str | None = contract.get("stage_id")

    offset_min = float(metrics.get("short_term_lufs_offset_vs_mixbus_min_db", -3.0))
    offset_max = float(metrics.get("short_term_lufs_offset_vs_mixbus_max_db", 3.0))
    lead_profile_id = contract.get("instrument_id", "Lead_Vocal_Melodic")

    # 2) Directorio temp/<contract_id> y session_config
    temp_dir = get_temp_dir(contract_id, create=True)

    cfg = load_session_config(contract_id)
    style_preset = cfg["style_preset"]
    instrument_by_file = cfg["instrument_by_file"]

    # 3) Listar stems del stage (wav), excluyendo full_song.wav
    stem_files: List[Path] = sorted(
        p for p in temp_dir.glob("*.wav")
        if p.name.lower() != "full_song.wav"
    )

    # 4) Construir referencia BED (mix sin lead) y mix_full (solo info)
    mix_full_mono, bed_mono, sr_ref = _load_bed_and_mix_signals(
        temp_dir=temp_dir,
        instrument_by_file=instrument_by_file,
        lead_profile_id=lead_profile_id,
    )

    WINDOW_SEC = float(metrics.get("short_term_window_sec", 3.0))
    HOP_SEC = float(metrics.get("short_term_hop_sec", 1.0))
    RMS_THR_DB = float(metrics.get("rms_threshold_db", -40.0))

    # 5) Preparar tareas (referencia = BED)
    tasks: List[
        Tuple[
            Path,
            str,
            bool,
            np.ndarray,
            int,
            float,
            float,
            float,
        ]
    ] = []

    for p in stem_files:
        fname = p.name
        inst_prof = instrument_by_file.get(fname, "Other")
        is_lead = _is_lead_vocal_profile(inst_prof, lead_profile_id)

        tasks.append(
            (
                p,
                inst_prof,
                is_lead,
                bed_mono,
                sr_ref,
                WINDOW_SEC,
                HOP_SEC,
                RMS_THR_DB,
            )
        )

    # --- Análisis por stem ---
    stems_analysis: List[Dict[str, Any]] = []
    if tasks:
        # mantenemos map (sin multiproceso) por estabilidad y por pasar arrays grandes
        results = list(map(_analyze_stem, tasks))
        stems_analysis = list(results)

    # Agregados globales (solo lead stems con datos)
    all_offsets: List[float] = [
        s["short_term_offset_mean_db"]
        for s in stems_analysis
        if s.get("is_lead_vocal", False) and s.get("short_term_offset_mean_db") is not None
    ]

    if all_offsets:
        arr_global = np.array(all_offsets, dtype=np.float32)
        global_mean = float(np.mean(arr_global))
        global_median = float(np.median(arr_global))
        global_min = float(np.min(arr_global))
        global_max = float(np.max(arr_global))
    else:
        global_mean = None
        global_median = None
        global_min = None
        global_max = None

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "short_term_offset_min_target_db": offset_min,
            "short_term_offset_max_target_db": offset_max,
            "short_term_window_sec": WINDOW_SEC,
            "short_term_hop_sec": HOP_SEC,
            "rms_threshold_db": RMS_THR_DB,
            "lead_profile_id": lead_profile_id,
            "reference_type": "bed_excluding_lead",
            "sr_reference_hz": sr_ref,
            "global_short_term_offset_mean_db": global_mean,
            "global_short_term_offset_median_db": global_median,
            "global_short_term_offset_min_db": global_min,
            "global_short_term_offset_max_db": global_max,
            "global_num_lead_stems_with_data": len(all_offsets),
        },
        "stems": stems_analysis,
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    logger.logger.info(
        f"[S3_LEADVOX_AUDIBILITY] Análisis completado (ref=BED). "
        f"global_offset_mean={global_mean} dB, stems_lead_con_datos={len(all_offsets)}. "
        f"JSON: {output_path}"
    )


if __name__ == "__main__":
    main()
