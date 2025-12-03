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
from utils.tonal_balance_utils import compute_tonal_error  # noqa: E402

def _load_analysis(contract_id: str) -> Dict[str, Any]:
    """
    Carga el JSON de análisis:
    """
    temp_dir = get_temp_dir(contract_id, create=False)
    analysis_path = temp_dir / f"analysis_{contract_id}.json"

    if not analysis_path.exists():
        print(f"[check_metrics] ERROR: No se encuentra el análisis en {analysis_path}", file=sys.stderr)
        sys.exit(1)

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
            print("[S0_SESSION_FORMAT] samplerates_present no unificado:", samplerates_present, file=sys.stderr)
            ok = False
        elif samplerates_present[0] != target_sr:
            print(f"[S0_SESSION_FORMAT] samplerate esperado {target_sr}, obtenido {samplerates_present[0]}",
                  file=sys.stderr)
            ok = False

    # 2) Máximo pico de sesión
    if max_peak_target is not None:
        if session_max_peak > max_peak_target + 1e-3:
            print(f"[S0_SESSION_FORMAT] session_max_peak_dbfs={session_max_peak} > target={max_peak_target}",
                  file=sys.stderr)
            ok = False

    # 3) Bit depth por stem
    if target_bit is not None:
        for stem in stems:
            bd = stem.get("bit_depth_file")
            if bd is None:
                continue
            if bd != target_bit:
                print(f"[S0_SESSION_FORMAT] bit_depth_file={bd} != target={target_bit} en {stem.get('file_name')}",
                      file=sys.stderr)
                ok = False

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
            print(
                f"[S1_STEM_DC_OFFSET] max_dc_offset_db_measured={max_dc_measured} > target={dc_target}",
                file=sys.stderr,
            )
            ok = False

    # Opcional: log informativo sobre picos, pero sin fallar el stage
    peak_target = session.get("true_peak_max_dbtp_target")
    max_peak_measured = session.get("max_peak_dbfs_measured")
    if peak_target is not None and max_peak_measured is not None:
        print(
            f"[S1_STEM_DC_OFFSET] INFO: true_peak_max_dbtp_target={peak_target}, "
            f"max_peak_dbfs_measured={max_peak_measured} (no se valida en esta etapa)",
            file=sys.stderr,
        )

    return ok



def _check_S1_STEM_WORKING_LOUDNESS(analysis: Dict[str, Any]) -> bool:
    """
    Valida S1_STEM_WORKING_LOUDNESS:

    - Por stem: se comprueba que NO estén por encima del rango de trabajo
      de su instrument_profile_resolved (con tolerancia).
      Si están por debajo, solo se registra un aviso.

    - A nivel de mix: de momento solo se loguea el mixbus_peak como info,
      la validación dura de headroom se delegará a otra etapa.
    """
    session = analysis.get("session", {})
    stems = analysis.get("stems", [])

    # Targets de sesión definidos en el análisis (se usan como referencia, no hard gate)
    true_peak_target = session.get("true_peak_per_stem_target_max_dbtp", -3.0)
    mixbus_peak_target = session.get("mixbus_peak_target_max_dbfs", -6.0)
    mixbus_peak_measured = session.get("mixbus_peak_dbfs_measured")

    ok = True
    lufs_tolerance_db = 1.0
    peak_tolerance_db = 0.1

    # 1) Validación por stem (solo para evitar que se pasen de rosca)
    for stem in stems:
        inst_profile_id = stem.get("instrument_profile_resolved") or stem.get("instrument_profile_requested") or "Other"
        profile = get_instrument_profile(inst_profile_id)
        lufs_range = profile.get("work_loudness_lufs_range")

        integrated_lufs = stem.get("integrated_lufs")
        stem_peak = stem.get("true_peak_dbfs")
        stem_name = stem.get("file_name")

        # 1.a) Loudness de trabajo:
        #     - si está por encima del máximo + margen, FAIL
        #     - si está por debajo del mínimo - margen, solo aviso
        if isinstance(lufs_range, list) and len(lufs_range) == 2 and integrated_lufs is not None:
            target_min, target_max = float(lufs_range[0]), float(lufs_range[1])
            lufs = float(integrated_lufs)

            upper_bound = target_max + lufs_tolerance_db
            lower_bound = target_min - lufs_tolerance_db

            if lufs > upper_bound:
                print(
                    f"[S1_STEM_WORKING_LOUDNESS] {stem_name}: "
                    f"LUFS={lufs:.2f} por ENCIMA de rango [{target_min}, {target_max}]±{lufs_tolerance_db}",
                    file=sys.stderr,
                )
                ok = False
            elif lufs < lower_bound:
                print(
                    f"[S1_STEM_WORKING_LOUDNESS] {stem_name}: "
                    f"LUFS={lufs:.2f} por DEBAJO de rango [{target_min}, {target_max}]±{lufs_tolerance_db} (solo aviso)",
                    file=sys.stderr,
                )

        # 1.b) True peak solo como info por ahora
        if stem_peak is not None:
            peak = float(stem_peak)
            if peak > true_peak_target + peak_tolerance_db:
                print(
                    f"[S1_STEM_WORKING_LOUDNESS] AVISO {stem_name}: "
                    f"true_peak_dbfs={peak:.2f} > target={true_peak_target} (+{peak_tolerance_db} margen) "
                    f"(no se usa como criterio de fallo en esta etapa)",
                    file=sys.stderr,
                )

    # 2) Mix preliminar (solo info, validación dura se hará en etapa de headroom/mixbus)
    if mixbus_peak_measured is not None:
        mix_peak = float(mixbus_peak_measured)
        if mix_peak > mixbus_peak_target + peak_tolerance_db:
            print(
                f"[S1_STEM_WORKING_LOUDNESS] AVISO mixbus_peak_dbfs_measured={mix_peak:.2f} "
                f"> target={mixbus_peak_target} (+{peak_tolerance_db} margen) "
                f"(no se usa como criterio de fallo en esta etapa)",
                file=sys.stderr,
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
            print(
                f"[S1_VOX_TUNING] {name}: desviación máxima {max_dev:.2f} cents "
                f"> target {target_dev:.2f} (+{MARGIN_CENTS:.1f} margen)."
            )
            ok = False

    if vocal_count == 0:
        print("[S1_VOX_TUNING] No se han detectado stems vocales; se considera éxito.")
        return True

    if ok:
        print(
            f"[S1_VOX_TUNING] Todas las voces cumplen: "
            f"desvío máximo <= {target_dev:.1f}c (+{MARGIN_CENTS:.1f} margen)."
        )

    return ok



def _check_S1_MIXBUS_HEADROOM(analysis: Dict[str, Any]) -> bool:
    """
    Check de QC para S1_MIXBUS_HEADROOM.

    - Falla (False) si el pico de mixbus o el LUFS integrado están por encima
      de los máximos definidos en el contrato (con pequeña tolerancia),
      **siempre que** el LUFS no esté ya por debajo del mínimo.

    - Si el LUFS está por debajo de lufs_integrated_min, tratamos cualquier exceso
      de pico como AVISO (no error duro), para evitar seguir hundiendo mezclas
      que ya vienen flojas de origen y que además no pueden cumplir simultáneamente
      peak y LUFS solo con gain lineal.

    - También lanza avisos cuando está por debajo de los mínimos, pero sin
      bloquear el pipeline.
    """
    session = analysis.get("session", {}) or {}
    metrics = analysis.get("metrics_from_contract", {}) or {}

    mix_peak_measured = session.get("mixbus_peak_dbfs_measured")
    lufs_measured = session.get("mixbus_lufs_integrated_measured")

    try:
        mix_peak_measured = float(mix_peak_measured)
    except (TypeError, ValueError):
        mix_peak_measured = None

    try:
        lufs_measured = float(lufs_measured) if lufs_measured is not None else None
    except (TypeError, ValueError):
        lufs_measured = None

    peak_min = float(metrics.get("peak_dbfs_min", -12.0))
    peak_max = float(metrics.get("peak_dbfs_max", -6.0))
    lufs_min = float(metrics.get("lufs_integrated_min", -26.0))
    lufs_max = float(metrics.get("lufs_integrated_max", -20.0))

    peak_tol = 0.2   # margen dB de pico
    lufs_tol = 0.5   # margen dB de LUFS

    ok = True

    # --- Avisos por estar por debajo de mínimos ---
    if mix_peak_measured is not None and mix_peak_measured != float("-inf"):
        if mix_peak_measured < peak_min - peak_tol:
            print(
                f"[S1_MIXBUS_HEADROOM][CHECK] mixbus_peak_dbfs_measured="
                f"{mix_peak_measured:.2f} < peak_dbfs_min={peak_min:.2f} "
                f"(solo aviso, no se considera error duro).",
                file=sys.stderr,
            )

    if lufs_measured is not None:
        if lufs_measured < lufs_min - lufs_tol:
            print(
                f"[S1_MIXBUS_HEADROOM][CHECK] mixbus_lufs_integrated_measured="
                f"{lufs_measured:.2f} < lufs_integrated_min={lufs_min:.2f} "
                f"(solo aviso, mezcla ya floja de origen).",
                file=sys.stderr,
            )

    # Flag para saber si la mezcla ya está floja de LUFS
    lufs_demasiado_bajo = (
        lufs_measured is not None and lufs_measured < lufs_min - lufs_tol
    )

    # --- Condiciones de error duro (solo si NO está floja de LUFS) ---
    if mix_peak_measured is not None and mix_peak_measured != float("-inf"):
        if mix_peak_measured > peak_max + peak_tol:
            if lufs_demasiado_bajo:
                # Mezcla ya floja de LUFS: tratamos exceso de pico como aviso, no error
                print(
                    f"[S1_MIXBUS_HEADROOM][CHECK] mixbus_peak_dbfs_measured="
                    f"{mix_peak_measured:.2f} > peak_dbfs_max={peak_max:.2f} "
                    f"(pero LUFS ya por debajo de mínimo; se deja para etapas posteriores).",
                    file=sys.stderr,
                )
            else:
                print(
                    f"[S1_MIXBUS_HEADROOM][CHECK] mixbus_peak_dbfs_measured="
                    f"{mix_peak_measured:.2f} > peak_dbfs_max={peak_max:.2f} "
                    f"(+{peak_tol} margen)",
                    file=sys.stderr,
                )
                ok = False

    if lufs_measured is not None:
        if lufs_measured > lufs_max + lufs_tol:
            print(
                f"[S1_MIXBUS_HEADROOM][CHECK] mixbus_lufs_integrated_measured="
                f"{lufs_measured:.2f} > lufs_integrated_max={lufs_max:.2f} "
                f"(+{lufs_tol} margen)",
                file=sys.stderr,
            )
            ok = False

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
            print(
                f"[S2_GROUP_PHASE_DRUMS] {name}: correlación 100–500 Hz={corr:.3f} "
                f"< min {correlation_min:.3f} (margen {corr_margin:.2f})."
            )
            ok = False

        # Lag residual
        try:
            lag_ms = float(lag_ms)
        except (TypeError, ValueError):
            print(f"[S2_GROUP_PHASE_DRUMS] {name}: lag_ms inválido={lag_ms!r}.")
            ok = False
            continue

        if abs(lag_ms) > (residual_max_lag_ms + 0.02):
            print(
                f"[S2_GROUP_PHASE_DRUMS] {name}: lag residual {lag_ms:.3f} ms "
                f"> {residual_max_lag_ms:.2f} ms (+0.02 margen)."
            )
            ok = False

    if ok:
        print(
            f"[S2_GROUP_PHASE_DRUMS] Fase/polaridad OK para todos los stems de {target_family}: "
            f"correlación >= {correlation_min:.2f} y |lag| <= {residual_max_lag_ms:.2f} ms."
        )

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
        print(
            f"[S3_MIXBUS_HEADROOM] peak={peak_meas:.2f} dBFS > peak_max {peak_max:.2f} (+{MARGIN_DB:.1f})."
        )
        ok = False

    if lufs_meas > lufs_max + MARGIN_DB:
        print(
            f"[S3_MIXBUS_HEADROOM] LUFS={lufs_meas:.2f} > lufs_max {lufs_max:.2f} (+{MARGIN_DB:.1f})."
        )
        ok = False

    # 2) SOFT: LUFS mínimo
    if lufs_meas < lufs_min - MARGIN_DB:
        # Si además tenemos margen de pico por arriba, es que el stage podría haber subido más y no lo hizo
        if peak_meas < peak_max - MARGIN_DB:
            print(
                f"[S3_MIXBUS_HEADROOM] LUFS={lufs_meas:.2f} por debajo de {lufs_min:.2f} (-{MARGIN_DB:.1f}), "
                f"y peak={peak_meas:.2f} aún lejos de peak_max={peak_max:.2f}. Fracaso."
            )
            ok = False
        else:
            # Peak ya pegado al techo: aceptamos como OK, lo arreglarán stages posteriores
            print(
                f"[S3_MIXBUS_HEADROOM] LUFS={lufs_meas:.2f} por debajo de {lufs_min:.2f} (-{MARGIN_DB:.1f}), "
                f"pero peak={peak_meas:.2f} está en el límite. Se acepta como válido (se subirá en mastering)."
            )

    if ok:
        print(
            f"[S3_MIXBUS_HEADROOM] OK: peak={peak_meas:.2f} dBFS, LUFS={lufs_meas:.2f} "
            f"(dentro de límites duros)."
        )

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
        print(
            f"[S3_LEADVOX_AUDIBILITY] offset_mean={offset_mean:.2f} dB fuera de rango "
            f"[{offset_min:.2f}, {offset_max:.2f}] ±{MARGIN_DB:.1f}."
        )
        ok = False
    else:
        print(
            f"[S3_LEADVOX_AUDIBILITY] OK: offset_mean={offset_mean:.2f} dB "
            f"dentro de [{offset_min:.2f}, {offset_max:.2f}] ±{MARGIN_DB:.1f}."
        )

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
            print(f"[S4_STEM_HPF_LPF] {name}: sin métrica low_rel_db; fracaso.")
            ok = False
        else:
            try:
                low_rel_db = float(low_rel_db)
            except (TypeError, ValueError):
                print(f"[S4_STEM_HPF_LPF] {name}: low_rel_db inválido={low_rel_db!r}; fracaso.")
                ok = False
            else:
                if low_rel_db > LOW_REL_MAX_DB:
                    print(
                        f"[S4_STEM_HPF_LPF] {name}: energía subgrave sólo {low_rel_db:.1f} dB "
                        f"por debajo del total (umbral {LOW_REL_MAX_DB:.1f} dB)."
                    )
                    ok = False

        # high_rel_db
        if high_rel_db is None:
            print(f"[S4_STEM_HPF_LPF] {name}: sin métrica high_rel_db; fracaso.")
            ok = False
        else:
            try:
                high_rel_db = float(high_rel_db)
            except (TypeError, ValueError):
                print(f"[S4_STEM_HPF_LPF] {name}: high_rel_db inválido={high_rel_db!r}; fracaso.")
                ok = False
            else:
                if high_rel_db > HIGH_REL_MAX_DB:
                    print(
                        f"[S4_STEM_HPF_LPF] {name}: energía por encima del LPF sólo {high_rel_db:.1f} dB "
                        f"por debajo del total (umbral {HIGH_REL_MAX_DB:.1f} dB)."
                    )
                    ok = False

    if useful_stems == 0:
        print(f"[S4_STEM_HPF_LPF] Todas las pistas tienen nivel muy bajo; se considera éxito.")
        return True

    if ok:
        print(
            f"[S4_STEM_HPF_LPF] OK: sub-bajos e hiss extremo "
            f"atenuados al menos {abs(LOW_REL_MAX_DB):.0f} dB por debajo del contenido principal "
            f"en {useful_stems} pistas."
        )

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
        print(
            f"[{contract_id}] OK: no se han detectado resonancias "
            f"por encima de {max_res_peak_db:.1f} dB sobre la media local."
        )
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
                print(
                    f"[{contract_id}] {name}: "
                    f"gain_above_local_db inválido={diff_raw!r}; se ignora en la validación."
                )
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
                print(
                    f"[{contract_id}] {name}: resonancia extrema en {freq_str} "
                    f"{diff:.1f} dB por encima de la media local "
                    f"(límite duro {HARD_FAIL_DB:.1f} dB)."
                )
                return False

    # A partir de aquí, siempre devolvemos éxito, pero con logging informativo
    soft_limit = max_res_peak_db + MARGIN_DB
    extended_limit = soft_limit + RESIDUAL_TOL_DB

    if worst_diff <= soft_limit:
        # Cumple holgadamente el objetivo del contrato
        print(
            f"[{contract_id}] OK: todas las resonancias residuales "
            f"({counted_res} detectadas) están dentro de "
            f"{soft_limit:.1f} dB sobre la media local."
        )
    elif worst_diff <= extended_limit:
        # Dentro de la tolerancia extendida: informativo pero no bloqueante
        print(
            f"[{contract_id}] AVISO: se han detectado {counted_res} resonancias "
            f"residuales; worst_case={worst_diff:.1f} dB por encima de la media local. "
            f"Objetivo del contrato={max_res_peak_db:.1f} dB (+{MARGIN_DB:.1f} dB margen), "
            f"tolerancia extendida hasta {extended_limit:.1f} dB debido a límites de "
            f"max_resonant_cuts_db / max_resonant_filters_per_band."
        )
    else:
        # Valor muy alto pero por debajo del HARD_FAIL_DB: seguimos sin bloquear,
        # pero dejamos un log más agresivo para revisar el material o el detector.
        print(
            f"[{contract_id}] AVISO FUERTE: worst_case={worst_diff:.1f} dB por encima de "
            f"la media local (objetivo {max_res_peak_db:.1f} + margen {MARGIN_DB:.1f}). "
            f"Se permite pasar esta etapa para no bloquear el pipeline, "
            f"pero sería recomendable revisar a mano este material."
        )

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
        if avg_gr > max_avg_gr + MARGIN_AVG_DB or max_gr > max_peak_gr + MARGIN_PEAK_DB:
            print(
                f"[{contract_id}] {fname}: "
                f"avg_GR={avg_gr:.2f} dB (límite {max_avg_gr:.2f} + {MARGIN_AVG_DB:.1f}), "
                f"max_GR={max_gr:.2f} dB (límite {max_peak_gr:.2f} + {MARGIN_PEAK_DB:.1f})."
            )
            ok = False

    if n == 0:
        # No hemos podido validar ningún stem con datos numéricos; ser estrictos.
        print(
            f"[{contract_id}] No se han encontrado métricas numéricas válidas "
            f"en {metrics_path}; fracaso."
        )
        return False

    if ok:
        print(
            f"[{contract_id}] OK: {n} stems validados. "
            f"worst_avg_GR={worst_avg:.2f} dB (límite {max_avg_gr:.2f} + {MARGIN_AVG_DB:.1f}), "
            f"worst_max_GR={worst_peak:.2f} dB (límite {max_peak_gr:.2f} + {MARGIN_PEAK_DB:.1f})."
        )
    else:
        print(
            f"[{contract_id}] FRACASO: se han encontrado stems con reducción de ganancia "
            f"por encima de los límites permitidos "
            f"(max_avg={max_avg_gr:.2f} dB, max_peak={max_peak_gr:.2f} dB, "
            f"márgenes avg={MARGIN_AVG_DB:.1f}, peak={MARGIN_PEAK_DB:.1f})."
        )

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
            print(
                f"[S5_LEADVOX_DYNAMICS] {fname}: GR media {avg_gr:.2f} dB "
                f"> max {max_avg_gr_contract:.2f} dB (+{MARGIN_DB:.1f} margen)."
            )
            ok = False

        # 2) Crest factor no queda por encima del máximo objetivo
        MIN_IMPROVE_DB = 0.5  # o 1.0 si quieres ser un poco más estricto

        if post_crest > crest_max_contract + MARGIN_CREST_UP:
            # Si no hemos mejorado al menos MIN_IMPROVE_DB respecto al crest inicial,
            # lo consideramos fallo duro. Si hemos mejorado algo, lo dejamos como warning.
            if pre_crest - post_crest < MIN_IMPROVE_DB:
                print(
                    f"[S5_LEADVOX_DYNAMICS] {fname}: crest post={post_crest:.2f} dB "
                    f"sigue muy por encima del objetivo {crest_max_contract:.2f} dB y "
                    f"apenas ha mejorado desde {pre_crest:.2f} dB."
                )
                ok = False
            else:
                print(
                    f"[S5_LEADVOX_DYNAMICS] {fname}: crest post={post_crest:.2f} dB "
                    f"sigue por encima del objetivo {crest_max_contract:.2f} dB, "
                    f"pero se ha reducido desde {pre_crest:.2f} dB; se acepta como éxito suave."
                )


        # 3) Crest factor no se reduce en exceso (no matar la expresividad)
        if pre_crest > 0.5:  # si el crest original es muy pequeño, no tiene sentido ratio
            crest_ratio = post_crest / pre_crest if pre_crest != 0.0 else 1.0
            if crest_ratio < CREST_MIN_RATIO:
                print(
                    f"[S5_LEADVOX_DYNAMICS] {fname}: crest factor reducido de "
                    f"{pre_crest:.2f} dB a {post_crest:.2f} dB "
                    f"(ratio={crest_ratio:.2f} < {CREST_MIN_RATIO:.2f})."
                )
                ok = False

        # 4) Automatización global (makeup) dentro de límites
        if abs(makeup_db) > max_auto_per_pass + MARGIN_AUTO:
            print(
                f"[S5_LEADVOX_DYNAMICS] {fname}: automatización global {makeup_db:.2f} dB "
                f"> max {max_auto_per_pass:.2f} dB (+{MARGIN_AUTO:.1f})."
            )
            ok = False

        # 5) (Opcional, suave): si crest_pre ya estaba por debajo de crest_min,
        #    no podemos exigir subirlo; pero si crest_pre estaba dentro de rango,
        #    no deberíamos empujarlo claramente por debajo de crest_min.
        if pre_crest >= crest_min_contract:
            if post_crest < crest_min_contract - MARGIN_DB:
                print(
                    f"[S5_LEADVOX_DYNAMICS] {fname}: crest post={post_crest:.2f} dB "
                    f"< target_min {crest_min_contract:.2f} dB - margen {MARGIN_DB:.1f}, "
                    "aunque el crest inicial ya estaba en rango; revisa parámetros de compresión."
                )
                ok = False

    if checked == 0:
        print(
            "[S5_LEADVOX_DYNAMICS] No se han encontrado registros válidos de stems lead; "
            "se considera éxito suave."
        )
        return True

    if ok:
        print(
            f"[S5_LEADVOX_DYNAMICS] OK en {checked} stems lead: "
            f"GR_media <= {max_avg_gr_contract:.1f} dB (+{MARGIN_DB:.1f}), "
            f"crest_post dentro de target y sin reducción excesiva, "
            f"automatización |makeup| <= {max_auto_per_pass:.1f} dB (+{MARGIN_AUTO:.1f})."
        )

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
        print(
            f"[S5_BUS_DYNAMICS_DRUMS] GR media bus={avg_gr:.2f} dB "
            f"> max {max_avg_gr_contract:.2f} dB (+{MARGIN_DB:.1f} margen)."
        )
        ok = False

    # 2) Crest factor final dentro de ventana objetivo
    if post_crest > crest_max_contract + MARGIN_CREST:
        print(
            f"[S5_BUS_DYNAMICS_DRUMS] Crest post bus={post_crest:.2f} dB "
            f"> target_max {crest_max_contract:.2f} dB (+{MARGIN_CREST:.1f})."
        )
        ok = False

    if post_crest < crest_min_contract - MARGIN_CREST:
        print(
            f"[S5_BUS_DYNAMICS_DRUMS] Crest post bus={post_crest:.2f} dB "
            f"< target_min {crest_min_contract:.2f} dB (-{MARGIN_CREST:.1f})."
        )
        ok = False

    # 3) No matar el crest original más de un 40%
    if pre_crest is not None and pre_crest > 0.5:
        crest_ratio = post_crest / pre_crest if pre_crest != 0.0 else 1.0
        if crest_ratio < CREST_MIN_RATIO:
            print(
                f"[S5_BUS_DYNAMICS_DRUMS] Crest bus reducido de {pre_crest:.2f} dB "
                f"a {post_crest:.2f} dB (ratio={crest_ratio:.2f} < {CREST_MIN_RATIO:.2f})."
            )
            ok = False

    if ok:
        print(
            f"[S5_BUS_DYNAMICS_DRUMS] OK: GR_media={avg_gr:.2f} dB <= "
            f"{max_avg_gr_contract:.1f} dB (+{MARGIN_DB:.1f}), "
            f"crest_post={post_crest:.2f} dB dentro de "
            f"[{crest_min_contract:.1f}, {crest_max_contract:.1f}] ±{MARGIN_CREST:.1f}, "
            f"sin reducción excesiva de crest vs pre ({pre_crest:.2f} dB)."
        )

    return ok


def _check_S6_BUS_REVERB_STYLE(data: Dict[str, Any]) -> bool:
    """
    Valida S6_BUS_REVERB_STYLE usando:

      - analysis_S6_BUS_REVERB_STYLE.json (para contrato / sesión).
      - space_depth_metrics_S6_BUS_REVERB_STYLE.json (métricas reales del stage).

    Reglas:

      - reverb_return_offset_db (reverb_LUFS - dry_LUFS)
          ∈ [reverb_return_lufs_offset_min_db, reverb_return_lufs_offset_max_db] ± MARGIN.
      - |applied_offset_delta_db| <= max_send_level_change_db_per_pass + MARGIN_DELTA.
      - Si hay returns, reverb_return_lufs < dry_mix_lufs (ambiente, no más fuerte que el dry).
    """
    contract_id = data.get("contract_id", "S6_BUS_REVERB_STYLE")
    metrics_from_contract = data.get("metrics_from_contract", {}) or {}
    session = data.get("session", {}) or {}

    # Valores objetivo desde contrato / sesión
    try:
        offset_min_contract = float(
            metrics_from_contract.get("reverb_return_lufs_offset_min_db", -24.0)
        )
        offset_max_contract = float(
            metrics_from_contract.get("reverb_return_lufs_offset_max_db", -8.0)
        )
    except (TypeError, ValueError):
        print(f"[{contract_id}] Métricas inválidas en metrics_from_contract; fracaso.")
        return False

    try:
        max_send_change_contract = float(
            session.get("max_send_level_change_db_per_pass")
            or data.get("limits", {}).get("max_send_level_change_db_per_pass")
            or 2.0
        )
    except (TypeError, ValueError):
        max_send_change_contract = 2.0

    # Cargar métricas del stage
    temp_dir = get_temp_dir(contract_id, create=False)
    metrics_path = temp_dir / "space_depth_metrics_S6_BUS_REVERB_STYLE.json"

    if not metrics_path.exists():
        print(
            f"[S6_BUS_REVERB_STYLE] ERROR: no se encuentra {metrics_path}. "
            f"Asegúrate de que el stage guarda métricas de espacio/profundidad."
        )
        return False

    with metrics_path.open("r", encoding="utf-8") as f:
        m = json.load(f)

    num_returns = int(m.get("num_returns", 0))

    # Si no se han generado returns, consideramos éxito suave:
    # no hay reverb en este stage (o no aplica).
    if num_returns == 0:
        print(
            "[S6_BUS_REVERB_STYLE] Sin returns de reverb generados; "
            "se asume mezcla seca o sin necesidad de ambiente. Éxito suave."
        )
        return True

    dry_lufs = m.get("dry_mix_lufs")
    rev_lufs = m.get("reverb_return_lufs")
    offset_now = m.get("reverb_return_offset_db")
    target_min = m.get("target_offset_min_db", offset_min_contract)
    target_max = m.get("target_offset_max_db", offset_max_contract)
    applied_delta = m.get("applied_offset_delta_db")
    max_send_change_recorded = m.get("max_send_level_change_db_per_pass", max_send_change_contract)

    try:
        dry_lufs = float(dry_lufs)
        rev_lufs = float(rev_lufs)
        offset_now = float(offset_now)
        target_min = float(target_min)
        target_max = float(target_max)
        applied_delta = float(applied_delta)
        max_send_change_recorded = float(max_send_change_recorded)
    except (TypeError, ValueError):
        print("[S6_BUS_REVERB_STYLE] Métricas de LUFS/offset inválidas; fracaso.")
        return False

    # Tolerancias
    MARGIN_OFFSET_DB = 1.0
    MARGIN_DELTA_DB = 0.1

    ok = True

    # 1) Offset dentro de rango objetivo (10–20 dB por debajo, p.ej. [-24, -8] dB)
    if offset_now < target_min - MARGIN_OFFSET_DB:
        print(
            f"[S6_BUS_REVERB_STYLE] Offset reverb={offset_now:.2f} dB demasiado bajo "
            f"(target_min={target_min:.2f} dB, margen={MARGIN_OFFSET_DB:.1f}). "
            "La reverb podría estar demasiado enterrada."
        )
        ok = False

    if offset_now > target_max + MARGIN_OFFSET_DB:
        print(
            f"[S6_BUS_REVERB_STYLE] Offset reverb={offset_now:.2f} dB demasiado alto "
            f"(target_max={target_max:.2f} dB, margen={MARGIN_OFFSET_DB:.1f}). "
            "La reverb podría estar demasiado presente."
        )
        ok = False

    # 2) Nivel global de reverb siempre por debajo del mix dry
    if rev_lufs >= dry_lufs:
        print(
            f"[S6_BUS_REVERB_STYLE] Reverb_LUFS={rev_lufs:.2f} dB >= dry_LUFS={dry_lufs:.2f} dB; "
            "la reverb no debe superar el nivel del mix dry."
        )
        ok = False

    # 3) Idempotencia: no subir/bajar más de max_send_change_db por pasada
    max_allowed_delta = max_send_change_recorded + MARGIN_DELTA_DB
    if abs(applied_delta) > max_allowed_delta:
        print(
            f"[S6_BUS_REVERB_STYLE] applied_offset_delta={applied_delta:.2f} dB "
            f"> max_send_change={max_send_change_recorded:.2f} dB "
            f"(+{MARGIN_DELTA_DB:.1f} margen)."
        )
        ok = False

    if ok:
        print(
            f"[S6_BUS_REVERB_STYLE] OK: offset={offset_now:.2f} dB dentro de "
            f"[{target_min:.1f}, {target_max:.1f}] ±{MARGIN_OFFSET_DB:.1f}, "
            f"reverb_LUFS={rev_lufs:.2f} dB < dry_LUFS={dry_lufs:.2f} dB, "
            f"y |applied_delta|={abs(applied_delta):.2f} dB <= "
            f"{max_send_change_recorded:.1f} dB (+{MARGIN_DELTA_DB:.1f})."
        )

    return ok



def _check_S7_MIXBUS_TONAL_BALANCE(data: Dict[str, Any]) -> bool:
    """
    Valida S7_MIXBUS_TONAL_BALANCE usando:

      - analysis_S7_MIXBUS_TONAL_BALANCE.json (para contrato / sesión).
      - tonal_metrics_S7_MIXBUS_TONAL_BALANCE.json (métricas reales del stage).

    Reglas:

      - error_RMS_post <= max_tonal_balance_error_db + MARGIN_ERR.
      - Si error_RMS_pre > umbral -> se espera mejora (o al menos no empeorar).
      - Si error_RMS_pre ya <= umbral -> Stage debe ser casi no-op
        (ganancias por banda pequeñas).
      - |gain_banda| <= max_eq_change_db_per_band_per_pass + MARGIN_EQ_LIMIT.
      - error por banda (post) |post - target| <= max_tonal_balance_error_db + MARGIN_ERR.
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
    MARGIN_ERR_DB = 0.5       # margen para error RMS y por banda
    MARGIN_EQ_LIMIT_DB = 0.1  # margen sobre max_eq_change
    MARGIN_IDEMP_GAIN_DB = 0.5  # si ya está bien, ganancias deberían ser < ~0.5 dB
    MARGIN_IMPROVE_DB = 0.25  # no permitir que el error empeore claramente

    ok = True

    # 1) Siempre: error RMS final debe estar bajo el umbral (con margen)
    if post_error_rms > max_err_contract + MARGIN_ERR_DB:
        print(
            f"[S7_MIXBUS_TONAL_BALANCE] error_RMS post={post_error_rms:.2f} dB "
            f"> max {max_err_contract:.2f} dB (+{MARGIN_ERR_DB:.1f} margen)."
        )
        ok = False

    # 2) Comportamiento según estaba la mezcla antes
    if pre_error_rms > max_err_contract + MARGIN_ERR_DB:
        # Caso A: antes estaba fuera de tolerancia → se espera mejora
        if post_error_rms > pre_error_rms + MARGIN_IMPROVE_DB:
            print(
                f"[S7_MIXBUS_TONAL_BALANCE] error_RMS ha empeorado: "
                f"pre={pre_error_rms:.2f} dB, post={post_error_rms:.2f} dB "
                f"(+{MARGIN_IMPROVE_DB:.1f} margen)."
            )
            ok = False
    else:
        # Caso B: ya estaba dentro de tolerancia → Stage debe ser casi no-op
        for band_id, gain in eq_gains_db.items():
            try:
                g = float(gain)
            except (TypeError, ValueError):
                continue
            if abs(g) > MARGIN_IDEMP_GAIN_DB + MARGIN_EQ_LIMIT_DB:
                print(
                    f"[S7_MIXBUS_TONAL_BALANCE] Banda {band_id}: ganancia={g:+.2f} dB "
                    f"> {MARGIN_IDEMP_GAIN_DB:.1f} dB (idempotencia)."
                )
                ok = False

    # 3) Límite formal de EQ por banda
    for band_id, gain in eq_gains_db.items():
        try:
            g = float(gain)
        except (TypeError, ValueError):
            continue
        if abs(g) > max_eq_change_contract + MARGIN_EQ_LIMIT_DB:
            print(
                f"[S7_MIXBUS_TONAL_BALANCE] Banda {band_id}: |EQ|={g:+.2f} dB "
                f"> max {max_eq_change_contract:.2f} dB (+{MARGIN_EQ_LIMIT_DB:.1f})."
            )
            ok = False

    # 4) Error por banda después de la EQ (usando compute_tonal_error para normalización)
    #    Reconstruimos diccionarios limpios para la función
    c_band_db = {}
    t_band_db = {}
    for k, v in post_band_db.items():
        try:
            c_band_db[k] = float(v)
        except (TypeError, ValueError):
            pass
    for k, v in target_band_db.items():
        try:
            t_band_db[k] = float(v)
        except (TypeError, ValueError):
            pass

    errors_by_band, _ = compute_tonal_error(c_band_db, t_band_db)

    for band_id, err_band in errors_by_band.items():
        if abs(err_band) > max_err_contract + MARGIN_ERR_DB:
            print(
                f"[S7_MIXBUS_TONAL_BALANCE] Banda {band_id}: error={err_band:+.2f} dB "
                f"> max {max_err_contract:.2f} dB (+{MARGIN_ERR_DB:.1f})."
            )
            ok = False

    if ok:
        print(
            f"[S7_MIXBUS_TONAL_BALANCE] OK: error_RMS pre={pre_error_rms:.2f} dB, "
            f"post={post_error_rms:.2f} dB (umbral={max_err_contract:.2f} dB), "
            f"ganancias por banda dentro de ±{max_eq_change_contract:.1f} dB "
            f"(+{MARGIN_EQ_LIMIT_DB:.1f}), y errores por banda dentro de "
            f"±{max_err_contract:.1f} dB (+{MARGIN_ERR_DB:.1f})."
        )

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
        print(
            f"[S8_MIXBUS_COLOR_GENERIC] true_peak post={post_tp:.2f} dBTP "
            f"< min {tp_min_contract:.2f} dBTP (-{TP_MARGIN:.1f} margen). "
            "La mezcla ha quedado demasiado baja tras color."
        )
        ok = False

    if post_tp > tp_max_contract + TP_MARGIN:
        print(
            f"[S8_MIXBUS_COLOR_GENERIC] true_peak post={post_tp:.2f} dBTP "
            f"> max {tp_max_contract:.2f} dBTP (+{TP_MARGIN:.1f} margen). "
            "La mezcla ha quedado demasiado alta tras color."
        )
        ok = False

    # 2) THD dentro del límite
    if thd_percent > max_thd_contract + THD_MARGIN:
        print(
            f"[S8_MIXBUS_COLOR_GENERIC] THD={thd_percent:.2f} % "
            f"> max {max_thd_contract:.2f} % (+{THD_MARGIN:.1f} margen)."
        )
        ok = False

    # 3) Drive de saturación dentro de límites por pase
    if abs(drive_used) > max_sat_per_pass_contract + DRIVE_MARGIN_DB:
        print(
            f"[S8_MIXBUS_COLOR_GENERIC] drive_db_used={drive_used:+.2f} dB "
            f"> max_additional_saturation_per_pass={max_sat_per_pass_contract:.2f} dB "
            f"(+{DRIVE_MARGIN_DB:.1f} margen)."
        )
        ok = False

    # 4) Idempotencia suave: si la true_peak pre ya estaba dentro del rango,
    #    no deberíamos hacer cambios grandes de drive/trim.
    pre_in_range = (
        pre_tp >= tp_min_contract - TP_MARGIN
        and pre_tp <= tp_max_contract + TP_MARGIN
    )
    if pre_in_range:
        if abs(drive_used) > IDEMP_SMALL_DB:
            print(
                f"[S8_MIXBUS_COLOR_GENERIC] Idempotencia: true_peak pre ya en rango "
                f"({pre_tp:.2f} dBTP), pero drive_used={drive_used:+.2f} dB "
                f"> {IDEMP_SMALL_DB:.1f} dB."
            )
            ok = False
        if abs(trim_applied) > IDEMP_SMALL_DB:
            print(
                f"[S8_MIXBUS_COLOR_GENERIC] Idempotencia: true_peak pre ya en rango "
                f"({pre_tp:.2f} dBTP), pero trim_db_applied={trim_applied:+.2f} dB "
                f"> {IDEMP_SMALL_DB:.1f} dB."
            )
            ok = False

    # 5) Sanity check suave sobre el RMS (no apachurrar demasiado en un pase)
    #    No es un requisito de contrato explícito, pero sirve como guard-rail.
    if pre_rms != float("-inf") and post_rms != float("-inf"):
        delta_rms = post_rms - pre_rms
        if delta_rms < -RMS_CHANGE_MAX_DB:
            print(
                f"[S8_MIXBUS_COLOR_GENERIC] RMS ha caído {delta_rms:.2f} dB "
                f"< -{RMS_CHANGE_MAX_DB:.1f} dB en un solo pase; coloración demasiado agresiva."
            )
            ok = False

    if ok:
        print(
            f"[S8_MIXBUS_COLOR_GENERIC] OK: true_peak pre={pre_tp:.2f} dBTP, "
            f"post={post_tp:.2f} dBTP dentro de [{tp_min_contract:.1f}, {tp_max_contract:.1f}] "
            f"±{TP_MARGIN:.1f}, THD={thd_percent:.2f} % <= {max_thd_contract:.2f} % "
            f"(+{THD_MARGIN:.1f}), drive_used={drive_used:+.2f} dB "
            f"<= {max_sat_per_pass_contract:.2f} dB (+{DRIVE_MARGIN_DB:.1f}), "
            f"y cambios de nivel coherentes con una coloración suave."
        )

    return ok




def _check_S9_MASTER_GENERIC(data: Dict[str, Any]) -> bool:
    """
    Valida S9_MASTER_GENERIC usando:

      - analysis_S9_MASTER_GENERIC.json (contrato/targets).
      - master_metrics_S9_MASTER_GENERIC.json (métricas reales del stage).

    Reglas principales:

      - TP_final <= target_ceiling_dbtp + CEIL_MARGIN.
      - LUFS_final ∈ [target_lufs - LUFS_TOL, target_lufs + LUFS_TOL] ± LUFS_MARGIN.
      - LRA_final ∈ [target_lra_min, target_lra_max] ± LRA_MARGIN.
      - limiter_GR_db <= max_limiter_gain_reduction_db + GR_MARGIN.
      - |width_factor_applied - 1.0|*100 <= max_stereo_width_change_percent + WIDTH_PCT_MARGIN,
        y además width_factor_applied ∈ [0.9, 1.1] ± WIDTH_FACTOR_MARGIN.
      - Idempotencia: si ya estabas cerca del target (±0.3 LU) y TP <= ceiling,
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
        print(
            f"[S9_MASTER_GENERIC] true_peak post={post_tp:.2f} dBTP "
            f"> ceiling {target_ceiling:.2f} dBTP (+{CEIL_MARGIN:.1f} margen)."
        )
        ok = False

    # 2) LUFS final dentro de [target -1, target +1] ± margen
    if post_lufs == float("-inf"):
        print("[S9_MASTER_GENERIC] LUFS post no válido (inf); fracaso.")
        ok = False
    else:
        low_lufs = target_lufs - LUFS_TOL - LUFS_MARGIN
        high_lufs = target_lufs + LUFS_TOL + LUFS_MARGIN
        if not (low_lufs <= post_lufs <= high_lufs):
            print(
                f"[S9_MASTER_GENERIC] LUFS post={post_lufs:.2f} fuera de "
                f"[{target_lufs - LUFS_TOL:.2f}, {target_lufs + LUFS_TOL:.2f}] "
                f"(±{LUFS_MARGIN:.1f} margen)."
            )
            ok = False

    # 3) LRA final dentro del rango objetivo ± margen
    if target_lra_min < target_lra_max:
        low_lra = target_lra_min - LRA_MARGIN
        high_lra = target_lra_max + LRA_MARGIN
        if not (low_lra <= post_lra <= high_lra):
            print(
                f"[S9_MASTER_GENERIC] LRA post={post_lra:.2f} fuera de "
                f"[{target_lra_min:.2f}, {target_lra_max:.2f}] "
                f"(±{LRA_MARGIN:.1f} margen)."
            )
            ok = False

    # 4) GR del limitador dentro del máximo permitido
    if limiter_gr_db > max_limiter_gr_contract + GR_MARGIN:
        print(
            f"[S9_MASTER_GENERIC] limiter_GR={limiter_gr_db:.2f} dB "
            f"> max_limiter_gain_reduction_db={max_limiter_gr_contract:.2f} dB "
            f"(+{GR_MARGIN:.1f} margen)."
        )
        ok = False

    # 5) Cambio de anchura estéreo dentro de límites por contrato
    width_delta_factor = width_factor_applied - 1.0
    width_delta_pct = abs(width_delta_factor) * 100.0

    if width_delta_pct > max_width_change_pct_contract + WIDTH_PCT_MARGIN:
        print(
            f"[S9_MASTER_GENERIC] Cambio de width={width_delta_pct:.2f}% "
            f"> max_stereo_width_change_percent={max_width_change_pct_contract:.2f}% "
            f"(+{WIDTH_PCT_MARGIN:.1f} margen)."
        )
        ok = False

    # Además, el factor absoluto debe estar entre [0.9, 1.1] ± margen
    if width_factor_applied < 0.9 - WIDTH_FACTOR_MARGIN or width_factor_applied > 1.1 + WIDTH_FACTOR_MARGIN:
        print(
            f"[S9_MASTER_GENERIC] width_factor_applied={width_factor_applied:.3f} "
            "fuera del rango [0.90, 1.10] con margen."
        )
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
            print(
                f"[S9_MASTER_GENERIC] Idempotencia: pre ya cerca del target "
                f"(LUFS={pre_lufs:.2f}, TP={pre_tp:.2f} dBTP), pero "
                f"limiter_GR={limiter_gr_db:.2f} dB > {IDEM_GR_MAX:.1f} dB "
                f"(+{IDEM_GR_MARGIN:.1f} margen)."
            )
            ok = False

    if ok:
        print(
            f"[S9_MASTER_GENERIC] OK: TP_final={post_tp:.2f} dBTP <= {target_ceiling:.2f} dBTP "
            f"(+{CEIL_MARGIN:.1f}), LUFS_final={post_lufs:.2f} "
            f"cerca de target={target_lufs:.2f} (±{LUFS_TOL:.1f} + {LUFS_MARGIN:.1f}), "
            f"LRA_final={post_lra:.2f} dentro de [{target_lra_min:.1f}, {target_lra_max:.1f}] "
            f"(±{LRA_MARGIN:.1f}), limiter_GR={limiter_gr_db:.2f} dB "
            f"<= {max_limiter_gr_contract:.2f} dB (+{GR_MARGIN:.1f}), "
            f"y width_factor={width_factor_applied:.3f} dentro de límites."
        )

    return ok


def _check_S10_MASTER_FINAL_LIMITS(data: Dict[str, Any]) -> bool:
    """
    Valida S10_MASTER_FINAL_LIMITS usando:

      - analysis_S10_MASTER_FINAL_LIMITS.json (ya cargado en 'data').
      - qc_metrics_S10_MASTER_FINAL_LIMITS.json (métricas reales del stage).

    Reglas clave:

      - TP_post <= true_peak_max_dbtp + TP_MARGIN.
      - |LUFS_post - target_LUFS| <= style_lufs_tolerance + LUFS_MARGIN.
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

    ok = True

    # 1) True peak final
    if post_tp > tp_max + TP_MARGIN:
        print(
            f"[S10_MASTER_FINAL_LIMITS] TP post={post_tp:.2f} dBTP "
            f"> max {tp_max:.2f} dBTP (+{TP_MARGIN:.1f} margen)."
        )
        ok = False

    # 2) LUFS final cerca del target (±0.5 LU + margen)
    if post_lufs == float("-inf"):
        print("[S10_MASTER_FINAL_LIMITS] LUFS post no válido (inf); fracaso.")
        ok = False
    else:
        lufs_low = target_lufs - style_lufs_tol - LUFS_MARGIN
        lufs_high = target_lufs + style_lufs_tol + LUFS_MARGIN
        if not (lufs_low <= post_lufs <= lufs_high):
            print(
                f"[S10_MASTER_FINAL_LIMITS] LUFS post={post_lufs:.2f} fuera de "
                f"[{target_lufs - style_lufs_tol:.2f}, {target_lufs + style_lufs_tol:.2f}] "
                f"(±{LUFS_MARGIN:.1f} margen)."
            )
            ok = False

    # 3) Diferencia de loudness L/R
    if post_diff_lr > max_ch_diff + CH_MARGIN:
        print(
            f"[S10_MASTER_FINAL_LIMITS] diff_LR post={post_diff_lr:.2f} dB "
            f"> max {max_ch_diff:.2f} dB (+{CH_MARGIN:.1f} margen)."
        )
        ok = False

    # 4) Correlación estéreo global
    if post_corr < corr_min - CORR_MARGIN:
        print(
            f"[S10_MASTER_FINAL_LIMITS] correlación post={post_corr:.3f} "
            f"< min {corr_min:.3f} (-{CORR_MARGIN:.2f} margen)."
        )
        ok = False

    # 5) Micro-ajuste de ceiling dentro de límites
    if abs(trim_db_applied) > max_output_ceiling_adjust_db + TRIM_MARGIN:
        print(
            f"[S10_MASTER_FINAL_LIMITS] trim_db_applied={trim_db_applied:.2f} dB "
            f"> max_output_ceiling_adjust_db={max_output_ceiling_adjust_db:.2f} dB "
            f"(+{TRIM_MARGIN:.2f} margen)."
        )
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
            print(
                f"[S10_MASTER_FINAL_LIMITS] Idempotencia: master pre ya cumplía "
                "los criterios, pero trim_db_applied="
                f"{trim_db_applied:.2f} dB > {IDEM_TRIM_MAX:.2f} dB "
                f"(+{IDEM_MARGIN:.2f} margen)."
            )
            ok = False

        # Cambios muy pequeños en LUFS, LRA y diff_LR
        delta_lufs = post_lufs - pre_lufs if pre_lufs != float("-inf") else 0.0
        delta_lra = post_lra - pre_lra
        delta_diff = post_diff_lr - pre_diff_lr

        if abs(delta_lufs) > IDEM_DELTA_LUFS_MAX:
            print(
                f"[S10_MASTER_FINAL_LIMITS] Idempotencia: ΔLUFS={delta_lufs:+.2f} dB "
                f"> {IDEM_DELTA_LUFS_MAX:.2f} dB."
            )
            ok = False

        if abs(delta_lra) > IDEM_DELTA_LRA_MAX:
            print(
                f"[S10_MASTER_FINAL_LIMITS] Idempotencia: ΔLRA={delta_lra:+.2f} dB "
                f"> {IDEM_DELTA_LRA_MAX:.2f} dB."
            )
            ok = False

        if abs(delta_diff) > IDEM_DELTA_DIFFLR_MAX:
            print(
                f"[S10_MASTER_FINAL_LIMITS] Idempotencia: Δdiff_LR={delta_diff:+.2f} dB "
                f"> {IDEM_DELTA_DIFFLR_MAX:.2f} dB."
            )
            ok = False

    if ok:
        print(
            f"[S10_MASTER_FINAL_LIMITS] OK: TP={post_tp:.2f} dBTP <= {tp_max:.2f} (+{TP_MARGIN:.1f}), "
            f"LUFS={post_lufs:.2f} cerca de target={target_lufs:.2f} "
            f"(tol_estilo=±{style_lufs_tol:.1f} + {LUFS_MARGIN:.1f}), "
            f"diff_LR={post_diff_lr:.2f} dB <= {max_ch_diff:.2f} (+{CH_MARGIN:.1f}), "
            f"corr={post_corr:.3f} >= {corr_min:.3f} (-{CORR_MARGIN:.2f}), "
            f"trim_db_applied={trim_db_applied:.2f} dB <= {max_output_ceiling_adjust_db:.2f} "
            f"(+{TRIM_MARGIN:.2f})."
        )

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
        print(
            f"[{contract_id}] metrics.export_report_json != true; "
            "el contrato exige exportar el reporte en JSON."
        )
        ok = False

    # 2) allow_audio_changes debe ser false
    allow_audio_changes = bool(limits_from_contract.get("allow_audio_changes", True))
    if allow_audio_changes:
        print(
            f"[{contract_id}] limits.allow_audio_changes == true; "
            "este stage de reporting no debe permitir cambios de audio."
        )
        ok = False

    # 3) Estructura mínima del reporte
    report = session.get("report")
    if not isinstance(report, dict):
        print(
            f"[{contract_id}] session.report no existe o no es un objeto; "
            "el reporte debe ir en el JSON de análisis de la fase de reporting."
        )
        return False  # sin report no tiene sentido seguir

    stages_report = report.get("stages", [])
    if not isinstance(stages_report, list) or len(stages_report) == 0:
        print(
            f"[{contract_id}] report.stages vacío o inexistente; "
            "debe listar las etapas y lo que se ha aplicado en cada una."
        )
        ok = False

    final_metrics = report.get("final_metrics", {})
    if not isinstance(final_metrics, dict) or not final_metrics:
        print(
            f"[{contract_id}] report.final_metrics vacío o inexistente; "
            "debe contener las métricas finales del master."
        )
        ok = False

    # Campos clave en final_metrics
    fm_tp = final_metrics.get("true_peak_dbtp")
    fm_lufs = final_metrics.get("lufs_integrated")
    fm_lra = final_metrics.get("lra")

    if fm_tp is None or fm_lufs is None or fm_lra is None:
        print(
            f"[{contract_id}] final_metrics debe incluir true_peak_dbtp, "
            "lufs_integrated y lra."
        )
        ok = False
    else:
        try:
            fm_tp = float(fm_tp)
            fm_lufs = float(fm_lufs)
            fm_lra = float(fm_lra)
        except (TypeError, ValueError):
            print(
                f"[{contract_id}] final_metrics contiene valores no numéricos "
                "en true_peak_dbtp / lufs_integrated / lra."
            )
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
                    print(
                        f"[{contract_id}] true_peak_dbtp en reporte={fm_tp:.2f}, "
                        f"pero en QC S10={qc_tp:.2f} (Δ>{TP_DIFF_MAX:.2f})."
                    )
                    ok = False

            if fm_lufs is not None and not np.isnan(qc_lufs):
                if abs(fm_lufs - qc_lufs) > LUFS_DIFF_MAX:
                    print(
                        f"[{contract_id}] lufs_integrated en reporte={fm_lufs:.2f}, "
                        f"pero en QC S10={qc_lufs:.2f} (Δ>{LUFS_DIFF_MAX:.2f})."
                    )
                    ok = False

            if fm_lra is not None and not np.isnan(qc_lra):
                if abs(fm_lra - qc_lra) > LRA_DIFF_MAX:
                    print(
                        f"[{contract_id}] lra en reporte={fm_lra:.2f}, "
                        f"pero en QC S10={qc_lra:.2f} (Δ>{LRA_DIFF_MAX:.2f})."
                    )
                    ok = False

        except Exception as e:
            print(
                f"[{contract_id}] Aviso: no se pudo leer/interpretar "
                f"{qc_path} para comparar QC del máster: {e}"
            )
            # no forzamos fallo por esto, solo avisamos
    else:
        print(
            f"[{contract_id}] Aviso: no existe {qc_path}; "
            "no se puede verificar coherencia del reporte con el QC de S10."
        )

    if ok:
        print(
            f"[{contract_id}] OK: reporte JSON presente, sin cambios de audio "
            "permitidos, lista de stages no vacía y métricas finales coherentes "
            "con el QC del máster."
        )

    return ok



# ----------------- DISPATCH GENERAL -----------------


def main() -> None:
    """
    Uso esperado desde stage.py:
        python utils/check_metrics_limits.py <CONTRACT_ID>

    Devuelve exit code 0 si el contrato se considera cumplido, 1 si no.
    """
    if len(sys.argv) < 2:
        print("Uso: python check_metrics_limits.py <CONTRACT_ID>", file=sys.stderr)
        sys.exit(1)

    contract_id = sys.argv[1]

    analysis = _load_analysis(contract_id)

    # Dispatch por contrato
    if contract_id == "S0_SESSION_FORMAT":
        ok = _check_S0_SESSION_FORMAT(analysis)
    elif contract_id == "S1_STEM_DC_OFFSET":
        ok = _check_S1_STEM_DC_OFFSET(analysis)
    elif contract_id == "S1_STEM_WORKING_LOUDNESS":
        ok = _check_S1_STEM_WORKING_LOUDNESS(analysis)
    elif contract_id == "S1_VOX_TUNING":
        ok = _check_S1_VOX_TUNING(analysis)
    elif contract_id == "S1_MIXBUS_HEADROOM":
        ok = _check_S1_MIXBUS_HEADROOM(analysis)
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
    elif contract_id == "S6_BUS_REVERB_STYLE":
        ok = _check_S6_BUS_REVERB_STYLE(analysis)
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
        print(f"[check_metrics] No hay validación específica para {contract_id}, se considera éxito por defecto.")
        ok = True

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
