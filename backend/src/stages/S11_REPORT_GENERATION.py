# C:\mix-master\backend\src\stages\S11_REPORT_GENERATION.py

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Any, List
import json

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from stages.pipeline_context import PipelineContext

from utils.analysis_utils import get_temp_dir


def process(context: PipelineContext) -> None:
    """
    Stage S11_REPORT_GENERATION:

      - Lee analysis_S11_REPORT_GENERATION.json.
      - Imprime por pantalla un resumen legible del reporte (sin tocar audio).
    """

    contract_id = context.contract_id  # "S11_REPORT_GENERATION"

    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        print(
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
        print("[S11_REPORT_GENERATION] No se ha encontrado 'session.report' en el análisis.")
        return

    print("\n==============================================")
    print("       RESUMEN DE PIPELINE DE MEZCLA/MASTER")
    print("==============================================")

    pipeline_version = report.get("pipeline_version", "desconocida")
    generated_at = report.get("generated_at_utc", "desconocida")
    style_preset = report.get("style_preset", "desconocido")

    print(f"Pipeline version: {pipeline_version}")
    print(f"Generado (UTC):  {generated_at}")
    print(f"Estilo:          {style_preset}")
    print("----------------------------------------------")

    stages: List[Dict[str, Any]] = report.get("stages", [])
    print("Etapas ejecutadas:\n")

    for s in stages:
        cid = s.get("contract_id")
        sid = s.get("stage_id")
        name = s.get("name", "")
        status = s.get("status", "unknown")

        label = cid or "(sin id)"
        if sid:
            label = f"{sid} / {cid}"

        print(f"- {label}")
        if name:
            print(f"  Descripción: {name}")
        print(f"  Estado: {status}\n")

    final_metrics = report.get("final_metrics", {})
    print("----------------------------------------------")
    print("Métricas finales del master:")

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

    print(f"  True peak (dBTP):        {_fmt(tp)}")
    print(f"  LUFS integrado:          {_fmt(lufs)}")
    print(f"  LRA (LU):                {_fmt(lra)}")
    print(f"  Correlación estéreo:     {_fmt(corr, '.3f')}")
    print(f"  Dif. L/R (dB):           {_fmt(diff_lr)}")
    print(f"  Crest factor (dB):       {_fmt(crest)}")

    print("==============================================\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Uso: python {Path(__file__).name} <CONTRACT_ID>")
        sys.exit(1)

    from dataclasses import dataclass
    @dataclass
    class _MockContext:
        contract_id: str
        next_contract_id: str | None = None

    process(_MockContext(contract_id=sys.argv[1]))
