import React, { useState } from "react";
import { COLORS, PATHWAY_LABELS, MONO_FONT, cellStyle, cellHeaderStyle, formatAssumptionValue } from "../styles";

export default function AssumptionsMatrix({ pathways, winnerPathway }) {
  const [selectedPathway, setSelectedPathway] = useState(winnerPathway || pathways[0]?.fuel_type || "diesel");
  const [tabAnimKey, setTabAnimKey] = useState(0);
  const [hoveredRow, setHoveredRow] = useState(null);
  const [hoveredTab, setHoveredTab] = useState(null);

  if (!pathways || pathways.length === 0) {
    return (
      <div style={{ padding: 16, color: COLORS.slateMuted, fontSize: 13, fontStyle: "italic" }}>
        No assumptions tracked for this fleet calculation.
      </div>
    );
  }

  const activePathwayData = pathways.find((p) => p.fuel_type === selectedPathway) || pathways[0];
  const assumptions = activePathwayData.assumptions || [];
  const overrideEntries = assumptions.filter((entry) => entry.is_override);
  const overrideCount = overrideEntries.length;
  const overrideNoun = overrideCount === 1 ? "Override" : "Overrides";

  function handleTabChange(fuelType) {
    if (fuelType !== selectedPathway) {
      setTabAnimKey((k) => k + 1);
      setSelectedPathway(fuelType);
      setHoveredRow(null);
    }
  }

  return (
    <div
      style={{
        marginTop: 14,
        marginBottom: 24,
        border: `1px solid ${COLORS.grayBorder}`,
        borderRadius: 8,
        background: "#FFFFFF",
        overflow: "hidden",
        boxShadow: "0 1px 2px rgba(0,0,0,0.03)",
      }}
    >
      {/* Header */}
      <div
        style={{
          background: COLORS.bgLight,
          borderBottom: `1px solid ${COLORS.grayBorder}`,
          padding: "10px 16px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 8,
        }}
      >
        <div>
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              color: COLORS.slateMuted,
              fontFamily: MONO_FONT,
            }}
          >
            Audit Provenance & Assumptions Registry
          </span>
        </div>
        <div style={{ fontSize: 12, color: COLORS.slateMuted }}>
          Parameters listed: <strong>{assumptions.length}</strong>
          {overrideCount > 0 && (
            <span style={{ marginLeft: 10, color: COLORS.amber, fontWeight: 600 }}>
              ({overrideCount} User {overrideNoun} Active)
            </span>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          borderBottom: `1px solid ${COLORS.grayBorder}`,
          background: "#FFFFFF",
          overflowX: "auto",
        }}
      >
        {pathways.map((p) => {
          const isSelected = p.fuel_type === selectedPathway;
          const isWinner = p.fuel_type === winnerPathway;
          const tabLabel = PATHWAY_LABELS[p.fuel_type] || p.fuel_type;
          const isTabHovered = hoveredTab === p.fuel_type;
          return (
            <button
              key={p.fuel_type}
              onClick={() => handleTabChange(p.fuel_type)}
              onMouseEnter={() => setHoveredTab(p.fuel_type)}
              onMouseLeave={() => setHoveredTab(null)}
              style={{
                padding: "10px 16px",
                border: "none",
                borderBottom: isSelected ? `2px solid ${COLORS.navy}` : "2px solid transparent",
                background: isSelected
                  ? "#FFFFFF"
                  : isTabHovered
                  ? "#F1F5F9"
                  : COLORS.bgLight,
                color: isSelected ? COLORS.navy : COLORS.slateMuted,
                fontWeight: isSelected ? 600 : 500,
                fontSize: 12,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 6,
                whiteSpace: "nowrap",
                fontFamily: "inherit",
                transition: "all 0.2s ease",
              }}
            >
              <span>{tabLabel}</span>
              {isWinner && (
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    color: COLORS.emeraldDark,
                    background: COLORS.emeraldBg,
                    border: `1px solid ${COLORS.emeraldBorder}`,
                    padding: "0 5px",
                    borderRadius: 8,
                  }}
                  aria-label="Winner"
                >
                  ✓
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Table with fade transition */}
      <div
        key={tabAnimKey}
        style={{
          overflowX: "auto",
          animation: "fp-fadeIn 0.25s ease forwards",
        }}
      >
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, textAlign: "left" }}>
          <thead>
            <tr>
              <th style={{ ...cellHeaderStyle, width: "24%" }}>Param ID</th>
              <th style={{ ...cellHeaderStyle, width: "28%" }}>Description / Parameter</th>
              <th style={{ ...cellHeaderStyle, width: "18%" }}>Value & Unit</th>
              <th style={{ ...cellHeaderStyle, width: "20%" }}>Source Authority</th>
              <th style={{ ...cellHeaderStyle, width: "10%", textAlign: "center" }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {assumptions.map((a) => {
              const displayValueWithUnit = formatAssumptionValue(a.value, a.unit);
              const isRowHovered = hoveredRow === a.param_id;
              const rowBackground = a.is_override
                ? isRowHovered ? "#FFF9E5" : "#FFFDF5"
                : isRowHovered ? COLORS.bgLight : "#FFFFFF";

              return (
                <tr
                  key={a.param_id}
                  onMouseEnter={() => setHoveredRow(a.param_id)}
                  onMouseLeave={() => setHoveredRow(null)}
                  style={{
                    background: rowBackground,
                    borderBottom: `1px solid ${COLORS.grayBorder}`,
                    transition: "background-color 0.15s ease",
                  }}
                >
                  <td
                    style={{
                      ...cellStyle,
                      fontFamily: MONO_FONT,
                      fontSize: 11,
                      color: COLORS.navy,
                      fontWeight: 600,
                    }}
                  >
                    {a.param_id}
                  </td>
                  <td style={cellStyle}>
                    <div style={{ fontWeight: 500, color: COLORS.navyDark }}>{a.label}</div>
                  </td>
                  <td
                    style={{
                      ...cellStyle,
                      fontFamily: MONO_FONT,
                      fontWeight: 600,
                      color: COLORS.slate,
                    }}
                  >
                    {displayValueWithUnit}
                  </td>
                  <td style={{ ...cellStyle, color: COLORS.slateMuted, fontSize: 11 }}>
                    {a.source_agency || "—"}
                  </td>
                  <td style={{ ...cellStyle, textAlign: "center" }}>
                    {a.is_override ? (
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          color: "#92400E",
                          background: COLORS.amberBg,
                          border: `1px solid #FDE68A`,
                          padding: "2px 6px",
                          borderRadius: 10,
                          display: "inline-block",
                        }}
                      >
                        Override
                      </span>
                    ) : (
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 600,
                          color: COLORS.slateMuted,
                          background: COLORS.bgLight,
                          border: `1px solid ${COLORS.grayBorder}`,
                          padding: "2px 6px",
                          borderRadius: 10,
                          display: "inline-block",
                        }}
                      >
                        Baseline
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
            {assumptions.length === 0 && (
              <tr>
                <td
                  colSpan={5}
                  style={{
                    ...cellStyle,
                    color: COLORS.slateMuted,
                    fontStyle: "italic",
                    textAlign: "center",
                    padding: 24,
                  }}
                >
                  No parameter assumptions logged for this pathway.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      <div
        style={{
          padding: "8px 16px",
          background: COLORS.bgLight,
          borderTop: `1px solid ${COLORS.grayBorder}`,
          fontSize: 11,
          color: COLORS.slateMuted,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <span>
          Every parameter lists its source. Values without a published source are labeled "Engineering estimate pending citation".
        </span>
      </div>
    </div>
  );
}
