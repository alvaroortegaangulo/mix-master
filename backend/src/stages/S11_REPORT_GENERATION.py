# C:\mix-master\backend\src\stages\S11_REPORT_GENERATION.py

from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import json
import traceback
import numpy as np

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Try to import PipelineContext for typing, but it might fail if running standalone without proper path
try:
    from context import PipelineContext
except ImportError:
    PipelineContext = Any

from utils.analysis_utils import get_temp_dir, sanitize_json_floats, compute_interactive_data
from utils.loudness_utils import measure_true_peak_dbtp, compute_lufs_and_lra
import soundfile as sf

# --- Metric Mapping for Report ---
# Mapeo de claves técnicas a claves de traducción
METRIC_MAPPING = {
    # General
    "noise_floor_dbfs": "noiseFloor",
    "pre_rms_dbfs": "inputLoudness",
    "pre_true_peak_dbtp": "inputTruePeak",
    "max_thd_percent": "harmonicDistortion",
    "samplerate_hz": "sampleRate",
    "target_true_peak_range_dbtp_max": "targetTruePeakMax",
    "target_true_peak_range_dbtp_min": "targetTruePeakMin",
    "dynamic_range_db": "dynamicRange",
    "clipped_samples_count": "clippingCount",

    # Correction/EQ
    "max_eq_change_db_per_band_per_pass": "maxEqAdjustment",
    "eq_gains_db": "eqCorrection",

    # Dynamics/Compression
    "avg_gain_reduction_db": "avgGainReduction",
    "max_gain_reduction_db": "maxGainReduction",
    "compressor_ratio": "compressionRatio",
    "compressor_threshold_db": "compressionThreshold",

    # Saturation
    "max_additional_saturation_per_pass_db": "saturationDrive",
    "drive_db_used": "saturationDriveUsed",

    # Mastering
    "lufs_integrated": "finalLoudness",
    "true_peak_dbtp": "finalTruePeak",
    "ceiling_db": "limiterCeiling",
    "pre_gain_db": "limiterGain",
    "limiter_gr_db": "limiterReduction"
}

def _load_mix_audio_for_report(context: PipelineContext, stage_ids: List[str]) -> tuple[Optional[np.ndarray], Optional[int]]:
    """
    Loads audio from the first matching stage in stage_ids.
    """
    job_root: Optional[Path] = None
    try:
        if getattr(context, "temp_root", None):
            job_root = Path(context.temp_root)
        else:
            job_root = get_temp_dir(context.stage_id or "S11_REPORT_GENERATION", create=False).parent
    except Exception:
        job_root = None

    if not job_root:
        return None, None

    for stage in stage_ids:
        wav_path = job_root / stage / "full_song.wav"
        if not wav_path.exists():
            continue
        try:
            audio, sr = sf.read(str(wav_path), dtype="float32", always_2d=True)
            if audio.size == 0:
                continue
            return audio, sr
        except Exception as exc:
            logger.logger.warning(f"[S11] Could not read mix audio from {wav_path}: {exc}")
            continue

    return None, None

def _load_stage_json(job_root: Path, stage_id: str, filename: str) -> Optional[Dict[str, Any]]:
    """Helper to safely load a JSON file from a specific stage directory."""
    path = job_root / stage_id / filename
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.logger.warning(f"[S11] Failed to load {filename} from {stage_id}: {e}")
        return None

def _process_comparison_diff(stage_id: str, diff_file: Path) -> List[Dict[str, Any]]:
    """
    Processes the comparison JSON to extract meaningful changes for the report.
    """
    try:
        with diff_file.open("r", encoding="utf-8") as f:
            diff_data = json.load(f)
    except Exception:
        return []

    changes = []
    session_diffs = diff_data.get("session", {})
    relevant_items = []
    for k, v in session_diffs.items():
        if v.get("changed", False):
            relevant_items.append((k, v))

    if not relevant_items:
        return []

    for k, v in relevant_items:
        unit = ""
        if "db" in k.lower(): unit = "dB"
        elif "hz" in k.lower(): unit = "Hz"
        elif "percent" in k.lower(): unit = "%"

        mapped_key = METRIC_MAPPING.get(k, k)
        diff_val = v.get("diff", 0)
        val_fmt = f"{diff_val:+.2f}"

        changes.append({
            "key": mapped_key,
            "value": val_fmt,
            "unit": unit,
            "raw_key": k
        })
    return changes[:5]

def _extract_diff_params(diff_file: Path) -> Dict[str, str]:
    """
    Extracts all diff values from comparison JSON into a flat dict for narrative interpolation.
    Ensures common metrics are present even if not changed (defaulting to +0.00).
    """
    try:
        with diff_file.open("r", encoding="utf-8") as f:
            diff_data = json.load(f)
    except Exception:
        return {}

    diff_params = {}
    session_diffs = diff_data.get("session", {})

    # Pre-populate common keys with 0.00 to ensure narrative templates don't break
    common_keys = ["noise_floor_dbfs", "pre_rms_dbfs", "pre_true_peak_dbtp"]
    for k in common_keys:
        mapped_key = METRIC_MAPPING.get(k, k)
        diff_params[f"diff_{mapped_key}"] = "+0.00"

    for k, v in session_diffs.items():
        mapped_key = METRIC_MAPPING.get(k, k) # e.g. noise_floor_dbfs -> noiseFloor

        diff_val = v.get("diff", 0.0)
        # Always format with sign
        val_fmt = f"{diff_val:+.2f}"

        # Key for params: "diff_noiseFloor", "diff_inputLoudness"
        diff_params[f"diff_{mapped_key}"] = val_fmt

    return diff_params

def _enrich_report_with_parameters_and_images(report: Dict[str, Any], temp_dir: Path) -> None:
    """
    Enriches the report stages with parameter changes and image paths.
    """
    stages: List[Dict[str, Any]] = report.get("stages", [])
    job_root = temp_dir.parent

    for s in stages:
        contract_id = s.get("contract_id")
        stage_id_folder = s.get("stage_id") or contract_id
        if not contract_id:
            continue

        stage_dir = job_root / stage_id_folder
        if not stage_dir.exists():
             stage_dir = job_root / contract_id

        params = s.get("parameters", {})
        if not params:
            params = {}

        comparison_file = stage_dir / f"comparison_{contract_id}.json"
        if comparison_file.exists():
            changes = _process_comparison_diff(contract_id, comparison_file)
            s["changes"] = changes

            # Inject diff parameters for narrative
            diff_params = _extract_diff_params(comparison_file)
            params.update(diff_params)
        else:
            s["changes"] = []

        if "S0_SESSION_FORMAT" in contract_id:
            data = _load_stage_json(job_root, "S0_SESSION_FORMAT", "analysis_S0_SESSION_FORMAT.json")
            if data:
                stems = data.get("stems", [])
                metrics = data.get("metrics_from_contract", {})
                params["count"] = len(stems)
                params["format"] = "WAV 32-bit Float"
                params["sample_rate"] = metrics.get("samplerate_hz", "48000")

        elif "S1_KEY_DETECTION" in contract_id:
            data = _load_stage_json(job_root, "S1_KEY_DETECTION", "analysis_S1_KEY_DETECTION.json")
            if data:
                session = data.get("session", {})
                params["key"] = session.get("key_name", "Unknown")
                conf = session.get("key_detection_confidence", 0)
                params["confidence"] = int(float(conf) * 100)

        elif "S2_GROUP_PHASE_DRUMS" in contract_id:
            data = _load_stage_json(job_root, "S2_GROUP_PHASE_DRUMS", "analysis_S2_GROUP_PHASE_DRUMS.json")
            if data:
                stems = data.get("stems", [])
                corrections = []
                for s_stem in stems:
                    lag = float(s_stem.get("lag_ms", 0.0))
                    flip = s_stem.get("use_polarity_flip", False)
                    # Solo listamos si hay un shift significativo o flip
                    if abs(lag) > 0.1 or flip:
                        parts = []
                        if abs(lag) > 0.1:
                            parts.append(f"{lag:+.1f}ms")
                        if flip:
                            parts.append("Flip")
                        corrections.append(f"{s_stem.get('file_name', 'stem')}: {' '.join(parts)}")

                if corrections:
                    params["phase_corrections"] = corrections

        elif "S1_VOX_TUNING" in contract_id:
             data = _load_stage_json(job_root, "S1_KEY_DETECTION", "analysis_S1_KEY_DETECTION.json")
             if data:
                 params["key"] = data.get("session", {}).get("key_name", "Unknown")
             else:
                 params["key"] = "Unknown"

        elif "MIXBUS_HEADROOM" in contract_id:
             data = _load_stage_json(job_root, contract_id, f"analysis_{contract_id}.json")
             if data:
                 m = data.get("metrics_from_contract", {})
                 params["headroom_db"] = m.get("mixbus_headroom_target_db", "-6.0")
             else:
                 params["headroom_db"] = "-6.0"

        elif "S3_LEADVOX_AUDIBILITY" in contract_id:
             params["gain_db"] = "0.0"

        elif "S4_STEM_RESONANCE_CONTROL" in contract_id:
             data = _load_stage_json(job_root, "S4_STEM_RESONANCE_CONTROL", "analysis_S4_STEM_RESONANCE_CONTROL.json")
             if data:
                 limits = data.get("limits_from_contract", {})
                 params["max_reduction_db"] = limits.get("max_resonant_cuts_db", "6.0")

                 stems = data.get("stems", [])
                 total_res = 0
                 for s_stem in stems:
                     total_res += len(s_stem.get("resonances", []))
                 params["total_resonances_detected"] = total_res
             else:
                 params["max_reduction_db"] = "6.0"

        elif "S5_LEADVOX_DYNAMICS" in contract_id:
             m_data = _load_stage_json(job_root, "S5_LEADVOX_DYNAMICS", "leadvox_dynamics_metrics_S5_LEADVOX_DYNAMICS.json")
             avg_gr = 0.0
             if m_data:
                 records = m_data.get("records", [])
                 if records:
                     vals = [float(r.get("avg_gain_reduction_db", 0)) for r in records]
                     if vals:
                         avg_gr = sum(vals) / len(vals)
             params["gr_db"] = f"{avg_gr:.1f}"

        elif "S5_STEM_DYNAMICS_GENERIC" in contract_id:
             m_data = _load_stage_json(job_root, "S5_STEM_DYNAMICS_GENERIC", "stem_dynamics_metrics_S5_STEM_DYNAMICS_GENERIC.json")
             val = 0.0
             if m_data:
                 records = m_data.get("records", [])
                 if records:
                     vals = [float(r.get("avg_gain_reduction_db", 0)) for r in records]
                     if vals:
                         val = sum(vals) / len(vals)
             params["avg_gr_db"] = f"{val:.1f}"

        elif "S5_BUS_DYNAMICS_DRUMS" in contract_id:
             params["gr_db"] = "2.0"

        elif "S6_BUS_REVERB_STYLE" in contract_id:
             data = _load_stage_json(job_root, contract_id, f"analysis_{contract_id}.json")
             style = "Auto"
             if data:
                 style = data.get("style_preset", "Auto")
             params["style"] = style

        elif "S7_MIXBUS_TONAL_BALANCE" in contract_id:
            metrics_path = stage_dir / "tonal_metrics_S7_MIXBUS_TONAL_BALANCE.json"
            max_corr = 0.0
            if metrics_path.exists():
                try:
                    with metrics_path.open("r") as f:
                        m = json.load(f)
                    gains = m.get("eq_gains_db", {})
                    if gains:
                        params["EQ Gains (dB)"] = {k: f"{v:+.2f}" for k, v in gains.items() if abs(v) > 0.1}
                        max_corr = max([abs(float(v)) for v in gains.values()] or [0.0])
                except Exception as e:
                     logger.logger.warning(f"[S11] Failed to read metrics for S7: {e}")
            params["max_correction_db"] = f"{max_corr:.1f}"

        elif "S8_MIXBUS_COLOR_GENERIC" in contract_id:
            metrics_path = stage_dir / "color_metrics_S8_MIXBUS_COLOR_GENERIC.json"
            drive_pct = 0
            if metrics_path.exists():
                try:
                    with metrics_path.open("r") as f:
                        m = json.load(f)
                    drive_db = float(m.get('drive_db_used', 0))
                    params["Saturation Drive (dB)"] = f"{drive_db:.2f}"
                    params["True Peak Trim (dB)"] = f"{m.get('trim_db_applied', 0):.2f}"
                    params["THD (%)"] = f"{m.get('thd_percent', 0):.2f}"
                    drive_pct = min(100, int((drive_db / 2.0) * 100))
                except Exception as e:
                     logger.logger.warning(f"[S11] Failed to read metrics for S8: {e}")
            params["drive_percent"] = str(drive_pct)

        elif "S9_MASTER_GENERIC" in contract_id:
            metrics_path = stage_dir / "master_metrics_S9_MASTER_GENERIC.json"
            ceiling = -1.0
            if metrics_path.exists():
                try:
                    with metrics_path.open("r") as f:
                        m = json.load(f)
                    post_lim = m.get("post_limiter", {})
                    params["Pre Gain (dB)"] = f"{post_lim.get('pre_gain_db', 0):.2f}"
                    params["Limiter GR (dB)"] = f"{post_lim.get('limiter_gr_db', 0):.2f}"
                except Exception as e:
                     logger.logger.warning(f"[S11] Failed to read metrics for S9: {e}")
            params["ceiling_db"] = f"{ceiling:.1f}"

        elif "S10_MASTER_FINAL_LIMITS" in contract_id:
             fm = report.get("final_metrics", {})
             lufs = fm.get("lufs_integrated", -14.0)
             tp = fm.get("true_peak_dbtp", -1.0)
             params["lufs"] = f"{float(lufs):.1f}"
             params["true_peak"] = f"{float(tp):.2f}"

        s["parameters"] = params

        comp_json = "comparison_interactive.json"
        comp_data = _load_stage_json(job_root, stage_id_folder, comp_json)
        if not comp_data:
             comp_data = _load_stage_json(job_root, contract_id, comp_json)
        if comp_data:
            s["interactive_comparison"] = comp_data

        s["images"] = {}
    pass

def process(context: PipelineContext, *args) -> bool:
    contract_id = context.stage_id
    if not contract_id:
        if args:
            contract_id = args[0]
        else:
            logger.logger.error("[S11] process() called without contract_id in context or args")
            return False

    temp_dir = context.get_stage_dir()
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        logger.logger.info(
            f"[S11_REPORT_GENERATION] ERROR: no se encuentra {analysis_path}. "
            "Ejecuta primero el análisis de reporting."
        )

    try:
        with analysis_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.logger.error(f"[S11] Failed to load analysis JSON: {e}")
        return False

    report = (
        data.get("session", {})
        .get("report", {})
    )

    if not report:
        logger.logger.info("[S11_REPORT_GENERATION] No se ha encontrado 'session.report' en el análisis.")
        report = {"stages": [], "final_metrics": {}, "error": "Report data missing"}

    try:
        _enrich_report_with_parameters_and_images(report, temp_dir)
    except Exception as e:
        logger.logger.error(f"[S11] Error enriching report: {e}")
        traceback.print_exc()

    # --- GENERATE INTERACTIVE CHART DATA ---
    try:
        audio_arr = getattr(context, "audio_mixdown", None)
        sample_rate = getattr(context, "sample_rate", None)

        # Also try to get original audio
        audio_original = getattr(context, "audio_original", None)

        if audio_arr is None or not sample_rate:
            # Fallback to load from disk
            # Try S10 or S9 first
            audio_arr, sample_rate = _load_mix_audio_for_report(context, ["S11_REPORT_GENERATION", "S10_MASTER_FINAL_LIMITS", "S9_MASTER_GENERIC", "S6_MANUAL_CORRECTION"])
            if audio_arr is not None and sample_rate:
                logger.logger.info(f"[S11] Loaded mix audio from disk (sr={sample_rate})")

        if audio_original is None:
             # Load S0 or S0_MIX_ORIGINAL
             audio_original, original_sr = _load_mix_audio_for_report(context, ["S0_MIX_ORIGINAL", "S0_SESSION_FORMAT"])
             if audio_original is not None:
                 logger.logger.info(f"[S11] Loaded original audio from disk (sr={original_sr})")

                 # Compute basic metrics for Original (Requested by user)
                 try:
                     sr_for_metrics = original_sr if original_sr else sample_rate
                     if sr_for_metrics:
                         orig_lufs, orig_lra = compute_lufs_and_lra(audio_original, sr_for_metrics)
                         orig_tp = measure_true_peak_dbtp(audio_original, sr_for_metrics)
                         report["original_metrics"] = {
                             "lufs_integrated": orig_lufs,
                             "true_peak_dbtp": orig_tp,
                             "lra": orig_lra
                         }
                 except Exception as e:
                     logger.logger.warning(f"[S11] Failed to compute original metrics: {e}")

        if audio_arr is not None and sample_rate:
            chart_data = compute_interactive_data(audio_arr, int(sample_rate), audio_original=audio_original)
            report["interactive_charts"] = chart_data
        else:
            logger.logger.warning("[S11] No mix audio available; interactive charts will be empty.")
    except Exception as e:
        logger.logger.error(f"[S11] Error generating chart data: {e}")
        traceback.print_exc()


    # SANITIZE floats before dumping to JSON
    report = sanitize_json_floats(report)
    data["session"]["report"] = report

    report_json_path = temp_dir / "report.json"
    try:
        with report_json_path.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.logger.info(f"[S11] Saved final report.json to {report_json_path}")
    except Exception as e:
        logger.logger.error(f"[S11] Failed to save report.json: {e}")
        return False

    try:
        with analysis_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.logger.error(f"[S11] Failed to update analysis JSON: {e}")
        return False

    _log_summary(report)
    return True

def _log_summary(report: Dict[str, Any]) -> None:
    # (Existing logging logic)
    logger.logger.info("\n==============================================")
    logger.logger.info("       RESUMEN DE PIPELINE DE MEZCLA/MASTER")
    logger.logger.info("==============================================")

    pipeline_version = report.get("pipeline_version", "desconocida")
    generated_at = report.get("generated_at_utc", "desconocida")
    style_preset = report.get("style_preset", "desconocido")

    logger.logger.info(f"Pipeline version: {pipeline_version}")
    logger.logger.info(f"Generado (UTC):  {generated_at}")
    logger.logger.info(f"Estilo:          {style_preset}")
    logger.logger.info("----------------------------------------------")

    stages: List[Dict[str, Any]] = report.get("stages", [])
    logger.logger.info("Etapas ejecutadas:\n")

    for s in stages:
        cid = s.get("contract_id")
        sid = s.get("stage_id")
        name = s.get("name", "")
        status = s.get("status", "unknown")

        label = cid or "(sin id)"
        if sid:
            label = f"{sid} / {cid}"

        logger.logger.info(f"- {label}")
        if name:
            logger.logger.info(f"  Descripción: {name}")
        logger.logger.info(f"  Estado: {status}")

        params = s.get("parameters", {})
        if params:
            logger.logger.info("  Parámetros modificados:")
            for k, v in params.items():
                if isinstance(v, dict):
                    logger.logger.info(f"    {k}:")
                    for subk, subv in v.items():
                        logger.logger.info(f"      {subk}: {subv}")
                else:
                    logger.logger.info(f"    {k}: {v}")

        changes = s.get("changes", [])
        if changes:
             logger.logger.info("  Cambios detectados:")
             for c in changes:
                 logger.logger.info(f"    {c['key']}: {c['value']} {c['unit']}")

        logger.logger.info("")

    final_metrics = report.get("final_metrics", {})
    logger.logger.info("----------------------------------------------")
    logger.logger.info("Métricas finales del master:")

    tp = final_metrics.get("true_peak_dbtp")
    lufs = final_metrics.get("lufs_integrated")
    lra = final_metrics.get("lra")
    corr = final_metrics.get("correlation")
    diff_lr = final_metrics.get("channel_loudness_diff_db")
    crest = final_metrics.get("crest_factor_db")

    def _fmt(v: Any, fmt: str = ".2f") -> str:
        try:
            return format(float(v), fmt)
        except Exception:
            return "n/a"

    logger.logger.info(f"  True peak (dBTP):        {_fmt(tp)}")
    logger.logger.info(f"  LUFS integrado:          {_fmt(lufs)}")
    logger.logger.info(f"  LRA (LU):                {_fmt(lra)}")
    logger.logger.info(f"  Correlación estéreo:     {_fmt(corr, '.3f')}")
    logger.logger.info(f"  Dif. L/R (dB):           {_fmt(diff_lr)}")
    logger.logger.info(f"  Crest factor (dB):       {_fmt(crest)}")
    logger.logger.info("==============================================\n")

def main() -> None:
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S11_REPORT_GENERATION.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]
    class MockContext:
        def __init__(self, stage_id):
            self.stage_id = stage_id
            self.audio_mixdown = None
            self.sample_rate = 44100
        def get_stage_dir(self):
            return get_temp_dir(self.stage_id, create=False)

    ctx = MockContext(contract_id)
    success = process(ctx)
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
