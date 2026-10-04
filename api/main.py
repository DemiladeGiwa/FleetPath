from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from io import BytesIO

from engine.models import (
    FleetInputPayload,
    EngineOutputPayload,
    PathwayOutputMetrics,
    VerdictConfig,
    AdvancedDashboardPayload,
    PaybackVectorItem,
)
from engine.resolver import resolve_input_payload
from engine.tco_calculator import calculate_pathway_tco, round_half_up, INFRA_LIFESPAN_YEARS
from engine.emissions_calculator import calculate_pathway_emissions, UnknownRegionError
from engine.assumptions_tracker import track_pathway_assumptions, get_static_assumptions, dedupe_assumptions
from api.report_generator import generate_fleet_report_pdf

app = FastAPI(title="FleetPath Core Engine API", version="1.0")
# DISCLOSED CHANGE: the Vite dev server may expose the UI as 127.0.0.1 rather
# than localhost; allow both explicit local origins so browser requests pass CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

PATHWAY_ORDER = ("diesel", "bev", "hydrogen", "cng", "biodiesel")

_PATHWAY_DISPLAY_NAMES = {
    "diesel": "Diesel",
    "bev": "Battery-Electric",
    "hydrogen": "Hydrogen Fuel Cell",
    "cng": "CNG",
    "biodiesel": "Biodiesel (B20)",
}

_DEFAULT_COST_WEIGHT = 0.60


# DISCLOSED CHANGE: corrected this docstring to match the current USD/CAD behavior.
class MixedCurrencyError(ValueError):
    """
    Raised when pathways being compared do not all resolve to the same
    currency, USD or CAD. This is a correctness guard, not a formatting
    concern: the verdict scorer's min-max normalization is only meaningful
    when every pathway's tco_total is in the same unit.
    """
    pass


def _assert_single_currency(pathways: Dict[str, PathwayOutputMetrics]) -> str:
    currencies = {p.currency for p in pathways.values()}
    if len(currencies) != 1:
        detail = ", ".join(f"{ft}={p.currency}" for ft, p in pathways.items())
        raise MixedCurrencyError(
            f"calculate_verdict received pathways in mixed currencies ({detail}); "
            "cannot rank tco_total across pathways denominated in different currencies."
        )
    return currencies.pop()


def _normalize_min_max_low_is_best(values: Dict[str, float]) -> Dict[str, float]:
    lowest = min(values.values())
    highest = max(values.values())
    if highest == lowest:
        return {k: 100.0 for k in values}
    return {k: 100.0 * (highest - v) / (highest - lowest) for k, v in values.items()}


def _build_summary_text(
    winner_fuel_type: str,
    payback_years: Optional[float],
    emissions_reduction_pct: float,
    cost_premium: float,
    currency: str,
    cost_weight: float,
) -> str:
    if winner_fuel_type == "diesel":
        return (
            "Diesel remains the lowest-cost, carbon-adjusted pathway for this fleet profile "
            "under current assumptions; no alternative pathway clears the cost-carbon utility threshold."
        )
    display_name = _PATHWAY_DISPLAY_NAMES[winner_fuel_type]
    if payback_years is not None:
        payback_str = f"an estimated {payback_years:.1f}-year payback"
    else:
        payback_str = "no payback within holding period"

    base = (
        f"{display_name} wins: {payback_str} versus the diesel "
        f"baseline, cutting annual CO2e emissions by {emissions_reduction_pct:.1f}% relative to diesel."
    )

    # DISCLOSED CHANGE (verdict-honesty fix): the utility scorer can select a
    # winner on blended cost+carbon utility even when that pathway's raw
    # annualized tco_total is higher than diesel's -- carbon weight alone can
    # carry it. Silently calling that pathway "wins" without surfacing the
    # premium contradicts the pathway comparison matrix sitting right below
    # it in both the UI and the PDF. Disclose the premium explicitly rather
    # than let the reader infer "wins" means "cheaper."
    # DISCLOSED CHANGE: refer to "annualized cost" rather than "lifetime cost over the fleet lifecycle"
    if cost_premium > 0:
        base += (
            f" Note: {display_name}'s annualized cost is {_fmt_money(cost_premium, currency)} higher than "
            "diesel's -- this pathway is favored on blended cost/carbon utility, "
            "not on lowest raw cost."
        )
    if abs(cost_weight - _DEFAULT_COST_WEIGHT) > 1e-6:
        weight_pct = round(cost_weight * 100)
        base += f" (Verdict computed with a user-adjusted weighting: {weight_pct}% cost priority / {100 - weight_pct}% carbon priority.)"
    return base


def _fmt_money(value: float, currency: str) -> str:
    return f"${round_half_up(value):,} {currency}"


def _upfront_capital(metric: PathwayOutputMetrics, fleet_lifecycle_years: int) -> float:
    return (metric.capex_vehicle_amortized * fleet_lifecycle_years) + (
        metric.capex_infra_amortized * INFRA_LIFESPAN_YEARS
    )


def _compute_verdict(
    pathways: Dict[str, PathwayOutputMetrics],
    fleet_lifecycle_years: int,
    cost_carbon_weight: Optional[float] = None,
    user_grant: float = 0.0,
) -> VerdictConfig:
    currency = _assert_single_currency(pathways)
    cost_weight = cost_carbon_weight if cost_carbon_weight is not None else _DEFAULT_COST_WEIGHT
    carbon_weight = 1.0 - cost_weight

    cost_values = {ft: p.tco_total for ft, p in pathways.items()}
    carbon_values = {ft: p.lifecycle_co2e_tons for ft, p in pathways.items()}

    cost_scores = _normalize_min_max_low_is_best(cost_values)
    carbon_scores = _normalize_min_max_low_is_best(carbon_values)

    utility_scores = {}
    for fuel_type in pathways:
        weighted_cost_score = cost_scores[fuel_type] * cost_weight
        weighted_carbon_score = carbon_scores[fuel_type] * carbon_weight
        utility_scores[fuel_type] = weighted_cost_score + weighted_carbon_score
    winner = max(PATHWAY_ORDER, key=lambda ft: utility_scores.get(ft, -float("inf")))

    diesel = pathways["diesel"]
    winner_result = pathways[winner]
    cost_premium = winner_result.tco_total - diesel.tco_total  # positive means winner costs MORE than diesel lifecycle-total

    if winner == "diesel":
        payback_years: Optional[float] = 0.0
        emissions_reduction_pct = 0.0
    else:
        winner_vehicle_capex_total = winner_result.capex_vehicle_amortized * fleet_lifecycle_years
        winner_infra_capex_total = winner_result.capex_infra_amortized * INFRA_LIFESPAN_YEARS
        diesel_vehicle_capex_total = diesel.capex_vehicle_amortized * fleet_lifecycle_years

        # DISCLOSED CHANGE: treat incentive_credits_usd (user_grant) as a reduction of upfront capital in incremental_capex
        winner_total_capex = (winner_vehicle_capex_total + winner_infra_capex_total) - user_grant
        incremental_capex = winner_total_capex - diesel_vehicle_capex_total
        diesel_annual_opex = diesel.opex_fuel + diesel.opex_maintenance
        winner_annual_opex = winner_result.opex_fuel + winner_result.opex_maintenance
        annual_opex_savings = diesel_annual_opex - winner_annual_opex

        if incremental_capex <= 0:
            # No extra capital to recover. That's an immediate payback only if the
            # winner also costs no more to run; if its annual opex is higher, it
            # never comes out ahead of diesel, so there is no payback to report.
            payback_years = 0.0 if annual_opex_savings >= 0 else None
        elif annual_opex_savings > 0:
            # DISCLOSED CHANGE (payback-horizon fix): incremental_capex /
            # annual_opex_savings alone can produce a number that LOOKS like
            # a valid payback but falls outside the fleet's own holding
            # horizon -- meaning the capex is never actually recouped within
            # the asset's service life. A payback figure that exceeds
            # fleet_lifecycle_years is not a real payback; report None
            # (renders as "no payback within holding period") so
            # the summary text doesn't claim a payback that can't happen
            # inside the vehicle's own lifespan.
            computed_payback = incremental_capex / annual_opex_savings
            if computed_payback > fleet_lifecycle_years:
                payback_years = None
            else:
                payback_years = round(computed_payback, 1)
        else:
            payback_years = None

        if diesel.lifecycle_co2e_tons > 0:
            emissions_reduction_pct = round(
                (diesel.lifecycle_co2e_tons - winner_result.lifecycle_co2e_tons)
                / diesel.lifecycle_co2e_tons
                * 100,
                1,
            )
        else:
            emissions_reduction_pct = 0.0

    return VerdictConfig(
        winner_pathway=winner,
        summary_text=_build_summary_text(
            winner,
            payback_years,
            emissions_reduction_pct,
            cost_premium,
            currency,
            cost_weight,
        ),
        payback_years=payback_years,
        emissions_reduction_pct=emissions_reduction_pct,
    )


calculate_verdict = _compute_verdict


def build_advanced_dashboard(
    pathways: Dict[str, PathwayOutputMetrics],
    fleet_lifecycle_years: int,
    user_grant: float = 0.0,
) -> AdvancedDashboardPayload:
    currency = _assert_single_currency(pathways)

    years_axis = list(range(fleet_lifecycle_years + 1))
    vectors = []
    for ft, metric in pathways.items():
        # DISCLOSED CHANGE: year 0 upfront capital already reflects statutory PETS/ITC
        # netted before amortization. Only subtract non-netted user grants for non-diesel pathways.
        grant_deduction = 0.0 if ft == "diesel" else user_grant
        year_0 = _upfront_capital(metric, fleet_lifecycle_years) - grant_deduction
        annual_opex = metric.opex_fuel + metric.opex_maintenance
        costs = [round(year_0 + t * annual_opex, 2) for t in range(fleet_lifecycle_years + 1)]
        vectors.append(PaybackVectorItem(fuel_type=ft, currency=currency, cumulative_cost_by_year=costs))
    return AdvancedDashboardPayload(
        tco_composition=list(pathways.values()),
        payback_vector=vectors,
        payback_vector_years_axis=years_axis,
    )


def run_calculation_pipeline(payload: FleetInputPayload) -> EngineOutputPayload:
    """
    Single source of truth for resolve -> calculate -> score. Both
    /api/v1/calculate and /api/v1/report call this rather than each
    running their own copy of the pipeline.

    Loops per fuel_type (rather than the bulk calculate_all_pathways/
    calculate_all_pathway_emissions helpers) so each pathway's TCO and
    emissions calculation runs inside its own track_pathway_assumptions()
    scope -- this is what lets PathwayOutputMetrics.assumptions reflect
    exactly the baseline reads and overrides consulted for that pathway.
    """
    resolved = resolve_input_payload(payload)

    pathways: Dict[str, PathwayOutputMetrics] = {}
    for fuel_type in _PATHWAY_DISPLAY_NAMES:
        with track_pathway_assumptions() as tracked_entries:
            result = calculate_pathway_tco(fuel_type, resolved)
            result.lifecycle_co2e_tons = calculate_pathway_emissions(fuel_type, resolved)
        static_entries = get_static_assumptions(fuel_type, resolved)
        result.assumptions = dedupe_assumptions(tracked_entries + static_entries)
        pathways[fuel_type] = result

    user_grant = resolved.overrides.incentive_credits_usd or 0.0
    verdict = _compute_verdict(
        pathways,
        resolved.fleet.lifecycle_years,
        resolved.overrides.cost_carbon_weight,
        user_grant=user_grant,
    )
    advanced = build_advanced_dashboard(
        pathways, resolved.fleet.lifecycle_years, user_grant=user_grant
    )

    return EngineOutputPayload(verdict=verdict, pathways=list(pathways.values()), advanced=advanced)


@app.get("/api/v1/health")
def health_check():
    return {"status": "operational", "engine_version": "1.0"}


@app.post("/api/v1/calculate", response_model=EngineOutputPayload)
def calculate_fleet_pathways(payload: FleetInputPayload):
    try:
        return run_calculation_pipeline(payload)
    except UnknownRegionError as e:  # DISCLOSED CHANGE: return 400 for unknown region codes
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/report")
def generate_fleet_report(payload: FleetInputPayload):
    try:
        engine_output = run_calculation_pipeline(payload)
        pdf_bytes = generate_fleet_report_pdf(payload, engine_output)
        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=fleetpath_report.pdf"},
        )
    except UnknownRegionError as e:  # DISCLOSED CHANGE: return 400 for unknown region codes
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
