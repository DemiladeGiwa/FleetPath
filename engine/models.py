from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Union


class RegionConfig(BaseModel):
    # DISCLOSED CHANGE (region-code boundary validation): an empty or
    # 1-character region code previously reached resolve_input_payload()
    # unvalidated and would fail deeper in the stack rather than at the API
    # boundary; now rejected with a clean 422.
    state_prov: str = Field(
        default="IN",
        min_length=2,
        max_length=2,
        description="2-letter US state or Canadian province postal abbreviation",
    )


class FleetConfig(BaseModel):
    # Only classes with sourced baselines are accepted (see engine/vehicle_classes.py).
    # Anything else, including utility_medium_duty, is rejected with a 422.
    vehicle_type: Literal["school_bus_typeC", "transit_short_haul"] = Field(
        default="school_bus_typeC",
        description="Vehicle classification type identifier",
    )
    # Who owns the fleet. Only private_contractor (a taxable Canadian corporation)
    # can claim the Clean Hydrogen ITC; the public-body types cannot.
    owner_type: Literal["school_district", "municipality", "transit_agency", "private_contractor"] = Field(
        default="school_district",
        description="Fleet owner type; gates tax-credit eligibility",
    )
    vehicle_count: int = Field(
        default=10,
        gt=0,
        description="Number of vehicles in fleet (minimum 1)",
    )
    annual_mileage_per_vehicle: float = Field(
        default=12000.0,
        gt=0.0,
        description="Annual miles operated per vehicle",
    )
    lifecycle_years: int = Field(
        default=12,
        gt=0,
        description="Fleet lifecycle analysis horizon in years",
    )


class OverridesConfig(BaseModel):
    # NOTE: these overrides remain currency-unlabeled inputs. Not addressed
    # in this change set -- flagged separately, see delivery notes.
    # DISCLOSED CHANGE (override arithmetic safety): a negative override
    # previously flowed directly into arithmetic and produced silently distorted
    # TCO/OpEx sums with no error; now rejected with a clean 422.
    electricity_rate_kwh: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Optional override for electricity rate per kWh",
    )
    diesel_price_gal: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Optional override for diesel reference price per gallon",
    )
    incentive_credits_usd: Optional[float] = Field(
        default=0.0,
        ge=0.0,
        description="Optional total upfront purchase incentive or rebate credits",
    )
    # DISCLOSED CHANGE (scoring-policy control): exposes the verdict
    # scorer's cost/carbon blend weight as a real user input instead of a
    # silent hardcoded 0.6. None resolves to that same 0.6 default in
    # api/main.py, so an unset value changes nothing for existing callers.
    # Represents "weight given to cost"; carbon weight is 1 - this value.
    cost_carbon_weight: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="User-selected weight given to cost vs. carbon in the verdict utility score; None uses the 0.6 default",
    )


class ClimateConfig(BaseModel):
    cold_climate_flag: Optional[bool] = Field(
        default=None,
        description="Explicit cold-climate flag; None defers to regional crosswalk table lookup",
    )


class FleetInputPayload(BaseModel):
    region: RegionConfig = Field(default_factory=RegionConfig)
    fleet: FleetConfig = Field(default_factory=FleetConfig)
    overrides: OverridesConfig = Field(default_factory=OverridesConfig)
    climate: ClimateConfig = Field(default_factory=ClimateConfig)


class AssumptionEntry(BaseModel):
    param_id: str
    label: str
    value: Union[float, str]
    unit: str
    source_agency: str
    is_override: bool


class PathwayOutputMetrics(BaseModel):
    fuel_type: str
    currency: Literal["USD", "CAD"]
    tco_total: float
    capex_vehicle_amortized: float
    capex_infra_amortized: float
    opex_fuel: float
    opex_maintenance: float
    incentives_applied: float
    lifecycle_co2e_tons: float
    cold_climate_adjustment_applied: bool
    hydrogen_supply: Optional[Literal["delivered_liquid", "onsite_electrolysis"]] = None
    pathway_notes: List[str] = Field(default_factory=list)
    assumptions: List[AssumptionEntry] = Field(default_factory=list)


class VerdictConfig(BaseModel):
    winner_pathway: str
    summary_text: str
    payback_years: Optional[float] = None
    emissions_reduction_pct: float


class PaybackVectorItem(BaseModel):
    fuel_type: str
    currency: Literal["USD", "CAD"]
    cumulative_cost_by_year: List[float]


class AdvancedDashboardPayload(BaseModel):
    tco_composition: List[PathwayOutputMetrics] = Field(default_factory=list)
    payback_vector: List[PaybackVectorItem] = Field(default_factory=list)
    payback_vector_years_axis: List[int] = Field(default_factory=list)


class EngineOutputPayload(BaseModel):
    verdict: VerdictConfig
    pathways: List[PathwayOutputMetrics]
    advanced: Optional[AdvancedDashboardPayload] = None
