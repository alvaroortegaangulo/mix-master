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

    data_list = []
    sr_ref = None
    ch_ref = None

    # Leemos todos los stems; asumimos mismo samplerate y canales
    # (garantizado por S0_SESSION_FORMAT). Si alguno no coincide, se omite.
    for p in stem_paths:
        try:
            data, sr = sf.read(p, always_2d=True)  # shape: (n_samples, n_channels)
        except Exception as e:
            print(f"[mixdown_stems] Aviso: no se pudo leer {p}: {e}")
            continue

        data = data.astype(np.float32)

        if sr_ref is None:
            sr_ref = sr
            ch_ref = data.shape[1]
        else:
            if sr != sr_ref or data.shape[1] != ch_ref:
                print(
                    f"[mixdown_stems] Aviso: se omite {p} por sr/canales inconsistentes "
                    f"(sr={sr}, ch={data.shape[1]} vs ref sr={sr_ref}, ch={ch_ref})"
                )
                continue

        data_list.append(data)

    if not data_list or sr_ref is None or ch_ref is None:
        print(f"[mixdown_stems] No hay stems válidos para mixdown en {stage_dir}")
        return

    max_len = max(d.shape[0] for d in data_list)
    mix = np.zeros((max_len, ch_ref), dtype=np.float32)

    # Suma directa, rellenando con ceros donde falten muestras
    for d in data_list:
        n = d.shape[0]
        mix[:n, :] += d

    # Evitar clipping: si excede 1.0, normalizamos
    peak = float(np.max(np.abs(mix)))
    if peak > 1.0 and peak > 0.0:
        mix /= peak

    out_path = stage_dir / "full_song.wav"
    sf.write(out_path, mix, sr_ref)

    print(f"[mixdown_stems] Mixdown completado en: {out_path}")


if __name__ == "__main__":
    main()
