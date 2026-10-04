"""
FleetPath — Verifiable Assumptions Matrix (PRD §7)
Read-only exposition layer over the baseline/grid-factor lookups already
consulted by tco_calculator.py and emissions_calculator.py. Does not
perform or alter any calculation — it observes dict reads during a single
pathway's calculation and separately enumerates the small set of
engine-constant lookups that are cached as module-level scalars at import
time and therefore cannot be observed live (see get_static_assumptions).
"""

import contextvars
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import AssumptionEntry, FleetInputPayload

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_FX_RATES_RAW: Dict[str, Any] = json.loads((_DATA_DIR / "fx_rates.json").read_text(encoding="utf-8"))

# Leaf-value key names used across the three JSON files. Every leaf dict
# that carries a "param_id" uses exactly one of these as its value key.
_VALUE_KEYS = {"default", "value", "co2e_lb_per_mwh"}

_current_tracker: "contextvars.ContextVar[Optional[List[AssumptionEntry]]]" = contextvars.ContextVar(
    "_current_tracker", default=None
)

PARAM_LABELS: Dict[str, str] = {
    "REF_CAPEX_VEH_DIESEL_BUS": "Diesel Bus Purchase Price",
    "REF_MAINT_CPM_DIESEL": "Diesel Maintenance Cost per Mile",
    "REF_FE_DIESEL_BUS_MPG": "Diesel Fuel Economy",
    "REF_CI_DIESEL_GHG": "Diesel Well-to-Wheel Carbon Intensity",
    "REF_PRICE_DIESEL_GAL": "Diesel Reference Price",
    "REF_CAPEX_VEH_BEV_BUS": "Battery-Electric Bus Purchase Price",
    "REF_MAINT_CPM_BEV": "BEV Maintenance Cost per Mile",
    "REF_FE_BEV_BUS_KWH": "BEV Energy Consumption",
    "REF_INFRA_BEV_DCFC_RATIO": "School Bus DC Fast Charger Ratio",
    "REF_INFRA_BEV_L2_HW": "School Bus Level 2 Charger Hardware Cost",
    "REF_INFRA_BEV_L2_INSTALL": "School Bus Level 2 Charger Installation Cost",
    "REF_INFRA_BEV_TRANSIT_DEPOT_HW": "Transit Depot Charger Hardware Cost",
    "REF_INFRA_BEV_TRANSIT_DEPOT_INSTALL": "Transit Depot Charger Installation Cost",
    "REF_INFRA_BEV_TRANSIT_RATIO": "Transit Depot Chargers per Bus",
    "REF_FE_BEV_SCHOOLBUS_KWH": "BEV School Bus Energy Consumption",
    "REF_CAPEX_VEH_DIESEL_TRANSIT": "Diesel Transit Bus Purchase Price",
    "REF_MAINT_CPM_DIESEL_TRANSIT": "Diesel Transit Maintenance Cost per Mile",
    "REF_FE_DIESEL_TRANSIT_MPG": "Diesel Transit Fuel Economy",
    "REF_CAPEX_VEH_B20_TRANSIT": "Biodiesel (B20) Transit Bus Purchase Price",
    "REF_MAINT_CPM_B20_TRANSIT": "Biodiesel (B20) Transit Maintenance Cost per Mile",
    "REF_FE_B20_TRANSIT_MPG": "Biodiesel (B20) Transit Fuel Economy",
    "REF_CAPEX_VEH_BEV_TRANSIT": "Battery-Electric Transit Bus Purchase Price",
    "REF_MAINT_CPM_BEV_TRANSIT": "BEV Transit Maintenance Cost per Mile",
    "REF_CAPEX_VEH_H2FC_TRANSIT": "Hydrogen Fuel Cell Transit Bus Purchase Price",
    "REF_MAINT_CPM_H2FC_TRANSIT": "Hydrogen Transit Maintenance Cost per Mile",
    "REF_FE_H2FC_TRANSIT_KG": "Hydrogen Transit Fuel Consumption",
    "REF_CAPEX_VEH_CNG_TRANSIT": "CNG Transit Bus Purchase Price",
    "REF_MAINT_CPM_CNG_TRANSIT": "CNG Transit Maintenance Cost per Mile",
    "REF_FE_CNG_TRANSIT_MPDGE": "CNG Transit Fuel Economy",
    "REF_INFRA_H2_ELECTROLYZER_CAPEX_KW": "Electrolyzer Installed Capital Cost",
    "REF_INFRA_H2_ELECTROLYZER_SMALL_SCALE": "Electrolyzer Small-Station Cost Multiplier",
    "REF_H2_ELECTROLYSIS_KWH_PER_KG": "Electrolysis System Electricity Use",
    "REF_H2_ELECTROLYZER_FIXED_OM": "Electrolyzer Fixed O&M Rate",
    "REF_H2_STACK_REPLACEMENT": "Electrolyzer Stack Replacement Cost",
    "REF_H2_STACK_INTERVAL": "Electrolyzer Stack Replacement Interval",
    "REF_H2_ELECTROLYZER_CF": "Electrolyzer Capacity Factor",
    "REF_INFRA_H2_ONSITE_CSD_CAPEX": "On-Site Station Compression, Storage & Dispensing CapEx",
    "REF_INFRA_H2_ONSITE_MIN_CAPACITY": "On-Site Station Minimum Design Capacity",
    "REF_CI_H2_SMR_WTG": "SMR Hydrogen Well-to-Gate Carbon Intensity",
    "REF_H2_LIQUEFACTION_KWH_PER_KG": "Hydrogen Liquefaction Electricity Use",
    "REF_INCENTIVE_CA_H2_ITC_TIER_1": "Clean Hydrogen ITC Rate, CI < 0.75",
    "REF_INCENTIVE_CA_H2_ITC_TIER_2": "Clean Hydrogen ITC Rate, CI 0.75 to < 2",
    "REF_INCENTIVE_CA_H2_ITC_TIER_3": "Clean Hydrogen ITC Rate, CI 2 to < 4",
    "GRID_FACTOR_US_AVG": "U.S. Average Grid Emissions Factor",
    "REF_INFRA_BEV_DCFC_50_HW": "BEV Charger Hardware Cost",
    "REF_INFRA_BEV_DCFC_50_MR": "BEV Charger Make-Ready (Site) Cost",
    "REF_INFRA_BEV_MAINT_PCT": "BEV Charger Annual Maintenance Rate",
    "REF_INFRA_BEV_WARRANT_PCT": "BEV Charger Warranty Cost Rate",
    "REF_INFRA_BEV_COMMS": "BEV Charger Annual Communications Cost",
    "REF_PRICE_ELEC_KWH": "Electricity Reference Rate",
    "REF_CLIMATE_BEV_COLD_PENALTY": "BEV Cold-Climate Consumption Penalty",
    "REF_CAPEX_VEH_H2FC_BUS": "Hydrogen Fuel Cell Bus Purchase Price",
    "REF_MAINT_CPM_H2FC": "Hydrogen Bus Maintenance Cost per Mile",
    "REF_FE_H2FC_BUS_KG": "Hydrogen Fuel Consumption",
    "REF_INFRA_H2_STATION_CAPEX": "Hydrogen Small-Tier Station CapEx (Reference)",
    "H2_TIER_THRESHOLD_KG_DAY": "Hydrogen Station Tier Threshold",
    "H2_CAPEX_SMALL_LIQUID": "Hydrogen Small-Tier Station CapEx",
    "H2_CAPEX_MEDIUM_DELIVERY": "Hydrogen Medium-Tier Station CapEx",
    "REF_PRICE_H2_KG_SMALL": "Hydrogen Price — Small Station Tier",
    "REF_PRICE_H2_KG_MED": "Hydrogen Price — Medium Station Tier",
    "REF_CLIMATE_H2_COLD_START": "Hydrogen Cold-Start Efficiency Penalty",
    "REF_CAPEX_VEH_CNG_BUS": "CNG Bus Purchase Price",
    "REF_MAINT_CPM_CNG": "CNG Maintenance Cost per Mile",
    "REF_FE_CNG_BUS_DGE": "CNG Fuel Economy",
    "REF_CI_CNG_GHG": "CNG Well-to-Wheel Carbon Intensity",
    "REF_PRICE_CNG_DGE": "CNG Reference Price",
    "CNG_FLEET_THRESHOLD_FAST_FILL": "CNG Fast-Fill Fleet-Size Threshold",
    "REF_INFRA_CNG_STATION_TIME": "CNG Time-Fill Station CapEx",
    "REF_INFRA_CNG_STATION_FAST": "CNG Fast-Fill Station CapEx",
    "REF_CAPEX_VEH_B20_BUS": "Biodiesel (B20) Bus Purchase Price",
    "REF_MAINT_CPM_B20": "Biodiesel (B20) Maintenance Cost per Mile",
    "REF_FE_B20_BUS_MPG": "Biodiesel (B20) Fuel Economy",
    "REF_CI_B20_GHG": "Biodiesel (B20) Well-to-Wheel Carbon Intensity",
    "INFRA_LIFESPAN_YEARS": "Infrastructure Amortization Lifespan",
    "REF_BIODIESEL_COLD_MAINTENANCE_MULTIPLIER": "Biodiesel Cold-Climate Maintenance Multiplier",
    # DISCLOSED CHANGE (pricing-bug remediation, phase 1 of 2): labels for the
    # canadian_regional_pricing param_ids staged in afleet_baselines.json.
    # Not yet exercised -- tco_calculator.py doesn't wire these in until
    # phase 2 (see PHASE 2 INSERTION POINT comments there) -- added now so
    # the assumptions matrix renders correctly the moment they are.
    "REF_PRICE_DIESEL_CAD_NB": "Diesel Reference Price (New Brunswick)",
    "REF_PRICE_DIESEL_CAD_ON": "Diesel Reference Price (Ontario)",
    "REF_PRICE_DIESEL_CAD_QC": "Diesel Reference Price (Quebec)",
    "REF_PRICE_DIESEL_CAD_BC": "Diesel Reference Price (British Columbia)",
    "REF_PRICE_DIESEL_CAD_AB": "Diesel Reference Price (Alberta)",
    "REF_PRICE_ELEC_CAD_NB": "Electricity Reference Rate (New Brunswick)",
    "REF_PRICE_ELEC_CAD_ON": "Electricity Reference Rate (Ontario)",
    "REF_PRICE_ELEC_CAD_QC": "Electricity Reference Rate (Quebec)",
    "REF_PRICE_ELEC_CAD_BC": "Electricity Reference Rate (British Columbia)",
    "REF_PRICE_ELEC_CAD_AB": "Electricity Reference Rate (Alberta)",
    "REF_INCENTIVE_QC_PETS_BEV_BUS": "Quebec PETS Electric School Bus Purchase Rebate",
}


class TrackedDict(dict):
    """
    Observes reads of leaf value keys (default/value/co2e_lb_per_mwh) on any
    dict that carries a "param_id", logging them to whichever tracker is
    active in the current context. Returns values unmodified; nested dicts
    are wrapped lazily on first access so chained lookups stay observable.
    """

    def __getitem__(self, key):
        value = super().__getitem__(key)
        if key in _VALUE_KEYS and "param_id" in self:
            tracker = _current_tracker.get()
            if tracker is not None:
                tracker.append(_entry_from_leaf(self, value))
        if isinstance(value, dict) and not isinstance(value, TrackedDict):
            value = TrackedDict(value)
        return value

    def get(self, key, default=None):
        # dict.get() bypasses a subclass's __getitem__ at the C level;
        # routing it through self[key] keeps .get() call sites observable.
        try:
            return self[key]
        except KeyError:
            return default


def _label_for(param_id: str) -> str:
    if param_id in PARAM_LABELS:
        return PARAM_LABELS[param_id]
    if param_id.startswith("REF_EM_"):
        # Grid factor entries (REF_EM_EGRID_<SUBREGION> / REF_EM_ECCC_<PROV>)
        # are only ever reached passively via TrackedDict — the subregion
        # code is the final underscore-separated token of the param_id.
        subregion = param_id.rsplit("_", 1)[-1]
        return f"Regional Grid Emissions Factor — {subregion}"
    return param_id.replace("_", " ").title()


def _entry_from_leaf(leaf: Dict[str, Any], value: Any, is_override: bool = False) -> AssumptionEntry:
    param_id = leaf["param_id"]
    # DISCLOSED CHANGE (GRID_FACTOR_NB citation fix): the split
    # source_agency + source_year pair is only present on some baseline
    # entries. Records that carry a single pre-formatted source_agency
    # string (e.g. grid_factors.json's Canadian entries, which already bake
    # the year into the citation text) were falling through to
    # leaf.get("source", ...) -- a key name that doesn't exist on these
    # records -- silently discarding the real citation and substituting the
    # generic default. Added an explicit source_agency-only branch so a
    # correctly-cited record is never overridden just because it doesn't
    # also carry a separate source_year field.
    has_split_source = "source_agency" in leaf and "source_year" in leaf
    has_agency_only = "source_agency" in leaf

    if has_split_source:
        source_agency = f"{leaf['source_agency']} {leaf['source_year']}"
    elif has_agency_only:
        source_agency = leaf["source_agency"]
    else:
        source_agency = leaf.get("source", "FleetPath Engineering Assumption")

    unit_from_leaf = leaf.get("unit")
    is_co2e_grid_factor = "co2e_lb_per_mwh" in leaf
    unit = unit_from_leaf or ("lb CO2e/MWh" if is_co2e_grid_factor else "")

    return AssumptionEntry(
        param_id=param_id,
        label=_label_for(param_id),
        value=value,
        unit=unit,
        source_agency=source_agency,
        is_override=is_override,
    )


def tracked_choice(override_value: Optional[float], baseline_entry: Dict[str, Any], value_key: str = "default"):
    """
    Replaces the `override_value or baseline_entry[value_key]` pattern at
    the three override-eligible call sites in tco_calculator.py. When an
    override is supplied, logs it explicitly (the baseline branch is never
    touched in that case, so passive TrackedDict tracking cannot see it).
    Otherwise defers to the baseline read, which TrackedDict observes on
    its own since baseline_entry is already a tracked dict by this point.
    """
    if override_value is not None:
        tracker = _current_tracker.get()
        if tracker is not None:
            param_id = baseline_entry["param_id"]
            tracker.append(AssumptionEntry(
                param_id=param_id,
                label=_label_for(param_id),
                value=override_value,
                unit=baseline_entry.get("unit", ""),
                source_agency="User-Provided Override",
                is_override=True,
            ))
        return override_value
    return baseline_entry[value_key]


def tracked_fx_conversion(usd_baseline_entry: Dict[str, Any], fx_rate: float, value_key: str = "default") -> float:
    """
    DISCLOSED CHANGE (pricing-bug remediation, phase 2 of 2): converts a USD
    AFLEET/NREL baseline entry to CAD via fx_rates.json's dated Bank of
    Canada rate, for the vehicle-capex, infrastructure-capex, maintenance-
    CPM, and CNG/hydrogen fuel-price parameters that have no native
    Canadian benchmark (see canadian_regional_pricing_gaps in
    afleet_baselines.json for what was searched and came up empty).

    Reading usd_baseline_entry[value_key] passes through TrackedDict's own
    __getitem__, so the underlying USD baseline entry is logged exactly as
    it would be for a US-region calculation. This function additionally
    appends one synthetic entry showing the converted CAD figure and the
    exact FX rate/date/source used -- so the assumptions matrix shows both
    numbers side by side (USD baseline -> CAD result), never just the
    converted figure standing alone with no way to verify the arithmetic.
    """
    usd_value = usd_baseline_entry[value_key]
    cad_value = usd_value * fx_rate

    tracker = _current_tracker.get()
    if tracker is not None:
        original_param_id = usd_baseline_entry.get("param_id", "UNKNOWN")
        original_label = _label_for(original_param_id)
        original_unit = usd_baseline_entry.get("unit", "")
        cad_unit = original_unit.replace("USD", "CAD") if "USD" in original_unit else original_unit

        fx_rate_entry = _FX_RATES_RAW["usd_to_cad"]
        observation_date = fx_rate_entry["rate_observation_date"]
        rate_value = fx_rate_entry["value"]
        source_citation_text = (
            f"{original_label} source (USD) x Bank of Canada daily rate "
            f"{observation_date} (1 USD = {rate_value} CAD)"
        )

        tracker.append(AssumptionEntry(
            param_id=f"{original_param_id}_CAD_FX",
            label=f"{original_label} (CAD, FX-converted)",
            value=round(cad_value, 4),
            unit=cad_unit,
            source_agency=source_citation_text,
            is_override=False,
        ))
    return cad_value


@contextmanager
def track_pathway_assumptions():
    """
    Scopes assumption recording to one pathway's calculation. Usage:
        with track_pathway_assumptions() as entries:
            calculate_pathway_tco(fuel_type, inputs)
            calculate_pathway_emissions(fuel_type, inputs)
        # entries now holds every baseline/override read during the block
    """
    token = _current_tracker.set([])
    try:
        yield _current_tracker.get()
    finally:
        _current_tracker.reset(token)


def dedupe_assumptions(entries: List[AssumptionEntry]) -> List[AssumptionEntry]:
    """Collapses repeat reads of the same param_id (tco_calculator and
    emissions_calculator often consult the same baseline entry) to one
    entry, keeping first-seen order."""
    seen = set()
    deduped = []
    for entry in entries:
        if entry.param_id in seen:
            continue
        seen.add(entry.param_id)
        deduped.append(entry)
    return deduped


# Explicit (non-passive) assumptions: engine_constants and grid factors
# engine_constants (INFRA_LIFESPAN_YEARS, BEV ratio, H2 tier thresholds/
# capex, CNG threshold) — and, for the same reason, the two climate-penalty
# constants in emissions_calculator.py — are cached as plain Python scalars
# at each calculator's own import time, before this module wraps any dict
# for tracking, so passive interception can never see them consulted during
# a specific calculation. Rather than touch every usage site inside the
# frozen calculators (5+ call sites across 3 functions in tco_calculator.py
# alone, including the INFRA_LIFESPAN_YEARS integrity assert, which is
# deliberately a stable Python constant and not meant to be re-read live),
# we independently load the same JSON here and attach the constants known
# to structurally apply to each pathway. This does not affect any
# calculated dollar or ton figure — it only affects which citations appear
# in the assumptions list.
_FULL_BASELINES_RAW: Dict[str, Any] = json.loads((_DATA_DIR / "afleet_baselines.json").read_text(encoding="utf-8"))
_ENGINE_CONSTANTS: Dict[str, Any] = _FULL_BASELINES_RAW["engine_constants"]
_H2_TIER_THRESHOLD_KG_DAY: float = _ENGINE_CONSTANTS["hydrogen_tier_threshold_kg_day"]["value"]


def _climate_penalty_entry(pathway: str, key: str) -> AssumptionEntry:
    node = _FULL_BASELINES_RAW[pathway]["climate_adjustment"][key]
    param_id = node["param_id"]
    return AssumptionEntry(
        param_id=param_id,
        label=_label_for(param_id),
        value=node["default"],
        unit=node.get("unit", ""),
        source_agency=node.get("source", "FleetPath Engineering Assumption"),
        is_override=False,
    )


def _engine_constant_entry(key: str) -> AssumptionEntry:
    node = _ENGINE_CONSTANTS[key]
    param_id = node["param_id"]
    return AssumptionEntry(
        param_id=param_id,
        label=_label_for(param_id),
        value=node["value"],
        unit=node.get("unit", ""),
        source_agency=node.get("source", "Engineering estimate pending citation"),
        is_override=False,
    )


def get_static_assumptions(fuel_type: str, inputs: FleetInputPayload) -> List[AssumptionEntry]:
    """
    Assumptions known structurally to apply to a pathway, independent of
    live dict-access interception (see module docstring above).
    """
    entries: List[AssumptionEntry] = []

    if fuel_type in ("bev", "hydrogen", "cng"):
        entries.append(_engine_constant_entry("infra_lifespan_years"))

    # Note: the regional grid emissions factor (REF_EM_EGRID_* / REF_EM_ECCC_*)
    # consulted by the bev/hydrogen pathways is NOT listed here — it is a
    # live dict read (via get_grid_factor_lb_per_mwh) and is already
    # captured by passive TrackedDict tracking, so listing it again here
    # would duplicate it ahead of dedup with a less specific ordering.

    if fuel_type == "bev":
        if inputs.climate.cold_climate_flag:
            entries.append(_climate_penalty_entry("bev", "cold_climate_efficiency_penalty_pct"))

    if fuel_type == "hydrogen":
        from .tco_calculator import hydrogen_daily_demand_kg  # deferred: tco_calculator is wrapped by this module at import

        entries.append(_engine_constant_entry("hydrogen_tier_threshold_kg_day"))
        is_small_station_tier = hydrogen_daily_demand_kg(inputs) <= _H2_TIER_THRESHOLD_KG_DAY
        tier_key = (
            "hydrogen_capex_small_liquid_usd"
            if is_small_station_tier
            else "hydrogen_capex_medium_delivery_usd"
        )
        entries.append(_engine_constant_entry(tier_key))
        if inputs.climate.cold_climate_flag:
            entries.append(_climate_penalty_entry("hydrogen", "cold_start_efficiency_penalty"))

    if fuel_type == "cng":
        entries.append(_engine_constant_entry("cng_fleet_threshold_fast_fill"))

    if fuel_type == "biodiesel":
        if inputs.climate.cold_climate_flag:
            entries.append(_climate_penalty_entry("biodiesel", "cold_weather_maintenance_multiplier"))

    return entries


# Wiring: wrap the calculators' already-loaded baseline dicts for passive
# tracking. Runs once, at this module's own import time. Deferred (function-
# scoped) imports inside tco_calculator.py's override branches — not a
# module-level import here of tco_calculator/emissions_calculator — are what
# keep this one-directional and import-order-safe (see tco_calculator.py
# comments at the three tracked_choice() call sites).

def _enable_tracking() -> None:
    from . import tco_calculator as _tco
    from . import emissions_calculator as _emissions

    if not isinstance(_tco._BASELINES, TrackedDict):
        _tco._BASELINES = TrackedDict(_tco._BASELINES)
    if not isinstance(_emissions._BASELINES, TrackedDict):
        _emissions._BASELINES = TrackedDict(_emissions._BASELINES)
    if not isinstance(_emissions._GRID_FACTORS, TrackedDict):
        _emissions._GRID_FACTORS = TrackedDict(_emissions._GRID_FACTORS)


_enable_tracking()