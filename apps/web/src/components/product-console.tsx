"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AdvisorView, AuditView } from "./console/advisor";
import { Brand } from "./console/brand";
import { ForecastView, type RunConfig } from "./console/forecast";
import { DigestView, GovernanceView } from "./console/governance";
import { Inspector } from "./console/inspector";
import { Ledger } from "./console/ledger";
import { LiveDemo } from "./console/live-demo";
import { Overview } from "./console/overview";
import { type StageId, VIEWS } from "./console/shared";
import { Sidebar } from "./console/sidebar";
import { SystemMap } from "./console/system-map";
import { type Command, CommandPalette } from "./ui/command-palette";
import { Icon } from "./ui/icons";
import { Kbd } from "./ui/primitives";
import { ThemeToggle, setThemePreference } from "./ui/theme";
import { ToastStack, useToasts } from "./ui/toast";
import { DEFAULT_MAPPING, SAMPLE_STATEMENT, type Session, request } from "@/lib/client";
import { addDays, compactMoney, humanize, minorFromRupees } from "@/lib/format";
import { deriveInsights } from "@/lib/insights";
import type {
  Account, AgentRun, DigestPreference, EvaluationRun, Forecast, GovernanceArtifact, GovernanceData,
  GovernanceRisk, GovernanceSummary, HumanReview, Notification, Scenario, Snapshot, Tenant, Transaction,
  UploadResult, View
} from "@/lib/types";

type Busy = null | "demo" | "account" | "upload" | "analysis" | "advisor" | "governance" | "digest" | "correction";
type ActiveSession = { token: string; tenant: Tenant };
type ProductMode = "demo" | "console" | "system";

const LEDGER_PAGE = 200;
const LEDGER_CAP = 1000;
const DEFAULT_QUESTION = "Can I afford this purchase without jeopardizing my cash buffer?";
const INITIAL_CONFIG: RunConfig = { asOf: "", horizon: 30, scenarioEnabled: true, scenarioName: "Laptop purchase", scenarioAmount: "75000.00", scenarioDate: "" };

function message(caught: unknown, fallback: string) {
  return caught instanceof Error ? caught.message : fallback;
}

/** Keeps the what-if date inside (as_of, as_of + horizon], which the scenario API requires. */
function normalizeConfig(next: RunConfig): RunConfig {
  if (!next.asOf) return next;
  const min = addDays(next.asOf, 1);
  const max = addDays(next.asOf, next.horizon);
  if (!next.scenarioDate || next.scenarioDate < min || next.scenarioDate > max) {
    return { ...next, scenarioDate: addDays(next.asOf, Math.min(10, next.horizon)) };
  }
  return next;
}

async function fetchLedger(auth: Session) {
  const items: Transaction[] = [];
  let total = 0;
  for (let offset = 0; offset < LEDGER_CAP; offset += LEDGER_PAGE) {
    const page = await request<{ items: Transaction[]; total: number }>(`/api/v1/transactions?limit=${LEDGER_PAGE}&offset=${offset}`, {}, auth);
    items.push(...page.items);
    total = page.total;
    if (items.length >= total || page.items.length < LEDGER_PAGE) break;
  }
  return { items, total };
}

async function sampleFile() {
  const response = await fetch(SAMPLE_STATEMENT.path);
  if (!response.ok) throw new Error("The bundled synthetic statement could not be loaded");
  return new File([await response.blob()], SAMPLE_STATEMENT.filename, { type: "text/csv" });
}

function uploadStatement(auth: Session, accountId: string, file: File) {
  const body = new FormData();
  body.set("mapping", DEFAULT_MAPPING);
  body.set("file", file);
  return request<UploadResult>(`/api/v1/accounts/${accountId}/transaction-uploads`, { method: "POST", body }, auth);
}

export function ProductConsole() {
  const [session, setSession] = useState<ActiveSession | null>(null);
  const [mode, setMode] = useState<ProductMode>("demo");
  const [view, setView] = useState<View>("overview");
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [transactionTotal, setTransactionTotal] = useState(0);
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [agentRun, setAgentRun] = useState<AgentRun | null>(null);
  const [visibleEvents, setVisibleEvents] = useState(0);
  const [governance, setGovernance] = useState<GovernanceData | null>(null);
  const [digestPreference, setDigestPreference] = useState<DigestPreference | null>(null);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [config, setConfigState] = useState<RunConfig>(INITIAL_CONFIG);
  const [question, setQuestion] = useState(DEFAULT_QUESTION);
  const [busy, setBusy] = useState<Busy>(null);
  const [startupError, setStartupError] = useState("");
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const bootstrapStarted = useRef(false);
  const { toasts, push, dismiss } = useToasts();

  const auth: Session | undefined = session ? { token: session.token, tenantId: session.tenant.id } : undefined;
  const insights = useMemo(() => deriveInsights(transactions), [transactions]);

  function navigate(next: View) {
    if (next === "system") {
      setMode("system");
      window.scrollTo({ top: 0 });
      return;
    }
    setView(next);
    setMode("console");
    window.scrollTo({ top: 0 });
  }

  function setConfig(patch: Partial<RunConfig>) {
    setConfigState((current) => normalizeConfig({ ...current, ...patch }));
  }

  /* ---------- loading ---------- */

  async function loadGovernance(scope: Session | undefined = auth) {
    if (!scope) return;
    const [summary, artifacts, risks, evaluations, reviews] = await Promise.all([
      request<GovernanceSummary>("/api/v1/governance/summary", {}, scope),
      request<GovernanceArtifact[]>("/api/v1/governance/artifacts", {}, scope),
      request<GovernanceRisk[]>("/api/v1/governance/risks", {}, scope),
      request<EvaluationRun[]>("/api/v1/governance/evaluations", {}, scope),
      request<HumanReview[]>("/api/v1/governance/reviews", {}, scope)
    ]);
    setGovernance({ summary, artifacts, risks, evaluations, reviews });
  }

  async function loadDigests(scope: Session | undefined = auth) {
    if (!scope) return;
    const [preference, delivered] = await Promise.all([
      request<DigestPreference | null>("/api/v1/digests/preference", {}, scope),
      request<Notification[]>("/api/v1/digests/notifications", {}, scope)
    ]);
    setDigestPreference(preference);
    setNotifications(delivered);
  }

  async function loadWorkspace(scope: Session) {
    const [nextAccounts, ledger] = await Promise.all([request<Account[]>("/api/v1/accounts", {}, scope), fetchLedger(scope)]);
    setAccounts(nextAccounts);
    setTransactions(ledger.items);
    setTransactionTotal(ledger.total);
    const known = ledger.items.find((item) => item.balance_minor !== null);
    if (known) setConfig({ asOf: known.transaction_date });
    const results = await Promise.allSettled([loadGovernance(scope), loadDigests(scope)]);
    const failed = results.find((result) => result.status === "rejected");
    if (failed) push({ tone: "error", title: "Some workspace panels could not load", body: message(failed.reason, "Governance or digest data is unavailable") });
  }

  async function openSession(token: string) {
    const me = await request<{ tenants: Tenant[] }>("/api/v1/auth/me", {}, { token });
    if (!me.tenants.length) throw new Error("No household membership is available");
    const tenant = me.tenants[0];
    const scope = { token, tenantId: tenant.id };
    return { scope, tenant };
  }

  async function startDemo() {
    setBusy("demo");
    setStartupError("");
    try {
      const { access_token: token } = await request<{ access_token: string }>("/api/v1/workspace/bootstrap", { method: "POST" });
      const { scope, tenant } = await openSession(token);
      const account = await request<Account>("/api/v1/accounts", {
        method: "POST",
        body: JSON.stringify({ name: SAMPLE_STATEMENT.accountName, currency: "INR", external_reference: SAMPLE_STATEMENT.externalReference })
      }, scope);
      const result = await uploadStatement(scope, account.id, await sampleFile());
      setUploadResult(result);
      await loadWorkspace(scope);
      setSession({ token, tenant });
      navigate("overview");
      push({ tone: "success", title: "Synthetic household ready", body: `${result.accepted_rows} rows imported · ${result.duplicate_rows} duplicate · ${result.rejected_rows} rejected. Next: Run analysis.` });
    } catch (caught) {
      setStartupError(message(caught, "Could not open the synthetic workspace"));
    } finally {
      setBusy(null);
    }
  }

  /* ---------- ledger ---------- */

  async function ensureAccount(scope: Session) {
    if (accounts[0]) return accounts[0];
    const account = await request<Account>("/api/v1/accounts", {
      method: "POST",
      body: JSON.stringify({ name: "Primary account", currency: "INR", external_reference: crypto.randomUUID() })
    }, scope);
    setAccounts([account]);
    return account;
  }

  async function createAccount() {
    if (!auth) return;
    setBusy("account");
    try {
      await ensureAccount(auth);
      push({ tone: "success", title: "Primary account created", body: "An empty INR ledger — import a statement next." });
    } catch (caught) {
      push({ tone: "error", title: "Could not create account", body: message(caught, "Unexpected account error") });
    } finally {
      setBusy(null);
    }
  }

  async function importFile(file: File | "sample") {
    if (!auth) return;
    setBusy("upload");
    try {
      const account = await ensureAccount(auth);
      const result = await uploadStatement(auth, account.id, file === "sample" ? await sampleFile() : file);
      setUploadResult(result);
      setSnapshot(null);
      setForecast(null);
      setScenario(null);
      await loadWorkspace(auth);
      push({
        tone: result.rejected_rows && !result.accepted_rows ? "error" : "success",
        title: result.replayed ? "Statement already imported" : "Statement imported",
        body: `${result.accepted_rows} accepted · ${result.duplicate_rows} duplicate · ${result.rejected_rows} rejected`
      });
    } catch (caught) {
      push({ tone: "error", title: "Import failed", body: message(caught, "The statement could not be imported") });
    } finally {
      setBusy(null);
    }
  }

  async function correctCategory(transaction: Transaction, category: string, reason: string) {
    if (!auth) return false;
    setBusy("correction");
    try {
      const updated = await request<Transaction>(`/api/v1/transactions/${transaction.id}/category`, { method: "PATCH", body: JSON.stringify({ category, reason }) }, auth);
      setTransactions((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      push({ tone: "success", title: "Correction recorded", body: `${humanize(transaction.category)} → ${humanize(category)}. Re-run analysis to version a new snapshot.` });
      return true;
    } catch (caught) {
      push({ tone: "error", title: "Correction failed", body: message(caught, "Could not save the correction") });
      return false;
    } finally {
      setBusy(null);
    }
  }

  /* ---------- analysis & advice ---------- */

  async function runAnalysis(): Promise<{ forecast: Forecast; scenario: Scenario | null } | null> {
    if (!auth || !accounts[0] || !transactions.length) {
      push({ tone: "error", title: "Import a statement first", body: "The analysis needs persisted ledger rows." });
      return null;
    }
    if (!config.asOf) {
      push({ tone: "error", title: "Choose a known-balance date", body: "The latest transaction on that date must carry a source balance." });
      return null;
    }
    let shockMinor = 0;
    if (config.scenarioEnabled) {
      try {
        shockMinor = minorFromRupees(config.scenarioAmount);
      } catch (caught) {
        push({ tone: "error", title: "Check the purchase amount", body: message(caught, "Invalid amount") });
        return null;
      }
    }
    setBusy("analysis");
    try {
      const nextSnapshot = await request<Snapshot>("/api/v1/analytics/snapshots", { method: "POST", body: JSON.stringify({ account_id: accounts[0].id, as_of: config.asOf }) }, auth);
      setSnapshot(nextSnapshot);
      const nextForecast = await request<Forecast>("/api/v1/analytics/forecasts", { method: "POST", body: JSON.stringify({ snapshot_id: nextSnapshot.id, horizon_days: config.horizon }) }, auth);
      setForecast(nextForecast);
      let nextScenario: Scenario | null = null;
      if (config.scenarioEnabled && shockMinor > 0) {
        const label = config.scenarioName.trim() || "Planned purchase";
        nextScenario = await request<Scenario>("/api/v1/analytics/scenarios", {
          method: "POST",
          body: JSON.stringify({ forecast_id: nextForecast.id, name: label, shocks: [{ day: config.scenarioDate, amount_minor: -shockMinor, label }] })
        }, auth);
      }
      setScenario(nextScenario);
      push({
        tone: nextScenario?.first_shortfall_date ? "error" : "success",
        title: nextScenario?.first_shortfall_date ? "Analysis complete — shortfall projected" : "Analysis complete",
        body: `${nextSnapshot.recurring_patterns.length} recurring patterns · ${nextSnapshot.anomaly_results.length} anomalies · low point ${compactMoney(nextScenario?.minimum_balance_minor ?? nextForecast.minimum_balance_minor)}`
      });
      return { forecast: nextForecast, scenario: nextScenario };
    } catch (caught) {
      push({ tone: "error", title: "Analysis stopped safely", body: message(caught, "Could not calculate the forecast") });
      return null;
    } finally {
      setBusy(null);
    }
  }

  async function askAdvisor(input?: { forecast: Forecast; scenario: Scenario | null }) {
    const baseline = input?.forecast ?? forecast;
    const branch = input ? input.scenario : scenario;
    if (!auth || !baseline) {
      push({ tone: "error", title: "Run the analysis first", body: "The advisor only reasons over a versioned forecast." });
      return;
    }
    setBusy("advisor");
    setAgentRun(null);
    setVisibleEvents(0);
    setInspectorOpen(true);
    try {
      const run = await request<AgentRun>("/api/v1/agent-runs", { method: "POST", body: JSON.stringify({ forecast_id: baseline.id, scenario_id: branch?.id ?? null, question }) }, auth);
      setAgentRun(run);
      setVisibleEvents(1);
      navigate("advice");
      await loadGovernance(auth).catch(() => undefined);
      push({ tone: run.verification_status === "accept" ? "success" : "error", title: run.verification_status === "accept" ? "Advice verified and released" : "Advice withheld by the verifier", body: `${run.events.length} events persisted · ${run.recommendations.length} recommendations` });
    } catch (caught) {
      push({ tone: "error", title: "Advisor step failed safely", body: message(caught, "No advice was released") });
    } finally {
      setBusy(null);
    }
  }

  async function runPipeline() {
    const result = await runAnalysis();
    if (result) await askAdvisor(result);
  }

  /* ---------- governance & digests ---------- */

  async function createGovernanceDemo() {
    if (!auth) return;
    setBusy("governance");
    try {
      await request("/api/v1/governance/demo-review", { method: "POST", body: "{}" }, auth);
      await loadGovernance(auth);
      push({ tone: "info", title: "Synthetic review case created", body: "An automatically rejected recommendation is waiting for a reviewer." });
    } catch (caught) {
      push({ tone: "error", title: "Could not create the governance demo", body: message(caught, "Unexpected governance error") });
    } finally {
      setBusy(null);
    }
  }

  async function rejectReview(reviewId: string) {
    if (!auth) return;
    setBusy("governance");
    try {
      await request(`/api/v1/governance/reviews/${reviewId}/decisions`, { method: "POST", body: JSON.stringify({ outcome: "reject", reason: "Unsafe guarantee remains forbidden; deterministic controls cannot be overridden." }) }, auth);
      await loadGovernance(auth);
      push({ tone: "success", title: "Reviewer decision recorded", body: "The rejection is stored with exact artifact lineage." });
    } catch (caught) {
      push({ tone: "error", title: "Could not record the decision", body: message(caught, "Unexpected governance error") });
    } finally {
      setBusy(null);
    }
  }

  async function saveDigestPreference(enabled: boolean) {
    if (!auth) return;
    setBusy("digest");
    try {
      await request("/api/v1/digests/preference", { method: "PUT", body: JSON.stringify({ enabled, weekday: 0, local_time: "09:00", timezone: "Asia/Kolkata" }) }, auth);
      await loadDigests(auth);
      push({ tone: "success", title: enabled ? "Weekly digest enabled" : "Weekly digest disabled" });
    } catch (caught) {
      push({ tone: "error", title: "Could not update the digest schedule", body: message(caught, "Unexpected digest error") });
    } finally {
      setBusy(null);
    }
  }

  /* ---------- effects ---------- */

  useEffect(() => {
    if (bootstrapStarted.current) return;
    bootstrapStarted.current = true;
    void startDemo();
    // The synthetic workspace is intentionally provisioned once per browser mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!agentRun || visibleEvents <= 0 || visibleEvents >= agentRun.events.length) return;
    const timer = window.setTimeout(() => setVisibleEvents((count) => count + 1), 650);
    return () => window.clearTimeout(timer);
  }, [agentRun, visibleEvents]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((open) => !open);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  /* ---------- render ---------- */

  if (!session) {
    return (
      <>
        <div className="auth-shell startup-shell">
          <header className="auth-topbar"><Brand /><ThemeToggle /></header>
          <main className="startup-layout">
            <section className="glass-strong startup-card" aria-live="polite">
              <span className="startup-mark"><Icon name={startupError ? "alert" : "refresh"} size={22} className={!startupError ? "spin" : ""} /></span>
              <p className="eyebrow">FINPILOT WORKSPACE</p>
              <h1>{startupError ? "The workspace could not open" : "Preparing your decision cockpit"}</h1>
              <p className="lede">{startupError || "Loading a private synthetic household and its auditable financial ledger. No login is required."}</p>
              {startupError ? (
                <button className="btn btn-primary btn-lg" onClick={() => void startDemo()} disabled={busy !== null}><Icon name="refresh" size={15} />Try again</button>
              ) : <div className="startup-progress"><i /></div>}
              <small className="fine-print"><Icon name="lock" size={12} />Synthetic data only · isolated workspace · deterministic money math</small>
            </section>
          </main>
        </div>
        <ToastStack toasts={toasts} dismiss={dismiss} />
      </>
    );
  }

  const completed = new Set<StageId>();
  if (transactions.length) { completed.add("import"); completed.add("categorize"); }
  if (snapshot) completed.add("analyze");
  if (forecast) completed.add("forecast");
  if (agentRun) completed.add("advise");
  if (agentRun?.verification_status === "accept") completed.add("verify");

  const meta = mode === "demo"
    ? { label: "Live Demo", subtitle: "A guided, end-to-end decision run" }
    : mode === "system"
      ? { label: "How it works", subtitle: "Architecture, agents and trace replay" }
      : VIEWS.find((item) => item.id === view) ?? VIEWS[0];
  const working = busy !== null;
  const canAnalyse = Boolean(accounts[0] && transactions.length && config.asOf);

  const commands: Command[] = [
    ...VIEWS.map((item) => ({ id: `view-${item.id}`, label: item.label, group: "Go to", icon: item.icon, run: () => navigate(item.id) })),
    { id: "sample", label: "Load synthetic sample statement", group: "Actions", icon: "bolt", disabled: working, run: () => void importFile("sample") },
    { id: "analysis", label: "Run deterministic analysis", group: "Actions", icon: "play", disabled: working || !canAnalyse, run: () => { navigate("forecast"); void runAnalysis(); } },
    { id: "advisor", label: "Ask the verified advisor", group: "Actions", icon: "advice", disabled: working || !forecast, run: () => void askAdvisor() },
    { id: "inspector", label: inspectorOpen ? "Hide agent log" : "Show agent log", group: "Actions", icon: "terminal", run: () => setInspectorOpen((open) => !open) },
    { id: "download", label: "Download sample CSV", group: "Actions", icon: "download", run: () => { const link = document.createElement("a"); link.href = SAMPLE_STATEMENT.path; link.download = SAMPLE_STATEMENT.filename; link.click(); } },
    { id: "theme-light", label: "Light appearance", group: "Appearance", icon: "sun", run: () => setThemePreference("light") },
    { id: "theme-dark", label: "Dark appearance", group: "Appearance", icon: "moon", run: () => setThemePreference("dark") },
    { id: "theme-system", label: "Match system appearance", group: "Appearance", icon: "monitor", run: () => setThemePreference("system") },
  ];

  return (
    <div className={`app-shell ${inspectorOpen ? "inspector-open" : ""}`}>
      <Sidebar
        tenant={session.tenant}
        view={mode === "demo" ? null : mode === "system" ? "system" : view}
        open={sidebarOpen}
        badges={{ ledger: transactionTotal, governance: governance?.summary.pending_reviews, advice: agentRun?.recommendations.length }}
        completed={completed}
        onNavigate={navigate}
        onClose={() => setSidebarOpen(false)}
      />
      {sidebarOpen && <div className="scrim" onClick={() => setSidebarOpen(false)} aria-hidden="true" />}

      <main className="app-main">
        <header className="glass toolbar">
          <button className="icon-btn menu-btn" onClick={() => setSidebarOpen(true)} aria-label="Open navigation"><Icon name="sidebar" size={17} /></button>
          <div className="toolbar-title"><h1>{meta.label}</h1><small>{meta.subtitle}</small></div>
          <div className="mode-switch" role="tablist" aria-label="Product mode">
            <button role="tab" aria-selected={mode === "demo"} className={mode === "demo" ? "active" : ""} onClick={() => setMode("demo")}><Icon name="play" size={13} />Live Demo</button>
            <button role="tab" aria-selected={mode === "console"} className={mode === "console" ? "active" : ""} onClick={() => setMode("console")}><Icon name="terminal" size={13} />Console</button>
            <button role="tab" aria-selected={mode === "system"} className={mode === "system" ? "active" : ""} onClick={() => setMode("system")}><Icon name="system" size={13} />How it works</button>
          </div>
          <button className="search-trigger" onClick={() => setPaletteOpen(true)} aria-label="Open command palette"><Icon name="search" size={15} /><span>Search or jump to…</span><Kbd>⌘K</Kbd></button>
          <ThemeToggle />
          <button className={`icon-btn ${inspectorOpen ? "active" : ""}`} onClick={() => setInspectorOpen((open) => !open)} aria-label="Toggle agent log" aria-pressed={inspectorOpen}><Icon name="terminal" size={17} />{agentRun && <span className="badge-dot" />}</button>
          <button className="btn btn-primary run-btn" onClick={runPipeline} disabled={working || !canAnalyse} title="Deterministic analysis, then the Mesh-powered advisor graph">
            <Icon name={working ? "refresh" : "play"} size={13} className={working ? "spin" : ""} />
            <span>{busy === "analysis" ? "Analysing…" : busy === "advisor" ? "Agents working…" : "Run FinPilot"}</span>
          </button>
        </header>

        <div className={`view ${working ? "is-busy" : ""}`} key={view}>
          {mode === "demo" && <LiveDemo insights={insights} rowCount={transactionTotal} completed={completed} snapshot={snapshot} forecast={forecast} scenario={scenario} run={agentRun} busy={working} onRun={() => void runPipeline()} onOpenConsole={() => setMode("console")} onOpenHow={() => setMode("system")} />}
          {mode === "console" && view === "overview" && <Overview insights={insights} transactions={transactions} snapshot={snapshot} hasAccount={accounts.length > 0} busy={working} onNavigate={navigate} onLoadSample={() => void importFile("sample")} onRunAnalysis={() => void runAnalysis()} />}
          {mode === "console" && view === "ledger" && <Ledger transactions={transactions} total={transactionTotal} hasAccount={accounts.length > 0} busy={working} uploadResult={uploadResult} onUpload={(file) => void importFile(file)} onLoadSample={() => void importFile("sample")} onCreateAccount={() => void createAccount()} onCorrect={correctCategory} />}
          {mode === "console" && view === "forecast" && <ForecastView config={config} setConfig={setConfig} snapshot={snapshot} forecast={forecast} scenario={scenario} canRun={canAnalyse} busy={working} onRunAnalysis={() => void runAnalysis()} onAskAdvisor={() => void askAdvisor()} />}
          {mode === "console" && view === "advice" && <AdvisorView run={agentRun} forecast={forecast} question={question} setQuestion={setQuestion} visibleEvents={visibleEvents} busy={working} onAsk={() => void askAdvisor()} />}
          {mode === "console" && view === "audit" && <AuditView run={agentRun} />}
          {mode === "console" && view === "governance" && <GovernanceView data={governance} busy={working} createDemo={() => void createGovernanceDemo()} rejectReview={(id) => void rejectReview(id)} />}
          {mode === "console" && view === "digests" && <DigestView preference={digestPreference} notifications={notifications} busy={working} savePreference={(enabled) => void saveDigestPreference(enabled)} />}
          {mode === "system" && <SystemMap agentRun={agentRun} visibleEvents={visibleEvents} setVisibleEvents={setVisibleEvents} />}
        </div>
      </main>

      {inspectorOpen && <Inspector run={agentRun} visibleEvents={visibleEvents} running={busy === "advisor" || busy === "analysis"} onClose={() => setInspectorOpen(false)} />}
      {paletteOpen && <CommandPalette commands={commands} onClose={() => setPaletteOpen(false)} />}
      <ToastStack toasts={toasts} dismiss={dismiss} />
    </div>
  );
}
