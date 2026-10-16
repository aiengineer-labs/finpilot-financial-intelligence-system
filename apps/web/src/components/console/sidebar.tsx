"use client";

import { useState } from "react";
import type { Tenant, View } from "@/lib/types";
import { Icon } from "../ui/icons";
import { Avatar, Pill, hueFor } from "../ui/primitives";
import { Brand } from "./auth-screen";
import { STAGES, type StageId, VIEWS } from "./shared";

type Props = {
  tenant: Tenant;
  view: View;
  open: boolean;
  badges: Partial<Record<View, number>>;
  completed: Set<StageId>;
  demoIdentity: { email: string; password: string } | null;
  onNavigate: (view: View) => void;
  onClose: () => void;
  onSignOut: () => void;
};

export function Sidebar({ tenant, view, open, badges, completed, demoIdentity, onNavigate, onClose, onSignOut }: Props) {
  const [copied, setCopied] = useState(false);
  const groups = ["Workspace", "Assurance", "Learn"] as const;
  const progress = Math.round((completed.size / STAGES.length) * 100);

  async function copyPassword() {
    if (!demoIdentity) return;
    try {
      await navigator.clipboard.writeText(demoIdentity.password);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  }

  return (
    <aside className={`glass sidebar ${open ? "open" : ""}`} aria-label="Primary navigation">
      <div className="sidebar-head">
        <Brand />
        <button className="icon-btn ghost sidebar-close" onClick={onClose} aria-label="Close navigation"><Icon name="close" size={15} /></button>
      </div>

      <div className="household">
        <Avatar label={tenant.name} hue={hueFor(tenant.name)} />
        <div><b>{tenant.name}</b><small>{tenant.role} · private tenant</small></div>
      </div>

      <nav className="nav">
        {groups.map((group) => (
          <div key={group} className="nav-group">
            <span className="nav-label">{group}</span>
            {VIEWS.filter((item) => item.group === group).map((item) => (
              <button key={item.id} className={view === item.id ? "active" : ""} aria-current={view === item.id ? "page" : undefined} onClick={() => { onNavigate(item.id); onClose(); }}>
                <Icon name={item.icon} size={17} />
                <span>{item.label}</span>
                {badges[item.id] ? <em>{badges[item.id]}</em> : null}
              </button>
            ))}
          </div>
        ))}
      </nav>

      <div className="sidebar-foot">
        {demoIdentity && (
          <div className="demo-card">
            <Pill tone="info" icon="flask">Synthetic demo</Pill>
            <small title={demoIdentity.email}>{demoIdentity.email}</small>
            <button className="btn btn-glass btn-sm" onClick={copyPassword}><Icon name={copied ? "check" : "copy"} size={13} />{copied ? "Copied" : "Copy password"}</button>
          </div>
        )}
        <div className="pipeline-card">
          <div className="pipeline-head"><b>Pipeline</b><span>{completed.size}/{STAGES.length}</span></div>
          <div className="progress"><i style={{ width: `${progress}%` }} /></div>
          <ol className="stage-list">
            {STAGES.map(([id, label]) => <li key={id} className={completed.has(id) ? "done" : ""}><span>{completed.has(id) ? <Icon name="check" size={11} /> : null}</span>{label}</li>)}
          </ol>
        </div>
        <button className="nav-signout" onClick={onSignOut}><Icon name="logout" size={16} />Sign out</button>
      </div>
    </aside>
  );
}
