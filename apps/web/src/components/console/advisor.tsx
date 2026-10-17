"use client";

import { useState } from "react";
import { eventUsage, summarizeAgentUsage, usd } from "@/lib/agent-usage";
import { humanize, money, percentFromBps } from "@/lib/format";
import type { AgentEvent, AgentRun } from "@/lib/types";
import { Icon, type IconName } from "../ui/icons";
import { EmptyState, Panel, PanelHeader, Pill, Ring, Segmented, StatTile } from "../ui/primitives";

const SUGGESTIONS = [
  "Where can I reduce my credit-card spending?",
  "How can I reduce my spending and save more money each month?",
  "Which recurring costs could I reduce next month?",
  "Can I afford this purchase without jeopardizing my cash buffer?"
];

const AGENTS: Array<{ id: string; label: string; icon: IconName; match: (node: string) => boolean }> = [
  { id: "analyst", label: "Behavior analyst", icon: "sparkline", match: (node) => node.includes("analyst") },
  { id: "advisor", label: "Financial advisor", icon: "advice", match: (node) => node.includes("advisor") || node.includes("revision") },
  { id: "critic", label: "Critic", icon: "search", match: (node) => node.includes("critic") },
  { id: "verifier", label: "Verifier", icon: "governance", match: (node) => node.includes("verif") }
];

type Props = {
  run: AgentRun | null;
  /** A versioned snapshot or forecast exists to ground the advice. */
  ready: boolean;
  question: string;
  setQuestion: (value: string) => void;
  visibleEvents: number;
  error: string;
  busy: boolean;
  onAsk: () => void;
};

export function AdvisorView({ run, ready, question, setQuestion, visibleEvents, error, busy, onAsk }: Props) {
  const seen = run ? run.events.slice(0, visibleEvents) : [];
  return (
    <div className="view-grid">
      <Panel className="span-12 question-panel">
        <PanelHeader eyebrow="FINANCIAL COPILOT" title="Ask against verified evidence" subtitle="The question is untrusted input. Specialists run through Mesh; money is checked by plain code." icon="advice" />
        <textarea className="question-input" value={question} onChange={(event) => setQuestion(event.target.value)} rows={3} maxLength={1000} aria-label="Question for the advisor" />
        <div className="question-footer">
          <div className="chip-row">{SUGGESTIONS.map((item) => <button key={item} type="button" className={`chip ${question === item ? "active" : ""}`} onClick={() => setQuestion(item)}>{item}</button>)}</div>
          <div className="button-row">
            <small className="muted">{ready ? `${question.length}/1000` : "Run the analysis first — the advisor needs versioned evidence"}</small>
            <button className="btn btn-primary" onClick={onAsk} disabled={busy || !ready || question.trim().length < 3}><Icon name="advice" size={14} />{busy ? "Agents working…" : "Ask advisor"}</button>
          </div>
        </div>
      </Panel>

      <Panel className="span-12 agent-flow-panel">
        <div className="agent-flow">
          {AGENTS.map((agent, index) => {
            const done = seen.some((event) => agent.match(event.node));
            const current = seen.length > 0 && agent.match(seen[seen.length - 1].node) && visibleEvents < (run?.events.length ?? 0);
            return (
              <div key={agent.id} className={`agent-node ${done ? "done" : ""} ${current ? "current" : ""}`}>
                <span><Icon name={done ? "check" : agent.icon} size={16} /></span>
                <b>{agent.label}</b>
                {index < AGENTS.length - 1 && <i aria-hidden="true" />}
              </div>
            );
          })}
        </div>
      </Panel>

      {error && <Panel className="span-12 callout-panel"><div className="callout bad"><Icon name="alert" size={16} /><div><b>Advisor unavailable</b><p>{error}</p></div></div></Panel>}

      {!run ? (
        <Panel className="span-12"><EmptyState icon="advice" title="No recommendation run yet">The advisor activates after the analysis versions a snapshot: spending evidence for card statements, plus a forecast for bank statements. Nothing on this page is pre-written.</EmptyState></Panel>
      ) : (
        <>
          <Panel className={`span-12 verdict ${run.verification_status === "accept" ? "pass" : "fail"}`}>
            <span className="verdict-icon"><Icon name={run.verification_status === "accept" ? "governance" : "alert"} size={22} /></span>
            <div>
              <p className="eyebrow">{run.verification_status === "accept" ? "VERIFIED BY DETERMINISTIC GATE" : "WITHHELD BY DETERMINISTIC GATE"}</p>
              <h2>{run.verification_status === "accept" ? "Recommendations released" : "Advice was not released"}</h2>
              <small>{humanize(run.status)} · {run.model_id} · {run.revision_attempts} revision {run.revision_attempts === 1 ? "attempt" : "attempts"} · {visibleEvents}/{run.events.length} events replayed</small>
            </div>
          </Panel>
          {run.final_response && <Panel className="span-12"><PanelHeader eyebrow="ADVISOR SUMMARY" title="Response" /><p className="prose">{run.final_response}</p></Panel>}
          <div className="span-12 rec-grid">
            {run.recommendations.map((item) => (
              <article key={item.id} className="glass rec-card">
                <header><Pill tone="info">Option {item.rank}</Pill><Pill tone={item.verification_status === "accept" ? "good" : "bad"} withIcon>{humanize(item.verification_status)}</Pill></header>
                <div className="rec-title"><h3>{item.title}</h3><Ring value={Math.round(item.confidence_bps / 100)} size={52} stroke={5} label={<small>{percentFromBps(item.confidence_bps)}</small>} /></div>
                <p>{item.explanation}</p>
                {item.amount_minor !== null && <strong className="rec-amount">{money(item.amount_minor, item.currency)}</strong>}
                <div className="evidence-strip">{item.evidence_ids.map((id) => <code key={id}>{id}</code>)}</div>
                <details><summary>Assumptions</summary><ul>{(item.assumptions.length ? item.assumptions : ["No additional assumptions"]).map((assumption) => <li key={assumption}>{assumption}</li>)}</ul></details>
              </article>
            ))}
            {!run.recommendations.length && <Panel className="span-12"><EmptyState icon="lock" title="No released recommendations">The verifier rejected every draft; see the audit trail for the reasons.</EmptyState></Panel>}
          </div>
        </>
      )}
    </div>
  );
}

export function AuditView({ run }: { run: AgentRun | null }) {
  const [filter, setFilter] = useState<"all" | "model" | "deterministic">("all");
  if (!run) return <div className="view-grid"><Panel className="span-12"><EmptyState icon="audit" title="No audit timeline yet">Every completed and rejected node of the next run will be persisted here.</EmptyState></Panel></div>;
  const modelEvents = run.events.filter((event) => event.model_id);
  const usage = summarizeAgentUsage(modelEvents);
  const events = run.events.filter((event) => filter === "all" || (filter === "model" ? event.model_id : !event.model_id));
  return (
    <div className="view-grid">
      <div className="span-12 stat-row">
        <StatTile icon="cpu" label="Mesh model calls" value={modelEvents.length} detail={`${run.events.length} total persisted events`} />
        <StatTile icon="bolt" label="Tokens" value={(run.total_input_tokens + run.total_output_tokens).toLocaleString("en-IN")} detail={`${run.total_input_tokens.toLocaleString("en-IN")} in · ${run.total_output_tokens.toLocaleString("en-IN")} out`} />
        <StatTile icon="doc" label="Mesh billed cost" value={usd(usage.costUsd)} detail={`${usage.cachedInputTokens.toLocaleString("en-IN")} cached input · ${usage.reasoningTokens.toLocaleString("en-IN")} reasoning`} />
        <StatTile icon="clock" label="Latency" value={`${(run.total_latency_ms / 1000).toFixed(1)} s`} detail={`${run.revision_attempts} revision attempts`} />
      </div>
      <Panel className="span-12">
        <PanelHeader eyebrow="IMMUTABLE DECISION TRAIL" title="Execution timeline" subtitle={`Verification: ${humanize(run.verification_status)}`} actions={<Segmented size="sm" label="Filter events" value={filter} onChange={setFilter} options={[{ value: "all", label: "All" }, { value: "model", label: "Model" }, { value: "deterministic", label: "Deterministic" }]} />} />
        <ol className="timeline">{events.map((event) => <TimelineItem key={event.id} event={event} />)}</ol>
      </Panel>
    </div>
  );
}

function TimelineItem({ event }: { event: AgentEvent }) {
  const detailKeys = Object.keys(event.details ?? {});
  const usage = eventUsage(event);
  return (
    <li className={event.model_id ? "model" : "deterministic"}>
      <span className="timeline-dot">{event.sequence}</span>
      <div className="timeline-body">
        <div className="timeline-head"><b>{humanize(event.node)}</b><Pill tone={event.event_type.includes("reject") || event.event_type.includes("block") ? "bad" : "neutral"}>{humanize(event.event_type)}</Pill></div>
        <p>{event.summary}</p>
        {event.model_id ? <div className="usage-strip">
          {usage.costUsd && <span>Mesh cost {usd(usage.costUsd)}</span>}
          {usage.cachedInputTokens > 0 && <span>{usage.cachedInputTokens.toLocaleString("en-IN")} cached input</span>}
          {usage.reasoningTokens > 0 && <span>{usage.reasoningTokens.toLocaleString("en-IN")} reasoning</span>}
        </div> : detailKeys.length > 0 && <small className="muted">Details recorded: {detailKeys.slice(0, 5).join(", ")}{detailKeys.length > 5 ? "…" : ""}</small>}
      </div>
      <aside>{event.model_id ? <><b><Icon name="cpu" size={12} /> {event.model_id}</b><small>{event.input_tokens ?? 0} in · {event.output_tokens ?? 0} out</small><small>{event.latency_ms ?? 0} ms</small></> : <><b><Icon name="lock" size={12} /> Deterministic</b><small>No model call</small></>}</aside>
    </li>
  );
}
