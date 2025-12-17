from backend.src.utils.diff_utils import compute_analysis_diff
import json

pre = {
    "session": {
        "noise_floor_dbfs": -50.8,
        "samplerate_hz": 48000,
        "static_val": 1.0
    },
    "stems": [
        {"file_name": "stem1.wav", "peak": -1.0}
    ]
}

post = {
    "session": {
        "noise_floor_dbfs": -50.35,
        "samplerate_hz": 48000,
        "static_val": 1.0
    },
    "stems": [
        {"file_name": "stem1.wav", "peak": -0.5}
    ]
}

diff = compute_analysis_diff(pre, post)
print(json.dumps(diff, indent=2))
