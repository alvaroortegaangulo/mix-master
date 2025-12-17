
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf
import librosa
import librosa.display
import json
from pathlib import Path
from utils.logger import logger
from utils.analysis_utils import compute_interactive_data

def generate_comparison_data(
    pre_audio_path: Path,
    post_audio_path: Path,
    output_dir: Path,
    stage_id: str
) -> dict:
    """
    Generates comparison data (Interactive JSON) for pre and post audio.
    Returns a dictionary with paths to the generated data relative to the stage dir.

    Legacy: Also generates 'waveform_comparison.png' for backwards compatibility if needed,
    but primarily focuses on 'comparison_interactive.json'.

    The structure of the JSON will be:
    {
       "pre": { "dynamics": ..., "spectrum": ... },
       "post": { "dynamics": ..., "spectrum": ... }
    }
    """
    files = {}

    if not pre_audio_path.exists() or not post_audio_path.exists():
        return files

    try:
        # Load audio (limit duration to 30s for performance if we were plotting,
        # but for interactive data we might want more? Let's stick to full or reasonably long)
        # However, for JSON size, we should be careful.
        # compute_interactive_data uses 100ms steps.
        # For 3 min song: 180s / 0.1 = 1800 points. 2 arrays (rms, peak) = 3600 floats.
        # That's small enough (~20KB).
        # Spectrum uses 64 bands. Tiny.
        # So we can process the full file or a reasonable chunk.
        # Let's use up to 60s to keep it fast but representative.

        y_pre, sr_pre = sf.read(pre_audio_path, always_2d=True, frames=48000*60)
        y_post, sr_post = sf.read(post_audio_path, always_2d=True, frames=48000*60)

        # Compute interactive data
        data_pre = compute_interactive_data(y_pre, sr_pre)
        data_post = compute_interactive_data(y_post, sr_post)

        comparison_data = {
            "pre": data_pre,
            "post": data_post
        }

        # Save to JSON
        json_path = output_dir / "comparison_interactive.json"
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(comparison_data, f, indent=2)

        files["interactive_comparison"] = json_path.name
        logger.logger.info(f"Generated interactive comparison data for {stage_id}")

        # --- Legacy Waveform Image (Optional / Fallback) ---
        # User asked to replace it, but maybe keep it just in case logic fails?
        # Actually user said "Quitar la imagen ... dejar solamente WAVEFORM COMPARISON (que sea interactiva)".
        # So I will NOT generate the images to save time and disk space.

    except Exception as e:
        logger.logger.error(f"Error generating comparison data for {stage_id}: {e}")

    return files
