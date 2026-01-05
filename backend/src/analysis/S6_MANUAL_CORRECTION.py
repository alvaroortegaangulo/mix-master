from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure src is on path when executed as a loose script
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.logger import logger
from utils.analysis_utils import load_contract, get_temp_dir

try:
    import soundfile as sf
except Exception:  # pragma: no cover
    sf = None  # type: ignore

try:
    from context import PipelineContext
except ImportError:  # pragma: no cover
    PipelineContext = None  # type: ignore

STAGE_ID = "S6_MANUAL_CORRECTION"


def _resolve_stage_dir(context: Optional["PipelineContext"]) -> Path:
    if context and getattr(context, "temp_root", None):
        return context.get_stage_dir(STAGE_ID)
    return get_temp_dir(STAGE_ID, create=True)


def _safe_read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _gather_stem_summary(stage_dir: Path) -> List[Dict[str, Any]]:
    """
    Lightweight stem summary (no full audio decode). We rely on soundfile.info
    when available; otherwise, we fall back to file listing only.
    """
    stems_data: List[Dict[str, Any]] = []

    for wav_path in sorted(stage_dir.glob("*.wav")):
        if wav_path.name.lower() == "full_song.wav":
            continue

        info: Dict[str, Any] = {"file_name": wav_path.name}

        if sf is not None:
            try:
                meta = sf.info(str(wav_path))
                info["channels"] = int(meta.channels)
                info["frames"] = int(meta.frames)
                info["sample_rate"] = int(meta.samplerate)
                if meta.samplerate and meta.frames:
                    info["duration_sec"] = float(meta.frames) / float(meta.samplerate)
            except Exception:
                pass

        stems_data.append(info)

    return stems_data


def process(context: Optional["PipelineContext"], *args) -> bool:
    stage_dir = _resolve_stage_dir(context)
    stage_dir.mkdir(parents=True, exist_ok=True)

    contract = load_contract(STAGE_ID)
    metrics = contract.get("metrics", {}) or {}
    limits = contract.get("limits", {}) or {}

    # Corrections info (helps debugging whether UI changes are being persisted)
    corrections_info: Dict[str, Any] = {"found": False, "path": None, "count": 0, "names": []}

    try:
        temp_root = getattr(context, "temp_root", None)
        if temp_root:
            corrections_path = Path(temp_root) / "work" / "manual_corrections.json"
        else:
            corrections_path = stage_dir.parent / "work" / "manual_corrections.json"

        if corrections_path.exists():
            raw = _safe_read_json(corrections_path)
            corr_list: List[Dict[str, Any]] = []
            if isinstance(raw, dict) and isinstance(raw.get("corrections"), list):
                corr_list = [c for c in raw["corrections"] if isinstance(c, dict)]
            elif isinstance(raw, list):
                corr_list = [c for c in raw if isinstance(c, dict)]

            corrections_info["found"] = True
            corrections_info["path"] = str(corrections_path)
            corrections_info["count"] = len(corr_list)
            corrections_info["names"] = [str(c.get("name") or "") for c in corr_list if c.get("name")]
    except Exception:
        pass

    analysis: Dict[str, Any] = {
        "contract_id": STAGE_ID,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {},
        "manual_corrections": corrections_info,
        "stems": _gather_stem_summary(stage_dir),
    }

    analysis_path = stage_dir / f"analysis_{STAGE_ID}.json"
    try:
        analysis_path.write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8")
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
