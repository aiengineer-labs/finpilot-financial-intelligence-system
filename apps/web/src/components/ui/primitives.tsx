import type { CSSProperties, ReactNode } from "react";
import { Icon, type IconName } from "./icons";
import { Sparkline } from "./charts";

export function Panel({ children, className = "", as: Tag = "section" }: { children: ReactNode; className?: string; as?: "section" | "article" | "div" | "aside" }) {
  return <Tag className={`glass panel ${className}`}>{children}</Tag>;
}

export function PanelHeader({ eyebrow, title, subtitle, actions, icon }: { eyebrow?: string; title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; icon?: IconName }) {
  return (
    <header className="panel-head">
      <div className="panel-title">
        {icon && <span className="panel-icon"><Icon name={icon} size={16} /></span>}
        <div>
          {eyebrow && <p className="eyebrow">{eyebrow}</p>}
          <h2>{title}</h2>
          {subtitle && <p className="panel-subtitle">{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="panel-actions">{actions}</div>}
    </header>
  );
}

export type Tone = "good" | "warn" | "bad" | "info" | "neutral";

const toneIcon: Record<Tone, IconName> = { good: "check", warn: "alert", bad: "close", info: "info", neutral: "info" };

export function Pill({ tone = "neutral", children, icon, withIcon = false }: { tone?: Tone; children: ReactNode; icon?: IconName; withIcon?: boolean }) {
  const glyph = icon ?? (withIcon ? toneIcon[tone] : undefined);
  return <span className={`pill tone-${tone}`}>{glyph && <Icon name={glyph} size={12} />}{children}</span>;
}

export function StatTile({ label, value, detail, tone, trend, icon }: { label: string; value: ReactNode; detail?: ReactNode; tone?: "good" | "bad"; trend?: number[]; icon?: IconName }) {
  return (
    <article className="glass stat">
      <div className="stat-top">
        <span className="stat-label">{icon && <Icon name={icon} size={14} />}{label}</span>
        {trend && trend.length > 1 && <Sparkline values={trend} width={64} />}
      </div>
      <strong className={`stat-value ${tone ?? ""}`}>{value}</strong>
      {detail && <small className="stat-detail">{detail}</small>}
    </article>
  );
}

export function Segmented<T extends string | number>({ options, value, onChange, label, size = "md" }: { options: Array<{ value: T; label: ReactNode }>; value: T; onChange: (value: T) => void; label: string; size?: "sm" | "md" }) {
  const index = Math.max(0, options.findIndex((option) => option.value === value));
  return (
    <div className={`segmented ${size}`} role="radiogroup" aria-label={label} style={{ "--count": options.length, "--index": index } as CSSProperties}>
      <span className="segmented-thumb" aria-hidden="true" />
      {options.map((option) => (
        <button key={String(option.value)} type="button" role="radio" aria-checked={option.value === value} className={option.value === value ? "active" : ""} onClick={() => onChange(option.value)}>
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function Switch({ checked, onChange, label, disabled }: { checked: boolean; onChange: (checked: boolean) => void; label: string; disabled?: boolean }) {
  return (
    <button type="button" role="switch" aria-checked={checked} aria-label={label} className="switch" disabled={disabled} onClick={() => onChange(!checked)}>
      <span />
    </button>
  );
}

export function Ring({ value, size = 92, stroke = 9, label, tone = "accent" }: { value: number; size?: number; stroke?: number; label?: ReactNode; tone?: "accent" | "good" | "warn" | "bad" }) {
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.min(Math.max(value, 0), 100);
  return (
    <div className={`ring ring-${tone}`} style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`${clamped}%`}>
        <circle className="ring-track" cx={size / 2} cy={size / 2} r={radius} strokeWidth={stroke} />
        <circle className="ring-fill" cx={size / 2} cy={size / 2} r={radius} strokeWidth={stroke} strokeDasharray={circumference} strokeDashoffset={circumference * (1 - clamped / 100)} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      </svg>
      <div className="ring-label">{label ?? `${clamped}%`}</div>
    </div>
  );
}

export function Meter({ value, tone }: { value: number; tone?: "good" | "warn" | "bad" }) {
  const clamped = Math.min(Math.max(value, 0), 100);
  const resolved = tone ?? (clamped >= 80 ? "good" : clamped >= 55 ? "warn" : "bad");
  return <span className={`meter meter-${resolved}`} role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={clamped}><i style={{ width: `${clamped}%` }} /></span>;
}

export function EmptyState({ icon, title, children, action }: { icon: IconName; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty">
      <span className="empty-icon"><Icon name={icon} size={26} /></span>
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action}
    </div>
  );
}

export function Avatar({ label, hue }: { label: string; hue: number }) {
  const initials = label.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join("") || "?";
  return <span className="avatar" style={{ "--hue": hue } as CSSProperties} aria-hidden="true">{initials}</span>;
}

export function hueFor(value: string) {
  let hash = 0;
  for (const char of value) hash = (hash * 31 + char.charCodeAt(0)) % 360;
  return hash;
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="kbd">{children}</kbd>;
}
