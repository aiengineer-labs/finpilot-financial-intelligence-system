"use client";

import { humanize } from "@/lib/format";
import type { Account, Tenant, View } from "@/lib/types";
import { Icon } from "../ui/icons";
import { Avatar, hueFor } from "../ui/primitives";
import { Brand } from "./brand";
import { STAGES, type StageId, VIEWS } from "./shared";

type Props = {
  tenant: Tenant;
  accounts: Account[];
  activeAccountId: string | undefined;
  busy: boolean;
  onSwitchAccount: (accountId: string) => void;
  view: View | null;
  open: boolean;
  badges: Partial<Record<View, number>>;
  completed: Set<StageId>;
  onNavigate: (view: View) => void;
  onClose: () => void;
};

export function Sidebar({ tenant, accounts, activeAccountId, busy, onSwitchAccount, view, open, badges, completed, onNavigate, onClose }: Props) {
  const groups = ["Workspace", "Assurance", "Learn"] as const;
  const progress = Math.round((completed.size / STAGES.length) * 100);

  return (
    <aside className={`glass sidebar ${open ? "open" : ""}`} aria-label="Primary navigation">
      <div className="sidebar-head">
        <Brand />
        <button className="icon-btn ghost sidebar-close" onClick={onClose} aria-label="Close navigation"><Icon name="close" size={15} /></button>
      </div>

      <div className="household">
        <Avatar label={tenant.name} hue={hueFor(tenant.name)} />
        <div><b>{tenant.name}</b><small>Financial analysis</small></div>
      </div>

      {accounts.length > 1 && (
        <label className="field account-field">
          <span>Active account</span>
          <select value={activeAccountId} disabled={busy} onChange={(event) => onSwitchAccount(event.target.value)}>
            {accounts.map((account) => <option key={account.id} value={account.id}>{account.account_type === "unknown" ? account.name : `${account.name} · ${humanize(account.account_type)}`}</option>)}
          </select>
        </label>
      )}

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
        <div className={`pipeline-card ${busy ? "live" : ""}`}>
          <div className="pipeline-head"><b><Icon name="advice" size={13} />Agent pipeline</b><span>{completed.size}/{STAGES.length}</span></div>
          <div className="progress"><i style={{ width: `${progress}%` }} /></div>
          <ol className="stage-list">
            {STAGES.map(([id, label]) => <li key={id} className={completed.has(id) ? "done" : ""}><span>{completed.has(id) ? <Icon name="check" size={11} /> : null}</span>{label}</li>)}
          </ol>
        </div>
      </div>
    </aside>
  );
}
