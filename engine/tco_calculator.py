import json
import math
from pathlib import Path
from typing import Any, Dict

from .models import FleetInputPayload, PathwayOutputMetrics
from .emissions_calculator import (
    get_bev_effective_kwh_per_mile,
    get_hydrogen_effective_kg_per_mile,
    get_grid_factor_lb_per_mwh,
    UnknownRegionError,
)
from .vehicle_classes import capex_key, maintenance_key, fuel_economy_key

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load_json(filename: str) -> Dict[str, Any]:
    return json.loads((_DATA_DIR / filename).read_text(encoding="utf-8"))


_BASELINES: Dict[str, Any] = _load_json("afleet_baselines.json")
_CROSSWALK: Dict[str, Any] = _load_json("state_crosswalk.json")
_CA_REGIONAL_PRICING: Dict[str, Any] = _BASELINES.get("canadian_regional_pricing", {})
_FX_RATES: Dict[str, Any] = _load_json("fx_rates.json")

_ENGINE_CONSTANTS = _BASELINES["engine_constants"]
INFRA_LIFESPAN_YEARS: int = int(_ENGINE_CONSTANTS["infra_lifespan_years"]["value"])
H2_TIER_THRESHOLD_KG_DAY: float = float(_ENGINE_CONSTANTS["hydrogen_tier_threshold_kg_day"]["value"])
H2_CAPEX_SMALL_LIQUID: float = float(_ENGINE_CONSTANTS["hydrogen_capex_small_liquid_usd"]["value"])
H2_CAPEX_MEDIUM_DELIVERY: float = float(_ENGINE_CONSTANTS["hydrogen_capex_medium_delivery_usd"]["value"])
CNG_FLEET_THRESHOLD_FAST_FILL: int = int(_ENGINE_CONSTANTS["cng_fleet_threshold_fast_fill"]["value"])

assert INFRA_LIFESPAN_YEARS == 20, "CRITICAL: INFRA_LIFESPAN_YEARS mutated in afleet_baselines.json."

KG_PER_LB = 0.45359237
HOURS_PER_YEAR = 8760.0

# DISCLOSED CHANGE (pricing-bug remediation, phase 2 of 2): every pathway now
# resolves fully to CAD for Canadian regions, closing the currency-mixing gap
# left open at the end of phase 1. Two citation tiers exist side by side and
# are labeled distinctly in the assumptions matrix (see assumptions_tracker.py
# tracked_fx_conversion):
#   - Native CAD: diesel/electricity pricing, sourced directly from NRCan /
#     Hydro-Quebec (canadian_regional_pricing in afleet_baselines.json).
#   - FX-converted: vehicle capex, infrastructure capex, maintenance CPM, and
#     CNG/hydrogen fuel price. No native Canadian benchmark was found for any
#     of these after a real search pass (see canadian_regional_pricing_gaps)
#     -- commercial bus/charger/station pricing is quote-based in both
#     countries and isn't published, and CUTA's fleet-cost statistics are
#     member-only. Converted via fx_rates.json, a dated Bank of Canada rate
#     refreshed offline by scripts/refresh_fx_snapshot.py -- this module
#     never calls that API itself.
# US regions are completely unaffected by any of this: currency stays "USD"
# and every value is read exactly as before.

def _resolve_region(state_prov: str) -> Dict[str, Any]:
    # DISCLOSED CHANGE (region-resolution consistency fix): previously
    # returned {} for an unrecognized code, silently defaulting every
    # downstream is_canadian check to False and applying USD pricing with
    # no indication anything was wrong. In the full pipeline this was
    # incidentally caught by bev's emissions calculation (which already
    # raises UnknownRegionError via get_subregion_for_state), but any
    # direct call to calculate_pathway_tco -- including several in this
    # test suite -- bypasses that check entirely. Now raises the same
    # UnknownRegionError emissions_calculator.py already uses, so both
    # lookup paths fail identically instead of one being silently lenient.
    state_code = state_prov.strip().upper()
    region_info = _CROSSWALK.get(state_code)
    if region_info is None:
        raise UnknownRegionError(
            f"No state_crosswalk.json entry for region code '{state_code}'."
        )
    return region_info


def _fx_rate_usd_to_cad() -> float:
    return float(_FX_RATES["usd_to_cad"]["value"])


# Pathways with a modeled cold-climate adjustment: BEV and hydrogen (consumption
# penalty, emissions_calculator.py) and biodiesel (maintenance multiplier, above).
# Diesel and CNG have none, so the output flag must stay False for them.
_COLD_ADJUSTED_PATHWAYS = frozenset({"bev", "hydrogen", "biodiesel"})


def _cold_climate_maintenance_multiplier(pathway: str, cold_climate_flag: bool) -> float:
    if not cold_climate_flag:
        return 1.0
    if pathway == "biodiesel":
        return _BASELINES["biodiesel"]["climate_adjustment"]["cold_weather_maintenance_multiplier"]["default"]
    return 1.0


def _money(value: float, currency: str) -> str:
    return f"${round_half_up(value):,} {currency}"


def round_half_up(value: float) -> int:
    """Whole-unit rounding that matches the frontend (Intl.NumberFormat rounds halves away from zero)."""
    from decimal import Decimal, ROUND_HALF_UP

    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _calc_bev_infrastructure(vehicle_count: int, vehicle_type: str, is_canadian: bool) -> Dict[str, Any]:
    # Charger model: school buses get one networked Level 2 charger each plus
    # DC fast chargers at one per REF_INFRA_BEV_DCFC_RATIO buses (Joint Office /
    # NREL guidance); transit buses get one depot charger each (NREL 2020).
    bev = _BASELINES["bev"]["infrastructure"]

    from .assumptions_tracker import tracked_fx_conversion  # local import avoids load-order coupling

    fx = _fx_rate_usd_to_cad() if is_canadian else None

    def cost(entry):
        return tracked_fx_conversion(entry, fx) if is_canadian else entry["default"]

    if vehicle_type == "school_bus_typeC":
        buses_per_dcfc = bev["school_bus_dcfc_buses_per_unit"]["default"]
        l2_units = vehicle_count
        dcfc_units = math.ceil(vehicle_count / buses_per_dcfc)
        groups = [
            (l2_units, cost(bev["school_bus_l2_hardware_usd"]), cost(bev["school_bus_l2_install_usd"])),
            (dcfc_units, cost(bev["dcfc_50_hardware_usd"]), cost(bev["dcfc_50_make_ready_usd"])),
        ]
        description = (
            f"{l2_units} Level 2 charger{'s' if l2_units != 1 else ''} (one per bus) + "
            f"{dcfc_units} 50 kW DC fast charger{'s' if dcfc_units != 1 else ''} (one per {buses_per_dcfc:g} buses)"
        )
    else:
        per_bus = bev["transit_depot_chargers_per_bus"]["default"]
        depot_units = math.ceil(vehicle_count * per_bus)
        groups = [
            (depot_units, cost(bev["transit_depot_charger_hardware_usd"]), cost(bev["transit_depot_charger_install_usd"])),
        ]
        description = f"{depot_units} depot charger{'s' if depot_units != 1 else ''} (one per bus)"

    comms_cost = cost(bev["annual_comms_usd"])
    # Fractions are dimensionless -- no FX conversion applies to these.
    maint_frac = bev["annual_maintenance_pct"]["default"]
    warranty_frac = bev["warranty_pct_lifetime"]["default"]

    chargers_required = sum(n for n, _, _ in groups)
    hardware_total = sum(n * hw for n, hw, _ in groups)
    total_infra_capex = sum(n * (hw + install) for n, hw, install in groups)

    annual_maint_cost = hardware_total * maint_frac
    annual_comms_total = chargers_required * comms_cost
    annual_warranty_amortized = (hardware_total * warranty_frac) / INFRA_LIFESPAN_YEARS
    annual_om_total = annual_maint_cost + annual_comms_total + annual_warranty_amortized

    return {
        "chargers_required": chargers_required,
        "total_infra_capex": total_infra_capex,
        "annual_om_total": annual_om_total,
        "description": description,
    }


def hydrogen_kg_per_mile(inputs: FleetInputPayload) -> float:
    h2 = _BASELINES["hydrogen"]
    base_kg_per_mile = h2["fuel_economy"][fuel_economy_key(inputs.fleet.vehicle_type, "hydrogen")]["default"]
    return get_hydrogen_effective_kg_per_mile(
        base_kg_per_mile=base_kg_per_mile,
        cold_climate_flag=inputs.climate.cold_climate_flag,
    )


def hydrogen_daily_demand_kg(inputs: FleetInputPayload) -> float:
    fleet = inputs.fleet
    daily_miles_per_vehicle = fleet.annual_mileage_per_vehicle / 365.0
    return fleet.vehicle_count * daily_miles_per_vehicle * hydrogen_kg_per_mile(inputs)


def _calc_hydrogen_infrastructure(daily_fleet_demand_kg_h2: float, is_canadian: bool) -> Dict[str, Any]:
    h2 = _BASELINES["hydrogen"]

    from .assumptions_tracker import tracked_fx_conversion  # local import avoids load-order coupling

    if daily_fleet_demand_kg_h2 <= H2_TIER_THRESHOLD_KG_DAY:
        tier = "small_liquid_delivery"
        usd_capex = H2_CAPEX_SMALL_LIQUID
        entry = h2["infrastructure"]["small_liquid_delivery_capex_usd"]
    else:
        tier = "medium_delivery"
        usd_capex = H2_CAPEX_MEDIUM_DELIVERY
        entry = h2["infrastructure"]["medium_delivery_capex_usd"]

    if is_canadian:
        total_infra_capex = tracked_fx_conversion(entry, _fx_rate_usd_to_cad())
    else:
        total_infra_capex = usd_capex

    return {
        "daily_fleet_demand_kg_h2": daily_fleet_demand_kg_h2,
        "station_tier": tier,
        "total_infra_capex": total_infra_capex,
    }


def _calc_cng_infrastructure(vehicle_count: int, is_canadian: bool) -> Dict[str, Any]:
    cng = _BASELINES["cng"]["infrastructure"]
    from .assumptions_tracker import tracked_fx_conversion  # local import avoids load-order coupling

    if vehicle_count <= CNG_FLEET_THRESHOLD_FAST_FILL:
        station_type = "time_fill"
        entry = cng["time_fill_station_capex_usd"]
    else:
        station_type = "fast_fill"
        entry = cng["fast_fill_station_capex_usd"]

    if is_canadian:
        total_infra_capex = tracked_fx_conversion(entry, _fx_rate_usd_to_cad())
    else:
        total_infra_capex = entry["default"]

    return {"station_type": station_type, "total_infra_capex": total_infra_capex}


def _amortize_vehicle_capex(capex_vehicle_total: float, fleet_lifecycle_years: int) -> float:
    return capex_vehicle_total / fleet_lifecycle_years


def _amortize_infra_capex(total_infra_capex: float) -> float:
    return total_infra_capex / INFRA_LIFESPAN_YEARS


def _region_flags(inputs: FleetInputPayload):
    region_info = _resolve_region(inputs.region.state_prov)
    province = region_info.get("code", "")
    is_canadian = region_info.get("country") == "CA" and province in _CA_REGIONAL_PRICING
    return region_info, province, is_canadian


def _calc_diesel_pathway(inputs: FleetInputPayload) -> Dict[str, Any]:
    diesel = _BASELINES["diesel"]
    fleet, overrides = inputs.fleet, inputs.overrides
    vt = fleet.vehicle_type

    from .assumptions_tracker import tracked_choice, tracked_fx_conversion  # local import avoids load-order coupling

    region_info, province, is_canadian = _region_flags(inputs)

    if is_canadian:
        fx = _fx_rate_usd_to_cad()
        capex_vehicle_total = tracked_fx_conversion(diesel["capex"][capex_key(vt)], fx) * fleet.vehicle_count
        ca_price_entry = _CA_REGIONAL_PRICING[province]["diesel"]
        price_per_gal = tracked_choice(overrides.diesel_price_gal, ca_price_entry, value_key="default_price_per_gal_cad")
        maint_cpm = tracked_fx_conversion(diesel["maintenance"][maintenance_key(vt)], fx)
        currency = "CAD"
    else:
        capex_vehicle_total = diesel["capex"][capex_key(vt)]["default"] * fleet.vehicle_count
        price_per_gal = tracked_choice(overrides.diesel_price_gal, diesel["fuel_price"]["default_price_gal"])
        maint_cpm = diesel["maintenance"][maintenance_key(vt)]["default"]
        currency = "USD"

    mpg = diesel["fuel_economy"][fuel_economy_key(vt, "diesel")]["default"]
    total_miles = fleet.vehicle_count * fleet.annual_mileage_per_vehicle
    gallons_consumed = total_miles / mpg
    opex_fuel = gallons_consumed * price_per_gal

    multiplier = _cold_climate_maintenance_multiplier("diesel", inputs.climate.cold_climate_flag)
    opex_maintenance = total_miles * maint_cpm * multiplier

    return {
        "capex_vehicle_total": capex_vehicle_total,
        "total_infra_capex": 0.0,
        "opex_fuel": opex_fuel,
        "opex_maintenance": opex_maintenance,
        "currency": currency,
    }


def _calc_biodiesel_pathway(inputs: FleetInputPayload) -> Dict[str, Any]:
    biodiesel = _BASELINES["biodiesel"]
    fleet, overrides = inputs.fleet, inputs.overrides
    vt = fleet.vehicle_type

    from .assumptions_tracker import tracked_choice, tracked_fx_conversion  # local import avoids load-order coupling

    region_info, province, is_canadian = _region_flags(inputs)

    if is_canadian:
        fx = _fx_rate_usd_to_cad()
        capex_vehicle_total = tracked_fx_conversion(biodiesel["capex"][capex_key(vt)], fx) * fleet.vehicle_count
        # Biodiesel shares the diesel price baseline, same as before this change.
        ca_price_entry = _CA_REGIONAL_PRICING[province]["diesel"]
        price_per_gal = tracked_choice(overrides.diesel_price_gal, ca_price_entry, value_key="default_price_per_gal_cad")
        maint_cpm = tracked_fx_conversion(biodiesel["maintenance"][maintenance_key(vt)], fx)
        currency = "CAD"
    else:
        capex_vehicle_total = biodiesel["capex"][capex_key(vt)]["default"] * fleet.vehicle_count
        price_per_gal = tracked_choice(overrides.diesel_price_gal, biodiesel["fuel_price"]["default_price_gal"])
        maint_cpm = biodiesel["maintenance"][maintenance_key(vt)]["default"]
        currency = "USD"

    mpg = biodiesel["fuel_economy"][fuel_economy_key(vt, "biodiesel")]["default"]
    total_miles = fleet.vehicle_count * fleet.annual_mileage_per_vehicle
    gallons_consumed = total_miles / mpg
    opex_fuel = gallons_consumed * price_per_gal

    multiplier = _cold_climate_maintenance_multiplier("biodiesel", inputs.climate.cold_climate_flag)
    opex_maintenance = total_miles * maint_cpm * multiplier

    return {
        "capex_vehicle_total": capex_vehicle_total,
        "total_infra_capex": 0.0,
        "opex_fuel": opex_fuel,
        "opex_maintenance": opex_maintenance,
        "currency": currency,
    }


def _electricity_rate(inputs: FleetInputPayload, province: str, is_canadian: bool) -> float:
    from .assumptions_tracker import tracked_choice  # local import avoids load-order coupling

    if is_canadian:
        ca_price_entry = _CA_REGIONAL_PRICING[province]["electricity"]
        return tracked_choice(inputs.overrides.electricity_rate_kwh, ca_price_entry, value_key="default_price_per_kwh_cad")
    return tracked_choice(inputs.overrides.electricity_rate_kwh, _BASELINES["bev"]["fuel_price"]["default_electricity_rate_usd_kwh"])


def _calc_bev_pathway(inputs: FleetInputPayload) -> Dict[str, Any]:
    bev = _BASELINES["bev"]
    fleet = inputs.fleet
    vt = fleet.vehicle_type

    from .assumptions_tracker import tracked_fx_conversion  # local import avoids load-order coupling

    region_info, province, is_canadian = _region_flags(inputs)

    infra = _calc_bev_infrastructure(fleet.vehicle_count, vt, is_canadian)

    base_kwh_per_mile = bev["fuel_economy"][fuel_economy_key(vt, "bev")]["default"]
    kwh_per_mile_effective = get_bev_effective_kwh_per_mile(
        base_kwh_per_mile=base_kwh_per_mile,
        cold_climate_flag=inputs.climate.cold_climate_flag,
    )

    electricity_rate = _electricity_rate(inputs, province, is_canadian)
    if is_canadian:
        fx = _fx_rate_usd_to_cad()
        capex_vehicle_total = tracked_fx_conversion(bev["capex"][capex_key(vt)], fx) * fleet.vehicle_count
        maint_cpm = tracked_fx_conversion(bev["maintenance"][maintenance_key(vt)], fx)
        currency = "CAD"
    else:
        capex_vehicle_total = bev["capex"][capex_key(vt)]["default"] * fleet.vehicle_count
        maint_cpm = bev["maintenance"][maintenance_key(vt)]["default"]
        currency = "USD"

    notes = [f"Charging: {infra['description']}."]

    # DISCLOSED CHANGE (BEV incentive gap, PRD §6 priority 2): Quebec's PETS
    # program (Programme d'electrification du transport scolaire) is a real,
    # cited purchase rebate -- applied to vehicle capex before amortization.
    # Gated strictly to province == "QC", not a general CA check -- no
    # equivalent was found for any other province after a real search pass
    # (see canadian_regional_pricing_gaps.bev_incentive_outside_quebec).
    # PETS covers electric school buses only, so transit buses never receive it.
    qc_pets_incentive_cad = 0.0
    if province == "QC" and vt == "school_bus_typeC":
        pets_entry = bev["incentives"]["qc_pets_purchase_rebate_cad_per_bus"]
        per_bus_rebate = pets_entry["value"]
        qc_pets_incentive_cad = per_bus_rebate * fleet.vehicle_count
        capex_vehicle_total = capex_vehicle_total - qc_pets_incentive_cad
        notes.append(
            f"Quebec PETS rebate applied: {_money(qc_pets_incentive_cad, 'CAD')} "
            f"({_money(per_bus_rebate, 'CAD')} per school bus), netted from upfront vehicle capital."
        )

    total_miles = fleet.vehicle_count * fleet.annual_mileage_per_vehicle
    kwh_consumed = total_miles * kwh_per_mile_effective
    opex_fuel = kwh_consumed * electricity_rate

    multiplier = _cold_climate_maintenance_multiplier("bev", inputs.climate.cold_climate_flag)
    fleet_maintenance_cost = total_miles * maint_cpm * multiplier
    opex_maintenance = fleet_maintenance_cost + infra["annual_om_total"]

    return {
        "capex_vehicle_total": capex_vehicle_total,
        "total_infra_capex": infra["total_infra_capex"],
        "qc_pets_incentive_cad": qc_pets_incentive_cad,
        "opex_fuel": opex_fuel,
        "opex_maintenance": opex_maintenance,
        "currency": currency,
        "notes": notes,
    }


def _h2_itc_rate_for_ci(ci_kg_per_kg: float) -> float:
    """Clean Hydrogen ITC tier for a modeled carbon intensity (kg CO2e/kg H2); 0.0 at 4.0 or above."""
    from .assumptions_tracker import TrackedDict  # list items are not wrapped automatically

    itc = _BASELINES["hydrogen"]["infrastructure"]["ca_federal_clean_hydrogen_itc"]
    for tier in itc["tiers"]:
        if ci_kg_per_kg < tier["max_ci_kg_co2e_per_kg"]:
            return TrackedDict(tier)["value"]
    return 0.0


def electrolysis_carbon_intensity_kg_per_kg(state_prov: str) -> float:
    """Modeled on-site electrolysis carbon intensity: system kWh/kg x regional grid factor."""
    oe = _BASELINES["hydrogen"]["infrastructure"]["onsite_electrolysis"]
    kwh_per_kg = oe["electrolyzer_system_kwh_per_kg"]["default"]
    lb_per_kwh = get_grid_factor_lb_per_mwh(state_prov) / 1000.0
    return kwh_per_kg * lb_per_kwh * KG_PER_LB


def _hydrogen_delivered_option(inputs: FleetInputPayload, is_canadian: bool) -> Dict[str, Any]:
    h2 = _BASELINES["hydrogen"]

    from .assumptions_tracker import tracked_fx_conversion  # local import avoids load-order coupling

    infra = _calc_hydrogen_infrastructure(hydrogen_daily_demand_kg(inputs), is_canadian)
    tier_key = (
        "small_liquid_delivery_capex_usd"
        if infra["station_tier"] == "small_liquid_delivery"
        else "medium_delivery_capex_usd"
    )
    price_entry = h2["infrastructure"][tier_key]["price_per_kg"]
    price_per_kg = tracked_fx_conversion(price_entry, _fx_rate_usd_to_cad()) if is_canadian else price_entry["default"]

    annual_kg = inputs.fleet.vehicle_count * inputs.fleet.annual_mileage_per_vehicle * hydrogen_kg_per_mile(inputs)
    return {
        "supply": "delivered_liquid",
        "total_infra_capex": infra["total_infra_capex"],
        "opex_fuel": annual_kg * price_per_kg,
        "station_opex": 0.0,
        "itc": 0.0,
        "itc_note": None,
    }


def _hydrogen_onsite_option(inputs: FleetInputPayload, region_info: Dict[str, Any], province: str, is_canadian: bool) -> Dict[str, Any]:
    oe = _BASELINES["hydrogen"]["infrastructure"]["onsite_electrolysis"]

    from .assumptions_tracker import tracked_fx_conversion  # local import avoids load-order coupling

    fx = _fx_rate_usd_to_cad() if is_canadian else None

    def cost(entry):
        return tracked_fx_conversion(entry, fx) if is_canadian else entry["default"]

    daily_kg = hydrogen_daily_demand_kg(inputs)
    kwh_per_kg = oe["electrolyzer_system_kwh_per_kg"]["default"]
    capacity_factor = oe["electrolyzer_capacity_factor"]["default"]
    electrolyzer_kw = daily_kg * kwh_per_kg / 24.0 / capacity_factor

    small_scale = oe["electrolyzer_small_scale_capex_multiplier"]["default"]
    electrolyzer_capex = electrolyzer_kw * cost(oe["electrolyzer_installed_capex_usd_per_kw"]) * small_scale
    csd_design_kg_day = max(daily_kg, oe["csd_min_design_capacity_kg_day"]["default"])
    csd_capex = csd_design_kg_day * cost(oe["csd_capex_usd_per_kg_day"])

    fixed_om = electrolyzer_capex * oe["electrolyzer_fixed_om_fraction"]["default"]
    operating_hours = HOURS_PER_YEAR * capacity_factor
    stack_replacement = (
        electrolyzer_capex
        * oe["stack_replacement_fraction"]["default"]
        * operating_hours
        / oe["stack_replacement_interval_hours"]["default"]
    )

    annual_kg = daily_kg * 365.0
    opex_fuel = annual_kg * kwh_per_kg * _electricity_rate(inputs, province, is_canadian)

    itc = 0.0
    itc_note = None
    if region_info.get("country") == "CA":
        itc_entry = _BASELINES["hydrogen"]["infrastructure"]["ca_federal_clean_hydrogen_itc"]
        ci = electrolysis_carbon_intensity_kg_per_kg(inputs.region.state_prov)
        currency = "CAD" if is_canadian else "USD"
        if inputs.fleet.owner_type not in itc_entry["eligible_owner_types"]:
            itc_note = (
                "Clean Hydrogen ITC: not applied. Only taxable Canadian corporations can claim it; "
                "the selected owner type is a public body."
            )
        else:
            rate = _h2_itc_rate_for_ci(ci)
            if rate > 0:
                itc = electrolyzer_capex * rate
                itc_note = (
                    f"Clean Hydrogen ITC: {rate:.0%} of {_money(electrolyzer_capex, currency)} electrolyzer capital "
                    f"= {_money(itc, currency)} (modeled carbon intensity {ci:.2f} kg CO2e/kg H2, estimate)."
                )
            else:
                itc_note = (
                    f"Clean Hydrogen ITC: not applied. Modeled carbon intensity {ci:.1f} kg CO2e/kg H2 "
                    "is at or above the 4.0 limit."
                )

    return {
        "supply": "onsite_electrolysis",
        "total_infra_capex": electrolyzer_capex + csd_capex - itc,
        "opex_fuel": opex_fuel,
        "station_opex": fixed_om + stack_replacement,
        "itc": itc,
        "itc_note": itc_note,
    }


def _hydrogen_option_annual_cost(option: Dict[str, Any]) -> float:
    return option["total_infra_capex"] / INFRA_LIFESPAN_YEARS + option["opex_fuel"] + option["station_opex"]


def select_hydrogen_supply(inputs: FleetInputPayload) -> Dict[str, Any]:
    """Models both hydrogen supply options and returns the one with the lower
    annualized station + fuel cost (vehicle costs are identical for both)."""
    region_info, province, is_canadian = _region_flags(inputs)
    delivered = _hydrogen_delivered_option(inputs, is_canadian)
    onsite = _hydrogen_onsite_option(inputs, region_info, province, is_canadian)
    if _hydrogen_option_annual_cost(onsite) < _hydrogen_option_annual_cost(delivered):
        chosen, other = onsite, delivered
    else:
        chosen, other = delivered, onsite
    return {"chosen": chosen, "other": other, "currency": "CAD" if is_canadian else "USD"}


_H2_SUPPLY_LABELS = {"delivered_liquid": "delivered liquid hydrogen", "onsite_electrolysis": "on-site electrolysis"}


def _calc_hydrogen_pathway(inputs: FleetInputPayload) -> Dict[str, Any]:
    h2 = _BASELINES["hydrogen"]
    fleet = inputs.fleet
    vt = fleet.vehicle_type

    from .assumptions_tracker import tracked_fx_conversion  # local import avoids load-order coupling

    region_info, province, is_canadian = _region_flags(inputs)

    if is_canadian:
        fx = _fx_rate_usd_to_cad()
        capex_vehicle_total = tracked_fx_conversion(h2["capex"][capex_key(vt)], fx) * fleet.vehicle_count
        maint_cpm = tracked_fx_conversion(h2["maintenance"][maintenance_key(vt)], fx)
        currency = "CAD"
    else:
        capex_vehicle_total = h2["capex"][capex_key(vt)]["default"] * fleet.vehicle_count
        maint_cpm = h2["maintenance"][maintenance_key(vt)]["default"]
        currency = "USD"

    selection = select_hydrogen_supply(inputs)
    chosen, other = selection["chosen"], selection["other"]

    total_miles = fleet.vehicle_count * fleet.annual_mileage_per_vehicle
    multiplier = _cold_climate_maintenance_multiplier("hydrogen", inputs.climate.cold_climate_flag)
    opex_maintenance = total_miles * maint_cpm * multiplier + chosen["station_opex"]

    notes = [
        f"Hydrogen supply: {_H2_SUPPLY_LABELS[chosen['supply']]} "
        f"({_money(_hydrogen_option_annual_cost(chosen), currency)}/yr station and fuel) chosen over "
        f"{_H2_SUPPLY_LABELS[other['supply']]} ({_money(_hydrogen_option_annual_cost(other), currency)}/yr)."
    ]
    if chosen["supply"] == "onsite_electrolysis" and chosen["itc_note"]:
        notes.append(chosen["itc_note"])
    elif region_info.get("country") == "CA":
        notes.append(
            "Clean Hydrogen ITC: not applied. A delivered-liquid station is refuelling equipment, "
            "which CRA excludes; the credit only covers on-site production equipment."
        )

    return {
        "capex_vehicle_total": capex_vehicle_total,
        "total_infra_capex": chosen["total_infra_capex"],
        "h2_itc_incentive_usd": chosen["itc"],  # in CAD for Canadian regions; name kept for API-shape continuity
        "hydrogen_supply": chosen["supply"],
        "opex_fuel": chosen["opex_fuel"],
        "opex_maintenance": opex_maintenance,
        "currency": currency,
        "notes": notes,
    }


def _calc_cng_pathway(inputs: FleetInputPayload) -> Dict[str, Any]:
    cng = _BASELINES["cng"]
    fleet = inputs.fleet
    vt = fleet.vehicle_type

    region_info = _resolve_region(inputs.region.state_prov)
    is_canadian = region_info.get("country") == "CA"

    from .assumptions_tracker import tracked_fx_conversion  # local import avoids load-order coupling

    infra = _calc_cng_infrastructure(fleet.vehicle_count, is_canadian)

    dge_per_mile = 1.0 / cng["fuel_economy"][fuel_economy_key(vt, "cng")]["default"]

    if is_canadian:
        fx = _fx_rate_usd_to_cad()
        capex_vehicle_total = tracked_fx_conversion(cng["capex"][capex_key(vt)], fx) * fleet.vehicle_count
        price_per_dge = tracked_fx_conversion(cng["fuel_price"]["default_price_dge"], fx)
        maint_cpm = tracked_fx_conversion(cng["maintenance"][maintenance_key(vt)], fx)
        currency = "CAD"
    else:
        capex_vehicle_total = cng["capex"][capex_key(vt)]["default"] * fleet.vehicle_count
        price_per_dge = cng["fuel_price"]["default_price_dge"]["default"]
        maint_cpm = cng["maintenance"][maintenance_key(vt)]["default"]
        currency = "USD"

    total_miles = fleet.vehicle_count * fleet.annual_mileage_per_vehicle
    dge_consumed = total_miles * dge_per_mile
    opex_fuel = dge_consumed * price_per_dge

    multiplier = _cold_climate_maintenance_multiplier("cng", inputs.climate.cold_climate_flag)
    opex_maintenance = total_miles * maint_cpm * multiplier

    station_label = "time-fill" if infra["station_type"] == "time_fill" else "fast-fill"
    return {
        "capex_vehicle_total": capex_vehicle_total,
        "total_infra_capex": infra["total_infra_capex"],
        "opex_fuel": opex_fuel,
        "opex_maintenance": opex_maintenance,
        "currency": currency,
        "notes": [f"CNG station: {station_label}."],
    }


_PATHWAY_CALCULATORS = {
    "diesel": _calc_diesel_pathway,
    "biodiesel": _calc_biodiesel_pathway,
    "bev": _calc_bev_pathway,
    "hydrogen": _calc_hydrogen_pathway,
    "cng": _calc_cng_pathway,
}


def calculate_pathway_tco(fuel_type: str, inputs: FleetInputPayload) -> PathwayOutputMetrics:
    if fuel_type not in _PATHWAY_CALCULATORS:
        raise ValueError(f"Unknown fuel_type: {fuel_type}")

    raw = _PATHWAY_CALCULATORS[fuel_type](inputs)

    capex_vehicle_amortized = _amortize_vehicle_capex(raw["capex_vehicle_total"], inputs.fleet.lifecycle_years)
    capex_infra_amortized = _amortize_infra_capex(raw["total_infra_capex"])
    user_incentives = inputs.overrides.incentive_credits_usd or 0.0
    if fuel_type == "diesel":
        incentives_applied = 0.0
        annualized_grant = 0.0
    else:
        h2_itc = raw.get("h2_itc_incentive_usd", 0.0)
        qc_pets = raw.get("qc_pets_incentive_cad", 0.0)
        incentives_applied = user_incentives + h2_itc + qc_pets
        # DISCLOSED CHANGE: treat user_incentives like PETS/ITC as upfront capital reduction,
        # subtracting grant / lifecycle_years from annualized tco_total instead of the whole grant.
        annualized_grant = user_incentives / inputs.fleet.lifecycle_years

    tco_total = (
        capex_vehicle_amortized
        + capex_infra_amortized
        + raw["opex_fuel"]
        + raw["opex_maintenance"]
        - annualized_grant
    )

    return PathwayOutputMetrics(
        fuel_type=fuel_type,
        currency=raw["currency"],
        tco_total=round(tco_total, 2),
        capex_vehicle_amortized=round(capex_vehicle_amortized, 2),
        capex_infra_amortized=round(capex_infra_amortized, 2),
        opex_fuel=round(raw["opex_fuel"], 2),
        opex_maintenance=round(raw["opex_maintenance"], 2),
        incentives_applied=round(incentives_applied, 2),
        lifecycle_co2e_tons=0.0,
        cold_climate_adjustment_applied=bool(inputs.climate.cold_climate_flag) and fuel_type in _COLD_ADJUSTED_PATHWAYS,
        hydrogen_supply=raw.get("hydrogen_supply"),
        pathway_notes=raw.get("notes", []),
    )


def calculate_all_pathways(inputs: FleetInputPayload) -> Dict[str, PathwayOutputMetrics]:
    return {ft: calculate_pathway_tco(ft, inputs) for ft in _PATHWAY_CALCULATORS}
