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
    Copia stems de src_stage a dst_stage.
    args puede ser (src_stage, dst_stage) o (dst_stage) si src es context.stage_id?
    stage.py llama a: _run_script(copy_script, context, stage_id, next_contract_id)
    => args = (stage_id, next_contract_id)
    """
    if len(args) < 2:
        logger.logger.info("[copy_stems] Error: Se requieren src_stage_id y dst_stage_id en args")
        return False

    src_stage_id = args[0]
    dst_stage_id = args[1]

    # Resolver directorios usando contexto
    src_dir = context.get_stage_dir(src_stage_id)
    dst_dir = context.get_stage_dir(dst_stage_id)

    if not dst_dir.exists():
        dst_dir.mkdir(parents=True, exist_ok=True)

    if not src_dir.exists():
        logger.logger.info(
            f"[copy_stems] Aviso: carpeta origen {src_dir} no existe; "
            f"no se copian stems de {src_stage_id} a {dst_stage_id}."
        )
        return True # No es error fatal, el pipeline continua

    audio_exts = {".wav", ".aif", ".aiff", ".flac", ".mp3", ".m4a", ".ogg", ".aac"}
    count = 0
    for audio_path in src_dir.glob("*"):
        if not audio_path.is_file():
            continue
        if audio_path.suffix.lower() not in audio_exts:
            continue
        # No copiar el mixdown dentro del loop de stems (se copia aparte)
        if audio_path.name.lower() == "full_song.wav":
            continue
        shutil.copy2(audio_path, dst_dir / audio_path.name)
        count += 1

    full_song_src = src_dir / "full_song.wav"
    if full_song_src.exists():
        shutil.copy2(full_song_src, dst_dir / full_song_src.name)
        logger.logger.info(
            f"[copy_stems] Copiado full_song.wav de {src_stage_id} a {dst_stage_id}"
        )

    # Copiar session_config.json si existe
    config_src = src_dir / "session_config.json"
    if config_src.exists():
        shutil.copy2(config_src, dst_dir / "session_config.json")

    logger.logger.info(f"[copy_stems] Copiados {count} stems de {src_stage_id} a {dst_stage_id}")
    return True


def main() -> None:
    if len(sys.argv) < 3:
        logger.logger.info("Uso: python copy_stems.py <SRC_STAGE_ID> <DST_STAGE_ID>")
        sys.exit(1)

    src_stage_id = sys.argv[1]
    dst_stage_id = sys.argv[2]

    # Construir context legacy
    temp_dir = get_temp_dir(src_stage_id, create=False)
    temp_root = temp_dir.parent
    job_id = temp_root.name

    if 'PipelineContext' in globals() and PipelineContext:
        ctx = PipelineContext(stage_id=src_stage_id, job_id=job_id, temp_root=temp_root)
        process(ctx, src_stage_id, dst_stage_id)

if __name__ == "__main__":
    main()
