from __future__ import annotations

import sys
from pathlib import Path

# --- hack sys.path para poder importar utils.* cuando se ejecuta como script ---
THIS_DIR = Path(__file__).resolve().parent      # .../src/utils
SRC_DIR = THIS_DIR.parent                       # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from stages.pipeline_context import PipelineContext

from utils.analysis_utils import get_temp_dir

def delete_stage_stems(stage_id: str) -> None:
    """
    Borra los stems (.wav) del stage actual, excepto full_song.wav.
    No borra otros artefactos (JSON, métricas, etc.).
    """
    # backend_root = Path(__file__).resolve().parents[2]  # .../backend
    # stage_dir = backend_root / "temp" / stage_id
    # Use get_temp_dir instead of hardcoding, to respect env vars if set in get_temp_dir logic
    stage_dir = get_temp_dir(stage_id, create=False)

    if not stage_dir.exists() or not stage_dir.is_dir():
        return

    for path in stage_dir.glob("*.wav"):
        if path.name.lower() == "full_song.wav":
            continue
        try:
            path.unlink()
            print(f"[cleanup_stage_stems] Deleted {path.name}")
        except Exception as exc:  # pragma: no cover - defensivo
            print(f"[cleanup_stage_stems] Could not delete {path}: {exc}")


def process(context: PipelineContext) -> None:
    delete_stage_stems(context.contract_id)


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python cleanup_stage_stems.py <STAGE_ID>")
        sys.exit(1)

    stage_id = sys.argv[1]
    delete_stage_stems(stage_id)


if __name__ == "__main__":
    main()
