"""
Maps each supported vehicle class to the baseline keys it reads in
afleet_baselines.json. Shared by tco_calculator.py and
emissions_calculator.py so both select the same per-class figures.

Utility trucks (Class 4-6) are not listed: no sourced baselines exist yet,
and FleetConfig.vehicle_type rejects them at the API boundary.
"""

from typing import Dict

SUPPORTED_VEHICLE_TYPES = ("school_bus_typeC", "transit_short_haul")

_CLASS_KEYS: Dict[str, Dict[str, object]] = {
    "school_bus_typeC": {
        "capex": "vehicle_bus_usd",
        "maintenance": "cost_per_mile_usd",
        "fuel_economy": {
            "diesel": "bus_mpg",
            "biodiesel": "bus_mpg",
            "bev": "school_bus_kwh_per_mile",
            "hydrogen": "bus_kg_per_mile",
            "cng": "bus_dge_per_mile",
        },
    },
    "transit_short_haul": {
        "capex": "vehicle_transit_usd",
        "maintenance": "transit_cost_per_mile_usd",
        "fuel_economy": {
            "diesel": "transit_mpg",
            "biodiesel": "transit_mpg",
            "bev": "transit_bus_kwh_per_mile",
            "hydrogen": "transit_kg_per_mile",
            "cng": "transit_miles_per_dge",
        },
    },
}


def capex_key(vehicle_type: str) -> str:
    return _CLASS_KEYS[vehicle_type]["capex"]


def maintenance_key(vehicle_type: str) -> str:
    return _CLASS_KEYS[vehicle_type]["maintenance"]


def fuel_economy_key(vehicle_type: str, pathway: str) -> str:
    return _CLASS_KEYS[vehicle_type]["fuel_economy"][pathway]
