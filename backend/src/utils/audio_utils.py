
import logging
import soundfile as sf
import numpy as np
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

def load_audio_stems(directory: Path) -> Dict[str, np.ndarray]:
    """
    Loads all WAV files in a directory into a dict of {filename: numpy_array}.
    Returns audio as float32.
    """
    stems = {}
    if not directory.exists():
        return stems

    for f in directory.iterdir():
        if f.suffix.lower() == '.wav' and f.name != 'full_song.wav':
            try:
                data, sr = sf.read(f, dtype='float32')
                # Ensure shape is (channels, samples) for processing?
                # soundfile returns (samples, channels)
                # Pedalboard expects (channels, samples)
                if data.ndim == 2:
                    data = data.T
                elif data.ndim == 1:
                    data = data[np.newaxis, :]
                stems[f.name] = data
            except Exception as e:
                logger.error(f"Failed to load stem {f.name}: {e}")
    return stems

def save_audio_stems(directory: Path, stems: Dict[str, np.ndarray], sample_rate: int):
    """
    Saves a dict of {filename: numpy_array} to a directory.
    Expects (channels, samples) format.
    """
    if not directory.exists():
        directory.mkdir(parents=True, exist_ok=True)

    for name, data in stems.items():
        try:
            # Soundfile expects (samples, channels)
            path = directory / name
            sf.write(path, data.T, sample_rate)
        except Exception as e:
            logger.error(f"Failed to save stem {name}: {e}")
