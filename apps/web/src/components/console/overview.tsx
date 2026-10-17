import { compactMoney, dayDiff, humanize, longDate, money, monthLabel, percentFromBps, shortDate, signedMoney, titleCase } from "@/lib/format";
import type { Insights } from "@/lib/insights";
import type { Snapshot, Transaction, View } from "@/lib/types";
import { CalendarHeatmap, ColumnChart, Donut, LineChart } from "../ui/charts";
import { Icon } from "../ui/icons";
import { Avatar, EmptyState, Meter, Panel, PanelHeader, Pill, Ring, StatTile, hueFor } from "../ui/primitives";
import { SAMPLE_STATEMENT } from "@/lib/client";
import { categorySlices } from "./shared";

type Props = {
  insights: Insights;
  transactions: Transaction[];
  snapshot: Snapshot | null;
  hasAccount: boolean;
  busy: boolean;
  onNavigate: (view: View) => void;
  onLoadSample: () => void;
  onRunAnalysis: () => void;
};

export function Overview({ insights, transactions, snapshot, hasAccount, busy, onNavigate, onLoadSample, onRunAnalysis }: Props) {
  if (!transactions.length) return <Onboarding hasAccount={hasAccount} busy={busy} onLoadSample={onLoadSample} onNavigate={onNavigate} />;

  const latest = insights.balances[insights.balances.length - 1];
  const first = insights.balances[0];
  const slices = categorySlices(insights.categories);
  const byId = new Map(transactions.map((item) => [item.id, item]));
  const busiest = [...insights.dailySpend.entries()].sort((a, b) => b[1] - a[1])[0];
  const spanDays = insights.firstDay && insights.lastDay ? dayDiff(insights.firstDay, insights.lastDay) + 1 : 0;

  return (
    <div className="view-grid">
      <Panel className="span-8 hero-balance">
        <PanelHeader eyebrow="LATEST KNOWN BALANCE" title={latest ? <span className="hero-figure">{money(latest.balance)}</span> : "No source balance"} subtitle={latest ? `Source-provided running balance on ${longDate(latest.day)}` : "This statement carries no balance column; FinPilot never infers one."} actions={first && latest && first.day !== latest.day ? <Pill tone={latest.balance >= first.balance ? "good" : "bad"} icon={latest.balance >= first.balance ? "arrowUpRight" : "arrowDownRight"}>{signedMoney(latest.balance - first.balance)} since {shortDate(first.day)}</Pill> : undefined} />
        {insights.balances.length > 1 && <LineChart height={210} ariaLabel="Daily closing balance from the imported statement" days={insights.balances.map((point) => point.day)} series={[{ id: "balance", label: "Closing balance", values: insights.balances.map((point) => point.balance), color: "var(--viz-1)", area: true }]} />}
      </Panel>

      <Panel className="span-4 savings-card">
        <PanelHeader eyebrow="RETENTION" title="Savings rate" subtitle={insights.firstDay && insights.lastDay ? `${shortDate(insights.firstDay)} – ${shortDate(insights.lastDay)}` : undefined} />
        <div className="savings-body">
          <Ring value={insights.rate} size={124} stroke={12} tone={insights.rate >= 20 ? "good" : insights.rate >= 5 ? "warn" : "bad"} label={<><strong>{insights.rate}%</strong><small>retained</small></>} />
          <dl className="kv">
            <div><dt>Cash in</dt><dd>{money(insights.income)}</dd></div>
            <div><dt>Cash out</dt><dd>{money(insights.spend)}</dd></div>
            <div><dt>Net</dt><dd className={insights.net >= 0 ? "positive" : "negative"}>{signedMoney(insights.net)}</dd></div>
          </dl>
        </div>
      </Panel>

      <div className="span-12 stat-row">
        <StatTile icon="arrowDownRight" label="Cash in" value={compactMoney(insights.income)} detail="Income, refunds and transfers separated" trend={insights.months.map((month) => month.income)} />
        <StatTile icon="arrowUpRight" label="Cash out" value={compactMoney(insights.spend)} detail={`${insights.months.length} months of spending`} trend={insights.months.map((month) => month.spend)} />
        <StatTile icon="repeat" label="Transfers excluded" value={insights.excluded} detail="Self-transfers and card repayments" />
        <StatTile icon="advice" label="Needs semantic review" value={insights.needsReview} detail="Ambiguous rows routed to Mesh, not guessed" tone={insights.needsReview ? undefined : "good"} />
      </div>

      <Panel className="span-7">
        <PanelHeader eyebrow="CASH FLOW" title="Monthly in and out" subtitle="Transfer-adjusted, from exact minor units" actions={<div className="legend-inline"><span><i style={{ background: "var(--viz-income)" }} />Cash in</span><span><i style={{ background: "var(--viz-spend)" }} />Cash out</span></div>} />
        <ColumnChart ariaLabel="Monthly cash in and cash out" groups={insights.months.map((month) => ({ key: month.key, label: monthLabel(month.key), values: [month.income, month.spend] }))} series={[{ label: "Cash in", color: "var(--viz-income)" }, { label: "Cash out", color: "var(--viz-spend)" }]} />
        <details className="data-table">
          <summary>View as table</summary>
          <table><thead><tr><th>Month</th><th>Cash in</th><th>Cash out</th><th>Net</th></tr></thead>
            <tbody>{insights.months.map((month) => <tr key={month.key}><td>{monthLabel(month.key)}</td><td>{money(month.income)}</td><td>{money(month.spend)}</td><td>{signedMoney(month.income - month.spend)}</td></tr>)}</tbody></table>
        </details>
      </Panel>

      <Panel className="span-5">
        <PanelHeader eyebrow="SPEND MIX" title="Where money went" subtitle="Hover a slice or row for detail" />
        {slices.length ? <Donut slices={slices} centerLabel="Total spend" /> : <EmptyState icon="overview" title="No spending yet" />}
      </Panel>

      <Panel className="span-7">
        <PanelHeader eyebrow="RHYTHM" title="Daily spending calendar" subtitle="Quartiles of non-zero spending days" />
        {insights.firstDay && insights.lastDay && <CalendarHeatmap start={insights.firstDay} end={insights.lastDay} values={insights.dailySpend} />}
        {busiest && (
          <div className="mini-stats">
            <div><span>Busiest day</span><b>{money(busiest[1])}</b><small>{shortDate(busiest[0])}</small></div>
            <div><span>Average spending day</span><b>{money(Math.round(insights.spend / Math.max(insights.dailySpend.size, 1)))}</b><small>{insights.dailySpend.size} days with spending</small></div>
            <div><span>No-spend days</span><b>{spanDays - insights.dailySpend.size}</b><small>of {spanDays} calendar days</small></div>
          </div>
        )}
      </Panel>

      <Panel className="span-5">
        <PanelHeader eyebrow="MERCHANTS" title="Top merchants by spend" />
        <ul className="merchant-list">
          {insights.merchants.map((merchant) => (
            <li key={merchant.name}>
              <Avatar label={merchant.name} hue={hueFor(merchant.name)} />
              <div><b>{titleCase(merchant.name)}</b><small>{merchant.count} payments · {humanize(merchant.category)}</small><span className="bar-track"><i style={{ width: `${(merchant.value / (insights.merchants[0]?.value || 1)) * 100}%` }} /></span></div>
              <strong>{money(merchant.value)}</strong>
            </li>
          ))}
        </ul>
      </Panel>

      <Panel className="span-7">
        <PanelHeader eyebrow="RECURRENCE ENGINE" title="Recurring commitments" subtitle={snapshot ? `Snapshot ${snapshot.id.slice(0, 8)} · as of ${longDate(snapshot.as_of)}` : "Detected deterministically from repeated merchant and date evidence"} actions={!snapshot ? <button className="btn btn-glass btn-sm" onClick={onRunAnalysis} disabled={busy}><Icon name="play" size={13} />Run analysis</button> : undefined} />
        {snapshot ? (
          snapshot.recurring_patterns.length ? (
            <div className="recurring-grid">
              {snapshot.recurring_patterns.map((pattern) => (
                <article key={pattern.id} className="recurring-item">
                  <Avatar label={pattern.merchant} hue={hueFor(pattern.merchant)} />
                  <div><b>{titleCase(pattern.merchant)}</b><small>{humanize(pattern.cadence)} · {percentFromBps(pattern.confidence_bps)} confidence</small><Meter value={pattern.confidence_bps / 100} /></div>
                  <strong className={pattern.typical_amount_minor >= 0 ? "positive" : ""}>{signedMoney(pattern.typical_amount_minor)}</strong>
                </article>
              ))}
            </div>
          ) : <EmptyState icon="repeat" title="No recurrence with enough evidence">Three or more observations on a regular cadence are required.</EmptyState>
        ) : <EmptyState icon="repeat" title="Not analysed yet">Run the deterministic analysis to version a snapshot and detect recurring income and bills.</EmptyState>}
      </Panel>

      <Panel className="span-5">
        <PanelHeader eyebrow="ROBUST ANOMALIES" title="Signals worth reviewing" subtitle="Median absolute deviation per category" />
        {snapshot ? (
          snapshot.anomaly_results.length ? (
            <ul className="signal-list">
              {snapshot.anomaly_results.map((anomaly) => {
                const row = byId.get(anomaly.transaction_id);
                return (
                  <li key={anomaly.transaction_id}>
                    <span className={`signal-icon sev-${anomaly.severity}`}><Icon name="alert" size={15} /></span>
                    <div><b>{row ? titleCase(row.merchant_normalized) : anomaly.transaction_id.slice(0, 8)}</b><small>{row ? `${shortDate(row.transaction_date)} · ${row.description}` : "Source row"}</small><small className="muted">{anomaly.explanation}</small></div>
                    <div className="signal-meta">{row && <strong>{money(Math.abs(row.amount_minor))}</strong>}<Pill tone={anomaly.severity === "high" ? "bad" : "warn"} withIcon>{anomaly.severity}</Pill></div>
                  </li>
                );
              })}
            </ul>
          ) : <EmptyState icon="check" title="No robust anomalies">Sparse categories stay unflagged by design.</EmptyState>
        ) : <EmptyState icon="alert" title="Awaiting a snapshot">Anomalies are computed with the versioned snapshot.</EmptyState>}
      </Panel>
    </div>
  );
}

function Onboarding({ hasAccount, busy, onLoadSample, onNavigate }: { hasAccount: boolean; busy: boolean; onLoadSample: () => void; onNavigate: (view: View) => void }) {
  const steps = [
    { title: "Create a private account", detail: "An empty INR ledger. No balance is invented.", done: hasAccount },
    { title: "Import a statement", detail: "Content-validated CSV or supported text PDF with traceable parsing.", done: false },
    { title: "Run deterministic analysis", detail: "Snapshot, recurrence, anomalies and a 30/60/90-day forecast.", done: false },
    { title: "Ask the verified advisor", detail: "Mesh-powered specialists, checked by plain-code verification.", done: false }
  ];
  return (
    <div className="view-grid">
      <Panel className="span-7 onboarding">
        <p className="eyebrow">GET STARTED</p>
        <h2 className="display">Bring a statement.<br />FinPilot shows its work.</h2>
        <p className="lede">Every number on the next screen comes from rows you import. The workspace starts empty; use your CSV or supported PDF, or explicitly select the fictional demo file.</p>
        <div className="button-row">
          <button className="btn btn-primary btn-lg" onClick={onLoadSample} disabled={busy}><Icon name="flask" size={16} />{busy ? "Importing…" : "Use fictional demo CSV"}</button>
          <button className="btn btn-glass btn-lg" onClick={() => onNavigate("ledger")}><Icon name="upload" size={16} />Upload my statement</button>
        </div>
        <a className="text-link" href={SAMPLE_STATEMENT.path} download><Icon name="download" size={14} />Download the upload-ready CSV (30 fictional rows)</a>
      </Panel>
      <Panel className="span-5">
        <PanelHeader eyebrow="CHECKLIST" title="Four steps to a verified answer" />
        <ol className="checklist">
          {steps.map((step, index) => (
            <li key={step.title} className={step.done ? "done" : ""}>
              <span>{step.done ? <Icon name="check" size={14} /> : index + 1}</span>
              <div><b>{step.title}</b><small>{step.detail}</small></div>
            </li>
          ))}
        </ol>
        <div className="sample-facts">
          <Pill tone="info" icon="flask">Synthetic</Pill>
          <span>Jul–Oct 2026 · 30 clean rows with salary, rent, subscriptions, transfers, a refund and an unusual medical expense.</span>
        </div>
      </Panel>
    </div>
  );
}
