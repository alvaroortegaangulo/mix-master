# C:\mix-master\backend\src\utils\copy_stems.py

from __future__ import annotations

import sys
import shutil
from pathlib import Path

# --- hack sys.path para poder importar utils.* cuando se ejecuta como script ---
THIS_DIR = Path(__file__).resolve().parent      # .../src/utils
SRC_DIR = THIS_DIR.parent                       # .../src
if str(SRC_DIR) not in sys.argv:
    # Nota: comprobamos en sys.path, no en sys.argv
    import sys as _sys
    if str(SRC_DIR) not in _sys.path:
        _sys.path.insert(0, str(SRC_DIR))

from utils.analysis_utils import get_temp_dir  # noqa: E402


def main() -> None:
    if len(sys.argv) < 3:
        print("Uso: python copy_stems.py <SRC_STAGE_ID> <DST_STAGE_ID>")
        sys.exit(1)

    src_stage_id = sys.argv[1]
    dst_stage_id = sys.argv[2]

    # En modo single-job:
    #   src_dir = PROJECT_ROOT/temp/<SRC_STAGE_ID>
    #   dst_dir = PROJECT_ROOT/temp/<DST_STAGE_ID>
    #
    # En modo multi-job (Celery, con MIX_JOB_ID/MIX_TEMP_ROOT):
    #   src_dir = PROJECT_ROOT/temp/<MIX_JOB_ID>/<SRC_STAGE_ID>
    #   dst_dir = PROJECT_ROOT/temp/<MIX_JOB_ID>/<DST_STAGE_ID>
    #
    # La lógica está encapsulada en get_temp_dir.
    src_dir = get_temp_dir(src_stage_id, create=False)
    dst_dir = get_temp_dir(dst_stage_id, create=True)

    if not src_dir.exists():
        print(
            f"[copy_stems] Aviso: carpeta origen {src_dir} no existe; "
            f"no se copian stems de {src_stage_id} a {dst_stage_id}."
        )
        return

    count = 0
    for wav_path in src_dir.glob("*.wav"):
        # No copiar el mixdown
        if wav_path.name.lower() == "full_song.wav":
            continue
        shutil.copy2(wav_path, dst_dir / wav_path.name)
        count += 1

    # Copiar session_config.json si existe
    config_src = src_dir / "session_config.json"
    if config_src.exists():
        shutil.copy2(config_src, dst_dir / "session_config.json")

    print(f"[copy_stems] Copiados {count} stems de {src_stage_id} a {dst_stage_id}")


if __name__ == "__main__":
    main()
