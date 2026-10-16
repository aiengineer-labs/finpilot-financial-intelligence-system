import { compactMoney, money } from "@/lib/format";
import type { Insights } from "@/lib/insights";
import type { AgentRun, Forecast, Scenario, Snapshot } from "@/lib/types";
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
  busy: boolean;
  onRun: () => void;
  onOpenConsole: () => void;
  onOpenHow: () => void;
};

const WORKERS: Array<{ icon: IconName; title: string; label: string; detail: string; kind: "code" | "mesh" }> = [
  { icon: "sparkline", title: "Financial engines", label: "Deterministic", detail: "Calculate recurrence, robust anomalies and forecasts from the versioned ledger.", kind: "code" },
  { icon: "advice", title: "Advisor + critic", label: "Mesh API", detail: "Drafts grounded actions, challenges unsupported claims and permits one bounded revision.", kind: "mesh" },
  { icon: "governance", title: "Financial verifier", label: "Release gate", detail: "Recomputes every amount and withholds advice that cannot be proven from stored evidence.", kind: "code" }
];

export function LiveDemo({ insights, rowCount, completed, snapshot, forecast, scenario, run, busy, onRun, onOpenConsole, onOpenHow }: Props) {
  const latest = insights.balances.at(-1)?.balance ?? null;
  const status = run ? (run.verification_status === "accept" ? "Verified" : "Withheld") : forecast ? "Forecast ready" : "Ready to run";

  return (
    <div className="demo-experience">
      <Panel className="demo-hero">
        <div className="demo-hero-copy">
          <div className="live-label"><span />LIVE · SYNTHETIC DATA</div>
          <h2>Watch FinPilot turn a statement into a verified decision.</h2>
          <p>One run crosses deterministic financial engines, specialized Mesh agents, an adversarial critic and an independent release gate. Every step remains inspectable.</p>
          <div className="button-row">
            <button className="btn btn-primary btn-lg" onClick={onRun} disabled={busy || !rowCount}>
              <Icon name={busy ? "refresh" : "play"} size={16} className={busy ? "spin" : ""} />
              {busy ? "FinPilot is working…" : run ? "Run again" : "Run live workflow"}
            </button>
            <button className="btn btn-glass btn-lg" onClick={onOpenHow}><Icon name="system" size={16} />See how it works</button>
          </div>
        </div>
        <div className="demo-summary glass-thin">
          <div><small>Known balance</small><strong>{latest === null ? "—" : money(latest)}</strong><span>Source-provided · {insights.lastDay ?? "awaiting data"}</span></div>
          <div className="demo-summary-grid">
            <span><small>Ledger</small><b>{rowCount} rows</b></span>
            <span><small>Savings</small><b>{insights.rate}%</b></span>
            <span><small>30-day low</small><b>{forecast ? compactMoney(scenario?.minimum_balance_minor ?? forecast.minimum_balance_minor) : "Pending"}</b></span>
            <span><small>Verdict</small><b>{status}</b></span>
          </div>
        </div>
      </Panel>

      <section className="demo-stage glass" aria-label="Live workflow progress">
        <header><div><p className="eyebrow">ORCHESTRATION</p><h3>One trace. Six auditable stages.</h3></div><Pill tone={run?.verification_status === "accept" ? "good" : "info"} icon={run ? "audit" : "clock"}>{run ? `${run.events.length} persisted events` : "Awaiting run"}</Pill></header>
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
        <div><p className="eyebrow">CURRENT EVIDENCE</p><h3>{snapshot ? "The decision record is versioned" : "The ledger is ready for analysis"}</h3><p>{snapshot ? `${snapshot.source_transaction_count} rows · ${snapshot.recurring_patterns.length} recurring patterns · ${snapshot.anomaly_results.length} anomalies` : `${rowCount} validated rows are stored. No model performs financial arithmetic.`}</p></div>
        <div className="button-row"><button className="btn btn-glass" onClick={onOpenConsole}><Icon name="overview" size={15} />Open full console</button>{run && <Pill tone={run.verification_status === "accept" ? "good" : "bad"} icon="governance">{run.verification_status}</Pill>}</div>
      </Panel>
    </div>
  );
}
