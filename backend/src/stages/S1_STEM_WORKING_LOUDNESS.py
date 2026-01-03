# C:\mix-master\backend\src\stages\S1_STEM_WORKING_LOUDNESS.py

from __future__ import annotations
from utils.logger import logger

import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

# --- hack sys.path para ejecutar como script suelto desde stage.py ---
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json  # noqa: E402
import os  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
from concurrent.futures import ThreadPoolExecutor, as_completed  # noqa: E402

from utils.analysis_utils import get_temp_dir  # noqa: E402
from utils.profiles_utils import get_instrument_profile  # noqa: E402


def load_analysis(contract_id: str) -> Dict[str, Any]:
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"
    if not analysis_path.exists():
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")
    with analysis_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _dbfs_from_amp(amp: float, eps: float = 1e-12) -> float:
    if amp <= 0.0:
        return float("-inf")
    return float(20.0 * np.log10(amp + eps))


def _amp_from_dbfs(dbfs: float) -> float:
    return float(10.0 ** (float(dbfs) / 20.0))


def _peak_dbfs_from_audio(x: np.ndarray, eps: float = 1e-12) -> float:
    x = np.asarray(x, dtype=np.float32)
    if x.size == 0:
        return float("-inf")
    peak = float(np.max(np.abs(x)))
    return _dbfs_from_amp(peak, eps=eps)


def apply_gain_to_stem(file_path: Path, gain_db: float) -> Tuple[float, float]:
    data, sr = sf.read(file_path, always_2d=False)
    data = np.asarray(data, dtype=np.float32)
    if data.size == 0 or gain_db == 0.0:
        peak = _peak_dbfs_from_audio(data)
        return peak, peak

    peak_pre = _peak_dbfs_from_audio(data)

    scale = float(10.0 ** (gain_db / 20.0))
    data_out = data * scale

    peak_post = _peak_dbfs_from_audio(data_out)

    sf.write(file_path, data_out, sr, subtype="FLOAT")
    return peak_pre, peak_post


def compute_gain_db_for_stem(
    stem_info: Dict[str, Any],
    true_peak_target_dbtp: float,
    max_gain_change_db_per_pass: Optional[float],
    lufs_tolerance_db: float,
    max_cut_db_per_pass: float,
    min_active_ratio_to_adjust: float,
    peak_margin_db: float,
) -> Tuple[float, str]:
    """
    Ganancia por stem con 2 objetivos:
      A) Loudness por rango (si se sale)
      B) Peak guard (si supera target, aunque esté "in_range")
    """
    file_name = stem_info.get("file_name", "unknown")
    inst_profile_id = stem_info.get("instrument_profile_resolved", "Other")
    profile = get_instrument_profile(inst_profile_id)
    lufs_range = profile.get("work_loudness_lufs_range")

    # Loudness preferido: active_lufs
    lufs = stem_info.get("active_lufs", None)
    if lufs is None or lufs == float("-inf"):
        lufs = stem_info.get("integrated_lufs", None)

    measured_peak_dbfs = stem_info.get("true_peak_dbfs", None)
    if measured_peak_dbfs is None or measured_peak_dbfs == float("-inf"):
        measured_peak_dbfs = -120.0
    measured_peak_dbfs = float(measured_peak_dbfs)

    # Actividad (para evitar decisiones malas en stems muy "huecos")
    activity = stem_info.get("activity", {}) or {}
    active_ratio = float(activity.get("active_ratio", 1.0))
    if active_ratio < float(min_active_ratio_to_adjust):
        return 0.0, f"{file_name}: skip_low_activity(active_ratio={active_ratio:.3f})"

    # 1) Ganancia por loudness (por rango)
    loud_gain = 0.0
    loud_reason = "no_loud_adjust"
    if isinstance(lufs_range, list) and len(lufs_range) == 2 and lufs is not None and lufs != float("-inf"):
        target_min, target_max = float(lufs_range[0]), float(lufs_range[1])
        lufs_f = float(lufs)

        upper = target_max + float(lufs_tolerance_db)
        lower = target_min - float(lufs_tolerance_db)

        if lufs_f > upper:
            loud_gain = target_max - lufs_f  # negativo
            loud_reason = f"too_loud(lufs={lufs_f:.2f} > {upper:.2f})"
        elif lufs_f < lower:
            loud_gain = target_min - lufs_f  # positivo
            loud_reason = f"too_quiet(lufs={lufs_f:.2f} < {lower:.2f})"
        else:
            loud_gain = 0.0
            loud_reason = f"in_range(lufs={lufs_f:.2f})"

    # 2) Peak guard: si pico > target+margin => recorte obligatorio
    peak_required_gain = 0.0
    if measured_peak_dbfs > (float(true_peak_target_dbtp) + float(peak_margin_db)):
        peak_required_gain = (float(true_peak_target_dbtp) - float(peak_margin_db)) - measured_peak_dbfs  # negativo
        # Ej: pico=-0.02, target=-3 => gain=-2.98 (aprox)
        peak_required_gain = min(0.0, peak_required_gain)

    # Combinar: si peak exige recorte, manda (aunque loud_gain diga 0 o positivo)
    gain_db = float(loud_gain)
    reason_parts = [loud_reason]

    if peak_required_gain < gain_db:
        # más negativo => más recorte
        gain_db = float(peak_required_gain)
        reason_parts.append(f"peak_guard(peak={measured_peak_dbfs:.2f} > {true_peak_target_dbtp:.2f})")

    # Clamp boost por pico (si loudness pide subir)
    if gain_db > 0.0:
        allowed_boost = (float(true_peak_target_dbtp) - float(peak_margin_db)) - measured_peak_dbfs
        if gain_db > allowed_boost:
            gain_db = max(0.0, float(allowed_boost))
            reason_parts.append(f"boost_clamped_by_peak(allowed={allowed_boost:.2f})")

    # Límite por contrato
    if max_gain_change_db_per_pass is not None:
        mg = float(max_gain_change_db_per_pass)
        gain_db = max(-mg, min(mg, gain_db))

    # Safety cap de recorte por pasada (pero ojo: si el pico está en 0, necesitas ~-3 sí o sí)
    if gain_db < -float(max_cut_db_per_pass):
        gain_db = -float(max_cut_db_per_pass)
        reason_parts.append(f"cap_cut({max_cut_db_per_pass:.2f}dB)")

    # Ignorar microcambios
    if abs(gain_db) < 0.10:
        return 0.0, " | ".join(reason_parts)

    return float(gain_db), " | ".join(reason_parts)


def _process_one_stem(
    stem_info: Dict[str, Any],
    true_peak_target_dbtp: float,
    max_gain_change_db_per_pass: Optional[float],
    lufs_tolerance_db: float,
    max_cut_db_per_pass: float,
    min_active_ratio_to_adjust: float,
    peak_margin_db: float,
) -> Tuple[str, float, str]:
    file_path = Path(stem_info["file_path"])
    stem_name = stem_info.get("file_name", file_path.name)

    gain_db, reason = compute_gain_db_for_stem(
        stem_info=stem_info,
        true_peak_target_dbtp=true_peak_target_dbtp,
        max_gain_change_db_per_pass=max_gain_change_db_per_pass,
        lufs_tolerance_db=lufs_tolerance_db,
        max_cut_db_per_pass=max_cut_db_per_pass,
        min_active_ratio_to_adjust=min_active_ratio_to_adjust,
        peak_margin_db=peak_margin_db,
    )

    if gain_db != 0.0:
        peak_pre, peak_post = apply_gain_to_stem(file_path, gain_db)
        logger.logger.info(
            f"[S1_STEM_WORKING_LOUDNESS] {stem_name}: gain={gain_db:+.2f} dB | "
            f"peak_pre={peak_pre:.2f} dBFS -> peak_post={peak_post:.2f} dBFS | {reason}"
        )
    else:
        logger.logger.info(f"[S1_STEM_WORKING_LOUDNESS] {stem_name}: gain=+0.00 dB | {reason}")

    return stem_name, float(gain_db), reason


def compute_mixbus_peak_details_streaming(
    stem_paths: List[Path],
    block_frames: int = 262144,
) -> Dict[str, Any]:
    """
    Encuentra el pico del mix (suma unity) en streaming:
      - peak_dbfs (sample-peak)
      - peak_frame, peak_channel, peak_sample_value (signed)
    """
    if not stem_paths:
        return {
            "peak_dbfs": float("-inf"),
            "peak_linear": 0.0,
            "peak_frame": None,
            "peak_channel": None,
            "peak_sample_value": 0.0,
        }

    files: List[sf.SoundFile] = [sf.SoundFile(str(p), mode="r") for p in stem_paths]
    try:
        sr_ref = files[0].samplerate
        ch_ref = files[0].channels
        for f in files[1:]:
            if f.samplerate != sr_ref or f.channels != ch_ref:
                raise ValueError("Samplerate/channels mismatch en stems; S0_SESSION_FORMAT debería uniformizar.")

        best_amp = 0.0
        best_frame = None
        best_ch = None
        best_sample = 0.0

        pos = 0
        while True:
            blocks = []
            any_data = False
            for f in files:
                b = f.read(frames=block_frames, dtype="float32", always_2d=True)
                if b.shape[0] > 0:
                    any_data = True
                blocks.append(b)

            if not any_data:
                break

            L = max((b.shape[0] for b in blocks), default=0)
            if L <= 0:
                pos += block_frames
                continue

            mix = np.zeros((L, ch_ref), dtype=np.float32)
            for b in blocks:
                if b.shape[0] == 0:
                    continue
                mix[: b.shape[0], :] += b

            abs_mix = np.abs(mix)
            flat_idx = int(np.argmax(abs_mix))
            local_frame, local_ch = np.unravel_index(flat_idx, abs_mix.shape)
            local_amp = float(abs_mix[local_frame, local_ch])

            if local_amp > best_amp:
                best_amp = local_amp
                best_frame = pos + int(local_frame)
                best_ch = int(local_ch)
                best_sample = float(mix[int(local_frame), int(local_ch)])

            pos += block_frames

        peak_dbfs = _dbfs_from_amp(best_amp)

    finally:
        for f in files:
            try:
                f.close()
            except Exception:
                pass

    return {
        "peak_dbfs": float(peak_dbfs),
        "peak_linear": float(best_amp),
        "peak_frame": best_frame,
        "peak_channel": best_ch,
        "peak_sample_value": float(best_sample),
    }


def read_stem_sample_at(
    stem_path: Path,
    frame_index: int,
    channel: int,
) -> float:
    with sf.SoundFile(str(stem_path), mode="r") as f:
        f.seek(int(frame_index))
        b = f.read(frames=1, dtype="float32", always_2d=True)
        if b.shape[0] == 0:
            return 0.0
        ch = min(int(channel), b.shape[1] - 1)
        return float(b[0, ch])


def apply_mixbus_preheadroom_selective(
    stems: List[Dict[str, Any]],
    mixbus_target_dbfs: float,
    max_iters: int,
    max_cut_db_per_iter: float,
    max_total_cut_db_per_stem: float,
    protect_vocals: bool,
    block_frames: int,
    peak_margin_db: float,
) -> None:
    """
    Reduce el pico del mixbus hacia target, recortando sólo stems que contribuyen al pico.
    """
    stem_paths = [Path(s["file_path"]) for s in stems]
    stem_name_by_path = {Path(s["file_path"]): s.get("file_name", Path(s["file_path"]).name) for s in stems}

    total_cut: Dict[Path, float] = {p: 0.0 for p in stem_paths}

    target_amp = _amp_from_dbfs(float(mixbus_target_dbfs) - float(peak_margin_db))

    for it in range(int(max_iters)):
        peak = compute_mixbus_peak_details_streaming(stem_paths, block_frames=block_frames)
        peak_dbfs = float(peak["peak_dbfs"])
        frame = peak["peak_frame"]
        ch = peak["peak_channel"]
        mix_sample = float(peak["peak_sample_value"])

        if frame is None or ch is None or peak_dbfs == float("-inf"):
            return

        if peak_dbfs <= float(mixbus_target_dbfs) + 0.10:
            logger.logger.info(
                f"[S1_STEM_WORKING_LOUDNESS] Mixbus pre-headroom OK: peak={peak_dbfs:.2f} dBFS <= target={mixbus_target_dbfs:.2f} dBFS (iter={it})."
            )
            return

        # Contribuciones en el frame pico (mismo canal)
        contrib: List[Tuple[Path, float]] = []
        for p in stem_paths:
            s = read_stem_sample_at(p, frame_index=int(frame), channel=int(ch))
            contrib.append((p, float(s)))

        # Sólo consideramos contribuciones con el mismo signo que el mix_sample (si no, recortar puede empeorar)
        sign = 1.0 if mix_sample >= 0.0 else -1.0
        aligned = [(p, s) for (p, s) in contrib if (s * sign) > 0.0 and abs(s) > 1e-9]

        if not aligned:
            logger.logger.info(
                f"[S1_STEM_WORKING_LOUDNESS] Mixbus peak alto ({peak_dbfs:.2f} dBFS) pero no hay contribuciones alineadas; se omite corrección selectiva."
            )
            return

        # Orden por contribución (abs)
        aligned.sort(key=lambda t: abs(t[1]), reverse=True)

        # Protección vocal (salvo que no haya alternativa)
        def is_vocal(p: Path) -> bool:
            return "vocal" in p.name.lower()

        candidates = aligned
        if protect_vocals:
            non_vocal = [(p, s) for (p, s) in aligned if not is_vocal(p)]
            if non_vocal:
                candidates = non_vocal

        # Seleccionar subset mínimo que permita bajar el pico (resolviendo g en u + g*v)
        mix_target_sample = sign * float(target_amp)

        chosen: List[Tuple[Path, float]] = []
        g_req: Optional[float] = None

        for k in range(1, len(candidates) + 1):
            sel = candidates[:k]
            v = float(sum(s for (_, s) in sel))
            if abs(v) < 1e-9:
                continue
            u = float(mix_sample - v)
            g = float((mix_target_sample - u) / v)
            if 0.0 < g < 1.0:
                chosen = sel
                g_req = g
                break

        if not chosen or g_req is None:
            # Si no encontramos solución "bonita", recortamos top-1 con step limitado (mejor que nada)
            chosen = candidates[:1]
            g_req = 10.0 ** (-(float(max_cut_db_per_iter) / 20.0))

        gain_req_db = float(20.0 * np.log10(float(g_req) + 1e-12))  # negativo
        gain_step_db = max(gain_req_db, -float(max_cut_db_per_iter))

        # Respetar máximo total por stem
        final_chosen: List[Path] = []
        for p, _s in chosen:
            if total_cut[p] <= -float(max_total_cut_db_per_stem) + 1e-6:
                continue
            final_chosen.append(p)

        if not final_chosen:
            logger.logger.info(
                "[S1_STEM_WORKING_LOUDNESS] Mixbus pre-headroom: no hay stems disponibles (cap total alcanzado)."
            )
            return

        # Aplicar recorte uniforme a los elegidos (step)
        for p in final_chosen:
            name = stem_name_by_path.get(p, p.name)
            peak_pre, peak_post = apply_gain_to_stem(p, gain_step_db)
            total_cut[p] += float(gain_step_db)
            logger.logger.info(
                f"[S1_STEM_WORKING_LOUDNESS] Mixbus pre-headroom iter={it}: {name} gain={gain_step_db:+.2f} dB | "
                f"peak_pre={peak_pre:.2f} -> peak_post={peak_post:.2f} | mix_peak={peak_dbfs:.2f} -> target={mixbus_target_dbfs:.2f}"
            )

    # Si llegamos aquí, no hemos alcanzado el target, pero hemos reducido algo sin matar todo con un trim global
    peak = compute_mixbus_peak_details_streaming(stem_paths, block_frames=block_frames)
    logger.logger.info(
        f"[S1_STEM_WORKING_LOUDNESS] Mixbus pre-headroom ended: peak={float(peak['peak_dbfs']):.2f} dBFS (target={mixbus_target_dbfs:.2f}) after max_iters={max_iters}."
    )


def main() -> None:
    if len(sys.argv) < 2:
        logger.logger.info("Uso: python S1_STEM_WORKING_LOUDNESS.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]
    analysis = load_analysis(contract_id)

    metrics: Dict[str, Any] = analysis.get("metrics_from_contract", {}) or {}
    session_metrics: Dict[str, Any] = analysis.get("session", {}) or {}
    stems: List[Dict[str, Any]] = analysis.get("stems", []) or []

    if not stems:
        logger.logger.info("[S1_STEM_WORKING_LOUDNESS] No hay stems en el análisis; nothing to do.")
        return

    # Targets
    true_peak_target_dbtp = float(session_metrics.get("true_peak_per_stem_target_max_dbtp", -3.0))
    mixbus_target_dbfs = float(session_metrics.get("mixbus_peak_target_max_dbfs", -6.0))

    # Parámetros (compatibles hacia atrás)
    max_gain_change_db_per_pass = metrics.get("max_gain_change_db_per_pass", None)

    # Nuevos defaults seguros
    lufs_tolerance_db = float(metrics.get("lufs_tolerance_db", 1.0))
    max_cut_db_per_pass = float(metrics.get("max_cut_db_per_pass", 3.0))  # para loudness/peak-guard por stem
    min_active_ratio_to_adjust = float(metrics.get("min_active_ratio_to_adjust", 0.05))
    peak_margin_db = float(metrics.get("peak_margin_db", 0.05))  # margen para evitar rozar el target

    # Mixbus pre-headroom selectivo
    mixbus_preheadroom_enabled = bool(metrics.get("mixbus_preheadroom_enabled", True))
    mixbus_max_iters = int(metrics.get("mixbus_max_iters", 3))
    mixbus_max_cut_db_per_iter = float(metrics.get("mixbus_max_cut_db_per_iter", 4.0))
    mixbus_max_total_cut_db_per_stem = float(metrics.get("mixbus_max_total_cut_db_per_stem", 12.0))
    mixbus_protect_vocals = bool(metrics.get("mixbus_protect_vocals", True))
    mixbus_block_frames = int(metrics.get("mixbus_block_frames", 262144))

    # Paralelización (threads)
    max_workers = int(metrics.get("max_workers", 4))
    max_workers = max(1, min(max_workers, os.cpu_count() or 1))

    # 1) Ajuste por stem (loudness + peak guard)
    total_changed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [
            ex.submit(
                _process_one_stem,
                stem,
                true_peak_target_dbtp,
                max_gain_change_db_per_pass,
                lufs_tolerance_db,
                max_cut_db_per_pass,
                min_active_ratio_to_adjust,
                peak_margin_db,
            )
            for stem in stems
        ]
        for fut in as_completed(futures):
            _name, gain_db, _reason = fut.result()
            if gain_db != 0.0:
                total_changed += 1

    logger.logger.info(
        f"[S1_STEM_WORKING_LOUDNESS] Normalización/Peak-Guard completado. Stems={len(stems)} modificados={total_changed}."
    )

    # 2) Pre-headroom de mixbus (selectivo)
    if mixbus_preheadroom_enabled:
        apply_mixbus_preheadroom_selective(
            stems=stems,
            mixbus_target_dbfs=mixbus_target_dbfs,
            max_iters=mixbus_max_iters,
            max_cut_db_per_iter=mixbus_max_cut_db_per_iter,
            max_total_cut_db_per_stem=mixbus_max_total_cut_db_per_stem,
            protect_vocals=mixbus_protect_vocals,
            block_frames=mixbus_block_frames,
            peak_margin_db=peak_margin_db,
        )

    logger.logger.info(
        f"[S1_STEM_WORKING_LOUDNESS] Stage completado para {len(stems)} stems."
    )


if __name__ == "__main__":
    main()
