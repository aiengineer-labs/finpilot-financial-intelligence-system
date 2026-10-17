"use client";

import { type DragEvent, useRef, useState } from "react";
import { SAMPLE_STATEMENT } from "@/lib/client";
import { compactMoney, money } from "@/lib/format";
import type { Insights } from "@/lib/insights";
import type { AgentRun, Forecast, Scenario, Snapshot, UploadResult } from "@/lib/types";
import { Icon, type IconName } from "../ui/icons";
import { Panel, Pill } from "../ui/primitives";
import { STAGES, type StageId } from "./shared";

type Props = {
  insights: Insights;
  rowCount: number;
  completed: Set<StageId>;
  snapshot: Snapshot | null;
  forecast: Forecast | null;
  scenario: Scenario | null;
  run: AgentRun | null;
  uploadResult: UploadResult | null;
  spendingOnly: boolean;
  busy: boolean;
  onUpload: (file: File) => void;
  onLoadSample: () => void;
  onRun: () => void;
  onOpenConsole: () => void;
  onOpenHow: () => void;
};

const WORKERS: Array<{ icon: IconName; title: string; label: string; detail: string; kind: "code" | "mesh" }> = [
  { icon: "sparkline", title: "Financial engines", label: "Deterministic", detail: "Calculate recurrence, robust anomalies and forecasts from the uploaded ledger.", kind: "code" },
  { icon: "advice", title: "Advisor + critic", label: "Mesh API", detail: "Draft grounded actions, challenge unsupported claims and permit one bounded revision.", kind: "mesh" },
  { icon: "governance", title: "Financial verifier", label: "Release gate", detail: "Recompute every amount and withhold advice that cannot be proven from stored evidence.", kind: "code" }
];

export function LiveDemo({ insights, rowCount, completed, snapshot, forecast, scenario, run, uploadResult, spendingOnly, busy, onUpload, onLoadSample, onRun, onOpenConsole, onOpenHow }: Props) {
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const latest = insights.balances.at(-1)?.balance ?? null;
  const status = run ? (run.verification_status === "accept" ? "Verified" : "Withheld") : forecast ? "Forecast ready" : snapshot?.analysis_mode === "spending" ? "Spending analysed" : rowCount ? "Ready to run" : "Awaiting statement";

  function drop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files[0];
    if (file && !busy) onUpload(file);
  }

  return (
    <div className="demo-experience">
      <Panel className={`demo-hero ${rowCount ? "has-data" : "awaiting-data"}`}>
        <div className="demo-hero-copy">
          <div className="live-label"><span />LIVE · {rowCount ? "UPLOADED STATEMENT" : "EMPTY WORKSPACE"}</div>
          <h2>{rowCount ? "Your statement is ready for a verified decision." : "Upload a bank or credit-card statement. FinPilot will show every decision."}</h2>
          <p>{rowCount ? "The values below come from persisted rows in this workspace. Run the workflow to cross deterministic engines, Mesh specialists, an adversarial critic and an independent release gate." : "Nothing is preloaded and no result is hardcoded. Your selected file passes through validation, categorization, financial engines and the inspectable agent workflow."}</p>

          {!rowCount ? (
            <div className={`demo-upload ${dragging ? "dragging" : ""}`} onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={drop}>
              <span className="demo-upload-icon"><Icon name="upload" size={24} /></span>
              <div><b>Drop a bank or card statement</b><small>CSV or text-based PDF · up to 5 MiB · no bank credentials</small></div>
              <button className="btn btn-primary" onClick={() => input.current?.click()} disabled={busy}><Icon name={busy ? "refresh" : "doc"} size={14} className={busy ? "spin" : ""} />{busy ? "Checking…" : "Choose statement"}</button>
              <input ref={input} type="file" accept=".csv,.pdf,text/csv,application/pdf" hidden onChange={(event) => { const file = event.target.files?.[0]; if (file) onUpload(file); event.target.value = ""; }} />
            </div>
          ) : (
            <div className="button-row">
              <button className="btn btn-primary btn-lg" onClick={onRun} disabled={busy}>
                <Icon name={busy ? "refresh" : "play"} size={16} className={busy ? "spin" : ""} />
                {busy ? "FinPilot is working…" : run ? "Run again" : spendingOnly ? "Analyse spending" : "Process uploaded statement"}
              </button>
              <button className="btn btn-glass btn-lg" onClick={() => input.current?.click()} disabled={busy}><Icon name="upload" size={16} />Upload another statement</button>
              <input ref={input} type="file" accept=".csv,.pdf,text/csv,application/pdf" hidden onChange={(event) => { const file = event.target.files?.[0]; if (file) onUpload(file); event.target.value = ""; }} />
            </div>
          )}

          <div className="demo-file-actions">
            {!rowCount && <button className="text-link as-button" onClick={onLoadSample} disabled={busy}><Icon name="flask" size={14} />Use the fictional demo CSV</button>}
            <a className="text-link" href={SAMPLE_STATEMENT.path} download><Icon name="download" size={14} />Download the upload-ready demo CSV</a>
            <button className="text-link as-button" onClick={onOpenHow}><Icon name="system" size={14} />Inspect the architecture</button>
          </div>
        </div>

        <div className="demo-summary glass-thin" aria-live="polite">
          <div><small>Known balance</small><strong>{latest === null ? "—" : money(latest)}</strong><span>{latest === null ? (spendingOnly ? "Card or balance-free statement" : "No source balance loaded") : `Source-provided · ${insights.lastDay}`}</span></div>
          <div className="demo-summary-grid">
            <span><small>Ledger</small><b>{rowCount ? `${rowCount} rows` : "Empty"}</b></span>
            <span><small>Savings</small><b>{rowCount ? `${insights.rate}%` : "—"}</b></span>
            <span><small>30-day low</small><b>{forecast ? compactMoney(scenario?.minimum_balance_minor ?? forecast.minimum_balance_minor) : spendingOnly ? "Needs balance" : "Pending"}</b></span>
            <span><small>Verdict</small><b>{status}</b></span>
          </div>
          {uploadResult && <div className="demo-import-result"><Icon name="check" size={14} /><span><b>{uploadResult.filename}</b><small>{uploadResult.source_format.toUpperCase()} verified · {uploadResult.accepted_rows} accepted · {uploadResult.duplicate_rows} duplicate · {uploadResult.rejected_rows} rejected</small></span></div>}
        </div>
      </Panel>

      <section className="demo-stage glass" aria-label="Live workflow progress">
        <header><div><p className="eyebrow">ORCHESTRATION</p><h3>One trace. Six auditable stages.</h3></div><Pill tone={run?.verification_status === "accept" ? "good" : "info"} icon={run ? "audit" : "clock"}>{run ? `${run.events.length} persisted events` : rowCount ? "Ready to process" : "Awaiting statement"}</Pill></header>
        <ol>
          {STAGES.map(([id, label], index) => {
            const done = completed.has(id);
            const active = busy && !done && STAGES.slice(0, index).every(([prior]) => completed.has(prior));
            return <li key={id} className={done ? "done" : active ? "active" : ""}><span>{done ? <Icon name="check" size={12} /> : index + 1}</span><b>{label}</b><small>{id === "categorize" || id === "advise" ? "Mesh bounded" : "Deterministic"}</small></li>;
          })}
        </ol>
      </section>

      <div className="demo-workers">
        {WORKERS.map((worker, index) => (
          <article className={`glass demo-worker ${worker.kind}`} key={worker.title}>
            <header><span><Icon name={worker.icon} size={19} /></span><em>0{index + 1}</em></header>
            <Pill tone={worker.kind === "mesh" ? "info" : "neutral"} icon={worker.kind === "mesh" ? "cpu" : "lock"}>{worker.label}</Pill>
            <h3>{worker.title}</h3>
            <p>{worker.detail}</p>
          </article>
        ))}
      </div>

      <Panel className="demo-evidence">
        <div><p className="eyebrow">CURRENT EVIDENCE</p><h3>{snapshot ? "The decision record is versioned" : rowCount ? "The ledger is ready for analysis" : "No financial evidence loaded"}</h3><p>{snapshot ? `${snapshot.source_transaction_count} rows · ${snapshot.recurring_patterns.length} recurring patterns · ${snapshot.anomaly_results.length} anomalies` : rowCount ? `${rowCount} validated rows are stored. No model performs financial arithmetic.` : "Upload a CSV or PDF, or explicitly load the fictional demo file to begin."}</p></div>
        <div className="button-row"><button className="btn btn-glass" onClick={onOpenConsole}><Icon name="overview" size={15} />Open full console</button>{run && <Pill tone={run.verification_status === "accept" ? "good" : "bad"} icon="governance">{run.verification_status}</Pill>}</div>
      </Panel>
    </div>
  );
}
