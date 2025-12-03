from __future__ import annotations

import sys
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
from pedalboard import Pedalboard, Reverb  # noqa: E402

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
# Helpers para reverb con Pedalboard
# ---------------------------------------------------------------------

def _map_rt60_to_room_size(rt60_s: float) -> float:
    """
    Mapea rt60 (segundos) a room_size (0-1) para el Reverb de Pedalboard.

    - Clampa rt60 entre ~0.3 y 3.0 s.
    - Devuelve room_size en [0.1, 0.99].
    """
    rt60_s = float(rt60_s)
    rt_min, rt_max = 0.3, 3.0
    rt60_s = max(rt_min, min(rt60_s, rt_max))
    norm = (rt60_s - rt_min) / (rt_max - rt_min)  # 0..1
    room_size = 0.1 + norm * (0.99 - 0.1)
    return float(max(0.1, min(room_size, 0.99)))


# ---------------------------------------------------------------------
# ---------------------------------------------------------------------

def _render_reverb_return_worker(
    args: tuple[str, str, float, float, int]
) -> Optional[Dict[str, Any]]:
    """
    Worker que:
      - Lee el stem.
      - Aplica Reverb de Pedalboard (100% wet, sin dry).
      - Aplica base_send_db.
      - Devuelve y_rev y metadatos (NO escribe a disco).

    Si hay error o el archivo está vacío, devuelve None.
    """
    fname, stem_path_str, rt60_s, base_send_db, seed = args  # seed se mantiene por firma
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

    # Aseguramos forma (N, C)
    if y.ndim == 1:
        y = y.reshape(-1, 1)

    # Configurar Reverb de Pedalboard 100% wet (return puro)
    room_size = _map_rt60_to_room_size(rt60_s)

    board = Pedalboard(
        [
            Reverb(
                room_size=float(room_size),
                wet_level=1.0,  # 100% wet
                dry_level=0.0,  # 0% dry
            )
        ]
    )

    try:
        y_rev = board(y, sr)
    except Exception as e:
        print(f"[S6_BUS_REVERB_STYLE] Error aplicando Reverb a '{fname}': {e}.")
        return None

    if not isinstance(y_rev, np.ndarray):
        y_rev = np.asarray(y_rev, dtype=np.float32)
    else:
        y_rev = y_rev.astype(np.float32)

    if y_rev.ndim == 1:
        y_rev = y_rev.reshape(-1, 1)

    # Aplicar base_send_db como ganancia del return
    send_gain = 10.0 ** (base_send_db / 20.0)
    y_rev *= send_gain

    rev_len = int(y_rev.shape[0])

    return {
        "stem_file": fname,
        "sr": sr,
        "y_rev": y_rev,
        "rt60_s": rt60_s,
        "base_send_db": base_send_db,
        "length": rev_len,
    }


def _choose_target_offset_db(
    offset_min_db: float,
    offset_max_db: float,
    style_preset: str,
) -> float:
    """
    El contrato define un rango de offsets dry/reverb [min, max] en dB.
    Aquí elegimos un punto dentro de ese rango, claramente del lado 'seco',
    y le damos un poco de dependencia por estilo.

    offset_min_db y offset_max_db son negativos (p.ej. -24, -6).
    """
    style = (style_preset or "").lower()

    # pos=0 -> offset_min (más seco), pos=1 -> offset_max (más wet)
    if any(k in style for k in ("flamenco", "rumba", "acoustic", "acústico", "jazz", "folk")):
        pos = 0.2   # reverb claramente sutil
    elif any(k in style for k in ("edm", "club", "trance", "house")):
        pos = 0.4   # un poco más presente
    elif any(k in style for k in ("urbano", "trap", "reggaeton", "hiphop", "urban")):
        pos = 0.35
    else:
        pos = 0.3   # valor intermedio tirando a seco

    pos = max(0.0, min(1.0, pos))
    return offset_min_db + pos * (offset_max_db - offset_min_db)


def main() -> None:
    """
    Stage S6_BUS_REVERB_STYLE:

      - Lee analysis_S6_BUS_REVERB_STYLE.json.
      - Para cada stem genera un retorno de reverb *_rev.wav en función del estilo y familia,
        usando Reverb de Pedalboard (100% wet, controlado por base_send_db).
      - Ajusta el nivel global de returns hacia un offset de loudness objetivo
        respecto al mix dry (full_song.wav o referencia fija).
      - Guarda métricas de espacio/profundidad para el futuro check.
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

    style_preset: str = analysis.get("style_preset", "default") or "default"

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
    # 1) Preparar tareas de generación de returns
    # ------------------------------------------------------------------
    tasks: List[tuple[str, str, float, float, int]] = []
    SEED_BASE = 12345  # mantenido por compatibilidad de firma

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
    # 2) Generar returns en serie
    # ------------------------------------------------------------------
    if tasks:
        for result in map(_render_reverb_return_worker, tasks):
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

    # ------------------------------------------------------------------
    # 4) Calcular y aplicar offset objetivo (ahora simétrico: puede subir o bajar reverb)
    # ------------------------------------------------------------------
    target_offset = _choose_target_offset_db(
        offset_min_db=offset_min_db,
        offset_max_db=offset_max_db,
        style_preset=style_preset,
    )

    # Si estamos muy fuera de rango por abajo o por arriba, forzamos a entrar
    # en la ventana del contrato antes de aplicar fine-tuning por estilo.
    MARGIN_IN_RANGE = 0.5  # dB
    MAX_GLOBAL_DELTA_DB = 12.0  # límite de seguridad para swings grandes

    # Desplazamiento necesario para ir hacia el objetivo
    delta_needed = target_offset - offset_now

    if abs(delta_needed) <= MARGIN_IN_RANGE:
        delta_db = 0.0
        print(
            "[S6_BUS_REVERB_STYLE] Offset de reverb ya suficientemente cercano al objetivo; "
            "no se ajusta nivel global de returns."
        )
    else:
        # Permitimos subir o bajar la reverb, pero limitando la corrección global
        # a un valor razonable para evitar cosas absurdas si la medición se va.
        delta_db = float(
            max(-MAX_GLOBAL_DELTA_DB, min(MAX_GLOBAL_DELTA_DB, delta_needed))
        )

        direction = "subiendo" if delta_db > 0.0 else "bajando"
        print(
            f"[S6_BUS_REVERB_STYLE] Ajustando returns globalmente {delta_db:.2f} dB "
            f"({direction}) hacia offset objetivo {target_offset:.2f} dB."
        )

        gain_global = 10.0 ** (delta_db / 20.0)

        # Reescalar cada archivo *_rev.wav y actualizar buffers en memoria
        for info, y_rev in zip(returns_info, all_returns):
            rev_path = temp_dir / info["return_file"]
            y_scaled = y_rev * gain_global
            sf.write(rev_path, y_scaled, global_sr)
            # Actualizamos el buffer en memoria por coherencia
            y_rev[:] = y_scaled

        # Actualizar sum_ret para métricas finales
        sum_ret *= gain_global
        current_reverb_lufs = _compute_rms_lufs_like(sum_ret)
        offset_now = current_reverb_lufs - dry_lufs

    # ------------------------------------------------------------------
    # 5) Guardar métricas para el futuro check
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
                "target_offset_target_db": target_offset,
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
