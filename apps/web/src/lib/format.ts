const formatters = new Map<string, Intl.NumberFormat>();

function formatter(key: string, options: Intl.NumberFormatOptions) {
  let cached = formatters.get(key);
  if (!cached) {
    cached = new Intl.NumberFormat("en-IN", options);
    formatters.set(key, cached);
  }
  return cached;
}

/** Display-only rendering of integer minor units; never used for authoritative maths. */
export function money(minor: number, currency = "INR", fractionDigits = 0) {
  return formatter(`money:${currency}:${fractionDigits}`, {
    style: "currency", currency, minimumFractionDigits: fractionDigits, maximumFractionDigits: fractionDigits
  }).format(minor / 100);
}

export function exactMoney(minor: number, currency = "INR") {
  return money(minor, currency, 2);
}

export function compactMoney(minor: number, currency = "INR") {
  return formatter(`compact:${currency}`, {
    style: "currency", currency, notation: "compact", maximumFractionDigits: 1
  }).format(minor / 100);
}

export function signedMoney(minor: number, currency = "INR") {
  const value = money(Math.abs(minor), currency);
  return minor > 0 ? `+${value}` : minor < 0 ? `−${value}` : value;
}

export function minorFromRupees(value: string): number {
  const normalized = value.trim().replaceAll(",", "");
  if (!/^\d+(\.\d{1,2})?$/.test(normalized)) throw new Error("Use a positive amount with at most two decimals");
  const [whole, fraction = ""] = normalized.split(".");
  return Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
}

function utc(iso: string) {
  return new Date(`${iso.slice(0, 10)}T00:00:00Z`);
}

export function shortDate(iso: string) {
  return utc(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", timeZone: "UTC" });
}

export function longDate(iso: string) {
  return utc(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

export function monthLabel(key: string) {
  return utc(`${key}-01`).toLocaleDateString("en-IN", { month: "short", timeZone: "UTC" });
}

export function weekday(iso: string) {
  return utc(iso).toLocaleDateString("en-IN", { weekday: "short", timeZone: "UTC" });
}

export function addDays(iso: string, days: number) {
  const date = utc(iso);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export function dayDiff(from: string, to: string) {
  return Math.round((utc(to).getTime() - utc(from).getTime()) / 86_400_000);
}

export function humanize(value: string) {
  const text = value.replaceAll("_", " ").trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function titleCase(value: string) {
  return value.replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function percentFromBps(bps: number) {
  return `${Math.round(bps / 100)}%`;
}

export function dateTime(iso: string) {
  return new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}
