"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const DEFAULT_MAPPING = JSON.stringify(
  {
    date: "Date",
    date_format: "%d/%m/%Y",
    debit: "Debit",
    credit: "Credit",
    merchant: "Merchant",
    description: "Description",
    transaction_id: "Transaction ID",
    currency: "Currency",
    balance: "Balance"
  },
  null,
  2
);

type Tenant = { id: string; name: string };
type Account = { id: string; name: string; currency: string };
type Transaction = {
  id: string;
  transaction_date: string;
  amount_minor: number;
  currency: string;
  merchant_normalized: string;
  description: string;
  kind: string;
  category: string;
  classification_method: string;
  is_excluded_from_cashflow: boolean;
};
type UploadSummary = {
  accepted_rows: number;
  rejected_rows: number;
  duplicate_rows: number;
  replayed: boolean;
  row_errors: Array<{ row: number; message: string }>;
};

export function TransactionWorkspace() {
  const [token, setToken] = useState("");
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [mapping, setMapping] = useState(DEFAULT_MAPPING);
  const [summary, setSummary] = useState<UploadSummary | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function api(path: string, init: RequestInit = {}, selectedTenant = tenant?.id) {
    const headers = new Headers(init.headers);
    if (token) headers.set("Authorization", `Bearer ${token}`);
    if (selectedTenant) headers.set("X-Tenant-ID", selectedTenant);
    return fetch(`${API_BASE}${path}`, { ...init, headers });
  }

  async function loadTransactions(activeToken: string, activeTenant: Tenant) {
    const response = await fetch(`${API_BASE}/api/v1/transactions`, {
      headers: {
        Authorization: `Bearer ${activeToken}`,
        "X-Tenant-ID": activeTenant.id
      }
    });
    if (!response.ok) throw new Error("Could not load transactions");
    const page = (await response.json()) as { items: Transaction[] };
    setTransactions(page.items);
  }

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      const login = await fetch(`${API_BASE}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: form.get("email"), password: form.get("password") })
      });
      if (!login.ok) throw new Error("Sign-in failed");
      const accessToken = ((await login.json()) as { access_token: string }).access_token;
      const identity = await fetch(`${API_BASE}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${accessToken}` }
      });
      if (!identity.ok) throw new Error("Could not load identity");
      const me = (await identity.json()) as { tenants: Tenant[] };
      if (!me.tenants.length) throw new Error("No household membership is available");
      const activeTenant = me.tenants[0];
      const accountResponse = await fetch(`${API_BASE}/api/v1/accounts`, {
        headers: { Authorization: `Bearer ${accessToken}`, "X-Tenant-ID": activeTenant.id }
      });
      if (!accountResponse.ok) throw new Error("Could not load accounts");
      setToken(accessToken);
      setTenant(activeTenant);
      setAccounts((await accountResponse.json()) as Account[]);
      await loadTransactions(accessToken, activeTenant);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unexpected sign-in error");
    } finally {
      setBusy(false);
    }
  }

  async function createAccount() {
    if (!tenant) return;
    setBusy(true);
    setError("");
    try {
      const response = await api("/api/v1/accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: "Primary account",
          currency: "INR",
          external_reference: crypto.randomUUID()
        })
      });
      if (!response.ok) throw new Error("Could not create account");
      setAccounts([(await response.json()) as Account]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unexpected account error");
    } finally {
      setBusy(false);
    }
  }

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!tenant || !accounts[0]) return;
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    form.set("mapping", mapping);
    try {
      JSON.parse(mapping);
      const response = await api(
        `/api/v1/accounts/${accounts[0].id}/transaction-uploads`,
        { method: "POST", body: form }
      );
      if (!response.ok) {
        const detail = (await response.json()) as { detail?: string };
        throw new Error(detail.detail ?? "CSV upload failed");
      }
      setSummary((await response.json()) as UploadSummary);
      await loadTransactions(token, tenant);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unexpected upload error");
    } finally {
      setBusy(false);
    }
  }

  if (!token || !tenant) {
    return (
      <main className="workspace-shell">
        <Link className="back-link" href="/">← FinPilot</Link>
        <section className="auth-card">
          <p className="eyebrow">SECURE WORKSPACE</p>
          <h1>Sign in to your household.</h1>
          <p className="lede">Credentials are exchanged for a short-lived token held only in memory.</p>
          <form className="stack-form" onSubmit={signIn}>
            <label>Email<input name="email" type="email" autoComplete="email" required /></label>
            <label>Password<input name="password" type="password" autoComplete="current-password" required /></label>
            <button className="primary" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
          </form>
          {error && <p className="form-error" role="alert">{error}</p>}
        </section>
      </main>
    );
  }

  return (
    <main className="workspace-shell">
      <header className="workspace-header">
        <div><Link className="back-link" href="/">← FinPilot</Link><h1>Transaction truth</h1></div>
        <div className="header-actions"><Link className="secondary nav-button" href="/forecast">Forecast studio →</Link><span className="badge online">{tenant.name}</span></div>
      </header>

      {!accounts.length ? (
        <section className="workspace-card empty-panel">
          <h2>No financial account yet</h2>
          <p>Create an empty INR account before importing a statement. No balance is invented.</p>
          <button className="primary" onClick={createAccount} disabled={busy}>Create primary account</button>
        </section>
      ) : (
        <section className="workspace-grid">
          <form className="workspace-card stack-form" onSubmit={upload}>
            <div><p className="eyebrow">CSV INGESTION</p><h2>Import a statement</h2></div>
            <label>CSV file<input name="file" type="file" accept=".csv,text/csv" required /></label>
            <label>Column mapping<textarea value={mapping} onChange={(event) => setMapping(event.target.value)} rows={14} spellCheck={false} /></label>
            <button className="primary" disabled={busy}>{busy ? "Validating…" : "Validate and import"}</button>
            <p className="form-note">Dates are explicit. Amounts use exact minor units. Replays do not duplicate the ledger.</p>
          </form>

          <section className="workspace-card">
            <p className="eyebrow">IMPORT RESULT</p>
            <h2>{summary ? (summary.replayed ? "Already imported" : "Import complete") : "Awaiting a file"}</h2>
            {summary && <div className="result-grid"><b>{summary.accepted_rows}<span>accepted</span></b><b>{summary.duplicate_rows}<span>duplicates</span></b><b>{summary.rejected_rows}<span>rejected</span></b></div>}
            {summary?.row_errors.map((item) => <p className="row-error" key={`${item.row}-${item.message}`}>Row {item.row}: {item.message}</p>)}
            {error && <p className="form-error" role="alert">{error}</p>}
          </section>
        </section>
      )}

      <section className="workspace-card transaction-table-wrap">
        <div className="table-heading"><div><p className="eyebrow">PERSISTED LEDGER</p><h2>{transactions.length} transactions</h2></div><span>Transfers excluded from cash flow</span></div>
        {!transactions.length ? <p className="empty-state">No imported transactions.</p> : (
          <table><thead><tr><th>Date</th><th>Merchant</th><th>Category</th><th>Type</th><th>Amount</th></tr></thead>
          <tbody>{transactions.map((transaction) => <tr key={transaction.id}><td>{transaction.transaction_date}</td><td><b>{transaction.merchant_normalized}</b><small>{transaction.description}</small></td><td>{transaction.category}<small>{transaction.classification_method}</small></td><td>{transaction.kind}{transaction.is_excluded_from_cashflow && <small>excluded</small>}</td><td className={transaction.amount_minor > 0 ? "positive" : "negative"}>{new Intl.NumberFormat("en-IN", { style: "currency", currency: transaction.currency }).format(transaction.amount_minor / 100)}</td></tr>)}</tbody></table>
        )}
      </section>
    </main>
  );
}
