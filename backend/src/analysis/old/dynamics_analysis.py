from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Dict

import numpy as np
import soundfile as sf

FRAME_SIZE = 1024
HOP_SIZE = FRAME_SIZE // 2
EPS = 1e-12

DYNAMICS_PROFILES = {
    "drums",
    "percussion",
    "bass",
    "acoustic_guitar",
    "electric_guitar",
    "keys",
    "synth",
    "lead_vocal",
    "backing_vocals",
    "fx",
    "ambience",
    "other",
    "auto",
}


@dataclass
class DynamicsAnalysisResult:
    filename: str
    relative_path: str
    sample_rate: int
    num_channels: int
    duration_seconds: float

    rms_dbfs: float
    peak_dbfs: float
    crest_factor_db: float
    transient_crest_db: float

    instrument_profile: str

    comp_enabled: bool
    comp_threshold_dbfs: float
    comp_ratio: float
    comp_attack_ms: float
    comp_release_ms: float
    comp_makeup_gain_db: float

    limiter_enabled: bool
    limiter_threshold_dbfs: float
    limiter_release_ms: float


def _safe_dbfs(x, floor: float = -120.0):
    """
    Acepta escalar o array. Devuelve:
      - float si la entrada es escalar
      - np.ndarray si la entrada es array
    """
    x_arr = np.asarray(x, dtype=float)

    # x <= 0 -> floor, x > 0 -> 20*log10(x)
    db = np.where(x_arr <= 0.0, floor, 20.0 * np.log10(x_arr))

    # Si es escalar, devolvemos un float puro
    if db.ndim == 0:
        return float(db)
    return db



def _infer_instrument_profile(
    filename: str,
    stem_profiles: Optional[Dict[str, str]] = None,
) -> str:
    name = filename
    stem = Path(filename).stem
    name_lower = name.lower()

    if stem_profiles:
        if name in stem_profiles:
            return stem_profiles[name]
        if stem in stem_profiles:
            return stem_profiles[stem]
        if "default" in stem_profiles:
            return stem_profiles["default"]

    if any(k in name_lower for k in ["lead_vocal", "leadvox", "ldv", "voz_lead", "voz lead"]):
        return "lead_vocal"
    if any(k in name_lower for k in ["backing", "bgv", "bvs", "choir", "coros", "doubles", "doble"]):
        return "backing_vocals"
    if any(k in name_lower for k in ["vox", "voz", "vocal", "singer"]):
        return "lead_vocal"

    if any(k in name_lower for k in ["kick", "bombo", "bd", "snare", "caja", "hat", "hihat", "ride", "cym", "toms"]):
        return "drums"
    if any(k in name_lower for k in ["perc", "shaker", "conga", "bongo", "clap", "palma", "cajon", "timbal"]):
        return "percussion"

    if any(k in name_lower for k in ["bass", "bajo", "sub"]):
        return "bass"

    if any(k in name_lower for k in ["acgtr", "acoustic_gtr", "acoustic-gtr", "nylon", "flamenca", "spanish_gtr"]):
        return "acoustic_guitar"
    if any(k in name_lower for k in ["gtr", "guitar", "egtr", "electric_gtr", "dist", "lead_gtr"]):
        return "electric_guitar"

    if any(k in name_lower for k in ["piano", "keys", "rhodes", "organ", "epiano"]):
        return "keys"
    if any(k in name_lower for k in ["synth", "sinte", "pad", "pluck", "arp"]):
        return "synth"

    if any(k in name_lower for k in ["fx", "impact", "whoosh", "riser", "drop"]):
        return "fx"
    if any(k in name_lower for k in ["amb", "room", "hall", "atm", "atmo", "noise"]):
        return "ambience"

    return "auto"


def _compute_transient_crest(mono: np.ndarray) -> float:
    n = mono.shape[0]
    if n < FRAME_SIZE:
        mono = np.pad(mono, (0, FRAME_SIZE - n), mode="constant")
        n = mono.shape[0]

    if n < FRAME_SIZE:
        return 0.0

    try:
        frames = np.lib.stride_tricks.sliding_window_view(mono, FRAME_SIZE)[::HOP_SIZE]
    except Exception:
        frames = np.stack(
            [mono[i : i + FRAME_SIZE] for i in range(0, n - FRAME_SIZE + 1, HOP_SIZE)],
            axis=0,
        )

    if frames.size == 0:
        return 0.0

    frame_peak = np.max(np.abs(frames), axis=1)
    frame_rms = np.sqrt(np.mean(frames * frames, axis=1))

    valid = (frame_peak > 0.0) & (frame_rms > 0.0)
    if not np.any(valid):
        return 0.0

    crest_db = _safe_dbfs(frame_peak[valid]) - _safe_dbfs(frame_rms[valid])
    return float(np.percentile(crest_db, 90))


def _suggest_dynamics_params(
    profile: str,
    rms_dbfs: float,
    peak_dbfs: float,
    crest_db: float,
    transient_crest_db: float,
) -> tuple[bool, float, float, float, float, float, bool, float, float]:
    p = (profile or "").strip().lower()

    comp_enabled = False
    comp_threshold_dbfs = rms_dbfs + 4.0
    comp_ratio = 1.5
    comp_attack_ms = 15.0
    comp_release_ms = 180.0
    comp_makeup_gain_db = 0.0

    limiter_enabled = True
    limiter_threshold_dbfs = -0.8
    limiter_release_ms = 80.0

    if peak_dbfs <= -45.0 or rms_dbfs <= -60.0:
        return (
            False,
            comp_threshold_dbfs,
            comp_ratio,
            comp_attack_ms,
            comp_release_ms,
            comp_makeup_gain_db,
            limiter_enabled,
            limiter_threshold_dbfs,
            limiter_release_ms,
        )

    is_vocal = p in ("lead_vocal", "backing_vocals")
    is_drums = p == "drums"
    is_perc = p == "percussion"
    is_bass = p == "bass"
    is_gtr = p in ("acoustic_guitar", "electric_guitar")
    is_keys_synth = p in ("keys", "synth")
    is_fx_amb = p in ("fx", "ambience")
    is_other = p in ("other", "auto", "")

    if is_vocal:
        if crest_db < 7.0:
            comp_enabled = False
        elif crest_db < 11.0:
            comp_enabled = True
            comp_ratio = 1.6
            comp_threshold_dbfs = rms_dbfs + 4.0
        elif crest_db < 15.0:
            comp_enabled = True
            comp_ratio = 2.0
            comp_threshold_dbfs = rms_dbfs + 3.0
        else:
            comp_enabled = True
            comp_ratio = 2.5
            comp_threshold_dbfs = rms_dbfs + 2.5
        comp_attack_ms = 5.0
        comp_release_ms = 120.0
    elif is_drums or is_perc:
        if crest_db < 8.0 and transient_crest_db < 12.0:
            comp_enabled = False
        else:
            comp_enabled = True
            base_thr = peak_dbfs - 10.0
            comp_threshold_dbfs = max(rms_dbfs + 4.0, base_thr)
            if transient_crest_db > 18.0 or crest_db > 16.0:
                comp_ratio = 3.0
                comp_attack_ms = 18.0
            elif transient_crest_db > 12.0:
                comp_ratio = 2.5
                comp_attack_ms = 14.0
            else:
                comp_ratio = 2.0
                comp_attack_ms = 10.0
            comp_release_ms = 100.0
    elif is_bass:
        if crest_db < 7.0:
            comp_enabled = False
        else:
            comp_enabled = True
            if crest_db > 14.0:
                comp_ratio = 3.0
                comp_threshold_dbfs = rms_dbfs + 3.0
            elif crest_db > 10.0:
                comp_ratio = 2.4
                comp_threshold_dbfs = rms_dbfs + 4.0
            else:
                comp_ratio = 2.0
                comp_threshold_dbfs = rms_dbfs + 5.0
            comp_attack_ms = 8.0
            comp_release_ms = 200.0
    elif is_gtr or is_keys_synth:
        if crest_db < 7.0:
            comp_enabled = False
        else:
            comp_enabled = True
            if crest_db > 14.0:
                comp_ratio = 2.2
                comp_threshold_dbfs = rms_dbfs + 3.5
            elif crest_db > 10.0:
                comp_ratio = 1.8
                comp_threshold_dbfs = rms_dbfs + 4.0
            else:
                comp_ratio = 1.6
                comp_threshold_dbfs = rms_dbfs + 5.0
            comp_attack_ms = 12.0
            comp_release_ms = 220.0
    elif is_fx_amb:
        if crest_db > 12.0:
            comp_enabled = True
            comp_ratio = 1.6
            comp_threshold_dbfs = rms_dbfs + 4.0
            comp_attack_ms = 15.0
            comp_release_ms = 250.0
        else:
            comp_enabled = False
    elif is_other:
        if crest_db > 10.0:
            comp_enabled = True
            comp_ratio = 1.6
            comp_threshold_dbfs = rms_dbfs + 4.0
            comp_attack_ms = 12.0
            comp_release_ms = 200.0
        else:
            comp_enabled = False

    if comp_enabled:
        comp_threshold_dbfs = max(comp_threshold_dbfs, rms_dbfs + 2.0)
        comp_threshold_dbfs = min(comp_threshold_dbfs, peak_dbfs - 1.0)
        comp_threshold_dbfs = min(comp_threshold_dbfs, -2.0)

    return (
        comp_enabled,
        comp_threshold_dbfs,
        comp_ratio,
        comp_attack_ms,
        comp_release_ms,
        comp_makeup_gain_db,
        limiter_enabled,
        limiter_threshold_dbfs,
        limiter_release_ms,
    )


def analyze_dynamics(
    media_dir: Path,
    stem_profiles: Optional[Dict[str, str]] = None,
) -> List[DynamicsAnalysisResult]:
    """
    Analiza dinamica de todos los .wav de media_dir.
    """
    if not media_dir.exists() or not media_dir.is_dir():
        raise FileNotFoundError(f"El directorio de medios no existe: {media_dir}")

    results: List[DynamicsAnalysisResult] = []

    for wav_path in sorted(media_dir.glob("*.wav")):
        audio, sr = sf.read(wav_path, dtype="float32", always_2d=True)
        num_samples, num_channels = audio.shape
        duration_seconds = float(num_samples) / float(sr) if num_samples > 0 else 0.0

        mono = audio.mean(axis=1, dtype=np.float32)

        if mono.size == 0:
            peak = rms = 0.0
        else:
            abs_mono = np.abs(mono)
            peak = float(abs_mono.max())
            rms = float(np.sqrt(np.mean(mono * mono)))

        peak_dbfs = _safe_dbfs(peak)
        rms_dbfs = _safe_dbfs(rms)
        crest_db = peak_dbfs - rms_dbfs

        transient_crest_db = _compute_transient_crest(mono)
        profile = _infer_instrument_profile(wav_path.name, stem_profiles=stem_profiles)

        (
            comp_enabled,
            comp_threshold_dbfs,
            comp_ratio,
            comp_attack_ms,
            comp_release_ms,
            comp_makeup_gain_db,
            limiter_enabled,
            limiter_threshold_dbfs,
            limiter_release_ms,
        ) = _suggest_dynamics_params(
            profile=profile,
            rms_dbfs=rms_dbfs,
            peak_dbfs=peak_dbfs,
            crest_db=crest_db,
            transient_crest_db=transient_crest_db,
        )

        results.append(
            DynamicsAnalysisResult(
                filename=wav_path.name,
                relative_path=wav_path.name,
                sample_rate=int(sr),
                num_channels=int(num_channels),
                duration_seconds=duration_seconds,
                rms_dbfs=rms_dbfs,
                peak_dbfs=peak_dbfs,
                crest_factor_db=crest_db,
                transient_crest_db=transient_crest_db,
                instrument_profile=profile,
                comp_enabled=comp_enabled,
                comp_threshold_dbfs=comp_threshold_dbfs,
                comp_ratio=comp_ratio,
                comp_attack_ms=comp_attack_ms,
                comp_release_ms=comp_release_ms,
                comp_makeup_gain_db=comp_makeup_gain_db,
                limiter_enabled=limiter_enabled,
                limiter_threshold_dbfs=limiter_threshold_dbfs,
                limiter_release_ms=limiter_release_ms,
            )
        )

    return results


def export_dynamics_to_json(
    results: List[DynamicsAnalysisResult],
    json_path: Path,
) -> None:
    """
    Exporta resultados de analisis de dinamica a JSON.
    """
    json_path.parent.mkdir(parents=True, exist_ok=True)

    payload = []
    for r in results:
        item = asdict(r)
        item["file_path"] = r.filename
        payload.append(item)

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
