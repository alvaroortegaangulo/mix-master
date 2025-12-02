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


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python mixdown_stems.py <STAGE_ID>")
        sys.exit(1)

    stage_id = sys.argv[1]

    # En modo single-job:
    #   stage_dir = PROJECT_ROOT/temp/<STAGE_ID>
    #
    # En modo multi-job (Celery, con MIX_JOB_ID/MIX_TEMP_ROOT):
    #   stage_dir = PROJECT_ROOT/temp/<MIX_JOB_ID>/<STAGE_ID>
    #   o MIX_TEMP_ROOT/<STAGE_ID> si MIX_TEMP_ROOT ya apunta a temp/<job_id>.
    stage_dir = get_temp_dir(stage_id, create=False)

    if not stage_dir.exists():
        print(f"[mixdown_stems] La carpeta de stage {stage_dir} no existe.")
        return

    # Tomar todos los .wav excepto full_song.wav (por si ya existiera)
    stem_paths = [
        p for p in stage_dir.glob("*.wav")
        if p.name.lower() != "full_song.wav"
    ]

    if not stem_paths:
        print(f"[mixdown_stems] No se han encontrado stems en {stage_dir}")
        return

    sr_ref = None
    ch_ref = None
    valid_paths = []

    # Leemos metadatos; asumimos mismo samplerate y canales (garantizado por S0_SESSION_FORMAT).
    for p in stem_paths:
        try:
            with sf.SoundFile(p, "r") as f:
                sr = f.samplerate
                ch = f.channels
        except Exception as e:
            print(f"[mixdown_stems] Aviso: no se pudo leer {p}: {e}")
            continue

        if sr_ref is None:
            sr_ref = sr
            ch_ref = ch
        else:
            if sr != sr_ref or ch != ch_ref:
                print(
                    f"[mixdown_stems] Aviso: se omite {p} por sr/canales inconsistentes "
                    f"(sr={sr}, ch={ch} vs ref sr={sr_ref}, ch={ch_ref})"
                )
                continue

        valid_paths.append(p)

    if not valid_paths or sr_ref is None or ch_ref is None:
        print(f"[mixdown_stems] No hay stems válidos para mixdown en {stage_dir}")
        return

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

    print(f"[mixdown_stems] Mixdown completado en: {out_path}")


if __name__ == "__main__":
    main()
