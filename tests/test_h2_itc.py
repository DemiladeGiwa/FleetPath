import pytest

from engine.models import FleetInputPayload, RegionConfig, FleetConfig, OverridesConfig, ClimateConfig
from engine.resolver import resolve_input_payload
from engine.tco_calculator import (
    calculate_pathway_tco,
    hydrogen_daily_demand_kg,
    _BASELINES,
    _FX_RATES,
    electrolysis_carbon_intensity_kg_per_kg,
    _hydrogen_delivered_option,
    _hydrogen_onsite_option,
    _resolve_region,
)


def _payload(state_prov: str, owner_type: str = "school_district", vehicle_count: int = 10):
    return resolve_input_payload(FleetInputPayload(
        region=RegionConfig(state_prov=state_prov),
        fleet=FleetConfig(
            vehicle_type="school_bus_typeC",
            owner_type=owner_type,
            vehicle_count=vehicle_count,
            annual_mileage_per_vehicle=12000.0,
            lifecycle_years=12,
        ),
        overrides=OverridesConfig(),
        climate=ClimateConfig(cold_climate_flag=None),
    ))


def _onsite(state_prov: str, owner_type: str):
    inputs = _payload(state_prov, owner_type)
    region = _resolve_region(state_prov)
    is_canadian = region["country"] == "CA"
    return _hydrogen_onsite_option(inputs, region, region["code"], is_canadian)


def _expected_electrolyzer_capex_cad(state_prov: str) -> float:
    oe = _BASELINES["hydrogen"]["infrastructure"]["onsite_electrolysis"]
    kw = (
        hydrogen_daily_demand_kg(_payload(state_prov))
        * oe["electrolyzer_system_kwh_per_kg"]["default"]
        / 24.0
        / oe["electrolyzer_capacity_factor"]["default"]
    )
    return kw * oe["electrolyzer_installed_capex_usd_per_kw"]["default"] * oe["electrolyzer_small_scale_capex_multiplier"]["default"] * _FX_RATES["usd_to_cad"]["value"]


@pytest.mark.parametrize("province,expected_rate", [("QC", 0.40), ("BC", 0.25), ("ON", 0.15), ("NB", 0.0), ("AB", 0.0)])
def test_itc_tier_follows_modeled_carbon_intensity_for_corporate_owner(province, expected_rate):
    corp = _onsite(province, "private_contractor")
    public = _onsite(province, "school_district")
    # Same station and costs for both owners; the only difference is the credit,
    # and it is taken on electrolyzer capital only (not compression/storage/dispensing).
    assert corp["total_infra_capex"] == pytest.approx(public["total_infra_capex"] - corp["itc"])
    assert corp["itc"] == pytest.approx(_expected_electrolyzer_capex_cad(province) * expected_rate)
    if expected_rate == 0.0:
        assert corp["itc"] == 0.0
        assert "4.0 limit" in corp["itc_note"]
    else:
        assert corp["itc"] > 0
        assert f"{expected_rate:.0%}" in corp["itc_note"]


def test_itc_never_applies_to_public_owners():
    for owner in ("school_district", "municipality", "transit_agency"):
        option = _onsite("QC", owner)
        assert option["itc"] == 0.0
        assert "taxable Canadian corporations" in option["itc_note"]


def test_itc_never_applies_to_delivered_liquid_stations():
    inputs = _payload("QC", "private_contractor")
    assert _hydrogen_delivered_option(inputs, is_canadian=True)["itc"] == 0.0


def test_itc_not_applied_in_us():
    option = _onsite("CA", "private_contractor")  # California
    assert option["itc"] == 0.0
    assert option["itc_note"] is None


def test_modeled_ci_uses_57_5_kwh_per_kg_and_grid_factor():
    # QC: 57.5 kWh/kg x 2.8 lb/MWh -> 0.073 kg CO2e/kg H2
    assert electrolysis_carbon_intensity_kg_per_kg("QC") == pytest.approx(57.5 * 2.8 / 1000 * 0.45359237, rel=1e-9)


def test_pathway_reports_chosen_supply_and_its_credit():
    for owner in ("school_district", "private_contractor"):
        result = calculate_pathway_tco("hydrogen", _payload("QC", owner))
        assert result.hydrogen_supply in ("delivered_liquid", "onsite_electrolysis")
        assert any(note.startswith("Hydrogen supply:") for note in result.pathway_notes)
        assert any("Clean Hydrogen ITC" in note for note in result.pathway_notes)
        if owner == "school_district":
            assert result.incentives_applied == 0.0
