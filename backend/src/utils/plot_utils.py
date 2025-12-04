
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf
import librosa
import librosa.display
from pathlib import Path
from utils.logger import logger

def generate_comparison_plots(
    pre_audio_path: Path,
    post_audio_path: Path,
    output_dir: Path,
    stage_id: str
) -> dict:
    """
    Generates comparison plots (Waveform and Spectrogram) for pre and post audio.
    Returns a dictionary with paths to the generated images relative to the stage dir.
    """
    images = {}

    if not pre_audio_path.exists() or not post_audio_path.exists():
        return images

    try:
        # Load audio (limit duration to 30s for performance and visualization clarity)
        y_pre, sr_pre = sf.read(pre_audio_path, always_2d=True, frames=48000*30)
        y_post, sr_post = sf.read(post_audio_path, always_2d=True, frames=48000*30)

        # Convert to mono for plotting
        y_pre_mono = np.mean(y_pre, axis=1)
        y_post_mono = np.mean(y_post, axis=1)

        # Ensure same length
        min_len = min(len(y_pre_mono), len(y_post_mono))
        y_pre_mono = y_pre_mono[:min_len]
        y_post_mono = y_post_mono[:min_len]

        # 1. Waveform Comparison
        plt.figure(figsize=(10, 4))
        plt.subplot(2, 1, 1)
        librosa.display.waveshow(y_pre_mono, sr=sr_pre, alpha=0.7, color='blue', label='Before')
        plt.title(f"{stage_id} - Waveform Before")
        plt.legend()

        plt.subplot(2, 1, 2)
        librosa.display.waveshow(y_post_mono, sr=sr_post, alpha=0.7, color='green', label='After')
        plt.title(f"{stage_id} - Waveform After")
        plt.legend()

        plt.tight_layout()
        wave_path = output_dir / f"waveform_comparison.png"
        plt.savefig(wave_path)
        plt.close()
        images['waveform'] = wave_path.name

        # 2. Spectrogram Comparison
        plt.figure(figsize=(12, 6))

        # Pre
        plt.subplot(2, 1, 1)
        D_pre = librosa.amplitude_to_db(np.abs(librosa.stft(y_pre_mono)), ref=np.max)
        librosa.display.specshow(D_pre, sr=sr_pre, x_axis='time', y_axis='log')
        plt.colorbar(format='%+2.0f dB')
        plt.title(f"{stage_id} - Spectrogram Before")

        # Post
        plt.subplot(2, 1, 2)
        D_post = librosa.amplitude_to_db(np.abs(librosa.stft(y_post_mono)), ref=np.max)
        librosa.display.specshow(D_post, sr=sr_post, x_axis='time', y_axis='log')
        plt.colorbar(format='%+2.0f dB')
        plt.title(f"{stage_id} - Spectrogram After")

        plt.tight_layout()
        spec_path = output_dir / f"spectrogram_comparison.png"
        plt.savefig(spec_path)
        plt.close()
        images['spectrogram'] = spec_path.name

    except Exception as e:
        logger.logger.error(f"Error generating plots for {stage_id}: {e}")

    return images
