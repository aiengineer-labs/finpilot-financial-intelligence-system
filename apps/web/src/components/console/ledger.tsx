"use client";

import { type DragEvent, type FormEvent, useMemo, useRef, useState } from "react";
import { SAMPLE_STATEMENT } from "@/lib/client";
import { exactMoney, humanize, longDate, money, percentFromBps, shortDate, titleCase } from "@/lib/format";
import type { Transaction, UploadResult } from "@/lib/types";
import { Icon } from "../ui/icons";
import { Avatar, EmptyState, Meter, Panel, PanelHeader, Pill, Segmented, hueFor } from "../ui/primitives";
import { KNOWN_CATEGORIES, categoryColor } from "./shared";

type Kind = "all" | "income" | "spend" | "transfer";
type Sort = "newest" | "oldest" | "largest";
const PAGE = 25;

type Props = {
  transactions: Transaction[];
  total: number;
  hasAccount: boolean;
  busy: boolean;
  uploadResult: UploadResult | null;
  onUpload: (file: File) => void;
  onLoadSample: () => void;
  onCreateAccount: () => void;
  onCorrect: (transaction: Transaction, category: string, reason: string) => Promise<boolean>;
};

export function Ledger({ transactions, total, hasAccount, busy, uploadResult, onUpload, onLoadSample, onCreateAccount, onCorrect }: Props) {
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<Kind>("all");
  const [category, setCategory] = useState("all");
  const [sort, setSort] = useState<Sort>("newest");
  const [page, setPage] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const categories = useMemo(() => [...new Set(transactions.map((item) => item.category))].sort(), [transactions]);
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const rows = transactions.filter((item) => {
      if (kind === "income" && !(item.amount_minor > 0 && !item.is_excluded_from_cashflow)) return false;
      if (kind === "spend" && !(item.amount_minor < 0 && !item.is_excluded_from_cashflow)) return false;
      if (kind === "transfer" && !item.is_excluded_from_cashflow) return false;
      if (category !== "all" && item.category !== category) return false;
      return !needle || `${item.merchant_normalized} ${item.description} ${item.category}`.toLowerCase().includes(needle);
    });
    return rows.sort((a, b) => sort === "largest" ? Math.abs(b.amount_minor) - Math.abs(a.amount_minor) : sort === "oldest" ? a.transaction_date.localeCompare(b.transaction_date) : b.transaction_date.localeCompare(a.transaction_date));
  }, [transactions, query, kind, category, sort]);

  const pages = Math.max(1, Math.ceil(filtered.length / PAGE));
  const current = Math.min(page, pages - 1);
  const visible = filtered.slice(current * PAGE, current * PAGE + PAGE);
  const selected = transactions.find((item) => item.id === selectedId) ?? null;

  function resetPage<T>(setter: (value: T) => void) {
    return (value: T) => { setter(value); setPage(0); };
  }

  return (
    <div className="view-grid">
      <ImportPanel hasAccount={hasAccount} busy={busy} uploadResult={uploadResult} onUpload={onUpload} onLoadSample={onLoadSample} onCreateAccount={onCreateAccount} />

      <Panel className="span-12 ledger-panel">
        <PanelHeader eyebrow="TRANSACTION TRUTH" title={`${total} persisted rows`} subtitle={total > transactions.length ? `Showing the latest ${transactions.length}; summaries cover loaded rows only.` : "Human corrections keep their lineage"} />
        <div className="toolbar-row">
          <label className="search-field"><Icon name="search" size={15} /><input value={query} onChange={(event) => resetPage(setQuery)(event.target.value)} placeholder="Search merchant, description or category" aria-label="Search transactions" /></label>
          <Segmented size="sm" label="Transaction type" value={kind} onChange={resetPage(setKind)} options={[{ value: "all", label: "All" }, { value: "income", label: "In" }, { value: "spend", label: "Out" }, { value: "transfer", label: "Transfers" }]} />
          <select className="select" value={category} onChange={(event) => resetPage(setCategory)(event.target.value)} aria-label="Filter by category">
            <option value="all">All categories</option>
            {categories.map((item) => <option key={item} value={item}>{humanize(item)}</option>)}
          </select>
          <select className="select" value={sort} onChange={(event) => setSort(event.target.value as Sort)} aria-label="Sort transactions">
            <option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="largest">Largest amount</option>
          </select>
        </div>
        {!transactions.length ? <EmptyState icon="ledger" title="No ledger rows yet">Import a statement above, or load the synthetic sample.</EmptyState> : !filtered.length ? <EmptyState icon="search" title="Nothing matches these filters" /> : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Date</th><th>Merchant</th><th>Category</th><th>Provenance</th><th className="num">Amount</th><th className="num hide-sm">Balance</th></tr></thead>
              <tbody>
                {visible.map((item) => (
                  <tr key={item.id} tabIndex={0} onClick={() => setSelectedId(item.id)} onKeyDown={(event) => { if (event.key === "Enter") setSelectedId(item.id); }} className={selectedId === item.id ? "selected" : ""}>
                    <td className="nowrap">{shortDate(item.transaction_date)}</td>
                    <td><div className="merchant-cell"><Avatar label={item.merchant_normalized} hue={hueFor(item.merchant_normalized)} /><div><b>{titleCase(item.merchant_normalized)}</b><small>{item.description || "—"}</small></div></div></td>
                    <td><span className="category-tag"><i style={{ background: categoryColor(item.category) }} />{humanize(item.category)}</span></td>
                    <td><div className="provenance"><span>{humanize(item.classification_method)}</span><Meter value={item.classification_confidence_bps / 100} /></div></td>
                    <td className={`num ${item.amount_minor >= 0 ? "positive" : ""}`}>{exactMoney(item.amount_minor, item.currency)}{item.is_excluded_from_cashflow && <small>excluded</small>}</td>
                    <td className="num hide-sm muted">{item.balance_minor === null ? "unknown" : money(item.balance_minor, item.currency)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {filtered.length > PAGE && (
          <footer className="pager">
            <span>{current * PAGE + 1}–{Math.min(filtered.length, current * PAGE + PAGE)} of {filtered.length}</span>
            <div>
              <button className="icon-btn" onClick={() => setPage(current - 1)} disabled={current === 0} aria-label="Previous page"><Icon name="chevronLeft" size={15} /></button>
              <button className="icon-btn" onClick={() => setPage(current + 1)} disabled={current >= pages - 1} aria-label="Next page"><Icon name="chevronRight" size={15} /></button>
            </div>
          </footer>
        )}
      </Panel>

      {selected && <TransactionSheet key={selected.id} transaction={selected} busy={busy} onClose={() => setSelectedId(null)} onCorrect={onCorrect} />}
    </div>
  );
}

function ImportPanel({ hasAccount, busy, uploadResult, onUpload, onLoadSample, onCreateAccount }: Pick<Props, "hasAccount" | "busy" | "uploadResult" | "onUpload" | "onLoadSample" | "onCreateAccount">) {
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  function drop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files[0];
    if (file && hasAccount && !busy) onUpload(file);
  }

  return (
    <>
      <Panel className="span-7">
        <PanelHeader eyebrow="CSV INGESTION" title="Import a statement" subtitle="Validated for encoding, explicit dates, exact amounts, duplicates and transfers" />
        {!hasAccount ? (
          <EmptyState icon="bank" title="No financial account yet" action={<button className="btn btn-primary" onClick={onCreateAccount} disabled={busy}><Icon name="plus" size={14} />Create primary account</button>}>Create an empty INR account first. No balance is invented.</EmptyState>
        ) : (
          <div className={`dropzone ${dragging ? "dragging" : ""}`} onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={drop}>
            <span className="dropzone-icon"><Icon name="upload" size={24} /></span>
            <b>Drop a CSV statement here</b>
            <small>UTF-8 · up to 5 MiB / 10,000 rows · columns Date, Debit, Credit, Merchant, Description, Transaction ID, Currency, Balance</small>
            <div className="button-row">
              <button className="btn btn-glass" onClick={() => input.current?.click()} disabled={busy}><Icon name="doc" size={14} />Choose file</button>
              <button className="btn btn-primary" onClick={onLoadSample} disabled={busy}><Icon name="bolt" size={14} />{busy ? "Working…" : "Use synthetic sample"}</button>
            </div>
            <a className="text-link" href={SAMPLE_STATEMENT.path} download><Icon name="download" size={13} />Download sample CSV</a>
            <input ref={input} type="file" accept=".csv,text/csv" hidden onChange={(event) => { const file = event.target.files?.[0]; if (file) onUpload(file); event.target.value = ""; }} />
          </div>
        )}
      </Panel>
      <Panel className="span-5">
        <PanelHeader eyebrow="LAST IMPORT" title={uploadResult ? (uploadResult.replayed ? "Already imported" : "Import complete") : "Awaiting a file"} subtitle={uploadResult ? `${uploadResult.filename} · ${uploadResult.total_rows} source rows` : "Replays of the same file never duplicate the ledger."} />
        {uploadResult ? (
          <>
            <div className="counter-row">
              <div className="counter good"><strong>{uploadResult.accepted_rows}</strong><span>accepted</span></div>
              <div className="counter warn"><strong>{uploadResult.duplicate_rows}</strong><span>duplicates</span></div>
              <div className="counter bad"><strong>{uploadResult.rejected_rows}</strong><span>rejected</span></div>
            </div>
            {uploadResult.replayed && <p className="note"><Icon name="repeat" size={14} />Identical upload detected — the existing import was returned unchanged.</p>}
            {uploadResult.row_errors.length > 0 && (
              <ul className="row-errors">
                {uploadResult.row_errors.slice(0, 6).map((item, index) => <li key={index}><Pill tone="bad">Row {String(item.row ?? "?")}</Pill><span>{String(item.message ?? item.code ?? "Invalid row")}</span></li>)}
              </ul>
            )}
          </>
        ) : <EmptyState icon="inbox" title="No import in this session" />}
      </Panel>
    </>
  );
}

function TransactionSheet({ transaction, busy, onClose, onCorrect }: { transaction: Transaction; busy: boolean; onClose: () => void; onCorrect: Props["onCorrect"] }) {
  const [category, setCategory] = useState(transaction.category);
  const [reason, setReason] = useState("");
  const options = [...new Set([...KNOWN_CATEGORIES, transaction.category])];

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (await onCorrect(transaction, category, reason)) setReason("");
  }

  return (
    <div className="sheet-backdrop" onPointerDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <aside className="sheet glass-strong" role="dialog" aria-modal="true" aria-label="Transaction detail" onKeyDown={(event) => { if (event.key === "Escape") onClose(); }}>
        <header className="sheet-head">
          <Avatar label={transaction.merchant_normalized} hue={hueFor(transaction.merchant_normalized)} />
          <div><h2>{titleCase(transaction.merchant_normalized)}</h2><small>{longDate(transaction.transaction_date)}</small></div>
          <button className="icon-btn" onClick={onClose} aria-label="Close detail" autoFocus><Icon name="close" size={16} /></button>
        </header>
        <strong className={`sheet-amount ${transaction.amount_minor >= 0 ? "positive" : ""}`}>{exactMoney(transaction.amount_minor, transaction.currency)}</strong>
        <dl className="kv detail-kv">
          <div><dt>Description</dt><dd>{transaction.description || "—"}</dd></div>
          <div><dt>Kind</dt><dd>{humanize(transaction.kind)}{transaction.is_excluded_from_cashflow && " · excluded from cash flow"}</dd></div>
          <div><dt>Category</dt><dd><span className="category-tag"><i style={{ background: categoryColor(transaction.category) }} />{humanize(transaction.category)}</span></dd></div>
          <div><dt>Classification</dt><dd>{humanize(transaction.classification_method)} · {percentFromBps(transaction.classification_confidence_bps)}</dd></div>
          <div><dt>Balance after</dt><dd>{transaction.balance_minor === null ? "Not provided by source" : exactMoney(transaction.balance_minor, transaction.currency)}</dd></div>
          <div><dt>Ledger ID</dt><dd><code>{transaction.id}</code></dd></div>
        </dl>
        <form className="correction" onSubmit={submit}>
          <p className="eyebrow">HUMAN CORRECTION</p>
          <label className="field">Category<select className="select" value={category} onChange={(event) => setCategory(event.target.value)}>{options.map((item) => <option key={item} value={item}>{humanize(item)}</option>)}</select></label>
          <label className="field">Reason<input value={reason} onChange={(event) => setReason(event.target.value)} minLength={3} maxLength={500} required placeholder="e.g. Gym membership is fitness" /></label>
          <button className="btn btn-primary" disabled={busy || category === transaction.category || reason.trim().length < 3}>Save correction</button>
          <small className="muted">The previous category is preserved as an immutable correction record.</small>
        </form>
      </aside>
    </div>
  );
}
