import type { CategorySlice } from "@/lib/insights";
import { humanize } from "@/lib/format";
import type { View } from "@/lib/types";
import type { IconName } from "../ui/icons";

/* Colour follows the entity, never its rank: six featured spend categories own a
   fixed, validated slot; everything else folds into a neutral "Other". */
const CATEGORY_SLOTS: Record<string, string> = {
  housing: "var(--viz-1)",
  groceries: "var(--viz-2)",
  dining: "var(--viz-3)",
  transport: "var(--viz-4)",
  shopping: "var(--viz-5)",
  utilities: "var(--viz-6)"
};
export const OTHER_COLOR = "var(--viz-other)";

export function categoryColor(category: string) {
  return CATEGORY_SLOTS[category] ?? OTHER_COLOR;
}

export function categorySlices(categories: CategorySlice[]) {
  const featured = categories.filter((item) => item.key in CATEGORY_SLOTS);
  const folded = categories.filter((item) => !(item.key in CATEGORY_SLOTS));
  const slices = featured.map((item) => ({ key: item.key, label: humanize(item.key), value: item.value, color: categoryColor(item.key), detail: `${item.count} payments` }));
  if (folded.length) {
    slices.push({
      key: "other",
      label: "Other",
      value: folded.reduce((sum, item) => sum + item.value, 0),
      color: OTHER_COLOR,
      detail: folded.map((item) => humanize(item.key).toLowerCase()).join(", ")
    });
  }
  return slices;
}

export const KNOWN_CATEGORIES = [
  "housing", "groceries", "dining", "transport", "shopping", "utilities", "entertainment",
  "healthcare", "subscriptions", "education", "fees_and_charges", "salary", "other_income", "refund",
  "transfer", "fitness", "insurance", "uncategorized"
];

export const VIEWS: Array<{ id: View; label: string; icon: IconName; group: "Workspace" | "Assurance" | "Learn"; subtitle: string }> = [
  { id: "overview", label: "Overview", icon: "overview", group: "Workspace", subtitle: "Cash position, spending and signals" },
  { id: "ledger", label: "Ledger", icon: "ledger", group: "Workspace", subtitle: "Imported transactions and provenance" },
  { id: "forecast", label: "Forecast", icon: "forecast", group: "Workspace", subtitle: "Deterministic balance projection and what-ifs" },
  { id: "advice", label: "Advisor", icon: "advice", group: "Workspace", subtitle: "Verified recommendations from the agent graph" },
  { id: "audit", label: "Audit trail", icon: "audit", group: "Assurance", subtitle: "Every node, model call and decision" },
  { id: "governance", label: "Governance", icon: "governance", group: "Assurance", subtitle: "Registry, risks, evaluations and oversight" },
  { id: "digests", label: "Digests", icon: "digests", group: "Assurance", subtitle: "Durable weekly check-ins" },
  { id: "system", label: "How it works", icon: "system", group: "Learn", subtitle: "Architecture and trace replay" }
];

export const STAGES = [
  ["import", "Import"], ["categorize", "Categorize"], ["analyze", "Analyze"],
  ["forecast", "Forecast"], ["advise", "Advise"], ["verify", "Verify"]
] as const;

export type StageId = (typeof STAGES)[number][0];

export const SCENARIO_PRESETS = [
  { label: "Laptop", name: "Laptop purchase", amount: "75000.00" },
  { label: "Family trip", name: "Family trip", amount: "180000.00" },
  { label: "Car down payment", name: "Car down payment", amount: "350000.00" }
] as const;
