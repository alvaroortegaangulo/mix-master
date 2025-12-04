
import numpy as np
import soundfile as sf
from pathlib import Path
from utils.plot_utils import generate_comparison_plots
import json
import shutil
import os

def test_backend():
    print("Testing plot_utils...")
    # 1. Create dummy audio
    sr = 44100
    t = np.linspace(0, 5, sr*5)
    y1 = np.sin(2*np.pi*440*t) # 440Hz
    y2 = np.sin(2*np.pi*880*t) # 880Hz

    test_dir = Path("test_backend_output")
    test_dir.mkdir(exist_ok=True)

    pre_path = test_dir / "pre.wav"
    post_path = test_dir / "post.wav"

    sf.write(pre_path, y1, sr)
    sf.write(post_path, y2, sr)

    # 2. Test plot generation
    images = generate_comparison_plots(pre_path, post_path, test_dir, "TEST_STAGE")
    print(f"Generated images: {images}")

    if not (test_dir / "waveform_comparison.png").exists():
        print("FAIL: Waveform image not created")
    if not (test_dir / "spectrogram_comparison.png").exists():
        print("FAIL: Spectrogram image not created")

    # 3. Test S11 Logic (Mocking environment)
    print("\nTesting S11 Report Logic...")

    # Setup mock file structure
    # temp/job_id/S11...
    # temp/job_id/S7...

    job_dir = test_dir / "job_123"
    s11_dir = job_dir / "S11_REPORT_GENERATION"
    s7_dir = job_dir / "S7_MIXBUS_TONAL_BALANCE"

    s11_dir.mkdir(parents=True, exist_ok=True)
    s7_dir.mkdir(parents=True, exist_ok=True)

    # Mock S7 metrics
    with open(s7_dir / "tonal_metrics_S7_MIXBUS_TONAL_BALANCE.json", "w") as f:
        json.dump({"eq_gains_db": {"low": 2.5, "mid": -1.0}}, f)

    # Mock S7 images (copy from step 2)
    shutil.copy(test_dir / "waveform_comparison.png", s7_dir / "waveform_comparison.png")
    shutil.copy(test_dir / "spectrogram_comparison.png", s7_dir / "spectrogram_comparison.png")

    # Mock S11 Analysis Input
    s11_analysis = {
        "session": {
            "report": {
                "pipeline_version": "1.0",
                "generated_at_utc": "2023-01-01T00:00:00Z",
                "style_preset": "Default",
                "stages": [
                    {
                        "contract_id": "S7_MIXBUS_TONAL_BALANCE",
                        "status": "analyzed"
                    }
                ],
                "final_metrics": {}
            }
        }
    }

    with open(s11_dir / "analysis_S11_REPORT_GENERATION.json", "w") as f:
        json.dump(s11_analysis, f)

    # Run S11 (Importing it effectively)
    # We need to set up sys.path or import the function
    import sys
    sys.path.append("backend/src")
    from stages.S11_REPORT_GENERATION import _enrich_report_with_parameters_and_images

    # Enrich
    report = s11_analysis["session"]["report"]
    _enrich_report_with_parameters_and_images(report, s11_dir)

    print("Enriched Report Stage 0:", json.dumps(report["stages"][0], indent=2))

    # Verify
    s7_report = report["stages"][0]
    if "EQ Gains (dB)" not in s7_report.get("parameters", {}):
         print("FAIL: S7 parameters not extracted")
    else:
         print("PASS: S7 parameters extracted")

    if "waveform" not in s7_report.get("images", {}):
         print("FAIL: S7 images not linked")
    else:
         print("PASS: S7 images linked")

    # Check file copy
    copied_img = s11_dir / "S7_MIXBUS_TONAL_BALANCE_waveform_comparison.png"
    if copied_img.exists():
        print("PASS: Image copied to report folder")
    else:
        print(f"FAIL: Image not copied to {copied_img}")

if __name__ == "__main__":
    try:
        test_backend()
    except Exception as e:
        print(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
