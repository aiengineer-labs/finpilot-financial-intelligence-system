"use client";

import { CSSProperties, FormEvent, useEffect, useMemo, useRef, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const DEFAULT_MAPPING = JSON.stringify({
  date: "Date", date_format: "%d/%m/%Y", debit: "Debit", credit: "Credit",
  merchant: "Merchant", description: "Description", transaction_id: "Transaction ID",
  currency: "Currency", balance: "Balance"
});

type Mode = "live" | "system";
type View = "overview" | "ledger" | "forecast" | "advice" | "audit" | "governance";
type Tenant = { id: string; name: string; role: string };
type Account = { id: string; name: string; currency: string };
type Transaction = {
  id: string; transaction_date: string; amount_minor: number; balance_minor: number | null;
  currency: string; merchant_normalized: string; description: string; kind: string;
  category: string; classification_method: string; classification_confidence_bps: number;
  is_excluded_from_cashflow: boolean;
};
type Pattern = { id: string; merchant: string; cadence: string; typical_amount_minor: number; confidence_bps: number };
type Snapshot = { id: string; as_of: string; currency: string; opening_balance_minor: number; source_transaction_count: number; recurring_patterns: Pattern[]; anomaly_results: Array<{ transaction_id: string; severity: string; explanation: string }> };
type Point = { day: string; balance_minor: number; recurring_flow_minor: number; estimated_variable_spend_minor: number };
type Forecast = { id: string; horizon_days: number; opening_balance_minor: number; minimum_balance_minor: number; assumptions: string[]; points: Point[] };
type Scenario = { id: string; name: string; minimum_balance_minor: number; first_shortfall_date: string | null; ending_delta_minor: number; points: Point[] };
type AgentEvent = { id: string; sequence: number; node: string; event_type: string; summary: string; details: Record<string, unknown>; model_id: string | null; latency_ms: number | null; input_tokens: number | null; output_tokens: number | null };
type Recommendation = { id: string; rank: number; title: string; explanation: string; amount_minor: number | null; currency: string; evidence_ids: string[]; assumptions: string[]; confidence_bps: number; verification_status: string };
type AgentRun = { id: string; status: string; verification_status: string; final_response: string; model_id: string; revision_attempts: number; total_latency_ms: number; total_input_tokens: number; total_output_tokens: number; events: AgentEvent[]; recommendations: Recommendation[] };
type GovernanceSummary = { artifacts: number; risks: number; pending_reviews: number; evaluation_failures: number; rejected_recommendations: number; release_ready: boolean; release_blockers: string[]; drift_alerts: string[]; baseline_version: string };
type GovernanceArtifact = { id: string; artifact_type: string; name: string; version: string; content_sha256: string; status: string; approval_source: string; approval_reason: string | null; created_at: string };
type GovernanceRisk = { id: string; risk_id: string; category: string; likelihood: string; impact: string; residual_risk: string; mitigation: string; owner_role: string; review_on: string; acceptance_status: string };
type EvaluationRun = { id: string; dataset_id: string; dataset_version: string; status: string; metrics: Record<string, number | string>; thresholds: Record<string, number | string>; model_id: string | null; failures: string[]; duration_ms: number; code_version: string };
type HumanReview = { id: string; source: string; reason: string; risk_level: string; status: string; evidence_ids: string[]; artifact_lineage: Record<string, string>; requested_by_user_id: string | null; created_at: string };
type GovernanceData = { summary: GovernanceSummary; artifacts: GovernanceArtifact[]; risks: GovernanceRisk[]; evaluations: EvaluationRun[]; reviews: HumanReview[] };

const stages = [
  ["import", "Import"], ["categorize", "Categorize"], ["analyze", "Analyze"],
  ["forecast", "Forecast"], ["advise", "Advise"], ["verify", "Verify"]
] as const;

const architecture = [
  { id: "ingest", icon: "⇩", title: "CSV ingestion", detail: "Validates UTF-8, explicit dates, exact minor units, duplicates, transfers and row errors.", runtime: "FastAPI · deterministic" },
  { id: "truth", icon: "▦", title: "PostgreSQL truth", detail: "Tenant-scoped ledger, immutable snapshot manifests and correction lineage.", runtime: "SQLAlchemy · Alembic" },
  { id: "analyst", icon: "⌁", title: "Behavior analyst", detail: "Explains recurrence and robust anomaly evidence without performing arithmetic.", runtime: "LangGraph · Mesh" },
  { id: "forecast", icon: "↗", title: "Forecast engine", detail: "Builds reproducible daily 30/60/90-day curves from known balances and patterns.", runtime: "Python integer math" },
  { id: "advisor", icon: "◇", title: "Financial advisor", detail: "Drafts bounded options citing only supplied snapshot, forecast and scenario evidence.", runtime: "LangGraph · Mesh" },
  { id: "critic", icon: "◎", title: "Critic loop", detail: "Challenges unsupported or overconfident advice and requests one bounded revision.", runtime: "LangGraph · Mesh" },
  { id: "verifier", icon: "✓", title: "Financial verifier", detail: "Rejects unknown amounts, evidence, currencies and prohibited certainty in plain code.", runtime: "Fail-closed · no LLM" },
  { id: "audit", icon: "≡", title: "Audit ledger", detail: "Persists every transition, model ID, latency, tokens, rejected draft and final decision.", runtime: "PostgreSQL · immutable lineage" }
];

function minorFromRupees(value: string): number {
  const normalized = value.trim().replaceAll(",", "");
  if (!/^\d+(\.\d{1,2})?$/.test(normalized)) throw new Error("Use a positive amount with at most two decimals");
  const [whole, fraction = ""] = normalized.split(".");
  return Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
}

function money(minor: number, currency = "INR") {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 0 }).format(minor / 100);
}

function BalanceChart({ baseline, scenario }: { baseline: Point[]; scenario?: Point[] }) {
  const paths = useMemo(() => {
    const values = [...baseline, ...(scenario ?? [])].map((point) => point.balance_minor);
    const low = Math.min(...values); const high = Math.max(...values); const range = Math.max(high - low, 1);
    const line = (points: Point[]) => points.map((point, index) => `${((index / Math.max(points.length - 1, 1)) * 700).toFixed(1)},${(190 - ((point.balance_minor - low) / range) * 160).toFixed(1)}`).join(" ");
    return { baseline: line(baseline), scenario: scenario ? line(scenario) : "", low, high };
  }, [baseline, scenario]);
  return <div className="fp-chart"><svg viewBox="0 0 700 210" role="img" aria-label="Daily projected balance"><line x1="0" x2="700" y1="190" y2="190" /><polyline className="fp-baseline" points={paths.baseline} />{paths.scenario && <polyline className="fp-scenario" points={paths.scenario} />}</svg><div><span>● Baseline</span>{scenario && <span>● What-if</span>}<small>{money(paths.low)} → {money(paths.high)}</small></div></div>;
}

export function ProductConsole() {
  const [mode, setMode] = useState<Mode>("live");
  const [view, setView] = useState<View>("overview");
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [token, setToken] = useState("");
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [agentRun, setAgentRun] = useState<AgentRun | null>(null);
  const [governance, setGovernance] = useState<GovernanceData | null>(null);
  const [visibleEvents, setVisibleEvents] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [uploadSummary, setUploadSummary] = useState("");
  const [uploadFileName, setUploadFileName] = useState("");
  const [asOf, setAsOf] = useState("");
  const [horizon, setHorizon] = useState(30);
  const [question, setQuestion] = useState("Can I afford this purchase without jeopardizing my cash buffer?");
  const [scenarioAmount, setScenarioAmount] = useState("75000.00");
  const [scenarioDate, setScenarioDate] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  async function api(path: string, init: RequestInit = {}, activeToken = token, activeTenant = tenant?.id) {
    const headers = new Headers(init.headers);
    if (!(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
    if (activeToken) headers.set("Authorization", `Bearer ${activeToken}`);
    if (activeTenant) headers.set("X-Tenant-ID", activeTenant);
    const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
    if (!response.ok) {
      const body = (await response.json().catch(() => ({}))) as { detail?: string };
      throw new Error(body.detail ?? `Request failed (${response.status})`);
    }
    return response;
  }

  async function loadWorkspace(activeToken: string, activeTenant: Tenant) {
    const [accountResponse, transactionResponse] = await Promise.all([
      api("/api/v1/accounts", {}, activeToken, activeTenant.id),
      api("/api/v1/transactions?limit=200", {}, activeToken, activeTenant.id)
    ]);
    const nextAccounts = (await accountResponse.json()) as Account[];
    const page = (await transactionResponse.json()) as { items: Transaction[] };
    setAccounts(nextAccounts); setTransactions(page.items);
    const known = page.items.find((item) => item.balance_minor !== null);
    if (known) setAsOf(known.transaction_date);
    await loadGovernance(activeToken, activeTenant.id);
  }

  async function loadGovernance(activeToken = token, activeTenant = tenant?.id) {
    if (!activeToken || !activeTenant) return;
    const [summaryResponse, artifactResponse, riskResponse, evaluationResponse, reviewResponse] = await Promise.all([
      api("/api/v1/governance/summary", {}, activeToken, activeTenant),
      api("/api/v1/governance/artifacts", {}, activeToken, activeTenant),
      api("/api/v1/governance/risks", {}, activeToken, activeTenant),
      api("/api/v1/governance/evaluations", {}, activeToken, activeTenant),
      api("/api/v1/governance/reviews", {}, activeToken, activeTenant)
    ]);
    setGovernance({
      summary: (await summaryResponse.json()) as GovernanceSummary,
      artifacts: (await artifactResponse.json()) as GovernanceArtifact[],
      risks: (await riskResponse.json()) as GovernanceRisk[],
      evaluations: (await evaluationResponse.json()) as EvaluationRun[],
      reviews: (await reviewResponse.json()) as HumanReview[]
    });
  }

  async function authenticate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const form = new FormData(event.currentTarget);
    try {
      const path = authMode === "register" ? "/api/v1/auth/register" : "/api/v1/auth/login";
      const body = authMode === "register"
        ? { email: form.get("email"), password: form.get("password"), household_name: form.get("household") }
        : { email: form.get("email"), password: form.get("password") };
      const login = await api(path, { method: "POST", body: JSON.stringify(body) }, "", undefined);
      const accessToken = ((await login.json()) as { access_token: string }).access_token;
      const identity = await api("/api/v1/auth/me", {}, accessToken, undefined);
      const me = (await identity.json()) as { tenants: Tenant[] };
      if (!me.tenants.length) throw new Error("No household membership is available");
      setToken(accessToken); setTenant(me.tenants[0]);
      await loadWorkspace(accessToken, me.tenants[0]);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Authentication failed"); }
    finally { setBusy(false); }
  }

  async function createAccount() {
    setBusy(true); setError("");
    try {
      const response = await api("/api/v1/accounts", { method: "POST", body: JSON.stringify({ name: "Primary account", currency: "INR", external_reference: crypto.randomUUID() }) });
      setAccounts([(await response.json()) as Account]);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not create account"); }
    finally { setBusy(false); }
  }

  async function uploadStatement() {
    const file = fileRef.current?.files?.[0];
    if (!file || !accounts[0] || !tenant) return;
    setUploadFileName(file.name);
    setBusy(true); setError("");
    try {
      const body = new FormData(); body.set("mapping", DEFAULT_MAPPING); body.set("file", file);
      const response = await api(`/api/v1/accounts/${accounts[0].id}/transaction-uploads`, { method: "POST", body });
      const result = (await response.json()) as { accepted_rows: number; rejected_rows: number; duplicate_rows: number; replayed: boolean };
      setUploadSummary(`${result.accepted_rows} accepted · ${result.duplicate_rows} duplicate · ${result.rejected_rows} rejected${result.replayed ? " · replay" : ""}`);
      await loadWorkspace(token, tenant);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Import failed"); }
    finally { setBusy(false); }
  }

  async function runFinPilot() {
    if (!accounts[0] || !asOf) { setError("Import data with a known balance and select its balance date first"); return; }
    setBusy(true); setError(""); setAgentRun(null); setVisibleEvents(0);
    try {
      const snapshotResponse = await api("/api/v1/analytics/snapshots", { method: "POST", body: JSON.stringify({ account_id: accounts[0].id, as_of: asOf }) });
      const nextSnapshot = (await snapshotResponse.json()) as Snapshot;
      const forecastResponse = await api("/api/v1/analytics/forecasts", { method: "POST", body: JSON.stringify({ snapshot_id: nextSnapshot.id, horizon_days: horizon }) });
      const nextForecast = (await forecastResponse.json()) as Forecast;
      let nextScenario: Scenario | null = null;
      if (scenarioAmount && scenarioDate) {
        const scenarioResponse = await api("/api/v1/analytics/scenarios", { method: "POST", body: JSON.stringify({ forecast_id: nextForecast.id, name: "Planned purchase", shocks: [{ day: scenarioDate, amount_minor: -minorFromRupees(scenarioAmount), label: "Planned purchase" }] }) });
        nextScenario = (await scenarioResponse.json()) as Scenario;
      }
      const runResponse = await api("/api/v1/agent-runs", { method: "POST", body: JSON.stringify({ forecast_id: nextForecast.id, scenario_id: nextScenario?.id ?? null, question }) });
      const nextRun = (await runResponse.json()) as AgentRun;
      setSnapshot(nextSnapshot); setForecast(nextForecast); setScenario(nextScenario); setAgentRun(nextRun);
      await loadGovernance();
      setVisibleEvents(1); setView("advice");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "FinPilot run failed safely"); }
    finally { setBusy(false); }
  }

  async function createGovernanceDemo() {
    setBusy(true); setError("");
    try {
      await api("/api/v1/governance/demo-review", { method: "POST", body: "{}" });
      await loadGovernance(); setView("governance");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not create governance demo"); }
    finally { setBusy(false); }
  }

  async function rejectReview(reviewId: string) {
    setBusy(true); setError("");
    try {
      await api(`/api/v1/governance/reviews/${reviewId}/decisions`, { method: "POST", body: JSON.stringify({ outcome: "reject", reason: "Unsafe guarantee remains forbidden; deterministic controls cannot be overridden." }) });
      await loadGovernance();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not record governance decision"); }
    finally { setBusy(false); }
  }

  useEffect(() => {
    if (!agentRun || visibleEvents <= 0 || visibleEvents >= agentRun.events.length) return;
    const timer = window.setTimeout(() => setVisibleEvents((count) => count + 1), 650);
    return () => window.clearTimeout(timer);
  }, [agentRun, visibleEvents]);

  const metrics = useMemo(() => {
    const included = transactions.filter((item) => !item.is_excluded_from_cashflow);
    const income = included.filter((item) => item.amount_minor > 0 && item.kind !== "refund").reduce((sum, item) => sum + item.amount_minor, 0);
    const spend = included.filter((item) => item.amount_minor < 0).reduce((sum, item) => sum + Math.abs(item.amount_minor), 0);
    const savings = income - spend; const rate = income ? Math.round((Math.max(savings, 0) / income) * 100) : 0;
    const categories = new Map<string, number>();
    included.filter((item) => item.amount_minor < 0).forEach((item) => categories.set(item.category, (categories.get(item.category) ?? 0) + Math.abs(item.amount_minor)));
    return { income, spend, savings, rate, categories: [...categories.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6) };
  }, [transactions]);

  const completed = new Set<string>();
  if (transactions.length) { completed.add("import"); completed.add("categorize"); }
  if (snapshot) completed.add("analyze");
  if (forecast) completed.add("forecast");
  if (agentRun) completed.add("advise");
  if (agentRun?.verification_status === "accept") completed.add("verify");

  return <div className="fp-app">
    <header className="fp-topbar"><div className="fp-brand"><span>⌁</span><strong>FinPilot</strong><em>TRACK 02</em></div><div className="fp-mode"><button className={mode === "live" ? "active" : ""} onClick={() => setMode("live")}>Live workspace</button><button className={mode === "system" ? "active" : ""} onClick={() => setMode("system")}>How it works</button></div><div className="fp-header-meta"><span>Mesh-only AI</span>{tenant ? <b>{tenant.name}</b> : <b>Synthetic-safe</b>}</div></header>

    {mode === "system" ? <SystemMap agentRun={agentRun} visibleEvents={visibleEvents} setVisibleEvents={setVisibleEvents} /> : !token || !tenant ? <main className="fp-auth-layout"><section><p className="fp-kicker">NEURO-SYMBOLIC FINANCIAL DECISION INTELLIGENCE</p><h1>See the math.<br />Watch the agents.<br /><span>Trust the evidence.</span></h1><p>Import a real statement, branch a what-if scenario, and inspect every deterministic calculation and Mesh-powered handoff.</p><div className="fp-trust-row"><span>Exact money math</span><span>Tenant isolation</span><span>Fail-closed advice</span></div></section><form className="fp-auth-panel" onSubmit={authenticate}><div className="fp-auth-toggle"><button type="button" className={authMode === "login" ? "active" : ""} onClick={() => setAuthMode("login")}>Sign in</button><button type="button" className={authMode === "register" ? "active" : ""} onClick={() => setAuthMode("register")}>Register</button></div><h2>{authMode === "login" ? "Continue to your household" : "Create a private household"}</h2>{authMode === "register" && <label>Household name<input name="household" required /></label>}<label>Email<input name="email" type="email" required /></label><label>Password<input name="password" type="password" minLength={12} required /></label><button className="fp-primary" disabled={busy}>{busy ? "Authenticating…" : authMode === "login" ? "Open workspace" : "Create household"}</button>{error && <p className="fp-error">{error}</p>}<small>Short-lived access tokens stay in memory. Financial data is never sent to the browser without tenant authorization.</small></form></main> : <main className="fp-workspace">
      <aside className="fp-sidebar"><div className="fp-household"><div><span>{tenant.name.slice(0, 2).toUpperCase()}</span><div><b>{tenant.name}</b><small>{tenant.role} · private workspace</small></div></div><p>{transactions.length ? `${transactions.length} verified ledger rows` : "Ready for your first statement"}</p></div><div className="fp-ring-card"><div className="fp-ring" style={{ "--rate": `${metrics.rate * 3.6}deg` } as CSSProperties}><b>{metrics.rate}%</b></div><dl><div><dt>Income</dt><dd>{money(metrics.income)}</dd></div><div><dt>Spend</dt><dd>{money(metrics.spend)}</dd></div><div><dt>Net</dt><dd className={metrics.savings >= 0 ? "positive" : "negative"}>{money(metrics.savings)}</dd></div></dl></div>{!accounts.length ? <button className="fp-upload" onClick={createAccount} disabled={busy}><span>＋</span><b>Create primary account</b><small>No balance will be invented</small></button> : <label className="fp-upload"><span>⇧</span><b>{uploadFileName || "Upload transactions"}</b><small>{uploadSummary || "CSV · explicit bank mapping"}</small><input ref={fileRef} type="file" accept=".csv,text/csv" onChange={uploadStatement} /></label>}<button className="fp-run" onClick={runFinPilot} disabled={busy || !transactions.length}>{busy ? "Running secure pipeline…" : "▷ Run FinPilot"}</button><div className="fp-controls"><label>Balance date<input type="date" value={asOf} onChange={(event) => setAsOf(event.target.value)} /></label><label>Horizon<select value={horizon} onChange={(event) => setHorizon(Number(event.target.value))}><option value={30}>30 days</option><option value={60}>60 days</option><option value={90}>90 days</option></select></label><label>Purchase date<input type="date" value={scenarioDate} onChange={(event) => setScenarioDate(event.target.value)} /></label><label>Purchase amount (₹)<input value={scenarioAmount} onChange={(event) => setScenarioAmount(event.target.value)} inputMode="decimal" /></label></div><div className="fp-stage-list">{stages.map(([id, label]) => <div key={id} className={completed.has(id) ? "done" : ""}><span>{completed.has(id) ? "✓" : "○"}</span>{label}</div>)}</div></aside>

      <section className="fp-main"><nav className="fp-tabs">{(["overview", "ledger", "forecast", "advice", "audit", "governance"] as View[]).map((item) => <button key={item} className={view === item ? "active" : ""} onClick={() => setView(item)}>{item}</button>)}</nav><div className="fp-pipeline">{stages.slice(1).map(([id, label], index) => <div key={id} className={completed.has(id) ? "done" : ""}><i>{index + 1}</i><span>{label}</span>{index < stages.length - 2 && <b>›</b>}</div>)}</div>{error && <p className="fp-error fp-wide-error">{error}</p>}
        {view === "overview" && <Overview metrics={metrics} snapshot={snapshot} transactions={transactions} />}
        {view === "ledger" && <Ledger transactions={transactions} />}
        {view === "forecast" && <ForecastView snapshot={snapshot} forecast={forecast} scenario={scenario} />}
        {view === "advice" && <AdviceView run={agentRun} question={question} setQuestion={setQuestion} visibleEvents={visibleEvents} />}
        {view === "audit" && <AuditView run={agentRun} />}
        {view === "governance" && <GovernanceView data={governance} busy={busy} createDemo={createGovernanceDemo} rejectReview={rejectReview} />}
      </section>

      <aside className="fp-agent-log"><header><span>›_</span><b>Agent log</b><em>{busy ? "running" : agentRun ? "persisted" : "idle"}</em></header><div>{!agentRun ? <p>{"// waiting for a verified run"}<br />{"// configure the inputs and press Run FinPilot"}</p> : agentRun.events.slice(0, visibleEvents).map((event) => <article key={event.id}><time>[{String(event.sequence).padStart(2, "0")}]</time><b>{event.node}</b><p>{event.summary}</p>{event.model_id && <span>Mesh API · {event.model_id} · {event.output_tokens ?? 0} tok · {event.latency_ms ?? 0} ms</span>}</article>)}</div>{agentRun && <footer>LLM tokens {agentRun.total_input_tokens + agentRun.total_output_tokens} · {agentRun.total_latency_ms} ms</footer>}</aside>
    </main>}
  </div>;
}

function Overview({ metrics, snapshot, transactions }: { metrics: { income: number; spend: number; savings: number; rate: number; categories: [string, number][] }; snapshot: Snapshot | null; transactions: Transaction[] }) {
  const max = Math.max(...metrics.categories.map((item) => item[1]), 1);
  return <div className="fp-content"><div className="fp-summary-grid"><article><span>Cash in</span><strong>{money(metrics.income)}</strong><small>Imported, transfer-adjusted</small></article><article><span>Cash out</span><strong>{money(metrics.spend)}</strong><small>Refunds and transfers separated</small></article><article><span>Net cash flow</span><strong className={metrics.savings >= 0 ? "positive" : "negative"}>{money(metrics.savings)}</strong><small>{metrics.rate}% retained</small></article><article><span>Data confidence</span><strong>{transactions.length ? "Source-backed" : "No data"}</strong><small>{snapshot ? `Snapshot ${snapshot.id.slice(0, 8)}` : "Run analysis to version evidence"}</small></article></div><div className="fp-two-col"><article className="fp-panel"><header><div><span className="fp-kicker">SPEND INTELLIGENCE</span><h2>Category movement</h2></div><small>Exact imported amounts</small></header>{metrics.categories.length ? <div className="fp-bars">{metrics.categories.map(([category, value]) => <div key={category}><label><span>{category.replaceAll("_", " ")}</span><b>{money(value)}</b></label><i><b style={{ width: `${(value / max) * 100}%` }} /></i></div>)}</div> : <p className="fp-empty">Upload a statement to calculate category movement.</p>}</article><article className="fp-panel"><header><div><span className="fp-kicker">DETERMINISTIC FINDINGS</span><h2>Signals worth reviewing</h2></div><small>MAD + recurrence</small></header>{snapshot ? <div className="fp-findings"><div><span>↻</span><p><b>{snapshot.recurring_patterns.length} recurring patterns</b><small>Backed by repeated merchant/date evidence</small></p></div><div><span>!</span><p><b>{snapshot.anomaly_results.length} robust anomalies</b><small>Sparse categories stay unflagged</small></p></div></div> : <p className="fp-empty">Run FinPilot to create a versioned analysis snapshot.</p>}</article></div></div>;
}

function Ledger({ transactions }: { transactions: Transaction[] }) {
  return <div className="fp-panel fp-ledger"><header><div><span className="fp-kicker">TRANSACTION TRUTH</span><h2>{transactions.length} persisted rows</h2></div><small>Human corrections retain lineage</small></header>{transactions.length ? <table><thead><tr><th>Date</th><th>Merchant</th><th>Category</th><th>Provenance</th><th>Amount</th></tr></thead><tbody>{transactions.map((item) => <tr key={item.id}><td>{item.transaction_date}</td><td><b>{item.merchant_normalized}</b><small>{item.description}</small></td><td><span className="fp-tag">{item.category}</span></td><td>{item.classification_method}<small>{(item.classification_confidence_bps / 100).toFixed(0)}% confidence</small></td><td className={item.amount_minor >= 0 ? "positive" : "negative"}>{money(item.amount_minor, item.currency)}{item.is_excluded_from_cashflow && <small>excluded transfer</small>}</td></tr>)}</tbody></table> : <p className="fp-empty">No ledger rows yet.</p>}</div>;
}

function ForecastView({ snapshot, forecast, scenario }: { snapshot: Snapshot | null; forecast: Forecast | null; scenario: Scenario | null }) {
  if (!snapshot || !forecast) return <div className="fp-empty-stage"><span>↗</span><h2>No forecast yet</h2><p>Select a known-balance date and run the secure pipeline.</p></div>;
  return <div className="fp-content"><div className="fp-summary-grid"><article><span>Opening balance</span><strong>{money(forecast.opening_balance_minor, snapshot.currency)}</strong><small>{snapshot.as_of}</small></article><article><span>Baseline minimum</span><strong>{money(forecast.minimum_balance_minor, snapshot.currency)}</strong><small>{forecast.horizon_days}-day horizon</small></article><article><span>Scenario minimum</span><strong>{scenario ? money(scenario.minimum_balance_minor, snapshot.currency) : "Not run"}</strong><small>{scenario?.first_shortfall_date ? `Shortfall ${scenario.first_shortfall_date}` : scenario ? "No projected shortfall" : "Optional what-if"}</small></article><article><span>Scenario delta</span><strong>{scenario ? money(scenario.ending_delta_minor, snapshot.currency) : "—"}</strong><small>Baseline remains immutable</small></article></div><article className="fp-panel"><header><div><span className="fp-kicker">DAILY CASH-FLOW</span><h2>Baseline vs. what-if</h2></div><small>Integer minor-unit engine</small></header><BalanceChart baseline={forecast.points} scenario={scenario?.points} /><ul className="fp-assumptions">{forecast.assumptions.map((item) => <li key={item}>{item}</li>)}</ul></article></div>;
}

function AdviceView({ run, question, setQuestion, visibleEvents }: { run: AgentRun | null; question: string; setQuestion: (value: string) => void; visibleEvents: number }) {
  return <div className="fp-content"><article className="fp-panel fp-question"><header><div><span className="fp-kicker">FINANCIAL COPILOT</span><h2>Ask against verified evidence</h2></div><small>No model arithmetic</small></header><textarea value={question} onChange={(event) => setQuestion(event.target.value)} rows={3} maxLength={1000} /><p>Questions are treated as untrusted input. Run FinPilot to execute the graph.</p></article>{!run ? <div className="fp-empty-stage"><span>◇</span><h2>No recommendation run yet</h2><p>The advisor only activates after a versioned forecast exists.</p></div> : <><div className="fp-verdict"><span className={run.verification_status === "accept" ? "pass" : "fail"}>{run.verification_status === "accept" ? "✓ VERIFIED" : "× WITHHELD"}</span><div><b>{run.status}</b><small>{run.model_id} · {run.revision_attempts} revision attempts · {visibleEvents}/{run.events.length} events replayed</small></div></div><div className="fp-rec-grid">{run.recommendations.map((item) => <article key={item.id}><header><span>OPTION {item.rank}</span><em>{(item.confidence_bps / 100).toFixed(0)}%</em></header><h3>{item.title}</h3><p>{item.explanation}</p>{item.amount_minor !== null && <strong>{money(item.amount_minor, item.currency)}</strong>}<details><summary>Evidence & assumptions</summary><small>Evidence: {item.evidence_ids.join(", ")}</small><small>{item.assumptions.join(" · ") || "No additional assumptions"}</small></details></article>)}</div></>}</div>;
}

function AuditView({ run }: { run: AgentRun | null }) {
  if (!run) return <div className="fp-empty-stage"><span>≡</span><h2>No audit timeline yet</h2><p>Every completed and rejected node will appear here.</p></div>;
  return <div className="fp-panel fp-timeline"><header><div><span className="fp-kicker">IMMUTABLE DECISION TRAIL</span><h2>Execution {run.id.slice(0, 8)}</h2></div><small>{run.verification_status}</small></header>{run.events.map((event) => <article key={event.id}><i>{event.sequence}</i><div><span>{event.event_type}</span><h3>{event.node}</h3><p>{event.summary}</p></div><aside>{event.model_id ? <><b>{event.model_id}</b><small>{event.input_tokens ?? 0} in · {event.output_tokens ?? 0} out</small><small>{event.latency_ms ?? 0} ms</small></> : <><b>Deterministic</b><small>No model call</small></>}</aside></article>)}</div>;
}

function GovernanceView({ data, busy, createDemo, rejectReview }: { data: GovernanceData | null; busy: boolean; createDemo: () => Promise<void>; rejectReview: (id: string) => Promise<void> }) {
  if (!data) return <div className="fp-empty-stage"><span>⌾</span><h2>Loading governance evidence</h2><p>FinPilot is resolving approved assets, risk controls and review lineage.</p></div>;
  const pending = data.reviews.filter((item) => item.status === "pending");
  return <div className="fp-content fp-governance"><div className="fp-summary-grid"><article><span>Asset registry</span><strong>{data.summary.artifacts}</strong><small>Versioned + hashed</small></article><article><span>Risk controls</span><strong>{data.summary.risks}</strong><small>Owned and review-dated</small></article><article><span>Human review</span><strong>{data.summary.pending_reviews}</strong><small>Pending cases</small></article><article><span>Release gate</span><strong className={data.summary.release_ready ? "positive" : "negative"}>{data.summary.release_ready ? "READY" : "BLOCKED"}</strong><small>{data.summary.evaluation_failures} incomplete gates</small></article></div><div className="fp-two-col"><article className="fp-panel"><header><div><span className="fp-kicker">LIVE EVALUATION GATES</span><h2>Promotion evidence</h2></div><small>{data.summary.baseline_version}</small></header><div className="fp-governance-list">{data.evaluations.map((item) => <div key={item.id}><span className={`fp-status-pill ${item.status}`}>{item.status}</span><p><b>{item.dataset_id}</b><small>{item.dataset_version} · code {item.code_version} · {item.duration_ms} ms</small>{item.failures.map((failure) => <em key={failure}>{failure}</em>)}</p></div>)}</div>{data.summary.release_blockers.length > 0 && <div className="fp-blockers"><b>Active blockers</b>{data.summary.release_blockers.map((item) => <span key={item}>{item}</span>)}</div>}</article><article className="fp-panel"><header><div><span className="fp-kicker">HUMAN OVERSIGHT</span><h2>Review queue</h2></div><button className="fp-mini-button" onClick={createDemo} disabled={busy}>Create synthetic case</button></header>{pending.length ? <div className="fp-review-list">{pending.map((item) => <article key={item.id}><header><span>{item.risk_level} · {item.source}</span><small>{new Date(item.created_at).toLocaleString()}</small></header><p>{item.reason}</p><small>{Object.keys(item.artifact_lineage).length} exact artifact versions retained</small>{item.requested_by_user_id === null && <button onClick={() => rejectReview(item.id)} disabled={busy}>Reject unsafe advice</button>}</article>)}</div> : <p className="fp-empty">No pending cases. Create the explicit synthetic demo to trace an automatic rejection through an auditable reviewer decision.</p>}</article></div><article className="fp-panel"><header><div><span className="fp-kicker">MODEL · PROMPT · POLICY REGISTRY</span><h2>Approved and proposed versions</h2></div><small>Secrets and full prompts excluded</small></header><div className="fp-artifact-grid">{data.artifacts.map((item) => <article key={item.id}><header><span>{item.artifact_type}</span><em className={`fp-status-pill ${item.status}`}>{item.status}</em></header><b>{item.name}</b><p>{item.version}</p><code>{item.content_sha256.slice(0, 16)}…</code><small>{item.approval_source}</small></article>)}</div></article><article className="fp-panel"><header><div><span className="fp-kicker">AI RISK REGISTER</span><h2>Residual risk and accountable owner</h2></div><small>{data.summary.drift_alerts.length} drift alerts</small></header><div className="fp-risk-table"><table><thead><tr><th>ID</th><th>Risk</th><th>Impact</th><th>Residual</th><th>Owner</th><th>Review</th></tr></thead><tbody>{data.risks.map((item) => <tr key={item.id}><td>{item.risk_id}</td><td><b>{item.category.replaceAll("_", " ")}</b><small>{item.mitigation}</small></td><td>{item.impact}</td><td><span className={`fp-status-pill ${item.residual_risk}`}>{item.residual_risk}</span></td><td>{item.owner_role}</td><td>{item.review_on}</td></tr>)}</tbody></table></div></article></div>;
}

function SystemMap({ agentRun, visibleEvents, setVisibleEvents }: { agentRun: AgentRun | null; visibleEvents: number; setVisibleEvents: (value: number | ((count: number) => number)) => void }) {
  const activeNode = agentRun?.events[Math.max(visibleEvents - 1, 0)]?.node;
  return <main className="fp-system"><section className="fp-system-intro"><p className="fp-kicker">INSPECTABLE BY DESIGN</p><h1>How FinPilot turns a statement into verified advice.</h1><p>Every green path below exists in the application. Mesh handles semantics; deterministic code owns money, authorization and release decisions.</p></section><section className="fp-graph"><div className="fp-flow-line" />{architecture.map((node, index) => <article key={node.id} className={(activeNode?.includes(node.id) || (node.id === "analyst" && activeNode === "behavior_analyst") || (node.id === "advisor" && ["financial_advisor", "revision"].includes(activeNode ?? "")) || (node.id === "verifier" && activeNode === "verification")) ? "active" : ""}><i>{index + 1}</i><span>{node.icon}</span><h3>{node.title}</h3><p>{node.detail}</p><small>{node.runtime}</small></article>)}</section><section className="fp-trace-player"><header><div><b>Trace player</b><span>{agentRun ? `${visibleEvents}/${agentRun.events.length} persisted events` : "Run the live workspace to record a trace"}</span></div><div><button onClick={() => setVisibleEvents((count) => Math.max(0, count - 1))} disabled={!agentRun || visibleEvents === 0}>‹ Prev</button><button className="active" onClick={() => setVisibleEvents((count) => agentRun ? Math.min(agentRun.events.length, count + 1) : 0)} disabled={!agentRun || visibleEvents >= agentRun.events.length}>Next ›</button><button onClick={() => setVisibleEvents(0)} disabled={!agentRun}>↻ Reset</button></div></header>{agentRun && visibleEvents > 0 && <div className="fp-trace-detail"><span>{agentRun.events[visibleEvents - 1].node}</span><strong>{agentRun.events[visibleEvents - 1].summary}</strong><small>{agentRun.events[visibleEvents - 1].model_id ? `Mesh · ${agentRun.events[visibleEvents - 1].model_id}` : "Deterministic control"}</small></div>}</section><section className="fp-stack"><article><span>LANGGRAPH</span><b>Typed conditional workflow</b><small>One bounded revision loop</small></article><article><span>FASTAPI</span><b>Authenticated API boundary</b><small>Tenant derived server-side</small></article><article><span>POSTGRESQL</span><b>Versioned financial truth</b><small>Immutable evidence lineage</small></article><article><span>MESH API</span><b>Only model gateway</b><small>Model, tokens and latency logged</small></article><article><span>NEXT.JS</span><b>Operational console</b><small>No fabricated live values</small></article></section><section className="fp-judge-grid"><header><p className="fp-kicker">CONTROL SURFACE</p><h2>What the implementation proves</h2></header>{["Real CSV truth and idempotency", "Exact recurrence and anomaly evidence", "Chronological forecast backtesting", "Immutable what-if branches", "Distinct Mesh-powered specialists", "Critic and bounded correction loop", "Independent financial verification", "Tenant-scoped audit and lineage"].map((item, index) => <article key={item}><i>{String(index + 1).padStart(2, "0")}</i><span>✓</span><b>{item}</b></article>)}</section></main>;
}
