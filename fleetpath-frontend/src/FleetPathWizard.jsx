import React, { useState, useRef } from "react";
import { COLORS } from "./styles";
import WizardSteps from "./components/WizardSteps";
import ResultsView from "./components/ResultsView";
import logoUrl from "./assets/fleetpath-logo.png";

// Set VITE_API_BASE at build time to point at a deployed API; local dev defaults to port 8000.
const API_BASE = (import.meta.env.VITE_API_BASE || "http://localhost:8000").replace(/\/$/, "");
const API_URL = `${API_BASE}/api/v1/calculate`;
const REPORT_URL = `${API_BASE}/api/v1/report`;

/* ── CSS injected once, globally ─────────────────────────── */
const GLOBAL_CSS = `
  input:focus, select:focus, button:focus-visible, summary:focus-visible {
    outline: 2px solid ${COLORS.navy};
    outline-offset: 2px;
  }
  /* hide default focus ring for mouse clicks */
  button:focus:not(:focus-visible), summary:focus:not(:focus-visible) {
    outline: none;
  }

  @keyframes fp-spinner {
    to { transform: rotate(360deg); }
  }
  .fp-spinner {
    display: inline-block;
    width: 14px;
    height: 14px;
    border: 2px solid currentColor;
    border-top-color: transparent;
    border-radius: 50%;
    animation: fp-spinner 0.6s linear infinite;
    vertical-align: middle;
  }

  @keyframes fp-fadeSlideIn {
    from { opacity: 0; transform: translateY(12px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  .fp-fade-slide-in {
    animation: fp-fadeSlideIn 0.4s cubic-bezier(0.22, 1, 0.36, 1) forwards;
  }

  @keyframes fp-fadeIn {
    from { opacity: 0; }
    to   { opacity: 1; }
  }
  .fp-fade-in {
    animation: fp-fadeIn 0.3s ease forwards;
  }

  /* Custom range slider styling */
  input[type="range"] {
    -webkit-appearance: none;
    appearance: none;
    width: 100%;
    height: 6px;
    border-radius: 3px;
    background: ${COLORS.grayBorder};
    outline: none;
    cursor: pointer;
  }
  input[type="range"]::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: ${COLORS.navy};
    border: 2px solid #FFFFFF;
    box-shadow: 0 1px 3px rgba(0,0,0,0.2);
    cursor: pointer;
    transition: transform 0.15s ease;
  }
  input[type="range"]::-webkit-slider-thumb:hover {
    transform: scale(1.15);
  }
  input[type="range"]::-moz-range-thumb {
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: ${COLORS.navy};
    border: 2px solid #FFFFFF;
    box-shadow: 0 1px 3px rgba(0,0,0,0.2);
    cursor: pointer;
  }

  /* Select styling */
  select {
    -webkit-appearance: none;
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath d='M2 4l4 4 4-4' fill='none' stroke='%23475569' stroke-width='1.5' stroke-linecap='round'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 12px center;
    padding-right: 32px !important;
  }

  /* Better input focus glow */
  input:focus, select:focus {
    border-color: ${COLORS.navy} !important;
    box-shadow: 0 0 0 3px rgba(27,42,74,0.08) !important;
  }

  .fp-loader-ring {
    animation: fp-spinner 0.8s linear infinite;
  }

  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 0.001ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.001ms !important;
      scroll-behavior: auto !important;
    }
    .fp-loader-ring, .fp-spinner { animation: none !important; }
  }

  /* Scrollbar styling */
  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb {
    background: ${COLORS.grayBorderDark};
    border-radius: 3px;
  }
  ::-webkit-scrollbar-thumb:hover { background: ${COLORS.slateLight}; }
`;

/* ── Loading state ───────────────────────────────────────── */
function CalculationLoader() {
  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "60px 24px",
        gap: 16,
      }}
    >
      <div
        aria-hidden="true"
        className="fp-loader-ring"
        style={{
          width: 40,
          height: 40,
          border: `3px solid ${COLORS.grayBorder}`,
          borderTopColor: COLORS.navy,
          borderRadius: "50%",
        }}
      />
      <div style={{ fontSize: 15, fontWeight: 600, color: COLORS.navy }}>Calculating…</div>
    </div>
  );
}

/* ── Main component ──────────────────────────────────────── */
export default function FleetPathWizard() {
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    state_prov: "",
    vehicle_type: "school_bus_typeC",
    owner_type: "",
    vehicle_count: 10,
    annual_mileage_per_vehicle: 12000,
    lifecycle_years: 12,
    electricity_rate_kwh: "",
    diesel_price_gal: "",
    incentive_credits_usd: "",
    cold_climate_flag: null,
    cost_carbon_weight: null,
  });
  const [result, setResult] = useState(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfError, setPdfError] = useState(null);
  const [stepAnimKey, setStepAnimKey] = useState(0);
  const contentRef = useRef(null);

  function updateField(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  function changeStep(newStep) {
    setStepAnimKey((k) => k + 1);
    setStep(newStep);
    if (contentRef.current) {
      const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
      contentRef.current.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
    }
  }

  function toNullableFloat(value) {
    if (value === "" || value === null || value === undefined) return null;
    const parsed = parseFloat(value);
    return Number.isNaN(parsed) ? null : parsed;
  }

  function buildCalculationPayload() {
    const region = { state_prov: form.state_prov };
    const fleet = {
      vehicle_type: form.vehicle_type,
      owner_type: form.owner_type,
      vehicle_count: Number(form.vehicle_count),
      annual_mileage_per_vehicle: Number(form.annual_mileage_per_vehicle),
      lifecycle_years: Number(form.lifecycle_years),
    };
    const overrides = {
      electricity_rate_kwh: toNullableFloat(form.electricity_rate_kwh),
      diesel_price_gal: toNullableFloat(form.diesel_price_gal),
      incentive_credits_usd: toNullableFloat(form.incentive_credits_usd),
      cost_carbon_weight: form.cost_carbon_weight,
    };
    const climate = { cold_climate_flag: form.cold_climate_flag };

    return { region, fleet, overrides, climate };
  }

  async function submitFleet() {
    setLoading(true);
    setError(null);
    const payload = buildCalculationPayload();

    try {
      const response = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        let errMsg = "Calculation failed";
        try {
          const body = await response.json();
          if (body.detail) {
            if (typeof body.detail === "string") {
              errMsg = body.detail;
            } else if (Array.isArray(body.detail)) {
              errMsg = body.detail.map((d) => d.msg || JSON.stringify(d)).join(", ");
            } else {
              errMsg = JSON.stringify(body.detail);
            }
          }
        } catch (_) {
          errMsg = `Calculation failed (status ${response.status}): ${response.statusText}`;
        }
        throw new Error(errMsg);
      }
      const data = await response.json();
      setResult(data);
      setStepAnimKey((k) => k + 1);
      setStep(4);
    } catch (err) {
      if (err.name === "TypeError" || err.message?.includes("fetch") || err.message?.includes("NetworkError")) {
        setError("Unable to reach the calculation service. Please verify that the backend server is running on port 8000.");
      } else {
        setError(err.message || "An unexpected error occurred during calculation.");
      }
    } finally {
      setLoading(false);
    }
  }

  async function downloadPdfReport() {
    if (!result) return;
    setPdfLoading(true);
    setPdfError(null);
    const payload = buildCalculationPayload();

    try {
      const response = await fetch(REPORT_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        let errMsg = "Failed to download PDF report";
        try {
          const body = await response.json();
          if (body.detail) {
            if (typeof body.detail === "string") {
              errMsg = body.detail;
            } else if (Array.isArray(body.detail)) {
              errMsg = body.detail.map((d) => d.msg || JSON.stringify(d)).join(", ");
            } else {
              errMsg = JSON.stringify(body.detail);
            }
          }
        } catch (_) {
          errMsg = `Download failed with status ${response.status}: ${response.statusText}`;
        }
        throw new Error(errMsg);
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `fleetpath_report_${form.state_prov}.pdf`);
      document.body.appendChild(link);
      link.click();
      if (link.parentNode) {
        link.parentNode.removeChild(link);
      }
      window.URL.revokeObjectURL(url);
    } catch (err) {
      if (err.name === "TypeError" || err.message?.includes("fetch") || err.message?.includes("NetworkError")) {
        setPdfError("Unable to reach the report service. Please verify that the backend server is running on port 8000.");
      } else {
        setPdfError(err.message || "Failed to download PDF report.");
      }
    } finally {
      setPdfLoading(false);
    }
  }

  function handleStartNew() {
    setStep(1);
    setForm({
      state_prov: "",
      vehicle_type: "school_bus_typeC",
      owner_type: "",
      vehicle_count: 10,
      annual_mileage_per_vehicle: 12000,
      lifecycle_years: 12,
      electricity_rate_kwh: "",
      diesel_price_gal: "",
      incentive_credits_usd: "",
      cold_climate_flag: null,
      cost_carbon_weight: null,
    });
    setResult(null);
    setAdvancedOpen(false);
    setError(null);
    setPdfError(null);
    setPdfLoading(false);
    setStepAnimKey((k) => k + 1);
  }

  function handleEditInputs() {
    setError(null);
    setPdfError(null);
    setStepAnimKey((k) => k + 1);
    setStep(3);
  }

  const stepsList = [
    { num: 1, label: "Jurisdiction" },
    { num: 2, label: "Fleet Profile" },
    { num: 3, label: "Financials" },
    { num: 4, label: "Decision Matrix" },
  ];

  const isResultsView = step === 4;

  return (
    <div
      style={{
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        maxWidth: isResultsView ? 1020 : 680,
        margin: "0 auto",
        padding: "32px 20px 48px",
        color: COLORS.navyDark,
        minHeight: "100vh",
        transition: "max-width 0.4s cubic-bezier(0.22, 1, 0.36, 1)",
      }}
    >
      <style>{GLOBAL_CSS}</style>

      {/* ── Header ──────────────────────────────── */}
      <header style={{ marginBottom: 28 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 6 }}>
          <h1 style={{ margin: 0, lineHeight: 0 }}>
            <img src={logoUrl} alt="FleetPath" width={193} height={36} style={{ display: "block", height: 36, width: "auto" }} />
          </h1>
          <span
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: COLORS.slateMuted,
              background: COLORS.bgLight,
              border: `1px solid ${COLORS.grayBorder}`,
              padding: "2px 6px",
              borderRadius: 3,
              fontFamily: "'JetBrains Mono', ui-monospace, monospace",
            }}
          >
            v1.0
          </span>
        </div>
        <p style={{ fontSize: 13, color: COLORS.slateMuted, margin: 0, lineHeight: 1.5 }}>
          Independent fuel pathway total cost of ownership and carbon verdict engine for public-sector fleets.
        </p>

        {/* ── Stepper ─────────────────────────────── */}
        <nav
          style={{
            display: "flex",
            alignItems: "center",
            marginTop: 20,
            borderBottom: `1px solid ${COLORS.grayBorder}`,
            paddingBottom: 12,
            gap: 6,
            overflowX: "auto",
          }}
          aria-label="Progress"
        >
          {stepsList.map((s, idx) => {
            const isCurrent = step === s.num;
            const isPast = step > s.num;
            return (
              <React.Fragment key={s.num}>
                {idx > 0 && (
                  <div
                    style={{
                      flex: "0 0 24px",
                      height: 2,
                      backgroundColor: isPast ? COLORS.emerald : COLORS.grayBorder,
                      borderRadius: 1,
                      transition: "background-color 0.3s ease",
                    }}
                  />
                )}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    fontSize: 12,
                    fontWeight: isCurrent ? 700 : 500,
                    color: isCurrent ? COLORS.navy : isPast ? COLORS.emeraldDark : COLORS.slateMuted,
                    whiteSpace: "nowrap",
                    transition: "color 0.3s ease",
                  }}
                >
                  <span
                    style={{
                      width: 22,
                      height: 22,
                      borderRadius: "50%",
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 11,
                      fontWeight: 700,
                      backgroundColor: isCurrent
                        ? COLORS.navy
                        : isPast
                        ? COLORS.emeraldBg
                        : COLORS.bgLight,
                      color: isCurrent ? "#FFFFFF" : isPast ? COLORS.emeraldDark : COLORS.slateMuted,
                      border: `1.5px solid ${
                        isCurrent
                          ? COLORS.navy
                          : isPast
                          ? COLORS.emeraldBorder
                          : COLORS.grayBorder
                      }`,
                      transition: "all 0.3s ease",
                    }}
                  >
                    {isPast ? "✓" : s.num}
                  </span>
                  <span>{s.label}</span>
                </div>
              </React.Fragment>
            );
          })}
        </nav>
      </header>

      {/* ── Content ──────────────────────────────── */}
      <main ref={contentRef}>
        {loading ? (
          <CalculationLoader />
        ) : step < 4 ? (
          <div key={stepAnimKey} className="fp-fade-slide-in">
            <WizardSteps
              step={step}
              setStep={changeStep}
              form={form}
              updateField={updateField}
              submitFleet={submitFleet}
              loading={loading}
              error={error}
            />
          </div>
        ) : (
          result && (
            <div key={`results-${stepAnimKey}`} className="fp-fade-slide-in">
              <ResultsView
                result={result}
                advancedOpen={advancedOpen}
                setAdvancedOpen={setAdvancedOpen}
                downloadPdfReport={downloadPdfReport}
                pdfLoading={pdfLoading}
                pdfError={pdfError}
                onEditInputs={handleEditInputs}
                onStartNew={handleStartNew}
              />
            </div>
          )
        )}
      </main>
    </div>
  );
}
