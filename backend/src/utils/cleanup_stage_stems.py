from __future__ import annotations

import sys
from pathlib import Path


def delete_stage_stems(stage_id: str) -> None:
    """
    Borra los stems (.wav) del stage actual, excepto full_song.wav.
    No borra otros artefactos (JSON, métricas, etc.).
    """
    backend_root = Path(__file__).resolve().parents[2]  # .../backend
    stage_dir = backend_root / "temp" / stage_id

    if not stage_dir.exists() or not stage_dir.is_dir():
        return

    for path in stage_dir.glob("*.wav"):
        if path.name.lower() == "full_song.wav":
            continue
        try:
            path.unlink()
            print(f"[cleanup_stage_stems] Deleted {path.name}")
        except Exception as exc:  # pragma: no cover - defensivo
            print(f"[cleanup_stage_stems] Could not delete {path}: {exc}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python cleanup_stage_stems.py <STAGE_ID>")
        sys.exit(1)

    stage_id = sys.argv[1]
    delete_stage_stems(stage_id)


if __name__ == "__main__":
    main()
