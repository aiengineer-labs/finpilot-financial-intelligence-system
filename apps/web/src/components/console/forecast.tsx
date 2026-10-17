import { addDays, compactMoney, dayDiff, exactMoney, humanize, longDate, money, percentFromBps, shortDate, signedMoney, titleCase } from "@/lib/format";

/** Engine assumptions quote integer minor units; render those figures as rupees for reading. */
function readable(assumption: string) {
  return assumption.replace(/(-?\d+) minor units(\/day)?/g, (_, value: string, perDay?: string) => `${exactMoney(Number(value))}${perDay ? " per day" : ""}`);
}
import type { Forecast, Scenario, Snapshot, SpendingSummary } from "@/lib/types";
import { type ChartMarker, LineChart } from "../ui/charts";
import { Icon } from "../ui/icons";
import { EmptyState, Meter, Panel, PanelHeader, Pill, Segmented, StatTile, Switch } from "../ui/primitives";
import { SCENARIO_PRESETS } from "./shared";

export type RunConfig = {
  asOf: string; horizon: number; scenarioEnabled: boolean; scenarioName: string;
  scenarioAmount: string; scenarioDate: string;
};

type Props = {
  config: RunConfig;
  setConfig: (patch: Partial<RunConfig>) => void;
  snapshot: Snapshot | null;
  forecast: Forecast | null;
  scenario: Scenario | null;
  spendingOnly: boolean;
  canRun: boolean;
  busy: boolean;
  onRunAnalysis: () => void;
  onAskAdvisor: () => void;
};

export function ForecastView({ config, setConfig, snapshot, forecast, scenario, spendingOnly, canRun, busy, onRunAnalysis, onAskAdvisor }: Props) {
  const minDate = config.asOf ? addDays(config.asOf, 1) : undefined;
  const maxDate = config.asOf ? addDays(config.asOf, config.horizon) : undefined;
  const spendingSnapshot = snapshot?.analysis_mode === "spending" ? snapshot : null;
  return (
    <div className="view-grid">
      <Panel className="span-12 composer">
        <PanelHeader eyebrow="RUN CONFIGURATION" title={spendingOnly ? "Analyse spending" : "Compose a projection"} subtitle={spendingOnly ? "Card or balance-free statement · recurrence and anomalies · no balance is invented" : "Integer minor-unit engine · no model call · every run is versioned"} icon="calendar" />
        <div className="composer-grid">
          <label className="field">{spendingOnly ? "Analysis date" : "Known-balance date"}<input type="date" value={config.asOf} onChange={(event) => setConfig({ asOf: event.target.value })} /></label>
          {!spendingOnly && <>
          <div className="field"><span>Horizon</span><Segmented label="Forecast horizon" value={config.horizon} onChange={(horizon) => setConfig({ horizon })} options={[{ value: 30, label: "30 days" }, { value: 60, label: "60 days" }, { value: 90, label: "90 days" }]} /></div>
          <div className="field switch-field"><span>What-if purchase</span><div><Switch checked={config.scenarioEnabled} onChange={(scenarioEnabled) => setConfig({ scenarioEnabled })} label="Include a what-if purchase" /><small>{config.scenarioEnabled ? "Branch from baseline" : "Baseline only"}</small></div></div>
          </>}
        </div>
        {config.scenarioEnabled && !spendingOnly && (
          <div className="composer-grid scenario-grid">
            <div className="field span-all"><span>Presets</span><div className="chip-row">{SCENARIO_PRESETS.map((preset) => <button key={preset.label} type="button" className={`chip ${config.scenarioAmount === preset.amount ? "active" : ""}`} onClick={() => setConfig({ scenarioName: preset.name, scenarioAmount: preset.amount })}>{preset.label}<small>{money(Number(preset.amount) * 100)}</small></button>)}</div></div>
            <label className="field">Scenario name<input value={config.scenarioName} maxLength={120} onChange={(event) => setConfig({ scenarioName: event.target.value })} /></label>
            <label className="field">Amount (₹)<input value={config.scenarioAmount} inputMode="decimal" onChange={(event) => setConfig({ scenarioAmount: event.target.value })} placeholder="75000.00" /></label>
            <label className="field">Purchase date<input type="date" value={config.scenarioDate} min={minDate} max={maxDate} onChange={(event) => setConfig({ scenarioDate: event.target.value })} /></label>
          </div>
        )}
        <div className="button-row end">
          <small className="muted">{!config.asOf ? "Import a statement to choose a date" : spendingOnly ? `Analyses every row up to ${shortDate(config.asOf)}` : `Projects ${shortDate(addDays(config.asOf, 1))} – ${shortDate(addDays(config.asOf, config.horizon))}`}</small>
          <button className="btn btn-glass" onClick={onAskAdvisor} disabled={busy || (!forecast && !spendingSnapshot)}><Icon name="advice" size={14} />Ask advisor</button>
          <button className="btn btn-primary" onClick={onRunAnalysis} disabled={busy || !canRun}><Icon name="play" size={13} />{busy ? "Calculating…" : spendingOnly ? "Analyse spending" : "Run analysis"}</button>
        </div>
      </Panel>

      {spendingSnapshot ? <SpendingResult snapshot={spendingSnapshot} /> : !forecast || !snapshot ? (
        <Panel className="span-12"><EmptyState icon="forecast" title={spendingOnly ? "No spending analysis yet" : "No forecast yet"}>{spendingOnly ? "This statement has no running balance (for example a credit-card statement), so FinPilot analyses spending, recurrence and anomalies. Cash forecasting needs a bank statement with balances." : "Select a known-balance date and run the analysis. Missing balances are never inferred."}</EmptyState></Panel>
      ) : <ForecastResult snapshot={snapshot} forecast={forecast} scenario={scenario} />}
    </div>
  );
}

function ForecastResult({ snapshot, forecast, scenario }: { snapshot: Snapshot; forecast: Forecast; scenario: Scenario | null }) {
  const days = forecast.points.map((point) => point.day);
  const series = [{ id: "baseline", label: "Baseline", values: forecast.points.map((point) => point.balance_minor), color: "var(--viz-1)", area: true }];
  if (scenario) series.push({ id: "scenario", label: scenario.name, values: scenario.points.map((point) => point.balance_minor), color: "var(--viz-2)", area: false });
  const markers: ChartMarker[] = [];
  const shockIndex = scenario ? scenario.points.findIndex((point, index) => point.balance_minor !== forecast.points[index]?.balance_minor) : -1;
  if (shockIndex >= 0) markers.push({ index: shockIndex, label: "Purchase", tone: "accent" });
  if (scenario?.first_shortfall_date) {
    const index = days.indexOf(scenario.first_shortfall_date);
    if (index >= 0 && index !== shockIndex) markers.push({ index, label: "Shortfall", tone: "bad" });
    else if (index >= 0) markers[markers.length - 1] = { index, label: "Purchase · shortfall", tone: "bad" };
  }
  const end = forecast.points[forecast.points.length - 1];
  const lowest = forecast.points.reduce((low, point) => (point.balance_minor < low.balance_minor ? point : low), forecast.points[0]);
  const runway = scenario?.first_shortfall_date ? dayDiff(snapshot.as_of, scenario.first_shortfall_date) : null;

  return (
    <>
      <div className="span-12 stat-row">
        <StatTile icon="wallet" label="Opening balance" value={compactMoney(forecast.opening_balance_minor)} detail={`Known on ${longDate(snapshot.as_of)}`} />
        <StatTile icon="forecast" label="Baseline low point" value={compactMoney(forecast.minimum_balance_minor)} detail={`${shortDate(lowest.day)} · ends at ${compactMoney(end.balance_minor)}`} />
        <StatTile icon="bolt" label="Scenario low point" value={scenario ? compactMoney(scenario.minimum_balance_minor) : "—"} tone={scenario ? (scenario.first_shortfall_date ? "bad" : "good") : undefined} detail={scenario ? (scenario.first_shortfall_date ? `Shortfall on ${shortDate(scenario.first_shortfall_date)}` : "No projected shortfall") : "Enable a what-if to compare"} />
        <StatTile icon="clock" label={runway !== null ? "Runway before shortfall" : "Ending change"} value={runway !== null ? `${runway} days` : scenario ? signedMoney(scenario.ending_delta_minor) : "—"} tone={runway !== null ? "bad" : undefined} detail="Baseline stays immutable" />
      </div>

      <Panel className="span-8">
        <PanelHeader eyebrow="DAILY PROJECTION" title={`${forecast.horizon_days}-day balance trajectory`} subtitle="Hover or use arrow keys to inspect any day" actions={<div className="legend-inline">{series.map((item) => <span key={item.id}><i className="line-key" style={{ background: item.color }} />{item.label}</span>)}</div>} />
        <LineChart days={days} series={series} markers={markers} ariaLabel={`Projected daily balance over ${forecast.horizon_days} days`} />
        {scenario && (
          <div className={`callout ${scenario.first_shortfall_date ? "bad" : "good"}`}>
            <Icon name={scenario.first_shortfall_date ? "alert" : "check"} size={16} />
            <p><b>{scenario.name}</b> {scenario.first_shortfall_date ? `drives the balance below zero on ${longDate(scenario.first_shortfall_date)}; the projected low is ${money(scenario.minimum_balance_minor)}.` : `keeps the projected low at ${money(scenario.minimum_balance_minor)} with no shortfall inside the horizon.`}</p>
          </div>
        )}
        <details className="data-table">
          <summary>View daily values</summary>
          <div className="table-scroll">
            <table><thead><tr><th>Day</th><th>Baseline</th>{scenario && <th>{scenario.name}</th>}<th>Recurring flow</th><th>Variable spend</th></tr></thead>
              <tbody>{forecast.points.map((point, index) => <tr key={point.day}><td>{shortDate(point.day)}</td><td>{exactMoney(point.balance_minor)}</td>{scenario && <td>{exactMoney(scenario.points[index]?.balance_minor ?? 0)}</td>}<td>{signedMoney(point.recurring_flow_minor)}</td><td>{money(point.estimated_variable_spend_minor)}</td></tr>)}</tbody></table>
          </div>
        </details>
      </Panel>

      <Panel className="span-4">
        <PanelHeader eyebrow="ASSUMPTIONS" title="What the curve means" />
        <ul className="assumptions">{forecast.assumptions.map((item) => <li key={item}><Icon name="info" size={14} /><span>{readable(item)}</span></li>)}</ul>
        <div className="evidence-strip">
          <Pill tone="info" icon="doc">{snapshot.source_transaction_count} source rows</Pill>
          <Pill tone="neutral" icon="lock">Snapshot {snapshot.id.slice(0, 8)}</Pill>
        </div>
      </Panel>

      {snapshot.spending && <SpendingBreakdown spending={snapshot.spending} />}
      <SnapshotEvidence snapshot={snapshot} recurringTitle="Recurring flows in the projection" />
    </>
  );
}

function SpendingResult({ snapshot }: { snapshot: Snapshot }) {
  const spending = snapshot.spending;
  return (
    <>
      <div className="span-12 stat-row">
        <StatTile icon="forecast" label="Projected 30-day spend" value={spending ? compactMoney(spending.projected_30_day_spend_minor) : "—"} detail={spending ? `At the ${spending.period_days}-day statement pace` : "Re-run the analysis"} />
        <StatTile icon="wallet" label="Average per day" value={spending ? money(spending.average_daily_spend_minor) : "—"} detail={spending ? `${money(spending.total_spend_minor)} spent ${shortDate(spending.period_start)} – ${shortDate(spending.period_end)}` : undefined} />
        <StatTile icon="bolt" label="Possible monthly saving" value={spending ? money(spending.combined_monthly_saving_minor) : "—"} tone="good" detail={spending ? `${spending.reduction_percent}% less in the top three categories` : undefined} />
        <StatTile icon="alert" label="Anomalies" value={snapshot.anomaly_results.length} detail={`${snapshot.source_transaction_count} rows analysed`} />
      </div>
      <Panel className="span-12">
        <div className="callout info"><Icon name="info" size={16} /><p>This statement has no running balance (for example a credit-card statement), so the forecast is a <b>spending projection</b> rather than a cash balance. The advisor recommends where to cut back, and every amount it cites is checked against these figures.</p></div>
      </Panel>
      {spending && <SpendingBreakdown spending={spending} />}
      <SnapshotEvidence snapshot={snapshot} recurringTitle="Recurring charges and credits" />
    </>
  );
}

function SpendingBreakdown({ spending }: { spending: SpendingSummary }) {
  return (
    <>
      <Panel className="span-7">
        <PanelHeader eyebrow="WHERE THE MONEY GOES" title="Top spending categories" subtitle={`Monthly pace and the saving from a ${spending.reduction_percent}% cut`} />
        {spending.categories.length ? (
          <div className="table-wrap"><table className="table compact">
            <thead><tr><th>Category</th><th>Share</th><th className="num">Per month</th><th className="num">Save {spending.reduction_percent}%</th></tr></thead>
            <tbody>{spending.categories.map((item) => <tr key={item.category}><td><b>{humanize(item.category)}</b><small className="muted"> · {item.transaction_count} payments</small></td><td><div className="provenance"><span>{percentFromBps(item.share_bps)}</span><Meter value={item.share_bps / 100} /></div></td><td className="num">{money(item.monthly_spend_minor)}</td><td className="num positive">{money(item.monthly_saving_minor)}</td></tr>)}</tbody>
          </table></div>
        ) : <EmptyState icon="overview" title="No spending in this period" />}
      </Panel>
      <Panel className="span-5">
        <PanelHeader eyebrow="MERCHANTS" title="Biggest merchants" subtitle={spending.savings_rate_bps !== null ? `Savings rate ${percentFromBps(spending.savings_rate_bps)} of inflow` : "Card spending by merchant"} />
        <ul className="signal-list">{spending.merchants.map((item) => <li key={item.merchant}><span className="signal-icon"><Icon name="wallet" size={15} /></span><div><b>{titleCase(item.merchant)}</b><small className="muted">{item.transaction_count} payments · {money(item.monthly_spend_minor)} per month</small></div><strong>{money(item.spend_minor)}</strong></li>)}</ul>
      </Panel>
    </>
  );
}

function SnapshotEvidence({ snapshot, recurringTitle }: { snapshot: Snapshot; recurringTitle: string }) {
  return (
    <>
      <Panel className="span-7">
        <PanelHeader eyebrow="RECURRENCE ENGINE" title={recurringTitle} subtitle={`${snapshot.recurring_patterns.length} patterns`} />
        {snapshot.recurring_patterns.length ? (
          <div className="table-wrap"><table className="table compact">
            <thead><tr><th>Merchant</th><th>Cadence</th><th>Confidence</th><th className="num">Typical</th></tr></thead>
            <tbody>{snapshot.recurring_patterns.map((pattern) => <tr key={pattern.id}><td><b>{titleCase(pattern.merchant)}</b></td><td>{humanize(pattern.cadence)}</td><td><div className="provenance"><span>{percentFromBps(pattern.confidence_bps)}</span><Meter value={pattern.confidence_bps / 100} /></div></td><td className={`num ${pattern.typical_amount_minor > 0 ? "positive" : ""}`}>{signedMoney(pattern.typical_amount_minor)}</td></tr>)}</tbody>
          </table></div>
        ) : <EmptyState icon="repeat" title="No recurring evidence" />}
      </Panel>

      <Panel className="span-5">
        <PanelHeader eyebrow="EXCLUDED FROM RECURRENCE" title="Anomaly evidence" subtitle="Robust outliers stay visible but are not projected" />
        {snapshot.anomaly_results.length ? (
          <ul className="signal-list">{snapshot.anomaly_results.map((item) => <li key={item.transaction_id}><span className={`signal-icon sev-${item.severity}`}><Icon name="alert" size={15} /></span><div><b>{humanize(item.explanation.split(" ")[0] ?? "Category")}</b><small className="muted">{item.explanation}</small></div><Pill tone={item.severity === "high" ? "bad" : "warn"} withIcon>{item.severity}</Pill></li>)}</ul>
        ) : <EmptyState icon="check" title="No anomalies in this snapshot" />}
      </Panel>
    </>
  );
}
