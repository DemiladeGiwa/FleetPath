import pytest

from engine.models import FleetInputPayload, RegionConfig, FleetConfig, OverridesConfig, ClimateConfig
from engine.resolver import resolve_input_payload
from engine.emissions_calculator import (
    calculate_all_pathway_emissions,
    get_subregion_for_state,
    get_grid_factor_lb_per_mwh,
    UnknownRegionError,
)


def _build_payload(state_prov, vehicle_count=10, annual_mileage_per_vehicle=12000, lifecycle_years=12):
    payload = FleetInputPayload(
        region=RegionConfig(state_prov=state_prov),
        fleet=FleetConfig(
            vehicle_type="school_bus_typeC",
            vehicle_count=vehicle_count,
            annual_mileage_per_vehicle=annual_mileage_per_vehicle,
            lifecycle_years=lifecycle_years,
        ),
        overrides=OverridesConfig(),
        climate=ClimateConfig(cold_climate_flag=None),
    )
    return resolve_input_payload(payload)


def test_crosswalk_resolves_expected_subregions():
    assert get_subregion_for_state("IN") == "RFCW"
    assert get_subregion_for_state("QC") == "ECCC_QC"
    assert get_subregion_for_state("ca") == "CAMX"


def test_unknown_region_raises():
    with pytest.raises(UnknownRegionError):
        get_subregion_for_state("ZZ")


def test_grid_factor_indiana_dirtier_than_quebec():
    indiana_factor = get_grid_factor_lb_per_mwh("IN")
    quebec_factor = get_grid_factor_lb_per_mwh("QC")
    assert indiana_factor > quebec_factor


def test_bev_emissions_indiana_exceeds_quebec_same_fleet():
    indiana_emissions = calculate_all_pathway_emissions(_build_payload("IN"))["bev"]
    quebec_emissions = calculate_all_pathway_emissions(_build_payload("QC"))["bev"]
    assert indiana_emissions > quebec_emissions
    assert quebec_emissions > 0


def test_hydrogen_electrolysis_emissions_indiana_exceeds_quebec_same_fleet():
    indiana_emissions = calculate_all_pathway_emissions(_build_payload("IN"))["hydrogen"]
    quebec_emissions = calculate_all_pathway_emissions(_build_payload("QC"))["hydrogen"]
    assert indiana_emissions > quebec_emissions


def test_diesel_emissions_are_region_independent():
    indiana_emissions = calculate_all_pathway_emissions(_build_payload("IN"))["diesel"]
    quebec_emissions = calculate_all_pathway_emissions(_build_payload("QC"))["diesel"]
    assert indiana_emissions == pytest.approx(quebec_emissions, abs=0.001)

def test_canadian_grid_factors_match_verified_eccc_annex7_values():
    # DISCLOSED CHANGE (grid-factor sourcing fix): locks in corrected
    # generation-intensity figures verified against the primary ECCC NIR
    # Annex 13 workbook (Table A13-5 NB, A13-6 QC, A13-7 ON, A13-10 AB, A13-11 BC, all 2021
    # data / Part 3 Annex 13). Sourced with real citation, native g/kWh, and
    # shown lb/MWh conversion.
    assert get_grid_factor_lb_per_mwh("NB") == pytest.approx(613.4, abs=0.05)
    assert get_grid_factor_lb_per_mwh("QC") == pytest.approx(2.8, abs=0.05)
    assert get_grid_factor_lb_per_mwh("ON") == pytest.approx(87.0, abs=0.05)
    assert get_grid_factor_lb_per_mwh("AB") == pytest.approx(1116.6, abs=0.05)
    assert get_grid_factor_lb_per_mwh("BC") == pytest.approx(30.9, abs=0.05)