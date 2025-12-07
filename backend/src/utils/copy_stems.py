from __future__ import annotations
import sys
from pathlib import Path

# --- hack sys.path para poder importar utils.* cuando se ejecuta como script ---
THIS_DIR = Path(__file__).resolve().parent      # .../src/utils
SRC_DIR = THIS_DIR.parent                       # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.logger import logger

try:
    from context import PipelineContext
except ImportError:
    PipelineContext = None # type: ignore


def process(context: PipelineContext, *args) -> bool:
    """
    In-memory: Copy is implicit. The next stage receives the same context object,
    so it has access to the same audio data.

    If we wanted to isolate changes, we would deep copy here, but typically
    the pipeline is sequential and modifying stems in place is desired
    (except for 'Undo' or comparison purposes, which are handled by stage.py snapshots).
    """
    # No-op for in-memory pipeline
    # logger.info("[copy_stems] In-memory mode: Skipping physical copy.")
    return True


def main() -> None:
    logger.info("[copy_stems] In-memory mode: No-op.")

if __name__ == "__main__":
    main()
