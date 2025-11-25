from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional

import numpy as np
import soundfile as sf
import essentia
import essentia.standard as es
import pyrubberband as pyrb


# ----------------------------------------------------------------------
# Configuración global
# ----------------------------------------------------------------------

PITCH_FRAME_SIZE = 2048
PITCH_HOP_SIZE = 128
PITCH_CONFIDENCE_MIN = 0.2  # por debajo de esto consideramos "no confiable"


@dataclass
class VocalAutoTuneResult:
    vocal_input_path: Path
    vocal_output_path: Path
    song_key: str
    song_scale: str
    num_frames: int
    shift_semitones_min: float
    shift_semitones_max: float
    shift_semitones_mean: float


# ----------------------------------------------------------------------
# Utilidades de tonalidad / escala
# ----------------------------------------------------------------------

_KEY_TO_SEMITONE = {
    "C": 0,
    "C#": 1, "DB": 1,
    "D": 2,
    "D#": 3, "EB": 3,
    "E": 4, "FB": 4,
    "F": 5, "E#": 5,
    "F#": 6, "GB": 6,
    "G": 7,
    "G#": 8, "AB": 8,
    "A": 9,
    "A#": 10, "BB": 10,
    "B": 11, "CB": 11,
}


def _normalize_key_str(key: str) -> str:
    k = key.strip().upper()
    # Normalizamos bemoles a "B" sin "b"/"#" minúsculas sueltas
    k = k.replace("M", "")  # por si viniera "Cm" etc. (por seguridad)
    return k


def _key_to_semitone(key: str) -> int:
    k = _normalize_key_str(key)
    if k not in _KEY_TO_SEMITONE:
        raise ValueError(f"Clave no reconocida: {key!r}")
    return _KEY_TO_SEMITONE[k]


def _scale_pitch_classes(song_key: str, song_scale: str) -> List[int]:
    """
    Devuelve los pitch classes (0-11) permitidos para la escala (key + major/minor).
    """
    root = _key_to_semitone(song_key)

    scale = song_scale.strip().lower()
    if scale.startswith("maj"):
        pattern = [0, 2, 4, 5, 7, 9, 11]  # mayor
    else:
        pattern = [0, 2, 3, 5, 7, 8, 10]  # menor natural

    pcs = [int((root + deg) % 12) for deg in pattern]
    pcs = sorted(set(pcs))
    return pcs


# ----------------------------------------------------------------------
# Lectura de key_analysis.csv
# ----------------------------------------------------------------------


def _read_song_key_from_csv(key_csv_path: Path) -> Tuple[str, str]:
    """
    Lee la primera fila de key_analysis.csv y devuelve (key, scale).
    """
    if not key_csv_path.exists():
        raise FileNotFoundError(f"No se encontró key_analysis.csv en: {key_csv_path}")

    with key_csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        try:
            row = next(reader)
        except StopIteration:
            raise RuntimeError(f"key_analysis.csv está vacío: {key_csv_path}")

    song_key = row["key"].strip()
    song_scale = row["scale"].strip()
    return song_key, song_scale


# ----------------------------------------------------------------------
# Análisis de F0 con PitchMelodia
# ----------------------------------------------------------------------


def _extract_pitch_curve(audio_mono: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Extrae F0 y confianza por frame usando Essentia PitchMelodia.
    Devuelve:
      pitch_hz: np.ndarray [num_frames]
      pitch_conf: np.ndarray [num_frames]
    """
    essentia.log.infoActive = False
    essentia.log.warningActive = False

    pitch_extractor = es.PitchMelodia(
        frameSize=PITCH_FRAME_SIZE,
        hopSize=PITCH_HOP_SIZE,
    )
    pitch_hz, pitch_conf = pitch_extractor(audio_mono)
    return np.asarray(pitch_hz, dtype=np.float32), np.asarray(pitch_conf, dtype=np.float32)


def _hz_to_midi(f: float) -> float:
    if f <= 0.0:
        return float("nan")
    return 69.0 + 12.0 * math.log2(f / 440.0)




def _pitch_to_midi(pitch_hz: np.ndarray, pitch_conf: np.ndarray) -> np.ndarray:
    """
    Convierte pitch (Hz) + confianza en un vector de notas MIDI (float),
    con NaNs en frames sin pitch fiable.
    """
    midi = np.full_like(pitch_hz, np.nan, dtype=np.float32)
    mask = (pitch_conf >= PITCH_CONFIDENCE_MIN) & (pitch_hz > 0.0)
    if not np.any(mask):
        return midi
    midi[mask] = 69.0 + 12.0 * np.log2(pitch_hz[mask] / 440.0)
    return midi


def _quantize_midi_to_scale(
    midi: np.ndarray,
    allowed_pcs: List[int],
) -> np.ndarray:
    """
    Para cada frame con nota MIDI valida, la engancha a la nota mas cercana
    cuya pitch class esta en la escala permitida.
    Devuelve un array target_midi (float) del mismo tamano.
    """
    target = np.copy(midi)

    for i in range(midi.shape[0]):
        m = float(midi[i])
        if math.isnan(m):
            continue

        base_int = int(round(m))
        best_m = base_int
        best_dist = None

        # Buscamos candidatos +-3 semitonos alrededor
        for offset in range(-3, 4):
            cand = base_int + offset
            pc = cand % 12
            if pc not in allowed_pcs:
                continue
            dist = abs(cand - m)
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best_m = cand

        if best_dist is not None:
            target[i] = float(best_m)
        else:
            target[i] = m

    return target

def _build_shift_curve(midi: np.ndarray, target_midi: np.ndarray) -> np.ndarray:
    """
    shift[i] = target_midi[i] - midi[i] (en semitonos).
    Frames no voiced -> shift = 0.
    """
    shift = np.zeros_like(target_midi, dtype=np.float32)
    voiced = ~np.isnan(midi) & ~np.isnan(target_midi)
    shift[voiced] = target_midi[voiced] - midi[voiced]
    return shift



def _segment_shift_curve(shift: np.ndarray, tol: float = 0.25) -> List[Tuple[int, int, float]]:
    """
    Agrupa frames consecutivos con shift similar en segmentos:
      (start_frame, end_frame_inclusive, shift_value)

    tol: diferencia maxima de semitonos para considerar que sigue siendo la misma nota.
    """
    n = shift.shape[0]
    if n == 0:
        return []

    diff = np.abs(np.diff(shift))
    boundaries = np.where(diff > tol)[0]
    starts = np.concatenate(([0], boundaries + 1))
    ends = np.concatenate((boundaries, [n - 1]))

    segments: List[Tuple[int, int, float]] = []
    for start, end in zip(starts, ends):
        segments.append((int(start), int(end), float(np.mean(shift[start:end + 1]))))

    return segments

# ----------------------------------------------------------------------
# Aplicación de pitch shifting por segmentos (pyrubberband)
# ----------------------------------------------------------------------


def _apply_pitch_corrections(
    audio_mono: np.ndarray,
    sr: int,
    segments: List[Tuple[int, int, float]],
) -> np.ndarray:
    """
    Aplica pitch shift por segmentos sobre audio_mono, usando pyrubberband
    con un shift constante por segmento.

    audio_mono: (num_samples,)
    segments: lista de (start_frame, end_frame_inclusive, shift_semitones)
    """
    num_samples = audio_mono.shape[0]
    out = np.copy(audio_mono).astype(np.float32, copy=False)

    for (start_f, end_f, shift_val) in segments:
        # Convertimos frames -> samples (aprox)
        start_sample = start_f * PITCH_HOP_SIZE
        end_sample = (end_f + 1) * PITCH_HOP_SIZE
        if start_sample >= num_samples:
            continue
        if end_sample > num_samples:
            end_sample = num_samples

        if end_sample <= start_sample:
            continue

        seg = audio_mono[start_sample:end_sample]

        if abs(shift_val) < 0.01:
            continue  # ya tenemos la copia original en out

        seg_ps = pyrb.pitch_shift(seg, sr, n_steps=shift_val)

        # Aseguramos misma longitud (por seguridad)
        L = min(seg.shape[0], seg_ps.shape[0])
        out[start_sample:start_sample + L] = seg_ps[:L]

        # Si Rubber Band devuelve ligeramente menos samples, rellenamos la cola con original
        if L < seg.shape[0]:
            out[start_sample + L:end_sample] = seg[L:seg.shape[0]]

    return out


# ----------------------------------------------------------------------
# Punto de entrada de alto nivel
# ----------------------------------------------------------------------


def run_vocal_tuning_autotune(
    input_media_dir: Path,
    output_media_dir: Path,
    key_csv_path: Optional[Path] = None,
    vocal_filename: str = "vocal.wav",
) -> VocalAutoTuneResult:
    """
    Auto-Tune offline de vocal.wav hacia la tonalidad del tema dada por key_analysis.csv.

    - Lee key_analysis.csv para obtener (key, scale).
    - Busca vocal_filename dentro de input_media_dir (ej. media/loudness/vocal.wav).
    - Extrae curva de F0 con PitchMelodia.
    - Cuantiza cada frame a la escala (key + major/minor).
    - Calcula una curva de shift en semitonos (nota a nota).
    - Segmenta la curva en tramos con shift aproximadamente constante.
    - Aplica pyrubberband.pitch_shift por segmento.
    - Escribe vocal.wav corregido en output_media_dir.
    - Devuelve un VocalAutoTuneResult con estadísticas básicas.

    Si key_csv_path es None, intentará deducirlo como:
      input_media_dir/../.. /analysis/key_analysis.csv
    """
    input_media_dir = input_media_dir.resolve()
    output_media_dir = output_media_dir.resolve()
    output_media_dir.mkdir(parents=True, exist_ok=True)

    # Deducción por defecto de key_analysis.csv
    if key_csv_path is None:
        key_csv_path = input_media_dir.parent.parent / "analysis" / "key_analysis.csv"

    key_csv_path = key_csv_path.resolve()

    vocal_input_path = input_media_dir / vocal_filename
    if not vocal_input_path.exists():
        raise FileNotFoundError(f"No se encontró el stem de voz: {vocal_input_path}")

    # 1) Tonalidad global del tema
    song_key, song_scale = _read_song_key_from_csv(key_csv_path)
    allowed_pcs = _scale_pitch_classes(song_key, song_scale)

    # 2) Cargamos vocal.wav (esperado mono, pero aceptamos multi y lo reducimos)
    audio, sr = sf.read(str(vocal_input_path), dtype="float32", always_2d=True)
    num_samples, num_channels = audio.shape

    if num_channels == 1:
        audio_mono = audio[:, 0].astype(np.float32)
    else:
        audio_mono = audio.mean(axis=1).astype(np.float32)

    duration_seconds = float(num_samples) / float(sr) if num_samples > 0 else 0.0

    # 3) Curva de F0
    pitch_hz, pitch_conf = _extract_pitch_curve(audio_mono)
    midi = _pitch_to_midi(pitch_hz, pitch_conf)

    # 4) Cuantización a la escala
    target_midi = _quantize_midi_to_scale(midi, allowed_pcs)
    shift_curve = _build_shift_curve(midi, target_midi)

    # 5) Segmentación por notas (shift aproximadamente constante)
    segments = _segment_shift_curve(shift_curve, tol=0.25)

    # 6) Aplicar pitch shift por segmentos
    tuned_mono = _apply_pitch_corrections(audio_mono, sr, segments)

    # 7) Reconstruir canales (si original era estéreo, clonamos el canal afinado)
    if num_channels == 1:
        tuned_audio = tuned_mono
    else:
        tuned_audio = np.tile(tuned_mono[:, None], (1, num_channels))

    # 8) Guardar resultado
    vocal_output_path = output_media_dir / vocal_filename
    sf.write(str(vocal_output_path), tuned_audio, sr)

    # 9) Métricas de resumen del shift aplicado
    if shift_curve.size > 0:
        shift_min = float(np.min(shift_curve))
        shift_max = float(np.max(shift_curve))
        shift_mean = float(np.mean(shift_curve))
    else:
        shift_min = shift_max = shift_mean = 0.0

    result = VocalAutoTuneResult(
        vocal_input_path=vocal_input_path,
        vocal_output_path=vocal_output_path,
        song_key=song_key,
        song_scale=song_scale,
        num_frames=int(shift_curve.shape[0]),
        shift_semitones_min=shift_min,
        shift_semitones_max=shift_max,
        shift_semitones_mean=shift_mean,
    )

    return result


def export_vocal_autotune_log(result: VocalAutoTuneResult, csv_path: Path) -> None:
    """
    Exporta un log simple de la operación de Auto-Tune de la voz.
    """
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "vocal_input_path",
        "vocal_output_path",
        "song_key",
        "song_scale",
        "num_frames",
        "shift_semitones_min",
        "shift_semitones_max",
        "shift_semitones_mean",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow({
            "vocal_input_path": str(result.vocal_input_path),
            "vocal_output_path": str(result.vocal_output_path),
            "song_key": result.song_key,
            "song_scale": result.song_scale,
            "num_frames": result.num_frames,
            "shift_semitones_min": f"{result.shift_semitones_min:.3f}",
            "shift_semitones_max": f"{result.shift_semitones_max:.3f}",
            "shift_semitones_mean": f"{result.shift_semitones_mean:.3f}",
        })
