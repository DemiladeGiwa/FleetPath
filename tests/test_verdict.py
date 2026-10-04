import pytest

from api.main import _upfront_capital, build_advanced_dashboard, calculate_verdict, run_calculation_pipeline
from engine.models import FleetConfig, FleetInputPayload, OverridesConfig, PathwayOutputMetrics, RegionConfig
from engine.tco_calculator import calculate_all_pathways


PATHWAYS = ("diesel", "bev", "hydrogen", "cng", "biodiesel")


def _metric(
    fuel_type,
    tco_total,
    lifecycle_co2e_tons,
    vehicle_capex=1000.0,
    infra_capex=0.0,
    fuel_opex=50.0,
    maintenance_opex=50.0,
    incentives=0.0,
    currency="USD",
):
    # DISCLOSED CHANGE (pricing-bug remediation, phase 1): currency is now a
    # required field on PathwayOutputMetrics with no default. These fixtures
    # use arbitrary synthetic numbers, not real regional data, so "USD" is a
    # safe default -- every call in this file uses the same currency, which
    # satisfies calculate_verdict's mixed-currency guard (see
    # api/main.py::_assert_single_currency). Pass currency="CAD" explicitly
    # if a future test needs to exercise that guard directly.
    return PathwayOutputMetrics(
        fuel_type=fuel_type,
        currency=currency,
        tco_total=tco_total,
        capex_vehicle_amortized=vehicle_capex,
        capex_infra_amortized=infra_capex,
        opex_fuel=fuel_opex,
        opex_maintenance=maintenance_opex,
        incentives_applied=incentives,
        lifecycle_co2e_tons=lifecycle_co2e_tons,
        cold_climate_adjustment_applied=False,
    )


def test_diesel_wins_when_it_dominates_cost_and_carbon():
    pathways = {
        "diesel": _metric("diesel", 100.0, 10.0),
        "bev": _metric("bev", 200.0, 20.0),
        "hydrogen": _metric("hydrogen", 300.0, 30.0),
        "cng": _metric("cng", 250.0, 25.0),
        "biodiesel": _metric("biodiesel", 150.0, 15.0),
    }
    verdict = calculate_verdict(pathways, fleet_lifecycle_years=12)
    assert verdict.winner_pathway == "diesel"
    assert verdict.payback_years == 0.0


def test_equal_normalized_scores_use_canonical_pathway_order():
    pathways = {
        fuel_type: _metric(fuel_type, 100.0, 10.0)
        for fuel_type in reversed(PATHWAYS)
    }
    verdict = calculate_verdict(pathways, fleet_lifecycle_years=12)
    assert verdict.winner_pathway == "diesel"


def test_alt_pathway_without_lifecycle_recovery_has_no_payback():
    pathways = {
        "diesel": _metric("diesel", 100.0, 100.0, vehicle_capex=1000.0, fuel_opex=100.0),
        "bev": _metric(
            "bev",
            90.0,
            0.0,
            vehicle_capex=2000.0,
            fuel_opex=150.0,
        ),
        "hydrogen": _metric("hydrogen", 300.0, 300.0),
        "cng": _metric("cng", 250.0, 250.0),
        "biodiesel": _metric("biodiesel", 200.0, 200.0),
    }
    verdict = calculate_verdict(pathways, fleet_lifecycle_years=12)
    assert verdict.winner_pathway == "bev"
    assert verdict.payback_years is None


def test_winner_with_no_capital_premium_has_zero_payback():
    pathways = {
        "diesel": _metric("diesel", 100.0, 100.0, vehicle_capex=1000.0),
        "bev": _metric("bev", 90.0, 0.0, vehicle_capex=1000.0, fuel_opex=25.0),
        "hydrogen": _metric("hydrogen", 300.0, 300.0),
        "cng": _metric("cng", 250.0, 250.0),
        "biodiesel": _metric("biodiesel", 200.0, 200.0),
    }
    verdict = calculate_verdict(pathways, fleet_lifecycle_years=12)
    assert verdict.winner_pathway == "bev"
    assert verdict.payback_years == 0.0


def test_winner_with_payback_beyond_fleet_lifecycle_reports_none_and_discloses_premium():
    # DISCLOSED CHANGE (verdict-honesty fix): locks in the regression caught
    # against the live NB/CNG scenario -- a pathway can win on blended
    # cost/carbon utility (carbon-weighted) while (a) its computed
    # incremental-capex payback exceeds the fleet's own holding horizon, and
    # (b) its annualized tco_total is HIGHER than diesel's. Before this fix,
    # payback_years reported a number that implied recovery within the
    # asset's life even though the payback period (60 yrs here) blew past
    # fleet_lifecycle_years (12), and summary_text never disclosed that the
    # "winning" pathway cost more than diesel over its lifecycle.
    pathways = {
        "diesel": _metric(
            "diesel", 100.0, 100.0, vehicle_capex=1000.0, fuel_opex=100.0, maintenance_opex=100.0
        ),
        "cng": _metric(
            "cng", 110.0, 5.0, vehicle_capex=1500.0, fuel_opex=50.0, maintenance_opex=50.0
        ),
        "bev": _metric("bev", 300.0, 300.0),
        "hydrogen": _metric("hydrogen", 300.0, 300.0),
        "biodiesel": _metric("biodiesel", 250.0, 250.0),
    }
    verdict = calculate_verdict(pathways, fleet_lifecycle_years=12)

    assert verdict.winner_pathway == "cng"

    # incremental_capex=6000, annual_opex_savings=100 -> computed payback is
    # 60 years, which exceeds the 12-year fleet_lifecycle_years horizon, so
    # this must report None (not 60.0) -- a payback that doesn't fit inside
    # the asset's own service life is not a real payback.
    assert verdict.payback_years is None
    assert "no payback within holding period" in verdict.summary_text

    # cng's tco_total (110.0) exceeds diesel's (100.0) by 10.0 -- the winner
    # costs more on an annualized basis despite winning on blended
    # utility, and summary_text must disclose that explicitly rather than
    # let "wins" read as "cheaper."
    assert "$10 USD" in verdict.summary_text
    assert "higher than diesel" in verdict.summary_text
    assert "blended cost/carbon utility" in verdict.summary_text


def test_advanced_dashboard_cumulative_cost_axis_and_year_zero():
    lifecycle_years = 12
    inputs = FleetInputPayload(overrides=OverridesConfig(incentive_credits_usd=50000.0))
    pathways = calculate_all_pathways(inputs)
    dashboard = build_advanced_dashboard(pathways, lifecycle_years, user_grant=50000.0)
    bev_vector = next(item for item in dashboard.payback_vector if item.fuel_type == "bev")
    bev = pathways["bev"]
    # DISCLOSED CHANGE: year 0 subtracts only user_grant, not double-deducting statutory incentives
    expected_year_zero = _upfront_capital(bev, lifecycle_years) - 50000.0
    assert len(bev_vector.cumulative_cost_by_year) == lifecycle_years + 1
    assert bev_vector.cumulative_cost_by_year[0] == pytest.approx(expected_year_zero, abs=0.01)


def test_payback_vector_qc_scenario_and_invariant():
    # DISCLOSED CHANGE: regression test for 2a payback chart fix and payback invariant
    payload = FleetInputPayload(
        region=RegionConfig(state_prov="QC"),
        fleet=FleetConfig(
            vehicle_type="school_bus_typeC",
            vehicle_count=10,
            annual_mileage_per_vehicle=12000,
            lifecycle_years=12,
        ),
    )
    result = run_calculation_pipeline(payload)
    vectors = {v.fuel_type: v for v in result.advanced.payback_vector}

    bev_costs = vectors["bev"].cumulative_cost_by_year
    h2_costs = vectors["hydrogen"].cumulative_cost_by_year
    diesel_costs = vectors["diesel"].cumulative_cost_by_year

    # Regression values. Updated for v1.0: school-bus charger model (Level 2 per
    # bus + DCFC per 5), school-bus BEV energy 1.7 kWh/mi, Quebec cold_climate
    # true, and hydrogen modeled as the cheaper of delivered liquid / on-site
    # electrolysis with no ITC for a public owner.
    assert bev_costs[0] == pytest.approx(4941119, abs=100)
    assert bev_costs[12] == pytest.approx(5492670, abs=100)

    assert h2_costs[12] == pytest.approx(16715858, abs=100)

    # Acceptance criteria: Diesel unchanged
    assert diesel_costs[0] == pytest.approx(1929900.0, abs=0.01)
    assert diesel_costs[12] == pytest.approx(4645062.0, abs=0.01)

    # Invariant: when verdict.payback_years is None and no user grant,
    # winner's final cumulative cost must be >= diesel's final cumulative cost
    assert result.verdict.payback_years is None
    winner = result.verdict.winner_pathway
    assert vectors[winner].cumulative_cost_by_year[-1] >= diesel_costs[-1]


def test_qc_bev_scenario_with_200k_grant():
    # DISCLOSED CHANGE: test 2d - user grant reduces annualized tco by grant / lifecycle_years,
    # year 0 upfront capital reduces by grant, diesel unaffected, winner & payback_years unchanged.
    baseline_payload = FleetInputPayload(
        region=RegionConfig(state_prov="QC"),
        fleet=FleetConfig(
            vehicle_type="school_bus_typeC",
            vehicle_count=10,
            annual_mileage_per_vehicle=12000,
            lifecycle_years=12,
        ),
    )
    grant_payload = FleetInputPayload(
        region=RegionConfig(state_prov="QC"),
        fleet=FleetConfig(
            vehicle_type="school_bus_typeC",
            vehicle_count=10,
            annual_mileage_per_vehicle=12000,
            lifecycle_years=12,
        ),
        overrides=OverridesConfig(incentive_credits_usd=200000.0),
    )
    base_res = run_calculation_pipeline(baseline_payload)
    grant_res = run_calculation_pipeline(grant_payload)

    base_bev = next(p for p in base_res.pathways if p.fuel_type == "bev")
    grant_bev = next(p for p in grant_res.pathways if p.fuel_type == "bev")
    base_diesel = next(p for p in base_res.pathways if p.fuel_type == "diesel")
    grant_diesel = next(p for p in grant_res.pathways if p.fuel_type == "diesel")

    # tco_total falls by 16,666.67 +/- 0.01 (not 200,000)
    expected_delta = 200000.0 / 12.0  # 16,666.666...
    assert (base_bev.tco_total - grant_bev.tco_total) == pytest.approx(expected_delta, abs=0.01)

    # Diesel unchanged
    assert grant_diesel.tco_total == pytest.approx(base_diesel.tco_total, abs=0.01)

    # payback vector year 0 = upfront capital - 200,000
    bev_grant_vector = next(v for v in grant_res.advanced.payback_vector if v.fuel_type == "bev")
    upfront_cap = _upfront_capital(grant_bev, 12)
    assert bev_grant_vector.cumulative_cost_by_year[0] == pytest.approx(upfront_cap - 200000.0, abs=0.01)

    # Winner unchanged and payback_years still None
    assert grant_res.verdict.winner_pathway == base_res.verdict.winner_pathway
    assert grant_res.verdict.payback_years is None


def test_cold_climate_flag_only_on_pathways_with_a_modeled_adjustment():
    from engine.models import FleetInputPayload, RegionConfig
    from engine.resolver import resolve_input_payload
    from engine.tco_calculator import calculate_all_pathways

    cold = resolve_input_payload(FleetInputPayload(region=RegionConfig(state_prov="NB")))
    flags = {k: v.cold_climate_adjustment_applied for k, v in calculate_all_pathways(cold).items()}
    assert flags == {"diesel": False, "bev": True, "hydrogen": True, "cng": False, "biodiesel": True}

    warm = resolve_input_payload(FleetInputPayload(region=RegionConfig(state_prov="TX")))
    assert not any(v.cold_climate_adjustment_applied for v in calculate_all_pathways(warm).values())


def test_equal_capex_but_higher_opex_reports_no_payback():
    # B20 can win on carbon weight with the same vehicle capex as diesel but higher
    # fuel/maintenance cost. That is not a 0.0-year payback; it never pays back.
    pathways = {
        "diesel": _metric("diesel", 100.0, 100.0, vehicle_capex=1000.0, fuel_opex=100.0, maintenance_opex=100.0),
        "biodiesel": _metric("biodiesel", 102.0, 10.0, vehicle_capex=1000.0, fuel_opex=102.0, maintenance_opex=100.0),
        "bev": _metric("bev", 300.0, 300.0),
        "hydrogen": _metric("hydrogen", 300.0, 300.0),
        "cng": _metric("cng", 300.0, 300.0),
    }
    verdict = calculate_verdict(pathways, fleet_lifecycle_years=12)
    assert verdict.winner_pathway == "biodiesel"
    assert verdict.payback_years is None
    assert "no payback within holding period" in verdict.summary_text
