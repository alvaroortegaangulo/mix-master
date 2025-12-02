# C:\mix-master\backend\src\stages\S7_MIXBUS_TONAL_BALANCE.py

from __future__ import annotations

import sys
import os
from pathlib import Path
from typing import Dict, Any

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from pedalboard import (  # noqa: E402
    Pedalboard,
    LowShelfFilter,
    HighShelfFilter,
    PeakFilter,
)

from utils.analysis_utils import get_temp_dir  # noqa: E402
from utils.tonal_balance_utils import (      # noqa: E402
    get_freq_bands,
    compute_band_energies,
    get_style_tonal_profile,
    compute_tonal_error,
)


def load_analysis(contract_id: str) -> Dict[str, Any]:
    """
    Carga el JSON de análisis generado por analysis\\S7_MIXBUS_TONAL_BALANCE.py.
    """
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data


# ---------------------------------------------------------------------
# EQ multibanda con Pedalboard
# ---------------------------------------------------------------------

def _build_pedalboard_eq(
    eq_gains_db: Dict[str, float],
    sr: int,
) -> Pedalboard:
    """
    Construye una Pedalboard con una cadena de filtros
    (LowShelf / Peak / HighShelf) a partir de:

      - eq_gains_db: dict band_id -> gain_db
      - get_freq_bands(): define rangos de frecuencia por banda

    La idea es aproximar el comportamiento del EQ por bandas
    FFT original usando:

      - LowShelfFilter para la primera banda (graves)
      - HighShelfFilter para la última banda (agudos)
      - PeakFilter para las bandas intermedias
    """
    bands = get_freq_bands()
    nyquist = float(sr) / 2.0 if sr > 0 else None

    plugins = []

    if not bands:
        return Pedalboard([])

    n_bands = len(bands)

    for idx, band in enumerate(bands):
        band_id = band.get("id")
        if band_id is None:
            continue

        gain_db = float(eq_gains_db.get(band_id, 0.0))
        # Evitar filtros inútiles
        if abs(gain_db) < 1e-3:
            continue

        f_min = float(band.get("f_min", 0.0))
        f_max = float(band.get("f_max", 0.0))

        # Clamp básico al rango útil
        if nyquist is not None and nyquist > 0.0:
            f_min = max(0.0, min(f_min, nyquist))
            f_max = max(0.0, min(f_max, nyquist))

        if f_max <= 0.0:
            continue

        # Banda inferior -> LowShelf
        if idx == 0 or f_min <= 0.0:
            cutoff = max(20.0, f_max if nyquist is None else min(f_max, nyquist))
            q = 0.707  # Q moderada
            plugins.append(
                LowShelfFilter(
                    cutoff_frequency_hz=cutoff,
                    gain_db=gain_db,
                    q=q,
                )
            )
            continue

        # Banda superior -> HighShelf
        if idx == n_bands - 1 or (nyquist is not None and f_max >= nyquist * 0.9):
            cutoff = max(20.0, f_min if nyquist is None else min(f_min, nyquist))
            q = 0.707
            plugins.append(
                HighShelfFilter(
                    cutoff_frequency_hz=cutoff,
                    gain_db=gain_db,
                    q=q,
                )
            )
            continue

        # Bandas intermedias -> PeakFilter centrado en la banda
        # Centro geométrico para evitar sesgo hacia f_max
        if f_min <= 0.0:
            center = f_max
        else:
            center = (f_min * f_max) ** 0.5

        if nyquist is not None:
            center = max(20.0, min(center, nyquist))

        bandwidth = max(f_max - f_min, 1.0)
        # Q aproximado: ratio centro / ancho
        q = float(center / bandwidth) if bandwidth > 0.0 else 1.0
        q = max(0.1, min(q, 4.0))  # valores razonables

        plugins.append(
            PeakFilter(
                cutoff_frequency_hz=center,
                gain_db=gain_db,
                q=q,
            )
        )

    return Pedalboard(plugins)


def _apply_multiband_eq_pedalboard(
    audio: np.ndarray,
    sr: int,
    eq_gains_db: Dict[str, float],
) -> np.ndarray:
    """
    Aplica un EQ multibanda usando Pedalboard.

    - audio: np.ndarray (N,) o (N, C)
    - eq_gains_db: dict band_id -> gain_db a aplicar en esa banda
    """
    x = np.asarray(audio, dtype=np.float32)

    if x.size == 0 or sr <= 0:
        return x

    if not eq_gains_db or all(abs(v) < 1e-3 for v in eq_gains_db.values()):
        # Sin ganancia relevante, devolvemos tal cual
        return x

    board = _build_pedalboard_eq(eq_gains_db, sr)

    if len(board) == 0:
        return x

    # Pedalboard detecta automáticamente si la forma es (N,) o (N, C)
    y = board(x, sr)

    y = np.asarray(y, dtype=np.float32)
    # Clamp suave para evitar picos muy extremos (igual que antes)
    y = np.clip(y, -1.5, 1.5)

    return y


# ---------------------------------------------------------------------
# Stage principal
# ---------------------------------------------------------------------

def main() -> None:
    """
    Stage S7_MIXBUS_TONAL_BALANCE:

      - Lee analysis_S7_MIXBUS_TONAL_BALANCE.json.
      - Si el error RMS de tonal balance ya está por debajo del umbral,
        actúa como no-op (idempotente).
      - Si no, calcula ganancia por banda (limitada por contrato) y aplica
        un EQ multibanda en full_song.wav usando Pedalboard.
      - Recalcula el tonal balance y guarda métricas en
        tonal_metrics_S7_MIXBUS_TONAL_BALANCE.json para el check.
    """
    if len(sys.argv) < 2:
        print("Uso: python S7_MIXBUS_TONAL_BALANCE.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S7_MIXBUS_TONAL_BALANCE"

    # 1) Cargar análisis previo
    analysis = load_analysis(contract_id)

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}
    session: Dict[str, Any] = analysis.get("session", {}) or {}

    style_preset = analysis.get("style_preset", "default")
    tonal_info: Dict[str, Any] = session.get("tonal_bands", {}) or {}

    prev_error_rms = float(tonal_info.get("error_rms_db", 0.0))
    current_band_db = tonal_info.get("current_band_db", {}) or {}
    target_band_db = tonal_info.get("target_band_db", {}) or {}

    max_tonal_error_db = float(metrics.get("max_tonal_balance_error_db", 3.0))
    max_eq_change_db = float(limits.get("max_eq_change_db_per_band_per_pass", 1.5))

    temp_dir = get_temp_dir(contract_id, create=False)
    full_song_path = temp_dir / "full_song.wav"

    if not full_song_path.exists():
        print(
            f"[S7_MIXBUS_TONAL_BALANCE] No existe {full_song_path}; "
            f"no se puede aplicar EQ de tonal balance."
        )
        # Guardamos métricas mínimas para que el check tenga algo que leer
        _save_tonal_metrics(
            temp_dir=temp_dir,
            contract_id=contract_id,
            style_preset=style_preset,
            pre_band_db=current_band_db,
            post_band_db=current_band_db,
            target_band_db=target_band_db,
            pre_error_rms=prev_error_rms,
            post_error_rms=prev_error_rms,
            eq_gains_db={},
            max_tonal_error_db=max_tonal_error_db,
            max_eq_change_db=max_eq_change_db,
        )
        return

    # Si las bandas/targets vienen vacíos (por algún motivo), reconstruimos objetivo desde estilo
    if not target_band_db:
        target_band_db = get_style_tonal_profile(style_preset)

    # 2) Caso idempotente: ya está dentro de tolerancia
    MARGIN_RMS = 0.25
    if prev_error_rms <= max_tonal_error_db + MARGIN_RMS:
        print(
            f"[S7_MIXBUS_TONAL_BALANCE] error_RMS={prev_error_rms:.2f} dB "
            f"<= umbral {max_tonal_error_db:.2f} dB (+{MARGIN_RMS:.2f}); no-op."
        )
        _save_tonal_metrics(
            temp_dir=temp_dir,
            contract_id=contract_id,
            style_preset=style_preset,
            pre_band_db=current_band_db,
            post_band_db=current_band_db,
            target_band_db=target_band_db,
            pre_error_rms=prev_error_rms,
            post_error_rms=prev_error_rms,
            eq_gains_db={},
            max_tonal_error_db=max_tonal_error_db,
            max_eq_change_db=max_eq_change_db,
        )
        return

    # 3) Calcular ganancia por banda para reducir error (limitada por max_eq_change_db)
    #    err_db = current - target ⇒ queremos mover hacia target: gain ≈ -err_db
    errors_by_band, _ = compute_tonal_error(current_band_db, target_band_db)
    eq_gains_db: Dict[str, float] = {}

    for band_id, err_db in errors_by_band.items():
        desired_gain = -float(err_db)
        gain = max(-max_eq_change_db, min(max_eq_change_db, desired_gain))
        # Evitar microajustes ridículos
        if abs(gain) < 0.1:
            gain = 0.0
        eq_gains_db[band_id] = float(gain)

    print("[S7_MIXBUS_TONAL_BALANCE] Ganancias de EQ por banda (dB):")
    for b_id, g in eq_gains_db.items():
        print(f"  - {b_id}: {g:+.2f} dB")

    # 4) Leer full_song y aplicar EQ con Pedalboard
    y, sr = sf.read(full_song_path, always_2d=False)
    if not isinstance(y, np.ndarray):
        y = np.asarray(y, dtype=np.float32)
    else:
        y = y.astype(np.float32)

    y_eq = _apply_multiband_eq_pedalboard(y, sr, eq_gains_db)

    # Guardar mixbus ecualizado
    sf.write(full_song_path, y_eq, sr)
    print(f"[S7_MIXBUS_TONAL_BALANCE] EQ multibanda aplicada sobre {full_song_path.name}.")

    # 5) Recalcular tonal balance post-EQ
    post_band_db = compute_band_energies(y_eq, sr)
    _, post_error_rms = compute_tonal_error(post_band_db, target_band_db)

    print(
        f"[S7_MIXBUS_TONAL_BALANCE] error_RMS pre={prev_error_rms:.2f} dB, "
        f"post={post_error_rms:.2f} dB."
    )

    # 6) Guardar métricas para el futuro check
    _save_tonal_metrics(
        temp_dir=temp_dir,
        contract_id=contract_id,
        style_preset=style_preset,
        pre_band_db=current_band_db,
        post_band_db=post_band_db,
        target_band_db=target_band_db,
        pre_error_rms=prev_error_rms,
        post_error_rms=post_error_rms,
        eq_gains_db=eq_gains_db,
        max_tonal_error_db=max_tonal_error_db,
        max_eq_change_db=max_eq_change_db,
    )


def _save_tonal_metrics(
    temp_dir: Path,
    contract_id: str,
    style_preset: str,
    pre_band_db: Dict[str, float],
    post_band_db: Dict[str, float],
    target_band_db: Dict[str, float],
    pre_error_rms: float,
    post_error_rms: float,
    eq_gains_db: Dict[str, float],
    max_tonal_error_db: float,
    max_eq_change_db: float,
) -> None:
    """
    Escribe tonal_metrics_S7_MIXBUS_TONAL_BALANCE.json con la estructura
    que espera _check_S7_MIXBUS_TONAL_BALANCE.
    """
    metrics_path = temp_dir / "tonal_metrics_S7_MIXBUS_TONAL_BALANCE.json"
    data = {
        "contract_id": contract_id,
        "style_preset": style_preset,
        "max_tonal_balance_error_db": max_tonal_error_db,
        "max_eq_change_db_per_band_per_pass": max_eq_change_db,
        "pre": {
            "band_db": pre_band_db,
            "error_rms_db": pre_error_rms,
        },
        "post": {
            "band_db": post_band_db,
            "error_rms_db": post_error_rms,
        },
        "target_band_db": target_band_db,
        "eq_gains_db": eq_gains_db,
    }

    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(
        f"[S7_MIXBUS_TONAL_BALANCE] Métricas de tonal balance guardadas en: {metrics_path}"
    )


if __name__ == "__main__":
    main()
