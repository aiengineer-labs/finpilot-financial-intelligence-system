"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type Tenant = { id: string; name: string };
type Account = { id: string; name: string; currency: string };
type Point = {
  day: string;
  balance_minor: number;
  recurring_flow_minor: number;
  estimated_variable_spend_minor: number;
};
type Snapshot = {
  id: string;
  as_of: string;
  currency: string;
  opening_balance_minor: number;
  source_transaction_count: number;
  recurring_patterns: Array<{
    id: string;
    merchant: string;
    cadence: string;
    typical_amount_minor: number;
    confidence_bps: number;
    explanation: string;
  }>;
  anomaly_results: Array<{ transaction_id: string; severity: string; explanation: string }>;
};
type Forecast = {
  id: string;
  snapshot_id: string;
  horizon_days: number;
  opening_balance_minor: number;
  minimum_balance_minor: number;
  assumptions: string[];
  points: Point[];
};
type Scenario = {
  id: string;
  name: string;
  minimum_balance_minor: number;
  first_shortfall_date: string | null;
  ending_delta_minor: number;
  points: Point[];
};

function parseRupees(value: string): number {
  const normalized = value.trim().replaceAll(",", "");
  if (!/^\d+(\.\d{1,2})?$/.test(normalized)) throw new Error("Enter a positive amount with at most two decimals");
  const [whole, fraction = ""] = normalized.split(".");
  return Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
}

function money(minor: number, currency: string) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency }).format(minor / 100);
}

function Curve({ baseline, scenario }: { baseline: Point[]; scenario?: Point[] }) {
  const paths = useMemo(() => {
    const values = [...baseline, ...(scenario ?? [])].map((point) => point.balance_minor);
    const low = Math.min(...values);
    const high = Math.max(...values);
    const range = Math.max(high - low, 1);
    const coordinates = (points: Point[]) => points.map((point, index) => {
      const x = points.length === 1 ? 0 : (index / (points.length - 1)) * 760;
      const y = 190 - ((point.balance_minor - low) / range) * 170;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
    return { baseline: coordinates(baseline), scenario: scenario ? coordinates(scenario) : "", low, high };
  }, [baseline, scenario]);

  return (
    <div className="curve-wrap">
      <svg viewBox="0 0 760 210" role="img" aria-label="Projected daily balance curve">
        <line x1="0" x2="760" y1="190" y2="190" className="chart-axis" />
        <polyline points={paths.baseline} className="chart-line baseline" />
        {paths.scenario && <polyline points={paths.scenario} className="chart-line scenario" />}
      </svg>
      <div className="chart-legend"><span>● Baseline</span>{scenario && <span>● Scenario</span>}<small>Range {paths.low}–{paths.high} minor units</small></div>
    </div>
  );
}

export function ForecastStudio() {
  const [token, setToken] = useState("");
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function api(path: string, init: RequestInit = {}, activeToken = token, activeTenant = tenant?.id) {
    const headers = new Headers(init.headers);
    headers.set("Content-Type", "application/json");
    if (activeToken) headers.set("Authorization", `Bearer ${activeToken}`);
    if (activeTenant) headers.set("X-Tenant-ID", activeTenant);
    const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
    if (!response.ok) {
      const body = (await response.json().catch(() => ({}))) as { detail?: string };
      throw new Error(body.detail ?? `Request failed (${response.status})`);
    }
    return response;
  }

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError("");
    const form = new FormData(event.currentTarget);
    try {
      const login = await api("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: form.get("email"), password: form.get("password") })
      }, "", undefined);
      const accessToken = ((await login.json()) as { access_token: string }).access_token;
      const identity = await api("/api/v1/auth/me", {}, accessToken, undefined);
      const me = (await identity.json()) as { tenants: Tenant[] };
      if (!me.tenants.length) throw new Error("No household membership is available");
      const activeTenant = me.tenants[0];
      const accountResponse = await api("/api/v1/accounts", {}, accessToken, activeTenant.id);
      setToken(accessToken); setTenant(activeTenant);
      setAccounts((await accountResponse.json()) as Account[]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unexpected sign-in error");
    } finally { setBusy(false); }
  }

  async function createForecast(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!accounts.length) return;
    setBusy(true); setError(""); setScenario(null);
    const form = new FormData(event.currentTarget);
    try {
      const snapshotResponse = await api("/api/v1/analytics/snapshots", {
        method: "POST",
        body: JSON.stringify({ account_id: form.get("account"), as_of: form.get("as_of") })
      });
      const nextSnapshot = (await snapshotResponse.json()) as Snapshot;
      const forecastResponse = await api("/api/v1/analytics/forecasts", {
        method: "POST",
        body: JSON.stringify({ snapshot_id: nextSnapshot.id, horizon_days: Number(form.get("horizon")) })
      });
      setSnapshot(nextSnapshot);
      setForecast((await forecastResponse.json()) as Forecast);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not calculate forecast");
    } finally { setBusy(false); }
  }

  async function runWhatIf(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!forecast) return;
    setBusy(true); setError("");
    const form = new FormData(event.currentTarget);
    try {
      const amount = parseRupees(String(form.get("amount")));
      const response = await api("/api/v1/analytics/scenarios", {
        method: "POST",
        body: JSON.stringify({
          forecast_id: forecast.id,
          name: form.get("name"),
          shocks: [{ day: form.get("day"), amount_minor: -amount, label: form.get("name") }]
        })
      });
      setScenario((await response.json()) as Scenario);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not run scenario");
    } finally { setBusy(false); }
  }

  if (!token || !tenant) return (
    <main className="workspace-shell">
      <Link className="back-link" href="/">← FinPilot</Link>
      <section className="auth-card"><p className="eyebrow">FORECAST STUDIO</p><h1>Use your verified ledger.</h1>
        <p className="lede">Sign in to create immutable forecasts and what-if branches.</p>
        <form className="stack-form" onSubmit={signIn}>
          <label>Email<input name="email" type="email" required /></label>
          <label>Password<input name="password" type="password" required /></label>
          <button className="primary" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        </form>{error && <p className="form-error" role="alert">{error}</p>}
      </section>
    </main>
  );

  return (
    <main className="workspace-shell">
      <header className="workspace-header"><div><Link className="back-link" href="/transactions">← Transaction truth</Link><h1>Forecast studio</h1></div><span className="badge online">{tenant.name}</span></header>
      <section className="workspace-grid">
        <form className="workspace-card stack-form" onSubmit={createForecast}>
          <div><p className="eyebrow">VERSIONED BASELINE</p><h2>Create a forecast</h2></div>
          <label>Account<select name="account" required>{accounts.map((account) => <option key={account.id} value={account.id}>{account.name} · {account.currency}</option>)}</select></label>
          <label>Known-balance date<input name="as_of" type="date" required /></label>
          <label>Horizon<select name="horizon" defaultValue="30"><option value="30">30 days</option><option value="60">60 days</option><option value="90">90 days</option></select></label>
          <button className="primary" disabled={busy || !accounts.length}>{busy ? "Calculating…" : "Create deterministic forecast"}</button>
          <p className="form-note">The latest transaction on this date must contain a source balance. Missing balances are never inferred.</p>
        </form>
        <form className="workspace-card stack-form" onSubmit={runWhatIf}>
          <div><p className="eyebrow">IMMUTABLE BRANCH</p><h2>Test a purchase</h2></div>
          <label>Scenario name<input name="name" defaultValue="Laptop purchase" required maxLength={120} /></label>
          <label>Purchase date<input name="day" type="date" required /></label>
          <label>Amount (₹)<input name="amount" inputMode="decimal" placeholder="75000.00" required /></label>
          <button className="primary" disabled={busy || !forecast}>Run against baseline</button>
          <p className="form-note">This creates a new scenario curve. It never changes imported transactions or the baseline.</p>
        </form>
      </section>
      {error && <p className="form-error studio-error" role="alert">{error}</p>}
      {forecast && snapshot && <>
        <section className="workspace-card analytics-summary">
          <div><p className="eyebrow">REPRODUCIBLE RESULT</p><h2>{forecast.horizon_days}-day balance trajectory</h2></div>
          <div className="result-grid"><b>{money(forecast.opening_balance_minor, snapshot.currency)}<span>opening balance</span></b><b>{money(forecast.minimum_balance_minor, snapshot.currency)}<span>baseline minimum</span></b><b>{snapshot.recurring_patterns.length}<span>recurring patterns</span></b></div>
          <Curve baseline={forecast.points} scenario={scenario?.points} />
          {scenario && <div className="scenario-callout"><strong>{scenario.name}</strong><span>Minimum {money(scenario.minimum_balance_minor, snapshot.currency)}</span><span>Ending change {money(scenario.ending_delta_minor, snapshot.currency)}</span><span>{scenario.first_shortfall_date ? `First shortfall ${scenario.first_shortfall_date}` : "No projected shortfall"}</span></div>}
        </section>
        <section className="workspace-grid analytics-details">
          <article className="workspace-card"><p className="eyebrow">EVIDENCE</p><h2>{snapshot.source_transaction_count} source rows</h2>{snapshot.recurring_patterns.length ? snapshot.recurring_patterns.map((pattern) => <div className="evidence-row" key={pattern.id}><b>{pattern.merchant}</b><span>{pattern.cadence} · {money(pattern.typical_amount_minor, snapshot.currency)} · {(pattern.confidence_bps / 100).toFixed(0)}%</span><small>{pattern.explanation}</small></div>) : <p className="empty-state">No recurrence has enough evidence yet.</p>}</article>
          <article className="workspace-card"><p className="eyebrow">ASSUMPTIONS</p><h2>What the curve means</h2><ul className="assumption-list">{forecast.assumptions.map((item) => <li key={item}>{item}</li>)}</ul></article>
        </section>
      </>}
    </main>
  );
}
