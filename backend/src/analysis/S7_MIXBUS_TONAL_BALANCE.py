# C:\mix-master\backend\src\analysis\S7_MIXBUS_TONAL_BALANCE.py

from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any, Tuple

# --- hack para importar utils ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402

from utils.analysis_utils import (  # noqa: E402
    load_contract,
    get_temp_dir,
    sf_read_limited,
)
from utils.session_utils import load_session_config  # noqa: E402
from utils.tonal_balance_utils import (  # noqa: E402
    get_freq_bands,
    compute_band_energies,
    get_style_tonal_profile,
)

try:
    from context import PipelineContext
except ImportError:
    PipelineContext = None  # type: ignore


def _finite_values(d: Dict[str, float]) -> list[float]:
    vals: list[float] = []
    for v in d.values():
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if fv == float("-inf"):
            continue
        vals.append(fv)
    return vals


def normalize_bands_db(
    band_db_abs: Dict[str, float],
) -> Tuple[Dict[str, float], float]:
    """
    Convierte energías absolutas por banda a energías relativas (forma espectral),
    restando la media de las bandas finitas.

    Devuelve:
      - band_db_rel: dict band_id -> (abs - mean_abs)
      - mean_abs_db: media usada (para diagnosticar offsets globales)
    """
    vals = _finite_values(band_db_abs)
    if not vals:
        return {k: float("-inf") for k in band_db_abs.keys()}, 0.0

    mean_abs = sum(vals) / float(len(vals))
    rel: Dict[str, float] = {}
    for k, v in band_db_abs.items():
        try:
            fv = float(v)
        except (TypeError, ValueError):
            rel[k] = float("-inf")
            continue
        if fv == float("-inf"):
            rel[k] = float("-inf")
        else:
            rel[k] = float(fv - mean_abs)
    return rel, float(mean_abs)


def compute_error_by_band_rel(
    current_rel: Dict[str, float],
    target_rel: Dict[str, float],
) -> Tuple[Dict[str, float], float]:
    """
    Error con signo definido:
      error = current_rel - target_rel

    RMS sobre bandas finitas comunes.
    """
    err: Dict[str, float] = {}
    sq: list[float] = []

    keys = set(current_rel.keys()) | set(target_rel.keys())
    for k in keys:
        c = current_rel.get(k, float("-inf"))
        t = target_rel.get(k, float("-inf"))
        try:
            cf = float(c)
            tf = float(t)
        except (TypeError, ValueError):
            continue
        if cf == float("-inf") or tf == float("-inf"):
            continue
        e = float(cf - tf)
        err[k] = e
        sq.append(e * e)

    rms = (sum(sq) / float(len(sq))) ** 0.5 if sq else 0.0
    return err, float(rms)


def _analyze_mixbus(full_song_path: Path) -> Dict[str, Any]:
    """
    Lee full_song.wav y calcula energías por banda (ABS).
    """
    try:
        y, sr = sf_read_limited(full_song_path, always_2d=False)
    except Exception as e:
        return {
            "band_current_db_abs": None,
            "sr_mix": None,
            "error": f"[S7_MIXBUS_TONAL_BALANCE] Aviso: no se puede leer full_song.wav: {e}.",
        }

    band_current_db_abs = compute_band_energies(y, sr)
    return {
        "band_current_db_abs": band_current_db_abs,
        "sr_mix": sr,
        "error": None,
    }


def process(context: PipelineContext, *args) -> bool:
    contract_id = args[0] if args else context.stage_id

    # 1) Contrato
    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    max_tonal_error_db = float(metrics.get("max_tonal_balance_error_db", 3.0))
    max_eq_change_db = float(limits.get("max_eq_change_db_per_band_per_pass", 1.5))

    # 2) Stage dir + session_config
    temp_dir = context.get_stage_dir(contract_id)
    temp_dir.mkdir(parents=True, exist_ok=True)

    cfg = load_session_config(contract_id)
    style_preset = cfg["style_preset"]

    # 3) Targets y bandas
    freq_bands = get_freq_bands()

    # Perfil de estilo (ABS, tal y como venga definido)
    band_target_db_abs: Dict[str, float] = get_style_tonal_profile(style_preset) or {}

    # 4) Medición
    full_song_path = temp_dir / "full_song.wav"

    band_current_db_abs: Dict[str, float] = {}
    band_current_db_rel: Dict[str, float] = {}
    band_target_db_rel: Dict[str, float] = {}
    band_error_db: Dict[str, float] = {}
    error_rms_db: float = 0.0
    sr_mix: int | None = None
    current_mean_abs_db: float = 0.0
    target_mean_abs_db: float = 0.0

    if full_song_path.exists():
        result = _analyze_mixbus(full_song_path)
        if result["error"] is not None:
            logger.logger.info(result["error"])
            band_current_db_abs = {b["id"]: float("-inf") for b in freq_bands}
        else:
            sr_mix = int(result["sr_mix"])
            band_current_db_abs = result["band_current_db_abs"] or {}

        # Normalización a REL (forma espectral)
        band_current_db_rel, current_mean_abs_db = normalize_bands_db(band_current_db_abs)
        band_target_db_rel, target_mean_abs_db = normalize_bands_db(band_target_db_abs)

        # Error REL (con signo definido)
        band_error_db, error_rms_db = compute_error_by_band_rel(
            band_current_db_rel, band_target_db_rel
        )

        logger.logger.info(
            f"[S7_MIXBUS_TONAL_BALANCE] full_song.wav analizado (sr={sr_mix}). "
            f"error_RMS_REL={error_rms_db:.2f} dB. "
            f"global_offset_abs={current_mean_abs_db - target_mean_abs_db:+.2f} dB."
        )
    else:
        logger.logger.info(
            f"[S7_MIXBUS_TONAL_BALANCE] Aviso: no existe {full_song_path}, "
            "no se puede medir el tonal balance del mixbus."
        )
        band_current_db_abs = {b["id"]: float("-inf") for b in freq_bands}
        band_current_db_rel = {b["id"]: float("-inf") for b in freq_bands}
        band_target_db_rel, target_mean_abs_db = normalize_bands_db(band_target_db_abs)
        band_error_db = {}
        error_rms_db = 0.0

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "samplerate_hz": sr_mix,
            "max_tonal_balance_error_db": max_tonal_error_db,
            "max_eq_change_db_per_band_per_pass": max_eq_change_db,
            "tonal_bands": {
                "bands": freq_bands,

                # REL (lo que debe usar el stage para “balance tonal”)
                "current_band_db": band_current_db_rel,
                "target_band_db": band_target_db_rel,
                "error_by_band_db": band_error_db,
                "error_rms_db": error_rms_db,

                # ABS (diagnóstico)
                "current_band_db_abs": band_current_db_abs,
                "target_band_db_abs": band_target_db_abs,
                "current_mean_abs_db": current_mean_abs_db,
                "target_mean_abs_db": target_mean_abs_db,
                "global_offset_abs_db": float(current_mean_abs_db - target_mean_abs_db),
            },
        },
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    logger.logger.info(
        f"[S7_MIXBUS_TONAL_BALANCE] Análisis completado. error_RMS_REL={error_rms_db:.2f} dB. "
        f"JSON: {output_path}"
    )
    return True


def main() -> None:
    """
    Legacy entry point (sin PipelineContext).
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S7_MIXBUS_TONAL_BALANCE.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]

    temp_dir = get_temp_dir(contract_id, create=False)
    temp_root = temp_dir.parent
    job_id = temp_root.name

    if PipelineContext:
        ctx = PipelineContext(stage_id=contract_id, job_id=job_id, temp_root=temp_root)
        process(ctx, contract_id)
    else:
        logger.logger.info("[S7_MIXBUS_TONAL_BALANCE] PipelineContext no disponible en modo legacy.")
        sys.exit(1)


if __name__ == "__main__":
    main()
