from utils.logger import logger
# C:\mix-master\backend\src\utils\mixdown_stems.py

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import soundfile as sf

# --- hack sys.path para poder importar utils.* cuando se ejecuta como script ---
THIS_DIR = Path(__file__).resolve().parent      # .../src/utils
SRC_DIR = THIS_DIR.parent                       # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.analysis_utils import get_temp_dir  # noqa: E402
try:
    from context import PipelineContext
except ImportError:
    PipelineContext = None # type: ignore


def process(context: PipelineContext, *args) -> bool:
    """
    Realiza el mixdown de los stems en la carpeta del stage.
    args[0] (opcional): stage_id override (si context.stage_id no es el deseado)
    """
    # Si se pasa un argumento extra (legacy calling convention en stage.py pasaba stage_id)
    # stage.py: _run_script(mixdown_script, context, stage_id) -> args=(stage_id,)
    stage_id = args[0] if args else context.stage_id

    # Resolver stage_dir usando context
    stage_dir = context.get_stage_dir(stage_id)

    if not stage_dir.exists():
        logger.logger.info(f"[mixdown_stems] La carpeta de stage {stage_dir} no existe.")
        return False # O True si queremos ser permisivos? Originalmente retornaba sin error.

    # Tomar todos los .wav excepto full_song.wav (por si ya existiera)
    stem_paths = [
        p for p in stage_dir.glob("*.wav")
        if p.name.lower() != "full_song.wav"
    ]

    if not stem_paths:
        logger.logger.info(f"[mixdown_stems] No se han encontrado stems en {stage_dir}")
        return True # No es error critico quizas?

    sr_ref = None
    ch_ref = None
    valid_paths = []

    # Leemos metadatos
    for p in stem_paths:
        try:
            with sf.SoundFile(p, "r") as f:
                sr = f.samplerate
                ch = f.channels
        except Exception as e:
            logger.logger.info(f"[mixdown_stems] Aviso: no se pudo leer {p}: {e}")
            continue

        if sr_ref is None:
            sr_ref = sr
            ch_ref = ch
        else:
            if sr != sr_ref or ch != ch_ref:
                logger.logger.info(
                    f"[mixdown_stems] Aviso: se omite {p} por sr/canales inconsistentes "
                    f"(sr={sr}, ch={ch} vs ref sr={sr_ref}, ch={ch_ref})"
                )
                continue

        valid_paths.append(p)

    if not valid_paths or sr_ref is None or ch_ref is None:
        logger.logger.info(f"[mixdown_stems] No hay stems válidos para mixdown en {stage_dir}")
        return True

    blocksize = 65536

    def _compute_peak(paths):
        peak_val = 0.0
        files = [sf.SoundFile(p, "r") for p in paths]
        try:
            while True:
                sum_block = np.zeros((blocksize, ch_ref), dtype=np.float32)
                max_len = 0
                for f in files:
                    data = f.read(blocksize, dtype="float32", always_2d=True)
                    if data.size == 0:
                        continue
                    n = data.shape[0]
                    max_len = max(max_len, n)
                    sum_block[:n, :] += data
                if max_len == 0:
                    break
                peak_val = max(peak_val, float(np.max(np.abs(sum_block[:max_len]))))
        finally:
            for f in files:
                f.close()
        return peak_val

    peak_mix = _compute_peak(valid_paths)
    if peak_mix <= 0.0:
        peak_mix = 1.0
    norm_gain = 1.0 / peak_mix if peak_mix > 1.0 else 1.0

    out_path = stage_dir / "full_song.wav"
    files = [sf.SoundFile(p, "r") for p in valid_paths]
    try:
        with sf.SoundFile(out_path, "w", samplerate=sr_ref, channels=ch_ref, subtype="FLOAT") as out_f:
            while True:
                sum_block = np.zeros((blocksize, ch_ref), dtype=np.float32)
                max_len = 0
                for f in files:
                    data = f.read(blocksize, dtype="float32", always_2d=True)
                    if data.size == 0:
                        continue
                    n = data.shape[0]
                    max_len = max(max_len, n)
                    sum_block[:n, :] += data
                if max_len == 0:
                    break
                if norm_gain != 1.0:
                    sum_block[:max_len, :] *= norm_gain
                out_f.write(sum_block[:max_len, :])
    finally:
        for f in files:
            f.close()

    logger.logger.info(f"[mixdown_stems] Mixdown completado en: {out_path}")
    return True


def main() -> None:
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python mixdown_stems.py <STAGE_ID>")
        sys.exit(1)

    stage_id = sys.argv[1]

    # Construir context legacy
    temp_dir = get_temp_dir(stage_id, create=False)
    # temp_dir es .../temp/job_id/stage_id
    temp_root = temp_dir.parent
    job_id = temp_root.name

    if 'PipelineContext' in globals() and PipelineContext:
        ctx = PipelineContext(stage_id=stage_id, job_id=job_id, temp_root=temp_root)
        process(ctx)
    else:
        # Fallback si Context no existe (raro)
        # Copiamos la logica de process pero con get_temp_dir
        # ... (aquí iría el código legacy si quisiéramos ser puristas,
        # pero es mejor asumir que process funciona con el contexto creado arriba)
        pass

if __name__ == "__main__":
    main()
