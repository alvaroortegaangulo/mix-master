from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

# --- hack sys.path para poder importar utils.* cuando se ejecuta como script ---
THIS_DIR = Path(__file__).resolve().parent      # .../src/utils
SRC_DIR = THIS_DIR.parent                       # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.logger import logger
from utils.audio_memory import perform_mixdown_in_memory

try:
    from context import PipelineContext
except ImportError:
    PipelineContext = None # type: ignore


def process(context: PipelineContext, *args) -> bool:
    """
    Realiza el mixdown de los stems usando los datos en memoria del contexto.
    Actualiza context.audio_mixdown.
    """
    if not context or not hasattr(context, 'audio_stems'):
        logger.error("[mixdown_stems] Invalid context or missing audio_stems")
        return False

    if not context.audio_stems:
        logger.warning("[mixdown_stems] No stems in memory to mix.")
        context.audio_mixdown = None
        return True

    perform_mixdown_in_memory(context)

    # Normalize if clipping (Peak > 1.0)
    if context.audio_mixdown is not None:
        peak = np.max(np.abs(context.audio_mixdown))
        if peak > 1.0:
            logger.info(f"[mixdown_stems] Normalizing mixdown (Peak: {peak:.2f})")
            context.audio_mixdown /= peak

    logger.info("[mixdown_stems] In-memory mixdown complete.")
    return True


def main() -> None:
    # Legacy CLI entry point - might not work without hydrating context from disk
    logger.error("[mixdown_stems] Cannot run standalone in in-memory mode without context hydration.")
    sys.exit(1)

if __name__ == "__main__":
    main()
