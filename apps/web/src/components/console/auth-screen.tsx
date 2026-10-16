"use client";

import { type FormEvent, useState } from "react";
import { Icon, type IconName } from "../ui/icons";
import { Segmented } from "../ui/primitives";
import { ThemeToggle } from "../ui/theme";

const FEATURES: Array<{ icon: IconName; title: string; detail: string }> = [
  { icon: "lock", title: "Exact money math", detail: "Integer minor units. Models never do arithmetic." },
  { icon: "governance", title: "Fail-closed advice", detail: "A plain-code verifier gates every recommendation." },
  { icon: "audit", title: "Complete lineage", detail: "Every node, model call and decision is persisted." }
];

type Props = {
  busy: "auth" | "demo" | null;
  error: string;
  onAuthenticate: (mode: "login" | "register", form: FormData) => void;
  onStartDemo: () => void;
  onShowSystem: () => void;
};

export function AuthScreen({ busy, error, onAuthenticate, onStartDemo, onShowSystem }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onAuthenticate(mode, new FormData(event.currentTarget));
  }

  return (
    <div className="auth-shell">
      <header className="auth-topbar">
        <Brand />
        <div className="button-row">
          <button className="btn btn-plain" onClick={onShowSystem}><Icon name="system" size={15} />How it works</button>
          <ThemeToggle />
        </div>
      </header>
      <main className="auth-layout">
        <section className="auth-hero">
          <p className="eyebrow">NEURO-SYMBOLIC FINANCIAL DECISION INTELLIGENCE</p>
          <h1>See the math.<br />Watch the agents.<br /><span className="gradient-text">Trust the evidence.</span></h1>
          <p className="lede">Import a statement, branch a what-if scenario, and inspect every deterministic calculation and Mesh-powered handoff.</p>
          <div className="feature-grid">
            {FEATURES.map((feature) => (
              <article key={feature.title} className="glass feature-card">
                <span className="panel-icon"><Icon name={feature.icon} size={16} /></span>
                <b>{feature.title}</b>
                <small>{feature.detail}</small>
              </article>
            ))}
          </div>
        </section>

        <section className="glass-strong auth-card" aria-label="Authentication">
          <Segmented label="Authentication mode" value={mode} onChange={setMode} options={[{ value: "login", label: "Sign in" }, { value: "register", label: "Register" }]} />
          <div>
            <h2>{mode === "login" ? "Welcome back" : "Create a private household"}</h2>
            <p className="muted">{mode === "login" ? "Continue to your tenant-isolated workspace." : "You become the owner of a new, isolated tenant."}</p>
          </div>
          <form className="auth-form" onSubmit={submit}>
            {mode === "register" && <label className="field">Household name<input name="household" required minLength={2} maxLength={120} autoComplete="organization" /></label>}
            <label className="field">Email<input name="email" type="email" required autoComplete="email" /></label>
            <label className="field">Password<input name="password" type="password" minLength={mode === "register" ? 12 : 1} required autoComplete={mode === "login" ? "current-password" : "new-password"} /></label>
            <button className="btn btn-primary btn-lg btn-block" disabled={busy !== null}>{busy === "auth" ? "Authenticating…" : mode === "login" ? "Open workspace" : "Create household"}</button>
          </form>
          {error && <p className="form-error" role="alert"><Icon name="alert" size={14} />{error}</p>}
          <div className="divider"><span>or explore safely</span></div>
          <button className="demo-button" onClick={onStartDemo} disabled={busy !== null}>
            <span className="demo-icon"><Icon name="flask" size={18} /></span>
            <span><b>{busy === "demo" ? "Preparing synthetic household…" : "Start synthetic demo"}</b><small>Registers a fresh private household with generated credentials and imports 141 fictional rows through the real pipeline.</small></span>
            <Icon name="chevronRight" size={16} />
          </button>
          <small className="fine-print"><Icon name="lock" size={12} />Access tokens stay in memory. Financial data is only returned for your authorized tenant.</small>
        </section>
      </main>
    </div>
  );
}

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className="brand">
      <span className="brand-mark" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 16l5-6 4 3 7-8" /><path d="M4 20h16" /></svg>
      </span>
      {!compact && <div><b>FinPilot</b><small>Decision intelligence</small></div>}
    </div>
  );
}
