"use client";

import { type CSSProperties, type DragEvent, type ReactNode, useRef, useState } from "react";
import { SAMPLE_STATEMENT } from "@/lib/client";
import { compactMoney, humanize, longDate, money, percentFromBps, shortDate, titleCase } from "@/lib/format";
import type { Insights } from "@/lib/insights";
import type { AgentRun, Forecast, Scenario, Snapshot, UploadResult, View } from "@/lib/types";
import { Icon, type IconName } from "../ui/icons";
import { Panel, Pill } from "../ui/primitives";
import { RhythmPanel, SpendMixPanel, spendingRhythm } from "./overview";
import { STAGES, type StageId } from "./shared";

/** What the console is doing right now, as far as this screen cares. */
export type Activity = "upload" | "categorize" | "analysis" | "advisor" | null;

type Props = {
  insights: Insights;
  rowCount: number;
  completed: Set<StageId>;
  snapshot: Snapshot | null;
  forecast: Forecast | null;
  scenario: Scenario | null;
  run: AgentRun | null;
  advisorError: string;
  uploadResult: UploadResult | null;
  spendingOnly: boolean;
  busy: boolean;
  activity: Activity;
  onUpload: (file: File) => void;
  onLoadSample: () => void;
  onRun: () => void;
  onNavigate: (view: View) => void;
  onOpenHow: () => void;
};

/* Each stage says plainly whether a model is involved; only categorize and advise call Mesh.
   Categorize is rules first: Mesh sees only the labels the rules could not place. */
const AGENTS: Record<StageId, { icon: IconName; role: string; ai: boolean }> = {
  import: { icon: "upload", role: "Validates every row", ai: false },
  categorize: { icon: "filter", role: "Rules, then Mesh for unclear rows", ai: true },
  analyze: { icon: "sparkline", role: "Finds patterns", ai: false },
  forecast: { icon: "forecast", role: "Looks 30 days ahead", ai: false },
  advise: { icon: "advice", role: "Drafts next moves", ai: true },
  verify: { icon: "governance", role: "Checks every amount", ai: false }
};

const ACCEPT = ".csv,.pdf,text/csv,application/pdf";

/* ---------- empty state ---------- */

function orbitPoint(index: number) {
  const angle = ((-90 + index * 60) * Math.PI) / 180;
  return { x: 50 + 36 * Math.cos(angle), y: 50 + 39 * Math.sin(angle) };
}

function AgentConstellation() {
  return (
    <aside className="constellation" aria-label="The six FinPilot pipeline stages">
      <div className="constellation-head"><span>AGENT PIPELINE</span><i><b />6 stages on standby</i></div>
      <div className="constellation-stage">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <ellipse className="orbit-path" cx="50" cy="50" rx="36" ry="39" />
          {STAGES.map(([id], index) => {
            const point = orbitPoint(index);
            return <line key={id} className={`orbit-link ${AGENTS[id].ai ? "ai" : ""}`} x1="50" y1="50" x2={point.x.toFixed(2)} y2={point.y.toFixed(2)} style={{ animationDelay: `${index * -0.4}s` }} />;
          })}
        </svg>
        <div className="core" aria-hidden="true">
          <span className="core-halo" />
          <span className="core-orb"><Icon name="advice" size={30} /></span>
          <b>FinPilot</b>
          <small>evidence in · actions out</small>
        </div>
        {STAGES.map(([id, label], index) => {
          const point = orbitPoint(index);
          const agent = AGENTS[id];
          return (
            <span key={id} className={`agent-chip ${agent.ai ? "ai" : ""}`} style={{ left: `${point.x}%`, top: `${point.y}%`, "--delay": `${index * 0.55}s` } as CSSProperties}>
              <i><Icon name={agent.icon} size={14} /></i>
              <b>{label}</b>
              <small>{agent.ai ? "Mesh AI" : "Exact code"}</small>
            </span>
          );
        })}
      </div>
      <div className="constellation-foot">
        <span><i className="legend-key ai" />Mesh AI, tightly bounded</span>
        <span><i className="legend-key" />Deterministic code</span>
      </div>
    </aside>
  );
}

function Landing({ busy, onUpload, onLoadSample, onOpenHow }: Pick<Props, "busy" | "onUpload" | "onLoadSample" | "onOpenHow">) {
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  function drop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files[0];
    if (file && !busy) onUpload(file);
  }

  return (
    <section className="glass copilot-landing">
      <div className="landing-copy">
        <p className="ai-eyebrow"><span />AI FINANCIAL COPILOT</p>
        <h2 className="copilot-title">Your money,<br /><span className="gradient-text">finally explained.</span></h2>
        <p className="copilot-lede">Drop in a statement. FinPilot&apos;s agents map your spending, look ahead and suggest practical next steps, and every amount is checked in code before you see it.</p>

        <div className={`composer ${dragging ? "dragging" : ""}`} onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={drop}>
          <div className="composer-main">
            <span className="composer-icon"><Icon name={busy ? "refresh" : "upload"} size={22} className={busy ? "spin" : ""} /></span>
            <div><b>{busy ? "Reading your statement…" : "Drop a bank or card statement here"}</b><small>{busy ? "Validating every row before anything is analysed" : "or choose a file from your device"}</small></div>
          </div>
          <div className="composer-bar">
            <div className="composer-tags" aria-label="Accepted statement formats">
              <span><Icon name="check" size={12} />CSV</span>
              <span><Icon name="check" size={12} />Text-based PDF</span>
              <span>Up to 5 MB</span>
            </div>
            <button className="btn btn-ai" onClick={() => input.current?.click()} disabled={busy}><Icon name="upload" size={14} />Browse files</button>
          </div>
          <input ref={input} type="file" accept={ACCEPT} hidden onChange={(event) => { const file = event.target.files?.[0]; if (file) onUpload(file); event.target.value = ""; }} />
        </div>

        <div className="suggestions">
          <span>Try</span>
          <button className="suggestion" onClick={onLoadSample} disabled={busy}><Icon name="flask" size={14} />Analyse a sample statement</button>
          <a className="suggestion" href={SAMPLE_STATEMENT.path} download><Icon name="download" size={14} />CSV template</a>
          <button className="suggestion" onClick={onOpenHow}><Icon name="system" size={14} />How the agents work</button>
        </div>

        <ul className="trust-strip">
          <li><Icon name="lock" size={14} />No bank login</li>
          <li><Icon name="governance" size={14} />Every amount verified</li>
          <li><Icon name="cpu" size={14} />AI never does the maths</li>
        </ul>
      </div>
      <AgentConstellation />
    </section>
  );
}

/* ---------- statement loaded ---------- */

function briefingPoints(insights: Insights, spendingOnly: boolean) {
  const points: Array<{ icon: IconName; text: ReactNode }> = [];
  const top = insights.categories[0];
  if (top && insights.spend) {
    points.push({ icon: "overview", text: <><b>{humanize(top.key)}</b> takes {Math.round((top.value / insights.spend) * 100)}% of your spending ({money(top.value)}).</> });
  }
  const rhythm = spendingRhythm(insights);
  if (rhythm.busiest) {
    points.push({ icon: "calendar", text: <>Your busiest day was <b>{shortDate(rhythm.busiest[0])}</b> at <b>{money(rhythm.busiest[1])}</b>; {rhythm.quietDays} of {rhythm.spanDays} days had no spending.</> });
  }
  const merchant = insights.merchants[0];
  if (!spendingOnly && insights.income && insights.net >= 0) {
    points.push({ icon: "wallet", text: <>You kept <b>{insights.rate}%</b> of the {compactMoney(insights.income)} that came in.</> });
  } else if (!spendingOnly && insights.income) {
    points.push({ icon: "alert", text: <>Spending ran <b>{money(-insights.net)}</b> ahead of the money that came in.</> });
  } else if (merchant) {
    points.push({ icon: "repeat", text: <><b>{titleCase(merchant.name)}</b> is your top merchant: {merchant.count} {merchant.count === 1 ? "payment" : "payments"}, {money(merchant.value)}.</> });
  }
  return points;
}

function Briefing({ insights, rowCount, snapshot, forecast, scenario, run, uploadResult, spendingOnly, busy, activity, onUpload, onRun }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const latest = insights.balances.at(-1)?.balance ?? null;
  const accepted = run?.verification_status === "accept";
  const status = run ? (accepted ? "Verified" : "Withheld") : forecast ? "Forecast ready" : snapshot?.analysis_mode === "spending" ? "Spending analysed" : "Ready to run";
  const period = insights.firstDay && insights.lastDay ? `${shortDate(insights.firstDay)} – ${longDate(insights.lastDay)}` : null;
  const running = activity === "categorize" || activity === "analysis" || activity === "advisor";

  return (
    <section className="glass briefing">
      <div className="briefing-message">
        <header className="ai-byline">
          <span className={`ai-avatar ${running ? "thinking" : ""}`}><Icon name="advice" size={15} /></span>
          <b>FinPilot</b>
          <small>{uploadResult ? uploadResult.filename : "Statement on file"}{period ? ` · ${period}` : ""}</small>
        </header>
        <h2>I&apos;ve read {rowCount} {rowCount === 1 ? "transaction" : "transactions"}. <span>Here&apos;s what stands out.</span></h2>
        <ul className="briefing-points">
          {briefingPoints(insights, spendingOnly).map((point, index) => <li key={index}><Icon name={point.icon} size={15} /><span>{point.text}</span></li>)}
        </ul>
        <p className="briefing-note"><Icon name="lock" size={13} />Computed exactly from your rows. No model touched these numbers.</p>
        <div className="button-row">
          <button className="btn btn-ai btn-lg" onClick={onRun} disabled={busy}>
            <Icon name={running ? "refresh" : "advice"} size={16} className={running ? "spin" : ""} />
            {running ? "Agents working…" : run ? "Run again" : spendingOnly ? "Find where to cut back" : "Run FinPilot"}
          </button>
          <button className="btn btn-glass btn-lg" onClick={() => input.current?.click()} disabled={busy}><Icon name={activity === "upload" ? "refresh" : "upload"} size={16} className={activity === "upload" ? "spin" : ""} />Upload another</button>
          <input ref={input} type="file" accept={ACCEPT} hidden onChange={(event) => { const file = event.target.files?.[0]; if (file) onUpload(file); event.target.value = ""; }} />
        </div>
      </div>

      <aside className="briefing-stats" aria-live="polite">
        <div className="briefing-figure">
          <small>{latest !== null ? "Known balance" : "Total spending"}</small>
          <strong>{money(latest ?? insights.spend)}</strong>
          <span>{latest !== null ? `Source-provided · ${shortDate(insights.balances.at(-1)?.day ?? "")}` : spendingOnly ? "Card or balance-free statement" : "No source balance loaded"}</span>
        </div>
        <dl className="briefing-grid">
          <div><dt>Ledger</dt><dd>{rowCount} rows</dd></div>
          {spendingOnly
            ? <div><dt>Avg spend day</dt><dd>{money(spendingRhythm(insights).averageDay)}</dd></div>
            : <div><dt>Kept</dt><dd>{insights.rate}%</dd></div>}
          {forecast || !spendingOnly
            ? <div><dt>30-day low</dt><dd>{forecast ? compactMoney(scenario?.minimum_balance_minor ?? forecast.minimum_balance_minor) : "Pending"}</dd></div>
            : <div><dt>30-day spend</dt><dd>{snapshot?.spending ? compactMoney(snapshot.spending.projected_30_day_spend_minor) : "Pending"}</dd></div>}
          <div><dt>Verdict</dt><dd className={run ? (accepted ? "positive" : "negative") : ""}>{status}</dd></div>
        </dl>
        {uploadResult && <div className="briefing-file"><Icon name="check" size={14} /><span><b>{uploadResult.source_format.toUpperCase()} verified</b><small>{uploadResult.accepted_rows} accepted · {uploadResult.duplicate_rows} duplicate · {uploadResult.rejected_rows} rejected</small></span></div>}
      </aside>
    </section>
  );
}

function AgentTrack({ completed, busy, run, spendingOnly }: Pick<Props, "completed" | "busy" | "run" | "spendingOnly">) {
  const modelCalls = run ? run.events.filter((event) => event.model_id).length : 0;
  return (
    <section className="glass agent-track" aria-label="Agent pipeline progress">
      <header>
        <div><p className="eyebrow">AGENT PIPELINE</p><h3>{run ? "Six stages, one auditable trace" : busy ? "Agents at work" : "Six stages, ready when you are"}</h3></div>
        {run
          ? <div className="track-meta"><span><Icon name="cpu" size={13} />{modelCalls} model calls</span><span><Icon name="bolt" size={13} />{(run.total_input_tokens + run.total_output_tokens).toLocaleString("en-IN")} tokens</span><span><Icon name="clock" size={13} />{(run.total_latency_ms / 1000).toFixed(1)} s</span></div>
          : <Pill tone={busy ? "info" : "neutral"} icon={busy ? "refresh" : "clock"}>{completed.size}/{STAGES.length} complete</Pill>}
      </header>
      <ol>
        {STAGES.map(([id, label], index) => {
          const done = completed.has(id);
          const active = busy && !done && STAGES.slice(0, index).every(([prior]) => completed.has(prior));
          const agent = AGENTS[id];
          return (
            <li key={id} className={done ? "done" : active ? "active" : ""}>
              <span className="track-glyph"><Icon name={done ? "check" : agent.icon} size={15} /></span>
              <b>{label}</b>
              <small>{id === "forecast" && spendingOnly ? "Projects 30-day spend" : agent.role}</small>
              <em className={agent.ai ? "ai" : ""}>{agent.ai ? "Mesh AI" : "Exact code"}</em>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function Thinking({ activity, completed }: { activity: Activity; completed: Set<StageId> }) {
  const next = STAGES.find(([id]) => !completed.has(id));
  const line = activity === "advisor"
    ? "The advisor is drafting options while the verifier checks every amount against your ledger…"
    : activity === "categorize"
      ? "Asking Mesh to label the payments the rules could not place. Only the labels are sent, never amounts or balances…"
      : "Finding recurring payments, unusual charges and what the coming weeks look like…";
  return (
    <section className="glass answer thinking" aria-live="polite" aria-busy="true">
      <header className="ai-byline">
        <span className="ai-avatar thinking"><Icon name="advice" size={15} /></span>
        <b>FinPilot</b>
        <small>{next ? `${next[1]} stage running` : "Finishing up"}</small>
      </header>
      <p className="thinking-line">{line}</p>
      <div className="shimmer-lines" aria-hidden="true"><i /><i /><i /></div>
    </section>
  );
}

function Answer({ run, spendingOnly, onNavigate }: { run: AgentRun; spendingOnly: boolean; onNavigate: (view: View) => void }) {
  const accepted = run.verification_status === "accept";
  const modelCalls = run.events.filter((event) => event.model_id).length;
  return (
    <section className="glass answer" aria-live="polite">
      {run.question && <div className="ask-bubble"><small>You asked</small><p>{run.question}</p></div>}
      <header className="ai-byline">
        <span className="ai-avatar"><Icon name="advice" size={15} /></span>
        <b>FinPilot</b>
        <small>{run.model_id} · {modelCalls} model {modelCalls === 1 ? "call" : "calls"} · {(run.total_latency_ms / 1000).toFixed(1)} s</small>
        <Pill tone={accepted ? "good" : "bad"} icon={accepted ? "governance" : "alert"}>{accepted ? "Amounts verified" : "Withheld by verifier"}</Pill>
      </header>
      <h2 className="answer-title">{accepted ? (spendingOnly ? "Here's where you can spend less" : "Here's how to spend less and save more") : "I held these recommendations back"}</h2>
      {accepted ? (
        <ol className="answer-list">
          {run.recommendations.map((item) => (
            <li key={item.id}>
              <span className="answer-rank">{item.rank}</span>
              <div className="answer-body">
                <b>{item.title}</b>
                <p>{item.explanation}</p>
                <div className="answer-meta">
                  <span><Icon name="bolt" size={12} />{percentFromBps(item.confidence_bps)} confidence</span>
                  <span><Icon name="doc" size={12} />{item.evidence_ids.length} evidence {item.evidence_ids.length === 1 ? "record" : "records"}</span>
                </div>
              </div>
              {item.amount_minor !== null && <strong className="answer-amount">{money(Math.abs(item.amount_minor), item.currency)}</strong>}
            </li>
          ))}
        </ol>
      ) : <p className="answer-prose">{run.final_response}</p>}
      <details className="answer-trace">
        <summary><Icon name="audit" size={14} />How FinPilot reached this<span>{run.events.length} steps</span><Icon name="chevronDown" size={14} /></summary>
        <ol>
          {run.events.map((event) => (
            <li key={event.id} className={event.model_id ? "ai" : ""}>
              <span>{event.sequence}</span>
              <div><b>{humanize(event.node)}</b><p>{event.summary}</p></div>
              <em>{event.model_id ? "Mesh AI" : "Exact code"}</em>
            </li>
          ))}
        </ol>
      </details>
      <footer className="answer-foot">
        <button className="text-link as-button" onClick={() => onNavigate("advice")}><Icon name="advice" size={14} />Ask a follow-up</button>
        <button className="text-link as-button" onClick={() => onNavigate("audit")}><Icon name="audit" size={14} />Full audit trail</button>
      </footer>
    </section>
  );
}

function ExploreRow({ rowCount, forecast, scenario, run, spendingOnly, onNavigate }: Pick<Props, "rowCount" | "forecast" | "scenario" | "run" | "spendingOnly" | "onNavigate">) {
  const tiles: Array<{ view: View; icon: IconName; label: string; detail: string }> = [
    { view: "overview", icon: "overview", label: "Overview", detail: "Cash position and signals" },
    { view: "ledger", icon: "ledger", label: "Ledger", detail: `${rowCount} rows with provenance` },
    { view: "forecast", icon: "forecast", label: "Forecast", detail: forecast ? `30-day low ${compactMoney(scenario?.minimum_balance_minor ?? forecast.minimum_balance_minor)}` : spendingOnly ? "Projected spending" : "Balance what-ifs" },
    { view: "audit", icon: "audit", label: "Audit trail", detail: run ? `${run.events.length} persisted events` : "Every decision, recorded" }
  ];
  return (
    <nav className="explore-row" aria-label="Explore the full analysis">
      {tiles.map((tile) => (
        <button key={tile.view} className="glass explore-tile" onClick={() => onNavigate(tile.view)}>
          <span><Icon name={tile.icon} size={16} /></span>
          <div><b>{tile.label}</b><small>{tile.detail}</small></div>
          <Icon name="chevronRight" size={15} />
        </button>
      ))}
    </nav>
  );
}

export function LiveDemo(props: Props) {
  const { insights, rowCount, completed, run, advisorError, spendingOnly, busy, activity, onRun, onNavigate } = props;

  if (!rowCount) return <div className="copilot"><Landing busy={busy} onUpload={props.onUpload} onLoadSample={props.onLoadSample} onOpenHow={props.onOpenHow} /></div>;

  const running = activity === "categorize" || activity === "analysis" || activity === "advisor";
  return (
    <div className="copilot">
      <Briefing {...props} />

      {advisorError && !running && <Panel className="advisor-recovery" aria-live="polite">
        <span className="advisor-recovery-icon"><Icon name="refresh" size={19} /></span>
        <div><p className="eyebrow">AI ADVISOR</p><h3>Your financial analysis is ready</h3><p>{advisorError}</p></div>
        <button className="btn btn-primary" onClick={onRun} disabled={busy}><Icon name={busy ? "refresh" : "advice"} size={14} className={busy ? "spin" : ""} />{busy ? "Retrying…" : "Retry AI advice"}</button>
      </Panel>}

      {running ? <Thinking activity={activity} completed={completed} /> : run && <Answer run={run} spendingOnly={spendingOnly} onNavigate={onNavigate} />}

      <AgentTrack completed={completed} busy={running} run={run} spendingOnly={spendingOnly} />

      <div className="view-grid">
        <RhythmPanel insights={insights} />
        <SpendMixPanel insights={insights} />
      </div>

      <ExploreRow {...props} />
    </div>
  );
}
