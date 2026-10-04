import pytest

from engine.models import FleetInputPayload, RegionConfig, FleetConfig, OverridesConfig, ClimateConfig
from engine.resolver import resolve_input_payload
from engine.tco_calculator import (
    calculate_all_pathways,
    hydrogen_daily_demand_kg,
    _calc_hydrogen_infrastructure,
    INFRA_LIFESPAN_YEARS,
    _BASELINES,
)


def _build_payload(vehicle_count, annual_mileage_per_vehicle=12000, lifecycle_years=12, state_prov="CA", vehicle_type="school_bus_typeC"):
    payload = FleetInputPayload(
        region=RegionConfig(state_prov=state_prov),
        fleet=FleetConfig(
            vehicle_type=vehicle_type,
            vehicle_count=vehicle_count,
            annual_mileage_per_vehicle=annual_mileage_per_vehicle,
            lifecycle_years=lifecycle_years,
        ),
        overrides=OverridesConfig(),
        climate=ClimateConfig(cold_climate_flag=None),
    )
    return resolve_input_payload(payload)


def test_school_bus_chargers_one_level2_per_bus_plus_dcfc_per_five():
    infra = _BASELINES["bev"]["infrastructure"]
    l2 = infra["school_bus_l2_hardware_usd"]["default"] + infra["school_bus_l2_install_usd"]["default"]
    dcfc = infra["dcfc_50_hardware_usd"]["default"] + infra["dcfc_50_make_ready_usd"]["default"]
    result_10 = calculate_all_pathways(_build_payload(vehicle_count=10))["bev"]
    result_11 = calculate_all_pathways(_build_payload(vehicle_count=11))["bev"]
    # 10 buses: 10 Level 2 + ceil(10/5)=2 DCFC; 11 buses: 11 Level 2 + ceil(11/5)=3 DCFC
    assert result_10.capex_infra_amortized == pytest.approx((10 * l2 + 2 * dcfc) / INFRA_LIFESPAN_YEARS, abs=0.01)
    assert result_11.capex_infra_amortized == pytest.approx((11 * l2 + 3 * dcfc) / INFRA_LIFESPAN_YEARS, abs=0.01)


def test_transit_buses_get_one_depot_charger_each():
    infra = _BASELINES["bev"]["infrastructure"]
    depot = infra["transit_depot_charger_hardware_usd"]["default"] + infra["transit_depot_charger_install_usd"]["default"]
    result = calculate_all_pathways(_build_payload(vehicle_count=7, vehicle_type="transit_short_haul"))["bev"]
    assert result.capex_infra_amortized == pytest.approx(7 * depot / INFRA_LIFESPAN_YEARS, abs=0.01)


def test_delivered_hydrogen_station_tier_steps_up_past_300kg_day():
    small_tier_capex = _BASELINES["engine_constants"]["hydrogen_capex_small_liquid_usd"]["value"]
    medium_tier_capex = _BASELINES["engine_constants"]["hydrogen_capex_medium_delivery_usd"]["value"]
    infra_101 = _calc_hydrogen_infrastructure(hydrogen_daily_demand_kg(_build_payload(vehicle_count=101)), is_canadian=False)
    infra_102 = _calc_hydrogen_infrastructure(hydrogen_daily_demand_kg(_build_payload(vehicle_count=102)), is_canadian=False)
    assert infra_101["station_tier"] == "small_liquid_delivery"
    assert infra_101["total_infra_capex"] == pytest.approx(small_tier_capex)
    assert infra_102["station_tier"] == "medium_delivery"
    assert infra_102["total_infra_capex"] == pytest.approx(medium_tier_capex)


def test_cng_station_type_steps_up_past_5_vehicles():
    time_fill_capex = _BASELINES["cng"]["infrastructure"]["time_fill_station_capex_usd"]["default"]
    fast_fill_capex = _BASELINES["cng"]["infrastructure"]["fast_fill_station_capex_usd"]["default"]
    result_5 = calculate_all_pathways(_build_payload(vehicle_count=5))["cng"]
    result_6 = calculate_all_pathways(_build_payload(vehicle_count=6))["cng"]
    assert result_5.capex_infra_amortized == pytest.approx(time_fill_capex / INFRA_LIFESPAN_YEARS, abs=0.01)
    assert result_6.capex_infra_amortized == pytest.approx(fast_fill_capex / INFRA_LIFESPAN_YEARS, abs=0.01)


def test_infrastructure_amortization_is_decoupled_from_fleet_lifecycle_years():
    result_10yr = calculate_all_pathways(_build_payload(vehicle_count=10, lifecycle_years=10))["bev"]
    result_15yr = calculate_all_pathways(_build_payload(vehicle_count=10, lifecycle_years=15))["bev"]
    assert result_10yr.capex_infra_amortized == pytest.approx(result_15yr.capex_infra_amortized, abs=0.001)
    assert result_10yr.capex_vehicle_amortized != pytest.approx(result_15yr.capex_vehicle_amortized, abs=0.001)
    assert result_10yr.capex_vehicle_amortized > result_15yr.capex_vehicle_amortized

