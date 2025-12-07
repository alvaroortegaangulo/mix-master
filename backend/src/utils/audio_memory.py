import io
import numpy as np
import soundfile as sf
from pathlib import Path
from typing import Dict, Tuple, Optional
from context import PipelineContext
from utils.logger import logger
from utils.job_store import JobStore

def load_stems_from_job_store(context: PipelineContext, job_store: JobStore) -> None:
    """
    Loads all audio files from Redis (JobStore) into context.audio_stems.
    """
    audio_exts = {".wav", ".aif", ".aiff", ".flac"}
    loaded_count = 0

    files_map = job_store.get_input_files(context.job_id)
    # files_map keys are bytes (Redis) -> convert to str
    # Sort for determinism
    filenames = sorted([k.decode('utf-8') for k in files_map.keys()])

    for fname in filenames:
        if fname.lower() == "full_song.wav":
            continue

        # simple check extension
        if Path(fname).suffix.lower() not in audio_exts:
            continue

        file_bytes = files_map[fname.encode('utf-8')]

        try:
            # Read from memory buffer
            with io.BytesIO(file_bytes) as bio:
                data, sr = sf.read(bio, always_2d=True, dtype='float32')

            # Set global sample rate if not set or verify consistency
            if loaded_count == 0:
                context.sample_rate = sr
            elif sr != context.sample_rate:
                logger.warning(f"[audio_memory] Sample rate mismatch: {fname} is {sr}, expected {context.sample_rate}.")
                # TODO: Resample if needed

            context.audio_stems[fname] = data
            loaded_count += 1
            logger.info(f"[audio_memory] Loaded {fname} ({data.shape}) from Redis.")

        except Exception as e:
            logger.error(f"[audio_memory] Failed to load {fname} from Redis: {e}")

    logger.info(f"[audio_memory] Loaded {loaded_count} stems from JobStore.")


def load_stems_into_memory(context: PipelineContext, source_dir: Path) -> None:
    """
    Loads all WAV/AIFF/FLAC files from source_dir into context.audio_stems.
    Sets context.sample_rate based on the first file (assumes consistency).
    """
    audio_exts = {".wav", ".aif", ".aiff", ".flac"}
    loaded_count = 0

    # Sort for determinism
    files = sorted([p for p in source_dir.iterdir() if p.is_file() and p.suffix.lower() in audio_exts])

    for file_path in files:
        if file_path.name.lower() == "full_song.wav":
            continue

        try:
            # Read with soundfile
            data, sr = sf.read(file_path, always_2d=True, dtype='float32')

            # Set global sample rate if not set or verify consistency
            if loaded_count == 0:
                context.sample_rate = sr
            elif sr != context.sample_rate:
                logger.warning(f"[audio_memory] Sample rate mismatch: {file_path.name} is {sr}, expected {context.sample_rate}. Resampling not implemented yet.")
                # TODO: Resample if needed

            context.audio_stems[file_path.name] = data
            loaded_count += 1
            logger.info(f"[audio_memory] Loaded {file_path.name} ({data.shape}) into memory.")

        except Exception as e:
            logger.error(f"[audio_memory] Failed to load {file_path.name}: {e}")

    logger.info(f"[audio_memory] Loaded {loaded_count} stems.")

def save_memory_to_disk(context: PipelineContext, target_dir: Path, save_stems: bool = True, save_mixdown: bool = True) -> None:
    """
    Saves in-memory audio to the target directory.
    Useful for creating artifacts for the frontend (like full_song.wav) or debugging.
    """
    target_dir.mkdir(parents=True, exist_ok=True)

    if save_stems:
        for name, data in context.audio_stems.items():
            out_path = target_dir / name
            try:
                sf.write(out_path, data, context.sample_rate)
            except Exception as e:
                logger.error(f"[audio_memory] Failed to write {name}: {e}")

    if save_mixdown and context.audio_mixdown is not None:
        out_path = target_dir / "full_song.wav"
        try:
            sf.write(out_path, context.audio_mixdown, context.sample_rate)
        except Exception as e:
            logger.error(f"[audio_memory] Failed to write full_song.wav: {e}")

def perform_mixdown_in_memory(context: PipelineContext) -> None:
    """
    Sums all stems in context.audio_stems and stores result in context.audio_mixdown.
    Handles different lengths by padding.
    """
    if not context.audio_stems:
        logger.warning("[audio_memory] No stems to mixdown.")
        context.audio_mixdown = None
        return

    # Find max length
    max_len = 0
    channels = 0

    for data in context.audio_stems.values():
        max_len = max(max_len, data.shape[0])
        channels = max(channels, data.shape[1])

    if max_len == 0:
        return

    mix = np.zeros((max_len, channels), dtype=np.float32)

    for data in context.audio_stems.values():
        length = data.shape[0]
        # Sum into mix
        # Handle channel mismatch (mono to stereo) if needed
        if data.shape[1] == channels:
            mix[:length, :] += data
        elif data.shape[1] == 1 and channels == 2:
            mix[:length, 0] += data[:, 0]
            mix[:length, 1] += data[:, 0]
        else:
            # Fallback or error?
            pass

    context.audio_mixdown = mix
