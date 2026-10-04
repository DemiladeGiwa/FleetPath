import json
from pathlib import Path
from typing import Dict, Any

from .models import FleetInputPayload

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_CROSSWALK: Dict[str, Any] = json.loads((_DATA_DIR / "state_crosswalk.json").read_text(encoding="utf-8"))


def resolve_input_payload(payload: FleetInputPayload) -> FleetInputPayload:
    """
    Populates climate.cold_climate_flag from the geographic crosswalk
    when not explicitly set. Mutates and returns the input payload in place.
    """
    if payload.climate.cold_climate_flag is None:
        state_code = payload.region.state_prov.strip().upper()
        regional_info = _CROSSWALK.get(state_code, {})
        payload.climate.cold_climate_flag = regional_info.get("cold_climate", False)
    return payload