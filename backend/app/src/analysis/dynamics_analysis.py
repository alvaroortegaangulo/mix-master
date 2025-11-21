from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List

import numpy as np
import soundfile as sf


FRAME_SIZE = 1024
HOP_SIZE = FRAME_SIZE // 2
EPS = 1e-12


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


# ----------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------


def _safe_dbfs(x: float, floor: float = -120.0) -> float:
    x = float(x)
    if x <= 0.0:
        return floor
    return 20.0 * np.log10(x)


def _infer_instrument_profile(filename: str) -> str:
    """
    Heurística simple basada en el nombre del archivo.
    Devuelve etiquetas tipo: vocal, kick, snare, toms, perc, bass, guitar, keys, other.
    """
    name = filename.lower()

    if any(k in name for k in ["vox", "voz", "vocal", "lead", "ldv", "singer"]):
        return "vocal"
    if any(k in name for k in ["kick", "bombo", "kik"]):
        return "kick"
    if any(k in name for k in ["snare", "caja", "sd"]):
        return "snare"
    if any(k in name for k in ["tom", "toms"]):
        return "toms"
    if any(k in name for k in ["perc", "shaker", "conga", "bongo", "clap"]):
        return "perc"
    if any(k in name for k in ["bass", "bajo", "sub"]):
        return "bass"
    if any(k in name for k in ["gtr", "guit", "guitar"]):
        return "guitar"
    if any(k in name for k in ["piano", "keys", "synth", "sinte", "pad"]):
        return "keys"
    return "other"


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
    Devuelve:
      comp_enabled, comp_threshold_dbfs, comp_ratio, comp_attack_ms, comp_release_ms, comp_makeup_gain_db,
      limiter_enabled, limiter_threshold_dbfs, limiter_release_ms
    """
    comp_enabled = True
    comp_threshold_dbfs = rms_dbfs - 4.0
    comp_ratio = 2.0
    comp_attack_ms = 10.0
    comp_release_ms = 120.0
    comp_makeup_gain_db = 0.0  # mantenemos nivel; loudness ya ha hecho gain staging

    limiter_enabled = True
    limiter_threshold_dbfs = -0.5
    limiter_release_ms = 100.0

    # Ajustes base por perfil
    if profile == "vocal":
        comp_ratio = 3.0
        comp_threshold_dbfs = rms_dbfs - 4.0
        comp_attack_ms = 8.0
        comp_release_ms = 120.0

        if crest_db < 8.0:
            comp_ratio = 2.0
            comp_threshold_dbfs = rms_dbfs - 2.0
        elif crest_db > 14.0:
            comp_ratio = 4.0
            comp_threshold_dbfs = rms_dbfs - 6.0

    elif profile == "bass":
        comp_ratio = 3.0
        comp_threshold_dbfs = rms_dbfs - 4.0
        comp_attack_ms = 5.0
        comp_release_ms = 150.0

        if crest_db < 8.0:
            comp_ratio = 2.0
            comp_threshold_dbfs = rms_dbfs - 3.0
        elif crest_db > 14.0:
            comp_ratio = 4.0
            comp_threshold_dbfs = rms_dbfs - 6.0

    elif profile in ("kick", "snare", "toms", "perc"):
        # Transientes fuertes: preservar ataque, controlar cola
        comp_ratio = 3.0
        comp_threshold_dbfs = peak_dbfs - 6.0
        comp_attack_ms = 20.0
        comp_release_ms = 120.0

        if transient_crest_db > 18.0 or crest_db > 16.0:
            comp_ratio = 4.0
            comp_threshold_dbfs = peak_dbfs - 8.0

    elif profile in ("guitar", "keys"):
        comp_ratio = 2.0
        comp_threshold_dbfs = rms_dbfs - 4.0
        comp_attack_ms = 15.0
        comp_release_ms = 200.0

        if crest_db > 14.0:
            comp_ratio = 3.0
            comp_threshold_dbfs = rms_dbfs - 6.0

    else:  # other
        if crest_db < 8.0:
            comp_enabled = False
        else:
            comp_enabled = True
            comp_ratio = 2.0
            comp_threshold_dbfs = rms_dbfs - 4.0
            comp_attack_ms = 12.0
            comp_release_ms = 150.0

    # Saneado: que el umbral no quede por encima del pico - 1 dB
    if comp_enabled:
        max_threshold = peak_dbfs - 1.0
        if comp_threshold_dbfs > max_threshold:
            comp_threshold_dbfs = max_threshold

        # Evitar valores extremadamente bajos
        if comp_threshold_dbfs < -60.0:
            comp_threshold_dbfs = -60.0

    # Limiter: siempre activo, muy suave, por seguridad
    limiter_enabled = True
    limiter_threshold_dbfs = -0.5
    limiter_release_ms = 100.0

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


def analyze_dynamics(media_dir: Path) -> List[DynamicsAnalysisResult]:
    """
    Analiza dinámica de todos los .wav de media_dir.

    Calcula:
      - RMS, peak, crest factor global.
      - Índice de transitorios (crest factor por frame, percentil 90).
      - Perfil de instrumento basado en filename.
      - Parámetros sugeridos de compresor + limitador.
    """
    if not media_dir.exists() or not media_dir.is_dir():
        raise FileNotFoundError(f"El directorio de medios no existe: {media_dir}")

    results: List[DynamicsAnalysisResult] = []

    for wav_path in sorted(media_dir.glob("*.wav")):
        audio, sr = sf.read(wav_path, always_2d=True)
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

        profile = _infer_instrument_profile(wav_path.name)

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
