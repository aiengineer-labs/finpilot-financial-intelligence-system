import type { AgentRun } from "@/lib/types";
import { humanize } from "@/lib/format";
import { Icon } from "../ui/icons";

export function Inspector({ run, visibleEvents, running, onClose }: { run: AgentRun | null; visibleEvents: number; running: boolean; onClose: () => void }) {
  return (
    <aside className="glass inspector" aria-label="Agent log">
      <header className="inspector-head">
        <span className="panel-icon"><Icon name="terminal" size={15} /></span>
        <div><b>Agent log</b><small>{running ? "Running secure pipeline…" : run ? "Persisted execution" : "Idle"}</small></div>
        <span className={`live-dot ${running ? "on" : run ? "done" : ""}`} aria-hidden="true" />
        <button className="icon-btn ghost inspector-close" onClick={onClose} aria-label="Close agent log"><Icon name="close" size={14} /></button>
      </header>
      <div className="inspector-body">
        {!run ? (
          <p className="console-idle">{"// waiting for a verified run"}<br />{"// run the analysis, then ask the advisor"}</p>
        ) : run.events.slice(0, visibleEvents).map((event) => (
          <article key={event.id} className="log-entry">
            <time>[{String(event.sequence).padStart(2, "0")}]</time>
            <div>
              <b>{humanize(event.node)}</b>
              <p>{event.summary}</p>
              <small>{event.model_id ? `Mesh · ${event.model_id} · ${event.output_tokens ?? 0} tok · ${event.latency_ms ?? 0} ms` : "deterministic · no model call"}</small>
            </div>
          </article>
        ))}
      </div>
      {run && <footer className="inspector-foot"><span>{(run.total_input_tokens + run.total_output_tokens).toLocaleString("en-IN")} tokens</span><span>{(run.total_latency_ms / 1000).toFixed(1)} s</span><span>{humanize(run.verification_status)}</span></footer>}
    </aside>
  );
}
