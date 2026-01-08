# C:\mix-master\backend\src\analysis\S3_LEADVOX_AUDIBILITY.py

from __future__ import annotations

import sys
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

import numpy as np  # noqa: E402

# --- hack para importar utils cuando se ejecuta como script suelto ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.analysis_utils import (  # noqa: E402
    load_contract,
    get_temp_dir,
    sf_read_limited,
)
from utils.session_utils import load_session_config  # noqa: E402
from utils.loudness_utils import measure_integrated_lufs  # noqa: E402


# ---------------------------------------------------------------------
# Logger robusto (evita problemas si utils.logger cambia)
# ---------------------------------------------------------------------
def _get_log(name: str) -> logging.Logger:
    try:
        from utils.logger import logger as _logger_singleton  # type: ignore
        if hasattr(_logger_singleton, "logger"):
            return _logger_singleton.logger
        return _logger_singleton
    except Exception:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        )
        return logging.getLogger(name)


LOG = _get_log("S3_LEADVOX_AUDIBILITY_ANALYSIS")


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


def _sum_signals(items: List[np.ndarray]) -> np.ndarray:
    if not items:
        return np.zeros(1, dtype=np.float32)
    max_len = max(len(a) for a in items)
    s = np.zeros(max_len, dtype=np.float32)
    for a in items:
        if a.size == 0:
            continue
        s[: len(a)] += a
    return s.astype(np.float32)


def _load_mix_bed_lead_signals(
    temp_dir: Path,
    instrument_by_file: Dict[str, str],
    lead_profile_id: str,
    sr_fallback: int = 48000,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int, List[Path], List[Path]]:
    """
    Devuelve:
      - mix_full_mono: suma de TODOS los stems (sin normalizar)
      - bed_mono: suma de stems EXCLUYENDO lead vocal (sin normalizar)
      - lead_sum_mono: suma de stems lead vocal (sin normalizar)
      - sr
      - lead_stem_paths
      - nonlead_stem_paths

    Nota: se excluye full_song.wav.
    """
    stem_files = sorted(
        p for p in temp_dir.glob("*.wav")
        if p.name.lower() != "full_song.wav"
    )
    if not stem_files:
        z = np.zeros(1, dtype=np.float32)
        return z, z, z, sr_fallback, [], []

    mix_list: List[np.ndarray] = []
    bed_list: List[np.ndarray] = []
    lead_list: List[np.ndarray] = []
    lead_paths: List[Path] = []
    nonlead_paths: List[Path] = []

    sr_ref: Optional[int] = None

    for p in stem_files:
        try:
            y, sr = sf_read_limited(p, always_2d=False)
        except Exception as e:
            LOG.warning("[S3] No se pudo leer %s: %s", p.name, e)
            continue

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
        if is_lead:
            lead_list.append(arr)
            lead_paths.append(p)
        else:
            bed_list.append(arr)
            nonlead_paths.append(p)

    if sr_ref is None:
        sr_ref = sr_fallback

    mix_full = _sum_signals(mix_list)
    bed = _sum_signals(bed_list)
    lead_sum = _sum_signals(lead_list)

    # Robustez:
    # - Si no hay bed (solo voz), usamos mix_full como referencia (evita división por 0 conceptual).
    if bed.size == 0 or (bed.size == 1 and float(bed[0]) == 0.0):
        bed = mix_full.copy()

    # - Si no hay lead, lead_sum queda a ceros (lo manejamos)
    return mix_full, bed, lead_sum, int(sr_ref), lead_paths, nonlead_paths


def _percentile(x: np.ndarray, p: float) -> Optional[float]:
    if x.size == 0:
        return None
    try:
        return float(np.percentile(x, p))
    except Exception:
        return None


def _compute_short_term_offsets_series(
    y_lead: np.ndarray,
    y_ref: np.ndarray,
    sr: int,
    window_sec: float = 3.0,
    hop_sec: float = 1.0,
    rms_threshold_db: float = -40.0,
) -> Dict[str, Any]:
    """
    Calcula offsets de LUFS por ventanas entre lead y referencia (bed).

    offset_db = LUFS_lead - LUFS_ref en cada ventana donde:
      - RMS_lead > rms_threshold_db

    Devuelve:
      - num_windows_total / used
      - offsets_db: lista
      - window_starts_sec: lista
      - mean/median/p95/min/max (sobre offsets_db)
    """
    y_lead = np.asarray(y_lead, dtype=np.float32)
    y_ref = np.asarray(y_ref, dtype=np.float32)

    n = min(y_lead.shape[0], y_ref.shape[0])
    if n <= 0:
        return {
            "num_windows_total": 0,
            "num_windows_used": 0,
            "offsets_db": [],
            "window_starts_sec": [],
            "offset_mean_db": None,
            "offset_median_db": None,
            "offset_p95_db": None,
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
            "offsets_db": [],
            "window_starts_sec": [],
            "offset_mean_db": None,
            "offset_median_db": None,
            "offset_p95_db": None,
            "offset_min_db": None,
            "offset_max_db": None,
        }

    rms_thr_lin = 10.0 ** (rms_threshold_db / 20.0)

    offsets: List[float] = []
    starts_sec: List[float] = []
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
        starts_sec.append(float(start) / float(sr))
        num_used += 1

    if not offsets:
        return {
            "num_windows_total": num_total,
            "num_windows_used": num_used,
            "offsets_db": [],
            "window_starts_sec": [],
            "offset_mean_db": None,
            "offset_median_db": None,
            "offset_p95_db": None,
            "offset_min_db": None,
            "offset_max_db": None,
        }

    arr = np.array(offsets, dtype=np.float32)

    return {
        "num_windows_total": num_total,
        "num_windows_used": num_used,
        "offsets_db": [float(x) for x in arr.tolist()],
        "window_starts_sec": starts_sec,
        "offset_mean_db": float(np.mean(arr)),
        "offset_median_db": float(np.median(arr)),
        "offset_p95_db": _percentile(arr, 95.0),
        "offset_min_db": float(np.min(arr)),
        "offset_max_db": float(np.max(arr)),
    }


def _analyze_stem_summary(
    stem_path: Path,
    inst_prof: str,
    is_lead: bool,
    bed_mono: np.ndarray,
    sr_ref: int,
    window_sec: float,
    hop_sec: float,
    rms_threshold_db: float,
    include_series: bool = True,
) -> Dict[str, Any]:
    """
    Analiza un stem (si es lead) vs BED: devuelve resumen + (opcional) series.
    """
    fname = stem_path.name
    out: Dict[str, Any] = {
        "file_name": fname,
        "file_path": str(stem_path),
        "instrument_profile": inst_prof,
        "is_lead_vocal": is_lead,
        "reference_type": "bed_excluding_lead",
        "short_term_num_windows_total": 0,
        "short_term_num_windows_used": 0,
        "short_term_offset_mean_db": None,
        "short_term_offset_median_db": None,
        "short_term_offset_p95_db": None,
        "short_term_offset_min_db": None,
        "short_term_offset_max_db": None,
    }

    if not is_lead:
        return out

    y, sr = sf_read_limited(stem_path, always_2d=False)
    y = np.asarray(y, dtype=np.float32)
    if y.ndim > 1:
        y = np.mean(y, axis=1).astype(np.float32)

    if int(sr) != int(sr_ref):
        LOG.info(
            "[S3_LEADVOX_AUDIBILITY] Advertencia: sr distinto en %s (%s vs %s); se usa longitud mínima común.",
            fname, sr, sr_ref
        )

    stats = _compute_short_term_offsets_series(
        y_lead=y,
        y_ref=bed_mono,
        sr=sr_ref,
        window_sec=window_sec,
        hop_sec=hop_sec,
        rms_threshold_db=rms_threshold_db,
    )

    out.update(
        {
            "short_term_num_windows_total": stats["num_windows_total"],
            "short_term_num_windows_used": stats["num_windows_used"],
            "short_term_offset_mean_db": stats["offset_mean_db"],
            "short_term_offset_median_db": stats["offset_median_db"],
            "short_term_offset_p95_db": stats["offset_p95_db"],
            "short_term_offset_min_db": stats["offset_min_db"],
            "short_term_offset_max_db": stats["offset_max_db"],
        }
    )

    if include_series:
        out["short_term_offsets_db"] = stats["offsets_db"]
        out["short_term_window_starts_sec"] = stats["window_starts_sec"]

    return out


def main() -> None:
    """
    Análisis para el contrato S3_LEADVOX_AUDIBILITY.

    Uso esperado desde stage.py:
        python analysis/S3_LEADVOX_AUDIBILITY.py S3_LEADVOX_AUDIBILITY
    """
    if len(sys.argv) < 2:
        LOG.info("Uso: python S3_LEADVOX_AUDIBILITY.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S3_LEADVOX_AUDIBILITY"

    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {}) or {}
    limits: Dict[str, Any] = contract.get("limits", {}) or {}
    stage_id: str | None = contract.get("stage_id")

    offset_min = float(metrics.get("short_term_lufs_offset_vs_mixbus_min_db", -3.0))
    offset_max = float(metrics.get("short_term_lufs_offset_vs_mixbus_max_db", 3.0))
    lead_profile_id = contract.get("instrument_id", "Lead_Vocal_Melodic")

    temp_dir = get_temp_dir(contract_id, create=True)

    cfg = load_session_config(contract_id)
    style_preset = cfg.get("style_preset", "balanced")
    instrument_by_file = cfg.get("instrument_by_file", {})

    # Cargar señales
    mix_full_mono, bed_mono, lead_sum_mono, sr_ref, lead_paths, _ = _load_mix_bed_lead_signals(
        temp_dir=temp_dir,
        instrument_by_file=instrument_by_file,
        lead_profile_id=lead_profile_id,
    )

    WINDOW_SEC = float(metrics.get("short_term_window_sec", 3.0))
    HOP_SEC = float(metrics.get("short_term_hop_sec", 1.0))
    RMS_THR_DB = float(metrics.get("rms_threshold_db", -40.0))

    # --- Series global basada en SUMA de leads vs BED (mejor perceptual que mean-of-means) ---
    lead_sum_series = _compute_short_term_offsets_series(
        y_lead=lead_sum_mono,
        y_ref=bed_mono,
        sr=sr_ref,
        window_sec=WINDOW_SEC,
        hop_sec=HOP_SEC,
        rms_threshold_db=RMS_THR_DB,
    )

    # --- Análisis por stem (solo resumen + series opcional) ---
    stem_files: List[Path] = sorted(
        p for p in temp_dir.glob("*.wav")
        if p.name.lower() != "full_song.wav"
    )

    stems_analysis: List[Dict[str, Any]] = []
    for p in stem_files:
        fname = p.name
        inst_prof = instrument_by_file.get(fname, "Other")
        is_lead = _is_lead_vocal_profile(inst_prof, lead_profile_id)
        stems_analysis.append(
            _analyze_stem_summary(
                stem_path=p,
                inst_prof=inst_prof,
                is_lead=is_lead,
                bed_mono=bed_mono,
                sr_ref=sr_ref,
                window_sec=WINDOW_SEC,
                hop_sec=HOP_SEC,
                rms_threshold_db=RMS_THR_DB,
                include_series=True,  # útil para debug/front
            )
        )

    # --- Global metrics (coherentes) desde lead_sum_series ---
    global_mean = lead_sum_series.get("offset_mean_db")
    global_median = lead_sum_series.get("offset_median_db")
    global_p95 = lead_sum_series.get("offset_p95_db")
    global_min = lead_sum_series.get("offset_min_db")
    global_max = lead_sum_series.get("offset_max_db")

    # (Opcional) legacy agregando medias por stem (solo para diagnóstico; ya no se usa para decisión)
    lead_means: List[float] = [
        float(s["short_term_offset_mean_db"])
        for s in stems_analysis
        if s.get("is_lead_vocal", False) and s.get("short_term_offset_mean_db") is not None
    ]
    legacy_stem_mean_aggregate = None
    if lead_means:
        a = np.array(lead_means, dtype=np.float32)
        legacy_stem_mean_aggregate = {
            "mean_db": float(np.mean(a)),
            "median_db": float(np.median(a)),
            "min_db": float(np.min(a)),
            "max_db": float(np.max(a)),
            "count": int(a.size),
        }

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

            # Global (coherente, basado en offsets por ventana de LEAD_SUM vs BED)
            "global_short_term_offset_mean_db": global_mean,
            "global_short_term_offset_median_db": global_median,
            "global_short_term_offset_p95_db": global_p95,
            "global_short_term_offset_min_db": global_min,
            "global_short_term_offset_max_db": global_max,
            "global_num_windows_used": int(lead_sum_series.get("num_windows_used", 0)),

            # Series global para automation en stage
            "lead_sum_short_term_offsets_db": lead_sum_series.get("offsets_db", []),
            "lead_sum_window_starts_sec": lead_sum_series.get("window_starts_sec", []),

            # Diagnóstico: legacy de medias por stem (NO usar para decisiones)
            "legacy_stem_mean_aggregate": legacy_stem_mean_aggregate,
        },
        "stems": stems_analysis,
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    LOG.info(
        "[S3_LEADVOX_AUDIBILITY] Análisis completado (ref=BED, lead_sum series). "
        "global_p95=%s dB, global_max=%s dB, windows_used=%s. JSON: %s",
        None if global_p95 is None else f"{float(global_p95):.2f}",
        None if global_max is None else f"{float(global_max):.2f}",
        int(lead_sum_series.get("num_windows_used", 0)),
        output_path,
    )


if __name__ == "__main__":
    main()
