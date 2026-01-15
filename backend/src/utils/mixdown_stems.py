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

from utils.logger import logger
from utils.analysis_utils import get_temp_dir  # noqa: E402

try:
    from context import PipelineContext
except ImportError:
    PipelineContext = None # type: ignore

# 512 MB limit for memory-based processing
MAX_MEMORY_BYTES = 512 * 1024 * 1024

def _process_streaming(valid_paths, out_path, sr_ref, ch_ref, norm_gain_hint=None):
    """
    Original block-based streaming implementation.
    Safely handles arbitrarily large files with constant memory usage.

    If norm_gain_hint is provided, it skips the first pass.
    Otherwise, it performs two passes (peak detection + write).
    """
    blocksize = 65536

    norm_gain = norm_gain_hint

    # Pass 1: Compute peak if needed
    if norm_gain is None:
        peak_val = 0.0
        files = [sf.SoundFile(p, "r") for p in valid_paths]
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

        peak_mix = peak_val
        if peak_mix <= 0.0:
            peak_mix = 1.0
        norm_gain = 1.0 / peak_mix if peak_mix > 1.0 else 1.0

    # Pass 2: Write output
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

    return True

def _process_memory(valid_paths, out_path, sr_ref, ch_ref, max_frames):
    """
    Optimized single-pass (memory-based) implementation.
    Reads all stems into memory, sums, normalizes, and writes once.
    """
    try:
        # Allocate accumulator
        mix_buffer = np.zeros((max_frames, ch_ref), dtype=np.float32)

        # Accumulate stems
        for p in valid_paths:
            data, _ = sf.read(p, always_2d=True, dtype='float32')
            n_frames = min(data.shape[0], max_frames)
            mix_buffer[:n_frames, :] += data[:n_frames, :]

        # Compute peak
        peak_mix = np.max(np.abs(mix_buffer)) if mix_buffer.size > 0 else 0.0

        if peak_mix <= 0.0:
            peak_mix = 1.0

        # Normalize in place
        if peak_mix > 1.0:
            mix_buffer *= (1.0 / peak_mix)

        # Write to disk
        sf.write(out_path, mix_buffer, sr_ref, subtype='FLOAT')
        return True

    except Exception as e:
        logger.logger.error(f"[mixdown_stems] Memory processing failed, falling back to streaming. Error: {e}")
        return False

def process(context: PipelineContext, *args) -> bool:
    """
    Realiza el mixdown de los stems en la carpeta del stage.
    args[0] (opcional): stage_id override (si context.stage_id no es el deseado)
    """
    stage_id = args[0] if args else context.stage_id

    # Resolver stage_dir usando context
    stage_dir = context.get_stage_dir(stage_id)

    if not stage_dir.exists():
        logger.logger.info(f"[mixdown_stems] La carpeta de stage {stage_dir} no existe.")
        return False

    # Tomar todos los .wav excepto full_song.wav (por si ya existiera)
    stem_paths = [
        p for p in stage_dir.glob("*.wav")
        if p.name.lower() != "full_song.wav"
    ]

    if not stem_paths:
        logger.logger.info(f"[mixdown_stems] No se han encontrado stems en {stage_dir}")
        return True

    sr_ref = None
    ch_ref = None
    valid_paths = []
    max_frames_all = 0

    # Leemos metadatos
    for p in stem_paths:
        try:
            with sf.SoundFile(p, "r") as f:
                sr = f.samplerate
                ch = f.channels
                frames = f.frames
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
        max_frames_all = max(max_frames_all, frames)

    if not valid_paths or sr_ref is None or ch_ref is None:
        logger.logger.info(f"[mixdown_stems] No hay stems válidos para mixdown en {stage_dir}")
        return True

    out_path = stage_dir / "full_song.wav"

    # Calculate estimated memory usage
    # Buffer size: max_frames * channels * 4 bytes (float32)
    estimated_memory = max_frames_all * ch_ref * 4

    use_memory = estimated_memory <= MAX_MEMORY_BYTES

    if use_memory:
        logger.logger.info(f"[mixdown_stems] Using memory strategy (Est: {estimated_memory/1024/1024:.1f} MB)")
        success = _process_memory(valid_paths, out_path, sr_ref, ch_ref, max_frames_all)
        if success:
            logger.logger.info(f"[mixdown_stems] Mixdown completado en: {out_path}")
            return True
        # If failed, fall through to streaming

    logger.logger.info(f"[mixdown_stems] Using streaming strategy")
    result = _process_streaming(valid_paths, out_path, sr_ref, ch_ref)

    if result:
        logger.logger.info(f"[mixdown_stems] Mixdown completado en: {out_path}")

    return result


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
        pass

if __name__ == "__main__":
    main()
