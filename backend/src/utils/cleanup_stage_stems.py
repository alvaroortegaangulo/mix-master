from __future__ import annotations
import sys
import shutil
from pathlib import Path

# --- hack sys.path para poder importar utils.* cuando se ejecuta como script ---
THIS_DIR = Path(__file__).resolve().parent      # .../src/utils
SRC_DIR = THIS_DIR.parent                       # .../src
if str(SRC_DIR) not in sys.argv:
    # Nota: comprobamos en sys.path, no en sys.argv
    import sys as _sys
    if str(SRC_DIR) not in _sys.path:
        _sys.path.insert(0, str(SRC_DIR))

from utils.logger import logger
from utils.analysis_utils import get_temp_dir  # noqa: E402

try:
    from context import PipelineContext
except ImportError:
    PipelineContext = None # type: ignore


def process(context: PipelineContext, *args) -> bool:
    """
    Limpia los stems (WAVs) de un stage para ahorrar espacio,
    PERO conserva full_song.wav y los JSONs de análisis/métricas.
    """
    stage_id = args[0] if args else context.stage_id
    stage_dir = context.get_stage_dir(stage_id)

    if not stage_dir.exists():
        logger.logger.info(f"[cleanup] La carpeta de stage {stage_dir} no existe.")
        return True

    # Definir qué conservar
    # - full_song.wav (es el resultado mixdown de la etapa)
    # - *.json (análisis, métricas, config)
    # - *.txt / logs (opcional)

    # Borrar todo lo demás (stems individuales)

    deleted_count = 0
    size_freed = 0

    for item in stage_dir.iterdir():
        if item.is_file():
            # Conservar JSONs
            if item.suffix.lower() == ".json":
                continue
            # Conservar full_song.wav
            if item.name.lower() == "full_song.wav":
                continue
            # Conservar imágenes generadas para el reporte (waveform/spectrogram)
            if item.suffix.lower() in [".png", ".jpg", ".jpeg"]:
                continue

            # Borrar wavs (stems), aiffs, flacs, etc.
            if item.suffix.lower() in [".wav", ".aif", ".aiff", ".flac", ".mp3"]:
                try:
                    s = item.stat().st_size
                    item.unlink()
                    deleted_count += 1
                    size_freed += s
                except Exception as e:
                    logger.logger.info(f"[cleanup] Error borrando {item.name}: {e}")

    mb_freed = size_freed / (1024 * 1024)
    if deleted_count > 0:
        logger.logger.info(f"[cleanup] Borrados {deleted_count} archivos en {stage_id}, liberados {mb_freed:.2f} MB.")
    else:
        # logger.logger.info(f"[cleanup] Nada que borrar en {stage_id}.")
        pass

    return True


def main() -> None:
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python cleanup_stage_stems.py <STAGE_ID>")
        sys.exit(1)

    stage_id = sys.argv[1]

    # Construir context legacy
    temp_dir = get_temp_dir(stage_id, create=False)
    temp_root = temp_dir.parent
    job_id = temp_root.name

    if 'PipelineContext' in globals() and PipelineContext:
        ctx = PipelineContext(stage_id=stage_id, job_id=job_id, temp_root=temp_root)
        process(ctx)
    else:
        # Fallback simple
        pass
        # (copiar logica de process usando get_temp_dir)

if __name__ == "__main__":
    main()
