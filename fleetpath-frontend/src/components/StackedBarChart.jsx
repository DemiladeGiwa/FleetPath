import React, { useState, useEffect, useRef } from "react";
import { COLORS, PATHWAY_LABELS, MONO_FONT, formatMoney } from "../styles";

export default function StackedBarChart({ data }) {
  const [hoveredItem, setHoveredItem] = useState(null);
  const [animated, setAnimated] = useState(false);
  const chartRef = useRef(null);

  // Trigger bar grow animation when the component enters the viewport
  useEffect(() => {
    if (!chartRef.current) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          // Small delay so the CSS transition is visible
          requestAnimationFrame(() => setAnimated(true));
          observer.disconnect();
        }
      },
      { threshold: 0.2 }
    );
    observer.observe(chartRef.current);
    return () => observer.disconnect();
  }, []);

  if (!data || data.length === 0) {
    return (
      <div style={{ padding: 16, color: COLORS.slateMuted, fontSize: 13, fontStyle: "italic" }}>
        No TCO composition data available.
      </div>
    );
  }

  const currency = data[0]?.currency || "USD";

  const segments = [
    { key: "capex_vehicle_amortized", label: "Vehicle CapEx (Amortized)", short: "Vehicle", color: COLORS.navy },
    { key: "capex_infra_amortized", label: "Infra CapEx (Amortized)", short: "Infra", color: "#3B5A8A" },
    { key: "opex_fuel", label: "Annual Fuel/Energy OpEx", short: "Fuel", color: COLORS.emeraldDark },
    { key: "opex_maintenance", label: "Annual Maintenance OpEx", short: "Maint.", color: "#0D9488" },
  ];

  const rowData = data.map((item) => {
    const grossCostSum = segments.reduce((runningTotal, seg) => {
      const segmentAmount = Number(item[seg.key]) || 0;
      return runningTotal + segmentAmount;
    }, 0);

    const parsedNetTco = Number(item.tco_total);
    const netTco = Number.isNaN(parsedNetTco) ? grossCostSum : parsedNetTco;
    const incentivesApplied = Number(item.incentives_applied) || 0;

    return {
      ...item,
      grossTotal: grossCostSum,
      netTco,
      incentives: incentivesApplied,
    };
  });

  const maxVal = Math.max(...rowData.map((d) => d.grossTotal), 1);

  return (
    <div ref={chartRef} style={{ marginTop: 12, marginBottom: 20 }}>
      {/* Legend */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 16,
          marginBottom: 16,
          padding: "8px 12px",
          background: COLORS.bgLight,
          borderRadius: 6,
          border: `1px solid ${COLORS.grayBorder}`,
        }}
      >
        {segments.map((seg) => (
          <div key={seg.key} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
            <span
              style={{
                width: 12,
                height: 12,
                borderRadius: 3,
                backgroundColor: seg.color,
                display: "inline-block",
              }}
            />
            <span style={{ color: COLORS.slate, fontWeight: 500 }}>{seg.label}</span>
          </div>
        ))}
      </div>

      {/* Bars */}
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {rowData.map((d, rowIndex) => {
          const isHovered = hoveredItem === d.fuel_type;
          const pathwayDisplayName = PATHWAY_LABELS[d.fuel_type] || d.fuel_type;
          const formattedNetTco = formatMoney(d.netTco, d.currency || currency);

          return (
            <div
              key={d.fuel_type}
              onMouseEnter={() => setHoveredItem(d.fuel_type)}
              onMouseLeave={() => setHoveredItem(null)}
              style={{
                padding: "10px 12px",
                borderRadius: 6,
                background: isHovered ? COLORS.bgLight : "transparent",
                border: `1px solid ${isHovered ? COLORS.grayBorder : "transparent"}`,
                transition: "all 0.2s ease",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "baseline",
                  marginBottom: 6,
                }}
              >
                <span style={{ fontSize: 13, fontWeight: 600, color: COLORS.navyDark }}>
                  {pathwayDisplayName}
                </span>
                <span
                  style={{
                    fontSize: 13,
                    fontWeight: 700,
                    color: COLORS.navy,
                    fontFamily: MONO_FONT,
                  }}
                >
                  {formattedNetTco}
                </span>
              </div>

              {/* Stacked bar with grow animation */}
              <div
                style={{
                  display: "flex",
                  height: 28,
                  width: "100%",
                  backgroundColor: "#EEF2F6",
                  borderRadius: 4,
                  overflow: "hidden",
                }}
              >
                {segments.map((seg) => {
                  const segmentValue = Number(d[seg.key]) || 0;
                  const widthPercentage = (segmentValue / maxVal) * 100;
                  if (widthPercentage <= 0) return null;

                  const formattedSegmentCost = formatMoney(segmentValue, d.currency || currency);
                  const tooltipText = `${seg.label}: ${formattedSegmentCost}`;

                  return (
                    <div
                      key={seg.key}
                      title={tooltipText}
                      style={{
                        width: animated ? `${widthPercentage}%` : "0%",
                        backgroundColor: seg.color,
                        height: "100%",
                        position: "relative",
                        transition: `width 0.7s cubic-bezier(0.22, 1, 0.36, 1) ${rowIndex * 100 + 100}ms`,
                        opacity: animated ? 1 : 0,
                      }}
                    />
                  );
                })}
              </div>

              {/* Segment breakdown */}
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: 12,
                  marginTop: 6,
                  fontSize: 11,
                  color: COLORS.slateMuted,
                }}
              >
                {segments.map((seg) => {
                  const segmentValue = Number(d[seg.key]) || 0;
                  const shortSegmentName = seg.short;
                  const formattedSegmentCost = formatMoney(segmentValue, d.currency || currency);

                  return (
                    <span key={seg.key}>
                      <strong style={{ color: COLORS.slate }}>{shortSegmentName}:</strong>{" "}
                      {formattedSegmentCost}
                    </span>
                  );
                })}
                {/* DISCLOSED CHANGE (2e Option 1): clarify that statutory capital incentives are lifetime and already reflected in amortized capital above */}
                {d.incentives > 0 && (
                  <span style={{ color: COLORS.emeraldDark, fontWeight: 500 }}>
                    Upfront incentives of {formatMoney(d.incentives, d.currency || currency)} (one-time total, not per year) were netted from capital before amortization
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
