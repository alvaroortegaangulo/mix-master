# C:\mix-master\backend\src\analysis\S6_BUS_REVERB_STYLE.py

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple
import os

# --- hack para importar utils ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from utils.analysis_utils import (  # noqa: E402
    load_contract,
    get_temp_dir,
    sf_read_limited,
)
from utils.session_utils import load_session_config  # noqa: E402
from utils.profiles_utils import get_instrument_family  # noqa: E402


def _compute_rms_lufs_like(y: np.ndarray) -> float:
    """
    Aproximación simple de LUFS integrados: usar RMS global en dBFS.
    Nos interesa la diferencia entre dry y reverb, no el valor absoluto.
    """
    arr = np.asarray(y, dtype=np.float32)
    if arr.ndim > 1:
        arr = np.mean(arr, axis=1)
    if arr.size == 0:
        return float("-inf")
    rms = float(np.sqrt(np.mean(arr**2)))
    if rms <= 0.0:
        return float("-inf")
    return 20.0 * np.log10(rms)


def _get_reverb_profile_for(style_preset: str, family: str) -> Dict[str, Any]:
    """
    Devuelve un perfil de reverb minimalista por estilo y familia.

    Campos:
      - reverb_type: descripción textual.
      - rt60_s: tiempo de decaimiento aproximado.
      - base_send_db: nivel de envío nominal (negativo, en dB).
    """
    style = (style_preset or "Default").lower()
    fam = family

    # Valores por defecto muy conservadores
    profile = {
        "reverb_type": "room_short",
        "rt60_s": 0.8,
        "base_send_db": -18.0,
    }

    # Flamenco / Rumba: rooms cortas, poco tail
    if "flamenco" in style or "rumba" in style:
        if fam == "Drums":
            profile.update(
                {"reverb_type": "room_short", "rt60_s": 0.5, "base_send_db": -20.0}
            )
        elif fam == "LeadVox":
            profile.update(
                {"reverb_type": "plate_short", "rt60_s": 0.8, "base_send_db": -18.0}
            )
        elif fam in ("Guitars", "KeysSynths"):
            profile.update(
                {"reverb_type": "room_short", "rt60_s": 0.6, "base_send_db": -22.0}
            )
        elif fam in ("FX", "Ambience"):
            profile.update(
                {"reverb_type": "hall_short", "rt60_s": 1.2, "base_send_db": -20.0}
            )

    # Urbano / Trap
    elif "urbano" in style or "trap" in style:
        if fam == "Drums":
            profile.update(
                {"reverb_type": "room_mid", "rt60_s": 0.7, "base_send_db": -20.0}
            )
        elif fam == "LeadVox":
            profile.update(
                {"reverb_type": "plate_mid", "rt60_s": 1.2, "base_send_db": -16.0}
            )
        elif fam in ("FX", "Ambience"):
            profile.update(
                {"reverb_type": "hall_mid", "rt60_s": 2.0, "base_send_db": -18.0}
            )

    # EDM / Club
    elif "edm" in style or "club" in style:
        if fam == "Drums":
            profile.update(
                {"reverb_type": "room_tight", "rt60_s": 0.6, "base_send_db": -22.0}
            )
        elif fam == "LeadVox":
            profile.update(
                {"reverb_type": "plate_mid", "rt60_s": 1.4, "base_send_db": -16.0}
            )
        elif fam in ("FX", "Ambience", "KeysSynths"):
            profile.update(
                {"reverb_type": "hall_long", "rt60_s": 3.0, "base_send_db": -18.0}
            )

    # Acústico / Jazz
    elif "acoustic" in style or "jazz" in style or "acústico" in style:
        if fam == "Drums":
            profile.update(
                {"reverb_type": "room_natural", "rt60_s": 1.0, "base_send_db": -20.0}
            )
        elif fam == "LeadVox":
            profile.update(
                {"reverb_type": "room_natural", "rt60_s": 1.4, "base_send_db": -18.0}
            )
        elif fam in ("Guitars", "KeysSynths"):
            profile.update(
                {"reverb_type": "room_natural", "rt60_s": 1.2, "base_send_db": -20.0}
            )

    # Otros estilos / por defecto usan profile base
    
    # --- GLOBAL TRIM: hacer la reverb mucho más sutil por defecto ---
    # Bajamos todos los envíos 6 dB para que el reverb arranque más discreto.
    GLOBAL_REVERB_TRIM_DB = 6.0
    profile["base_send_db"] = float(profile.get("base_send_db", -18.0)) - GLOBAL_REVERB_TRIM_DB

    return profile


def _analyze_stem(
    args: Tuple[Path, str, str]
) -> Dict[str, Any]:
    """

    Recibe:
      - stem_path: ruta al .wav
      - inst_prof: instrument_profile
      - style_preset: preset de estilo de la sesión

    Devuelve el dict de análisis por stem más un mensaje de log.
    """
    stem_path, inst_prof, style_preset = args
    fname = stem_path.name
    family = get_instrument_family(inst_prof)
    reverb_profile = _get_reverb_profile_for(style_preset, family)

    log_msg = (
        f"[S6_BUS_REVERB_STYLE] {fname}: inst={inst_prof}, fam={family}, "
        f"type={reverb_profile['reverb_type']}, rt60={reverb_profile['rt60_s']:.2f}s, "
        f"base_send={reverb_profile['base_send_db']:.1f} dB."
    )

    return {
        "file_name": fname,
        "file_path": str(stem_path),
        "instrument_profile": inst_prof,
        "family": family,
        "reverb_profile": reverb_profile,
        "log_msg": log_msg,
    }


def main() -> None:
    """
    Análisis para el contrato S6_BUS_REVERB_STYLE.

    Uso desde stage.py:
        python analysis/S6_BUS_REVERB_STYLE.py S6_BUS_REVERB_STYLE
    """
    if len(sys.argv) < 2:
        print("Uso: python S6_BUS_REVERB_STYLE.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S6_BUS_REVERB_STYLE"

    # 1) Cargar contrato
    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    offset_min_db = float(metrics.get("reverb_return_lufs_offset_min_db", -24.0))
    offset_max_db = float(metrics.get("reverb_return_lufs_offset_max_db", -8.0))
    max_send_change_db = float(limits.get("max_send_level_change_db_per_pass", 2.0))

    # 2) temp/<contract_id> y session_config
    temp_dir = get_temp_dir(contract_id, create=True)
    cfg = load_session_config(contract_id)
    style_preset = cfg["style_preset"]
    instrument_by_file = cfg["instrument_by_file"]

    # 3) Leer mix dry desde full_song.wav si existe
    full_song_path = temp_dir / "full_song.wav"
    dry_lufs = float("-inf")
    if full_song_path.exists():
        try:
            y_mix, sr_mix = sf_read_limited(full_song_path, always_2d=False)
            dry_lufs = _compute_rms_lufs_like(y_mix)
            print(
                f"[S6_BUS_REVERB_STYLE] Mix dry (full_song.wav): "
                f"aprox_LUFS={dry_lufs:.2f} dB."
            )
        except Exception as e:
            print(
                f"[S6_BUS_REVERB_STYLE] Aviso: no se puede leer full_song.wav: {e}."
            )

    # 4) Stems del stage (excluyendo full_song.wav)
    stem_files: List[Path] = sorted(
        p for p in temp_dir.glob("*.wav")
        if p.name.lower() != "full_song.wav"
    )

    # 5) Preparar tareas para análisis en serie
    tasks: List[Tuple[Path, str, str]] = []
    for p in stem_files:
        fname = p.name
        inst_prof = instrument_by_file.get(fname, "Other")
        tasks.append((p, inst_prof, style_preset))

    stems_analysis: List[Dict[str, Any]] = []

    if tasks:
        results: List[Dict[str, Any]] = [_analyze_stem(t) for t in tasks]
    else:
        results = []

    # 6) Recoger resultados y logs
    for stem_entry in results:
        log_msg = stem_entry.pop("log_msg", None)
        if log_msg:
            print(log_msg)
        stems_analysis.append(stem_entry)

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "dry_mix_lufs": dry_lufs,
            "reverb_return_lufs_offset_min_db": offset_min_db,
            "reverb_return_lufs_offset_max_db": offset_max_db,
            "max_send_level_change_db_per_pass": max_send_change_db,
        },
        "stems": stems_analysis,
    }

    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    print(
        f"[S6_BUS_REVERB_STYLE] Análisis completado para {len(stems_analysis)} stems. "
        f"JSON: {output_path}"
    )


if __name__ == "__main__":
    main()
