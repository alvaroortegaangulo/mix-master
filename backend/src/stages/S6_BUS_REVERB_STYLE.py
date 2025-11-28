# C:\mix-master\backend\src\stages\S6_BUS_REVERB_STYLE.py

from __future__ import annotations

import sys
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Dict, Any, List, Optional
from scipy.signal import fftconvolve

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from utils.analysis_utils import get_temp_dir


def _compute_rms_lufs_like(y: np.ndarray) -> float:
    """
    Aproximación simple de LUFS integrados: usar RMS global en dBFS.
    """
    arr = np.asarray(y, dtype=np.float32)
    if arr.ndim > 1:
        arr = np.mean(arr, axis=1)
    if arr.size == 0:
        return float("-inf")
    rms = float(np.sqrt(np.mean(arr**2)))
    if rms <= 0.0:
        return float("-inf")
    return 20.0 * np.log10(rms)


def _generate_reverb_ir(
    sr: int,
    rt60_s: float,
    seed: int = 12345,
) -> np.ndarray:
    """
    Genera una IR de reverb muy simple:
      - ruido filtrado con envolvente de decaimiento exponencial.
      - longitud ~ 2 * rt60_s, limitada a 5 s máx.

    Es determinista vía seed para idempotencia.
    """
    rt60_s = max(rt60_s, 0.1)
    length_s = min(rt60_s * 2.0, 5.0)
    n = int(sr * length_s)
    if n <= 0:
        n = int(sr * 0.3)

    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(n).astype(np.float32)

    # Suavizado simple (lowpass muy tosco) para que no suene demasiado áspero
    for i in range(1, n):
        noise[i] = 0.8 * noise[i - 1] + 0.2 * noise[i]

    t = np.arange(n, dtype=np.float32) / float(sr)
    decay = np.exp(-3.0 * t / rt60_s).astype(np.float32)

    ir = noise * decay
    peak = float(np.max(np.abs(ir)))
    if peak > 0.0:
        ir /= peak

    # Atenuamos algo para evitar excesos; el nivel relativo lo ajustaremos con sends
    ir *= 0.4
    return ir


def load_analysis(contract_id: str) -> Dict[str, Any]:
    """
    Carga el JSON de análisis generado por analysis\\S6_BUS_REVERB_STYLE.py.
    """
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data


# ---------------------------------------------------------------------
# Worker para ProcessPoolExecutor: genera el return de reverb de un stem
# ---------------------------------------------------------------------

def _render_reverb_return_worker(
    args: tuple[str, str, float, float, int]
) -> Optional[Dict[str, Any]]:
    """
    Worker que:
      - Lee el stem.
      - Genera la IR.
      - Convoluciona por canal.
      - Aplica base_send_db.
      - Devuelve y_rev y metadatos (NO escribe a disco).

    Si hay error o el archivo está vacío, devuelve None.
    """
    fname, stem_path_str, rt60_s, base_send_db, seed = args
    stem_path = Path(stem_path_str)

    try:
        y, sr = sf.read(stem_path, always_2d=False)
    except Exception as e:
        print(f"[S6_BUS_REVERB_STYLE] Aviso: no se puede leer '{fname}' en worker: {e}.")
        return None

    if not isinstance(y, np.ndarray):
        y = np.asarray(y, dtype=np.float32)
    else:
        y = y.astype(np.float32)

    if y.size == 0:
        print(f"[S6_BUS_REVERB_STYLE] {fname}: archivo vacío; se omite su reverb.")
        return None

    if y.ndim == 1:
        y = y.reshape(-1, 1)

    n, c = y.shape

    # IR determinista
    ir = _generate_reverb_ir(sr, rt60_s, seed=seed)

    # Convolución simple por canal
    rev_len = n + len(ir) - 1
    y_rev = np.zeros((rev_len, c), dtype=np.float32)

    for ch in range(c):
        conv = fftconvolve(y[:, ch], ir, mode="full")
        y_rev[:, ch] = conv.astype(np.float32)

    # Aplicar base_send_db
    send_gain = 10.0 ** (base_send_db / 20.0)
    y_rev *= send_gain

    return {
        "stem_file": fname,
        "sr": sr,
        "y_rev": y_rev,
        "rt60_s": rt60_s,
        "base_send_db": base_send_db,
        "length": rev_len,
    }


def main() -> None:
    """
    Stage S6_BUS_REVERB_STYLE:

      - Lee analysis_S6_BUS_REVERB_STYLE.json.
      - Para cada stem genera un retorno de reverb *_rev.wav en función del estilo y familia.
      - Ajusta el nivel global de returns hacia un offset de loudness objetivo
        respecto al mix dry (full_song.wav).
      - Guarda métricas de espacio/profundidad para el futuro check.
      - Usa ProcessPoolExecutor para paralelizar la generación de los returns.
    """
    if len(sys.argv) < 2:
        print("Uso: python S6_BUS_REVERB_STYLE.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]  # "S6_BUS_REVERB_STYLE"

    analysis = load_analysis(contract_id)

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    limits: Dict[str, Any] = analysis.get("limits_from_contract", {}) or {}
    session: Dict[str, Any] = analysis.get("session", {}) or {}
    stems: List[Dict[str, Any]] = analysis.get("stems", []) or []

    offset_min_db = float(metrics.get("reverb_return_lufs_offset_min_db", -24.0))
    offset_max_db = float(metrics.get("reverb_return_lufs_offset_max_db", -8.0))
    max_send_change_db = float(limits.get("max_send_level_change_db_per_pass", 2.0))

    dry_lufs = float(session.get("dry_mix_lufs", float("-inf")))

    temp_dir = get_temp_dir(contract_id, create=False)
    full_song_path = temp_dir / "full_song.wav"

    sr_ref: Optional[int] = None
    if full_song_path.exists():
        try:
            y_mix, sr_mix = sf.read(full_song_path, always_2d=False)
            sr_ref = sr_mix
            # Recalcular por si acaso
            dry_lufs = _compute_rms_lufs_like(y_mix)
        except Exception as e:
            print(
                f"[S6_BUS_REVERB_STYLE] Aviso: no se puede leer full_song.wav: {e}."
            )

    # Si no tenemos full_song, tomamos como referencia -18 dBFS (neutro)
    if dry_lufs == float("-inf"):
        dry_lufs = -18.0
        print(
            "[S6_BUS_REVERB_STYLE] No se ha podido medir el mix dry; "
            "se asume referencia -18 dBFS para offsets."
        )

    # ------------------------------------------------------------------
    # 1) Preparar tareas para ProcessPoolExecutor (por stem)
    # ------------------------------------------------------------------
    tasks: List[tuple[str, str, float, float, int]] = []
    SEED_BASE = 12345  # mismo seed base para IRs deterministas

    for idx, stem in enumerate(stems):
        fname = stem.get("file_name")
        if not fname:
            continue

        stem_path = temp_dir / fname
        if not stem_path.exists():
            continue

        reverb_profile = stem.get("reverb_profile") or {}
        rt60_s = float(reverb_profile.get("rt60_s", 0.8))
        base_send_db = float(reverb_profile.get("base_send_db", -18.0))

        # Usamos un seed fijo (como en la versión original) para que la IR sea
        # la misma en todos los stems y la ejecución siga siendo idempotente.
        seed = SEED_BASE

        tasks.append(
            (
                fname,
                str(stem_path),
                rt60_s,
                base_send_db,
                seed,
            )
        )

    all_returns: List[np.ndarray] = []
    returns_info: List[Dict[str, Any]] = []
    global_sr: Optional[int] = sr_ref
    max_return_len = 0

    # ------------------------------------------------------------------
    # 2) Generar returns en paralelo
    # ------------------------------------------------------------------
    if tasks:
        max_workers = min(4, os.cpu_count() or 1)
        with ProcessPoolExecutor(max_workers=max_workers) as ex:
            for result in ex.map(_render_reverb_return_worker, tasks):
                if result is None:
                    continue

                fname = result["stem_file"]
                sr = int(result["sr"])
                y_rev = result["y_rev"]
                rt60_s = float(result["rt60_s"])
                base_send_db = float(result["base_send_db"])
                rev_len = int(result["length"])

                # Consistencia de samplerate
                if global_sr is None:
                    global_sr = sr
                elif sr != global_sr:
                    print(
                        f"[S6_BUS_REVERB_STYLE] Aviso: samplerate inconsistente en {fname} "
                        f"(sr={sr}, ref={global_sr}); se omite su reverb."
                    )
                    continue

                stem_name = Path(fname).stem
                rev_name = f"{stem_name}_rev.wav"
                rev_path = temp_dir / rev_name

                # Escribimos el return generado
                sf.write(rev_path, y_rev, global_sr)

                print(
                    f"[S6_BUS_REVERB_STYLE] {fname}: rt60={rt60_s:.2f}s, "
                    f"base_send={base_send_db:.1f} dB, "
                    f"return -> {rev_name} (len={rev_len})."
                )

                all_returns.append(y_rev)
                returns_info.append(
                    {
                        "stem_file": fname,
                        "return_file": rev_name,
                        "rt60_s": rt60_s,
                        "base_send_db": base_send_db,
                        "length": rev_len,
                    }
                )
                if rev_len > max_return_len:
                    max_return_len = rev_len

    if not all_returns or global_sr is None:
        print(
            "[S6_BUS_REVERB_STYLE] No se han generado returns de reverb; "
            "no se aplicará ajuste de offset."
        )
        # Aun así guardamos métricas vacías
        metrics_path = temp_dir / "space_depth_metrics_S6_BUS_REVERB_STYLE.json"
        with metrics_path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "contract_id": contract_id,
                    "dry_mix_lufs": dry_lufs,
                    "reverb_return_lufs": float("-inf"),
                    "reverb_return_offset_db": None,
                    "target_offset_min_db": offset_min_db,
                    "target_offset_max_db": offset_max_db,
                    "max_send_level_change_db_per_pass": max_send_change_db,
                    "num_returns": 0,
                    "returns_info": returns_info,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )
        return

    # ------------------------------------------------------------------
    # 3) Sumar todos los returns para medir nivel global de reverb
    # ------------------------------------------------------------------
    sum_ret = np.zeros((max_return_len,), dtype=np.float32)
    for y_rev in all_returns:
        mono = np.mean(y_rev, axis=1)
        sum_ret[: mono.shape[0]] += mono

    current_reverb_lufs = _compute_rms_lufs_like(sum_ret)
    offset_now = current_reverb_lufs - dry_lufs

    print(
        f"[S6_BUS_REVERB_STYLE] Reverb sum actual: aprox_LUFS={current_reverb_lufs:.2f} dB, "
        f"offset_vs_dry={offset_now:.2f} dB."
    )

    # 4) Calcular offset objetivo (punto medio del rango)
    target_offset = 0.5 * (offset_min_db + offset_max_db)

    # Queremos mover el offset hacia target_offset, pero como máximo max_send_change_db
    delta_needed = target_offset - offset_now
    delta_db = max(-max_send_change_db, min(max_send_change_db, delta_needed))

    # 5) Aplicar ajuste global a todos los returns (idempotente por diseño)
    if abs(delta_db) > 1e-3:
        gain_global = 10.0 ** (delta_db / 20.0)
        print(
            f"[S6_BUS_REVERB_STYLE] Ajustando returns globalmente {delta_db:.2f} dB "
            f"hacia offset objetivo {target_offset:.2f} dB."
        )
        # Reescalar cada archivo *_rev.wav y actualizar buffers en memoria
        for info, y_rev in zip(returns_info, all_returns):
            rev_path = temp_dir / info["return_file"]
            y_scaled = y_rev * gain_global
            sf.write(rev_path, y_scaled, global_sr)

        # Actualizar sum_ret para métricas finales
        sum_ret *= gain_global
        current_reverb_lufs = _compute_rms_lufs_like(sum_ret)
        offset_now = current_reverb_lufs - dry_lufs
    else:
        print(
            "[S6_BUS_REVERB_STYLE] Offset de reverb ya cercano al objetivo; "
            "no se ajusta nivel global de returns."
        )

    # ------------------------------------------------------------------
    # 6) Guardar métricas para el futuro check
    # ------------------------------------------------------------------
    metrics_path = temp_dir / "space_depth_metrics_S6_BUS_REVERB_STYLE.json"
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "contract_id": contract_id,
                "dry_mix_lufs": dry_lufs,
                "reverb_return_lufs": current_reverb_lufs,
                "reverb_return_offset_db": offset_now,
                "target_offset_min_db": offset_min_db,
                "target_offset_max_db": offset_max_db,
                "target_offset_mid_db": target_offset,
                "applied_offset_delta_db": delta_db,
                "max_send_level_change_db_per_pass": max_send_change_db,
                "num_returns": len(returns_info),
                "returns_info": returns_info,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(
        f"[S6_BUS_REVERB_STYLE] Stage completado. Returns={len(returns_info)}, "
        f"reverb_LUFS={current_reverb_lufs:.2f} dB, offset_vs_dry={offset_now:.2f} dB. "
        f"Métricas: {metrics_path}"
    )


if __name__ == "__main__":
    main()
