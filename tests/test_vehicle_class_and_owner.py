import warnings

import pytest
from fastapi.testclient import TestClient

from api.main import app, run_calculation_pipeline
from engine.emissions_calculator import calculate_pathway_emissions, get_grid_factor_lb_per_mwh
from engine.models import FleetInputPayload, RegionConfig, FleetConfig, OverridesConfig, ClimateConfig
from engine.resolver import resolve_input_payload
from engine.tco_calculator import calculate_pathway_tco, hydrogen_kg_per_mile, select_hydrogen_supply, _BASELINES

warnings.filterwarnings("ignore", category=DeprecationWarning)
client = TestClient(app)


def _body(vehicle_type="school_bus_typeC", owner_type=None, state_prov="TX"):
    fleet = {"vehicle_type": vehicle_type, "vehicle_count": 10, "annual_mileage_per_vehicle": 12000, "lifecycle_years": 12}
    if owner_type is not None:
        fleet["owner_type"] = owner_type
    return {"region": {"state_prov": state_prov}, "fleet": fleet, "overrides": {}, "climate": {}}


def _payload(state_prov="TX", vehicle_type="school_bus_typeC", owner_type="school_district", cold=None):
    return resolve_input_payload(FleetInputPayload(
        region=RegionConfig(state_prov=state_prov),
        fleet=FleetConfig(vehicle_type=vehicle_type, owner_type=owner_type, vehicle_count=10,
                          annual_mileage_per_vehicle=12000.0, lifecycle_years=12),
        overrides=OverridesConfig(),
        climate=ClimateConfig(cold_climate_flag=cold),
    ))


@pytest.mark.parametrize("vehicle_type", ["utility_medium_duty", "not_a_real_type"])
def test_unsupported_vehicle_types_are_rejected(vehicle_type):
    assert client.post("/api/v1/calculate", json=_body(vehicle_type=vehicle_type)).status_code == 422


def test_invalid_owner_type_is_rejected():
    assert client.post("/api/v1/calculate", json=_body(owner_type="hedge_fund")).status_code == 422


def test_owner_type_defaults_to_school_district():
    assert FleetConfig().owner_type == "school_district"


def test_vehicle_class_changes_results():
    school = run_calculation_pipeline(FleetInputPayload(**_body("school_bus_typeC")))
    transit = run_calculation_pipeline(FleetInputPayload(**_body("transit_short_haul")))
    for s, t in zip(school.pathways, transit.pathways):
        assert s.fuel_type == t.fuel_type
        assert s.tco_total != t.tco_total


def test_transit_reads_transit_baselines():
    result = calculate_pathway_tco("diesel", _payload(vehicle_type="transit_short_haul"))
    capex = _BASELINES["diesel"]["capex"]["vehicle_transit_usd"]["default"]
    assert result.capex_vehicle_amortized == pytest.approx(capex * 10 / 12)


def test_school_bus_bev_uses_school_bus_energy_figure():
    tx = _payload("TX", cold=False)  # no cold penalty, US pricing
    expected_kwh = 10 * 12000 * _BASELINES["bev"]["fuel_economy"]["school_bus_kwh_per_mile"]["default"]
    lb = expected_kwh * get_grid_factor_lb_per_mwh("TX") / 1000.0
    assert calculate_pathway_emissions("bev", tx) == pytest.approx(lb / 2204.62, abs=0.001)


def test_quebec_pets_applies_to_school_buses_only():
    school = calculate_pathway_tco("bev", _payload("QC", "school_bus_typeC"))
    transit = calculate_pathway_tco("bev", _payload("QC", "transit_short_haul"))
    assert school.incentives_applied == pytest.approx(125000 * 10)
    assert transit.incentives_applied == 0.0
    assert not any("PETS" in n for n in transit.pathway_notes)


def test_hydrogen_emissions_follow_chosen_supply():
    for state in ("QC", "TX", "NB", "CA"):
        inputs = _payload(state)
        supply = select_hydrogen_supply(inputs)["chosen"]["supply"]
        kg = 10 * 12000 * hydrogen_kg_per_mile(inputs)
        if supply == "onsite_electrolysis":
            expected_t = kg * 57.5 * get_grid_factor_lb_per_mwh(state) / 1000.0 / 2204.62
        else:
            expected_t = kg * (9.4 + 11.0 * 770.9 / 1000.0 * 0.45359237) / 1000.0
        assert calculate_pathway_emissions("hydrogen", inputs) == pytest.approx(expected_t, abs=0.001)


def test_delivered_liquid_carbon_intensity_is_13_25():
    ci = 9.4 + 11.0 * 770.9 / 1000.0 * 0.45359237
    assert ci == pytest.approx(13.25, abs=0.01)


def test_cold_flag_only_on_adjusted_pathways_for_quebec_now_cold():
    result = run_calculation_pipeline(FleetInputPayload(**_body(state_prov="QC")))
    flags = {p.fuel_type: p.cold_climate_adjustment_applied for p in result.pathways}
    assert flags == {"diesel": False, "bev": True, "hydrogen": True, "cng": False, "biodiesel": True}


def test_health_reports_v1_0():
    assert client.get("/api/v1/health").json()["engine_version"] == "1.0"
