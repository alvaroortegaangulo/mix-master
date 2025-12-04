# C:\mix-master\backend\src\stages\S11_REPORT_GENERATION.py

from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any, List
import json
import shutil

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.analysis_utils import get_temp_dir


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
                continue

        # 2. Extract Parameters
        params = {}

        # Specific Logic for known stages
        if "S7_MIXBUS_TONAL_BALANCE" in contract_id:
            metrics_path = stage_dir / "tonal_metrics_S7_MIXBUS_TONAL_BALANCE.json"
            if metrics_path.exists():
                try:
                    with metrics_path.open("r") as f:
                        m = json.load(f)
                    # format eq gains
                    gains = m.get("eq_gains_db", {})
                    if gains:
                        params["EQ Gains (dB)"] = {k: f"{v:+.2f}" for k, v in gains.items() if abs(v) > 0.1}
                except:
                    pass

        elif "S8_MIXBUS_COLOR_GENERIC" in contract_id:
            metrics_path = stage_dir / "color_metrics_S8_MIXBUS_COLOR_GENERIC.json"
            if metrics_path.exists():
                try:
                    with metrics_path.open("r") as f:
                        m = json.load(f)
                    params["Saturation Drive (dB)"] = f"{m.get('drive_db_used', 0):.2f}"
                    params["True Peak Trim (dB)"] = f"{m.get('trim_db_applied', 0):.2f}"
                    params["THD (%)"] = f"{m.get('thd_percent', 0):.2f}"
                except:
                    pass

        elif "S9_MASTER_GENERIC" in contract_id:
            metrics_path = stage_dir / "master_metrics_S9_MASTER_GENERIC.json"
            if metrics_path.exists():
                try:
                    with metrics_path.open("r") as f:
                        m = json.load(f)
                    post_lim = m.get("post_limiter", {})
                    post_final = m.get("post_final", {})
                    params["Pre Gain (dB)"] = f"{post_lim.get('pre_gain_db', 0):.2f}"
                    params["Limiter GR (dB)"] = f"{post_lim.get('limiter_gr_db', 0):.2f}"
                    params["Stereo Width Factor"] = f"{post_final.get('width_factor_applied', 1.0):.2f}"
                except:
                    pass

        s["parameters"] = params

        # 3. Find Images
        # Look for waveform_comparison.png and spectrogram_comparison.png
        images = {}
        for img_name in ["waveform_comparison.png", "spectrogram_comparison.png"]:
            img_path = stage_dir / img_name
            if img_path.exists():
                # Copy to S11 folder with unique name
                new_name = f"{contract_id}_{img_name}"
                dest_path = temp_dir / new_name
                shutil.copy2(img_path, dest_path)

                # Determine type key
                key = "waveform" if "waveform" in img_name else "spectrogram"
                images[key] = new_name

        s["images"] = images

    # Add general summary
    # We can compare S0 input vs S10 output (using final metrics vs initial metrics if available)
    # For now, just a placeholder text or constructed from available data
    report["general_summary"] = "Processing completed. "
    if report.get("final_metrics"):
        lufs = report["final_metrics"].get("lufs_integrated")
        report["general_summary"] += f"Final Integrated Loudness: {lufs:.2f} LUFS. "


def main() -> None:
    """
    Stage S11_REPORT_GENERATION:

      - Lee analysis_S11_REPORT_GENERATION.json.
      - Enriquece el reporte con parámetros e imágenes.
      - Guarda el JSON actualizado para el frontend.
      - Imprime por pantalla un resumen legible.
    """
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S11_REPORT_GENERATION.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S11_REPORT_GENERATION"

    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        logger.logger.info(
            f"[S11_REPORT_GENERATION] ERROR: no se encuentra {analysis_path}. "
            "Ejecuta primero el análisis de reporting."
        )
        return

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    report = (
        data.get("session", {})
        .get("report", {})
    )

    if not report:
        logger.logger.info("[S11_REPORT_GENERATION] No se ha encontrado 'session.report' en el análisis.")
        return

    # --- ENRICH REPORT ---
    _enrich_report_with_parameters_and_images(report, temp_dir)

    # Save enriched report back to analysis json (or a separate report.json)
    # We'll save it to 'report.json' in the S11 folder for easier frontend access
    report_json_path = temp_dir / "report.json"
    with report_json_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Also update the analysis json
    data["session"]["report"] = report
    with analysis_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


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


if __name__ == "__main__":
    main()
