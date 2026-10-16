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
