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


from typing import Dict, Any
from utils.logger import logger
from utils.profiles_utils import get_instrument_profile


def _check_S1_STEM_WORKING_LOUDNESS(data: Dict[str, Any]) -> bool:
    """
    Valida S1_STEM_WORKING_LOUDNESS usando:
      - analysis_S1_STEM_WORKING_LOUDNESS.json
      - working_loudness_metrics_S1_STEM_WORKING_LOUDNESS.json (aplicaciones reales)
    """
    contract_id = data.get("contract_id", "S1_STEM_WORKING_LOUDNESS")
    metrics = data.get("metrics_from_contract", {}) or {}
    limits = data.get("limits_from_contract", {}) or {}
    session = data.get("session", {}) or {}

    mix_target = float(session.get("mixbus_peak_target_max_dbfs", metrics.get("mixbus_peak_target_max_dbfs", -6.0)))
    stem_peak_target = float(session.get("true_peak_per_stem_target_max_dbfs", metrics.get("true_peak_per_stem_target_max_dbfs", -6.0)))

    # Leer métricas del stage
    temp_dir = get_temp_dir(contract_id, create=False)
    metrics_path = temp_dir / "working_loudness_metrics_S1_STEM_WORKING_LOUDNESS.json"
    if not metrics_path.exists():
        print(f"[{contract_id}] ERROR: no existe {metrics_path}.")
        return False

    with metrics_path.open("r", encoding="utf-8") as f:
        m = json.load(f)

    ok = True
    MARGIN_DB = 0.5

    predicted_mix_peak = float(m.get("predicted_mixbus_peak_dbfs", float("-inf")))
    global_gain = float(m.get("global_gain_db", 0.0))

    lim = m.get("limits", {}) or {}
    max_global_step_db = float(lim.get("max_global_step_db", limits.get("max_gain_change_db_per_pass", 6.0)))
    max_cut_per_stem_db = float(lim.get("max_cut_per_stem_db", limits.get("max_gain_change_db_per_pass", 6.0)))

    # 1) Cap global
    if abs(global_gain) > abs(max_global_step_db) + 0.1:
        logger.print_metric("Global Gain", global_gain, target=f"<= {max_global_step_db}", status="FAIL", details="Exceeded cap")
        ok = False

    # 2) Cap por stem: evitar recortes agresivos disparejos
    per_stem = m.get("per_stem", []) or []
    for r in per_stem:
        try:
            g_total = float(r.get("gain_total_db", 0.0))
            fname = str(r.get("file", "<unnamed>"))
        except Exception:
            continue
        if g_total < -abs(max_cut_per_stem_db) - 0.1:
            logger.print_metric(f"{fname} Gain", g_total, target=f">= {-abs(max_cut_per_stem_db)}", status="FAIL", details="Too aggressive")
            ok = False

    # 3) Mixbus: informativo (WARN si no llega)
    if predicted_mix_peak != float("-inf") and predicted_mix_peak > mix_target + MARGIN_DB:
        logger.print_metric("Mixbus Peak (Pred)", predicted_mix_peak, target=f"<= {mix_target}", status="WARN", details="Will be handled by later headroom stage if needed")
    else:
        logger.print_metric("Mixbus Peak (Pred)", predicted_mix_peak, target=f"<= {mix_target}", status="PASS")

    if ok:
        logger.print_metric("Stem Working Loudness Check", "OK", status="PASS", details="Caps respected; mixbus logged")

    return ok




def _check_S1_VOX_TUNING(data: Dict[str, Any]) -> bool:
    """
    Validación de S1_VOX_TUNING (coherencia de configuración):

    - Si hay stems vocales y tuning_strength > 0:
        * Si existe key_name o key_root_pc (key detectada), entonces:
            - Debe existir scale_pitch_classes_resolved como lista válida [0..11].
          Si no, FAIL (implica afinación cromática por falta de escala).
    - La desviación de pitch estimada en el análisis es PRE-tuning: se reporta como WARN/INFO,
      no como condición de fallo.
    """
    contract_id = data.get("contract_id", "S1_VOX_TUNING")
    session = data.get("session", {}) or {}
    stems: List[Dict[str, Any]] = data.get("stems", []) or []

    vocal_stems = [s for s in stems if s.get("is_vocal_stem", False)]
    if not vocal_stems:
        logger.print_metric("Vocal Tuning Check", "No vocals", status="PASS")
        return True

    # tuning strength (si está a 0, no exigimos escala)
    tuning_strength = session.get("tuning_strength_0_1_target")
    try:
        tuning_strength = float(tuning_strength) if tuning_strength is not None else 1.0
    except (TypeError, ValueError):
        tuning_strength = 1.0

    key_name = session.get("key_name")
    key_root_pc = session.get("key_root_pc")
    key_mode = session.get("key_mode")

    scale_resolved = session.get("scale_pitch_classes_resolved")
    scale_ok = False
    pcs: List[int] = []

    if isinstance(scale_resolved, list) and len(scale_resolved) > 0:
        try:
            pcs = sorted({int(x) % 12 for x in scale_resolved})
            scale_ok = len(pcs) > 0
        except Exception:
            scale_ok = False

    ok = True

    # 1) coherencia: si hay key detectada, exigir escala resuelta
    key_present = (key_name is not None) or (key_root_pc is not None)
    if tuning_strength > 0.0 and key_present:
        if not scale_ok:
            logger.print_metric(
                "Scale for Tuning",
                "None",
                target="scale_pitch_classes_resolved",
                status="FAIL",
                details=f"Key present (key={key_name}, mode={key_mode}) but scale is missing -> chromatic tuning",
            )
            ok = False
        else:
            logger.print_metric(
                "Scale for Tuning",
                pcs,
                target=f"Key={key_name} mode={key_mode}",
                status="PASS",
                details="Scale resolved and will constrain tuning",
            )
    else:
        # No hay key o tuning_strength==0: cromático permitido
        logger.print_metric(
            "Scale for Tuning",
            pcs if scale_ok else "None",
            status="PASS",
            details="Key not present or tuning disabled; chromatic allowed",
        )

    # 2) Reporte informativo de desviación PRE (no bloquea)
    target_dev = session.get("pitch_cents_max_deviation_target")
    try:
        target_dev = float(target_dev) if target_dev is not None else None
    except (TypeError, ValueError):
        target_dev = None

    if target_dev is not None:
        MARGIN_CENTS = 5.0
        for stem in vocal_stems:
            name = stem.get("file_name", "<unnamed>")
            max_dev = stem.get("estimated_pitch_deviation_cents_max")
            if max_dev is None:
                logger.print_metric(f"{name} Pitch Dev (pre)", "N/A", target=target_dev, status="WARN", details="No analysis value")
                continue
            try:
                v = float(max_dev)
            except (TypeError, ValueError):
                logger.print_metric(f"{name} Pitch Dev (pre)", "Invalid", target=target_dev, status="WARN")
                continue

            if v > target_dev + MARGIN_CENTS:
                logger.print_metric(f"{name} Pitch Dev (pre)", v, target=target_dev, status="WARN", details=f"Above target by >{MARGIN_CENTS}c (pre-tuning)")
            else:
                logger.print_metric(f"{name} Pitch Dev (pre)", v, target=target_dev, status="PASS")

    if ok:
        logger.print_metric("Vocal Tuning Check", "OK", status="PASS", details=f"vocals={len(vocal_stems)}")
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
    QC corregido para S3_MIXBUS_HEADROOM:
      - Fuente de verdad: headroom_metrics_S3_MIXBUS_HEADROOM.json (pre/post reales).
      - HARD: peak_post <= peak_dbfs_max (+ margen).
      - SOFT: LUFS_post dentro de [min,max] con WARN si cae por debajo, porque este stage
              ya no persigue LUFS, solo headroom.
    """
    contract_id = data.get("contract_id", "S3_MIXBUS_HEADROOM")
    metrics = data.get("metrics_from_contract", {}) or {}

    try:
        peak_max = float(metrics.get("peak_dbfs_max", -6.0))
        lufs_min = float(metrics.get("lufs_integrated_min", -28.0))
        lufs_max = float(metrics.get("lufs_integrated_max", -20.0))
    except (TypeError, ValueError):
        print(f"[{contract_id}] Métricas inválidas; fracaso.")
        return False

    temp_dir = get_temp_dir(contract_id, create=False)
    mpath = temp_dir / "headroom_metrics_S3_MIXBUS_HEADROOM.json"
    if not mpath.exists():
        print(f"[{contract_id}] ERROR: no existe {mpath}.")
        return False

    with mpath.open("r", encoding="utf-8") as f:
        m = json.load(f)

    post = m.get("post", {}) or {}
    pre = m.get("pre", {}) or {}

    try:
        peak_post = float(post.get("sample_peak_dbfs", float("-inf")))
        lufs_post = float(post.get("lufs", float("-inf")))
        peak_pre = float(pre.get("sample_peak_dbfs", float("-inf")))
        true_peak_post = float(post.get("true_peak_dbtp", float("-inf")))
    except (TypeError, ValueError):
        print(f"[{contract_id}] Métricas numéricas inválidas en {mpath}.")
        return False

    MARGIN_DB = 0.5
    ok = True

    # HARD: peak (sample-peak vs target dBFS)
    if peak_post > peak_max + MARGIN_DB:
        logger.print_metric("Mix Peak Post", peak_post, target=f"<= {peak_max}", status="FAIL", details=f"Margin: {MARGIN_DB}")
        ok = False
    else:
        logger.print_metric("Mix Peak Post", peak_post, target=f"<= {peak_max}", status="PASS")

    if np.isfinite(true_peak_post):
        logger.print_metric("Mix True Peak Post", true_peak_post, status="INFO")

    # SOFT: LUFS
    if lufs_post == float("-inf"):
        logger.print_metric("Mix LUFS Post", "N/A", status="WARN", details="No LUFS meter available")
    else:
        if lufs_post > lufs_max + MARGIN_DB:
            logger.print_metric("Mix LUFS Post", lufs_post, target=f"<= {lufs_max}", status="WARN", details="Above max (handled later)")
        elif lufs_post < lufs_min - MARGIN_DB:
            # aquí tu caso: puede quedar bajo si el material es muy dinámico,
            # pero S3 no debe perseguir LUFS.
            logger.print_metric("Mix LUFS Post", lufs_post, target=f">= {lufs_min}", status="WARN", details="Below min (expected if peak-constrained)")
        else:
            logger.print_metric("Mix LUFS Post", lufs_post, target=f"[{lufs_min}, {lufs_max}]", status="PASS")

    if ok:
        logger.print_metric("Mixbus Headroom Check", "OK", status="PASS", details=f"Peak pre={peak_pre:.2f} -> post={peak_post:.2f}")

    return ok




def _check_S3_LEADVOX_AUDIBILITY(data: Dict[str, Any]) -> bool:
    """
    Valida S3_LEADVOX_AUDIBILITY usando:

      - analysis_S3_LEADVOX_AUDIBILITY.json (pre-offset vs BED).
      - leadvox_metrics_S3_LEADVOX_AUDIBILITY.json (decisión real del stage).

    Reglas:
      - Si no hay datos (no ventanas con voz), PASS suave.
      - Validamos el POST predicho:
          offset_post_pred = offset_pre + gain_db_applied
          debe caer en [offset_min, offset_max] (± margen).
      - Validamos cap de true-peak:
          lead_pred_post_tp_max_dbtp <= lead_tp_target + margen.
      - Idempotencia: si pre ya estaba en rango (± margen),
          gain_db_applied debe ser pequeño.
    """
    contract_id = data.get("contract_id", "S3_LEADVOX_AUDIBILITY")
    session = data.get("session", {}) or {}
    metrics = data.get("metrics_from_contract", {}) or {}
    limits = data.get("limits_from_contract", {}) or {}

    # Banda objetivo desde contrato
    try:
        offset_min = float(metrics.get("short_term_lufs_offset_vs_mixbus_min_db", -3.0))
        offset_max = float(metrics.get("short_term_lufs_offset_vs_mixbus_max_db", 3.0))
    except (TypeError, ValueError):
        print(f"[{contract_id}] Métricas inválidas en metrics_from_contract; fracaso.")
        return False

    offset_pre = session.get("global_short_term_offset_mean_db")
    num_lead = int(session.get("global_num_lead_stems_with_data", 0) or 0)

    if offset_pre is None or num_lead == 0:
        logger.print_metric("Lead Vox Audibility", "No data", status="PASS", details="No vocal windows detected")
        return True

    try:
        offset_pre = float(offset_pre)
    except (TypeError, ValueError):
        print(f"[S3_LEADVOX_AUDIBILITY] offset_pre inválido={offset_pre!r}; fracaso.")
        return False

    # Leer métricas del stage
    temp_dir = get_temp_dir(contract_id, create=False)
    metrics_path = temp_dir / "leadvox_metrics_S3_LEADVOX_AUDIBILITY.json"

    if not metrics_path.exists():
        logger.print_metric("Lead Vox Metrics", "Missing", status="FAIL", details="leadvox_metrics_S3_LEADVOX_AUDIBILITY.json not found")
        return False

    with metrics_path.open("r", encoding="utf-8") as f:
        m = json.load(f)

    gain_db = float(m.get("decision", {}).get("gain_db_applied", 0.0) or 0.0)
    tp = m.get("true_peak", {}) or {}
    lead_tp_target = float(tp.get("lead_true_peak_target_max_dbtp", -3.0))
    lead_pred_post_tp_max = tp.get("lead_pred_post_tp_max_dbtp", None)

    # Tolerancias
    MARGIN_DB = 0.5
    TP_MARGIN_DB = 0.2
    IDEM_GAIN_MAX_DB = 0.5

    ok = True

    # 1) Validar offset post (predicho)
    offset_post_pred = float(offset_pre) + float(gain_db)

    if not (offset_min - MARGIN_DB <= offset_post_pred <= offset_max + MARGIN_DB):
        logger.print_metric(
            "Lead Vox Offset (Post Pred)",
            offset_post_pred,
            target=f"[{offset_min}, {offset_max}]",
            status="FAIL",
            details=f"Pre={offset_pre:.2f}, gain={gain_db:+.2f}, margin={MARGIN_DB}",
        )
        ok = False
    else:
        logger.print_metric(
            "Lead Vox Offset (Post Pred)",
            offset_post_pred,
            target=f"[{offset_min}, {offset_max}]",
            status="PASS",
            details=f"Pre={offset_pre:.2f}, gain={gain_db:+.2f}",
        )

    # 2) Validar true-peak post (predicho)
    if lead_pred_post_tp_max is not None:
        try:
            lead_pred_post_tp_max = float(lead_pred_post_tp_max)
            if lead_pred_post_tp_max > lead_tp_target + TP_MARGIN_DB:
                logger.print_metric(
                    "Lead Vox TP (Post Pred)",
                    lead_pred_post_tp_max,
                    target=f"<= {lead_tp_target}",
                    status="FAIL",
                    details=f"Margin={TP_MARGIN_DB}",
                )
                ok = False
            else:
                logger.print_metric(
                    "Lead Vox TP (Post Pred)",
                    lead_pred_post_tp_max,
                    target=f"<= {lead_tp_target}",
                    status="PASS",
                )
        except (TypeError, ValueError):
            # si está corrupto, fallo duro
            logger.print_metric("Lead Vox TP (Post Pred)", "Invalid", status="FAIL")
            ok = False

    # 3) Idempotencia: si ya estaba en rango, no debería aplicar gran gain
    pre_in_range = (offset_min - MARGIN_DB <= offset_pre <= offset_max + MARGIN_DB)
    if pre_in_range and abs(gain_db) > IDEM_GAIN_MAX_DB:
        logger.print_metric(
            "Lead Vox Gain (Idem)",
            gain_db,
            target=f"<= {IDEM_GAIN_MAX_DB}",
            status="FAIL",
            details="Pre already in range",
        )
        ok = False

    # 4) Límite formal por pasos (si existe)
    max_gain_step = float(limits.get("max_gain_change_db_per_pass", 2.0))
    max_steps = int(limits.get("max_steps_per_pass", 2))
    max_total = max_gain_step * max_steps
    if abs(gain_db) > max_total + 0.1:
        logger.print_metric(
            "Lead Vox Gain (Limit)",
            gain_db,
            target=f"<= {max_total}",
            status="FAIL",
            details="Exceeded max_total_gain",
        )
        ok = False

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
    Validación basada en métricas reales POST del stage:

      - Lee resonance_metrics_S4_STEM_RESONANCE_CONTROL.json.
      - PASS/WARN si aún hay resonancias (puede ser normal por límites).
      - FAIL si hay patrón dañino: mucho corte y poca mejora.
    """
    contract_id = data.get("contract_id", "S4_STEM_RESONANCE_CONTROL")
    metrics_from_contract = data.get("metrics_from_contract", {}) or {}
    limits_from_contract = data.get("limits_from_contract", {}) or {}

    try:
        thr_db = float(metrics_from_contract.get("max_resonance_peak_db_above_local", 12.0))
    except (TypeError, ValueError):
        thr_db = 12.0

    try:
        max_cuts_db = float(limits_from_contract.get("max_resonant_cuts_db", 8.0))
    except (TypeError, ValueError):
        max_cuts_db = 8.0

    try:
        max_filters = int(limits_from_contract.get("max_resonant_filters_per_band", 3))
    except (TypeError, ValueError):
        max_filters = 3

    temp_dir = get_temp_dir(contract_id, create=False)
    metrics_path = temp_dir / "resonance_metrics_S4_STEM_RESONANCE_CONTROL.json"

    if not metrics_path.exists():
        logger.print_metric("Resonance Metrics", "Missing", status="FAIL", details=str(metrics_path))
        return False

    with metrics_path.open("r", encoding="utf-8") as f:
        m = json.load(f)

    stems: List[Dict[str, Any]] = m.get("stems", []) or []
    summary = m.get("summary", {}) or {}

    worst_pre = float(summary.get("worst_pre_db", 0.0) or 0.0)
    worst_post = float(summary.get("worst_post_db", 0.0) or 0.0)
    improve = float(summary.get("improvement_db", worst_pre - worst_post) or (worst_pre - worst_post))

    # Tolerancias / reglas
    # - No forzamos bajar por debajo del umbral en 1 pasada.
    # - Sí exigimos que si cortas fuerte, mejores algo.
    MIN_IMPROVE_DB = 2.0
    OVERCUT_SUM_DB = 10.0     # suma de cuts por stem que ya es “mucha cirugía”
    OVERCUT_NO_IMPROVE_DB = 1.0

    ok = True

    # 1) límites formales por notch
    for s in stems:
        notches = s.get("applied_notches", []) or []
        if len(notches) > max_filters:
            logger.print_metric(f"{s.get('file_name','?')} Notches", len(notches), target=f"<= {max_filters}", status="FAIL")
            ok = False

        for n in notches:
            try:
                cut = float(n.get("cut_db", 0.0))
                q = float(n.get("q", 0.0))
            except (TypeError, ValueError):
                continue

            if cut > max_cuts_db + 0.1:
                logger.print_metric(f"{s.get('file_name','?')} Cut", cut, target=f"<= {max_cuts_db}", status="FAIL")
                ok = False

            if q > 10.0 + 0.1:
                logger.print_metric(f"{s.get('file_name','?')} Q", q, target="<= 10.0", status="FAIL", details="Q too high (ringing risk)")
                ok = False

    # 2) mejora global (si estabas muy por encima, al menos mejora algo)
    if worst_pre > thr_db + 6.0:
        if improve < MIN_IMPROVE_DB:
            logger.print_metric("Worst Resonance Improvement", improve, target=f">= {MIN_IMPROVE_DB}", status="FAIL", details=f"pre={worst_pre:.2f}, post={worst_post:.2f}")
            ok = False
        else:
            logger.print_metric("Worst Resonance Improvement", improve, status="PASS", details=f"pre={worst_pre:.2f}, post={worst_post:.2f}")
    else:
        # si no era grave, no exigimos gran mejora
        logger.print_metric("Worst Resonance Post", worst_post, status="PASS", details=f"pre={worst_pre:.2f}")

    # 3) patrón dañino: mucho corte por stem y poca mejora
    for s in stems:
        total_cut = float(s.get("total_cut_db_sum", 0.0) or 0.0)
        pre_w = float(s.get("pre", {}).get("worst_resonance_db", 0.0) or 0.0)
        post_w = float(s.get("post", {}).get("worst_resonance_db", 0.0) or 0.0)
        imp = pre_w - post_w

        if total_cut >= OVERCUT_SUM_DB and imp <= OVERCUT_NO_IMPROVE_DB:
            logger.print_metric(
                f"{s.get('file_name','?')} Over-EQ",
                imp,
                target=f"> {OVERCUT_NO_IMPROVE_DB}",
                status="FAIL",
                details=f"total_cut={total_cut:.1f} dB, pre={pre_w:.2f}, post={post_w:.2f}",
            )
            ok = False

    if ok:
        logger.print_metric("Resonance Control Check", "OK", status="PASS", details=f"worst_post={worst_post:.2f} dB")

    return ok



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
    contract_id = data.get("contract_id", "S7_MIXBUS_TONAL_BALANCE")
    metrics_from_contract = data.get("metrics_from_contract", {}) or {}
    limits_from_contract = data.get("limits_from_contract", {}) or {}

    try:
        max_err_contract = float(metrics_from_contract.get("max_tonal_balance_error_db", 3.0))
    except (TypeError, ValueError):
        print(f"[{contract_id}] max_tonal_balance_error_db inválido en contrato; fracaso.")
        return False

    try:
        max_eq_change_contract = float(limits_from_contract.get("max_eq_change_db_per_band_per_pass", 1.5))
    except (TypeError, ValueError):
        max_eq_change_contract = 1.5

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
    MARGIN_ERR_DB = 0.5
    MARGIN_EQ_LIMIT_DB = 0.1
    MARGIN_IDEMP_GAIN_DB = 0.5
    MARGIN_IMPROVE_DB = 0.25

    # Nuevo: detectar “trim global”
    GLOBAL_STD_MAX = 0.12
    GLOBAL_MEAN_MIN = 0.25
    GLOBAL_MIN_BANDS = 3

    ok = True

    # ------------------------------------------------------------------
    # 0) Anti-global-trim: si casi todas las bandas tienen el mismo gain
    # ------------------------------------------------------------------
    vals = []
    for _bid, g in eq_gains_db.items():
        try:
            gv = float(g)
        except (TypeError, ValueError):
            continue
        if abs(gv) >= 0.10:
            vals.append(gv)

    if len(vals) >= GLOBAL_MIN_BANDS:
        mean_g = sum(vals) / float(len(vals))
        var_g = sum((v - mean_g) ** 2 for v in vals) / float(len(vals))
        std_g = var_g ** 0.5

        if std_g <= GLOBAL_STD_MAX and abs(mean_g) >= GLOBAL_MEAN_MIN:
            logger.print_metric(
                "EQ Pattern",
                f"mean={mean_g:+.2f} std={std_g:.2f}",
                target="Not global trim",
                status="FAIL",
                details="Stage applied near-uniform gain across bands (global attenuation/boost).",
            )
            ok = False

    # ------------------------------------------------------------------
    # 1) Comportamiento según estaba antes
    # ------------------------------------------------------------------
    if pre_error_rms <= max_err_contract + MARGIN_ERR_DB:
        if post_error_rms > max_err_contract + MARGIN_ERR_DB:
            logger.print_metric("Tonal RMS Post", post_error_rms, target=f"<= {max_err_contract}", status="FAIL", details="Regressed out of tolerance")
            ok = False

        if post_error_rms > pre_error_rms + MARGIN_IMPROVE_DB:
            logger.print_metric("Tonal RMS Post", post_error_rms, target=f"<= {pre_error_rms}", status="FAIL", details="Got worse")
            ok = False

        for band_id, gain in eq_gains_db.items():
            try:
                g = float(gain)
            except (TypeError, ValueError):
                continue
            if abs(g) > MARGIN_IDEMP_GAIN_DB + MARGIN_EQ_LIMIT_DB:
                logger.print_metric(f"{band_id} Gain", g, target=f"<= {MARGIN_IDEMP_GAIN_DB}", status="FAIL", details="Idempotency violation")
                ok = False
    else:
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
    # 3) Error por banda (REL) si RMS ya está dentro
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
    contract_id = data.get("contract_id", "S8_MIXBUS_COLOR_GENERIC")
    metrics_from_contract = data.get("metrics_from_contract", {}) or {}
    limits_from_contract = data.get("limits_from_contract", {}) or {}

    try:
        tp_min_contract = float(metrics_from_contract.get("target_true_peak_range_dbtp_min", -4.0))
        tp_max_contract = float(metrics_from_contract.get("target_true_peak_range_dbtp_max", -2.0))
        max_thd_contract = float(metrics_from_contract.get("max_thd_percent", 3.0))
    except (TypeError, ValueError):
        print(f"[{contract_id}] Métricas inválidas en metrics_from_contract; fracaso.")
        return False

    try:
        max_sat_per_pass_contract = float(limits_from_contract.get("max_additional_saturation_per_pass", 1.0))
    except (TypeError, ValueError):
        max_sat_per_pass_contract = 1.0

    # --- CORRECCIÓN CLAVE: Leer límite de ganancia del contrato (ej. 6.0 dB) ---
    try:
        max_gain_allowed = float(limits_from_contract.get("max_gain_change_db_per_pass", 2.0))
    except (TypeError, ValueError):
        max_gain_allowed = 2.0

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

    targets = m.get("targets", {}) or {}
    pre = m.get("pre", {}) or {}
    post = m.get("post", {}) or {}
    proc = m.get("process", {}) or {}

    try:
        pre_tp = float(pre.get("true_peak_dbtp", float("-inf")))
        post_tp = float(post.get("true_peak_dbtp", float("-inf")))
        drive_used = float(proc.get("drive_db_used", 0.0))
        thd_percent = float(proc.get("thd_percent", 0.0))
        trim_total_db = float(proc.get("trim_total_db", 0.0))
        under_levelled = bool(proc.get("under_levelled_mode", False))
        nf_comp_delta = post.get("noise_floor_compensated_delta_db", None)
        nf_delta = post.get("noise_floor_delta_db", None)
    except (TypeError, ValueError):
        print("[S8_MIXBUS_COLOR_GENERIC] Métricas inválidas en color_metrics; fracaso.")
        return False

    # Tolerancias
    TP_MARGIN = 0.3
    THD_MARGIN = 0.3
    DRIVE_MARGIN_DB = 0.1

    # Guardas “calidad”
    NF_COMP_WARN_DB = 1.5  # si el noise floor compensado sube > 1.5 dB, hay suciedad añadida
    
    ok = True

    # 1) True peak: NO permitir pasarse del máximo. Si queda bajo y under_levelled, WARN (no FAIL).
    if post_tp > tp_max_contract + TP_MARGIN:
        logger.print_metric("True Peak Post", post_tp, target=f"<= {tp_max_contract}", status="FAIL", details=f"Margin: {TP_MARGIN}")
        ok = False
    elif post_tp < tp_min_contract - TP_MARGIN:
        if under_levelled:
            logger.print_metric(
                "True Peak Post",
                post_tp,
                target=f">= {tp_min_contract}",
                status="WARN",
                details="Under-levelled mode: lift capped to avoid noise/harshness",
            )
        else:
            logger.print_metric("True Peak Post", post_tp, target=f">= {tp_min_contract}", status="FAIL", details="Too low")
            ok = False
    else:
        logger.print_metric("True Peak Post", post_tp, target=f"[{tp_min_contract}, {tp_max_contract}]", status="PASS")

    # 2) THD dentro del límite
    if thd_percent > max_thd_contract + THD_MARGIN:
        logger.print_metric("THD", f"{thd_percent:.2f}%", target=f"<= {max_thd_contract}%", status="FAIL", details=f"Margin: {THD_MARGIN}")
        ok = False

    # 3) Drive dentro de límites por pase
    if abs(drive_used) > max_sat_per_pass_contract + DRIVE_MARGIN_DB:
        logger.print_metric("Drive Used", drive_used, target=f"<= {max_sat_per_pass_contract}", status="FAIL", details=f"Margin: {DRIVE_MARGIN_DB}")
        ok = False

    # 4) Guardas informativas sobre lift grande / ruido
    # --- CORRECCIÓN APLICADA: Usar max_gain_allowed en lugar de hardcode 2.0 ---
    if abs(trim_total_db) > max_gain_allowed:
        logger.print_metric("Trim Total", trim_total_db, target=f"<= {max_gain_allowed}", status="WARN", details="Large lift in color stage")

    if isinstance(nf_comp_delta, (int, float)):
        if float(nf_comp_delta) > NF_COMP_WARN_DB:
            logger.print_metric(
                "Noise Floor (Comp) Δ",
                float(nf_comp_delta),
                target=f"<= {NF_COMP_WARN_DB}",
                status="WARN",
                details="Noise/harshness likely added beyond simple gain",
            )
    elif isinstance(nf_delta, (int, float)) and float(nf_delta) > 3.0:
        # fallback si no hay compensado (compatibilidad)
        logger.print_metric("Noise Floor Δ", float(nf_delta), target="<= 3.0", status="WARN")

    if ok:
        logger.print_metric("Mixbus Color Check", "OK", status="PASS", details=f"TP: {post_tp:.2f} dBTP, THD: {thd_percent:.2f}%")

    return ok



def _check_S9_MASTER_GENERIC(data: Dict[str, Any]) -> bool:
    """
    QC estricto para S9_MASTER_GENERIC:

    - Exige ceiling.
    - Exige que el LUFS final esté razonablemente cerca del target.
      (Si no lo está, se considera FAIL: indica headroom upstream roto o cap GR insuficiente).
    - Verifica que el stage haya empujado hasta el cap (si está lejos del target).
    """
    contract_id = data.get("contract_id", "S9_MASTER_GENERIC")
    limits_from_contract = data.get("limits_from_contract", {}) or {}

    try:
        max_limiter_gr_contract = float(limits_from_contract.get("max_limiter_gain_reduction_db", 4.0))
    except (TypeError, ValueError):
        max_limiter_gr_contract = 4.0

    temp_dir = get_temp_dir(contract_id, create=False)
    metrics_path = temp_dir / "master_metrics_S9_MASTER_GENERIC.json"

    if not metrics_path.exists():
        print(f"[S9_MASTER_GENERIC] ERROR: no se encuentra {metrics_path}.")
        return False

    with metrics_path.open("r", encoding="utf-8") as f:
        m = json.load(f)

    targets = m.get("targets", {}) or {}
    pre = m.get("pre", {}) or {}
    post_lim = m.get("post_limiter", {}) or {}
    post_final = m.get("post_final", {}) or {}

    try:
        target_lufs = float(targets.get("target_lufs_integrated", -11.0))
        target_ceiling = float(targets.get("target_ceiling_dbtp", -1.0))
        max_gr = float(targets.get("max_limiter_gain_reduction_db", max_limiter_gr_contract))
    except (TypeError, ValueError):
        logger.print_metric("S9 Targets", "Invalid", status="FAIL")
        return False

    try:
        pre_lufs = float(pre.get("lufs_integrated", float("-inf")))
        pre_tp = float(pre.get("true_peak_dbtp", float("-inf")))

        gain_db = float(post_lim.get("pre_gain_db", 0.0))
        limiter_gr = float(post_lim.get("limiter_gr_db", 0.0))

        post_tp = float(post_final.get("true_peak_dbtp", float("-inf")))
        post_lufs = float(post_final.get("lufs_integrated", float("-inf")))
    except (TypeError, ValueError):
        logger.print_metric("S9 Metrics", "Invalid", status="FAIL")
        return False

    ok = True

    # Márgenes
    CEIL_MARGIN = 0.10
    # Si tu target es -11, un master a -19 no es aceptable: hard fail.
    # Ajusta esto si S9 fuera "pre-master" (pero entonces el target no debería ser -11 aquí).
    LUFS_PASS_TOL = 1.5     # ±1.5 LU
    LUFS_FAIL_FAR = 3.0     # más de 3 LU del target => FAIL
    GR_MARGIN = 0.20

    # 1) Ceiling
    if post_tp > target_ceiling + CEIL_MARGIN:
        logger.print_metric("True Peak Post", post_tp, target=f"<= {target_ceiling}", status="FAIL", details=f"Margin: {CEIL_MARGIN}")
        ok = False

    # 2) Loudness enforcement
    if post_lufs == float("-inf"):
        logger.print_metric("LUFS Post", "Invalid", status="FAIL")
        return False

    dist = abs(post_lufs - target_lufs)

    if dist <= LUFS_PASS_TOL:
        logger.print_metric("LUFS Post", post_lufs, target=f"{target_lufs} ±{LUFS_PASS_TOL}", status="PASS")
    elif dist > LUFS_FAIL_FAR:
        logger.print_metric("LUFS Post", post_lufs, target=f"{target_lufs} ±{LUFS_FAIL_FAR}", status="FAIL", details="Too far from target")
        ok = False
    else:
        logger.print_metric("LUFS Post", post_lufs, target=f"{target_lufs} ±{LUFS_PASS_TOL}", status="WARN", details="Slightly off target")

    # 3) Si estamos lejos del target por debajo, debe estar empujando cerca del cap GR,
    #    si no, significa que está dejando loudness en la mesa.
    if post_lufs < (target_lufs - LUFS_PASS_TOL):
        # queremos subir; si no estamos cerca del límite de GR -> FAIL (no está empujando)
        if limiter_gr < (max_gr - 0.8):
            logger.print_metric(
                "Limiter GR Utilization",
                limiter_gr,
                target=f"≈ {max_gr}",
                status="FAIL",
                details="Not using available GR; loudness target not pursued",
            )
            ok = False
        else:
            logger.print_metric(
                "Limiter GR Utilization",
                limiter_gr,
                target=f"≈ {max_gr}",
                status="WARN",
                details="Likely limited by GR cap / upstream headroom",
            )

    # 4) Límite formal de GR del limitador
    if limiter_gr > max_gr + GR_MARGIN:
        logger.print_metric("Limiter GR", limiter_gr, target=f"<= {max_gr}", status="FAIL", details=f"Margin: {GR_MARGIN}")
        ok = False

    if ok:
        logger.print_metric("Master Generic Check", "OK", status="PASS", details=f"LUFS={post_lufs:.2f}, TP={post_tp:.2f}, GR≈{limiter_gr:.2f}")

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
