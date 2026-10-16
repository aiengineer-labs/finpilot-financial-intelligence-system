"use client";

import type { AgentRun } from "@/lib/types";
import { Icon, type IconName } from "../ui/icons";
import { Panel, PanelHeader, Pill } from "../ui/primitives";

const ARCHITECTURE: Array<{ id: string; icon: IconName; title: string; detail: string; runtime: string; model: boolean; nodes: string[] }> = [
  { id: "ingest", icon: "upload", title: "CSV ingestion", detail: "Validates UTF-8, explicit dates, exact minor units, duplicates, transfers and row errors.", runtime: "FastAPI · deterministic", model: false, nodes: [] },
  { id: "truth", icon: "bank", title: "PostgreSQL truth", detail: "Tenant-scoped ledger, immutable snapshot manifests and correction lineage.", runtime: "SQLAlchemy · Alembic", model: false, nodes: [] },
  { id: "analyst", icon: "sparkline", title: "Behavior analyst", detail: "Explains recurrence and robust anomaly evidence without performing arithmetic.", runtime: "LangGraph · Mesh", model: true, nodes: ["behavior_analyst", "analyst"] },
  { id: "forecast", icon: "forecast", title: "Forecast engine", detail: "Builds reproducible daily 30/60/90-day curves from known balances and patterns.", runtime: "Python integer math", model: false, nodes: ["forecast"] },
  { id: "advisor", icon: "advice", title: "Financial advisor", detail: "Drafts bounded options citing only supplied snapshot, forecast and scenario evidence.", runtime: "LangGraph · Mesh", model: true, nodes: ["financial_advisor", "revision", "advisor"] },
  { id: "critic", icon: "search", title: "Critic loop", detail: "Challenges unsupported or overconfident advice and requests one bounded revision.", runtime: "LangGraph · Mesh", model: true, nodes: ["critic"] },
  { id: "verifier", icon: "governance", title: "Financial verifier", detail: "Rejects unknown amounts, evidence, currencies and prohibited certainty in plain code.", runtime: "Fail-closed · no LLM", model: false, nodes: ["verification", "verifier"] },
  { id: "audit", icon: "audit", title: "Audit ledger", detail: "Persists every transition, model ID, latency, tokens, rejected draft and final decision.", runtime: "PostgreSQL · immutable lineage", model: false, nodes: ["audit"] },
  { id: "digest", icon: "digests", title: "Digest dispatcher", detail: "Claims due weekly work once and records an idempotent in-app delivery.", runtime: "Signed Vercel Cron · SQL lock", model: false, nodes: ["digest"] }
];

const STACK = [
  ["LangGraph", "Typed conditional workflow", "One bounded revision loop"],
  ["FastAPI", "Isolated API boundary", "Synthetic workspace server-side"],
  ["PostgreSQL", "Versioned financial truth", "Immutable evidence lineage"],
  ["Mesh API", "Only model gateway", "Model, tokens and latency logged"],
  ["Next.js", "Operational console", "No fabricated live values"]
];

const CONTROLS = [
  "Real CSV truth and idempotency", "Exact recurrence and anomaly evidence", "Chronological forecast backtesting",
  "Immutable what-if branches", "Distinct Mesh-powered specialists", "Critic and bounded correction loop",
  "Independent financial verification", "Tenant-scoped audit and lineage", "Durable idempotent digest delivery"
];

type Props = { agentRun: AgentRun | null; visibleEvents: number; setVisibleEvents: (value: number | ((count: number) => number)) => void };

export function SystemMap({ agentRun, visibleEvents, setVisibleEvents }: Props) {
  const current = agentRun && visibleEvents > 0 ? agentRun.events[visibleEvents - 1] : null;
  const activeNode = current?.node ?? "";
  return (
    <div className="view-grid">
      <Panel className="span-12 system-intro">
        <p className="eyebrow">INSPECTABLE BY DESIGN</p>
        <h2 className="display">How FinPilot turns a statement into verified advice.</h2>
        <p className="lede">Mesh handles semantics. Deterministic code owns money, policy and release decisions — and every handoff below is persisted.</p>
        <div className="legend-inline"><span><i style={{ background: "var(--accent)" }} />Deterministic</span><span><i style={{ background: "var(--purple)" }} />Mesh-powered</span></div>
      </Panel>

      <div className="span-12 arch-grid">
        {ARCHITECTURE.map((node, index) => (
          <article key={node.id} className={`glass arch-node ${node.model ? "model" : ""} ${node.nodes.some((name) => activeNode.includes(name)) ? "active" : ""}`}>
            <header><span className="arch-icon"><Icon name={node.icon} size={18} /></span><small>{String(index + 1).padStart(2, "0")}</small></header>
            <h3>{node.title}</h3>
            <p>{node.detail}</p>
            <Pill tone={node.model ? "info" : "neutral"} icon={node.model ? "cpu" : "lock"}>{node.runtime}</Pill>
          </article>
        ))}
      </div>

      <Panel className="span-12 trace-player">
        <PanelHeader eyebrow="TRACE PLAYER" title={agentRun ? `${visibleEvents}/${agentRun.events.length} persisted events` : "No trace recorded yet"} subtitle={agentRun ? `Execution ${agentRun.id.slice(0, 8)}` : "Ask the advisor in the live workspace to record a trace"} actions={
          <div className="button-row">
            <button className="icon-btn" onClick={() => setVisibleEvents((count) => Math.max(0, count - 1))} disabled={!agentRun || visibleEvents === 0} aria-label="Previous event"><Icon name="chevronLeft" size={15} /></button>
            <button className="btn btn-primary btn-sm" onClick={() => setVisibleEvents((count) => (agentRun ? Math.min(agentRun.events.length, count + 1) : 0))} disabled={!agentRun || visibleEvents >= agentRun.events.length}>Next event<Icon name="chevronRight" size={13} /></button>
            <button className="icon-btn" onClick={() => setVisibleEvents(0)} disabled={!agentRun} aria-label="Reset trace"><Icon name="refresh" size={15} /></button>
          </div>
        } />
        {agentRun && <div className="trace-progress"><i style={{ width: `${(visibleEvents / Math.max(agentRun.events.length, 1)) * 100}%` }} /></div>}
        {current && <div className="trace-detail"><Pill tone={current.model_id ? "info" : "neutral"} icon={current.model_id ? "cpu" : "lock"}>{current.model_id ? `Mesh · ${current.model_id}` : "Deterministic control"}</Pill><b>{current.node}</b><p>{current.summary}</p></div>}
      </Panel>

      <div className="span-12 stack-grid">
        {STACK.map(([name, title, detail]) => <article key={name} className="glass stack-card"><span className="eyebrow">{name}</span><b>{title}</b><small>{detail}</small></article>)}
      </div>

      <Panel className="span-12">
        <PanelHeader eyebrow="CONTROL SURFACE" title="What the implementation proves" />
        <div className="control-grid">{CONTROLS.map((item, index) => <div key={item} className="control-item"><span>{String(index + 1).padStart(2, "0")}</span><Icon name="check" size={14} /><b>{item}</b></div>)}</div>
      </Panel>
    </div>
  );
}
