from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List

import numpy as np
from pedalboard import Pedalboard, HighpassFilter, Compressor, Gain, Limiter
from pedalboard.io import AudioFile

from src.utils.stage_base import BaseCorrectionStage


def _safe_dbfs(value: float, floor: float = -120.0) -> float:
    v = float(value)
    if v <= 0.0:
        return floor
    return 20.0 * np.log10(v)


@dataclass
class MasteringRow:
    filename: str
    relative_path: str
    sample_rate: int
    num_channels: int
    duration_seconds: float
    peak_dbfs: float
    rms_dbfs: float
    is_vocal: bool
    is_bus_fx: bool
    bus_key: str | None
    recommended_target_peak_dbfs: float
    recommended_drive_db: float


@dataclass
class MasteringCorrectionResult:
    filename: str
    input_path: Path
    output_path: Path
    sample_rate: int
    num_channels: int
    duration_seconds: float
    is_vocal: bool
    is_bus_fx: bool
    bus_key: str | None
    original_peak_dbfs: float
    original_rms_dbfs: float
    resulting_peak_dbfs: float
    resulting_rms_dbfs: float
    pre_gain_db: float


def load_mastering_json(json_path: Path) -> List[MasteringRow]:
    if not json_path.exists():
        raise FileNotFoundError(f"No se encontro el JSON de analisis de mastering: {json_path}")

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Formato de JSON inesperado en {json_path}")

    rows: List[MasteringRow] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        try:
            rows.append(
                MasteringRow(
                    filename=item.get("filename") or item.get("file_path") or "",
                    relative_path=item.get("relative_path") or item.get("filename") or item.get("file_path") or "",
                    sample_rate=int(item.get("sample_rate", 0)),
                    num_channels=int(item.get("num_channels", 0)),
                    duration_seconds=float(item.get("duration_seconds", 0.0)),
                    peak_dbfs=float(item.get("peak_dbfs", 0.0)),
                    rms_dbfs=float(item.get("rms_dbfs", 0.0)),
                    is_vocal=bool(item.get("is_vocal", False)),
                    is_bus_fx=bool(item.get("is_bus_fx", False)),
                    bus_key=item.get("bus_key"),
                    recommended_target_peak_dbfs=float(item.get("recommended_target_peak_dbfs", -4.0)),
                    recommended_drive_db=float(item.get("recommended_drive_db", 0.0)),
                )
            )
        except Exception:
            continue
    return rows


def _apply_mastering_to_file(
    row: MasteringRow,
    input_media_dir: Path,
    vocal_tuning_media_dir: Path,
    output_media_dir: Path,
    vocal_filename: str = "vocal.wav",
) -> MasteringCorrectionResult:
    # ----------------------------------------------------------------------
    # 1) Seleccionar archivo de entrada (voz puede venir del afinado)
    # ----------------------------------------------------------------------
    base_input_path = (input_media_dir / row.relative_path).resolve()
    input_path = base_input_path

    if row.is_vocal:
        tuned_path = (vocal_tuning_media_dir / vocal_filename).resolve()
        if tuned_path.exists():
            input_path = tuned_path

    if not input_path.exists():
        raise FileNotFoundError(f"No se encontro el WAV de entrada para mastering: {input_path}")

    output_media_dir.mkdir(parents=True, exist_ok=True)
    output_path = (output_media_dir / row.filename).resolve()

    # ----------------------------------------------------------------------
    # 2) Leer audio
    # ----------------------------------------------------------------------
    with AudioFile(str(input_path), "r") as f:
        audio = f.read(f.frames)
        sr = f.samplerate
        num_channels = f.num_channels

    audio = audio.astype(np.float32, copy=False)

    if audio.size > 0:
        original_peak = float(np.max(np.abs(audio)))
        original_rms = float(np.sqrt(np.mean(audio ** 2)))
    else:
        original_peak = 0.0
        original_rms = 0.0

    original_peak_dbfs = _safe_dbfs(original_peak)
    original_rms_dbfs = _safe_dbfs(original_rms)
    crest_db = original_peak_dbfs - original_rms_dbfs

    # ----------------------------------------------------------------------
    # 3) Clasificación de la pista
    # ----------------------------------------------------------------------
    filename_lower = row.filename.lower()
    bus_key = (row.bus_key or "").lower()

    is_bus_fx = row.is_bus_fx
    is_vocal = row.is_vocal and not is_bus_fx

    is_kick = "kick" in filename_lower
    is_snare = "snare" in filename_lower or "clap" in filename_lower
    is_perc_name = "perc" in filename_lower or "cajon" in filename_lower or "timbal" in filename_lower
    is_drum_bus = bus_key == "drums"
    is_percussive = is_kick or is_snare or is_perc_name or is_drum_bus

    # ----------------------------------------------------------------------
    # 4) Target de pico más realista y suave
    # ----------------------------------------------------------------------
    base_target = row.recommended_target_peak_dbfs
    if not (-18.0 <= base_target <= -0.5):
        base_target = -4.0

    if is_bus_fx:
        # FX más bajos
        target_peak_dbfs = min(base_target, -6.0 if bus_key == "fx" else -5.0)
    elif is_vocal:
        # Voz entre -5 y -3 dBFS
        target_peak_dbfs = max(min(base_target, -3.0), -5.0)
    elif is_percussive:
        # Bombo/caja/perc entre -6 y -4 dBFS
        target_peak_dbfs = max(min(base_target, -4.0), -6.0)
    else:
        # Resto de instrumentos: -6 .. -3.5
        target_peak_dbfs = max(min(base_target, -3.5), -6.0)

    # ----------------------------------------------------------------------
    # 5) Pre-gain MUY conservador por tipo de pista
    # ----------------------------------------------------------------------
    gain_needed = target_peak_dbfs - original_peak_dbfs  # positivo = habría que subir

    if is_bus_fx:
        # Nunca subir FX en mastering; solo bajar un poco si vienen pasados
        pre_gain_db = np.clip(gain_needed * 0.3, -6.0, 0.0)
    elif is_vocal:
        # Si la voz viene muy alta, permitir bajarla. Si viene baja, subir muy poco.
        if gain_needed < 0:
            pre_gain_db = np.clip(gain_needed * 0.8, -4.0, 0.0)
        else:
            pre_gain_db = np.clip(gain_needed * 0.4, -1.0, 1.0)
    elif is_percussive:
        # Bombo y percusión: casi no se suben; se permite bajarlos suavemente
        if gain_needed < 0:
            pre_gain_db = np.clip(gain_needed * 0.7, -3.0, 0.0)
        else:
            pre_gain_db = np.clip(gain_needed * 0.3, -1.0, 1.0)
    else:
        # Otros: ajuste suave general
        pre_gain_db = np.clip(gain_needed * 0.5, -3.0, 2.0)

    # Valores muy pequeños -> nada
    if abs(pre_gain_db) < 0.25:
        pre_gain_db = 0.0

    effects = []
    if pre_gain_db != 0.0:
        effects.append(Gain(gain_db=pre_gain_db))

    # ----------------------------------------------------------------------
    # 6) Filtro de graves (DC / rumble) según tipo
    # ----------------------------------------------------------------------
    if is_bus_fx:
        effects.append(HighpassFilter(cutoff_frequency_hz=150.0))
    elif is_vocal:
        effects.append(HighpassFilter(cutoff_frequency_hz=80.0))
    elif is_percussive:
        effects.append(HighpassFilter(cutoff_frequency_hz=35.0))
    else:
        effects.append(HighpassFilter(cutoff_frequency_hz=30.0))

    # ----------------------------------------------------------------------
    # 7) Compresión muy sutil (o ninguna) según crest y tipo
    # ----------------------------------------------------------------------
    use_compressor = True

    # Nunca comprimimos los buses FX en mastering, solo los limitamos por seguridad
    if is_bus_fx:
        use_compressor = False

    # Si la pista ya viene muy comprimida (crest bajo), no insistimos
    if crest_db <= 5.0 and not is_vocal:
        use_compressor = False

    if use_compressor:
        if is_vocal:
            # Compresión suave tipo bus vocal
            comp_ratio = 1.4
            comp_attack = 12.0
            comp_release = 220.0
            # Domar sólo los picos más fuertes
            comp_threshold = min(original_peak_dbfs - 5.0, -4.0)
        elif is_percussive:
            # Respetar transitorios de bombo/caja
            comp_ratio = 1.25
            comp_attack = 25.0
            comp_release = 160.0
            comp_threshold = min(original_peak_dbfs - 4.0, -3.0)
        else:
            # Otros stems: glue muy suave
            comp_ratio = 1.3
            comp_attack = 18.0
            comp_release = 240.0
            comp_threshold = min(original_peak_dbfs - 4.5, -3.5)

        effects.append(
            Compressor(
                threshold_db=comp_threshold,
                ratio=comp_ratio,
                attack_ms=comp_attack,
                release_ms=comp_release,
            )
        )

    # ----------------------------------------------------------------------
    # 8) Limitador de seguridad (NO para volumen extremo)
    # ----------------------------------------------------------------------
    if is_bus_fx:
        limiter_threshold = -6.0
        limiter_release = 120.0
    elif is_percussive:
        # Dejarle respirar algo más
        limiter_threshold = -1.5
        limiter_release = 70.0
    else:
        limiter_threshold = -1.0
        limiter_release = 120.0

    effects.append(
        Limiter(
            threshold_db=limiter_threshold,
            release_ms=limiter_release,
        )
    )

    board = Pedalboard(effects)
    processed = board(audio, sample_rate=sr) if effects else audio

    if processed.size > 0:
        processed_peak = float(np.max(np.abs(processed)))
        processed_rms = float(np.sqrt(np.mean(processed ** 2)))
    else:
        processed_peak = 0.0
        processed_rms = 0.0

    resulting_peak_dbfs = _safe_dbfs(processed_peak)
    resulting_rms_dbfs = _safe_dbfs(processed_rms)

    with AudioFile(str(output_path), "w", sr, num_channels) as f:
        f.write(processed.astype(np.float32, copy=False))

    return MasteringCorrectionResult(
        filename=row.filename,
        input_path=input_path,
        output_path=output_path,
        sample_rate=sr,
        num_channels=num_channels,
        duration_seconds=row.duration_seconds,
        is_vocal=is_vocal,
        is_bus_fx=is_bus_fx,
        bus_key=row.bus_key,
        original_peak_dbfs=original_peak_dbfs,
        original_rms_dbfs=original_rms_dbfs,
        resulting_peak_dbfs=resulting_peak_dbfs,
        resulting_rms_dbfs=resulting_rms_dbfs,
        pre_gain_db=pre_gain_db,
    )


def write_mastering_log(results: List[MasteringCorrectionResult], log_json_path: Path) -> Path:
    log_json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = []
    for r in results:
        payload.append(
            {
                "filename": r.filename,
                "input_path": str(r.input_path),
                "output_path": str(r.output_path),
                "sample_rate": r.sample_rate,
                "num_channels": r.num_channels,
                "duration_seconds": r.duration_seconds,
                "is_vocal": bool(r.is_vocal),
                "is_bus_fx": bool(r.is_bus_fx),
                "bus_key": r.bus_key,
                "original_peak_dbfs": r.original_peak_dbfs,
                "original_rms_dbfs": r.original_rms_dbfs,
                "resulting_peak_dbfs": r.resulting_peak_dbfs,
                "resulting_rms_dbfs": r.resulting_rms_dbfs,
                "pre_gain_db": r.pre_gain_db,
            }
        )
    log_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return log_json_path


class MasteringStage(BaseCorrectionStage[MasteringRow, MasteringCorrectionResult]):
    def __init__(
        self,
        analysis_json_path: Path,
        input_media_dir: Path,
        vocal_tuning_media_dir: Path,
        output_media_dir: Path,
        vocal_filename: str = "vocal.wav",
    ) -> None:
        super().__init__(
            analysis_json_path=analysis_json_path,
            input_media_dir=input_media_dir,
            output_media_dir=output_media_dir,
        )
        self.vocal_tuning_media_dir = vocal_tuning_media_dir
        self.vocal_filename = vocal_filename

    def load_rows(self) -> List[MasteringRow]:
        return load_mastering_json(self.analysis_json_path)

    def process_row(self, row: MasteringRow) -> MasteringCorrectionResult:
        return _apply_mastering_to_file(
            row=row,
            input_media_dir=self.input_media_dir,
            vocal_tuning_media_dir=self.vocal_tuning_media_dir,
            output_media_dir=self.output_media_dir,
            vocal_filename=self.vocal_filename,
        )

    def write_log(self, results: List[MasteringCorrectionResult]) -> Path:
        log_json_path = self.output_media_dir / "mastering_correction_log.json"
        return write_mastering_log(results, log_json_path)


def run_mastering_correction(
    analysis_json_path: Path,
    input_media_dir: Path,
    vocal_tuning_media_dir: Path,
    output_media_dir: Path,
    vocal_filename: str = "vocal.wav",
) -> Path:
    stage = MasteringStage(
        analysis_json_path=analysis_json_path,
        input_media_dir=input_media_dir,
        vocal_tuning_media_dir=vocal_tuning_media_dir,
        output_media_dir=output_media_dir,
        vocal_filename=vocal_filename,
    )
    return stage.run()
