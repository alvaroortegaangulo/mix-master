# C:\mix-master\backend\src\stages\S11_REPORT_GENERATION.py

from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import json
import shutil
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

from utils.analysis_utils import get_temp_dir, sanitize_json_floats
import soundfile as sf


def _compute_interactive_data(audio: np.ndarray, sr: int) -> Dict[str, Any]:
    """
    Generates data for interactive charts:
    1. Dynamics: RMS & Peak over time (e.g. 100ms windows)
    2. Spectrum: Average magnitude spectrum (log-spaced bands)
    """
    if audio is None or len(audio) == 0:
        return {}

    if audio.ndim > 1:
        # Mix to mono for analysis
        mono = np.mean(audio, axis=1)
    else:
        mono = audio

    # --- Dynamics (RMS & Peak) ---
    window_sec = 0.1  # 100ms
    window_samples = int(sr * window_sec)
    if window_samples == 0: window_samples = 1024

    # Pad to multiple of window
    pad_len = (window_samples - (len(mono) % window_samples)) % window_samples
    if pad_len > 0:
        mono_padded = np.pad(mono, (0, pad_len))
    else:
        mono_padded = mono

    # Reshape
    chunks = mono_padded.reshape(-1, window_samples)

    # RMS per chunk
    rms_vals = np.sqrt(np.mean(chunks**2, axis=1))
    rms_db = 20 * np.log10(np.maximum(rms_vals, 1e-9))

    # Peak per chunk
    peak_vals = np.max(np.abs(chunks), axis=1)
    peak_db = 20 * np.log10(np.maximum(peak_vals, 1e-9))

    # Clean up limits
    rms_db = np.clip(rms_db, -90, 0)
    peak_db = np.clip(peak_db, -90, 0)

    dynamics = {
        "time_step": window_sec,
        "rms_db": [round(float(x), 2) for x in rms_db],
        "peak_db": [round(float(x), 2) for x in peak_db],
        "duration_sec": len(mono) / sr
    }

    # --- Spectrum (Averaged Log Bands) ---
    n_fft = 4096

    # Take up to 100 chunks spread across the file to estimate average spectrum
    step = len(mono) // 100
    if step < n_fft:
        step = n_fft

    indices = np.arange(0, len(mono) - n_fft, step)
    if len(indices) == 0:
        # Fallback for short files
        indices = [0]
        if len(mono) < n_fft:
            n_fft = len(mono)
            if n_fft == 0:
                return {"dynamics": dynamics}

    magnitudes = []
    window = np.hanning(n_fft)

    for idx in indices:
        if idx + n_fft > len(mono): break
        chunk = mono[idx:idx+n_fft] * window
        fft = np.fft.rfft(chunk)
        mag = np.abs(fft)
        magnitudes.append(mag)

    if not magnitudes:
        avg_mag = np.zeros(n_fft//2 + 1)
    else:
        avg_mag = np.mean(magnitudes, axis=0)

    freqs = np.fft.rfftfreq(n_fft, 1/sr)

    # Log Bins
    min_freq = 20
    max_freq = sr / 2
    num_bands = 64

    log_freqs = np.logspace(np.log10(min_freq), np.log10(max_freq), num_bands + 1)
    band_energies = []
    band_centers = []

    for i in range(num_bands):
        f_start = log_freqs[i]
        f_end = log_freqs[i+1]
        mask = (freqs >= f_start) & (freqs < f_end)

        if np.any(mask):
            # Mean Power
            energy = np.mean(avg_mag[mask]**2)
            db = 10 * np.log10(np.maximum(energy, 1e-12))
            band_energies.append(db)
        else:
            band_energies.append(-90.0)

        band_centers.append(np.sqrt(f_start * f_end))

    # Normalize spectrum for display (relative to max)
    max_db = max(band_energies) if band_energies else -90
    # Or keep absolute? Absolute is hard to interpret without calibration.
    # But relative is fine. Let's keep absolute dBFS-ish (calculated from normalized audio).

    spectrum = {
        "frequencies": [round(float(f), 1) for f in band_centers],
        "magnitudes_db": [round(float(m), 2) for m in band_energies]
    }

    return {
        "dynamics": dynamics,
        "spectrum": spectrum
    }

def _load_mix_audio_for_report(context: PipelineContext) -> tuple[Optional[np.ndarray], Optional[int]]:
    """
    Fallback para cargar el mix final desde disco cuando el contexto
    no trae audio en memoria (pipeline actual). Prioriza el WAV mßs
    reciente disponible.
    """
    job_root: Optional[Path] = None
    try:
        if getattr(context, "temp_root", None):
            job_root = Path(context.temp_root)
        else:
            # Legacy fallback: usar el stage dir actual para resolver el job root
            job_root = get_temp_dir(context.stage_id or "S11_REPORT_GENERATION", create=False).parent
    except Exception:
        job_root = None

    if not job_root:
        return None, None

    candidates = [
        job_root / "S11_REPORT_GENERATION" / "full_song.wav",
        job_root / "S10_MASTER_FINAL_LIMITS" / "full_song.wav",
        job_root / "S6_MANUAL_CORRECTION" / "full_song.wav",
        job_root / "S0_SESSION_FORMAT" / "full_song.wav",
        job_root / "S0_MIX_ORIGINAL" / "full_song.wav",
    ]

    for wav_path in candidates:
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


def _enrich_report_with_parameters_and_images(report: Dict[str, Any], temp_dir: Path) -> None:
    """
    Enriches the report stages with parameter changes and image paths.
    Also copies the images to the report folder (S11 temp dir) so they are accessible.
    """

    stages: List[Dict[str, Any]] = report.get("stages", [])

    for s in stages:
        contract_id = s.get("contract_id")
        if not contract_id:
            continue

        # 1. Find Stage Temp Dir
        # Note: We rely on standard folder structure (parent of S11 temp dir -> stage_id)
        # S11 temp dir: .../job_id/S11_REPORT_GENERATION
        # Stage temp dir: .../job_id/contract_id (actually stage_id, which is often same or prefix)

        job_root = temp_dir.parent
        # Contracts.json map contract_id to stage_id, but here 's' has 'stage_id' field too
        # If 'stage_id' is None or missing, fall back to contract_id
        stage_id_folder = s.get("stage_id") or contract_id
        stage_dir = job_root / stage_id_folder

        if not stage_dir.exists():
            # Try contract_id directly
            stage_dir = job_root / contract_id
            if not stage_dir.exists():
                logger.logger.warning(f"[S11] Stage dir not found for {contract_id}: {stage_dir}")
                continue

        # 2. Extract Parameters
        params = s.get("parameters", {})

        # S0: Session Format
        if "S0_SESSION_FORMAT" in contract_id:
             analysis_path = stage_dir / f"analysis_{contract_id}.json"
             if analysis_path.exists():
                try:
                    with analysis_path.open("r", encoding="utf-8") as f:
                        data = json.load(f)
                    stems = data.get("stems", [])
                    metrics = data.get("metrics_from_contract", {})

                    params["count"] = len(stems)
                    params["sample_rate"] = metrics.get("samplerate_hz", 48000)
                    params["format"] = "32-bit Float"
                except Exception as e:
                    logger.logger.warning(f"[S11] Failed to read analysis for S0: {e}")

        # S5: Lead Vox Dynamics
        elif "S5_LEADVOX_DYNAMICS" in contract_id:
             metrics_path = stage_dir / "leadvox_dynamics_metrics_S5_LEADVOX_DYNAMICS.json"
             if metrics_path.exists():
                try:
                    with metrics_path.open("r", encoding="utf-8") as f:
                        m = json.load(f)
                    records = m.get("records", [])
                    if records:
                        avg_gr = sum(r.get("avg_gain_reduction_db", 0) for r in records) / len(records)
                        params["gr_db"] = f"{avg_gr:.1f}"
                    else:
                        params["gr_db"] = "0.0"
                except Exception as e:
                    logger.logger.warning(f"[S11] Failed to read metrics for S5 Lead: {e}")

        # S7: Tonal Balance
        elif "S7_MIXBUS_TONAL_BALANCE" in contract_id:
            metrics_path = stage_dir / "tonal_metrics_S7_MIXBUS_TONAL_BALANCE.json"
            if metrics_path.exists():
                try:
                    with metrics_path.open("r", encoding="utf-8") as f:
                        m = json.load(f)
                    # format eq gains
                    gains = m.get("eq_gains_db", {})
                    if gains:
                        params["EQ Gains (dB)"] = {k: f"{v:+.2f}" for k, v in gains.items() if abs(v) > 0.1}

                        max_correction = max((abs(float(v)) for v in gains.values()), default=0.0)
                        params["max_correction_db"] = f"{max_correction:.1f}"
                except Exception as e:
                     logger.logger.warning(f"[S11] Failed to read metrics for S7: {e}")

        elif "S8_MIXBUS_COLOR_GENERIC" in contract_id:
            metrics_path = stage_dir / "color_metrics_S8_MIXBUS_COLOR_GENERIC.json"
            if metrics_path.exists():
                try:
                    with metrics_path.open("r", encoding="utf-8") as f:
                        m = json.load(f)
                    params["Saturation Drive (dB)"] = f"{m.get('drive_db_used', 0):.2f}"
                    params["drive_percent"] = f"{m.get('drive_db_used', 0):.1f}" # Assuming drive_db maps roughly to percent for UI text

                    params["True Peak Trim (dB)"] = f"{m.get('trim_db_applied', 0):.2f}"
                    params["THD (%)"] = f"{m.get('thd_percent', 0):.2f}"
                except Exception as e:
                     logger.logger.warning(f"[S11] Failed to read metrics for S8: {e}")

        elif "S9_MASTER_GENERIC" in contract_id:
            metrics_path = stage_dir / "master_metrics_S9_MASTER_GENERIC.json"
            if metrics_path.exists():
                try:
                    with metrics_path.open("r", encoding="utf-8") as f:
                        m = json.load(f)
                    post_lim = m.get("post_limiter", {})
                    post_final = m.get("post_final", {})
                    params["Pre Gain (dB)"] = f"{post_lim.get('pre_gain_db', 0):.2f}"
                    params["Limiter GR (dB)"] = f"{post_lim.get('limiter_gr_db', 0):.2f}"
                    params["Stereo Width Factor"] = f"{post_final.get('width_factor_applied', 1.0):.2f}"

                    # For translation
                    params["ceiling_db"] = "-0.5" # Usually hardcoded safe ceiling or retrieved if saved
                except Exception as e:
                     logger.logger.warning(f"[S11] Failed to read metrics for S9: {e}")

        s["parameters"] = params

        # 3. Find Images
        # Look for waveform_comparison.png and spectrogram_comparison.png
        # Priority: Check if already in temp_dir (pushed by stage.py), else check stage_dir and copy.
        images = {}
        for img_name in ["waveform_comparison.png", "spectrogram_comparison.png"]:
            unique_name = f"{contract_id}_{img_name}"
            pre_copied_path = temp_dir / unique_name
            stage_path = stage_dir / img_name

            final_name = None

            if pre_copied_path.exists():
                final_name = unique_name
            elif stage_path.exists():
                # Copy to S11 folder with unique name
                dest_path = temp_dir / unique_name
                try:
                    shutil.copy2(stage_path, dest_path)
                    final_name = unique_name
                    # logger.logger.info(f"[S11] Copied image {img_name} for {contract_id}")
                except Exception as e:
                    logger.logger.error(f"[S11] Failed to copy image {stage_path}: {e}")

            if final_name:
                # Determine type key
                key = "waveform" if "waveform" in img_name else "spectrogram"
                images[key] = final_name

        s["images"] = images

    pass

def process(context: PipelineContext, *args) -> bool:
    """
    Standard entry point for stage.py orchestrator.
    """
    contract_id = context.stage_id
    if not contract_id:
        # Fallback to args if legacy
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
        # We allow continuation to try and generate a partial report

    try:
        with analysis_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.logger.error(f"[S11] Failed to load analysis JSON: {e}")
        # If analysis is broken, we can't do much.
        # But we MUST return True to avoid pipeline failure if possible, or False?
        # User wants robust report.
        # If analysis load fails, we can't enrich anything.
        return False

    report = (
        data.get("session", {})
        .get("report", {})
    )

    if not report:
        logger.logger.info("[S11_REPORT_GENERATION] No se ha encontrado 'session.report' en el análisis.")
        report = {"stages": [], "final_metrics": {}, "error": "Report data missing"}

    # --- ENRICH REPORT ---
    try:
        _enrich_report_with_parameters_and_images(report, temp_dir)
    except Exception as e:
        logger.logger.error(f"[S11] Error enriching report: {e}")
        traceback.print_exc()

    # --- GENERATE INTERACTIVE CHART DATA ---
    try:
        audio_arr = getattr(context, "audio_mixdown", None)
        sample_rate = getattr(context, "sample_rate", None)

        # Si no viene en memoria (pipeline actual), cargamos desde disco
        if audio_arr is None or not sample_rate:
            audio_arr, sample_rate = _load_mix_audio_for_report(context)
            if audio_arr is not None and sample_rate:
                logger.logger.info(f"[S11] Loaded mix audio from disk for interactive charts (sr={sample_rate})")

        if audio_arr is not None and sample_rate:
            chart_data = _compute_interactive_data(audio_arr, int(sample_rate))
            report["interactive_charts"] = chart_data
        else:
            logger.logger.warning("[S11] No mix audio available; interactive charts will be empty.")
    except Exception as e:
        logger.logger.error(f"[S11] Error generating chart data: {e}")
        traceback.print_exc()


    # SANITIZE floats before dumping to JSON
    report = sanitize_json_floats(report)
    data["session"]["report"] = report

    # Save enriched report back to analysis json (or a separate report.json)
    # We'll save it to 'report.json' in the S11 folder for easier frontend access
    report_json_path = temp_dir / "report.json"
    try:
        with report_json_path.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.logger.info(f"[S11] Saved final report.json to {report_json_path}")
    except Exception as e:
        logger.logger.error(f"[S11] Failed to save report.json: {e}")
        return False

    # Also update the analysis json
    try:
        with analysis_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.logger.error(f"[S11] Failed to update analysis JSON: {e}")
        return False

    _log_summary(report)
    return True


def _log_summary(report: Dict[str, Any]) -> None:
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

        # Log parameters if any
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
    """
    Legacy entry point.
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S11_REPORT_GENERATION.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S11_REPORT_GENERATION"

    # Minimal context mock for legacy execution
    class MockContext:
        def __init__(self, stage_id):
            self.stage_id = stage_id
            self.audio_mixdown = None # No audio in legacy mode
            self.sample_rate = 44100
        def get_stage_dir(self):
            return get_temp_dir(self.stage_id, create=False)

    ctx = MockContext(contract_id)
    success = process(ctx)
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
