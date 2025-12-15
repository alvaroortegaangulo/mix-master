from __future__ import annotations

import sys
import json
import shutil
import logging
import numpy as np
import soundfile as sf
from pathlib import Path
from typing import Dict, List, Optional, Any

# Pedalboard imports for effects
from pedalboard import (
    Pedalboard,
    Compressor,
    HighShelfFilter,
    LowShelfFilter,
    PeakingFilter,
    Gain
)

# --- hack sys.path ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.logger import logger

try:
    from context import PipelineContext
except ImportError:
    PipelineContext = None  # type: ignore


STAGE_ID = "S6_MANUAL_CORRECTION_ADJUSTMENT"


def _load_corrections(stage_dir: Path) -> List[Dict[str, Any]]:
    json_path = stage_dir / "changes.json"
    if not json_path.exists():
        logger.logger.warning(f"[{STAGE_ID}] No se encontró changes.json en {stage_dir}")
        return []
    try:
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            # data deberia ser una lista de correcciones: { name, volume_db, pan, eq, compression, mute, solo }
            # O un objeto que contiene "corrections"
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "corrections" in data:
                return data["corrections"]
            return []
    except Exception as e:
        logger.logger.error(f"[{STAGE_ID}] Error leyendo changes.json: {e}")
        return []


def process(context: PipelineContext) -> bool:
    """
    S6_MANUAL_CORRECTION_ADJUSTMENT:
    1. Lee changes.json del stage_dir actual.
    2. Busca stems finales disponibles (prioriza S6_MANUAL_CORRECTION -> S11_REPORT_GENERATION).
    3. Aplica efectos (EQ, Comp, Gain, Pan) a cada stem.
    4. Guarda los stems procesados en stage_dir.
    5. mixdown_stems.py se encargará (llamado externamente) de sumarlos.
    """
    stage_id = STAGE_ID
    try:
        context.stage_id = STAGE_ID
    except Exception:
        pass
    stage_dir = context.get_stage_dir(stage_id)
    temp_root = context.temp_root

    # 1. Correcciones
    corrections = _load_corrections(stage_dir)
    if not corrections:
        logger.logger.info(f"[{stage_id}] Sin correcciones definidas. Saliendo.")
        return False

    # 2. Origen: stems finales disponibles (S6 -> S11 -> S10 -> S0 fallback)
    candidate_sources = [
        temp_root / "S6_MANUAL_CORRECTION",
        temp_root / "S11_REPORT_GENERATION",
        temp_root / "S10_MASTER_FINAL_LIMITS",
        temp_root / "S0_SESSION_FORMAT",
        temp_root / "S0_MIX_ORIGINAL",
    ]

    source_dir: Optional[Path] = None
    for cand in candidate_sources:
        if cand.exists():
            stems_here = [p for p in cand.glob("*.wav") if p.name.lower() != "full_song.wav"]
            if stems_here:
                source_dir = cand
                break

    if source_dir is None:
        logger.logger.error(f"[{stage_id}] No se encontraron stems fuente en {temp_root}")
        return False

    # Mapa de correcciones por nombre de stem
    corr_map = {c["name"]: c for c in corrections}

    # Check solo mode
    # Si hay algun stem en SOLO, muteamos el resto.
    solo_active = any(c.get("solo", False) for c in corrections)

    logger.logger.info(f"[{stage_id}] Procesando correcciones para {len(corrections)} stems. Solo Mode: {solo_active}")

    # Procesar cada stem
    stems_found = list(source_dir.glob("*.wav"))
    processed_count = 0

    for stem_path in stems_found:
        if stem_path.name.lower() == "full_song.wav":
            continue

        stem_name = stem_path.stem # 'vocals', 'drums', etc.
        corr = corr_map.get(stem_name)

        # Si no hay correccion explicita, copiamos tal cual?
        # El frontend manda TODOS los stems, asi que si falta es raro.
        # Asumiremos defaults si falta.
        if not corr:
            corr = {
                "volume_db": 0.0,
                "pan": 0.0,
                "mute": False,
                "solo": False,
                "eq": {"low": 0, "mid": 0, "high": 0},
                "compression": {"threshold": 0, "ratio": 1}
            }

        # Determinamos si debe sonar
        is_muted = corr.get("mute", False)
        is_solo = corr.get("solo", False)

        should_play = True
        if solo_active:
            if not is_solo:
                should_play = False
        else:
            if is_muted:
                should_play = False

        # Leemos audio
        try:
            audio, sr = sf.read(str(stem_path))
        except Exception as e:
            logger.logger.warning(f"[{stage_id}] Error leyendo stem {stem_name}: {e}")
            continue

        # Asegurar stereo (Pedalboard trabaja mejor asi, o manejamos mono)
        if len(audio.shape) == 1:
            audio = np.stack([audio, audio], axis=1) # Mono to Stereo
        elif audio.shape[1] > 2:
            audio = audio[:, :2] # Keep first 2

        if not should_play:
            # Silencio
            audio = np.zeros_like(audio)
        else:
            # Chain de efectos
            board = Pedalboard()

            # 1. Compressor
            comp_cfg = corr.get("compression", {})
            thresh = float(comp_cfg.get("threshold", 0))
            ratio = float(comp_cfg.get("ratio", 1))
            if thresh < 0 or ratio > 1:
                 # Pedalboard Compressor defaults: threshold_db=0, ratio=1
                 board.append(Compressor(threshold_db=thresh, ratio=ratio))

            # 2. EQ
            eq_cfg = corr.get("eq", {})
            low_gain = float(eq_cfg.get("low", 0))
            mid_gain = float(eq_cfg.get("mid", 0))
            high_gain = float(eq_cfg.get("high", 0))

            if abs(low_gain) > 0.01:
                board.append(LowShelfFilter(cutoff_frequency_hz=320, gain_db=low_gain))
            if abs(mid_gain) > 0.01:
                board.append(PeakingFilter(cutoff_frequency_hz=1000, gain_db=mid_gain, q=1.0))
            if abs(high_gain) > 0.01:
                board.append(HighShelfFilter(cutoff_frequency_hz=3200, gain_db=high_gain))

            # 3. Volume
            vol_db = float(corr.get("volume_db", 0))
            if abs(vol_db) > 0.01:
                board.append(Gain(gain_db=vol_db))

            # Apply Pedalboard
            try:
                # Pedalboard espera (channels, samples) pero soundfile devuelve (samples, channels)
                # Ojo: Pedalboard __call__ input: (C, T) array or (T, C) if implicit?
                # Docs: "input_audio must be either a NumPy array of shape (channels, samples)..."
                # So transpose.
                input_audio = audio.T
                output_audio = board(input_audio, sr)
                audio = output_audio.T
            except Exception as e:
                logger.logger.error(f"[{stage_id}] Error aplicando efectos a {stem_name}: {e}")

            # 4. Pan (manual con numpy)
            pan = float(corr.get("pan", 0))
            if abs(pan) > 0.01:
                # Constant power panning
                # pan range -1 (L) to 1 (R)
                # L = cos(theta), R = sin(theta)
                # theta from 0 to pi/2. Pan -1 -> 0, Pan 1 -> pi/2
                # map [-1, 1] -> [0, pi/2]
                theta = (pan + 1) * (np.pi / 4)
                gain_L = np.cos(theta)
                gain_R = np.sin(theta)

                audio[:, 0] *= gain_L
                audio[:, 1] *= gain_R

        # Guardar resultado
        out_path = stage_dir / f"{stem_name}.wav"
        sf.write(str(out_path), audio, sr)
        processed_count += 1

    logger.logger.info(f"[{stage_id}] Procesados {processed_count} stems.")
    return True
