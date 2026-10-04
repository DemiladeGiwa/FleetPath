import React from "react";
import {
  COLORS,
  US_STATES,
  CA_PROVINCES,
  VEHICLE_TYPES,
  OWNER_TYPES,
  cardStyle,
  labelStyle,
  inputStyle,
  errorStyle,
  secondaryButtonStyle,
  primaryButtonStyle,
} from "../styles";

export function getVehicleCountError(val) {
  if (val === "" || val === null || val === undefined) return "Vehicle count is required.";
  const num = Number(val);
  if (isNaN(num) || !Number.isInteger(num) || num < 1) {
    return "Vehicle count must be an integer of 1 or more.";
  }
  return null;
}

export function getMileageError(val) {
  if (val === "" || val === null || val === undefined) return "Annual mileage is required.";
  const num = Number(val);
  if (isNaN(num) || num <= 0) {
    return "Annual mileage must be greater than 0.";
  }
  if (num > 200000) {
    return "Annual mileage per vehicle cannot exceed 200,000 miles.";
  }
  return null;
}

export function getLifecycleYearsError(val) {
  if (val === "" || val === null || val === undefined) return "Holding horizon is required.";
  const num = Number(val);
  if (isNaN(num) || !Number.isInteger(num) || num < 1 || num > 30) {
    return "Vehicle holding horizon must be an integer between 1 and 30 years.";
  }
  return null;
}

export function getNonNegativeError(val, fieldName) {
  if (val === "" || val === null || val === undefined) return null;
  const num = Number(val);
  if (Number.isNaN(num)) {
    return `${fieldName} must be a valid number or be left blank to use the regional baseline.`;
  }
  if (num < 0) {
    return `${fieldName} cannot be negative.`;
  }
  return null;
}

function FieldError({ message }) {
  if (!message) return null;
  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: 6,
        marginTop: 6,
        padding: "6px 10px",
        background: COLORS.dangerBg,
        borderRadius: 4,
        border: `1px solid ${COLORS.dangerBorder}`,
      }}
      className="fp-fade-in"
    >
      <span style={{ color: COLORS.danger, fontSize: 13, lineHeight: 1, flexShrink: 0 }}>⚠</span>
      <span style={{ ...errorStyle, marginTop: 0, lineHeight: 1.3 }}>{message}</span>
    </div>
  );
}

export function StepCard({ title, subtitle, children }) {
  return (
    <div style={cardStyle}>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: COLORS.navy, margin: "0 0 4px 0" }}>
          {title}
        </h2>
        {subtitle && (
          <p style={{ fontSize: 13, color: COLORS.slateMuted, margin: 0, lineHeight: 1.5 }}>
            {subtitle}
          </p>
        )}
      </div>
      {children}
    </div>
  );
}

export function NavButtons({ onBack, onNext, disabled, nextLabel = "Next", loading = false }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        marginTop: 28,
        paddingTop: 18,
        borderTop: `1px solid ${COLORS.grayBorder}`,
      }}
    >
      {onBack ? (
        <button type="button" onClick={onBack} style={secondaryButtonStyle}>
          ← Back
        </button>
      ) : (
        <span />
      )}
      <button
        type="button"
        onClick={onNext}
        disabled={disabled}
        style={{
          ...primaryButtonStyle(disabled),
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        {loading && <span className="fp-spinner" aria-hidden="true" />}
        {nextLabel}
      </button>
    </div>
  );
}

export default function WizardSteps({
  step,
  setStep,
  form,
  updateField,
  submitFleet,
  loading,
  error,
}) {
  const vehicleCountError = getVehicleCountError(form.vehicle_count);
  const mileageError = getMileageError(form.annual_mileage_per_vehicle);
  const isStep2Valid = !vehicleCountError && !mileageError && Boolean(form.owner_type);

  const lifecycleYearsError = getLifecycleYearsError(form.lifecycle_years);
  const electricityRateError = getNonNegativeError(form.electricity_rate_kwh, "Electricity rate");
  const dieselPriceError = getNonNegativeError(form.diesel_price_gal, "Diesel price");
  const incentiveCreditsError = getNonNegativeError(form.incentive_credits_usd, "Incentive amount");
  const isStep3Valid =
    !lifecycleYearsError &&
    !electricityRateError &&
    !dieselPriceError &&
    !incentiveCreditsError;

  return (
    <>
      {step === 1 && (
        <StepCard
          title="Step 1: Fleet Location & Jurisdiction"
          subtitle="Select your operating jurisdiction to automatically calibrate regional electric grid intensities, fuel prices, and statutory incentives."
        >
          <label style={labelStyle}>State or Province Code</label>
          <select
            value={form.state_prov}
            onChange={(e) => updateField("state_prov", e.target.value)}
            style={inputStyle}
          >
            <option value="">Select a region...</option>
            <optgroup label="United States (EPA eGRID / AFLEET Baselines)">
              {US_STATES.map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
            </optgroup>
            <optgroup label="Canada (ECCC NIR / Clean Hydrogen ITC)">
              {CA_PROVINCES.map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
            </optgroup>
          </select>

          <NavButtons onNext={() => setStep(2)} disabled={!form.state_prov} />
        </StepCard>
      )}

      {step === 2 && (
        <StepCard
          title="Step 2: Fleet Operating Profile"
          subtitle="Define your target asset class, total fleet size, and annual duty cycle."
        >
          <label style={labelStyle}>Vehicle Classification</label>
          <select
            value={form.vehicle_type}
            onChange={(e) => updateField("vehicle_type", e.target.value)}
            style={inputStyle}
          >
            {VEHICLE_TYPES.map((v) => (
              <option key={v.value} value={v.value}>
                {v.label}
              </option>
            ))}
          </select>

          <label style={labelStyle} htmlFor="fp-owner-type">Fleet Owner</label>
          <select
            id="fp-owner-type"
            value={form.owner_type}
            onChange={(e) => updateField("owner_type", e.target.value)}
            style={inputStyle}
          >
            <option value="">Select who owns the fleet...</option>
            {OWNER_TYPES.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <p style={{ fontSize: 12, color: COLORS.slateMuted, margin: "6px 0 0 0", lineHeight: 1.5 }}>
            Ownership decides tax-credit eligibility. Only a private contractor (a taxable corporation)
            can claim Canada's Clean Hydrogen ITC.
          </p>

          <label style={labelStyle}>Total Fleet Size (vehicle count)</label>
          <input
            type="number"
            min="1"
            value={form.vehicle_count}
            onChange={(e) => updateField("vehicle_count", e.target.value)}
            style={inputStyle}
            placeholder="e.g. 10"
          />
          <FieldError message={vehicleCountError} />

          <label style={labelStyle}>Annual Mileage per Vehicle (miles/yr)</label>
          <input
            type="number"
            min="0"
            value={form.annual_mileage_per_vehicle}
            onChange={(e) => updateField("annual_mileage_per_vehicle", e.target.value)}
            style={inputStyle}
            placeholder="e.g. 12000"
          />
          <FieldError message={mileageError} />

          <NavButtons onBack={() => setStep(1)} onNext={() => setStep(3)} disabled={!isStep2Valid} />
        </StepCard>
      )}

      {step === 3 && (
        <StepCard
          title="Step 3: Financial Parameters & Custom Overrides"
          subtitle="Set your asset amortization holding horizon and optionally provide local utility rates or secured grant credits."
        >
          <label style={labelStyle}>Asset Holding Horizon / Lifespan (years)</label>
          <input
            type="number"
            min="1"
            max="30"
            value={form.lifecycle_years}
            onChange={(e) => updateField("lifecycle_years", e.target.value)}
            style={inputStyle}
          />
          <FieldError message={lifecycleYearsError} />

          <details
            style={{
              marginTop: 20,
              border: `1px solid ${COLORS.grayBorder}`,
              borderRadius: 8,
              padding: "14px 18px",
              background: COLORS.bgLight,
            }}
          >
            <summary
              style={{
                cursor: "pointer",
                color: COLORS.navy,
                fontWeight: 600,
                fontSize: 13,
                listStyle: "none",
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <span style={{
                display: "inline-block",
                transition: "transform 0.2s ease",
                fontSize: 10,
              }}>▶</span>
              Advanced Cost Overrides & Grant Credits (Optional)
            </summary>
            <div style={{ marginTop: 14 }}>
              <label style={labelStyle}>Local Electricity Commercial Rate ($/kWh)</label>
              <input
                type="text"
                inputMode="decimal"
                value={form.electricity_rate_kwh}
                onChange={(e) => updateField("electricity_rate_kwh", e.target.value)}
                style={inputStyle}
                placeholder="Leave blank to use verified regional baseline"
              />
              <FieldError message={electricityRateError} />

              <label style={labelStyle}>Local Bulk Diesel Fuel Price ($/gal)</label>
              <input
                type="text"
                inputMode="decimal"
                value={form.diesel_price_gal}
                onChange={(e) => updateField("diesel_price_gal", e.target.value)}
                style={inputStyle}
                placeholder="Leave blank to use verified regional baseline"
              />
              <FieldError message={dieselPriceError} />

              <label style={labelStyle}>Secured Clean Fuel Grant / Incentive Credit ($)</label>
              <input
                type="text"
                inputMode="decimal"
                value={form.incentive_credits_usd}
                onChange={(e) => updateField("incentive_credits_usd", e.target.value)}
                style={inputStyle}
                placeholder="0 if none"
              />
              <FieldError message={incentiveCreditsError} />

              <div style={{ marginTop: 20, paddingTop: 16, borderTop: `1px solid ${COLORS.grayBorder}` }}>
                <label style={labelStyle}>Verdict Priority: Cost vs. Carbon</label>
                <p style={{ fontSize: 12, color: COLORS.slateMuted, margin: "0 0 10px 0" }}>
                  Controls how the recommended pathway is chosen. Defaults to Balanced.
                </p>
                <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
                  {[
                    { label: "Cost Priority", value: 0.8 },
                    { label: "Balanced", value: 0.6 },
                    { label: "Carbon Priority", value: 0.3 },
                  ].map((preset) => {
                    const isActive = Math.abs((form.cost_carbon_weight ?? 0.6) - preset.value) < 0.001;
                    return (
                      <button
                        key={preset.label}
                        type="button"
                        onClick={() => updateField("cost_carbon_weight", preset.value)}
                        style={{
                          flex: 1,
                          padding: "8px 10px",
                          fontSize: 12,
                          fontWeight: 600,
                          borderRadius: 6,
                          border: `1.5px solid ${isActive ? COLORS.navy : COLORS.grayBorder}`,
                          background: isActive ? COLORS.navy : "#fff",
                          color: isActive ? "#fff" : COLORS.navy,
                          cursor: "pointer",
                          transition: "all 0.2s ease",
                        }}
                      >
                        {preset.label}
                      </button>
                    );
                  })}
                </div>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={form.cost_carbon_weight ?? 0.6}
                  onChange={(e) => updateField("cost_carbon_weight", parseFloat(e.target.value))}
                  style={{ width: "100%" }}
                />
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: COLORS.slateMuted, marginTop: 4 }}>
                  <span>100% Carbon</span>
                  <span style={{ fontWeight: 600, color: COLORS.navy }}>
                    {Math.round((form.cost_carbon_weight ?? 0.6) * 100)}% Cost / {100 - Math.round((form.cost_carbon_weight ?? 0.6) * 100)}% Carbon
                  </span>
                  <span>100% Cost</span>
                </div>
              </div>
            </div>
          </details>

          {error && (
            <div
              className="fp-fade-in"
              style={{
                background: COLORS.dangerBg,
                border: `1px solid ${COLORS.dangerBorder}`,
                padding: "12px 16px",
                borderRadius: 6,
                color: COLORS.danger,
                marginTop: 18,
                fontSize: 13,
                display: "flex",
                alignItems: "flex-start",
                gap: 8,
              }}
            >
              <span style={{ fontSize: 16, lineHeight: 1 }}>⚠</span>
              <div>
                <strong>Calculation Error:</strong> {error}
              </div>
            </div>
          )}

          <NavButtons
            onBack={() => setStep(2)}
            onNext={submitFleet}
            nextLabel={loading ? "Computing Decision Matrix..." : "Calculate Verdict →"}
            disabled={loading || !isStep3Valid}
            loading={loading}
          />
        </StepCard>
      )}
    </>
  );
}
