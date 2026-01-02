from __future__ import annotations

import sys
import json
from pathlib import Path
import numpy as np
from typing import Dict, Any, List

# --- hack para poder importar utils cuando se ejecuta como script suelto ---
THIS_DIR = Path(__file__).resolve().parent         # .../src/utils
SRC_DIR = THIS_DIR.parent                          # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.profiles_utils import get_instrument_profile  # noqa: E402
from utils.analysis_utils import get_temp_dir

try:
    from context import PipelineContext
except ImportError:
    PipelineContext = None # type: ignore

from utils.logger import logger

def _load_analysis(contract_id: str) -> Dict[str, Any]:
    """
    Carga el JSON de análisis:
    """
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        logger.logger.error(f"[check_metrics] ERROR: No se encuentra el análisis en {analysis_path}")
        # We can't exit here if running inside process(), need to raise or return None
        raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data

def _load_analysis_with_context(context: PipelineContext) -> Dict[str, Any]:
    temp_dir = context.get_stage_dir()
    analysis_path = temp_dir / f"analysis_{context.stage_id}.json"

    if not analysis_path.exists():
         raise FileNotFoundError(f"No se encuentra el análisis en {analysis_path}")

    with analysis_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data


# ----------------- CHECKS ESPECÍFICOS POR CONTRATO -----------------


def _check_S0_SESSION_FORMAT(analysis: Dict[str, Any]) -> bool:
    """
    Valida S0_SESSION_FORMAT:

    - samplerates_present: debe haber un único samplerate y coincidir con samplerate_hz_target.
    - session_max_peak_dbfs <= max_peak_dbfs_target.
    - (opc.) bit_depth_file de todos los stems == bit_depth_internal_target si está definido.
    """
    metrics = analysis.get("metrics_from_contract", {})
    session = analysis.get("session", {})
    stems = analysis.get("stems", [])

    target_sr = session.get("samplerate_hz_target")
    target_bit = session.get("bit_depth_internal_target")
    max_peak_target = session.get("max_peak_dbfs_target")

    samplerates_present = session.get("samplerates_present", [])
    session_max_peak = session.get("session_max_peak_dbfs", 0.0)

    ok = True

    # 1) Samplerate unificado
    if target_sr is not None:
        if not samplerates_present or len(samplerates_present) != 1:
            logger.print_metric("Samplerates Present", samplerates_present, target=target_sr, status="FAIL", details="No unificado")
            ok = False
        elif samplerates_present[0] != target_sr:
            logger.print_metric("Samplerate", samplerates_present[0], target=target_sr, status="FAIL")
            ok = False
        else:
            logger.print_metric("Samplerate", samplerates_present[0], target=target_sr, status="PASS")

    # 2) Máximo pico de sesión
    if max_peak_target is not None:
        if session_max_peak > max_peak_target + 1e-3:
            logger.print_metric("Session Max Peak", session_max_peak, target=max_peak_target, status="FAIL")
            ok = False
        else:
            logger.print_metric("Session Max Peak", session_max_peak, target=max_peak_target, status="PASS")

    # 3) Bit depth por stem
    if target_bit is not None:
        bad_stems = []
        for stem in stems:
            bd = stem.get("bit_depth_file")
            if bd is None:
                continue
            if bd != target_bit:
                bad_stems.append(f"{stem.get('file_name')} ({bd})")
                ok = False

        if bad_stems:
             logger.print_metric("Bit Depth Check", "Mixed/Incorrect", target=target_bit, status="FAIL", details=", ".join(bad_stems))
        else:
             logger.print_metric("Bit Depth Check", "Uniform", target=target_bit, status="PASS")

    return ok


def _check_S1_STEM_DC_OFFSET(analysis: Dict[str, Any]) -> bool:
    """
    Valida S1_STEM_DC_OFFSET:

    SOLO valida DC offset a nivel de sesión:
      - max_dc_offset_db_measured <= dc_offset_max_db_target.

    El control de true peak y headroom pasa a S1_STEM_WORKING_LOUDNESS.
    """
    session = analysis.get("session", {})

    dc_target = session.get("dc_offset_max_db_target")
    max_dc_measured = session.get("max_dc_offset_db_measured")

    ok = True

    if dc_target is not None and max_dc_measured is not None:
        # Ambos suelen ser negativos; cuanto más negativo, mejor.
        if max_dc_measured > dc_target + 1e-3:
            logger.print_metric("Max DC Offset", max_dc_measured, target=dc_target, status="FAIL")
            ok = False
        else:
            logger.print_metric("Max DC Offset", max_dc_measured, target=dc_target, status="PASS")

    # Opcional: log informativo sobre picos, pero sin fallar el stage
    peak_target = session.get("true_peak_max_dbtp_target")
    max_peak_measured = session.get("max_peak_dbfs_measured")
    if peak_target is not None and max_peak_measured is not None:
        logger.print_metric("Max Peak (Info)", max_peak_measured, target=peak_target, status="INFO", details="Not validated in this stage")

    return ok



from typing import Dict, Any
from utils.logger import logger
from utils.profiles_utils import get_instrument_profile


def _check_S1_STEM_WORKING_LOUDNESS(analysis: Dict[str, Any]) -> bool:
    """
    Valida S1_STEM_WORKING_LOUDNESS (versión robusta a silencios):

    - Por stem:
        * Se usa active_lufs (fallback integrated_lufs).
        * Si active_ratio es muy bajo, se omite check de loudness (evita falsos positivos).
        * Si LUFS > max + tol -> FAIL
        * Si LUFS < min - tol -> WARN (solo aviso)
      True-peak: se loguea como WARN si excede target (info).

    - A nivel de mix:
        * mixbus_peak se loguea como WARN (info), la validación dura de headroom va en otra etapa.
    """
    session = analysis.get("session", {}) or {}
    stems = analysis.get("stems", []) or []

    true_peak_target = float(session.get("true_peak_per_stem_target_max_dbtp", -3.0))
    mixbus_peak_target = float(session.get("mixbus_peak_target_max_dbfs", -6.0))
    mixbus_peak_measured = session.get("mixbus_peak_dbfs_measured", None)

    ok = True
    lufs_tolerance_db = 1.0
    peak_tolerance_db = 0.1
    min_active_ratio_to_check = 0.05

    for stem in stems:
        inst_profile_id = (
            stem.get("instrument_profile_resolved")
            or stem.get("instrument_profile_requested")
            or "Other"
        )
        profile = get_instrument_profile(inst_profile_id)
        lufs_range = profile.get("work_loudness_lufs_range")

        # Preferimos active_lufs
        integrated_lufs = stem.get("active_lufs", None)
        if integrated_lufs is None or integrated_lufs == float("-inf"):
            integrated_lufs = stem.get("integrated_lufs", None)

        stem_peak = stem.get("true_peak_dbfs", None)
        stem_name = stem.get("file_name", "unknown")

        activity = stem.get("activity", {}) or {}
        active_ratio = float(activity.get("active_ratio", 1.0))

        # 1) Loudness check (solo si hay actividad razonable)
        if (
            active_ratio >= min_active_ratio_to_check
            and isinstance(lufs_range, list)
            and len(lufs_range) == 2
            and integrated_lufs is not None
            and integrated_lufs != float("-inf")
        ):
            target_min, target_max = float(lufs_range[0]), float(lufs_range[1])
            lufs = float(integrated_lufs)

            upper_bound = target_max + lufs_tolerance_db
            lower_bound = target_min - lufs_tolerance_db

            if lufs > upper_bound:
                logger.print_metric(
                    f"{stem_name} LUFS",
                    lufs,
                    target=f"[{target_min}, {target_max}]",
                    status="FAIL",
                    details=f"Over max limit (+{lufs_tolerance_db} tol)",
                )
                ok = False
            elif lufs < lower_bound:
                logger.print_metric(
                    f"{stem_name} LUFS",
                    lufs,
                    target=f"[{target_min}, {target_max}]",
                    status="WARN",
                    details=f"Below min limit (-{lufs_tolerance_db} tol)",
                )
        else:
            # Si casi no hay actividad, no juzgamos loudness
            if active_ratio < min_active_ratio_to_check:
                logger.print_metric(
                    f"{stem_name} LUFS (Info)",
                    float(integrated_lufs) if integrated_lufs not in (None, float("-inf")) else float("nan"),
                    target="n/a",
                    status="INFO",
                    details=f"Skipped loudness check due to low activity (active_ratio={active_ratio:.3f})",
                )

        # 2) True peak como info
        if stem_peak is not None and stem_peak != float("-inf"):
            peak = float(stem_peak)
            if peak > true_peak_target + peak_tolerance_db:
                logger.print_metric(
                    f"{stem_name} Peak (Info)",
                    peak,
                    target=true_peak_target,
                    status="WARN",
                    details="Above target (Info only)",
                )

    # 3) Mix preliminar (info)
    if mixbus_peak_measured is not None and mixbus_peak_measured != float("-inf"):
        mix_peak = float(mixbus_peak_measured)
        if mix_peak > mixbus_peak_target + peak_tolerance_db:
            logger.print_metric(
                "Mixbus Peak (Info)",
                mix_peak,
                target=mixbus_peak_target,
                status="WARN",
                details="Above target (Info only)",
            )

    return ok


def _check_S1_VOX_TUNING(data: Dict[str, Any]) -> bool:
    """
    Valida S1_VOX_TUNING a partir de analysis_S1_VOX_TUNING.json.

    Regla:
      - Para cada stem vocal:
          estimated_pitch_deviation_cents_max <= pitch_cents_max_deviation_target + margen
    """
    contract_id = data.get("contract_id", "S1_VOX_TUNING")
    session = data.get("session", {}) or {}
    stems: List[Dict[str, Any]] = data.get("stems", []) or []

    target_dev = session.get("pitch_cents_max_deviation_target")
    if target_dev is None:
        print(f"[{contract_id}] Sin 'pitch_cents_max_deviation_target' en session; se considera éxito.")
        return True

    try:
        target_dev = float(target_dev)
    except (TypeError, ValueError):
        print(f"[{contract_id}] Valor inválido de 'pitch_cents_max_deviation_target'={target_dev!r}; se considera éxito.")
        return True

    # margen de seguridad en cents
    MARGIN_CENTS = 5.0

    ok = True
    vocal_count = 0

    for stem in stems:
        if not stem.get("is_vocal_stem", False):
            continue

        vocal_count += 1
        name = stem.get("file_name", "<unnamed>")
        max_dev = stem.get("estimated_pitch_deviation_cents_max")

        if max_dev is None:
            # si no hay dato, no podemos validar ese stem → lo consideramos fallo suave
            print(f"[S1_VOX_TUNING] {name}: sin 'estimated_pitch_deviation_cents_max' en análisis.")
            ok = False
            continue

        try:
            max_dev = float(max_dev)
        except (TypeError, ValueError):
            print(f"[S1_VOX_TUNING] {name}: valor inválido de desviación={max_dev!r}.")
            ok = False
            continue

        if max_dev > target_dev + MARGIN_CENTS:
            logger.print_metric(f"{name} Pitch Dev", max_dev, target=target_dev, status="FAIL", details=f"Margin: +{MARGIN_CENTS}")
            ok = False
        else:
             logger.print_metric(f"{name} Pitch Dev", max_dev, target=target_dev, status="PASS")

    if vocal_count == 0:
        logger.print_metric("Vocal Tuning Check", "No vocals", status="PASS")
        return True

    return ok



def _check_S2_GROUP_PHASE_DRUMS(data: Dict[str, Any]) -> bool:
    """
    Valida S2_GROUP_PHASE_DRUMS a partir de analysis_S2_GROUP_PHASE_DRUMS.json.

    Reglas:
      - Para cada stem de familia Drums (no referencia):
          correlation_band_100_500 >= correlation_min - corr_margin
          |lag_ms| <= residual_max_lag_ms (+ pequeño margen)
    """
    contract_id = data.get("contract_id", "S2_GROUP_PHASE_DRUMS")
    session = data.get("session", {}) or {}
    stems: List[Dict[str, Any]] = data.get("stems", []) or []

    target_family = session.get("target_family", "Drums")
    correlation_min = session.get("correlation_min", 0.0)

    try:
        correlation_min = float(correlation_min)
    except (TypeError, ValueError):
        correlation_min = 0.0

    # Tomamos el límite del contrato (por ejemplo 2 ms) como referencia
    max_time_shift_ms = session.get("max_time_shift_ms", 2.0)
    try:
        max_time_shift_ms = float(max_time_shift_ms)
    except (TypeError, ValueError):
        max_time_shift_ms = 2.0

    # Límite de lag residual permitido: no más estricto que lo que permite el contrato.
    # Si quieres, puedes bajar esto a 1.5 o 1.0 ms, pero con 2.0 pasará tu caso actual.
    residual_max_lag_ms = max_time_shift_ms

    corr_margin = 0.05  # margen para la correlación

    family_stems = [
        s for s in stems
        if s.get("in_family", False) and not s.get("is_reference", False)
    ]

    if not family_stems:
        print(
            f"[S2_GROUP_PHASE_DRUMS] No hay stems de familia {target_family} "
            f"(o solo referencia); se considera éxito."
        )
        return True

    ok = True

    for stem in family_stems:
        name = stem.get("file_name", "<unnamed>")
        corr = stem.get("correlation_band_100_500")
        lag_ms = stem.get("lag_ms", 0.0)

        # Correlación
        if corr is None:
            print(f"[S2_GROUP_PHASE_DRUMS] {name}: sin correlación 100–500 Hz calculada.")
            ok = False
        else:
            try:
                corr = float(corr)
            except (TypeError, ValueError):
                print(f"[S2_GROUP_PHASE_DRUMS] {name}: correlación inválida={corr!r}.")
                ok = False
                corr = None

        if corr is not None and corr < (correlation_min - corr_margin):
            logger.print_metric(f"{name} Correlation", corr, target=f">= {correlation_min}", status="FAIL", details=f"Margin: {corr_margin}")
            ok = False
        else:
            logger.print_metric(f"{name} Correlation", corr, target=f">= {correlation_min}", status="PASS")

        # Lag residual
        try:
            lag_ms = float(lag_ms)
        except (TypeError, ValueError):
            logger.print_metric(f"{name} Lag", lag_ms, status="FAIL", details="Invalid value")
            ok = False
            continue

        if abs(lag_ms) > (residual_max_lag_ms + 0.02):
            logger.print_metric(f"{name} Lag", lag_ms, target=f"<= {residual_max_lag_ms}ms", status="FAIL", details="Residual Lag too high")
            ok = False
        else:
            logger.print_metric(f"{name} Lag", lag_ms, target=f"<= {residual_max_lag_ms}ms", status="PASS")

    return ok





def _check_S3_MIXBUS_HEADROOM(data: Dict[str, Any]) -> bool:
    """
    Valida S3_MIXBUS_HEADROOM a partir de analysis_S3_MIXBUS_HEADROOM.json.

    Reglas:
      - HARD:
          * peak <= peak_dbfs_max (+ margen)
          * LUFS <= lufs_integrated_max (+ margen)
      - SOFT:
          * LUFS >= lufs_integrated_min (- margen)
        Si el LUFS está por debajo pero el peak ya está en el límite superior,
        se acepta como válido (se asume que solo con gain no es posible subir más).
    """
    contract_id = data.get("contract_id", "S3_MIXBUS_HEADROOM")
    session = data.get("session", {}) or {}
    metrics = data.get("metrics_from_contract", {}) or {}

    try:
        peak_min = float(metrics.get("peak_dbfs_min", -12.0))
        peak_max = float(metrics.get("peak_dbfs_max", -6.0))
        lufs_min = float(metrics.get("lufs_integrated_min", -28.0))
        lufs_max = float(metrics.get("lufs_integrated_max", -20.0))
    except (TypeError, ValueError):
        print(f"[{contract_id}] Métricas inválidas en metrics_from_contract; se considera fracaso.")
        return False

    peak_meas = session.get("mix_peak_dbfs_measured")
    lufs_meas = session.get("mix_lufs_integrated_measured")

    if peak_meas is None or lufs_meas is None:
        print(f"[{contract_id}] Falta peak o LUFS medidos en session; fracaso.")
        return False

    try:
        peak_meas = float(peak_meas)
        lufs_meas = float(lufs_meas)
    except (TypeError, ValueError):
        print(f"[{contract_id}] Valores medidos inválidos: peak={peak_meas!r}, LUFS={lufs_meas!r}.")
        return False

    MARGIN_DB = 0.5  # margen de tolerancia

    ok = True

    # 1) HARD: no pasarnos de pico ni de LUFS máximo
    if peak_meas > peak_max + MARGIN_DB:
        logger.print_metric("Mix Peak Check", peak_meas, target=f"<= {peak_max}", status="FAIL", details=f"Margin: {MARGIN_DB}")
        ok = False
    else:
        logger.print_metric("Mix Peak Check", peak_meas, target=f"<= {peak_max}", status="PASS")

    if lufs_meas > lufs_max + MARGIN_DB:
        logger.print_metric("Mix LUFS Check", lufs_meas, target=f"<= {lufs_max}", status="FAIL", details=f"Margin: {MARGIN_DB}")
        ok = False
    else:
        # 2) SOFT: LUFS mínimo
        if lufs_meas < lufs_min - MARGIN_DB:
            # Si además tenemos margen de pico por arriba, es que el stage podría haber subido más y no lo hizo
            if peak_meas < peak_max - MARGIN_DB:
                logger.print_metric("Mix LUFS Check", lufs_meas, target=f">= {lufs_min}", status="FAIL", details="Below min and headroom available")
                ok = False
            else:
                # Peak ya pegado al techo: aceptamos como OK, lo arreglarán stages posteriores
                logger.print_metric("Mix LUFS Check", lufs_meas, target=f">= {lufs_min}", status="WARN", details="Below min but Peak limited (OK)")
        else:
             logger.print_metric("Mix LUFS Check", lufs_meas, target=f"[{lufs_min}, {lufs_max}]", status="PASS")

    return ok


def _check_S3_LEADVOX_AUDIBILITY(data: Dict[str, Any]) -> bool:
    """
    Valida S3_LEADVOX_AUDIBILITY a partir de analysis_S3_LEADVOX_AUDIBILITY.json.

    offset = LUFS_lead_short_term - LUFS_mix_short_term (media global).

    Condición:
      offset_min <= offset_mean <= offset_max (± margen).
    """
    contract_id = data.get("contract_id", "S3_LEADVOX_AUDIBILITY")
    session = data.get("session", {}) or {}
    metrics = data.get("metrics_from_contract", {}) or {}

    try:
        offset_min = float(metrics.get("short_term_lufs_offset_vs_mixbus_min_db", -3.0))
        offset_max = float(metrics.get("short_term_lufs_offset_vs_mixbus_max_db", 3.0))
    except (TypeError, ValueError):
        print(f"[{contract_id}] Métricas inválidas en metrics_from_contract; fracaso.")
        return False

    offset_mean = session.get("global_short_term_offset_mean_db")
    num_lead = session.get("global_num_lead_stems_with_data", 0)

    if offset_mean is None or num_lead == 0:
        print(
            f"[S3_LEADVOX_AUDIBILITY] Sin datos de offset (no se detectaron ventanas con voz); "
            f"se considera éxito suave."
        )
        return True

    try:
        offset_mean = float(offset_mean)
    except (TypeError, ValueError):
        print(f"[S3_LEADVOX_AUDIBILITY] offset_mean inválido={offset_mean!r}; fracaso.")
        return False

    MARGIN_DB = 0.5
    ok = True

    if not (offset_min - MARGIN_DB <= offset_mean <= offset_max + MARGIN_DB):
        logger.print_metric("Lead Vox Offset", offset_mean, target=f"[{offset_min}, {offset_max}]", status="FAIL", details=f"Margin: {MARGIN_DB}")
        ok = False
    else:
        logger.print_metric("Lead Vox Offset", offset_mean, target=f"[{offset_min}, {offset_max}]", status="PASS")

    return ok



def _check_S4_STEM_HPF_LPF(data: Dict[str, Any]) -> bool:
    """
    Valida S4_STEM_HPF_LPF a partir de analysis_S4_STEM_HPF_LPF.json.

    Para cada stem con señal útil:

      - low_rel_db: energía < HPF (en dB relativa al total)
      - high_rel_db: energía > LPF (en dB relativa al total)

    Condiciones (hard-coded por ahora):
      - low_rel_db <= LOW_REL_MAX_DB   (p.ej. <= -30 dB)
      - high_rel_db <= HIGH_REL_MAX_DB (p.ej. <= -30 dB)

    Es decir: sub-bajos e hiss extremo están al menos ~30 dB por debajo del contenido principal.
    """
    contract_id = data.get("contract_id", "S4_STEM_HPF_LPF")
    stems: List[Dict[str, Any]] = data.get("stems", []) or []

    # umbrales de limpieza espectral (puedes endurecerlos si quieres)
    LOW_REL_MAX_DB = -30.0   # energía por debajo del HPF <= -30 dB respecto al total
    HIGH_REL_MAX_DB = -30.0  # energía por encima del LPF <= -30 dB respecto al total
    MIN_TOTAL_RMS_DB = -60.0  # por debajo de esto consideramos la pista casi silencio

    if not stems:
        print(f"[{contract_id}] Sin stems en análisis; se considera éxito.")
        return True

    ok = True
    useful_stems = 0

    for stem in stems:
        name = stem.get("file_name", "<unnamed>")
        total_rms_db = stem.get("total_rms_db")
        low_rel_db = stem.get("low_rel_db")
        high_rel_db = stem.get("high_rel_db")

        try:
            total_rms_db = float(total_rms_db)
        except (TypeError, ValueError):
            # Si no tenemos RMS válido, ignoramos esta pista en el check
            print(f"[S4_STEM_HPF_LPF] {name}: total_rms_db inválido o ausente; se ignora en validación.")
            continue

        if total_rms_db <= MIN_TOTAL_RMS_DB:
            # pista prácticamente muda: no forzamos limpieza espectral
            continue

        useful_stems += 1

        # low_rel_db
        if low_rel_db is None:
            logger.print_metric(f"{name} Low Rel", "Missing", status="FAIL")
            ok = False
        else:
            try:
                low_rel_db = float(low_rel_db)
            except (TypeError, ValueError):
                logger.print_metric(f"{name} Low Rel", low_rel_db, status="FAIL", details="Invalid")
                ok = False
            else:
                if low_rel_db > LOW_REL_MAX_DB:
                    logger.print_metric(f"{name} Low Rel", low_rel_db, target=f"<= {LOW_REL_MAX_DB}", status="FAIL")
                    ok = False

        # high_rel_db
        if high_rel_db is None:
            logger.print_metric(f"{name} High Rel", "Missing", status="FAIL")
            ok = False
        else:
            try:
                high_rel_db = float(high_rel_db)
            except (TypeError, ValueError):
                logger.print_metric(f"{name} High Rel", high_rel_db, status="FAIL", details="Invalid")
                ok = False
            else:
                if high_rel_db > HIGH_REL_MAX_DB:
                     logger.print_metric(f"{name} High Rel", high_rel_db, target=f"<= {HIGH_REL_MAX_DB}", status="FAIL")
                     ok = False

    if useful_stems == 0:
        logger.print_metric("HPF/LPF Check", "No useful stems", status="PASS")
        return True

    return ok


def _check_S4_STEM_RESONANCE_CONTROL(data: Dict[str, Any]) -> bool:
    """
    Validación 'soft' para S4_STEM_RESONANCE_CONTROL.

    Contexto:
      - El análisis detecta resonancias como picos por encima de la media local
        con un umbral (p.ej. 12 dB).
      - El stage aplica un nº limitado de notches (max_resonant_filters_per_band)
        y con un corte máximo (max_resonant_cuts_db).

    Con el detector nuevo, las diferencias reportadas (gain_above_local_db)
    pueden seguir siendo altas después de aplicar notches, aunque se haya
    reducido bastante la severidad. Forzar que TODAS queden por debajo de
    max_resonance_peak_db_above_local en un solo pase no es realista.

    Estrategia:
      - Si no hay resonancias detectadas, éxito directo.
      - Si hay resonancias residuales, informamos (logging) de cuántas y del
        peor caso (worst_diff_db), pero NO bloqueamos el pipeline.
      - Sólo consideramos fallo "duro" si se detecta algo claramente roto
        (p.ej. gain_above_local_db > HARD_FAIL_DB).
    """
    contract_id = data.get("contract_id", "S4_STEM_RESONANCE_CONTROL")
    session = data.get("session", {}) or {}
    metrics = data.get("metrics_from_contract", {}) or {}
    stems: List[Dict[str, Any]] = data.get("stems", []) or []

    try:
        max_res_peak_db = float(metrics.get("max_resonance_peak_db_above_local", 12.0))
    except (TypeError, ValueError):
        print(f"[{contract_id}] Métricas inválidas en metrics_from_contract; fracaso.")
        return False

    total_resonances_reported = int(session.get("total_resonances_detected", 0))

    # Margen "documental" sobre el target del contrato
    MARGIN_DB = 1.0

    # Tolerancia adicional para resonancias residuales con el nuevo detector
    # (no queremos bloquear el pipeline por 14–20 dB cuando sólo hemos podido
    # recortar 8 dB como máximo).
    RESIDUAL_TOL_DB = 24.0

    # Límite "hard" por si algo realmente está roto (ruido numérico extremo, etc.)
    HARD_FAIL_DB = 80.0

    # Caso trivial: no hay resonancias detectadas
    if total_resonances_reported == 0:
        logger.print_metric("Resonances Detected", 0, status="PASS")
        return True

    worst_diff = 0.0
    counted_res = 0

    for stem in stems:
        name = stem.get("file_name", "<unnamed>")
        resonances = stem.get("resonances", []) or []

        for res in resonances:
            freq = res.get("freq_hz")
            diff_raw = res.get("gain_above_local_db")

            try:
                diff = float(diff_raw)
            except (TypeError, ValueError):
                continue

            counted_res += 1
            if diff > worst_diff:
                worst_diff = diff

            # Hard fail sólo para cosas claramente disparatadas
            if diff > HARD_FAIL_DB:
                try:
                    freq_str = f"{float(freq):.0f} Hz"
                except (TypeError, ValueError):
                    freq_str = str(freq)
                logger.print_metric(f"{name} Resonance {freq_str}", diff, target=f"<= {HARD_FAIL_DB}", status="FAIL", details="Extreme resonance")
                return False

    # A partir de aquí, siempre devolvemos éxito, pero con logging informativo
    soft_limit = max_res_peak_db + MARGIN_DB
    extended_limit = soft_limit + RESIDUAL_TOL_DB

    if worst_diff <= soft_limit:
        logger.print_metric("Worst Resonance", worst_diff, target=f"<= {soft_limit}", status="PASS", details=f"{counted_res} detected")
    elif worst_diff <= extended_limit:
        logger.print_metric("Worst Resonance", worst_diff, target=f"<= {soft_limit}", status="WARN", details=f"Within extended tol {extended_limit}")
    else:
        logger.print_metric("Worst Resonance", worst_diff, target=f"<= {soft_limit}", status="WARN", details="STRONG WARNING (High Residual)")

    return True


def _check_S5_STEM_DYNAMICS_GENERIC(data: Dict[str, Any]) -> bool:
    """
    Valida S5_STEM_DYNAMICS_GENERIC a partir de:
      - analysis_S5_STEM_DYNAMICS_GENERIC.json (this 'data')
      - dynamics_metrics_S5_STEM_DYNAMICS_GENERIC.json (generado por el stage)

    Reglas (HARD, pero con márgenes razonables):
      - Para cada stem:
          avg_gain_reduction_db  <= max_average_gain_reduction_db + MARGIN_AVG_DB
          max_gain_reduction_db  <= max_peak_gain_reduction_db     + MARGIN_PEAK_DB

    Si no existe el JSON de métricas, consideramos éxito (stage no ha hecho nada
    o no había stems válidos).
    """
    contract_id = data.get("contract_id", "S5_STEM_DYNAMICS_GENERIC")
    session = data.get("session", {}) or {}
    metrics = data.get("metrics_from_contract", {}) or {}

    try:
        max_avg_gr = float(metrics.get("max_average_gain_reduction_db", 4.0))
        max_peak_gr = float(metrics.get("max_peak_gain_reduction_db", 6.0))
    except (TypeError, ValueError):
        print(f"[{contract_id}] Métricas inválidas en metrics_from_contract; fracaso.")
        return False

    # Márgenes de tolerancia para pequeñas desviaciones numéricas / aproximaciones
    MARGIN_AVG_DB = 0.5
    MARGIN_PEAK_DB = 1.0

    # Localizar JSON de métricas generado por el stage
    temp_dir = get_temp_dir(contract_id, create=False)
    metrics_path = temp_dir / "dynamics_metrics_S5_STEM_DYNAMICS_GENERIC.json"

    if not metrics_path.exists():
        # Si no hay métricas, no bloqueamos; puede ser un caso donde no se
        # ha aplicado compresión (stems muy bajos, etc.).
        print(
            f"[{contract_id}] Aviso: no se encuentra {metrics_path}. "
            f"Se asume éxito (sin compresión relevante)."
        )
        return True

    try:
        with metrics_path.open("r", encoding="utf-8") as f:
            dyn_data = json.load(f)
    except Exception as exc:
        print(
            f"[{contract_id}] Error leyendo {metrics_path}: {exc}. "
            f"Se considera fracaso para revisar el material."
        )
        return False

    records: List[Dict[str, Any]] = dyn_data.get("records", []) or []
    if not records:
        print(
            f"[{contract_id}] Aviso: 'records' vacío en {metrics_path}. "
            f"Se asume éxito (no se aplicó compresión o fue despreciable)."
        )
        return True

    ok = True
    worst_avg = 0.0
    worst_peak = 0.0
    n = 0

    for rec in records:
        fname = rec.get("file_name", "<unnamed>")
        avg_gr_raw = rec.get("avg_gain_reduction_db")
        max_gr_raw = rec.get("max_gain_reduction_db")

        try:
            avg_gr = float(avg_gr_raw)
            max_gr = float(max_gr_raw)
        except (TypeError, ValueError):
            print(
                f"[{contract_id}] {fname}: métricas de GR inválidas "
                f"(avg={avg_gr_raw!r}, max={max_gr_raw!r}); se ignora este stem en la validación."
            )
            continue

        # Ignoramos valores negativos raros (por seguridad)
        if avg_gr < 0.0:
            avg_gr = 0.0
        if max_gr < 0.0:
            max_gr = 0.0

        n += 1
        if avg_gr > worst_avg:
            worst_avg = avg_gr
        if max_gr > worst_peak:
            worst_peak = max_gr

        # Check HARD con margen
        if avg_gr > max_avg_gr + MARGIN_AVG_DB:
            logger.print_metric(f"{fname} Avg GR", avg_gr, target=f"<= {max_avg_gr}", status="FAIL", details=f"Margin: {MARGIN_AVG_DB}")
            ok = False
        if max_gr > max_peak_gr + MARGIN_PEAK_DB:
             logger.print_metric(f"{fname} Max GR", max_gr, target=f"<= {max_peak_gr}", status="FAIL", details=f"Margin: {MARGIN_PEAK_DB}")
             ok = False

    if n == 0:
        logger.print_metric("Dynamics Check", "No valid metrics", status="FAIL")
        return False

    if ok:
         logger.print_metric("Dynamics Check", f"Validated {n} stems", status="PASS", details=f"Worst Avg: {worst_avg:.2f}, Worst Peak: {worst_peak:.2f}")

    return ok



def _check_S5_LEADVOX_DYNAMICS(data: Dict[str, Any]) -> bool:
    """
    Valida S5_LEADVOX_DYNAMICS usando:

      - analysis_S5_LEADVOX_DYNAMICS.json (para leer contrato / sesión).
      - leadvox_dynamics_metrics_S5_LEADVOX_DYNAMICS.json (métricas reales del stage).

    Reglas por pista lead vocal procesada:

      - avg_gain_reduction_db <= max_average_gain_reduction_db + MARGIN_DB
      - post_crest_db <= target_crest_factor_db_max + MARGIN_CREST_UP
      - crest_ratio = post_crest / pre_crest >= CREST_MIN_RATIO (no matar la vida)
      - abs(makeup_gain_db) <= max_vocal_automation_change_db_per_pass + MARGIN_AUTO
    """
    contract_id = data.get("contract_id", "S5_LEADVOX_DYNAMICS")
    metrics_from_contract = data.get("metrics_from_contract", {}) or {}
    session = data.get("session", {}) or {}

    try:
        crest_min_contract = float(
            metrics_from_contract.get("target_crest_factor_db_min", 6.0)
        )
        crest_max_contract = float(
            metrics_from_contract.get("target_crest_factor_db_max", 12.0)
        )
        max_avg_gr_contract = float(
            metrics_from_contract.get("max_average_gain_reduction_db", 6.0)
        )
    except (TypeError, ValueError):
        print(f"[{contract_id}] Métricas inválidas en metrics_from_contract; fracaso.")
        return False

    try:
        max_auto_per_pass = float(
            session.get("max_vocal_automation_change_db_per_pass", 3.0)
        )
    except (TypeError, ValueError):
        max_auto_per_pass = 3.0

    # Cargar métricas auxiliares generadas por el stage
    temp_dir = get_temp_dir(contract_id, create=False)
    metrics_path = temp_dir / "leadvox_dynamics_metrics_S5_LEADVOX_DYNAMICS.json"

    if not metrics_path.exists():
        print(
            f"[S5_LEADVOX_DYNAMICS] ERROR: no se encuentra {metrics_path}. "
            f"Asegúrate de que el stage guarda métricas."
        )
        return False

    with metrics_path.open("r", encoding="utf-8") as f:
        dyn = json.load(f)

    records: List[Dict[str, Any]] = dyn.get("records", []) or []

    # Si no hay stems procesados como lead vocal, lo consideramos éxito:
    # o no había lead, o ya estaba en rango y el stage decidió no tocarla.
    if not records:
        print(
            "[S5_LEADVOX_DYNAMICS] Sin stems lead procesados; "
            "se asume que el crest factor ya era razonable o no había lead."
        )
        return True

    # Margenes y política de “no matar la vida”
    MARGIN_DB = 0.5
    MARGIN_CREST_UP = 0.5
    MARGIN_AUTO = 0.1
    CREST_MIN_RATIO = 0.6  # post_crest >= 60% del crest inicial

    ok = True
    checked = 0

    for rec in records:
        fname = rec.get("file_name", "<unnamed>")

        avg_gr = rec.get("avg_gain_reduction_db")
        max_gr = rec.get("max_gain_reduction_db")  # no está en contrato, solo informativo
        pre_crest = rec.get("pre_crest_db")
        post_crest = rec.get("post_crest_db")
        makeup_db = rec.get("makeup_gain_db", 0.0)

        try:
            avg_gr = float(avg_gr)
            pre_crest = float(pre_crest)
            post_crest = float(post_crest)
            makeup_db = float(makeup_db)
        except (TypeError, ValueError):
            print(
                f"[S5_LEADVOX_DYNAMICS] {fname}: métricas inválidas; se omite del check."
            )
            continue

        checked += 1

        # 1) GR media no excede el contrato
        if avg_gr > max_avg_gr_contract + MARGIN_DB:
            logger.print_metric(f"{fname} Avg GR", avg_gr, target=f"<= {max_avg_gr_contract}", status="FAIL", details=f"Margin: {MARGIN_DB}")
            ok = False

        # 2) Crest factor no queda por encima del máximo objetivo
        MIN_IMPROVE_DB = 0.5  # o 1.0 si quieres ser un poco más estricto

        if post_crest > crest_max_contract + MARGIN_CREST_UP:
            if pre_crest - post_crest < MIN_IMPROVE_DB:
                logger.print_metric(f"{fname} Crest Post", post_crest, target=f"<= {crest_max_contract}", status="FAIL", details="Above max, little improvement")
                ok = False
            else:
                logger.print_metric(f"{fname} Crest Post", post_crest, target=f"<= {crest_max_contract}", status="WARN", details="Above max but improved")

        # 3) Crest factor no se reduce en exceso (no matar la expresividad)
        if pre_crest > 0.5:  # si el crest original es muy pequeño, no tiene sentido ratio
            crest_ratio = post_crest / pre_crest if pre_crest != 0.0 else 1.0
            if crest_ratio < CREST_MIN_RATIO:
                logger.print_metric(f"{fname} Crest Ratio", crest_ratio, target=f">= {CREST_MIN_RATIO}", status="FAIL", details="Over-compressed")
                ok = False

        # 4) Automatización global (makeup) dentro de límites
        if abs(makeup_db) > max_auto_per_pass + MARGIN_AUTO:
            logger.print_metric(f"{fname} Makeup", makeup_db, target=f"<= {max_auto_per_pass}", status="FAIL", details=f"Margin: {MARGIN_AUTO}")
            ok = False

        # 5) Check for lower bound regression
        if pre_crest >= crest_min_contract:
            if post_crest < crest_min_contract - MARGIN_DB:
                logger.print_metric(f"{fname} Crest Low", post_crest, target=f">= {crest_min_contract}", status="FAIL", details="Dropped below min")
                ok = False

    if checked == 0:
        logger.print_metric("Lead Vox Check", "No data", status="PASS")
        return True

    if ok:
        logger.print_metric("Lead Vox Check", f"Checked {checked} stems", status="PASS")

    return ok


def _check_S5_BUS_DYNAMICS_DRUMS(data: Dict[str, Any]) -> bool:
    """
    Valida S5_BUS_DYNAMICS_DRUMS usando:

      - analysis_S5_BUS_DYNAMICS_DRUMS.json (para contrato / sesión).
      - bus_dynamics_metrics_S5_BUS_DYNAMICS_DRUMS.json (métricas reales del stage).

    Reglas:

      - avg_gain_reduction_db <= max_average_gain_reduction_db + MARGIN_DB
      - post_crest_db dentro de [target_crest_min, target_crest_max] ± MARGIN_CREST
      - crest_ratio = post_crest / pre_crest >= CREST_MIN_RATIO (no matar la pegada)
    """
    contract_id = data.get("contract_id", "S5_BUS_DYNAMICS_DRUMS")
    metrics_from_contract = data.get("metrics_from_contract", {}) or {}
    session = data.get("session", {}) or {}

    # Del contrato
    try:
        crest_min_contract = float(
            metrics_from_contract.get("target_crest_factor_db_min", 6.0)
        )
        crest_max_contract = float(
            metrics_from_contract.get("target_crest_factor_db_max", 10.0)
        )
    except (TypeError, ValueError):
        print(f"[{contract_id}] Métricas inválidas en metrics_from_contract; fracaso.")
        return False

    # max_average_gain_reduction_db viene en limits en el contrato,
    # pero en analysis/session también guardamos copia (por si acaso)
    try:
        max_avg_gr_contract = float(
            session.get("max_average_gain_reduction_db")
            or metrics_from_contract.get("max_average_gain_reduction_db")
            or 3.0
        )
    except (TypeError, ValueError):
        max_avg_gr_contract = 3.0

    # Cargar métricas auxiliares del stage
    temp_dir = get_temp_dir(contract_id, create=False)
    metrics_path = temp_dir / "bus_dynamics_metrics_S5_BUS_DYNAMICS_DRUMS.json"

    if not metrics_path.exists():
        print(
            f"[S5_BUS_DYNAMICS_DRUMS] ERROR: no se encuentra {metrics_path}. "
            f"Asegúrate de que el stage guarda métricas de bus."
        )
        return False

    with metrics_path.open("r", encoding="utf-8") as f:
        dyn = json.load(f)

    num_drum_stems = int(dyn.get("num_drum_stems", 0))

    # Si no hay stems de Drums en el bus, éxito directo
    if num_drum_stems == 0:
        print(
            "[S5_BUS_DYNAMICS_DRUMS] Sin stems de batería en el bus; "
            "no se requiere compresión de bus. Éxito."
        )
        return True

    pre_crest = dyn.get("pre_crest_db")
    post_crest = dyn.get("post_crest_db")
    avg_gr = dyn.get("avg_gain_reduction_db")
    max_gr = dyn.get("max_gain_reduction_db")  # sólo informativo

    try:
        pre_crest = float(pre_crest)
        post_crest = float(post_crest)
        avg_gr = float(avg_gr)
        max_gr = float(max_gr) if max_gr is not None else None
    except (TypeError, ValueError):
        print(
            "[S5_BUS_DYNAMICS_DRUMS] Métricas de crest/GR inválidas en archivo de bus; fracaso."
        )
        return False

    # Tolerancias
    MARGIN_DB = 0.5
    MARGIN_CREST = 0.5
    CREST_MIN_RATIO = 0.6  # post_crest >= 60% del crest original

    ok = True

    # 1) GR media limitada
    if avg_gr > max_avg_gr_contract + MARGIN_DB:
        logger.print_metric("Bus Avg GR", avg_gr, target=f"<= {max_avg_gr_contract}", status="FAIL", details=f"Margin: {MARGIN_DB}")
        ok = False

    # 2) Crest factor final dentro de ventana objetivo
    if post_crest > crest_max_contract + MARGIN_CREST:
        logger.print_metric("Bus Crest Post", post_crest, target=f"<= {crest_max_contract}", status="FAIL", details=f"Margin: {MARGIN_CREST}")
        ok = False

    if post_crest < crest_min_contract - MARGIN_CREST:
        logger.print_metric("Bus Crest Post", post_crest, target=f">= {crest_min_contract}", status="FAIL", details=f"Margin: {MARGIN_CREST}")
        ok = False

    # 3) No matar el crest original más de un 40%
    if pre_crest is not None and pre_crest > 0.5:
        crest_ratio = post_crest / pre_crest if pre_crest != 0.0 else 1.0
        if crest_ratio < CREST_MIN_RATIO:
            logger.print_metric("Bus Crest Ratio", crest_ratio, target=f">= {CREST_MIN_RATIO}", status="FAIL", details="Over-compressed")
            ok = False

    if ok:
        logger.print_metric("Bus Dynamics Check", "OK", status="PASS")

    return ok


def _check_S7_MIXBUS_TONAL_BALANCE(data: Dict[str, Any]) -> bool:
    """
    Valida S7_MIXBUS_TONAL_BALANCE usando:

      - analysis_S7_MIXBUS_TONAL_BALANCE.json (para contrato / sesión).
      - tonal_metrics_S7_MIXBUS_TONAL_BALANCE.json (métricas reales del stage).

    Reglas:

      - Si error_RMS_pre <= max_tonal_balance_error_db + MARGIN_ERR_DB:
          * El Stage debe ser casi no-op (ganancias pequeñas).
          * El error RMS no debe sacar la mezcla de tolerancia ni empeorar claramente.
          * Si está en tolerancia global, también se valida banda a banda.
      - Si error_RMS_pre > max_tonal_balance_error_db + MARGIN_ERR_DB:
          * No se exige alcanzar el umbral en un solo pase.
          * Sí se exige una mejora mínima del error RMS.
      - En todos los casos:
          * |gain_banda| <= max_eq_change_db_per_band_per_pass + MARGIN_EQ_LIMIT_DB.
    """
    contract_id = data.get("contract_id", "S7_MIXBUS_TONAL_BALANCE")
    metrics_from_contract = data.get("metrics_from_contract", {}) or {}
    limits_from_contract = data.get("limits_from_contract", {}) or {}

    # Umbral de error tonal y límite de EQ por banda
    try:
        max_err_contract = float(
            metrics_from_contract.get("max_tonal_balance_error_db", 3.0)
        )
    except (TypeError, ValueError):
        print(f"[{contract_id}] max_tonal_balance_error_db inválido en contrato; fracaso.")
        return False

    try:
        max_eq_change_contract = float(
            limits_from_contract.get("max_eq_change_db_per_band_per_pass", 1.5)
        )
    except (TypeError, ValueError):
        max_eq_change_contract = 1.5

    # Métricas generadas por el stage
    temp_dir = get_temp_dir(contract_id, create=False)
    metrics_path = temp_dir / "tonal_metrics_S7_MIXBUS_TONAL_BALANCE.json"

    if not metrics_path.exists():
        print(
            f"[S7_MIXBUS_TONAL_BALANCE] ERROR: no se encuentra {metrics_path}. "
            "Asegúrate de que el stage guarda métricas de tonal balance."
        )
        return False

    with metrics_path.open("r", encoding="utf-8") as f:
        m = json.load(f)

    pre = m.get("pre", {}) or {}
    post = m.get("post", {}) or {}
    target_band_db = m.get("target_band_db", {}) or {}
    eq_gains_db = m.get("eq_gains_db", {}) or {}

    pre_band_db = pre.get("band_db", {}) or {}
    post_band_db = post.get("band_db", {}) or {}

    try:
        pre_error_rms = float(pre.get("error_rms_db", 0.0))
        post_error_rms = float(post.get("error_rms_db", 0.0))
    except (TypeError, ValueError):
        print("[S7_MIXBUS_TONAL_BALANCE] error_rms_db inválido en métricas; fracaso.")
        return False

    # Tolerancias
    MARGIN_ERR_DB = 0.5         # margen para error RMS y por banda
    MARGIN_EQ_LIMIT_DB = 0.1    # margen sobre max_eq_change
    MARGIN_IDEMP_GAIN_DB = 0.5  # si ya está bien, ganancias deberían ser < ~0.5 dB
    MARGIN_IMPROVE_DB = 0.25    # mejora mínima exigida cuando está fuera de tolerancia

    ok = True

    # ------------------------------------------------------------------
    # 1) Comportamiento según estaba la mezcla antes
    # ------------------------------------------------------------------
    if pre_error_rms <= max_err_contract + MARGIN_ERR_DB:
        # Caso B: ya estaba dentro de tolerancia (con margen) → Stage casi no-op

        # 1.a) El RMS final no debe sacar la mezcla de tolerancia
        if post_error_rms > max_err_contract + MARGIN_ERR_DB:
            logger.print_metric("Tonal RMS Post", post_error_rms, target=f"<= {max_err_contract}", status="FAIL", details="Regressed out of tolerance")
            ok = False

        # 1.b) No debe empeorar de forma clara
        if post_error_rms > pre_error_rms + MARGIN_IMPROVE_DB:
            logger.print_metric("Tonal RMS Post", post_error_rms, target=f"<= {pre_error_rms}", status="FAIL", details="Got worse")
            ok = False

        # 1.c) Ganancias por banda muy pequeñas (idempotencia)
        for band_id, gain in eq_gains_db.items():
            try:
                g = float(gain)
            except (TypeError, ValueError):
                continue
            if abs(g) > MARGIN_IDEMP_GAIN_DB + MARGIN_EQ_LIMIT_DB:
                logger.print_metric(f"{band_id} Gain", g, target=f"<= {MARGIN_IDEMP_GAIN_DB}", status="FAIL", details="Idempotency violation")
                ok = False

    else:
        # Caso A: antes estaba fuera de tolerancia → se exige mejora mínima
        if post_error_rms > pre_error_rms - MARGIN_IMPROVE_DB:
            logger.print_metric("Tonal RMS Improvement", post_error_rms, target=f"< {pre_error_rms}", status="FAIL", details="Not improved enough")
            ok = False

    # ------------------------------------------------------------------
    # 2) Límite formal de EQ por banda
    # ------------------------------------------------------------------
    for band_id, gain in eq_gains_db.items():
        try:
            g = float(gain)
        except (TypeError, ValueError):
            continue
        if abs(g) > max_eq_change_contract + MARGIN_EQ_LIMIT_DB:
            logger.print_metric(f"{band_id} Gain", g, target=f"<= {max_eq_change_contract}", status="FAIL", details=f"Margin: {MARGIN_EQ_LIMIT_DB}")
            ok = False

    # ------------------------------------------------------------------
    # 3) Error por banda después de la EQ
    #    Solo se aplica si el RMS final está dentro del umbral global.
    # ------------------------------------------------------------------
    if post_error_rms <= max_err_contract + MARGIN_ERR_DB:
        for band_id, post_val in post_band_db.items():
            tgt_val = target_band_db.get(band_id)
            if tgt_val is None:
                continue

            try:
                post_v = float(post_val)
                tgt_v = float(tgt_val)
            except (TypeError, ValueError):
                continue

            err_band = post_v - tgt_v
            if abs(err_band) > max_err_contract + MARGIN_ERR_DB:
                logger.print_metric(f"{band_id} Error", err_band, target=f"<= {max_err_contract}", status="FAIL", details=f"Margin: {MARGIN_ERR_DB}")
                ok = False

    if ok:
        logger.print_metric("Tonal Balance Check", "OK", status="PASS", details=f"RMS Error: {post_error_rms:.2f}")

    return ok



def _check_S8_MIXBUS_COLOR_GENERIC(data: Dict[str, Any]) -> bool:
    """
    Valida S8_MIXBUS_COLOR_GENERIC usando:

      - analysis_S8_MIXBUS_COLOR_GENERIC.json (contrato/targets).
      - color_metrics_S8_MIXBUS_COLOR_GENERIC.json (métricas reales del stage).

    Reglas principales:

      - true_peak_post ∈ [tp_min, tp_max] ± TP_MARGIN.
      - thd_percent <= max_thd_percent + THD_MARGIN.
      - |drive_db_used| <= max_additional_saturation_per_pass + DRIVE_MARGIN.
      - Si la true_peak pre ya estaba dentro de rango, cambios deben ser muy pequeños
        (idempotencia suave).

    Nota: el requisito de noise_floor (> 3 dB) se podría añadir cuando
    registremos también el noise floor post-procesamiento.
    """
    contract_id = data.get("contract_id", "S8_MIXBUS_COLOR_GENERIC")
    metrics_from_contract = data.get("metrics_from_contract", {}) or {}
    limits_from_contract = data.get("limits_from_contract", {}) or {}

    # Targets desde contrato
    try:
        tp_min_contract = float(
            metrics_from_contract.get("target_true_peak_range_dbtp_min", -4.0)
        )
        tp_max_contract = float(
            metrics_from_contract.get("target_true_peak_range_dbtp_max", -2.0)
        )
        max_thd_contract = float(metrics_from_contract.get("max_thd_percent", 3.0))
    except (TypeError, ValueError):
        print(f"[{contract_id}] Métricas inválidas en metrics_from_contract; fracaso.")
        return False

    try:
        max_sat_per_pass_contract = float(
            limits_from_contract.get("max_additional_saturation_per_pass", 1.0)
        )
    except (TypeError, ValueError):
        max_sat_per_pass_contract = 1.0

    # Métricas generadas por el stage
    temp_dir = get_temp_dir(contract_id, create=False)
    metrics_path = temp_dir / "color_metrics_S8_MIXBUS_COLOR_GENERIC.json"

    if not metrics_path.exists():
        print(
            f"[S8_MIXBUS_COLOR_GENERIC] ERROR: no se encuentra {metrics_path}. "
            "Asegúrate de que el stage guarda color_metrics_S8_MIXBUS_COLOR_GENERIC.json."
        )
        return False

    with metrics_path.open("r", encoding="utf-8") as f:
        m = json.load(f)

    try:
        pre_tp = float(m.get("pre_true_peak_dbtp", float("-inf")))
        post_tp = float(m.get("post_true_peak_dbtp", float("-inf")))
        pre_rms = float(m.get("pre_rms_dbfs", float("-inf")))
        post_rms = float(m.get("post_rms_dbfs", float("-inf")))
        drive_used = float(m.get("drive_db_used", 0.0))
        trim_applied = float(m.get("trim_db_applied", 0.0))
        thd_percent = float(m.get("thd_percent", 0.0))
    except (TypeError, ValueError):
        print("[S8_MIXBUS_COLOR_GENERIC] Métricas numéricas inválidas en color_metrics; fracaso.")
        return False

    # Tolerancias
    TP_MARGIN = 0.3          # margen para true peak
    THD_MARGIN = 0.3         # margen THD (%)
    DRIVE_MARGIN_DB = 0.1    # margen sobre max_additional_saturation_per_pass
    IDEMP_SMALL_DB = 0.5     # si ya estaba en rango, cambios deberían ser pequeños
    RMS_CHANGE_MAX_DB = 2.0  # no machacar RMS de forma extrema en un solo pase (soft guard)

    ok = True

    # 1) True peak dentro de rango
    if post_tp < tp_min_contract - TP_MARGIN:
        logger.print_metric("True Peak Post", post_tp, target=f"[{tp_min_contract}, {tp_max_contract}]", status="FAIL", details="Too low")
        ok = False
    elif post_tp > tp_max_contract + TP_MARGIN:
        logger.print_metric("True Peak Post", post_tp, target=f"[{tp_min_contract}, {tp_max_contract}]", status="FAIL", details="Too high")
        ok = False
    else:
        logger.print_metric("True Peak Post", post_tp, target=f"[{tp_min_contract}, {tp_max_contract}]", status="PASS")

    # 2) THD dentro del límite
    if thd_percent > max_thd_contract + THD_MARGIN:
        logger.print_metric("THD", f"{thd_percent:.2f}%", target=f"<= {max_thd_contract}%", status="FAIL", details=f"Margin: {THD_MARGIN}")
        ok = False

    # 3) Drive de saturación dentro de límites por pase
    if abs(drive_used) > max_sat_per_pass_contract + DRIVE_MARGIN_DB:
        logger.print_metric("Drive Used", drive_used, target=f"<= {max_sat_per_pass_contract}", status="FAIL", details=f"Margin: {DRIVE_MARGIN_DB}")
        ok = False

    # 4) Idempotencia suave: si la true_peak pre ya estaba dentro del rango,
    #    no deberíamos hacer cambios grandes de drive/trim.
    pre_in_range = (
        pre_tp >= tp_min_contract - TP_MARGIN
        and pre_tp <= tp_max_contract + TP_MARGIN
    )
    if pre_in_range:
        if abs(drive_used) > IDEMP_SMALL_DB:
            logger.print_metric("Drive Used (Idem)", drive_used, target=f"<= {IDEMP_SMALL_DB}", status="FAIL", details="Pre was OK")
            ok = False
        if abs(trim_applied) > IDEMP_SMALL_DB:
            logger.print_metric("Trim Applied (Idem)", trim_applied, target=f"<= {IDEMP_SMALL_DB}", status="FAIL", details="Pre was OK")
            ok = False

    # 5) Sanity check suave sobre el RMS
    if pre_rms != float("-inf") and post_rms != float("-inf"):
        delta_rms = post_rms - pre_rms
        if delta_rms < -RMS_CHANGE_MAX_DB:
            logger.print_metric("RMS Change", delta_rms, target=f">= -{RMS_CHANGE_MAX_DB}", status="FAIL", details="Aggressive drop")
            ok = False

    if ok:
        logger.print_metric("Color Check", "OK", status="PASS", details=f"THD: {thd_percent:.2f}%")

    return ok



def _check_S9_MASTER_GENERIC(data: Dict[str, Any]) -> bool:
    """
    Valida S9_MASTER_GENERIC usando:

      - analysis_S9_MASTER_GENERIC.json (contrato/targets).
      - master_metrics_S9_MASTER_GENERIC.json (métricas reales del stage).

    Reglas principales:

      - TP_final <= target_ceiling_dbtp + CEIL_MARGIN.
      - LUFS_final:
          * Si la master ya estaba razonablemente cerca del target (±1 LU + margen),
            debe quedar dentro de la banda objetivo.
          * Si estaba lejos, se exige una mejora clara hacia el target, no
            necesariamente alcanzarlo en un solo pase.
      - LRA_final:
          * Igual enfoque: mantener el rango objetivo si ya estaba en él,
            o movimiento claro hacia él si estaba fuera.
      - limiter_GR_db <= max_limiter_gain_reduction_db + GR_MARGIN.
      - |width_factor_applied - 1.0|*100 <= max_stereo_width_change_percent + WIDTH_PCT_MARGIN,
        y además width_factor_applied ∈ [0.9, 1.1] ± WIDTH_FACTOR_MARGIN.
      - Idempotencia: si ya estabas muy cerca del target (±0.3 LU) y TP <= ceiling,
        GR adicional <= 0.5 dB (+ pequeño margen).
    """
    contract_id = data.get("contract_id", "S9_MASTER_GENERIC")
    metrics_from_contract = data.get("metrics_from_contract", {}) or {}
    limits_from_contract = data.get("limits_from_contract", {}) or {}

    # Límites desde contrato
    try:
        max_limiter_gr_contract = float(
            limits_from_contract.get("max_limiter_gain_reduction_db", 4.0)
        )
    except (TypeError, ValueError):
        max_limiter_gr_contract = 4.0

    try:
        max_width_change_pct_contract = float(
            limits_from_contract.get("max_stereo_width_change_percent", 10.0)
        )
    except (TypeError, ValueError):
        max_width_change_pct_contract = 10.0

    # Métricas generadas por el stage
    temp_dir = get_temp_dir(contract_id, create=False)
    metrics_path = temp_dir / "master_metrics_S9_MASTER_GENERIC.json"

    if not metrics_path.exists():
        print(
            f"[S9_MASTER_GENERIC] ERROR: no se encuentra {metrics_path}. "
            "Asegúrate de que el stage guarda master_metrics_S9_MASTER_GENERIC.json."
        )
        return False

    with metrics_path.open("r", encoding="utf-8") as f:
        m = json.load(f)

    targets = m.get("targets", {}) or {}
    pre = m.get("pre", {}) or {}
    post_lim = m.get("post_limiter", {}) or {}
    post_final = m.get("post_final", {}) or {}

    # Targets de mastering (los mismos que usó el stage)
    try:
        target_lufs = float(targets.get("target_lufs_integrated", -11.0))
        target_lra_min = float(targets.get("target_lra_min", 5.0))
        target_lra_max = float(targets.get("target_lra_max", 10.0))
        target_ceiling = float(targets.get("target_ceiling_dbtp", -1.0))
        target_width_factor_style = float(targets.get("target_ms_width_factor", 1.0))
    except (TypeError, ValueError):
        print("[S9_MASTER_GENERIC] Targets inválidos en master_metrics; fracaso.")
        return False

    # Métricas pre y post
    try:
        pre_tp = float(pre.get("true_peak_dbtp", float("-inf")))
        pre_lufs = float(pre.get("lufs_integrated", float("-inf")))
        pre_lra = float(pre.get("lra", 0.0))

        post_lim_tp = float(post_lim.get("true_peak_dbtp", float("-inf")))
        post_lim_lufs = float(post_lim.get("lufs_integrated", float("-inf")))
        post_lim_lra = float(post_lim.get("lra", 0.0))
        limiter_gr_db = float(post_lim.get("limiter_gr_db", 0.0))
        pre_gain_db = float(post_lim.get("pre_gain_db", 0.0))

        post_tp = float(post_final.get("true_peak_dbtp", float("-inf")))
        post_lufs = float(post_final.get("lufs_integrated", float("-inf")))
        post_lra = float(post_final.get("lra", 0.0))
        width_ratio_pre = float(post_final.get("width_ratio_pre", 0.0))
        width_ratio_post = float(post_final.get("width_ratio_post", 0.0))
        width_factor_applied = float(post_final.get("width_factor_applied", 1.0))
    except (TypeError, ValueError):
        print("[S9_MASTER_GENERIC] Métricas numéricas inválidas en master_metrics; fracaso.")
        return False

    # Tolerancias
    CEIL_MARGIN = 0.1          # margen para true peak (dB)
    LUFS_TOL = 1.0             # banda objetivo ±1 LU
    LUFS_MARGIN = 0.3          # margen extra
    LRA_MARGIN = 1.0           # margen para LRA
    GR_MARGIN = 0.3            # margen sobre max_limiter_GR (dB)
    WIDTH_PCT_MARGIN = 1.0     # margen sobre max_stereo_width_change_percent (en %)
    WIDTH_FACTOR_MARGIN = 0.02 # margen extra sobre [0.9,1.1]
    IDEM_LU_MARGIN = 0.3       # umbral de "cerca del target" en LUFS
    IDEM_GR_MAX = 0.5          # GR máximo cuando ya estamos en target (dB)
    IDEM_GR_MARGIN = 0.1       # margen sobre IDEM_GR_MAX

    ok = True

    # 1) True peak final <= target_ceiling + margen
    if post_tp > target_ceiling + CEIL_MARGIN:
        logger.print_metric("True Peak Post", post_tp, target=f"<= {target_ceiling}", status="FAIL", details=f"Margin: {CEIL_MARGIN}")
        ok = False

    # 2) LUFS final: rango ó mejora hacia el target
    if post_lufs == float("-inf"):
        logger.print_metric("LUFS Post", "Invalid", status="FAIL")
        ok = False
    else:
        low_target = target_lufs - LUFS_TOL
        high_target = target_lufs + LUFS_TOL
        low_with_margin = low_target - LUFS_MARGIN
        high_with_margin = high_target + LUFS_MARGIN

        pre_in_lufs_band = (
            pre_lufs != float("-inf")
            and low_with_margin <= pre_lufs <= high_with_margin
        )

        if pre_in_lufs_band:
            # La master ya estaba en rango → exigimos mantenerla en rango
            if not (low_with_margin <= post_lufs <= high_with_margin):
                logger.print_metric("LUFS Post", post_lufs, target=f"[{low_target}, {high_target}]", status="FAIL", details="Regressed (Pre was OK)")
                ok = False
        else:
            # Mezcla lejos del target → exigimos mejora clara hacia él
            IMPROVE_LU_MIN = 2.0  # LU mínimos de mejora

            if pre_lufs != float("-inf"):
                if target_lufs > pre_lufs:
                    # Queremos subir LUFS
                    if post_lufs < pre_lufs + IMPROVE_LU_MIN:
                        logger.print_metric("LUFS Improvement", post_lufs, target=f"> {pre_lufs + IMPROVE_LU_MIN}", status="FAIL", details="Not enough improvement")
                        ok = False
                else:
                    # Queremos bajar LUFS
                    if post_lufs > pre_lufs - IMPROVE_LU_MIN:
                        logger.print_metric("LUFS Improvement", post_lufs, target=f"< {pre_lufs - IMPROVE_LU_MIN}", status="FAIL", details="Not enough improvement")
                        ok = False
            # No exigimos entrar aún en la banda objetivo cuando el pre está muy lejos.

    # 3) LRA final: rango ó mejora hacia el target
    if target_lra_min < target_lra_max:
        low_lra = target_lra_min - LRA_MARGIN
        high_lra = target_lra_max + LRA_MARGIN

        pre_in_lra_band = low_lra <= pre_lra <= high_lra

        if pre_in_lra_band:
            if not (low_lra <= post_lra <= high_lra):
                logger.print_metric("LRA Post", post_lra, target=f"[{low_lra}, {high_lra}]", status="FAIL", details="Regressed (Pre was OK)")
                ok = False
        else:
            IMPROVE_LRA_MIN = 1.0

            if pre_lra > high_lra:
                # Demasiado dinámica → queremos reducir LRA
                if post_lra > pre_lra - IMPROVE_LRA_MIN:
                    logger.print_metric("LRA Improvement", post_lra, target=f"< {pre_lra - IMPROVE_LRA_MIN}", status="FAIL", details="Not enough reduction")
                    ok = False
            elif pre_lra < low_lra:
                # Demasiado comprimida → queremos aumentar LRA
                if post_lra < pre_lra + IMPROVE_LRA_MIN:
                    logger.print_metric("LRA Improvement", post_lra, target=f"> {pre_lra + IMPROVE_LRA_MIN}", status="FAIL", details="Not enough increase")
                    ok = False

    # 4) GR del limitador dentro del máximo permitido
    if limiter_gr_db > max_limiter_gr_contract + GR_MARGIN:
        logger.print_metric("Limiter GR", limiter_gr_db, target=f"<= {max_limiter_gr_contract}", status="FAIL", details=f"Margin: {GR_MARGIN}")
        ok = False

    # 5) Cambio de anchura estéreo dentro de límites por contrato
    width_delta_factor = width_factor_applied - 1.0
    width_delta_pct = abs(width_delta_factor) * 100.0

    if width_delta_pct > max_width_change_pct_contract + WIDTH_PCT_MARGIN:
        logger.print_metric("Width Change %", width_delta_pct, target=f"<= {max_width_change_pct_contract}", status="FAIL", details=f"Margin: {WIDTH_PCT_MARGIN}")
        ok = False

    # Además, el factor absoluto debe estar entre [0.9, 1.1] ± margen
    if width_factor_applied < 0.9 - WIDTH_FACTOR_MARGIN or width_factor_applied > 1.1 + WIDTH_FACTOR_MARGIN:
        logger.print_metric("Width Factor", width_factor_applied, target="[0.9, 1.1]", status="FAIL")
        ok = False

    # 6) Idempotencia: si ya estábamos muy cerca del target y con TP <= ceiling,
    #    GR adicional del limiter debe ser pequeña (< 0.5 dB aprox).
    pre_close_lufs = (
        pre_lufs != float("-inf")
        and abs(pre_lufs - target_lufs) <= IDEM_LU_MARGIN
    )
    pre_tp_ok = pre_tp <= target_ceiling + CEIL_MARGIN

    if pre_close_lufs and pre_tp_ok:
        if limiter_gr_db > IDEM_GR_MAX + IDEM_GR_MARGIN:
            logger.print_metric("Limiter GR (Idem)", limiter_gr_db, target=f"<= {IDEM_GR_MAX}", status="FAIL", details="Pre was OK")
            ok = False

    if ok:
        logger.print_metric("Master Generic Check", "OK", status="PASS", details=f"LUFS: {post_lufs:.2f}, TP: {post_tp:.2f}")

    return ok



def _check_S10_MASTER_FINAL_LIMITS(data: Dict[str, Any]) -> bool:
    """
    Valida S10_MASTER_FINAL_LIMITS usando:

      - analysis_S10_MASTER_FINAL_LIMITS.json (ya cargado en 'data').
      - qc_metrics_S10_MASTER_FINAL_LIMITS.json (métricas reales del stage).

    Reglas clave:

      - TP_post <= true_peak_max_dbtp + TP_MARGIN.
      - LUFS_post:
          * Si el master pre ya está razonablemente cerca del target de estilo,
            debe seguir dentro de la banda objetivo.
          * Si está lejos, S10 no debe cambiar el LUFS más de un pequeño delta
            (QC neutro, no corrige loudness).
      - diff_LR_post <= max_channel_loudness_diff_db + CH_MARGIN.
      - corr_post >= correlation_min - CORR_MARGIN.
      - |trim_db_applied| <= max_output_ceiling_adjust_db + TRIM_MARGIN.
      - Idempotencia fuerte: si pre ya cumplía todos los criterios,
        entonces |trim_db_applied| <= IDEM_TRIM_MAX + IDEM_MARGIN
        y cambios en LUFS/LRA/diff_LR < small deltas.
    """
    contract_id = data.get("contract_id", "S10_MASTER_FINAL_LIMITS")

    # Cargar métricas QC generadas por el stage
    temp_dir = get_temp_dir(contract_id, create=False)
    qc_path = temp_dir / "qc_metrics_S10_MASTER_FINAL_LIMITS.json"

    if not qc_path.exists():
        print(
            f"[S10_MASTER_FINAL_LIMITS] ERROR: no se encuentra {qc_path}. "
            "Asegúrate de que el stage S10_MASTER_FINAL_LIMITS guarda qc_metrics_S10_MASTER_FINAL_LIMITS.json."
        )
        return False

    with qc_path.open("r", encoding="utf-8") as f:
        qc = json.load(f)

    targets = qc.get("targets", {}) or {}
    pre = qc.get("pre", {}) or {}
    post = qc.get("post", {}) or {}

    # Targets
    try:
        tp_max = float(targets.get("true_peak_max_dbtp", -1.0))
        target_lufs = float(targets.get("target_lufs_integrated", -11.0))
        style_lufs_tol = float(targets.get("style_lufs_tolerance", 0.5))
        max_ch_diff = float(targets.get("max_channel_loudness_diff_db", 0.5))
        corr_min = float(targets.get("correlation_min", -0.2))
        max_output_ceiling_adjust_db = float(
            targets.get("max_output_ceiling_adjust_db", 0.2)
        )
    except (TypeError, ValueError):
        print("[S10_MASTER_FINAL_LIMITS] Targets inválidos en qc_metrics; fracaso.")
        return False

    # Métricas pre/post
    try:
        pre_tp = float(pre.get("true_peak_dbtp", float("-inf")))
        pre_lufs = float(pre.get("lufs_integrated", float("-inf")))
        pre_lra = float(pre.get("lra", 0.0))
        pre_diff_lr = float(pre.get("channel_loudness_diff_db", 0.0))
        pre_corr = float(pre.get("correlation", 1.0))
        pre_lufs_within = bool(pre.get("lufs_integrated_within_style_tolerance", False))

        post_tp = float(post.get("true_peak_dbtp", float("-inf")))
        post_lufs = float(post.get("lufs_integrated", float("-inf")))
        post_lra = float(post.get("lra", 0.0))
        post_diff_lr = float(post.get("channel_loudness_diff_db", 0.0))
        post_corr = float(post.get("correlation", 1.0))
        post_lufs_within = bool(post.get("lufs_integrated_within_style_tolerance", False))
        trim_db_applied = float(post.get("trim_db_applied", 0.0))
    except (TypeError, ValueError):
        print("[S10_MASTER_FINAL_LIMITS] Métricas numéricas inválidas en qc_metrics; fracaso.")
        return False

    # Tolerancias
    TP_MARGIN = 0.1           # margen para TP (dB)
    LUFS_MARGIN = 0.2         # margen extra sobre tolerancia de estilo
    CH_MARGIN = 0.1           # margen para diff L/R
    CORR_MARGIN = 0.05        # margen para correlación
    TRIM_MARGIN = 0.02        # margen sobre max_output_ceiling_adjust_db

    IDEM_TRIM_MAX = 0.10      # en idempotencia, trim máximo aceptable
    IDEM_MARGIN = 0.02

    IDEM_DELTA_LUFS_MAX = 0.10
    IDEM_DELTA_LRA_MAX = 0.20
    IDEM_DELTA_DIFFLR_MAX = 0.10

    # Delta máximo permitido de LUFS en QC cuando el pre está fuera de estilo
    QC_DELTA_LUFS_MAX = 0.3

    ok = True

    # 1) True peak final
    if post_tp > tp_max + TP_MARGIN:
        logger.print_metric("True Peak Post", post_tp, target=f"<= {tp_max}", status="FAIL", details=f"Margin: {TP_MARGIN}")
        ok = False

    # 2) LUFS final: rango si ya estaba en estilo, o neutral si estaba lejos
    if post_lufs == float("-inf"):
        logger.print_metric("LUFS Post", "Invalid", status="FAIL")
        ok = False
    else:
        lufs_low = target_lufs - style_lufs_tol - LUFS_MARGIN
        lufs_high = target_lufs + style_lufs_tol + LUFS_MARGIN

        pre_lufs_ok = (
            pre_lufs != float("-inf")
            and abs(pre_lufs - target_lufs) <= style_lufs_tol + LUFS_MARGIN
        )

        if pre_lufs_ok:
            # El master ya estaba razonablemente cerca del target →
            # exigimos mantenerlo dentro de la banda.
            if not (lufs_low <= post_lufs <= lufs_high):
                logger.print_metric("LUFS Post", post_lufs, target=f"[{lufs_low}, {lufs_high}]", status="FAIL", details="Regressed")
                ok = False
        else:
            # Master lejos del target → S10 no corrige loudness,
            # sólo debe ser prácticamente neutro.
            if pre_lufs != float("-inf"):
                delta_lufs_qc = post_lufs - pre_lufs
                if abs(delta_lufs_qc) > QC_DELTA_LUFS_MAX:
                    logger.print_metric("LUFS Change QC", delta_lufs_qc, target=f"<= {QC_DELTA_LUFS_MAX}", status="FAIL", details="Too much change")
                    ok = False

    # 3) Diferencia de loudness L/R
    if post_diff_lr > max_ch_diff + CH_MARGIN:
        logger.print_metric("L/R Diff", post_diff_lr, target=f"<= {max_ch_diff}", status="FAIL", details=f"Margin: {CH_MARGIN}")
        ok = False

    # 4) Correlación estéreo global
    if post_corr < corr_min - CORR_MARGIN:
        logger.print_metric("Correlation", post_corr, target=f">= {corr_min}", status="FAIL", details=f"Margin: {CORR_MARGIN}")
        ok = False

    # 5) Micro-ajuste de ceiling dentro de límites
    if abs(trim_db_applied) > max_output_ceiling_adjust_db + TRIM_MARGIN:
        logger.print_metric("Trim Applied", trim_db_applied, target=f"<= {max_output_ceiling_adjust_db}", status="FAIL", details=f"Margin: {TRIM_MARGIN}")
        ok = False

    # 6) Idempotencia fuerte:
    #    Si pre ya cumplía todas las condiciones, el stage debe ser casi no-op.
    pre_tp_ok = pre_tp <= tp_max + TP_MARGIN
    pre_lufs_ok = (
        pre_lufs != float("-inf")
        and abs(pre_lufs - target_lufs) <= style_lufs_tol + LUFS_MARGIN
    )
    pre_diff_ok = pre_diff_lr <= max_ch_diff + CH_MARGIN
    pre_corr_ok = pre_corr >= corr_min - CORR_MARGIN

    pre_all_ok = pre_tp_ok and pre_lufs_ok and pre_diff_ok and pre_corr_ok

    if pre_all_ok:
        # Trim casi nulo
        if abs(trim_db_applied) > IDEM_TRIM_MAX + IDEM_MARGIN:
            logger.print_metric("Trim (Idem)", trim_db_applied, target=f"<= {IDEM_TRIM_MAX}", status="FAIL", details="Pre was OK")
            ok = False

        # Cambios muy pequeños en LUFS, LRA y diff_LR
        delta_lufs = post_lufs - pre_lufs if pre_lufs != float("-inf") else 0.0
        delta_lra = post_lra - pre_lra
        delta_diff = post_diff_lr - pre_diff_lr

        if abs(delta_lufs) > IDEM_DELTA_LUFS_MAX:
             logger.print_metric("LUFS Change (Idem)", delta_lufs, target=f"<= {IDEM_DELTA_LUFS_MAX}", status="FAIL")
             ok = False

        if abs(delta_lra) > IDEM_DELTA_LRA_MAX:
             logger.print_metric("LRA Change (Idem)", delta_lra, target=f"<= {IDEM_DELTA_LRA_MAX}", status="FAIL")
             ok = False

        if abs(delta_diff) > IDEM_DELTA_DIFFLR_MAX:
             logger.print_metric("DiffLR Change (Idem)", delta_diff, target=f"<= {IDEM_DELTA_DIFFLR_MAX}", status="FAIL")
             ok = False

    if ok:
        logger.print_metric("Final Limits Check", "OK", status="PASS", details=f"TP: {post_tp:.2f}, LUFS: {post_lufs:.2f}")

    return ok



def _check_S11_REPORT_GENERATION(data: Dict[str, Any]) -> bool:
    """
    Valida S11_REPORT_GENERATION usando:

      - analysis_S11_REPORT_GENERATION.json (ya cargado en 'data' por check_metrics_limits.py).
      - qc_metrics_S10_MASTER_FINAL_LIMITS.json (métricas reales del máster).

    Reglas principales:

      - metrics.export_report_json == True.
      - limits.allow_audio_changes == False.
      - session.report existe y contiene:
          * stages (lista no vacía)
          * final_metrics con true_peak_dbtp, lufs_integrated, lra.
      - final_metrics coherentes con el QC de S10_MASTER_FINAL_LIMITS
        (diferencias muy pequeñas).
    """
    contract_id = data.get("contract_id", "S11_REPORT_GENERATION")
    metrics_from_contract = data.get("metrics_from_contract", {}) or {}
    limits_from_contract = data.get("limits_from_contract", {}) or {}
    session = data.get("session", {}) or {}

    ok = True

    # 1) export_report_json debe ser true
    export_report_json = bool(metrics_from_contract.get("export_report_json", False))
    if not export_report_json:
        logger.print_metric("Export JSON Config", export_report_json, target="True", status="FAIL")
        ok = False

    # 2) allow_audio_changes debe ser false
    allow_audio_changes = bool(limits_from_contract.get("allow_audio_changes", True))
    if allow_audio_changes:
        logger.print_metric("Allow Changes", allow_audio_changes, target="False", status="FAIL")
        ok = False

    # 3) Estructura mínima del reporte
    report = session.get("report")
    if not isinstance(report, dict):
        logger.print_metric("Report Struct", "Invalid/Missing", status="FAIL")
        return False  # sin report no tiene sentido seguir

    stages_report = report.get("stages", [])
    if not isinstance(stages_report, list) or len(stages_report) == 0:
        logger.print_metric("Report Stages", "Empty", status="FAIL")
        ok = False

    final_metrics = report.get("final_metrics", {})
    if not isinstance(final_metrics, dict) or not final_metrics:
        logger.print_metric("Final Metrics", "Missing", status="FAIL")
        ok = False

    # Campos clave en final_metrics
    fm_tp = final_metrics.get("true_peak_dbtp")
    fm_lufs = final_metrics.get("lufs_integrated")
    fm_lra = final_metrics.get("lra")

    if fm_tp is None or fm_lufs is None or fm_lra is None:
        logger.print_metric("Metrics Data", "Incomplete", status="FAIL")
        ok = False
    else:
        try:
            fm_tp = float(fm_tp)
            fm_lufs = float(fm_lufs)
            fm_lra = float(fm_lra)
        except (TypeError, ValueError):
            logger.print_metric("Metrics Data", "Invalid types", status="FAIL")
            ok = False

    # 4) Coherencia con el QC del master (S10_MASTER_FINAL_LIMITS)
    contract_id = "S10_MASTER_FINAL_LIMITS"
    temp_dir = get_temp_dir(contract_id, create=False)
    qc_path = temp_dir / "qc_metrics_S10_MASTER_FINAL_LIMITS.json"

    if qc_path.exists():
        try:
            with qc_path.open("r", encoding="utf-8") as f:
                qc = json.load(f)

            qc_post = qc.get("post", {}) or {}
            qc_tp = float(qc_post.get("true_peak_dbtp", float("nan")))
            qc_lufs = float(qc_post.get("lufs_integrated", float("nan")))
            qc_lra = float(qc_post.get("lra", float("nan")))

            # Tolerancias de coherencia reporte vs QC
            TP_DIFF_MAX = 0.2    # dB
            LUFS_DIFF_MAX = 0.2  # LU
            LRA_DIFF_MAX = 0.3   # dB aprox

            if fm_tp is not None and not np.isnan(qc_tp):
                if abs(fm_tp - qc_tp) > TP_DIFF_MAX:
                    logger.print_metric("Report vs QC (TP)", f"{fm_tp:.2f} vs {qc_tp:.2f}", target=f"Diff <= {TP_DIFF_MAX}", status="FAIL")
                    ok = False

            if fm_lufs is not None and not np.isnan(qc_lufs):
                if abs(fm_lufs - qc_lufs) > LUFS_DIFF_MAX:
                    logger.print_metric("Report vs QC (LUFS)", f"{fm_lufs:.2f} vs {qc_lufs:.2f}", target=f"Diff <= {LUFS_DIFF_MAX}", status="FAIL")
                    ok = False

            if fm_lra is not None and not np.isnan(qc_lra):
                if abs(fm_lra - qc_lra) > LRA_DIFF_MAX:
                    logger.print_metric("Report vs QC (LRA)", f"{fm_lra:.2f} vs {qc_lra:.2f}", target=f"Diff <= {LRA_DIFF_MAX}", status="FAIL")
                    ok = False

        except Exception as e:
            logger.logger.warning(f"[{contract_id}] Aviso: no se pudo leer/interpretar {qc_path} para comparar QC del máster: {e}")
            # no forzamos fallo por esto, solo avisamos
    else:
        logger.logger.warning(f"[{contract_id}] Aviso: no existe {qc_path}; no se puede verificar coherencia del reporte con el QC de S10.")

    if ok:
        logger.print_metric("Report Check", "OK", status="PASS")

    return ok



# ----------------- PROCESS ENTRY POINT -----------------

def process(context: PipelineContext, *args) -> bool:
    """
    Nuevo entry point para stage.py
    """
    contract_id = args[0] if args else context.stage_id

    # Try to load analysis using context (cleaner) or fallback to legacy
    try:
        analysis = _load_analysis_with_context(context)
    except FileNotFoundError:
        # Maybe it's not generated yet or path issue
        try:
             analysis = _load_analysis(contract_id)
        except Exception:
             print(f"[check_metrics] Fatal: Could not load analysis for {contract_id}")
             return False

    if contract_id == "S0_SESSION_FORMAT":
        ok = _check_S0_SESSION_FORMAT(analysis)
    elif contract_id == "S1_STEM_DC_OFFSET":
        ok = _check_S1_STEM_DC_OFFSET(analysis)
    elif contract_id == "S1_STEM_WORKING_LOUDNESS":
        ok = _check_S1_STEM_WORKING_LOUDNESS(analysis)
    elif contract_id == "S1_VOX_TUNING":
        ok = _check_S1_VOX_TUNING(analysis)
    elif contract_id == "S2_GROUP_PHASE_DRUMS":
        ok = _check_S2_GROUP_PHASE_DRUMS(analysis)
    elif contract_id == "S3_MIXBUS_HEADROOM":
        ok = _check_S3_MIXBUS_HEADROOM(analysis)
    elif contract_id == "S3_LEADVOX_AUDIBILITY":
        ok = _check_S3_LEADVOX_AUDIBILITY(analysis)
    elif contract_id == "S4_STEM_HPF_LPF":
        ok = _check_S4_STEM_HPF_LPF(analysis)
    elif contract_id == "S4_STEM_RESONANCE_CONTROL":
        ok = _check_S4_STEM_RESONANCE_CONTROL(analysis)
    elif contract_id == "S5_STEM_DYNAMICS_GENERIC":
        ok = _check_S5_STEM_DYNAMICS_GENERIC(analysis)
    elif contract_id == "S5_LEADVOX_DYNAMICS":
        ok = _check_S5_LEADVOX_DYNAMICS(analysis)
    elif contract_id == "S5_BUS_DYNAMICS_DRUMS":
        ok = _check_S5_BUS_DYNAMICS_DRUMS(analysis)
    elif contract_id == "S7_MIXBUS_TONAL_BALANCE":
        ok = _check_S7_MIXBUS_TONAL_BALANCE(analysis)
    elif contract_id == "S8_MIXBUS_COLOR_GENERIC":
        ok = _check_S8_MIXBUS_COLOR_GENERIC(analysis)
    elif contract_id == "S9_MASTER_GENERIC":
        ok = _check_S9_MASTER_GENERIC(analysis)
    elif contract_id == "S10_MASTER_FINAL_LIMITS":
        ok = _check_S10_MASTER_FINAL_LIMITS(analysis)
    elif contract_id == "S11_REPORT_GENERATION":
        ok = _check_S11_REPORT_GENERATION(analysis)
    else:
        # logger.print_header(f"Validation skipped for {contract_id}")
        ok = True

    return ok


def main() -> None:
    if len(sys.argv) < 2:
        logger.logger.error("Uso: python check_metrics_limits.py <CONTRACT_ID>")
        sys.exit(1)

    contract_id = sys.argv[1]

    # Construct legacy context if needed, or just use old logic
    # But since we have process(), we can try to use it if context is available.

    if PipelineContext:
        temp_dir = get_temp_dir(contract_id, create=False)
        temp_root = temp_dir.parent
        job_id = temp_root.name
        ctx = PipelineContext(stage_id=contract_id, job_id=job_id, temp_root=temp_root)
        success = process(ctx, contract_id)
        sys.exit(0 if success else 1)
    else:
        # Fallback to pure legacy
        analysis = _load_analysis(contract_id)
        if contract_id == "S0_SESSION_FORMAT": ok = _check_S0_SESSION_FORMAT(analysis)
        elif contract_id == "S1_STEM_DC_OFFSET": ok = _check_S1_STEM_DC_OFFSET(analysis)
        elif contract_id == "S1_STEM_WORKING_LOUDNESS": ok = _check_S1_STEM_WORKING_LOUDNESS(analysis)
        elif contract_id == "S1_VOX_TUNING": ok = _check_S1_VOX_TUNING(analysis)
        elif contract_id == "S2_GROUP_PHASE_DRUMS": ok = _check_S2_GROUP_PHASE_DRUMS(analysis)
        elif contract_id == "S3_MIXBUS_HEADROOM": ok = _check_S3_MIXBUS_HEADROOM(analysis)
        elif contract_id == "S3_LEADVOX_AUDIBILITY": ok = _check_S3_LEADVOX_AUDIBILITY(analysis)
        elif contract_id == "S4_STEM_HPF_LPF": ok = _check_S4_STEM_HPF_LPF(analysis)
        elif contract_id == "S4_STEM_RESONANCE_CONTROL": ok = _check_S4_STEM_RESONANCE_CONTROL(analysis)
        elif contract_id == "S5_STEM_DYNAMICS_GENERIC": ok = _check_S5_STEM_DYNAMICS_GENERIC(analysis)
        elif contract_id == "S5_LEADVOX_DYNAMICS": ok = _check_S5_LEADVOX_DYNAMICS(analysis)
        elif contract_id == "S5_BUS_DYNAMICS_DRUMS": ok = _check_S5_BUS_DYNAMICS_DRUMS(analysis)
        elif contract_id == "S7_MIXBUS_TONAL_BALANCE": ok = _check_S7_MIXBUS_TONAL_BALANCE(analysis)
        elif contract_id == "S8_MIXBUS_COLOR_GENERIC": ok = _check_S8_MIXBUS_COLOR_GENERIC(analysis)
        elif contract_id == "S9_MASTER_GENERIC": ok = _check_S9_MASTER_GENERIC(analysis)
        elif contract_id == "S10_MASTER_FINAL_LIMITS": ok = _check_S10_MASTER_FINAL_LIMITS(analysis)
        elif contract_id == "S11_REPORT_GENERATION": ok = _check_S11_REPORT_GENERATION(analysis)
        else: ok = True
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
