export const COLORS = {
  navy: "#1B2A4A",
  navyDark: "#0F172A",
  slate: "#334155",
  slateMuted: "#475569",
  slateLight: "#64748B",
  emerald: "#1F9D6E",
  emeraldDark: "#15803D",
  emeraldBg: "#F0FDF4",
  emeraldBorder: "#86EFAC",
  grayBorder: "#E2E8F0",
  grayBorderDark: "#CBD5E1",
  bgLight: "#F8FAFC",
  bgCard: "#FFFFFF",
  danger: "#B91C1C",
  dangerBg: "#FEF2F2",
  dangerBorder: "#FCA5A5",
  amber: "#B45309",
  amberBg: "#FFFBEB",
  blue: "#0284C7",
  purple: "#7C3AED",
  rust: "#C2410C",
};

export const PATHWAY_LABELS = {
  diesel: "Diesel",
  bev: "Battery-Electric",
  hydrogen: "Hydrogen Fuel Cell",
  cng: "CNG",
  biodiesel: "Biodiesel (B20)",
};

// DISCLOSED CHANGE: trimmed to states with real crosswalk/grid-factor data.
// NY/MI/OH/PA/IL/CO previously listed but caused UnknownRegionError on submit.
// Re-add only after real eGRID sourcing + crosswalk/grid_factors entries exist.
export const US_STATES = ["IN", "CA", "TX", "WA"];
export const CA_PROVINCES = ["ON", "QC", "BC", "AB", "NB"];

// Only classes with sourced baselines. Utility trucks (Class 4-6) return
// once they have sourced data; the API rejects them until then.
export const VEHICLE_TYPES = [
  { value: "school_bus_typeC", label: "School Bus (Type C)" },
  { value: "transit_short_haul", label: "Transit Bus (40-ft)" },
];

export const OWNER_TYPES = [
  { value: "school_district", label: "School district / board" },
  { value: "municipality", label: "Municipality" },
  { value: "transit_agency", label: "Public transit agency" },
  { value: "private_contractor", label: "Private contractor (corporation)" },
];

export const MONO_FONT = "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace";

export function formatMoney(value, currency = "USD") {
  if (value === null || value === undefined) {
    return "—";
  }
  const numericValue = Number(value);
  if (Number.isNaN(numericValue)) {
    return "—";
  }
  const roundedAmount = Math.round(numericValue);
  const formattedNumber = roundedAmount.toLocaleString("en-US");
  return `$${formattedNumber} ${currency}`;
}

export function formatTons(value) {
  if (value === null || value === undefined) {
    return "—";
  }
  const numericValue = Number(value);
  if (Number.isNaN(numericValue)) {
    return "—";
  }
  const formattedTons = numericValue.toLocaleString("en-US", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
  return `${formattedTons} t`;
}

export const NO_PAYBACK_TEXT = "No payback within holding period";

export function formatYears(value) {
  if (value === null || value === undefined) {
    return NO_PAYBACK_TEXT;
  }
  const numericValue = Number(value);
  if (Number.isNaN(numericValue)) {
    return NO_PAYBACK_TEXT;
  }
  const formattedYears = numericValue.toFixed(1);
  return `${formattedYears} yrs`;
}

// Baseline values whose unit starts with "fraction" are stored as fractions
// (0.005 = 0.5%); show them as percentages so the registry reads correctly.
export function formatAssumptionValue(value, unit) {
  const numericValue = Number(value);
  if (unit && unit.startsWith("fraction") && !Number.isNaN(numericValue)) {
    const pct = (numericValue * 100).toLocaleString("en-US", { maximumFractionDigits: 2 });
    return `${pct}%${unit.replace(/^fraction/, "")}`;
  }
  if (typeof value === "number") {
    return `${value.toLocaleString("en-US", { maximumFractionDigits: 4 })}${unit ? ` ${unit}` : ""}`;
  }
  return `${value}${unit ? ` ${unit}` : ""}`;
}

export function formatPct(value) {
  if (value === null || value === undefined) {
    return "—";
  }
  const numericValue = Number(value);
  if (Number.isNaN(numericValue)) {
    return "—";
  }
  const formattedPercent = numericValue.toFixed(1);
  return `${formattedPercent}%`;
}

export const cardStyle = {
  background: COLORS.bgCard,
  border: `1px solid ${COLORS.grayBorder}`,
  borderRadius: 10,
  padding: 28,
  boxShadow: "0 1px 3px 0 rgba(0,0,0,0.04), 0 1px 2px -1px rgba(0,0,0,0.03)",
};

export const errorStyle = {
  color: COLORS.danger,
  fontSize: 12,
  marginTop: 4,
  marginBottom: 0,
};

export const cellStyle = {
  borderBottom: `1px solid ${COLORS.grayBorder}`,
  padding: "10px 12px",
  textAlign: "left",
  fontSize: 13,
  color: COLORS.navyDark,
};

export const cellHeaderStyle = {
  borderBottom: `2px solid ${COLORS.grayBorder}`,
  padding: "10px 12px",
  textAlign: "left",
  fontSize: 11,
  fontWeight: 600,
  letterSpacing: "0.05em",
  textTransform: "uppercase",
  color: COLORS.slateMuted,
  background: COLORS.bgLight,
};

export const labelStyle = {
  display: "block",
  fontSize: 13,
  fontWeight: 500,
  color: COLORS.slate,
  marginTop: 14,
  marginBottom: 4,
};

export const inputStyle = {
  width: "100%",
  padding: "10px 12px",
  border: `1px solid ${COLORS.grayBorderDark}`,
  borderRadius: 6,
  fontSize: 14,
  color: COLORS.navyDark,
  backgroundColor: "#FFFFFF",
  boxSizing: "border-box",
  fontFamily: "inherit",
  transition: "border-color 0.2s ease, box-shadow 0.2s ease",
};

export const secondaryButtonStyle = {
  background: "#FFFFFF",
  border: `1px solid ${COLORS.grayBorderDark}`,
  color: COLORS.slate,
  padding: "10px 20px",
  borderRadius: 6,
  cursor: "pointer",
  fontSize: 13,
  fontWeight: 500,
  transition: "all 0.2s ease",
};

export function primaryButtonStyle(disabled) {
  return {
    background: disabled ? "#94A3B8" : COLORS.navy,
    border: "none",
    color: "#FFFFFF",
    padding: "10px 22px",
    borderRadius: 6,
    cursor: disabled ? "not-allowed" : "pointer",
    fontSize: 13,
    fontWeight: 600,
    letterSpacing: "0.01em",
    transition: "all 0.2s ease",
    boxShadow: disabled ? "none" : "0 1px 2px rgba(27,42,74,0.2)",
  };
}
