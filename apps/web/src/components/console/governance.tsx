"use client";

import { dateTime, humanize, longDate } from "@/lib/format";
import type { DigestPreference, EvaluationRun, GovernanceData, GovernanceRisk, Notification } from "@/lib/types";
import { Icon } from "../ui/icons";
import { EmptyState, Panel, PanelHeader, Pill, StatTile, Switch, type Tone } from "../ui/primitives";

const LEVELS = ["low", "medium", "high", "critical"] as const;

function levelTone(level: string): Tone {
  return level === "critical" || level === "high" ? "bad" : level === "medium" ? "warn" : "good";
}

function statusTone(status: string): Tone {
  if (["approved", "passed", "pass", "accepted", "resolved", "delivered"].includes(status)) return "good";
  if (["failed", "fail", "rejected", "blocked"].includes(status)) return "bad";
  if (["pending", "proposed", "draft", "incomplete", "not_run"].includes(status)) return "warn";
  return "neutral";
}

function blockerLabel(blocker: string) {
  if (blocker === "evaluation:mesh-model-redteam:not_run") return "Model security check has not run";
  if (blocker === "evaluation:mesh-model-redteam:fail") return "Model security test did not pass";
  if (blocker.startsWith("evaluation:")) return `${humanize(blocker.split(":")[1] ?? "evaluation")} needs attention`;
  if (blocker.startsWith("risk:")) return `${blocker.split(":")[1] ?? "Risk"} requires review`;
  return humanize(blocker.replaceAll(":", " "));
}

function evaluationFailure(failure: string) {
  return failure === "External Mesh egress approval pending"
    ? "Run the model security suite to complete this check."
    : failure;
}

function runDuration(ms: number) {
  if (!ms) return "Not run yet";
  return ms >= 60_000 ? `${Math.round(ms / 60_000)} min` : ms >= 1_000 ? `${(ms / 1_000).toFixed(1)} s` : `${ms} ms`;
}

/** The measured outcome in words, from the run's own metrics. */
function evaluationOutcome(item: EvaluationRun) {
  const { cases, failed, errors, critical_failed: critical } = item.metrics;
  if (typeof cases !== "number" || typeof failed !== "number") return null;
  const parts = [`${cases} attacks`, `${failed} succeeded`];
  if (typeof critical === "number") parts.push(`${critical} critical`);
  if (typeof errors === "number" && errors) parts.push(`${errors} incomplete`);
  return parts.join(" · ");
}

/** The API keeps every record as history; the gate and this list use the newest per check. */
function latestPerCheck(evaluations: EvaluationRun[]) {
  const seen = new Set<string>();
  return evaluations.filter((item) => !seen.has(item.dataset_id) && Boolean(seen.add(item.dataset_id)));
}

type GovernanceProps = { data: GovernanceData | null; busy: boolean; createDemo: () => void; rejectReview: (id: string) => void };

function artifactConfiguration(configuration: Record<string, string | number | boolean | string[]>) {
  const preferred = ["model_id", "reasoning_effort", "response_format", "template_version", "policy_version"];
  return preferred.flatMap((key) => key in configuration ? [[key, configuration[key]] as const] : []).slice(0, 3);
}

export function GovernanceView({ data, busy, createDemo, rejectReview }: GovernanceProps) {
  if (!data) return <div className="view-grid"><Panel className="span-12"><EmptyState icon="governance" title="Loading governance evidence">Resolving approved assets, risk controls and review lineage.</EmptyState></Panel></div>;
  const pending = data.reviews.filter((item) => item.status === "pending");
  const resolved = data.reviews.filter((item) => item.status !== "pending");
  return (
    <div className="view-grid">
      <div className="span-12 stat-row">
        <StatTile icon="doc" label="Asset registry" value={data.summary.artifacts} detail="Versioned and hashed" />
        <StatTile icon="alert" label="Risk controls" value={data.summary.risks} detail={`${data.summary.drift_alerts.length} drift alerts`} />
        <StatTile icon="user" label="Pending human review" value={data.summary.pending_reviews} detail={`${data.summary.rejected_recommendations} rejected recommendations`} />
        <StatTile icon="governance" label="Release gate" value={data.summary.release_ready ? "Ready" : "Blocked"} tone={data.summary.release_ready ? "good" : "bad"} detail={`${data.summary.evaluation_failures} incomplete gates · ${data.summary.baseline_version}`} />
      </div>

      {data.summary.release_blockers.length > 0 && (
        <Panel className="span-12 callout-panel">
          <div className="callout info"><Icon name="lock" size={16} /><div><b>{data.summary.release_blockers.length} AI readiness check{data.summary.release_blockers.length === 1 ? "" : "s"} remaining</b><ul>{data.summary.release_blockers.map((item) => <li key={item}>{blockerLabel(item)}</li>)}</ul></div></div>
        </Panel>
      )}

      <Panel className="span-7">
        <PanelHeader eyebrow="AI READINESS" title="Quality checks" subtitle="Independent checks required before a model or prompt change is released" />
        {data.evaluations.length ? (
          <ul className="gate-list">
            {latestPerCheck(data.evaluations).map((item) => (
              <li key={item.id}>
                <span className={`gate-status ${item.status}`}><Icon name={item.status === "pass" ? "check" : item.status === "not_run" ? "clock" : "alert"} size={16} /></span>
                <div>
                  <header><b>{item.dataset_id === "mesh-model-redteam" ? "Model security test" : "Prompt-injection test"}</b><Pill tone={statusTone(item.status)}>{item.status === "not_run" ? "Action needed" : humanize(item.status)}</Pill></header>
                  <p>{item.dataset_id === "mesh-model-redteam" ? "Challenges the live AI model with adversarial financial prompts." : "Checks that statement text cannot override FinPilot's safety rules."}</p>
                  <div className="gate-meta"><span>{runDuration(item.duration_ms)}</span>{evaluationOutcome(item) && <span>{evaluationOutcome(item)}</span>}{item.model_id && <span>{item.model_id}</span>}<span>Code {item.code_version}</span></div>
                  {item.failures.map((failure) => <em key={failure}>{evaluationFailure(failure)}</em>)}
                </div>
              </li>
            ))}
          </ul>
        ) : <EmptyState icon="flask" title="No evaluation runs recorded" />}
      </Panel>

      <Panel className="span-5">
        <PanelHeader eyebrow="RISK POSTURE" title="Likelihood × impact" subtitle="Count of registered risks per cell" />
        <RiskMatrix risks={data.risks} />
      </Panel>

      <Panel className="span-12">
        <PanelHeader eyebrow="HUMAN OVERSIGHT" title="Review queue" subtitle="Reviewer decisions are recorded with exact artifact lineage" actions={<button className="btn btn-glass btn-sm" onClick={createDemo} disabled={busy}><Icon name="flask" size={13} />Create synthetic case</button>} />
        {pending.length || resolved.length ? (
          <div className="review-grid">
            {[...pending, ...resolved.slice(0, 4)].map((item) => (
              <article key={item.id} className={`review-card ${item.status}`}>
                <header><Pill tone={levelTone(item.risk_level)} withIcon>{item.risk_level}</Pill><Pill tone={statusTone(item.status)}>{humanize(item.status)}</Pill></header>
                <p>{item.reason}</p>
                <small className="muted">{humanize(item.source)} · {dateTime(item.created_at)} · {Object.keys(item.artifact_lineage).length} artifact versions retained</small>
                {item.status === "pending" && item.requested_by_user_id === null && <button className="btn btn-danger btn-sm" onClick={() => rejectReview(item.id)} disabled={busy}><Icon name="close" size={13} />Reject unsafe advice</button>}
              </article>
            ))}
          </div>
        ) : <EmptyState icon="user" title="No review cases">Create the synthetic case to trace an automatic rejection through an auditable reviewer decision.</EmptyState>}
      </Panel>

      <Panel className="span-12">
        <PanelHeader eyebrow="MODEL · PROMPT · POLICY REGISTRY" title="Approved and proposed versions" subtitle="Hashes only — secrets and full prompts are excluded" />
        <div className="artifact-grid">
          {data.artifacts.map((item) => (
            <article key={item.id} className="artifact-card">
              <header><span className="muted">{humanize(item.artifact_type)}</span><Pill tone={statusTone(item.status)}>{humanize(item.status)}</Pill></header>
              <b>{item.name}</b>
              <small>{item.version}</small>
              {artifactConfiguration(item.configuration).length > 0 && <dl className="artifact-config">
                {artifactConfiguration(item.configuration).map(([key, value]) => <div key={key}><dt>{humanize(key)}</dt><dd>{Array.isArray(value) ? value.join(", ") : String(value)}</dd></div>)}
              </dl>}
              <code title={item.content_sha256}>{item.content_sha256.slice(0, 16)}…</code>
              <small className="muted">{humanize(item.approval_source)}</small>
            </article>
          ))}
        </div>
      </Panel>

      <Panel className="span-12">
        <PanelHeader eyebrow="AI RISK REGISTER" title="Residual risk and accountable owner" />
        <div className="table-wrap"><table className="table">
          <thead><tr><th>ID</th><th>Risk</th><th>Likelihood</th><th>Impact</th><th>Residual</th><th className="hide-sm">Owner</th><th className="hide-sm">Review</th></tr></thead>
          <tbody>{data.risks.map((item) => (
            <tr key={item.id}>
              <td className="nowrap"><code>{item.risk_id}</code></td>
              <td><b>{humanize(item.category)}</b><small>{item.mitigation}</small></td>
              <td>{humanize(item.likelihood)}</td>
              <td>{humanize(item.impact)}</td>
              <td><Pill tone={levelTone(item.residual_risk)} withIcon>{item.residual_risk}</Pill></td>
              <td className="hide-sm">{humanize(item.owner_role)}</td>
              <td className="hide-sm nowrap">{longDate(item.review_on)}</td>
            </tr>
          ))}</tbody>
        </table></div>
      </Panel>
    </div>
  );
}

function RiskMatrix({ risks }: { risks: GovernanceRisk[] }) {
  const rows = [...LEVELS].reverse();
  const count = (likelihood: string, impact: string) => risks.filter((risk) => risk.likelihood === likelihood && risk.impact === impact).length;
  return (
    <div className="risk-matrix" role="table" aria-label="Risk count by likelihood and impact">
      <div className="risk-axis-y" aria-hidden="true">Likelihood</div>
      <div className="risk-grid">
        {rows.map((likelihood) => (
          <div key={likelihood} className="risk-row" role="row">
            <span className="risk-label" role="rowheader">{humanize(likelihood)}</span>
            {LEVELS.map((impact) => {
              const value = count(likelihood, impact);
              const severity = LEVELS.indexOf(likelihood) + LEVELS.indexOf(impact);
              return <span key={impact} role="cell" className={`risk-cell sev-${severity >= 5 ? "critical" : severity >= 4 ? "high" : severity >= 2 ? "medium" : "low"} ${value ? "filled" : ""}`} aria-label={`${likelihood} likelihood, ${impact} impact: ${value}`}>{value || ""}</span>;
            })}
          </div>
        ))}
        <div className="risk-row risk-foot" aria-hidden="true"><span />{LEVELS.map((impact) => <span key={impact}>{humanize(impact)}</span>)}</div>
      </div>
      <div className="risk-axis-x" aria-hidden="true">Impact</div>
    </div>
  );
}

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

type DigestProps = { preference: DigestPreference | null; notifications: Notification[]; busy: boolean; savePreference: (enabled: boolean) => void };

export function DigestView({ preference, notifications, busy, savePreference }: DigestProps) {
  return (
    <div className="view-grid">
      <Panel className="span-7 digest-schedule">
        <PanelHeader eyebrow="DURABLE PROACTIVE INSIGHTS" title="Weekly financial check-in" subtitle="Schedule state lives in PostgreSQL and is claimed once by a signed dispatcher" icon="digests" />
        <div className="setting-row">
          <div><b>Weekly digest</b><small>{preference?.enabled ? `${WEEKDAYS[preference.weekday] ?? "Monday"}s at ${preference.local_time} · ${preference.timezone}` : "Off — enable a Monday 09:00 Asia/Kolkata check-in"}</small></div>
          <Switch checked={Boolean(preference?.enabled)} onChange={savePreference} label="Weekly digest" disabled={busy} />
        </div>
        <div className="setting-row"><div><b>Delivery channel</b><small>Guaranteed in-app adapter; no email or Telegram configured</small></div><Pill tone="info" icon="inbox">In-app</Pill></div>
        <div className="setting-row"><div><b>Next eligibility</b><small>Daily cron trigger with weekly application-level eligibility</small></div><span className="setting-value">{preference?.next_due_at ? dateTime(preference.next_due_at) : "Not scheduled"}</span></div>
        <div className="setting-row"><div><b>Last dispatched</b><small>One delivery per schedule key</small></div><span className="setting-value">{preference?.last_dispatched_at ? dateTime(preference.last_dispatched_at) : "Never"}</span></div>
      </Panel>
      <Panel className="span-5">
        <PanelHeader eyebrow="DELIVERY AUDIT" title="In-app notifications" subtitle={`${notifications.length} delivered`} />
        {notifications.length ? (
          <ul className="notification-list">
            {notifications.map((item) => (
              <li key={item.id} className="notification">
                <span className="notification-icon"><Icon name="digests" size={15} /></span>
                <div><header><b>{item.subject}</b><small>{dateTime(item.delivered_at ?? item.created_at)}</small></header><p>{item.body}</p><small className="muted">Job {item.digest_job_id.slice(0, 8)} · {humanize(item.status)}</small></div>
              </li>
            ))}
          </ul>
        ) : <EmptyState icon="inbox" title="No digest delivered yet">The production cron evaluates due preferences once per day.</EmptyState>}
      </Panel>
    </div>
  );
}
