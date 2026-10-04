import pytest

from api.main import calculate_fleet_pathways
from engine.models import FleetInputPayload, OverridesConfig, RegionConfig
from engine.tco_calculator import calculate_pathway_tco


def test_zero_and_positive_price_overrides_are_used():
    baseline = FleetInputPayload()
    zero_price = FleetInputPayload(overrides=OverridesConfig(diesel_price_gal=0.0))
    high_price = FleetInputPayload(overrides=OverridesConfig(diesel_price_gal=20.0))

    baseline_result = calculate_pathway_tco("diesel", baseline)
    zero_result = calculate_pathway_tco("diesel", zero_price)
    high_result = calculate_pathway_tco("diesel", high_price)

    assert zero_result.opex_fuel == 0.0
    assert high_result.opex_fuel > baseline_result.opex_fuel


def test_electricity_override_changes_bev_cost_and_can_change_winner():
    # DISCLOSED CHANGE (grid-factor sourcing fix, side effect): the default
    # region (CA -> CAMX) previously won this scenario for bev due to
    # CAMX's uncorrected placeholder grid factor (400.0 lb/MWh, vs. the
    # real EPA eGRID2023 Rev 2 figure of 430.0). With CAMX corrected, cng
    # already wins the CA baseline, leaving no bev-winning state for the
    # override to flip away from. QC is used instead: its corrected grid
    # factor (2.8 lb/MWh, effectively zero-carbon hydro) plus its wired
    # PETS incentive reliably produce a bev-winning baseline, so the
    # override's winner-flip effect remains meaningfully testable.
    baseline = calculate_fleet_pathways(FleetInputPayload(region=RegionConfig(state_prov="QC")))
    adjusted = calculate_fleet_pathways(
        FleetInputPayload(
            region=RegionConfig(state_prov="QC"),
            overrides=OverridesConfig(electricity_rate_kwh=5.0)
        )
    )
    baseline_bev = next(path for path in baseline.pathways if path.fuel_type == "bev")
    adjusted_bev = next(path for path in adjusted.pathways if path.fuel_type == "bev")
    assert adjusted_bev.opex_fuel > baseline_bev.opex_fuel
    assert baseline.verdict.winner_pathway == "bev"
    assert adjusted.verdict.winner_pathway != baseline.verdict.winner_pathway


def test_incentive_override_reduces_non_diesel_pathway_cost():
    baseline = calculate_pathway_tco("bev", FleetInputPayload())
    adjusted = calculate_pathway_tco(
        "bev", FleetInputPayload(overrides=OverridesConfig(incentive_credits_usd=50000.0))
    )
    assert adjusted.incentives_applied == pytest.approx(50000.0)
    # DISCLOSED CHANGE: user grant is amortized over fleet lifecycle years (12 yr default)
    assert adjusted.tco_total == pytest.approx(baseline.tco_total - (50000.0 / 12.0), abs=0.01)


def test_incentive_override_does_not_reduce_diesel_baseline():
    baseline_diesel = calculate_pathway_tco("diesel", FleetInputPayload())
    result = calculate_pathway_tco(
        "diesel", FleetInputPayload(overrides=OverridesConfig(incentive_credits_usd=50000.0))
    )
    assert result.incentives_applied == 0.0
    # DISCLOSED CHANGE: diesel tco_total is not reduced by user incentives
    assert result.tco_total == pytest.approx(baseline_diesel.tco_total, abs=0.01)


def _send_post_request(body_dict):
    import asyncio
    import json
    from api.main import app

    body_bytes = json.dumps(body_dict).encode("utf-8")
    headers = [
        (b"host", b"testserver"),
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body_bytes)).encode("utf-8")),
    ]
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "path": "/api/v1/calculate",
        "raw_path": b"/api/v1/calculate",
        "query_string": b"",
        "headers": headers,
    }
    response_status = None
    response_body = []

    async def receive():
        return {"type": "http.request", "body": body_bytes, "more_body": False}

    async def send(message):
        nonlocal response_status, response_body
        if message["type"] == "http.response.start":
            response_status = message["status"]
        elif message["type"] == "http.response.body":
            response_body.append(message.get("body", b""))

    asyncio.run(app(scope, receive, send))
    parsed_json = json.loads(b"".join(response_body).decode("utf-8"))
    return response_status, parsed_json


def test_negative_overrides_rejected_at_schema_boundary():
    import pydantic

    # Direct Pydantic model validation
    with pytest.raises(pydantic.ValidationError):
        OverridesConfig(electricity_rate_kwh=-0.05)
    with pytest.raises(pydantic.ValidationError):
        OverridesConfig(diesel_price_gal=-1.0)
    with pytest.raises(pydantic.ValidationError):
        OverridesConfig(incentive_credits_usd=-500.0)

    # API HTTP endpoint validation
    status, body = _send_post_request({"overrides": {"electricity_rate_kwh": -0.05}})
    assert status == 422
    assert any("greater_than_equal" in str(err) for err in body.get("detail", []))

    status, body = _send_post_request({"overrides": {"diesel_price_gal": -1.0}})
    assert status == 422

    status, body = _send_post_request({"overrides": {"incentive_credits_usd": -500.0}})
    assert status == 422


def test_invalid_state_prov_length_rejected_with_422():
    import pydantic

    # Direct Pydantic model validation
    with pytest.raises(pydantic.ValidationError):
        RegionConfig(state_prov="")
    with pytest.raises(pydantic.ValidationError):
        RegionConfig(state_prov="A")

    # API HTTP endpoint validation
    status_empty, body_empty = _send_post_request({"region": {"state_prov": ""}})
    assert status_empty == 422

    status_1char, body_1char = _send_post_request({"region": {"state_prov": "A"}})
    assert status_1char == 422


def test_valid_scenario_request_accepted_with_200():
    status, body = _send_post_request({
        "region": {"state_prov": "QC"},
        "fleet": {
            "vehicle_type": "school_bus_typeC",
            "vehicle_count": 10,
            "annual_mileage_per_vehicle": 12000,
            "lifecycle_years": 12,
        },
        "overrides": {},
        "climate": {},
    })
    assert status == 200
    assert body["verdict"]["winner_pathway"] == "bev"
    assert len(body["pathways"]) == 5


def test_unknown_region_code_rejected_with_400():
    # DISCLOSED CHANGE: test that unsupported region code ZZ returns HTTP 400 naming the code
    status, body = _send_post_request({"region": {"state_prov": "ZZ"}})
    assert status == 400
    assert "ZZ" in body.get("detail", "")


