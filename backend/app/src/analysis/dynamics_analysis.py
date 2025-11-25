# src/analysis/dynamics_analysis.py

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict

import numpy as np
import soundfile as sf


FRAME_SIZE = 1024
HOP_SIZE = FRAME_SIZE // 2
EPS = 1e-12


# Perfiles alineados con Space&Depth
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

    instrument_profile: str  # alineado con DYNAMICS_PROFILES

    comp_enabled: bool
    comp_threshold_dbfs: float
    comp_ratio: float
    comp_attack_ms: float
    comp_release_ms: float
    comp_makeup_gain_db: float

    limiter_enabled: bool
    limiter_threshold_dbfs: float
    limiter_release_ms: float


# ----------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------


def _safe_dbfs(x: float, floor: float = -120.0) -> float:
    x = float(x)
    if x <= 0.0:
        return floor
    return 20.0 * np.log10(x)


def _infer_instrument_profile(
    filename: str,
    stem_profiles: Optional[Dict[str, str]] = None,
) -> str:
    """
    Intenta inferir el perfil de instrumento usando primero stem_profiles
    (mismos tags que Space&Depth) y, si no hay mapping, heurística por nombre.

    Devuelve uno de:
      drums, percussion, bass, acoustic_guitar, electric_guitar,
      keys, synth, lead_vocal, backing_vocals, fx, ambience, other, auto
    """
    name = filename
    stem = Path(filename).stem
    name_lower = name.lower()

    # 1) Si vienen perfiles explícitos desde el frontend, son la verdad
    if stem_profiles:
        if name in stem_profiles:
            return stem_profiles[name]
        if stem in stem_profiles:
            return stem_profiles[stem]
        if "default" in stem_profiles:
            return stem_profiles["default"]

    # 2) Heurística por nombre de archivo
    # Voces
    if any(k in name_lower for k in ["lead_vocal", "leadvox", "ldv", "voz_lead", "voz lead"]):
        return "lead_vocal"
    if any(k in name_lower for k in ["backing", "bgv", "bvs", "choir", "coros", "doubles", "doble"]):
        return "backing_vocals"
    if any(k in name_lower for k in ["vox", "voz", "vocal", "singer"]):
        # Si no está claro si es lead o coros, tratamos como lead para dinámica
        return "lead_vocal"

    # Batería / percusión
    if any(k in name_lower for k in ["kick", "bombo", "bd", "snare", "caja", "hat", "hihat", "ride", "cym", "toms"]):
        return "drums"
    if any(k in name_lower for k in ["perc", "shaker", "conga", "bongo", "clap", "palma", "cajon", "timbal"]):
        return "percussion"

    # Bajo
    if any(k in name_lower for k in ["bass", "bajo", "sub"]):
        return "bass"

    # Guitarras
    if any(k in name_lower for k in ["acgtr", "acoustic_gtr", "acoustic-gtr", "nylon", "flamenca", "spanish_gtr"]):
        return "acoustic_guitar"
    if any(k in name_lower for k in ["gtr", "guitar", "egtr", "electric_gtr", "dist", "lead_gtr"]):
        return "electric_guitar"

    # Teclas / synth
    if any(k in name_lower for k in ["piano", "keys", "rhodes", "organ", "epiano"]):
        return "keys"
    if any(k in name_lower for k in ["synth", "sinte", "pad", "pluck", "arp"]):
        return "synth"

    # FX / ambience
    if any(k in name_lower for k in ["fx", "impact", "whoosh", "riser", "drop"]):
        return "fx"
    if any(k in name_lower for k in ["amb", "room", "hall", "atm", "atmo", "noise"]):
        return "ambience"

    # Si no hay match claro, devolvemos other/auto
    return "auto"


def _compute_transient_crest(mono: np.ndarray) -> float:
    """
    Calcula un índice de transitorios basado en crest factor por frame
    y devuelve el percentil 90 en dB.
    """
    n = mono.shape[0]
    if n < FRAME_SIZE:
        mono = np.pad(mono, (0, FRAME_SIZE - n), mode="constant")
        n = mono.shape[0]

    cf_list = []

    for start in range(0, n - FRAME_SIZE + 1, HOP_SIZE):
        frame = mono[start:start + FRAME_SIZE]
        peak = float(np.max(np.abs(frame)))
        rms = float(np.sqrt(np.mean(frame**2))) if frame.size > 0 else 0.0
        if rms <= 0.0 or peak <= 0.0:
            continue
        cf_db = _safe_dbfs(peak) - _safe_dbfs(rms)
        cf_list.append(cf_db)

    if not cf_list:
        return 0.0

    return float(np.percentile(cf_list, 90))


def _suggest_dynamics_params(
    profile: str,
    rms_dbfs: float,
    peak_dbfs: float,
    crest_db: float,
    transient_crest_db: float,
) -> tuple[bool, float, float, float, float, float, bool, float, float]:
    """
    Diseño "pro" y sutil:

      - Compresor sólo si hay dinámica real (crest razonable).
      - Ratios típicamente 1.4–3:1.
      - Umbral por encima del RMS (o relativo al pico en percusiones).
      - Tiempos pensados por familia de instrumento.

    Devuelve:
      comp_enabled, comp_threshold_dbfs, comp_ratio, comp_attack_ms, comp_release_ms, comp_makeup_gain_db,
      limiter_enabled, limiter_threshold_dbfs, limiter_release_ms
    """
    p = (profile or "").strip().lower()

    # Valores por defecto (muy conservadores)
    comp_enabled = False
    comp_threshold_dbfs = rms_dbfs + 4.0
    comp_ratio = 1.5
    comp_attack_ms = 15.0
    comp_release_ms = 180.0
    comp_makeup_gain_db = 0.0  # Loudness ya hizo gain staging

    limiter_enabled = True
    limiter_threshold_dbfs = -0.8
    limiter_release_ms = 80.0

    # Si el stem está muy bajo, ni nos molestamos
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

    # ------------------------------------------------------------------ 
    # VOCES
    # ------------------------------------------------------------------ 
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

    # ------------------------------------------------------------------ 
    # DRUMS / PERCUSIÓN
    # ------------------------------------------------------------------ 
    elif is_drums or is_perc:
        if crest_db < 8.0 and transient_crest_db < 12.0:
            comp_enabled = False
        else:
            comp_enabled = True
            # Umbral relativo al pico para preservar ataque
            base_thr = peak_dbfs - 10.0  # pico -10 dB
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

    # ------------------------------------------------------------------ 
    # BASS
    # ------------------------------------------------------------------ 
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

    # ------------------------------------------------------------------ 
    # GUITARRAS / KEYS / SYNTH
    # ------------------------------------------------------------------ 
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

    # ------------------------------------------------------------------ 
    # FX / AMBIENCE
    # ------------------------------------------------------------------ 
    elif is_fx_amb:
        if crest_db > 12.0:
            comp_enabled = True
            comp_ratio = 1.6
            comp_threshold_dbfs = rms_dbfs + 4.0
            comp_attack_ms = 15.0
            comp_release_ms = 250.0
        else:
            comp_enabled = False

    # ------------------------------------------------------------------ 
    # OTHER / AUTO
    # ------------------------------------------------------------------ 
    elif is_other:
        if crest_db > 10.0:
            comp_enabled = True
            comp_ratio = 1.6
            comp_threshold_dbfs = rms_dbfs + 4.0
            comp_attack_ms = 12.0
            comp_release_ms = 200.0
        else:
            comp_enabled = False

    # ------------------------------------------------------------------ 
    # Saneos globales de threshold
    # ------------------------------------------------------------------ 
    if comp_enabled:
        # Threshold siempre al menos algo por encima de RMS
        comp_threshold_dbfs = max(comp_threshold_dbfs, rms_dbfs + 2.0)

        # Nunca por encima de (peak - 1 dB)
        comp_threshold_dbfs = min(comp_threshold_dbfs, peak_dbfs - 1.0)

        # Nunca tan cerca de 0 dBFS
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


# ----------------------------------------------------------------------
# Análisis principal
# ----------------------------------------------------------------------


def analyze_dynamics(
    media_dir: Path,
    stem_profiles: Optional[Dict[str, str]] = None,
) -> List[DynamicsAnalysisResult]:
    """
    Analiza dinámica de todos los .wav de media_dir.

    Calcula:
      - RMS, peak, crest factor global.
      - Índice de transitorios (crest factor por frame, percentil 90).
      - Perfil de instrumento alineado con Space&Depth.
      - Parámetros sugeridos de compresor + limitador (sutiles).
    """
    if not media_dir.exists() or not media_dir.is_dir():
        raise FileNotFoundError(f"El directorio de medios no existe: {media_dir}")

    results: List[DynamicsAnalysisResult] = []

    for wav_path in sorted(media_dir.glob("*.wav")):
        audio, sr = sf.read(wav_path, dtype="float32", always_2d=True)
        num_samples, num_channels = audio.shape
        duration_seconds = float(num_samples) / float(sr) if num_samples > 0 else 0.0

        # Mono para análisis
        mono = audio.mean(axis=1).astype(np.float32)

        peak = float(np.max(np.abs(mono))) if mono.size > 0 else 0.0
        rms = float(np.sqrt(np.mean(mono**2))) if mono.size > 0 else 0.0

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

        result = DynamicsAnalysisResult(
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
        results.append(result)

    return results


def export_dynamics_to_csv(
    results: List[DynamicsAnalysisResult],
    csv_path: Path,
) -> None:
    """
    Exporta resultados de análisis de dinámica a CSV.
    """
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "filename",
        "relative_path",
        "sample_rate",
        "num_channels",
        "duration_seconds",
        "rms_dbfs",
        "peak_dbfs",
        "crest_factor_db",
        "transient_crest_db",
        "instrument_profile",
        "comp_enabled",
        "comp_threshold_dbfs",
        "comp_ratio",
        "comp_attack_ms",
        "comp_release_ms",
        "comp_makeup_gain_db",
        "limiter_enabled",
        "limiter_threshold_dbfs",
        "limiter_release_ms",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for r in results:
            writer.writerow({
                "filename": r.filename,
                "relative_path": r.relative_path,
                "sample_rate": r.sample_rate,
                "num_channels": r.num_channels,
                "duration_seconds": f"{r.duration_seconds:.6f}",
                "rms_dbfs": f"{r.rms_dbfs:.2f}",
                "peak_dbfs": f"{r.peak_dbfs:.2f}",
                "crest_factor_db": f"{r.crest_factor_db:.2f}",
                "transient_crest_db": f"{r.transient_crest_db:.2f}",
                "instrument_profile": r.instrument_profile,
                "comp_enabled": int(r.comp_enabled),
                "comp_threshold_dbfs": f"{r.comp_threshold_dbfs:.2f}",
                "comp_ratio": f"{r.comp_ratio:.2f}",
                "comp_attack_ms": f"{r.comp_attack_ms:.2f}",
                "comp_release_ms": f"{r.comp_release_ms:.2f}",
                "comp_makeup_gain_db": f"{r.comp_makeup_gain_db:.2f}",
                "limiter_enabled": int(r.limiter_enabled),
                "limiter_threshold_dbfs": f"{r.limiter_threshold_dbfs:.2f}",
                "limiter_release_ms": f"{r.limiter_release_ms:.2f}",
            })
