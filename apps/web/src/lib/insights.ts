import type { Transaction } from "./types";

export type CategorySlice = { key: string; value: number; count: number };
export type MonthFlow = { key: string; income: number; spend: number };
export type MerchantSpend = { name: string; value: number; count: number; category: string };
export type BalancePoint = { day: string; balance: number };

export type Insights = {
  income: number;
  spend: number;
  net: number;
  rate: number;
  categories: CategorySlice[];
  months: MonthFlow[];
  dailySpend: Map<string, number>;
  merchants: MerchantSpend[];
  balances: BalancePoint[];
  firstDay: string | null;
  lastDay: string | null;
  needsReview: number;
  excluded: number;
};

/**
 * End-of-day balance from source-provided running balances. Within a day the API
 * does not preserve statement order, so the closing row is the one whose balance
 * is not the opening balance (balance − amount) of any other row that day.
 */
function closingBalance(rows: Transaction[]): number | null {
  const known = rows.filter((row) => row.balance_minor !== null);
  if (!known.length) return null;
  const openings = new Set(known.map((row) => (row.balance_minor as number) - row.amount_minor));
  const closing = known.find((row) => !openings.has(row.balance_minor as number)) ?? known[known.length - 1];
  return closing.balance_minor;
}

export function deriveInsights(transactions: Transaction[]): Insights {
  const included = transactions.filter((item) => !item.is_excluded_from_cashflow);
  let income = 0;
  let spend = 0;
  const categories = new Map<string, CategorySlice>();
  const months = new Map<string, MonthFlow>();
  const dailySpend = new Map<string, number>();
  const merchants = new Map<string, MerchantSpend>();
  const byDay = new Map<string, Transaction[]>();

  for (const item of transactions) {
    const rows = byDay.get(item.transaction_date) ?? [];
    rows.push(item);
    byDay.set(item.transaction_date, rows);
  }

  for (const item of included) {
    const monthKey = item.transaction_date.slice(0, 7);
    const month = months.get(monthKey) ?? { key: monthKey, income: 0, spend: 0 };
    if (item.amount_minor > 0 && item.kind !== "refund") {
      income += item.amount_minor;
      month.income += item.amount_minor;
    }
    if (item.amount_minor < 0) {
      const value = Math.abs(item.amount_minor);
      spend += value;
      month.spend += value;
      dailySpend.set(item.transaction_date, (dailySpend.get(item.transaction_date) ?? 0) + value);
      const slice = categories.get(item.category) ?? { key: item.category, value: 0, count: 0 };
      slice.value += value;
      slice.count += 1;
      categories.set(item.category, slice);
      const merchant = merchants.get(item.merchant_normalized) ?? { name: item.merchant_normalized, value: 0, count: 0, category: item.category };
      merchant.value += value;
      merchant.count += 1;
      merchants.set(item.merchant_normalized, merchant);
    }
    months.set(monthKey, month);
  }

  const days = [...byDay.keys()].sort();
  const balances: BalancePoint[] = [];
  for (const day of days) {
    const balance = closingBalance(byDay.get(day) ?? []);
    if (balance !== null) balances.push({ day, balance });
  }

  const net = income - spend;
  return {
    income,
    spend,
    net,
    rate: income ? Math.round((Math.max(net, 0) / income) * 100) : 0,
    categories: [...categories.values()].sort((a, b) => b.value - a.value),
    months: [...months.values()].sort((a, b) => a.key.localeCompare(b.key)),
    dailySpend,
    merchants: [...merchants.values()].sort((a, b) => b.value - a.value).slice(0, 6),
    balances,
    firstDay: days[0] ?? null,
    lastDay: days[days.length - 1] ?? null,
    needsReview: transactions.filter((item) => item.classification_method === "mesh_required").length,
    excluded: transactions.length - included.length
  };
}
