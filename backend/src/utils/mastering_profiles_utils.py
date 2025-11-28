# C:\mix-master\backend\src\utils\mastering_profiles_utils.py

from __future__ import annotations

from typing import Dict, Any


def get_mastering_profile(style_preset: str | None) -> Dict[str, Any]:
    """
    Devuelve un perfil de mastering por estilo.

    Campos:
      - target_lufs_integrated: nivel de LUFS objetivo.
      - target_lra_min / max: rango de LRA deseado.
      - target_ceiling_dbtp: techo de true peak (por defecto -1 dBTP).
      - target_ms_width_factor: factor de anchura M/S objetivo (1.0 = neutro).

    NOTA: estos valores son aproximados y se pueden ajustar con experiencia real.
    """
    style = (style_preset or "default").lower()

    # Perfil base "pop genérico"
    profile: Dict[str, Any] = {
        "target_lufs_integrated": -11.0,
        "target_lra_min": 5.0,
        "target_lra_max": 10.0,
        "target_ceiling_dbtp": -1.0,
        "target_ms_width_factor": 1.0,  # sin widening extra
    }

    # Flamenco / Rumba: algo más dinámico y menos loud
    if "flamenco" in style or "rumba" in style:
        profile.update(
            {
                "target_lufs_integrated": -12.0,
                "target_lra_min": 6.0,
                "target_lra_max": 12.0,
                "target_ms_width_factor": 1.0,
            }
        )

    # Urbano / Trap / Reggaeton: algo más loud, dinámica moderada
    elif "urbano" in style or "trap" in style or "reggaeton" in style:
        profile.update(
            {
                "target_lufs_integrated": -9.0,
                "target_lra_min": 4.0,
                "target_lra_max": 8.0,
                "target_ms_width_factor": 1.05,
            }
        )

    # EDM / Club / House: más loud, LRA algo más baja, algo de width
    elif "edm" in style or "club" in style or "house" in style:
        profile.update(
            {
                "target_lufs_integrated": -7.5,
                "target_lra_min": 3.0,
                "target_lra_max": 7.0,
                "target_ms_width_factor": 1.05,
            }
        )

    # Acústico / Jazz: menos loud, más rango dinámico
    elif "acoustic" in style or "acústico" in style or "jazz" in style:
        profile.update(
            {
                "target_lufs_integrated": -14.0,
                "target_lra_min": 7.0,
                "target_lra_max": 12.0,
                "target_ms_width_factor": 1.0,
            }
        )

    # Otros estilos usan el perfil base

    return profile
