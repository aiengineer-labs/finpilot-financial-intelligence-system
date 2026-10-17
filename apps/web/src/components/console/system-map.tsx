"use client";

import { useMemo, useState } from "react";
import type { AgentRun, ArchitectureEdge, ArchitectureManifest, ArchitectureNode } from "@/lib/types";
import { Icon } from "../ui/icons";
import { Panel, PanelHeader, Pill } from "../ui/primitives";

type MapTab = "graph" | "agents" | "contracts" | "timeline";
type Props = {
  architecture: ArchitectureManifest | null;
  agentRun: AgentRun | null;
  visibleEvents: number;
  setVisibleEvents: (value: number | ((count: number) => number)) => void;
};

const KIND_LABEL: Record<ArchitectureNode["kind"], string> = {
  input: "Input / output",
  guardrail: "Guardrail",
  deterministic: "Deterministic tool",
  store: "Data store",
  mesh: "LLM agent · Mesh",
  verifier: "Independent verifier",
  output: "Terminal state"
};

function edgePath(edge: ArchitectureEdge, nodes: Map<string, ArchitectureNode>) {
  const source = nodes.get(edge.source);
  const target = nodes.get(edge.target);
  if (!source || !target) return "";
  const vertical = Math.abs(target.y - source.y) > Math.abs(target.x - source.x);
  if (vertical) {
    const middle = (source.y + target.y) / 2;
    return `M ${source.x} ${source.y} C ${source.x} ${middle}, ${target.x} ${middle}, ${target.x} ${target.y}`;
  }
  const middle = (source.x + target.x) / 2;
  return `M ${source.x} ${source.y} C ${middle} ${source.y}, ${middle} ${target.y}, ${target.x} ${target.y}`;
}

export function SystemMap({ architecture, agentRun, visibleEvents, setVisibleEvents }: Props) {
  const [tab, setTab] = useState<MapTab>("graph");
  const [selectedId, setSelectedId] = useState<string>("supervisor");
  const nodes = useMemo(() => new Map(architecture?.nodes.map((node) => [node.id, node]) ?? []), [architecture]);
  const current = agentRun && visibleEvents > 0 ? agentRun.events[visibleEvents - 1] : null;
  const seen = new Set(agentRun?.events.slice(0, visibleEvents).map((event) => event.node) ?? []);
  const selected = nodes.get(selectedId) ?? architecture?.nodes[0] ?? null;

  return (
    <div className="system-workspace">
      <section className="system-heading">
        <p className="eyebrow">GENERATED FROM THE DEPLOYED GRAPH MANIFEST</p>
        <h2>How FinPilot works</h2>
        <p>The real neuro-symbolic path: uploaded rows become deterministic evidence, Mesh agents interpret that evidence, and plain code decides whether advice can be released.</p>
        {architecture && <div className="system-versions"><Pill tone="info" icon="system">{architecture.graph_version}</Pill><Pill tone="neutral" icon="cpu">{architecture.mesh_model ?? "Mesh model not configured"}</Pill><Pill tone="neutral" icon="governance">{architecture.verifier_version}</Pill></div>}
      </section>

      <div className="system-tabs" role="tablist" aria-label="Architecture views">
        {(["graph", "agents", "contracts", "timeline"] as const).map((item) => <button key={item} role="tab" aria-selected={tab === item} className={tab === item ? "active" : ""} onClick={() => setTab(item)}>{item === "graph" ? "Live graph" : item === "agents" ? "Agents & roles" : item === "contracts" ? "State & contracts" : "Run timeline"}</button>)}
      </div>

      <Panel className="trace-player system-player">
        <PanelHeader eyebrow="TRACE PLAYER" title={agentRun ? `${visibleEvents}/${agentRun.events.length} persisted events` : "No agent run loaded"} subtitle={agentRun ? `Execution ${agentRun.id.slice(0, 8)} · ${agentRun.verification_status}` : "Upload a statement and run FinPilot to replay its actual decisions"} actions={
          <div className="button-row">
            <button className="icon-btn" onClick={() => setVisibleEvents(0)} disabled={!agentRun} aria-label="Reset trace"><Icon name="refresh" size={15} /></button>
            <button className="icon-btn" onClick={() => setVisibleEvents((count) => Math.max(0, count - 1))} disabled={!agentRun || visibleEvents === 0} aria-label="Previous event"><Icon name="chevronLeft" size={15} /></button>
            <button className="btn btn-primary btn-sm" onClick={() => setVisibleEvents((count) => (agentRun ? Math.min(agentRun.events.length, count + 1) : 0))} disabled={!agentRun || visibleEvents >= agentRun.events.length}><Icon name="play" size={12} />Next</button>
          </div>
        } />
        {agentRun && <div className="trace-progress"><i style={{ width: `${(visibleEvents / Math.max(agentRun.events.length, 1)) * 100}%` }} /></div>}
      </Panel>

      {!architecture ? <Panel><p className="muted">Loading the deployed architecture manifest…</p></Panel> : tab === "graph" ? (
        <div className="graph-layout">
          <Panel className="graph-canvas" aria-label="FinPilot neuro-symbolic agent graph">
            <svg viewBox="0 0 1160 740" role="img" aria-label="Statement ingestion, financial engines, Mesh agents, critic loop and deterministic verification">
              <defs>
                <marker id="arrow-normal" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" /></marker>
                <marker id="arrow-revise" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" /></marker>
              </defs>
              <g className="graph-edges">
                {architecture.edges.map((edge) => {
                  const source = nodes.get(edge.source);
                  const target = nodes.get(edge.target);
                  if (!source || !target) return null;
                  return <g key={`${edge.source}-${edge.target}`} className={`graph-edge branch-${edge.branch}`}><path d={edgePath(edge, nodes)} markerEnd={`url(#arrow-${edge.branch === "revise" ? "revise" : "normal"})`} /><text x={(source.x + target.x) / 2} y={(source.y + target.y) / 2 - 7}>{edge.label}</text></g>;
                })}
              </g>
              <g className="graph-nodes">
                {architecture.nodes.map((node, index) => {
                  const active = current?.node === node.id;
                  const done = seen.has(node.id);
                  return <g key={node.id} role="button" tabIndex={0} aria-label={`${node.label}: ${node.detail}`} className={`graph-node kind-${node.kind} ${active ? "active" : ""} ${done ? "done" : ""} ${selected?.id === node.id ? "selected" : ""}`} transform={`translate(${node.x - 80} ${node.y - 39})`} onClick={() => setSelectedId(node.id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") setSelectedId(node.id); }}>
                    <rect width="160" height="78" rx="15" />
                    <circle cx="22" cy="22" r="11" />
                    <text className="node-index" x="22" y="26" textAnchor="middle">{done ? "✓" : String(index + 1)}</text>
                    <text className="node-title" x="42" y="24">{node.label}</text>
                    <text className="node-runtime" x="16" y="51">{node.runtime}</text>
                  </g>;
                })}
              </g>
            </svg>
          </Panel>

          <aside className="graph-inspector glass">
            <h3>How to read this</h3>
            <p>Blue nodes are deterministic code, violet nodes call models only through Mesh, amber is the independent release gate, and dashed paths are model or audit handoffs.</p>
            <div className="graph-legend">
              {Object.entries(KIND_LABEL).map(([kind, label]) => <span key={kind} className={`kind-${kind}`}><i />{label}</span>)}
            </div>
            {selected && <div className="selected-node"><span className="eyebrow">SELECTED NODE</span><h3>{selected.label}</h3><p>{selected.detail}</p><Pill tone={selected.kind === "mesh" ? "info" : selected.kind === "verifier" ? "warn" : "neutral"}>{selected.runtime}</Pill></div>}
            {current && <div className="selected-node live"><span className="eyebrow">CURRENT TRACE EVENT</span><h3>{current.node}</h3><p>{current.summary}</p>{current.model_id && <Pill tone="info" icon="cpu">{current.model_id}</Pill>}</div>}
          </aside>
        </div>
      ) : tab === "agents" ? (
        <div className="agent-manifest-grid">
          {architecture.nodes.filter((node) => ["mesh", "verifier", "deterministic"].includes(node.kind)).map((node) => <article className={`glass agent-manifest kind-${node.kind}`} key={node.id}><span className="eyebrow">{KIND_LABEL[node.kind]}</span><h3>{node.label}</h3><p>{node.detail}</p><Pill tone={node.kind === "mesh" ? "info" : node.kind === "verifier" ? "warn" : "neutral"}>{node.runtime}</Pill></article>)}
        </div>
      ) : tab === "contracts" ? (
        <div className="contracts-grid">
          <Panel><PanelHeader eyebrow="VERSION CONTRACT" title="Exact runtime lineage" /><dl className="kv"><div><dt>Graph</dt><dd>{architecture.graph_version}</dd></div><div><dt>Prompts</dt><dd>{architecture.prompt_version}</dd></div><div><dt>Verifier</dt><dd>{architecture.verifier_version}</dd></div><div><dt>Model gateway</dt><dd>{architecture.mesh_model ?? "Not configured"}</dd></div></dl></Panel>
          <Panel><PanelHeader eyebrow="ADVICE STATE" title="Bounded, typed handoffs" /><ul className="contract-list"><li>Question and route intent</li><li>Versioned forecast/scenario evidence</li><li>Analyst explanation</li><li>Structured recommendation draft</li><li>Critique and verifier reasons</li><li>Revision count and terminal verdict</li></ul></Panel>
          <Panel><PanelHeader eyebrow="NON-NEGOTIABLE" title="Deterministic authority" /><ul className="contract-list"><li>Models never calculate authoritative money</li><li>Unknown evidence IDs fail closed</li><li>Currency and amount claims are allowlisted</li><li>Only one correction loop is permitted</li><li>Every transition is persisted</li></ul></Panel>
        </div>
      ) : (
        <Panel className="timeline-panel">
          <PanelHeader eyebrow="PERSISTED RUN" title={agentRun ? `${agentRun.events.length} recorded transitions` : "No timeline yet"} subtitle={agentRun ? `${agentRun.total_input_tokens + agentRun.total_output_tokens} tokens · ${agentRun.total_latency_ms} ms · ${agentRun.revision_attempts} revisions` : "The timeline appears only after a real uploaded statement is processed."} />
          {agentRun ? <ol className="system-timeline">{agentRun.events.map((event, index) => <li key={event.id} className={index < visibleEvents ? "visible" : ""}><span>{event.sequence}</span><div><b>{event.node}</b><p>{event.summary}</p></div><aside>{event.model_id ? <Pill tone="info" icon="cpu">Mesh</Pill> : <Pill tone="neutral" icon="lock">Code</Pill>}<small>{event.latency_ms === null ? "—" : `${event.latency_ms} ms`}</small></aside></li>)}</ol> : <p className="muted">Upload a statement in Live Demo, process it, then return here to replay the run.</p>}
        </Panel>
      )}
    </div>
  );
}
