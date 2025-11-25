from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List

import numpy as np
from pedalboard import Pedalboard, Compressor, Limiter, Gain
from pedalboard.io import AudioFile


@dataclass
class DynamicsRow:
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


@dataclass
class DynamicsCorrectionResult:
    filename: str
    input_path: Path
    output_path: Path
    sample_rate: int
    num_channels: int
    duration_seconds: float
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
    original_peak_dbfs: float
    original_rms_dbfs: float
    resulting_peak_dbfs: float
    resulting_rms_dbfs: float


def _safe_dbfs(x: float, floor: float = -120.0) -> float:
    x = float(x)
    if x <= 0.0:
        return floor
    return 20.0 * np.log10(x)


def _parse_bool(v: str) -> bool:
    v = v.strip()
    if not v:
        return False
    return v in ("1", "true", "True", "YES", "yes")


def _parse_float(v: str, default: float = 0.0) -> float:
    v = v.strip()
    if not v:
        return default
    return float(v)


# ----------------------------------------------------------------------
# Lectura del CSV de análisis
# ----------------------------------------------------------------------


def load_dynamics_csv(csv_path: Path) -> List[DynamicsRow]:
    if not csv_path.exists():
        raise FileNotFoundError(f"No se encontró el CSV de análisis de dinámica: {csv_path}")

    rows: List[DynamicsRow] = []

    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for line in reader:
            row = DynamicsRow(
                filename=line["filename"],
                relative_path=line.get("relative_path") or line["filename"],
                sample_rate=int(line["sample_rate"]),
                num_channels=int(line["num_channels"]),
                duration_seconds=float(line["duration_seconds"]),
                rms_dbfs=float(line["rms_dbfs"]),
                peak_dbfs=float(line["peak_dbfs"]),
                crest_factor_db=float(line["crest_factor_db"]),
                transient_crest_db=float(line["transient_crest_db"]),
                instrument_profile=line.get("instrument_profile", ""),
                comp_enabled=_parse_bool(line.get("comp_enabled", "0")),
                comp_threshold_dbfs=_parse_float(line.get("comp_threshold_dbfs", "0.0")),
                comp_ratio=_parse_float(line.get("comp_ratio", "1.0")),
                comp_attack_ms=_parse_float(line.get("comp_attack_ms", "10.0")),
                comp_release_ms=_parse_float(line.get("comp_release_ms", "100.0")),
                comp_makeup_gain_db=_parse_float(line.get("comp_makeup_gain_db", "0.0")),
                limiter_enabled=_parse_bool(line.get("limiter_enabled", "0")),
                limiter_threshold_dbfs=_parse_float(line.get("limiter_threshold_dbfs", "-0.5")),
                limiter_release_ms=_parse_float(line.get("limiter_release_ms", "100.0")),
            )
            rows.append(row)

    return rows


# ----------------------------------------------------------------------
# Heurísticas "pro" para refinar los parámetros de dinámica del CSV
# ----------------------------------------------------------------------


def _classify_instrument(instrument_profile: str, filename: str):
    """
    Clasificación de la pista basada en:
      1) instrument_profile que llega del frontend (STEM_PROFILE_OPTIONS):
         - auto
         - drums
         - percussion
         - bass
         - acoustic_guitar
         - electric_guitar
         - keys
         - synth
         - lead_vocal
         - backing_vocals
         - fx
         - ambience
         - other
      2) Si sigue sin estar claro (auto/other/vacío), se cae al heurístico
         por nombre de archivo que teníamos antes.

    Devuelve:
      is_percussive, is_bass, is_vocal, is_gtr_or_keys
    """
    ip = (instrument_profile or "").strip().lower()
    filename_lower = filename.lower()

    is_percussive = False
    is_bass = False
    is_vocal = False
    is_gtr_or_keys = False

    # ------------------ 1) Clasificación directa por perfil ------------------
    if ip in ("drums", "percussion"):
        is_percussive = True
    elif ip == "bass":
        is_bass = True
    elif ip in ("lead_vocal", "backing_vocals"):
        is_vocal = True
    elif ip in ("acoustic_guitar", "electric_guitar", "keys", "synth"):
        # Guitarras y teclas/synth → mismo tratamiento dinámico base
        is_gtr_or_keys = True
    elif ip in ("fx", "ambience", "other", "auto", ""):
        # Se tratan como "no claramente clasificados" y se deja la puerta
        # abierta al fallback por nombre.
        pass
    else:
        # Cualquier otro tag inesperado: tratamos como desconocido.
        pass

    # Si el perfil ya nos da info suficiente, no necesitamos heurístico extra
    if is_percussive or is_bass or is_vocal or is_gtr_or_keys:
        return is_percussive, is_bass, is_vocal, is_gtr_or_keys

    # ------------------ 2) Fallback heurístico por nombre --------------------
    text = (instrument_profile or "").lower() + " " + filename_lower

    is_kick = any(t in text for t in ("kick", "bombo", "bd"))
    is_snare = any(t in text for t in ("snare", "sna", "caja"))
    is_hat = any(t in text for t in ("hat", "hihat", "hh", "ride", "cym"))
    is_tom = any(t in text for t in ("tom", "timbal"))
    is_hand_perc = any(t in text for t in ("perc", "shaker", "clap", "palma", "cajon"))
    is_drum = is_kick or is_snare or is_hat or is_tom or is_hand_perc

    is_bass = any(t in text for t in ("bass", "bajo", "sub"))
    is_vocal = any(t in text for t in ("vocal", "vox", "voz", "lead_vocal", "backing_vocals"))
    is_gtr = any(t in text for t in ("guitar", "gtr", "acoustic_guitar", "electric_guitar"))
    is_keys = any(t in text for t in ("keys", "piano", "synth", "pad", "rhodes"))

    is_percussive = is_drum
    is_gtr_or_keys = is_gtr or is_keys

    return is_percussive, is_bass, is_vocal, is_gtr_or_keys


def _refine_dynamics_settings(row: DynamicsRow):
    """
    Toma los ajustes sugeridos por el análisis y los "domestica" para que la
    compresión sea más musical, respetando:

      - tipo de instrumento (perfil + fallback)
      - crest factor (dinámica global)
      - transient_crest_db (transitorios)
      - rms/peak reales

    Devuelve la tupla:
      (comp_enabled, thr, ratio, attack_ms, release_ms, makeup_db,
       limiter_enabled, limiter_threshold_dbfs, limiter_release_ms)
    """
    is_perc, is_bass, is_vocal, is_gtr_keys = _classify_instrument(
        row.instrument_profile, row.filename
    )

    peak_dbfs = row.peak_dbfs
    rms_dbfs = row.rms_dbfs
    crest_db = row.crest_factor_db
    transient_db = row.transient_crest_db

    comp_enabled = row.comp_enabled
    thr = row.comp_threshold_dbfs
    ratio = row.comp_ratio
    attack = row.comp_attack_ms
    release = row.comp_release_ms
    makeup = row.comp_makeup_gain_db
    lim_enabled = row.limiter_enabled
    lim_thr = row.limiter_threshold_dbfs
    lim_rel = row.limiter_release_ms

    # ---------------------- Ratio: evitar aplastamiento ----------------------
    ratio = max(ratio, 1.0)
    ratio = min(ratio, 8.0)

    # Si ya está bastante comprimido (crest bajo), limitamos ratio
    if crest_db < 8.0:
        ratio = min(ratio, 3.0)
    if crest_db < 5.0:
        ratio = min(ratio, 2.0)

    # Voces → ratios razonables
    if is_vocal:
        ratio = max(1.2, min(ratio, 3.0))
    # Percusiones → ratios moderados
    if is_perc:
        ratio = max(1.1, min(ratio, 3.5))
    # Bajos → un poco más de control permitido
    if is_bass:
        ratio = max(1.5, min(ratio, 4.0))
    # Guitarras/keys → suaves
    if is_gtr_keys and not is_vocal:
        ratio = max(1.1, min(ratio, 2.5))

    # ---------------------- Threshold vs RMS/Peak ----------------------------
    if comp_enabled:
        # No queremos thresholds muy por debajo del RMS → eso destruye dinámica.
        min_thr_above_rms = 2.0
        if is_vocal:
            min_thr_above_rms = 3.0

        thr = max(thr, rms_dbfs + min_thr_above_rms)

        # Threshold no puede estar por encima de (peak - 1) dB
        thr = min(thr, peak_dbfs - 1.0)

        # En general, no queremos trabajar tan cerca de 0 dBFS
        thr = min(thr, -2.0)

    # ---------------------- Tiempos: protegiendo transitorios ----------------
    # Clamps genéricos
    attack = max(attack, 0.3)
    attack = min(attack, 60.0)
    release = max(release, 20.0)
    release = min(release, 800.0)

    if is_perc:
        # Para percusiones: no matar transitorios
        if transient_db > 10.0:
            attack = max(attack, 10.0)
        else:
            attack = max(attack, 5.0)
        release = max(release, 60.0)
        release = min(release, 250.0)

    elif is_bass:
        attack = max(attack, 5.0)
        attack = min(attack, 30.0)
        release = max(release, 80.0)
        release = min(release, 400.0)

    elif is_vocal:
        attack = max(attack, 3.0)
        attack = min(attack, 20.0)
        release = max(release, 60.0)
        release = min(release, 350.0)

    elif is_gtr_keys:
        attack = max(attack, 5.0)
        attack = min(attack, 25.0)
        release = max(release, 80.0)
        release = min(release, 400.0)

    # ---------------------- Makeup: mantener dinámica ------------------------
    makeup = max(min(makeup, 6.0), -6.0)

    if is_perc:
        makeup = max(min(makeup, 2.0), -3.0)
    elif is_vocal:
        makeup = max(min(makeup, 3.0), -3.0)
    else:
        makeup = max(min(makeup, 3.5), -4.0)

    # Si ya tiene crest bajo, reducimos cualquier boost agresivo
    if crest_db < 6.0 and makeup > 0.0:
        makeup = min(makeup, 1.5)

    # Estimación grosera de GR en picos → si deja el crest ridículo, recortamos makeup
    if comp_enabled and ratio > 1.0:
        peak_above_thr = max(0.0, peak_dbfs - thr)
        gr_peak = peak_above_thr * (1.0 - 1.0 / ratio)
        if crest_db - gr_peak < 4.0:
            makeup = min(makeup, 1.0)

    # ---------------------- Compresor realmente activo o no ------------------
    if comp_enabled:
        if ratio <= 1.1:
            comp_enabled = False
        elif thr >= peak_dbfs - 0.5:
            comp_enabled = False

    # ---------------------- Limitador como "safety only" ---------------------
    if lim_enabled:
        if peak_dbfs <= -3.0:
            lim_enabled = False
        else:
            lim_thr = max(peak_dbfs - 3.0, lim_thr)
            lim_thr = min(lim_thr, -0.5)
            lim_thr = min(lim_thr, -0.3)
            lim_thr = max(lim_thr, -8.0)

    return (
        comp_enabled,
        thr,
        ratio,
        attack,
        release,
        makeup,
        lim_enabled,
        lim_thr,
        lim_rel,
    )


# ----------------------------------------------------------------------
# Aplicación de compresor + limitador
# ----------------------------------------------------------------------


def _apply_dynamics_to_file(
    row: DynamicsRow,
    input_media_dir: Path,
    output_media_dir: Path,
) -> DynamicsCorrectionResult:
    input_path = (input_media_dir / row.relative_path).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"No se encontró el WAV de entrada: {input_path}")

    output_media_dir.mkdir(parents=True, exist_ok=True)
    output_path = (output_media_dir / row.filename).resolve()

    # Leer audio
    with AudioFile(str(input_path), "r") as f:
        audio = f.read(f.frames)  # (channels, samples)
        sr = f.samplerate
        num_channels = f.num_channels

    audio = audio.astype(np.float32, copy=False)

    # Métricas originales
    original_peak = float(np.max(np.abs(audio))) if audio.size > 0 else 0.0
    original_rms = float(np.sqrt(np.mean(audio ** 2))) if audio.size > 0 else 0.0

    original_peak_dbfs = _safe_dbfs(original_peak)
    original_rms_dbfs = _safe_dbfs(original_rms)

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
    ) = _refine_dynamics_settings(row)

    # Construir cadena de efectos
    effects = []

    if comp_enabled:
        comp = Compressor(
            threshold_db=comp_threshold_dbfs,
            ratio=comp_ratio,
            attack_ms=comp_attack_ms,
            release_ms=comp_release_ms,
        )
        effects.append(comp)

        if abs(comp_makeup_gain_db) > 0.01:
            effects.append(Gain(gain_db=comp_makeup_gain_db))

    if limiter_enabled:
        effects.append(
            Limiter(
                threshold_db=limiter_threshold_dbfs,
                release_ms=limiter_release_ms,
            )
        )

    board = Pedalboard(effects)
    processed = board(audio, sample_rate=sr) if effects else audio

    # Métricas resultantes
    processed_peak = float(np.max(np.abs(processed))) if processed.size > 0 else 0.0
    processed_rms = float(np.sqrt(np.mean(processed ** 2))) if processed.size > 0 else 0.0

    resulting_peak_dbfs = _safe_dbfs(processed_peak)
    resulting_rms_dbfs = _safe_dbfs(processed_rms)

    # Escribir archivo corregido
    with AudioFile(str(output_path), "w", sr, num_channels) as f:
        f.write(processed)

    return DynamicsCorrectionResult(
        filename=row.filename,
        input_path=input_path,
        output_path=output_path,
        sample_rate=sr,
        num_channels=num_channels,
        duration_seconds=row.duration_seconds,
        instrument_profile=row.instrument_profile,
        comp_enabled=comp_enabled,
        comp_threshold_dbfs=comp_threshold_dbfs,
        comp_ratio=comp_ratio,
        comp_attack_ms=comp_attack_ms,
        comp_release_ms=comp_release_ms,
        comp_makeup_gain_db=comp_makeup_gain_db,
        limiter_enabled=limiter_enabled,
        limiter_threshold_dbfs=limiter_threshold_dbfs,
        limiter_release_ms=limiter_release_ms,
        original_peak_dbfs=original_peak_dbfs,
        original_rms_dbfs=original_rms_dbfs,
        resulting_peak_dbfs=resulting_peak_dbfs,
        resulting_rms_dbfs=resulting_rms_dbfs,
    )


# ----------------------------------------------------------------------
# Log de corrección
# ----------------------------------------------------------------------


def write_dynamics_correction_log(
    results: List[DynamicsCorrectionResult],
    log_csv_path: Path,
) -> None:
    log_csv_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "filename",
        "input_path",
        "output_path",
        "sample_rate",
        "num_channels",
        "duration_seconds",
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
        "original_peak_dbfs",
        "original_rms_dbfs",
        "resulting_peak_dbfs",
        "resulting_rms_dbfs",
    ]

    with log_csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for r in results:
            writer.writerow({
                "filename": r.filename,
                "input_path": str(r.input_path),
                "output_path": str(r.output_path),
                "sample_rate": r.sample_rate,
                "num_channels": r.num_channels,
                "duration_seconds": f"{r.duration_seconds:.6f}",
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
                "original_peak_dbfs": f"{r.original_peak_dbfs:.2f}",
                "original_rms_dbfs": f"{r.original_rms_dbfs:.2f}",
                "resulting_peak_dbfs": f"{r.resulting_peak_dbfs:.2f}",
                "resulting_rms_dbfs": f"{r.resulting_rms_dbfs:.2f}",
            })


# ----------------------------------------------------------------------
# Punto de entrada de alto nivel
# ----------------------------------------------------------------------


def run_dynamics_correction(
    analysis_csv_path: Path,
    input_media_dir: Path,
    output_media_dir: Path,
) -> Path:
    """
    Ejecuta la corrección de dinámica de todos los stems (compresor + limitador).

    :param analysis_csv_path: Ruta al CSV de análisis de dinámica.
    :param input_media_dir: Carpeta con los WAV de entrada (stems ya ecualizados).
    :param output_media_dir: Carpeta donde se guardarán los WAV corregidos.
    :return: Ruta al CSV de log de corrección.
    """
    rows = load_dynamics_csv(analysis_csv_path)

    results: List[DynamicsCorrectionResult] = []

    for row in rows:
        result = _apply_dynamics_to_file(row, input_media_dir, output_media_dir)
        results.append(result)

    log_csv_path = output_media_dir / "dynamics_correction_log.csv"
    write_dynamics_correction_log(results, log_csv_path)

    return log_csv_path
