import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

with open(BASE_DIR / "profiles.json", "r", encoding="utf-8") as f:
    PROFILES = json.load(f)

with open(BASE_DIR / "stage_contracts.json", "r", encoding="utf-8") as f:
    CONTRACTS = json.load(f)


def get_contracts_for_stage(stage_id, instrument_id="*", style_id="*"):
    """Devuelve los contratos que aplican a una fase dada e instrumento/estilo."""
    stage = CONTRACTS["stages"][stage_id]
    contracts = []
    for c in stage["contracts"]:
        inst_match = c["instrument_id"] in ("*", instrument_id)
        style_match = c["style_id"] in ("*", style_id)
        if inst_match and style_match:
            contracts.append(c)
    return contracts


def get_instrument_profile(instrument_id):
    return PROFILES["instrument_profiles"][instrument_id]


def get_style_profile(style_id):
    return PROFILES["style_profiles"][style_id]


# Ejemplo: contratos de dinámica para voz principal en Flamenco/Rumba
stage_id = "S5_DYNAMICS"
instrument_id = "Lead_Vocal_Melodic"
style_id = "Flamenco_Rumba"

contracts = get_contracts_for_stage(stage_id, instrument_id, style_id)
instrument_profile = get_instrument_profile(instrument_id)
style_profile = get_style_profile(style_id)

print("Contratos S5 para Lead_Vocal_Melodic:", contracts)
print("Perfil instrumento:", instrument_profile)
print("Perfil estilo:", style_profile["mastering_targets"])
