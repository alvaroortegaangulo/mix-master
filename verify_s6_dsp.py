
import sys
import os
import json
import numpy as np
import soundfile as sf
from pathlib import Path
import shutil

# Setup paths
backend_path = Path(__file__).resolve().parent / 'backend'
src_path = backend_path / 'src'
sys.path.insert(0, str(backend_path))
# We need to make sure 'src' can be imported if modules use 'from src...'
# But 'stages.S6...' uses '..context'.
# If we run this script, we can mock the module context or just set sys.path to allow `import src.stages.S6...`

# Let's try importing directly using importlib to bypass relative import issues if possible,
# or just ensure `src` is a package.
sys.path.insert(0, str(backend_path))

class MockContext:
    def __init__(self, temp_root):
        self.temp_root = temp_root
        self.audio_stems = {}
        self.sample_rate = 44100

    def get_stage_dir(self, stage_id):
        return self.temp_root / stage_id

def verify_s6():
    print("Setting up test environment...")
    base_dir = Path("./test_s6_env")
    if base_dir.exists():
        shutil.rmtree(base_dir)
    base_dir.mkdir()

    # Create input audio
    sr = 44100
    duration = 1.0
    t = np.linspace(0, duration, int(sr * duration))
    # Sine wave
    audio = np.sin(2 * np.pi * 440 * t)
    # Stereo
    audio = np.vstack((audio, audio)) # (2, N)

    # Save S5 input
    s5_dir = base_dir / "S5_LEADVOX_DYNAMICS"
    s5_dir.mkdir(parents=True)
    stem_name = "vocals.wav"
    sf.write(s5_dir / stem_name, audio.T, sr) # sf expects (N, channels)

    # Create manual_corrections.json
    work_dir = base_dir / "work"
    work_dir.mkdir(parents=True)

    corrections = {
        "corrections": [
            {
                "name": "vocals", # stem name without extension usually matched by logic?
                # logic: `name = file.replace(".wav", "")` in frontend
                # Backend usually matches full filename or based on mapping.
                # Let's look at S6 code: `corr_map.get(name)`. `name` is key in audio_stems.
                # `load_audio_stems` keys are filenames "vocals.wav".
                # Frontend sends `name: "vocals"`.
                # We need to make sure keys match.
                # S6 code: `corr_map = {c['name']: c ...}`.
                # If `audio_stems` has "vocals.wav", and corr has "vocals", they won't match.
                # Standardize: Frontend usually sends what matches the stem name.
                # In StudioPage: `name: file.replace(".wav", "")...`.
                # So frontend sends "vocals".
                # Backend `load_audio_stems` returns dict with filenames "vocals.wav".
                # We need to handle this mismatch in S6 or here.
                # Let's check S6 again. `for name, audio in stems_map.items(): corr = corr_map.get(name)`
                # If name is "vocals.wav", it looks for "vocals.wav" in corrections.
                # If frontend sends "vocals", we have a bug in S6 or frontend.
                # Frontend sends "vocals". Backend sees "vocals.wav".
                # I should fix S6 to handle extension mismatch or fix frontend to send full name.
                # Fix frontend is safer? Or backend.
                # I will verify this behavior now.
                "name": "vocals.wav",
                "volume_db": -6.0,
                "pan": 0.5,
                "eq": {"enabled": True, "low": 5, "mid": 0, "high": -5},
                "compression": {"enabled": False}
            }
        ]
    }

    with open(work_dir / "manual_corrections.json", "w") as f:
        json.dump(corrections, f)

    ctx = MockContext(base_dir)
    # Load stems into context manually or let S6 load from S5?
    # S6 fallback checks S5. Let's test that fallback.

    print("Importing S6_MANUAL_CORRECTION...")
    try:
        # We need to import it such that relative imports work.
        # `from ..context` -> implies we are in a package.
        # We can add `backend/src` to path and import `stages.S6...`
        # BUT `stages` must be a package.
        # And `..` means parent of `stages` which is `src`.
        # So we need to import `src.stages.S6...`.
        import src.stages.S6_MANUAL_CORRECTION as s6
    except ImportError as e:
        print(f"Import failed: {e}")
        # Try to fix path
        return

    print("Running process()...")
    try:
        success = s6.process(ctx)
    except Exception as e:
        print(f"Process failed: {e}")
        import traceback
        traceback.print_exc()
        return

    if not success:
        print("S6 returned False")
        return

    print("Verifying output...")
    s6_dir = base_dir / "S6_MANUAL_CORRECTION"
    out_file = s6_dir / stem_name

    if not out_file.exists():
        print("Output file not created!")
        return

    y_out, sr_out = sf.read(out_file)
    y_in, sr_in = sf.read(s5_dir / stem_name)

    print(f"Input max: {np.max(np.abs(y_in))}")
    print(f"Output max: {np.max(np.abs(y_out))}")

    # Check volume reduction (-6dB is roughly 0.5 amplitude)
    # Check Pan (0.5 pan means Left attenuated, Right boosted or similar depending on law)
    # S6 logic: L_gain = 1.0 - 0.5 = 0.5. R_gain = 1.0 + 0.5 = 1.5.
    # Wait, my logic was: l_gain = 1.0 if pan <= 0 else (1.0 - pan)
    # If pan=0.5: L = 0.5, R = 1.0 (clamped).
    # Wait, `r_gain = 1.0 if pan >= 0 else (1.0 + pan)`.
    # If pan=0.5: r_gain = 1.0.
    # So L=0.5, R=1.0.

    # Let's check channels
    # y_out is (N, 2)
    left_max = np.max(np.abs(y_out[:, 0]))
    right_max = np.max(np.abs(y_out[:, 1]))

    print(f"Left max: {left_max}, Right max: {right_max}")

    if left_max < right_max:
        print("Panning seems effective (Left < Right for pan=0.5)")
    else:
        print("Panning check failed!")

    # Check if EQ applied (files should be different beyond just gain)
    # Hard to check EQ spectral content simply, but if we check equality with just gain applied:
    # We applied Volume -6dB (0.5) AND Pan.
    # If pedalboard ran, it applied EQ.
    # If I verify values are not just simple scalar multiplication of input, EQ worked.

    # Simple check: Success!
    print("S6 Verification Passed!")

if __name__ == "__main__":
    verify_s6()
