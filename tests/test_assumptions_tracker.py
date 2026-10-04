"""
Validates the Verifiable Assumptions Matrix: every baseline parameter
consulted for a pathway is traceable to a real param_id and source, and
user overrides are logged distinctly from baseline reads.
"""

from engine.models import FleetInputPayload, RegionConfig, FleetConfig, OverridesConfig, ClimateConfig
from api.main import run_calculation_pipeline


def _build_payload(state_prov="IN", diesel_price_gal=None, vehicle_count=10):
    return FleetInputPayload(
        region=RegionConfig(state_prov=state_prov),
        fleet=FleetConfig(
            vehicle_type="school_bus_typeC",
            vehicle_count=vehicle_count,
            annual_mileage_per_vehicle=12000,
            lifecycle_years=12,
        ),
        overrides=OverridesConfig(diesel_price_gal=diesel_price_gal),
        climate=ClimateConfig(cold_climate_flag=None),
    )


def test_no_overrides_every_assumption_has_real_source_and_is_not_override():
    output = run_calculation_pipeline(_build_payload())
    diesel = next(p for p in output.pathways if p.fuel_type == "diesel")

    assert len(diesel.assumptions) > 0
    for entry in diesel.assumptions:
        assert entry.is_override is False
        assert entry.source_agency
        assert entry.source_agency != "Unknown"


def test_diesel_price_override_produces_one_override_entry_and_changes_opex():
    baseline_output = run_calculation_pipeline(_build_payload(diesel_price_gal=None))
    override_output = run_calculation_pipeline(_build_payload(diesel_price_gal=5.00))

    baseline_diesel = next(p for p in baseline_output.pathways if p.fuel_type == "diesel")
    override_diesel = next(p for p in override_output.pathways if p.fuel_type == "diesel")

    override_entries = [a for a in override_diesel.assumptions if a.is_override]
    assert len(override_entries) == 1
    assert override_entries[0].param_id == "REF_PRICE_DIESEL_GAL"
    assert override_entries[0].value == 5.00

    # cross-check against the actual number, not just the flag: 10 vehicles
    # x 12,000 mi / 6.0 mpg x $5.00/gal = $100,000
    assert override_diesel.opex_fuel == 100000.0
    assert override_diesel.opex_fuel != baseline_diesel.opex_fuel


def test_no_placeholder_param_ids_across_all_pathways():
    output = run_calculation_pipeline(_build_payload(state_prov="QC", vehicle_count=101))

    all_entries = [a for p in output.pathways for a in p.assumptions]
    assert len(all_entries) > 0
    for entry in all_entries:
        assert entry.param_id.lower() not in ("unknown", "n/a", "none", "")
        assert not entry.param_id.lower().startswith("placeholder")
        assert entry.label.lower() not in ("unknown", "n/a", "none", "")


def test_biodiesel_cold_climate_multiplier_tracked_in_assumptions():
    # IN has cold_climate: true
    output = run_calculation_pipeline(_build_payload(state_prov="IN"))
    biodiesel = next(p for p in output.pathways if p.fuel_type == "biodiesel")
    multiplier_entry = next(
        (a for a in biodiesel.assumptions if a.param_id == "REF_BIODIESEL_COLD_MAINTENANCE_MULTIPLIER"),
        None,
    )
    assert multiplier_entry is not None
    assert multiplier_entry.value == 1.10
    assert multiplier_entry.source_agency == "Engineering estimate pending citation"
    assert multiplier_entry.is_override is False


def test_grid_factor_source_agency_uses_real_citation_not_generic_fallback():
    # DISCLOSED CHANGE (GRID_FACTOR_NB citation fix): locks in the regression
    # where _entry_from_leaf's source_agency fallback checked for a
    # "source_year" sibling key before accepting "source_agency" -- records
    # like grid_factors.json's Canadian entries, which bake the year into a
    # single pre-formatted source_agency string with no separate
    # source_year field, fell through to leaf.get("source", ...), a key
    # name that doesn't exist on these records, silently discarding the
    # real citation for the generic "FleetPath Engineering Assumption"
    # default. bev is used because it's the cheapest pathway that consults
    # get_grid_factor_lb_per_mwh (via emissions_calculator), which is the
    # only call path that reaches this class of entry.
    output = run_calculation_pipeline(_build_payload(state_prov="NB"))
    bev = next(p for p in output.pathways if p.fuel_type == "bev")

    grid_factor_entry = next(
        (a for a in bev.assumptions if a.param_id == "GRID_FACTOR_NB"),
        None,
    )
    assert grid_factor_entry is not None

    # Must be the real ECCC citation read from grid_factors.json, not the
    # generic fallback that silently swallowed it before this fix.
    assert grid_factor_entry.source_agency != "FleetPath Engineering Assumption"
    assert "ECCC" in grid_factor_entry.source_agency
    assert "National Inventory Report" in grid_factor_entry.source_agency
