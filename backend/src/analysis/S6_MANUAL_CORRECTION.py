from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

# Ensure src is on path when executed as a loose script
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.logger import logger
from utils.analysis_utils import load_contract, get_temp_dir
from utils.audio_utils import load_audio_stems

try:
    from context import PipelineContext
except ImportError:
    PipelineContext = None  # type: ignore

STAGE_ID = "S6_MANUAL_CORRECTION"


def _resolve_stage_dir(context: PipelineContext | None) -> Path:
    if context and getattr(context, "temp_root", None):
        return context.get_stage_dir(STAGE_ID)
    return get_temp_dir(STAGE_ID, create=True)


def _gather_stem_summary(stage_dir: Path) -> List[Dict[str, Any]]:
    stems_data: List[Dict[str, Any]] = []
    stems = load_audio_stems(stage_dir)
    for name, audio in stems.items():
        info: Dict[str, Any] = {"file_name": name}
        try:
            info["channels"] = int(audio.shape[0]) if hasattr(audio, "shape") else None
            if hasattr(audio, "shape") and len(audio.shape) > 1:
                info["frames"] = int(audio.shape[1])
        except Exception:
            # Best-effort summary; keep going even if shape is unexpected
            pass
        stems_data.append(info)
    return stems_data


def process(context: PipelineContext | None, *args) -> bool:
    stage_dir = _resolve_stage_dir(context)
    stage_dir.mkdir(parents=True, exist_ok=True)

    contract = load_contract(STAGE_ID)
    metrics = contract.get("metrics", {}) or {}
    limits = contract.get("limits", {}) or {}

    analysis: Dict[str, Any] = {
        "contract_id": STAGE_ID,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {},
        "stems": _gather_stem_summary(stage_dir),
    }

    analysis_path = stage_dir / f"analysis_{STAGE_ID}.json"
    try:
        analysis_path.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
        logger.logger.info(f"[{STAGE_ID}] analysis written to {analysis_path}")
        return True
    except Exception as exc:
        logger.logger.error(f"[{STAGE_ID}] Failed to write analysis file: {exc}")
        return False


def main() -> None:
    ctx = PipelineContext(stage_id=STAGE_ID, job_id="", temp_root=_resolve_stage_dir(None).parent) if PipelineContext else None
    process(ctx, STAGE_ID)


if __name__ == "__main__":
    main()
