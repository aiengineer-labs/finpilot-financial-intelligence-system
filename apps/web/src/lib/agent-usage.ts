import type { AgentEvent } from "./types";

function nonNegativeInteger(value: unknown) {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0 ? value : 0;
}

function decimal(value: unknown) {
  const text = typeof value === "string" || typeof value === "number" ? String(value) : "";
  return /^\d+(\.\d+)?$/.test(text) ? text : null;
}

/** Add provider-reported USD decimals exactly without binary floating-point arithmetic. */
function sumDecimals(values: string[]) {
  if (!values.length) return null;
  const scale = Math.max(...values.map((value) => value.split(".")[1]?.length ?? 0));
  const factor = 10n ** BigInt(scale);
  const total = values.reduce((sum, value) => {
    const [whole, fraction = ""] = value.split(".");
    return sum + BigInt(whole) * factor + BigInt(fraction.padEnd(scale, "0") || "0");
  }, 0n);
  if (!scale) return total.toString();
  const fraction = (total % factor).toString().padStart(scale, "0").replace(/0+$/, "");
  return fraction ? `${total / factor}.${fraction}` : (total / factor).toString();
}

export function eventUsage(event: AgentEvent) {
  return {
    costUsd: decimal(event.details.cost_usd),
    cachedInputTokens: nonNegativeInteger(event.details.cached_input_tokens),
    reasoningTokens: nonNegativeInteger(event.details.reasoning_tokens)
  };
}

export function summarizeAgentUsage(events: AgentEvent[]) {
  const usage = events.filter((event) => event.model_id).map(eventUsage);
  return {
    costUsd: sumDecimals(usage.flatMap((item) => item.costUsd ? [item.costUsd] : [])),
    cachedInputTokens: usage.reduce((sum, item) => sum + item.cachedInputTokens, 0),
    reasoningTokens: usage.reduce((sum, item) => sum + item.reasoningTokens, 0)
  };
}

export function usd(value: string | null) {
  return value === null ? "Not reported" : `$${value}`;
}
