import json
from pathlib import Path
from typing import Any, Dict

from .models import FleetInputPayload
from .vehicle_classes import fuel_economy_key

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load_json(filename: str) -> Dict[str, Any]:
    return json.loads((_DATA_DIR / filename).read_text(encoding="utf-8"))


_GRID_FACTORS: Dict[str, Any] = _load_json("grid_factors.json")
_STATE_CROSSWALK: Dict[str, Any] = _load_json("state_crosswalk.json")
_BASELINES: Dict[str, Any] = _load_json("afleet_baselines.json")

LB_PER_METRIC_TON = 2204.62
KG_PER_LB = 0.45359237

# DISCLOSED CHANGE (assumptions_tracker integration): previously hardcoded
# module constants (0.20 / 0.05) with no param_id. Promoted to sourced
# afleet_baselines.json entries so they are traceable in the assumptions
# matrix; the numeric values are unchanged.
BEV_COLD_CLIMATE_PENALTY_PCT = _BASELINES["bev"]["climate_adjustment"][
    "cold_climate_efficiency_penalty_pct"
].get("default", 0.20)
H2_COLD_START_PENALTY_PCT = _BASELINES["hydrogen"]["climate_adjustment"][
    "cold_start_efficiency_penalty"
].get("default", 0.05)


class UnknownRegionError(Exception):
    pass


def get_subregion_for_state(state_prov: str) -> str:
    code = state_prov.strip().upper()
    entry = _STATE_CROSSWALK.get(code)
    if entry is None:
        raise UnknownRegionError(f"No state_crosswalk.json entry for region code '{code}'.")
    return entry.get("subregion") or entry.get("primary_subregion") or entry.get("grid_id")


def get_grid_factor_lb_per_mwh(state_prov: str) -> float:
    subregion = get_subregion_for_state(state_prov)
    factor_entry = _GRID_FACTORS.get(subregion)
    if factor_entry is None:
        raise UnknownRegionError(f"grid_factors.json has no entry for subregion '{subregion}'.")
    return factor_entry["co2e_lb_per_mwh"]


def get_bev_effective_kwh_per_mile(base_kwh_per_mile: float, cold_climate_flag: bool) -> float:
    if cold_climate_flag:
        return base_kwh_per_mile * (1.0 + BEV_COLD_CLIMATE_PENALTY_PCT)
    return base_kwh_per_mile


def get_hydrogen_effective_kg_per_mile(base_kg_per_mile: float, cold_climate_flag: bool) -> float:
    if cold_climate_flag:
        return base_kg_per_mile * (1.0 + H2_COLD_START_PENALTY_PCT)
    return base_kg_per_mile


def _calc_bev_emissions(inputs: FleetInputPayload) -> float:
    bev = _BASELINES["bev"]
    fleet = inputs.fleet

    base_kwh_per_mile = bev["fuel_economy"][fuel_economy_key(fleet.vehicle_type, "bev")]["default"]
    effective_kwh_per_mile = get_bev_effective_kwh_per_mile(
        base_kwh_per_mile, inputs.climate.cold_climate_flag
    )
    grid_factor_lb_per_mwh = get_grid_factor_lb_per_mwh(inputs.region.state_prov)
    grid_factor_lb_per_kwh = grid_factor_lb_per_mwh / 1000.0

    total_miles = fleet.vehicle_count * fleet.annual_mileage_per_vehicle
    total_kwh = total_miles * effective_kwh_per_mile
    total_lb_co2e = total_kwh * grid_factor_lb_per_kwh

    return total_lb_co2e / LB_PER_METRIC_TON


def _calc_hydrogen_emissions(inputs: FleetInputPayload) -> float:
    # The supply option (delivered liquid vs on-site electrolysis) is chosen on
    # cost in tco_calculator.py; emissions follow whichever option was chosen.
    from .tco_calculator import hydrogen_kg_per_mile, select_hydrogen_supply  # deferred: tco_calculator imports this module

    h2 = _BASELINES["hydrogen"]
    fleet = inputs.fleet
    total_miles = fleet.vehicle_count * fleet.annual_mileage_per_vehicle
    total_kg_h2 = total_miles * hydrogen_kg_per_mile(inputs)

    supply = select_hydrogen_supply(inputs)["chosen"]["supply"]
    if supply == "onsite_electrolysis":
        kwh_per_kg_h2 = h2["infrastructure"]["onsite_electrolysis"]["electrolyzer_system_kwh_per_kg"]["default"]
        grid_factor_lb_per_kwh = get_grid_factor_lb_per_mwh(inputs.region.state_prov) / 1000.0
        total_lb_co2e = total_kg_h2 * kwh_per_kg_h2 * grid_factor_lb_per_kwh
        return total_lb_co2e / LB_PER_METRIC_TON

    # Delivered liquid: SMR well-to-gate plus liquefaction electricity at the
    # US-average grid factor (the delivered-liquid price is NREL H2A, US-based).
    smr_kg_co2e_per_kg = h2["emissions"]["smr_well_to_gate_kg_co2e_per_kg"]["default"]
    liquefaction_kwh_per_kg = h2["emissions"]["liquefaction_kwh_per_kg"]["default"]
    us_avg_lb_per_kwh = _GRID_FACTORS["US_AVG"]["co2e_lb_per_mwh"] / 1000.0
    kg_co2e_per_kg_h2 = smr_kg_co2e_per_kg + liquefaction_kwh_per_kg * us_avg_lb_per_kwh * KG_PER_LB
    total_kg_co2e = total_kg_h2 * kg_co2e_per_kg_h2
    return total_kg_co2e / 1000.0


def _calc_diesel_emissions(inputs: FleetInputPayload) -> float:
    diesel = _BASELINES["diesel"]
    fleet = inputs.fleet

    mpg = diesel["fuel_economy"][fuel_economy_key(fleet.vehicle_type, "diesel")]["default"]
    lb_per_gallon = diesel["emissions"]["carbon_intensity_wtw"]["default"]

    total_miles = fleet.vehicle_count * fleet.annual_mileage_per_vehicle
    gallons = total_miles / mpg
    total_lb_co2e = gallons * lb_per_gallon

    return total_lb_co2e / LB_PER_METRIC_TON


def _calc_biodiesel_emissions(inputs: FleetInputPayload) -> float:
    biodiesel = _BASELINES["biodiesel"]
    fleet = inputs.fleet

    mpg = biodiesel["fuel_economy"][fuel_economy_key(fleet.vehicle_type, "biodiesel")]["default"]
    lb_per_gallon = biodiesel["emissions"]["carbon_intensity_wtw"]["default"]

    total_miles = fleet.vehicle_count * fleet.annual_mileage_per_vehicle
    gallons = total_miles / mpg
    total_lb_co2e = gallons * lb_per_gallon

    return total_lb_co2e / LB_PER_METRIC_TON


def _calc_cng_emissions(inputs: FleetInputPayload) -> float:
    cng = _BASELINES["cng"]
    fleet = inputs.fleet

    dge_per_mile = 1.0 / cng["fuel_economy"][fuel_economy_key(fleet.vehicle_type, "cng")]["default"]
    lb_per_dge = cng["emissions"]["carbon_intensity_wtw"]["default"]

    total_miles = fleet.vehicle_count * fleet.annual_mileage_per_vehicle
    dge_consumed = total_miles * dge_per_mile
    total_lb_co2e = dge_consumed * lb_per_dge

    return total_lb_co2e / LB_PER_METRIC_TON


_EMISSIONS_CALCULATORS = {
    "diesel": _calc_diesel_emissions,
    "biodiesel": _calc_biodiesel_emissions,
    "bev": _calc_bev_emissions,
    "hydrogen": _calc_hydrogen_emissions,
    "cng": _calc_cng_emissions,
}


def calculate_pathway_emissions(fuel_type: str, inputs: FleetInputPayload) -> float:
    if fuel_type not in _EMISSIONS_CALCULATORS:
        raise ValueError(f"Unknown fuel_type: {fuel_type}")
    return round(_EMISSIONS_CALCULATORS[fuel_type](inputs), 3)


def calculate_all_pathway_emissions(inputs: FleetInputPayload) -> Dict[str, float]:
    return {ft: calculate_pathway_emissions(ft, inputs) for ft in _EMISSIONS_CALCULATORS}
