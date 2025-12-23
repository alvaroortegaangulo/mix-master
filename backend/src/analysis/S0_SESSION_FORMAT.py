from utils.logger import logger
# C:\mix-master\backend\src\analysis\S0_SESSION_FORMAT.py

import sys
from pathlib import Path

# Añadir .../src al sys.path para poder hacer "from utils ..."
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
from typing import Dict, Any, List  # noqa: E402
import os  # noqa: E402

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from utils.analysis_utils import (  # noqa: E402
    load_contract,
    get_temp_dir,
    load_audio_mono,
    compute_peak_dbfs,
)
from utils.session_utils import (  # noqa: E402
    load_session_config,
    infer_bus_target,
)

SUPPORTED_AUDIO_EXTS = {".wav", ".aif", ".aiff", ".mp3"}


def _load_audio_for_conversion(path: Path) -> tuple[np.ndarray, int]:
    """
    Lee audio con soundfile si es posible; fallback a librosa para formatos
    como MP3 cuando libsndfile no lo soporta.
    Devuelve audio en float32 con forma (samples, channels).
    """
    try:
        data, sr = sf.read(path, always_2d=True)
        return data.astype(np.float32, copy=False), int(sr)
    except Exception:
        try:
            import librosa  # type: ignore
        except Exception as exc:  # pragma: no cover - depende del entorno
            raise RuntimeError(f"No se pudo leer {path.name}; falta backend para MP3/AIFF: {exc}") from exc

        data, sr = librosa.load(path, sr=None, mono=False)
        if data.ndim == 1:
            data = data.reshape(-1, 1)
        else:
            data = data.T
        return data.astype(np.float32, copy=False), int(sr)


def _unique_wav_path(path: Path) -> Path:
    base = path.with_suffix(".wav")
    if not base.exists():
        return base
    stem = path.stem
    for i in range(1, 1000):
        candidate = path.with_name(f"{stem}_{i}.wav")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"No se pudo encontrar nombre libre para {path.name}")


def _convert_to_wav(path: Path) -> Path:
    data, sr = _load_audio_for_conversion(path)
    wav_path = _unique_wav_path(path)
    sf.write(wav_path, data, sr, subtype="FLOAT")
    return wav_path


def _update_session_config_paths(temp_dir: Path, converted: Dict[str, str]) -> None:
    if not converted:
        return
    cfg_path = temp_dir / "session_config.json"
    if not cfg_path.exists():
        return
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return

    stems = cfg.get("stems", [])
    updated = False
    for stem in stems:
        if not isinstance(stem, dict):
            continue
        fname = stem.get("file_name")
        if fname in converted:
            stem["file_name"] = converted[fname]
            updated = True

    if updated:
        cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

def analyze_stem(stem_path: Path) -> Dict[str, Any]:
    """
    Analiza un stem: samplerate, canales, duración, pico, silencios inicio/fin, bit_depth.
    Usa load_audio_mono + compute_peak_dbfs para unificar lógica.
    """
    mono, sr = load_audio_mono(stem_path)
    duration_sec = len(mono) / float(sr) if len(mono) > 0 else 0.0

    peak_dbfs = compute_peak_dbfs(mono)
    peak_linear = float(np.max(np.abs(mono))) if mono.size > 0 else 0.0

    # Detección de silencio en cabecera y cola (umbral fijo muy bajo)
    silence_threshold = 10 ** (-60.0 / 20.0)  # -60 dBFS aprox
    non_silent_indices = np.where(np.abs(mono) > silence_threshold)[0]
    if non_silent_indices.size > 0:
        start_idx = int(non_silent_indices[0])
        end_idx = int(non_silent_indices[-1])
        start_time_sec = start_idx / float(sr)
        end_time_sec = end_idx / float(sr)
        silence_head_sec = start_time_sec
        silence_tail_sec = duration_sec - end_time_sec
    else:
        start_time_sec = 0.0
        end_time_sec = 0.0
        silence_head_sec = duration_sec
        silence_tail_sec = 0.0

    info = sf.info(stem_path)
    samplerate_hz = info.samplerate
    channels = info.channels
    subtype = info.subtype or ""
    bit_depth_file = None
    if "16" in subtype:
        bit_depth_file = 16
    elif "24" in subtype:
        bit_depth_file = 24
    elif "32" in subtype:
        bit_depth_file = 32

    return {
        "file_name": stem_path.name,
        "file_path": str(stem_path),
        "samplerate_hz": samplerate_hz,
        "channels": channels,
        "bit_depth_file": bit_depth_file,
        "duration_sec": duration_sec,
        "peak_linear": peak_linear,
        "peak_dbfs": peak_dbfs,
        "start_time_sec": start_time_sec,
        "end_time_sec": end_time_sec,
        "silence_head_sec": silence_head_sec,
        "silence_tail_sec": silence_tail_sec,
    }


def main() -> None:
    """
    Script de análisis para el contrato S0_SESSION_FORMAT.

    Uso esperado desde stage.py:
        python analysis/S0_SESSION_FORMAT.py S0_SESSION_FORMAT
    """
    if len(sys.argv) < 2:
        logger.logger.error("Uso: python S0_SESSION_FORMAT.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S0_SESSION_FORMAT"

    # 1) Cargar contrato y temp/<contract_id>
    contract = load_contract(contract_id)
    metrics: Dict[str, Any] = contract.get("metrics", {})
    limits: Dict[str, Any] = contract.get("limits", {})
    stage_id: str | None = contract.get("stage_id")

    temp_dir = get_temp_dir(contract_id, create=True)

    # 2) Cargar config de sesión (style_preset e instrument_profile desde frontend)
    cfg = load_session_config(contract_id)
    style_preset = cfg["style_preset"]
    instrument_by_file = cfg["instrument_by_file"]

    # 3) Convertir a WAV si llegan AIFF/MP3 para unificar el pipeline
    converted: Dict[str, str] = {}
    stem_candidates = [
        p for p in temp_dir.iterdir()
        if p.is_file()
        and p.suffix.lower() in SUPPORTED_AUDIO_EXTS
        and p.name.lower() != "full_song.wav"
    ]
    for src in stem_candidates:
        if src.suffix.lower() == ".wav":
            continue
        try:
            wav_path = _convert_to_wav(src)
            converted[src.name] = wav_path.name
            try:
                src.unlink()
            except Exception as exc:
                logger.logger.warning(f"[S0_SESSION_FORMAT] No se pudo borrar {src.name}: {exc}")
            logger.logger.info(f"[S0_SESSION_FORMAT] Convertido {src.name} -> {wav_path.name}")
        except Exception as exc:
            logger.logger.error(f"[S0_SESSION_FORMAT] Error convirtiendo {src.name} a WAV: {exc}")
            raise

    if converted:
        _update_session_config_paths(temp_dir, converted)
        for old_name, new_name in converted.items():
            if old_name in instrument_by_file and new_name not in instrument_by_file:
                instrument_by_file[new_name] = instrument_by_file[old_name]

    # 4) Leer y analizar stems desde temp/<contract_id>
    stem_files: List[Path] = sorted(
        p for p in temp_dir.glob("*.wav")
        if p.name.lower() != "full_song.wav"  # por si en algún momento existiera
    )

    stems_analysis: List[Dict[str, Any]] = []
    session_max_peak_dbfs = float("-inf")
    samplerates_present = set()

    # Análisis de stems en serie (manteniendo el orden)
    results = [analyze_stem(p) for p in stem_files] if stem_files else []

    for stem_info in results:
        file_name = stem_info["file_name"]
        requested_profile = instrument_by_file.get(file_name)
        if not requested_profile:
            file_stem = Path(file_name).stem
            for key, prof in instrument_by_file.items():
                if Path(key).stem == file_stem:
                    requested_profile = prof
                    break
        if not requested_profile:
            requested_profile = "Other"

        # Resolver instrument_profile cuando es "Auto"
        if str(requested_profile).lower() == "auto":
            resolved_profile = "Other"  # de momento, sin clasificador automático
        else:
            resolved_profile = requested_profile

        bus_target = infer_bus_target(resolved_profile)

        stem_info["instrument_profile_requested"] = requested_profile
        stem_info["instrument_profile_resolved"] = resolved_profile
        stem_info["bus_target"] = bus_target

        stems_analysis.append(stem_info)

        samplerates_present.add(stem_info["samplerate_hz"])
        peak_dbfs = stem_info["peak_dbfs"]
        if peak_dbfs > session_max_peak_dbfs:
            session_max_peak_dbfs = peak_dbfs

    # 4) Construir estructura SessionState para el JSON de salida
    buses: Dict[str, Dict[str, Any]] = {}
    for stem in stems_analysis:
        bus = stem["bus_target"]
        if bus not in buses:
            buses[bus] = {
                "bus_id": bus,
                "stems": []
            }
        buses[bus]["stems"].append(stem["file_name"])

    session_state: Dict[str, Any] = {
        "contract_id": contract_id,
        "stage_id": stage_id,
        "style_preset": style_preset,
        "metrics_from_contract": metrics,
        "limits_from_contract": limits,
        "session": {
            "samplerate_hz_target": metrics.get("samplerate_hz"),
            "bit_depth_internal_target": metrics.get("bit_depth_internal"),
            "max_peak_dbfs_target": metrics.get("max_peak_dbfs"),
            "samplerates_present": sorted(list(samplerates_present)),
            "session_max_peak_dbfs": session_max_peak_dbfs,
        },
        "stems": stems_analysis,
        "buses": list(buses.values()),
    }

    # 5) Guardar JSON de análisis
    output_path = temp_dir / f"analysis_{contract_id}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(session_state, f, indent=2, ensure_ascii=False)

    # logger.info(f"[S0_SESSION_FORMAT] Analysis JSON saved: {output_path}")


if __name__ == "__main__":
    main()
