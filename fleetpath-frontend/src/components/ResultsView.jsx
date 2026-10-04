import React, { useState } from "react";
import {
  COLORS,
  PATHWAY_LABELS,
  MONO_FONT,
  cardStyle,
  cellStyle,
  cellHeaderStyle,
  formatMoney,
  formatTons,
  formatYears,
  formatPct,
} from "../styles";
import StackedBarChart from "./StackedBarChart";
import PaybackLineChart from "./PaybackLineChart";
import AssumptionsMatrix from "./AssumptionsMatrix";

/* ── Stagger helper ────────────────────────────────────── */
function StaggeredChild({ index, children }) {
  return (
    <div
      style={{
        opacity: 0,
        animation: `fp-fadeSlideIn 0.45s cubic-bezier(0.22, 1, 0.36, 1) ${index * 80}ms forwards`,
      }}
    >
      {children}
    </div>
  );
}

export default function ResultsView({
  result,
  advancedOpen,
  setAdvancedOpen,
  downloadPdfReport,
  pdfLoading,
  pdfError,
  onEditInputs,
  onStartNew,
}) {
  if (!result || !result.verdict || !result.pathways) {
    return null;
  }

  const { verdict, pathways, advanced } = result;
  const currency = pathways[0]?.currency || "USD";
  const winner = verdict.winner_pathway;
  const winnerData = pathways.find((p) => p.fuel_type === winner) || pathways[0];
  const dieselData = pathways.find((p) => p.fuel_type === "diesel") || pathways[0];

  const [hoveredRow, setHoveredRow] = useState(null);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* ── Hero Verdict Card ────────────────────── */}
      <StaggeredChild index={0}>
        <div
          style={{
            ...cardStyle,
            padding: "28px 28px 24px",
            background: "#FFFFFF",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-start",
              flexWrap: "wrap",
              gap: 16,
              marginBottom: 16,
            }}
          >
            <div>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  color: COLORS.emeraldDark,
                  marginBottom: 6,
                }}
              >
                Recommended Pathway
              </div>
              <h2
                style={{
                  fontSize: 30,
                  fontWeight: 800,
                  color: COLORS.navy,
                  margin: 0,
                  lineHeight: 1.15,
                  letterSpacing: "-0.01em",
                }}
              >
                {PATHWAY_LABELS[winner] || winner}
              </h2>
            </div>

            <div
              style={{
                textAlign: "right",
                background: COLORS.bgLight,
                padding: "12px 18px",
                borderRadius: 8,
                border: `1px solid ${COLORS.grayBorder}`,
                minWidth: 180,
              }}
            >
              {/* DISCLOSED CHANGE: use Annualized TCO instead of Lifetime TCO */}
              <div style={{ fontSize: 11, fontWeight: 600, color: COLORS.slateMuted, textTransform: "uppercase", marginBottom: 2 }}>
                Annualized TCO ({currency})
              </div>
              <div
                style={{
                  fontSize: 26,
                  fontWeight: 800,
                  color: COLORS.navyDark,
                  fontFamily: MONO_FONT,
                  letterSpacing: "-0.02em",
                }}
              >
                {formatMoney(winnerData?.tco_total, currency)}
              </div>
            </div>
          </div>

          <p
            style={{
              fontSize: 14,
              lineHeight: 1.6,
              color: COLORS.slate,
              margin: "0 0 20px 0",
              maxWidth: 640,
            }}
          >
            {verdict.summary_text}
          </p>

          {/* ── Stat pills ──────────────────────────── */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
              gap: 10,
              paddingTop: 16,
              borderTop: `1px solid ${COLORS.grayBorder}`,
              marginBottom: 20,
            }}
          >
            <div style={{ background: COLORS.bgLight, padding: "12px 14px", borderRadius: 6, border: `1px solid ${COLORS.grayBorder}` }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: COLORS.slateMuted, textTransform: "uppercase", marginBottom: 2 }}>
                Payback vs Diesel
              </div>
              <div style={{ fontSize: 16, fontWeight: 700, color: COLORS.navyDark }}>
                {formatYears(verdict.payback_years)}
              </div>
            </div>

            <div style={{ background: COLORS.bgLight, padding: "12px 14px", borderRadius: 6, border: `1px solid ${COLORS.grayBorder}` }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: COLORS.slateMuted, textTransform: "uppercase", marginBottom: 2 }}>
                CO₂e Reduction
              </div>
              <div
                style={{
                  fontSize: 16,
                  fontWeight: 700,
                  color: verdict.emissions_reduction_pct > 0 ? COLORS.emeraldDark : COLORS.slate,
                }}
              >
                {formatPct(verdict.emissions_reduction_pct)}
              </div>
            </div>

            {/* DISCLOSED CHANGE: use Annual Emissions instead of Lifetime Emissions */}
            <div style={{ background: COLORS.bgLight, padding: "12px 14px", borderRadius: 6, border: `1px solid ${COLORS.grayBorder}` }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: COLORS.slateMuted, textTransform: "uppercase", marginBottom: 2 }}>
                Annual Emissions
              </div>
              <div style={{ fontSize: 16, fontWeight: 700, color: COLORS.navyDark }}>
                {formatTons(winnerData?.lifecycle_co2e_tons)}
              </div>
            </div>

            <div style={{ background: COLORS.bgLight, padding: "12px 14px", borderRadius: 6, border: `1px solid ${COLORS.grayBorder}` }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: COLORS.slateMuted, textTransform: "uppercase", marginBottom: 2 }}>
                Currency Standard
              </div>
              <div style={{ fontSize: 16, fontWeight: 700, color: COLORS.navyDark }}>
                {currency} Native
              </div>
            </div>
          </div>

          {/* ── Actions ─────────────────────────────── */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 12,
            }}
          >
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <button
                onClick={downloadPdfReport}
                disabled={pdfLoading}
                style={{
                  background: pdfLoading ? "#94A3B8" : COLORS.navy,
                  border: "none",
                  color: "#FFFFFF",
                  padding: "10px 18px",
                  borderRadius: 6,
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: pdfLoading ? "not-allowed" : "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  boxShadow: pdfLoading ? "none" : "0 1px 3px rgba(27,42,74,0.2)",
                  transition: "all 0.2s ease",
                }}
              >
                {pdfLoading && <span className="fp-spinner" aria-hidden="true" />}
                {pdfLoading ? "Generating Report..." : "Download PDF Audit Report"}
              </button>
              <button
                onClick={onEditInputs}
                style={{
                  background: "#FFFFFF",
                  border: `1px solid ${COLORS.grayBorderDark}`,
                  color: COLORS.slate,
                  padding: "10px 16px",
                  borderRadius: 6,
                  fontSize: 13,
                  fontWeight: 500,
                  cursor: "pointer",
                  transition: "all 0.2s ease",
                }}
              >
                ← Edit Inputs & Overrides
              </button>
            </div>

            <button
              onClick={onStartNew}
              style={{
                background: "none",
                border: "none",
                color: COLORS.slateMuted,
                cursor: "pointer",
                fontSize: 12,
                textDecoration: "underline",
                padding: 0,
                transition: "color 0.15s ease",
              }}
            >
              Start a new calculation
            </button>
          </div>

          {pdfError && (
            <div
              style={{
                background: COLORS.dangerBg,
                border: `1px solid ${COLORS.dangerBorder}`,
                padding: "10px 14px",
                borderRadius: 6,
                color: COLORS.danger,
                fontSize: 13,
                marginTop: 14,
              }}
            >
              <strong>Report Generation Error:</strong> {pdfError}
            </div>
          )}
        </div>
      </StaggeredChild>

      {/* ── Decision Matrix Card ─────────────────── */}
      <StaggeredChild index={1}>
        <div style={cardStyle}>
          <div style={{ marginBottom: 14 }}>
            <h3 style={{ fontSize: 17, fontWeight: 700, color: COLORS.navy, margin: "0 0 4px 0" }}>
              5-Pathway Decision Matrix
            </h3>
            <p style={{ fontSize: 12, color: COLORS.slateMuted, margin: 0 }}>
              Side-by-side total cost of ownership and carbon comparison against the diesel baseline.
            </p>
          </div>

          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, textAlign: "left" }}>
              <thead>
                <tr>
                  <th style={{ ...cellHeaderStyle, width: "26%" }}>Fuel Pathway</th>
                  {/* DISCLOSED CHANGE: use Annualized TCO and Annual CO2e in table headers */}
                  <th style={{ ...cellHeaderStyle, width: "22%" }}>Annualized TCO</th>
                  <th style={{ ...cellHeaderStyle, width: "18%" }}>Cost Delta</th>
                  <th style={{ ...cellHeaderStyle, width: "18%" }}>Annual CO₂e</th>
                  <th style={{ ...cellHeaderStyle, width: "16%", textAlign: "center" }}>Verdict</th>
                </tr>
              </thead>
              <tbody>
                {pathways.map((p) => {
                  const isWinner = p.fuel_type === winner;
                  const isDiesel = p.fuel_type === "diesel";
                  const baselineDieselTco = dieselData?.tco_total || 0;
                  const currentPathwayTco = p.tco_total;
                  const deltaCostVsBaseline = currentPathwayTco - baselineDieselTco;
                  const isLowerCostThanDiesel = deltaCostVsBaseline < 0;
                  const absoluteDeltaCost = Math.abs(deltaCostVsBaseline);
                  const formattedDeltaAmount = formatMoney(absoluteDeltaCost, p.currency || currency);
                  const pathwayLabel = PATHWAY_LABELS[p.fuel_type] || p.fuel_type;
                  const isHovered = hoveredRow === p.fuel_type;

                  return (
                    <tr
                      key={p.fuel_type}
                      onMouseEnter={() => setHoveredRow(p.fuel_type)}
                      onMouseLeave={() => setHoveredRow(null)}
                      style={{
                        background: isWinner
                          ? "rgba(31, 157, 110, 0.05)"
                          : isHovered
                          ? "#F8FAFC"
                          : "#FFFFFF",
                        borderBottom: `1px solid ${COLORS.grayBorder}`,
                        transition: "background-color 0.15s ease",
                        cursor: "default",
                      }}
                    >
                      <td style={cellStyle}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <span style={{ fontWeight: isWinner ? 700 : 600, color: COLORS.navyDark }}>
                            {pathwayLabel}
                          </span>
                          {isDiesel && (
                            <span
                              style={{
                                fontSize: 10,
                                color: COLORS.slateMuted,
                                background: COLORS.bgLight,
                                border: `1px solid ${COLORS.grayBorder}`,
                                padding: "1px 5px",
                                borderRadius: 3,
                                fontWeight: 500,
                              }}
                            >
                              Baseline
                            </span>
                          )}
                        </div>
                      </td>
                      <td
                        style={{
                          ...cellStyle,
                          fontFamily: MONO_FONT,
                          fontWeight: isWinner ? 700 : 500,
                          color: isWinner ? COLORS.navy : COLORS.navyDark,
                        }}
                      >
                        {formatMoney(p.tco_total, p.currency || currency)}
                      </td>
                      <td
                        style={{
                          ...cellStyle,
                          fontFamily: MONO_FONT,
                          fontSize: 12,
                        }}
                      >
                        {isDiesel ? (
                          <span style={{ color: COLORS.slateMuted }}>$0 (Baseline)</span>
                        ) : isLowerCostThanDiesel ? (
                          <span style={{ color: COLORS.emeraldDark, fontWeight: 600 }}>
                            -{formattedDeltaAmount}
                          </span>
                        ) : (
                          <span style={{ color: COLORS.slateMuted }}>
                            +{formattedDeltaAmount}
                          </span>
                        )}
                      </td>
                      <td
                        style={{
                          ...cellStyle,
                          fontFamily: MONO_FONT,
                        }}
                      >
                        {formatTons(p.lifecycle_co2e_tons)}
                      </td>
                      <td style={{ ...cellStyle, textAlign: "center" }}>
                        {isWinner ? (
                          <span
                            style={{
                              fontSize: 11,
                              fontWeight: 700,
                              color: COLORS.emeraldDark,
                              background: COLORS.emeraldBg,
                              border: `1px solid ${COLORS.emeraldBorder}`,
                              padding: "2px 10px",
                              borderRadius: 10,
                              display: "inline-block",
                              letterSpacing: "0.02em",
                            }}
                          >
                            ✓ Winner
                          </span>
                        ) : (
                          <span style={{ color: COLORS.slateLight, fontSize: 12 }}>—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </StaggeredChild>

      {/* ── Pathway notes ─────────────────────────── */}
      {pathways.some((p) => (p.pathway_notes || []).length > 0) && (
        <StaggeredChild index={2}>
          <div style={cardStyle}>
            <h3 style={{ fontSize: 15, fontWeight: 700, color: COLORS.navy, margin: "0 0 8px 0" }}>Notes</h3>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: COLORS.slate, lineHeight: 1.6 }}>
              {pathways.flatMap((p) =>
                (p.pathway_notes || []).map((note, i) => (
                  <li key={`${p.fuel_type}-${i}`}>
                    <strong style={{ color: COLORS.navyDark }}>{PATHWAY_LABELS[p.fuel_type] || p.fuel_type}:</strong>{" "}
                    {note}
                  </li>
                ))
              )}
            </ul>
          </div>
        </StaggeredChild>
      )}

      {/* ── Advanced Fiduciary Audit Dashboard ──── */}
      <StaggeredChild index={3}>
        <div style={cardStyle}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 12,
            }}
          >
            <div>
              <h3 style={{ fontSize: 17, fontWeight: 700, color: COLORS.navy, margin: "0 0 2px 0" }}>
                Advanced Fiduciary Audit Dashboard
              </h3>
              <p style={{ fontSize: 12, color: COLORS.slateMuted, margin: 0 }}>
                Granular CapEx/OpEx component breakdown, cumulative payback curves, and assumption provenance.
              </p>
            </div>
            <button
              onClick={() => setAdvancedOpen(!advancedOpen)}
              style={{
                background: advancedOpen ? COLORS.navy : "#FFFFFF",
                border: `1px solid ${COLORS.navy}`,
                color: advancedOpen ? "#FFFFFF" : COLORS.navy,
                padding: "8px 16px",
                borderRadius: 6,
                cursor: "pointer",
                fontSize: 13,
                fontWeight: 600,
                transition: "all 0.2s ease",
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              {advancedOpen ? "Hide Dashboard" : "Show Dashboard"}
              <span style={{
                display: "inline-block",
                transition: "transform 0.25s ease",
                transform: advancedOpen ? "rotate(180deg)" : "rotate(0deg)",
                fontSize: 10,
              }}>
                ▼
              </span>
            </button>
          </div>

          {advancedOpen && (
            <div
              className="fp-fade-slide-in"
              style={{ marginTop: 24, paddingTop: 20, borderTop: `1px solid ${COLORS.grayBorder}` }}
            >
              <div style={{ marginBottom: 32 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
                  <h4 style={{ fontSize: 15, fontWeight: 700, color: COLORS.navy, margin: 0 }}>
                    TCO Composition Breakdown
                  </h4>
                  <span style={{ fontSize: 11, color: COLORS.slateMuted }}>
                    Amortized Vehicle & Infra CapEx + Annualized OpEx ({currency})
                  </span>
                </div>
                <StackedBarChart data={advanced?.tco_composition || pathways} />
              </div>

              <div style={{ marginBottom: 32 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
                  <h4 style={{ fontSize: 15, fontWeight: 700, color: COLORS.navy, margin: 0 }}>
                    Cumulative Payback Trajectory
                  </h4>
                  <span style={{ fontSize: 11, color: COLORS.slateMuted }}>
                    Cumulative expenditure from Year 0 upfront capital to horizon ({currency})
                  </span>
                </div>
                <PaybackLineChart
                  vectors={advanced?.payback_vector || []}
                  yearsAxis={advanced?.payback_vector_years_axis || []}
                />
              </div>

              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
                  <h4 style={{ fontSize: 15, fontWeight: 700, color: COLORS.navy, margin: 0 }}>
                    Verifiable Assumptions & Provenance Registry
                  </h4>
                  <span style={{ fontSize: 11, color: COLORS.slateMuted }}>
                    Individual citations and user overrides by pathway
                  </span>
                </div>
                <AssumptionsMatrix pathways={pathways} winnerPathway={winner} />
              </div>
            </div>
          )}
        </div>
      </StaggeredChild>
    </div>
  );
}
