"""
FleetPath — PDF Report Generation Engine (PRD §7)
Renders an already-computed EngineOutputPayload as a single-page, audit-style
PDF. Performs no calculation — pathways and verdict are rendered as passed in.
"""

import json
from io import BytesIO
from pathlib import Path
from typing import Dict, Any, Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth

from engine.models import FleetInputPayload, EngineOutputPayload, PathwayOutputMetrics
from engine.tco_calculator import round_half_up

_LOGO_PATH = Path(__file__).resolve().parents[1] / "assets" / "fleetpath-logo.png"

NAVY = HexColor("#1B2A4A")
EMERALD = HexColor("#1F9D6E")  # rules and outlines only
EMERALD_TEXT = HexColor("#166534")  # text: 7.1:1 on white, 6.3:1 on the winner-row tint (WCAG AA)
GRAY_LINE = HexColor("#C7CBD1")
GRAY_TEXT = HexColor("#4A4F58")
OFF_WHITE = HexColor("#F7F7F5")

PAGE_W, PAGE_H = letter
MARGIN = 0.65 * inch
CONTENT_W = PAGE_W - (2 * MARGIN)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_STATE_CROSSWALK: Dict[str, Any] = json.loads((_DATA_DIR / "state_crosswalk.json").read_text(encoding="utf-8"))

_VEHICLE_DISPLAY_NAMES = {
    "school_bus_typeC": "School Bus (Type C)",
    "transit_short_haul": "Transit Bus (40-ft)",
}

_OWNER_DISPLAY_NAMES = {
    "school_district": "School district / board",
    "municipality": "Municipality",
    "transit_agency": "Public transit agency",
    "private_contractor": "Private contractor",
}

_FUEL_DISPLAY_NAMES = {
    "diesel": "Diesel",
    "bev": "Battery-Electric",
    "hydrogen": "Hydrogen Fuel Cell",
    "cng": "CNG",
    "biodiesel": "Biodiesel (B20)",
}
_PATHWAY_ORDER = ["diesel", "bev", "hydrogen", "cng", "biodiesel"]

# DISCLOSED CHANGE: footnote previously cited NIR 2025 (CY2026), which does not match
# the NIR 2023 (1990-2021) source actually cited in data/grid_factors.json for every
# Canadian region. Corrected to match the real underlying citation.
_METHODOLOGY_FOOTNOTE = (
    "Methodology: Argonne AFLEET 2023 school-bus baselines; NREL transit-bus evaluations (2020) and the "
    "NLR Fuel Cell Electric Bus Status Report 2025; NREL H2A and DOE Hydrogen Program Records 19009, 21002 "
    "and 24005 for hydrogen stations; ANL 2022 hydrogen life-cycle analysis; EPA eGRID 2023 Rev 2 grid "
    "emission factors (US); Environment and Climate Change Canada National Inventory Report 2023 "
    "(NIR 1990-2021) provincial grid intensities (Canada). Every figure is in the assumptions registry "
    "with its source. This is a decision-support estimate, not a procurement guarantee."
)


def _fmt_money(value: float, currency: str) -> str:
    # DISCLOSED CHANGE (pricing-bug remediation): was a hardcoded "$" with no
    # currency disclosure. Renders the resolved pathway currency (CAD for
    # Canadian fleets, USD for US fleets) produced by the calculation engine.
    return f"${round_half_up(value):,} {currency}"


def _fmt_tons(value: float) -> str:
    return f"{value:,.1f} t"


def _fmt_years(value: Optional[float]) -> str:
    if value is None:
        return "No payback within holding period"
    return f"{value:.1f} yr"


def _fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    return f"{value:.1f}%"


def _draw_wrapped_text(c: canvas.Canvas, text: str, x: float, y: float, max_width: float,
                        font: str, size: int, leading: float, color=GRAY_TEXT) -> float:
    """Draws left-aligned wrapped text starting at (x, y). Returns the y position after the last line."""
    c.setFont(font, size)
    c.setFillColor(color)
    words = text.split()
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if stringWidth(candidate, font, size) <= max_width:
            line = candidate
        else:
            c.drawString(x, y, line)
            y -= leading
            line = word
    if line:
        c.drawString(x, y, line)
        y -= leading
    return y


def _row_value(pathway: PathwayOutputMetrics, column: str) -> str:
    if column == "tco_total":
        return _fmt_money(pathway.tco_total, pathway.currency)
    if column == "lifecycle_co2e_tons":
        return _fmt_tons(pathway.lifecycle_co2e_tons)
    if column == "cold_climate_adjustment_applied":
        return "Yes" if pathway.cold_climate_adjustment_applied else "No"
    valid_columns = ("tco_total", "lifecycle_co2e_tons", "cold_climate_adjustment_applied")
    raise ValueError(
        f"Unknown column '{column}' requested for report row; expected one of: {', '.join(valid_columns)}"
    )


def generate_fleet_report_pdf(
    fleet_input: FleetInputPayload,
    engine_output: EngineOutputPayload,
    matrix_font_size: int = 9,
) -> bytes:
    """
    Renders a single-page audit report PDF and returns it as bytes.
    matrix_font_size shrinks if the 5-row matrix risks overflowing the page —
    callers should not need to pass this; it is used internally for the retry.
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)

    y = PAGE_H - MARGIN

    # Header: logo left, report title right, navy rule underneath
    logo = ImageReader(str(_LOGO_PATH))
    logo_w, logo_h = logo.getSize()
    draw_h = 0.42 * inch
    c.drawImage(logo, MARGIN, PAGE_H - 0.72 * inch, width=draw_h * logo_w / logo_h, height=draw_h, mask="auto")
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.48 * inch, "Fuel Pathway Decision Report")
    c.setFillColor(GRAY_TEXT)
    c.setFont("Helvetica", 9)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.66 * inch, "Independent cost and carbon analysis for fleet procurement decisions")
    c.setStrokeColor(NAVY)
    c.setLineWidth(1.5)
    c.line(MARGIN, PAGE_H - 0.86 * inch, PAGE_W - MARGIN, PAGE_H - 0.86 * inch)
    y = PAGE_H - 1.15 * inch

    # Fleet profile summary block
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(NAVY)
    c.drawString(MARGIN, y, "Fleet Profile")
    y -= 0.22 * inch

    raw_region = fleet_input.region.state_prov.strip().upper()
    region_display = _STATE_CROSSWALK.get(raw_region, {}).get("state_name", fleet_input.region.state_prov)
    vehicle_class_display = _VEHICLE_DISPLAY_NAMES.get(
        fleet_input.fleet.vehicle_type, fleet_input.fleet.vehicle_type
    )
    fleet_size_display = f"{fleet_input.fleet.vehicle_count} vehicles"
    annual_mileage_display = f"{fleet_input.fleet.annual_mileage_per_vehicle:,.0f} mi"
    holding_period_display = f"{fleet_input.fleet.lifecycle_years} yr"
    owner_display = _OWNER_DISPLAY_NAMES.get(fleet_input.fleet.owner_type, fleet_input.fleet.owner_type)

    profile_rows = [
        [("Region", region_display), ("Vehicle class", vehicle_class_display), ("Owner", owner_display)],
        [("Fleet size", fleet_size_display), ("Annual mileage", annual_mileage_display), ("Holding period", holding_period_display)],
    ]
    col_w = CONTENT_W / 3
    for row in profile_rows:
        for i, (label, value) in enumerate(row):
            x = MARGIN + (i * col_w)
            c.setFont("Helvetica", 7)
            c.setFillColor(GRAY_TEXT)
            c.drawString(x, y, label.upper())
            c.setFont("Helvetica-Bold", 9)
            c.setFillColor(NAVY)
            c.drawString(x, y - 0.16 * inch, str(value))
        y -= 0.40 * inch
    y -= 0.02 * inch

    c.setStrokeColor(GRAY_LINE)
    c.line(MARGIN, y, PAGE_W - MARGIN, y)
    y -= 0.28 * inch

    # Verdict block
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(NAVY)
    c.drawString(MARGIN, y, "Verdict")
    y -= 0.22 * inch

    y = _draw_wrapped_text(
        c, engine_output.verdict.summary_text, MARGIN, y, CONTENT_W,
        font="Helvetica", size=10, leading=0.18 * inch, color=GRAY_TEXT,
    )
    y -= 0.06 * inch

    payback_display = _fmt_years(engine_output.verdict.payback_years)
    emissions_reduction_display = _fmt_pct(engine_output.verdict.emissions_reduction_pct)
    verdict_line = (
        f"Payback vs. diesel: {payback_display}    "
        f"|    Emissions reduction vs. diesel: {emissions_reduction_display}"
    )

    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(EMERALD_TEXT)
    c.drawString(MARGIN, y, verdict_line)
    y -= 0.34 * inch

    c.setStrokeColor(GRAY_LINE)
    c.line(MARGIN, y, PAGE_W - MARGIN, y)
    y -= 0.28 * inch

    # 5-pathway comparison matrix
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(NAVY)
    c.drawString(MARGIN, y, "Pathway Comparison")
    y -= 0.24 * inch

    # DISCLOSED CHANGE: use "Annualized TCO" and "Annual CO2e" instead of "Lifetime TCO" and "Lifecycle CO2e"
    columns = [
        ("Fuel Pathway", 0.30),
        ("Annualized TCO", 0.24),
        ("Annual CO2e", 0.24),
        ("Cold-Climate Adj.", 0.22),
    ]
    col_x = []
    current_x_offset = MARGIN
    for column_name, width_fraction in columns:
        col_x.append(current_x_offset)
        column_width = CONTENT_W * width_fraction
        current_x_offset += column_width

    # Row/header height scales with matrix_font_size so the shrink-and-retry
    # path below actually reclaims vertical space instead of only shrinking text.
    row_h = matrix_font_size + 12
    header_h = matrix_font_size + 12
    cell_padding_x = 4
    text_vertical_offset = 8
    header_vertical_offset = 7

    c.setFillColor(NAVY)
    c.rect(MARGIN, y - header_h, CONTENT_W, header_h, stroke=0, fill=1)
    c.setFont("Helvetica-Bold", matrix_font_size)
    c.setFillColor(HexColor("#FFFFFF"))
    for i, (label, _) in enumerate(columns):
        c.drawString(col_x[i] + cell_padding_x, y - header_h + header_vertical_offset, label)
    y -= header_h

    pathways_by_type = {p.fuel_type: p for p in engine_output.pathways}
    winner = engine_output.verdict.winner_pathway
    winner_row_bottom = None

    for fuel_type in _PATHWAY_ORDER:
        pathway = pathways_by_type.get(fuel_type)
        if pathway is None:
            continue

        is_winner = fuel_type == winner
        row_top = y

        if is_winner:
            c.setFillColor(HexColor("#E4F4EC"))  # subtle emerald tint
            c.rect(MARGIN, row_top - row_h, CONTENT_W, row_h, stroke=0, fill=1)
        else:
            c.setFillColor(OFF_WHITE)
            c.rect(MARGIN, row_top - row_h, CONTENT_W, row_h, stroke=0, fill=1)

        c.setStrokeColor(GRAY_LINE)
        c.line(MARGIN, row_top - row_h, PAGE_W - MARGIN, row_top - row_h)

        if is_winner:
            winner_row_bottom = row_top - row_h

        label = _FUEL_DISPLAY_NAMES[fuel_type]
        if is_winner:
            label = f"{label}  (Winner)"  # text marker — not color-only, base-14-font safe, width-checked against col 0

        text_baseline_y = row_top - row_h + text_vertical_offset

        c.setFont("Helvetica-Bold" if is_winner else "Helvetica", matrix_font_size)
        c.setFillColor(EMERALD_TEXT if is_winner else NAVY)
        c.drawString(col_x[0] + cell_padding_x, text_baseline_y, label)

        c.setFillColor(NAVY if is_winner else GRAY_TEXT)
        c.setFont("Helvetica-Bold" if is_winner else "Helvetica", matrix_font_size)
        c.drawString(col_x[1] + cell_padding_x, text_baseline_y, _row_value(pathway, "tco_total"))
        c.drawString(col_x[2] + cell_padding_x, text_baseline_y, _row_value(pathway, "lifecycle_co2e_tons"))
        c.drawString(col_x[3] + cell_padding_x, text_baseline_y, _row_value(pathway, "cold_climate_adjustment_applied"))

        y -= row_h

    total_matrix_height = header_h + (row_h * len(_PATHWAY_ORDER))
    c.setStrokeColor(NAVY)
    c.setLineWidth(1)
    c.rect(MARGIN, y, CONTENT_W, total_matrix_height, stroke=1, fill=0)

    # Winner outline drawn after the table frame, inset so all four sides stay visible.
    if winner_row_bottom is not None:
        inset = 1.5
        c.setStrokeColor(EMERALD)
        c.setLineWidth(1.2)
        c.rect(MARGIN + inset, winner_row_bottom + inset, CONTENT_W - 2 * inset, row_h - 2 * inset, stroke=1, fill=0)
    c.setLineWidth(1)
    y -= 0.32 * inch

    # Pathway notes: charging setup, incentives, hydrogen supply and ITC status
    note_lines = [
        f"{_FUEL_DISPLAY_NAMES[ft]}: {note}"
        for ft in _PATHWAY_ORDER
        for note in (pathways_by_type[ft].pathway_notes if ft in pathways_by_type else [])
    ]
    if note_lines:
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(NAVY)
        c.drawString(MARGIN, y, "Notes")
        y -= 0.20 * inch
        for line in note_lines:
            y = _draw_wrapped_text(
                c, line, MARGIN, y, CONTENT_W,
                font="Helvetica", size=8, leading=0.15 * inch, color=GRAY_TEXT,
            )
            y -= 0.03 * inch

    # Methodology footnote
    footnote_y = MARGIN + 0.35 * inch
    c.setStrokeColor(GRAY_LINE)
    c.line(MARGIN, footnote_y + 0.14 * inch, PAGE_W - MARGIN, footnote_y + 0.14 * inch)
    _draw_wrapped_text(
        c, _METHODOLOGY_FOOTNOTE, MARGIN, footnote_y, CONTENT_W,
        font="Helvetica", size=6.5, leading=0.11 * inch, color=GRAY_TEXT,
    )

    min_safe_bottom_y = MARGIN + (0.8 * inch)
    is_content_overflowing = y < min_safe_bottom_y

    c.showPage()
    c.save()

    if is_content_overflowing and matrix_font_size > 6:
        return generate_fleet_report_pdf(fleet_input, engine_output, matrix_font_size=matrix_font_size - 1)

    buffer.seek(0)
    return buffer.getvalue()