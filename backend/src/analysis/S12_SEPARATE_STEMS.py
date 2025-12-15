from __future__ import annotations

import sys
import json
from pathlib import Path
from typing import Dict, Any, Optional

THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.analysis_utils import (  # type: ignore  # noqa: E402
    load_contract,
    get_temp_dir,
)


def _inspect_stage_stems(temp_dir: Path) -> Dict[str, Any]:
    exts = {".wav", ".flac", ".aiff", ".aif", ".ogg", ".m4a", ".mp3"}
    stems: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    for p in sorted(temp_dir.glob("*")):
        if p.is_file() and p.suffix.lower() in exts and p.name.lower() != "full_song.wav":
            stems.append({"name": p.name, "bytes": int(p.stat().st_size)})
            seen_names.add(p.name)

    legacy_dir = temp_dir / "stems"
    if legacy_dir.exists():
        for p in sorted(legacy_dir.glob("*")):
            if p.is_file() and p.suffix.lower() in exts and p.name not in seen_names:
                stems.append({"name": p.name, "bytes": int(p.stat().st_size)})
                seen_names.add(p.name)

    return {
        "stems_dir": str(temp_dir),
        "stems_dir_legacy": str(legacy_dir),
        "stems_count": len(stems),
        "stems_files": stems,
        "stems_ready": len(stems) >= 2,
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python S12_SEPARATE_STEMS.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]
    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {}) or {}
    limits: Dict[str, Any] = contract.get("limits", {}) or {}
    stage_id: Optional[str] = contract.get("stage_id")

    temp_dir = get_temp_dir(contract_id, create=True)
    stems_info = _inspect_stage_stems(temp_dir)
    full_song_path = temp_dir / "full_song.wav"

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "source_full_song_exists": full_song_path.exists(),
            "source_full_song_path": str(full_song_path) if full_song_path.exists() else None,
            **stems_info,
        },
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    print(f"[S12_SEPARATE_STEMS] Análisis completado. JSON: {output_path}")


if __name__ == "__main__":
    main()
