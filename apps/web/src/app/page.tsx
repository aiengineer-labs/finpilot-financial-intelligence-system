import { StatusCard } from "@/components/status-card";
import { getHealth } from "@/lib/api";

export default async function Home() {
  const health = await getHealth();

  return (
    <main>
      <nav>
        <a className="brand" href="#top" aria-label="FinPilot home">
          <span>FP</span> FinPilot
        </a>
        <span className="phase">Foundation · Phase 1</span>
      </nav>

      <section className="hero" id="top">
        <div>
          <p className="eyebrow">NEURO-SYMBOLIC FINANCIAL INTELLIGENCE</p>
          <h1>Know what your money can safely do next.</h1>
          <p className="lede">
            Deterministic financial truth, contextual Mesh-powered reasoning, and an audit trail
            for every recommendation.
          </p>
          <div className="actions">
            <a className="primary" href="#system-status">Inspect system</a>
            <a className="secondary" href="http://localhost:8000/docs">API contract</a>
          </div>
        </div>
        <aside className="trust-panel">
          <p>Trust boundary</p>
          <ul>
            <li><b>Math</b><span>Deterministic</span></li>
            <li><b>Reasoning</b><span>Mesh only</span></li>
            <li><b>Access</b><span>Tenant scoped</span></li>
            <li><b>Actions</b><span>Read-only</span></li>
          </ul>
        </aside>
      </section>

      <section className="status" id="system-status" aria-labelledby="status-heading">
        <header>
          <div>
            <p className="eyebrow">LIVE FOUNDATION CHECK</p>
            <h2 id="status-heading">System status</h2>
          </div>
          <span className={health ? "badge online" : "badge offline"}>
            {health ? "API reachable" : "API unavailable"}
          </span>
        </header>
        <div className="status-grid">
          <StatusCard label="API" value={health?.status ?? "offline"} tone={health ? "good" : "warning"} />
          <StatusCard label="Financial data" value="No data yet" />
          <StatusCard label="Model route" value="Mesh enforced" tone="good" />
          <StatusCard label="Money actions" value="Disabled" tone="good" />
        </div>
        <p className="empty-state">
          This is an honest foundation state. Upload, forecasting, scenarios, and agent views will
          appear only when their real backend slices are implemented and verified.
        </p>
      </section>
    </main>
  );
}
