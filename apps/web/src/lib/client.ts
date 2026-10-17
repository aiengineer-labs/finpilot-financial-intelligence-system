export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");

export const SAMPLE_STATEMENT = {
  path: "/samples/finpilot-demo-bank-statement.csv",
  filename: "finpilot-demo-bank-statement.csv"
} as const;

/** Explicit bank column mapping for the bundled synthetic statement format. */
export const DEFAULT_MAPPING = JSON.stringify({
  date: "Date", date_format: "%d/%m/%Y", debit: "Debit", credit: "Credit",
  merchant: "Merchant", description: "Description", transaction_id: "Transaction ID",
  currency: "Currency", balance: "Balance"
});

type Detail = string | { code?: string; message?: string; statement_kind?: string } | Array<{ msg?: string; loc?: Array<string | number> }> | undefined;

/** A failed API call, keeping the stable error code so callers can recover deliberately. */
export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly code?: string, readonly statementKind?: string) {
    super(message);
    this.name = "ApiError";
  }
}

function describe(detail: Detail, status: number) {
  if (typeof detail === "string") return detail;
  if (detail && !Array.isArray(detail)) return detail.message ?? detail.code ?? `Request failed (${status})`;
  if (Array.isArray(detail) && detail.length) {
    return detail.map((item) => [item.loc?.slice(1).join("."), item.msg].filter(Boolean).join(": ")).join("; ");
  }
  return `Request failed (${status})`;
}

export type Session = { token: string; tenantId?: string };

export async function request<T>(path: string, init: RequestInit = {}, session?: Session): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (session?.token) headers.set("Authorization", `Bearer ${session.token}`);
  if (session?.tenantId) headers.set("X-Tenant-ID", session.tenantId);
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  } catch {
    throw new Error("FinPilot API is unavailable through the application gateway");
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: Detail };
    const detail = body.detail && typeof body.detail === "object" && !Array.isArray(body.detail) ? body.detail : undefined;
    throw new ApiError(describe(body.detail, response.status), response.status, detail?.code, detail?.statement_kind);
  }
  return (await response.json()) as T;
}
