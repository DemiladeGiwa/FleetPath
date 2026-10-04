"""
Validates the PDF report generator returns well-formed output across the
required edge cases: normal winner, diesel-as-winner, and a missing
payback_years value.
"""

from engine.models import (
    FleetInputPayload,
    RegionConfig,
    FleetConfig,
    OverridesConfig,
    ClimateConfig,
    EngineOutputPayload,
    VerdictConfig,
)
from engine.resolver import resolve_input_payload
from engine.tco_calculator import calculate_all_pathways
from engine.emissions_calculator import calculate_all_pathway_emissions
from api.report_generator import generate_fleet_report_pdf


def _build_engine_output(state_prov="IN", vehicle_count=10):
    payload = FleetInputPayload(
        region=RegionConfig(state_prov=state_prov),
        fleet=FleetConfig(
            vehicle_type="school_bus_typeC",
            vehicle_count=vehicle_count,
            annual_mileage_per_vehicle=12000,
            lifecycle_years=12,
        ),
        overrides=OverridesConfig(),
        climate=ClimateConfig(cold_climate_flag=None),
    )
    resolved = resolve_input_payload(payload)
    pathways = calculate_all_pathways(resolved)
    emissions = calculate_all_pathway_emissions(resolved)
    for fuel_type, result in pathways.items():
        result.lifecycle_co2e_tons = emissions[fuel_type]
    return resolved, list(pathways.values())


def test_generates_non_empty_pdf_bytes():
    resolved, pathway_list = _build_engine_output()
    verdict = VerdictConfig(
        winner_pathway="bev",
        summary_text="Battery-Electric wins: an estimated 4.2-year payback versus the diesel baseline.",
        payback_years=4.2,
        emissions_reduction_pct=68.0,
    )
    output = EngineOutputPayload(verdict=verdict, pathways=pathway_list)

    pdf_bytes = generate_fleet_report_pdf(resolved, output)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF")


def test_diesel_winner_does_not_throw():
    resolved, pathway_list = _build_engine_output()
    verdict = VerdictConfig(
        winner_pathway="diesel",
        summary_text=(
            "Diesel remains the lowest-cost, carbon-adjusted pathway for this fleet profile "
            "under current assumptions; no alternative pathway clears the cost-carbon utility threshold."
        ),
        payback_years=0.0,
        emissions_reduction_pct=0.0,
    )
    output = EngineOutputPayload(verdict=verdict, pathways=pathway_list)

    pdf_bytes = generate_fleet_report_pdf(resolved, output)

    assert len(pdf_bytes) > 0


def test_missing_payback_years_does_not_throw():
    resolved, pathway_list = _build_engine_output()
    verdict = VerdictConfig(
        winner_pathway="bev",
        summary_text="Battery-Electric wins on cost-carbon utility.",
        payback_years=None,
        emissions_reduction_pct=68.0,
    )
    output = EngineOutputPayload(verdict=verdict, pathways=pathway_list)

    pdf_bytes = generate_fleet_report_pdf(resolved, output)

    assert len(pdf_bytes) > 0


def test_methodology_footnote_nir_year_matches_grid_factors():
    import json
    from pathlib import Path
    from api.report_generator import _METHODOLOGY_FOOTNOTE

    grid_factors = json.loads((Path(__file__).resolve().parents[1] / "data" / "grid_factors.json").read_text(encoding="utf-8"))
    ca_sources = [
        entry["source_agency"]
        for entry in grid_factors.values()
        if "ECCC" in entry.get("source_agency", "")
    ]
    assert len(ca_sources) > 0

    # Ensure footnote cites the same NIR report edition and time period as grid_factors.json
    assert "National Inventory Report 2023" in _METHODOLOGY_FOOTNOTE
    assert "NIR 1990-2021" in _METHODOLOGY_FOOTNOTE
    for source in ca_sources:
        if "NIR 1990-2021" in source:
            assert "National Inventory Report 2023" in source


def test_fleet_profile_and_payback_labels_in_pdf():
    from io import BytesIO
    from pypdf import PdfReader

    resolved, pathway_list = _build_engine_output(state_prov="IN")
    verdict = VerdictConfig(
        winner_pathway="bev",
        summary_text="Battery-Electric wins.",
        payback_years=None,
        emissions_reduction_pct=68.0,
    )
    output = EngineOutputPayload(verdict=verdict, pathways=pathway_list)

    pdf_bytes = generate_fleet_report_pdf(resolved, output)
    reader = PdfReader(BytesIO(pdf_bytes))
    text = reader.pages[0].extract_text()

    assert "Indiana" in text
    assert "School Bus (Type C)" in text
    assert "No payback within holding period" in text
    assert "Battery-Electric  (Winner)" in text
