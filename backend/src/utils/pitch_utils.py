# C:\mix-master\backend\src\utils\pitch_utils.py

from __future__ import annotations
from stages.pipeline_context import PipelineContext

from typing import Dict, Any, Tuple, List

import numpy as np
import librosa


def _quantize_single_midi_to_scale(m: float, scale_pcs: List[int]) -> float:
    """
    Cuantiza un valor MIDI flotante 'm' a la nota entera más cercana
    cuya pitch-class (n % 12) esté en 'scale_pcs'.

    Para cada pitch-class permitida s, buscamos el entero n = s + 12*k
    más cercano a m.
    """
    best_n = None
    best_dist = None
    for s in scale_pcs:
        k = round((m - s) / 12.0)
        n = s + 12 * k
        dist = abs(n - m)
        if best_dist is None or dist < best_dist:
            best_dist = dist
            best_n = n
    return float(best_n)


def estimate_pitch_deviation(
    y: np.ndarray,
    sr: int,
    fmin_note: str = "C2",
    fmax_note: str = "C7",
) -> Dict[str, Any]:
    """
    Estima desviaciones globales de pitch para una señal mono:

      - Usa librosa.yin para estimar f0 por frame.
      - Convierte a notas MIDI.
      - Calcula la desviación en cents respecto al semitono más cercano.
      - Devuelve:
          - max_abs_deviation_cents
          - median_deviation_cents
          - recommended_global_shift_semitones (para centrar la afinación)

    Si no hay frames sonoros (todo NaN), devuelve valores por defecto.
    """
    if y.size == 0:
        return {
            "max_abs_deviation_cents": None,
            "median_deviation_cents": None,
            "recommended_global_shift_semitones": 0.0,
        }

    fmin_hz = librosa.note_to_hz(fmin_note)
    fmax_hz = librosa.note_to_hz(fmax_note)

    f0 = librosa.yin(y, fmin=fmin_hz, fmax=fmax_hz, sr=sr)

    mask = ~np.isnan(f0)
    if not mask.any():
        return {
            "max_abs_deviation_cents": None,
            "median_deviation_cents": None,
            "recommended_global_shift_semitones": 0.0,
        }

    f0_valid = f0[mask]
    midi = librosa.hz_to_midi(f0_valid)

    midi_rounded = np.round(midi)
    dev_semitones = midi - midi_rounded
    dev_cents = dev_semitones * 100.0

    max_abs_dev_cents = float(np.max(np.abs(dev_cents)))
    median_dev_cents = float(np.median(dev_cents))
    recommended_global_shift_semitones = float(-median_dev_cents / 100.0)

    return {
        "max_abs_deviation_cents": max_abs_dev_cents,
        "median_deviation_cents": median_dev_cents,
        "recommended_global_shift_semitones": recommended_global_shift_semitones,
    }


def apply_global_pitch_shift(
    y: np.ndarray,
    sr: int,
    shift_semitones: float,
) -> np.ndarray:
    """
    Aplica un pitch-shift global en semitonos usando librosa.effects.pitch_shift.

    - Soporta mono o multicanal (n_samples,) o (n_samples, n_channels).
    """
    if abs(shift_semitones) < 1e-3 or y.size == 0:
        return y

    if y.ndim == 1:
        y_shifted = librosa.effects.pitch_shift(y, sr=sr, n_steps=shift_semitones)
        return y_shifted.astype(y.dtype)

    # Multicanal: aplicar canal a canal
    y_T = y.T  # (n_channels, n_samples)
    shifted_channels = []
    for ch in y_T:
        ch_shifted = librosa.effects.pitch_shift(ch, sr=sr, n_steps=shift_semitones)
        shifted_channels.append(ch_shifted)

    y_shifted_T = np.stack(shifted_channels, axis=0)
    y_shifted = y_shifted_T.T  # (n_samples, n_channels)
    return y_shifted.astype(y.dtype)


def tune_vocal_time_varying(
    y: np.ndarray,
    sr: int,
    tuning_strength: float = 1.0,
    max_shift_semitones: float | None = None,
    pitch_cents_max_deviation: float | None = None,
    fmin_note: str = "C2",
    fmax_note: str = "C7",
    frame_length: int = 2048,
    hop_length: int = 512,
    allowed_scale_pcs: List[int] | None = None,
) -> np.ndarray:
    """
    Afinación time-varying (nota a nota) con escala + corrección suave:

      - Cuantiza a la nota de la escala más cercana (si allowed_scale_pcs no es None).
      - Corrige por regiones de nota.
      - La fuerza de corrección es dinámica:
          * regiones muy desviadas -> corrección fuerte
          * regiones poco desviadas -> corrección suave o nula
      - Usa crossfades en bordes para evitar clics.

    Esto reduce el efecto robótico y mantiene más “humanidad” en la voz.
    """
    if y.size == 0:
        return y

    # Curva de pitch en mono (audio puede ser multicanal)
    if y.ndim == 1:
        y_mono = y.astype(np.float32)
    else:
        y_mono = np.mean(y, axis=1).astype(np.float32)

    fmin_hz = librosa.note_to_hz(fmin_note)
    fmax_hz = librosa.note_to_hz(fmax_note)

    f0 = librosa.yin(
        y_mono,
        fmin=fmin_hz,
        fmax=fmax_hz,
        sr=sr,
        frame_length=frame_length,
        hop_length=hop_length,
    )

    n_frames = len(f0)
    frames_idx = np.arange(n_frames)

    midi = np.full_like(f0, np.nan, dtype=np.float32)
    mask_valid = ~np.isnan(f0)
    if not mask_valid.any():
        return y

    midi[mask_valid] = librosa.hz_to_midi(f0[mask_valid])

    # --- Cuantización a escala o cromática ---
    target_midi = np.full_like(midi, np.nan, dtype=np.float32)
    if allowed_scale_pcs:
        idx_valid = np.where(mask_valid)[0]
        for i in idx_valid:
            target_midi[i] = _quantize_single_midi_to_scale(float(midi[i]), allowed_scale_pcs)
    else:
        target_midi[mask_valid] = np.round(midi[mask_valid])

    dev_semitones = np.full_like(midi, 0.0, dtype=np.float32)
    dev_semitones[mask_valid] = midi[mask_valid] - target_midi[mask_valid]
    dev_cents = dev_semitones * 100.0

    # Umbral de corrección (en cents) para saltarse regiones casi perfectas
    cents_thresh = pitch_cents_max_deviation if pitch_cents_max_deviation is not None else 0.0
    max_shift = float(max_shift_semitones) if max_shift_semitones is not None else None

    # Agrupar frames contiguos con misma target_midi -> regiones
    regions: List[Tuple[int, int]] = []
    current_start = None
    current_target = None

    for i in frames_idx:
        if not mask_valid[i]:
            if current_start is not None:
                regions.append((current_start, i - 1))
                current_start = None
                current_target = None
            continue

        t_midi = target_midi[i]

        if current_start is None:
            current_start = i
            current_target = t_midi
        else:
            if t_midi != current_target:
                regions.append((current_start, i - 1))
                current_start = i
                current_target = t_midi

    if current_start is not None:
        regions.append((current_start, n_frames - 1))

    y_out = y.copy()

    MIN_SEG_SAMPLES = 2048   # no afinamos segmentos ridículamente cortos
    MAX_FADE_SAMPLES = 1024  # crossfade máximo en cada borde

    for (start_f, end_f) in regions:
        region_mask = mask_valid[start_f : end_f + 1]
        if not region_mask.any():
            continue

        region_dev_cents = dev_cents[start_f : end_f + 1][region_mask]

        # Si toda la región está dentro del umbral de corrección -> la dejamos tal cual
        if np.all(np.abs(region_dev_cents) < cents_thresh):
            continue

        # --- NUEVO: fuerza de corrección dinámica por región ---
        median_abs_cents = float(np.median(np.abs(region_dev_cents)))

        # Queremos:
        #   - si la desviación es pequeña -> poco tuning
        #   - si es grande -> más tuning, hasta tuning_strength
        # Escalamos en función de la desviación, saturando a 100 cents
        base_strength = float(tuning_strength)
        REF_CENTS_FULL = 100.0  # a partir de 1 semitono de error aplicamos la fuerza completa

        dyn_factor = min(median_abs_cents / REF_CENTS_FULL, 1.0)
        effective_strength = base_strength * dyn_factor

        # Si la corrección resultante es muy pequeña, ni tocamos
        if effective_strength < 0.1:
            continue

        region_dev_semitones = dev_semitones[start_f : end_f + 1][region_mask]
        median_dev_semitones = float(np.median(region_dev_semitones))

        # Shift = corregir mediana de dev, pero aplicado con fuerza efectiva
        shift_semitones = -median_dev_semitones * effective_strength

        # Limitar por max_shift
        if max_shift is not None:
            if shift_semitones > max_shift:
                shift_semitones = max_shift
            elif shift_semitones < -max_shift:
                shift_semitones = -max_shift

        if abs(shift_semitones) < 1e-2:
            continue

        start_sample = int(start_f * hop_length)
        end_sample = int(min((end_f + 1) * hop_length, y.shape[0]))

        if end_sample <= start_sample:
            continue

        segment = y_out[start_sample:end_sample]
        seg_len = segment.shape[0]

        if seg_len < MIN_SEG_SAMPLES:
            continue

        seg_shifted = apply_global_pitch_shift(segment, sr=sr, shift_semitones=shift_semitones)

        # CROSSFADE
        fade_len = min(MAX_FADE_SAMPLES, seg_len // 4)
        if fade_len < 16:
            y_out[start_sample:end_sample] = seg_shifted
            continue

        if segment.ndim == 1:
            w = np.linspace(0.0, 1.0, fade_len, dtype=segment.dtype)
            w_rev = w[::-1]
        else:
            w = np.linspace(0.0, 1.0, fade_len, dtype=segment.dtype).reshape(-1, 1)
            w_rev = w[::-1, :]

        new_seg = segment.copy()

        # fade-in
        new_seg[:fade_len] = segment[:fade_len] * (1.0 - w) + seg_shifted[:fade_len] * w
        # centro
        if seg_len > 2 * fade_len:
            new_seg[fade_len:-fade_len] = seg_shifted[fade_len:-fade_len]
        # fade-out
        new_seg[-fade_len:] = segment[-fade_len:] * (1.0 - w_rev) + seg_shifted[-fade_len:] * w_rev

        y_out[start_sample:end_sample] = new_seg

    return y_out

