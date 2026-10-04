import React, { useState, useEffect, useRef } from "react";
import { COLORS, PATHWAY_LABELS, MONO_FONT, formatMoney } from "../styles";

export default function PaybackLineChart({ vectors, yearsAxis }) {
  const [hoveredYear, setHoveredYear] = useState(null);
  const [animated, setAnimated] = useState(false);
  const chartRef = useRef(null);

  // Trigger line draw animation
  useEffect(() => {
    if (!chartRef.current) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          requestAnimationFrame(() => setAnimated(true));
          observer.disconnect();
        }
      },
      { threshold: 0.2 }
    );
    observer.observe(chartRef.current);
    return () => observer.disconnect();
  }, []);

  if (!vectors || vectors.length === 0 || !yearsAxis || yearsAxis.length === 0) {
    return (
      <div style={{ padding: 16, color: COLORS.slateMuted, fontSize: 13, fontStyle: "italic" }}>
        No payback trajectory data available.
      </div>
    );
  }

  const currency = vectors[0]?.currency || "USD";

  const totalWidth = 720;
  const totalHeight = 340;
  const paddingLeft = 85;
  const paddingRight = 25;
  const paddingTop = 25;
  const paddingBottom = 40;
  const chartPlotWidth = totalWidth - paddingLeft - paddingRight;
  const chartPlotHeight = totalHeight - paddingTop - paddingBottom;

  const allValues = vectors.flatMap((v) => v.cumulative_cost_by_year || []);
  if (allValues.length === 0) {
    return null;
  }

  const maxVal = Math.max(...allValues, 1000);
  const minVal = Math.min(...allValues, 0);
  const valRange = maxVal - minVal || 1;

  const lineColors = {
    diesel: COLORS.navy,
    bev: COLORS.emeraldDark,
    hydrogen: COLORS.blue,
    cng: COLORS.rust,
    biodiesel: COLORS.purple,
  };

  const getXCoordinate = (yearIndex) => {
    const totalYearSteps = yearsAxis.length - 1;
    const progressFraction = yearIndex / (totalYearSteps || 1);
    return paddingLeft + (progressFraction * chartPlotWidth);
  };

  const getYCoordinate = (costValue) => {
    const normalizedHeightFraction = (costValue - minVal) / valRange;
    const yOffsetFromBottom = normalizedHeightFraction * chartPlotHeight;
    return paddingTop + chartPlotHeight - yOffsetFromBottom;
  };

  // Generate 4-5 Y-axis grid tick levels
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((ratio) => minVal + (ratio * valRange));

  const formatShortMoney = (val) => {
    const numericVal = Number(val);
    if (numericVal >= 1_000_000) {
      const millions = (numericVal / 1_000_000).toFixed(1);
      return `$${millions}M`;
    }
    if (numericVal >= 1_000) {
      const thousands = Math.round(numericVal / 1_000);
      return `$${thousands}k`;
    }
    return `$${Math.round(numericVal)}`;
  };

  // Compute total polyline length for stroke-dasharray animation
  function computePolylineLength(points) {
    let length = 0;
    for (let i = 1; i < points.length; i++) {
      const dx = points[i].x - points[i - 1].x;
      const dy = points[i].y - points[i - 1].y;
      length += Math.sqrt(dx * dx + dy * dy);
    }
    return length;
  }

  // Handle mouse move for crosshair
  function handleMouseMove(e) {
    const svg = chartRef.current?.querySelector("svg");
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const mouseX = ((e.clientX - rect.left) / rect.width) * totalWidth;
    const relX = mouseX - paddingLeft;
    if (relX < 0 || relX > chartPlotWidth) {
      setHoveredYear(null);
      return;
    }
    const totalSteps = yearsAxis.length - 1;
    const idx = Math.round((relX / chartPlotWidth) * totalSteps);
    setHoveredYear(Math.max(0, Math.min(idx, totalSteps)));
  }

  return (
    <div ref={chartRef} style={{ marginTop: 12, marginBottom: 20 }}>
      {/* Legend with cumulative total at horizon */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 16,
          marginBottom: 14,
          padding: "8px 12px",
          background: COLORS.bgLight,
          borderRadius: 6,
          border: `1px solid ${COLORS.grayBorder}`,
        }}
      >
        {vectors.map((v) => {
          const finalCost = v.cumulative_cost_by_year?.[v.cumulative_cost_by_year.length - 1];
          const pathwayLabel = PATHWAY_LABELS[v.fuel_type] || v.fuel_type;
          const pathwayColor = lineColors[v.fuel_type] || COLORS.slate;
          return (
            <div key={v.fuel_type} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
              <span
                style={{
                  width: 14,
                  height: 3,
                  backgroundColor: pathwayColor,
                  display: "inline-block",
                  borderRadius: 1,
                }}
              />
              <span style={{ fontWeight: 600, color: COLORS.navyDark }}>
                {pathwayLabel}:
              </span>
              <span style={{ color: COLORS.slateMuted, fontFamily: MONO_FONT, fontSize: 11 }}>
                {formatMoney(finalCost, v.currency || currency)}
              </span>
            </div>
          );
        })}
      </div>

      {/* Chart */}
      <div
        style={{ width: "100%", overflowX: "auto", position: "relative" }}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoveredYear(null)}
      >
        <svg
          viewBox={`0 0 ${totalWidth} ${totalHeight}`}
          style={{ width: "100%", maxWidth: totalWidth, height: "auto", display: "block" }}
        >
          {/* Grid lines */}
          {yTicks.map((tickVal, i) => {
            const y = getYCoordinate(tickVal);
            return (
              <g key={i}>
                <line
                  x1={paddingLeft}
                  y1={y}
                  x2={paddingLeft + chartPlotWidth}
                  y2={y}
                  stroke="#E2E8F0"
                  strokeDasharray="3 3"
                />
                <text
                  x={paddingLeft - 10}
                  y={y + 4}
                  fontSize="11"
                  textAnchor="end"
                  fill={COLORS.slateMuted}
                  fontFamily="'Inter', sans-serif"
                >
                  {formatShortMoney(tickVal)} {currency}
                </text>
              </g>
            );
          })}

          {/* X-axis ticks */}
          {yearsAxis.map((year, idx) => {
            // Show first, last, and every 2-3 years to avoid clutter
            const totalYears = yearsAxis.length;
            const tickInterval = Math.ceil(totalYears / 6);
            const isFirstYear = idx === 0;
            const isLastYear = idx === totalYears - 1;
            const isIntervalTick = idx % tickInterval === 0;
            const showTick = isFirstYear || isLastYear || isIntervalTick;

            if (!showTick) return null;
            const x = getXCoordinate(idx);
            const axisBaselineY = paddingTop + chartPlotHeight;

            return (
              <g key={year}>
                <line
                  x1={x}
                  y1={axisBaselineY}
                  x2={x}
                  y2={axisBaselineY + 5}
                  stroke="#94A3B8"
                />
                <text
                  x={x}
                  y={axisBaselineY + 18}
                  fontSize="11"
                  textAnchor="middle"
                  fill={COLORS.slate}
                  fontFamily="'Inter', sans-serif"
                >
                  Yr {year}
                </text>
              </g>
            );
          })}

          {/* Hover crosshair */}
          {hoveredYear !== null && (
            <line
              x1={getXCoordinate(hoveredYear)}
              y1={paddingTop}
              x2={getXCoordinate(hoveredYear)}
              y2={paddingTop + chartPlotHeight}
              stroke={COLORS.slateMuted}
              strokeWidth="1"
              strokeDasharray="4 2"
              opacity="0.5"
            />
          )}

          {/* Data lines */}
          {vectors.map((v, lineIdx) => {
            const cumulativeCosts = v.cumulative_cost_by_year || [];
            const points = cumulativeCosts.map((val, idx) => ({
              x: getXCoordinate(idx),
              y: getYCoordinate(val),
            }));

            const svgPolylinePoints = points.map((p) => `${p.x},${p.y}`).join(" ");
            const isDiesel = v.fuel_type === "diesel";
            const lineColor = lineColors[v.fuel_type] || COLORS.slate;
            const totalLength = computePolylineLength(points);

            return (
              <g key={v.fuel_type}>
                <polyline
                  points={svgPolylinePoints}
                  fill="none"
                  stroke={lineColor}
                  strokeWidth={isDiesel ? "2.5" : "2"}
                  strokeDasharray={
                    animated
                      ? isDiesel ? "4 3" : undefined
                      : `${totalLength} ${totalLength}`
                  }
                  strokeDashoffset={animated ? 0 : totalLength}
                  style={{
                    transition: animated
                      ? `stroke-dashoffset 1.2s cubic-bezier(0.22, 1, 0.36, 1) ${lineIdx * 150}ms`
                      : "none",
                  }}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                {/* Data points — show all when hovered, just endpoints otherwise */}
                {cumulativeCosts.map((val, idx) => {
                  const isEndpoint = idx === 0 || idx === cumulativeCosts.length - 1;
                  const isHoveredPoint = hoveredYear === idx;
                  const showDot = isEndpoint || isHoveredPoint;
                  if (!showDot) return null;

                  return (
                    <circle
                      key={idx}
                      cx={getXCoordinate(idx)}
                      cy={getYCoordinate(val)}
                      r={isHoveredPoint ? 5 : 3}
                      fill={lineColor}
                      stroke="#FFFFFF"
                      strokeWidth={isHoveredPoint ? 2 : 1}
                      style={{ transition: "r 0.15s ease" }}
                    />
                  );
                })}
              </g>
            );
          })}

          {/* Hover value labels */}
          {hoveredYear !== null && vectors.map((v) => {
            const cost = v.cumulative_cost_by_year?.[hoveredYear];
            if (cost === undefined) return null;
            const lineColor = lineColors[v.fuel_type] || COLORS.slate;
            const x = getXCoordinate(hoveredYear);
            const y = getYCoordinate(cost);

            return (
              <text
                key={`label-${v.fuel_type}`}
                x={x + 8}
                y={y - 6}
                fontSize="10"
                fill={lineColor}
                fontWeight="600"
                fontFamily="'JetBrains Mono', monospace"
              >
                {formatShortMoney(cost)}
              </text>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
